"""Company Ministry Routes — Agent & Supervisor ministry-scoped endpoints.

Endpoints:
  GET /ministry/company-debt/{company_id}  — Agent: debt detail for MY ministry's fee_type only
  GET /ministry/lookup                     — ONRC agent: national company lookup (read-only)

Security:
  - Ministry agents see ONLY their ministry's obligations (scoped by ministry_id)
  - ONRC agents see all companies but CANNOT modify them
  - All queries use parameterized SQL ($1, $2)
"""

import re
from typing import Any, Dict, List, Optional
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger

from app.database.connection import get_database
from app.modules.auth.middleware.auth_middleware import get_current_user
from app.modules.permissions.middleware.permission_middleware import permission_required
from app.modules.companies.services.agent_context import get_agent_ministry_id, get_agent_city_scope

router = APIRouter(tags=["Company Ministry"])


# ── Agent Ministry: Company Debt Detail ──────────────────────────────────────

@router.get("/ministry/company-debt/{company_id}")
async def get_company_debt_for_my_ministry(
    company_id: str,
    db=Depends(get_database),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _=Depends(permission_required("company.view")),
):
    """Get company's debt detail for the agent's ministry ONLY.

    Returns all obligations for the agent's ministry_id, with:
    - Per-obligation detail: amount, penalty, due_date, status, paid_at
    - Totals: total_due, total_paid, total_overdue, recovery_rate
    - Company basic info (name, NIF, zone)

    Agent of Tesoro sees ONLY fee_type='treasury_fee' obligations.
    Agent of Ayuntamiento sees ONLY fee_type='ayuntamiento_fee' obligations.
    """
    ministry_id = await get_agent_ministry_id(db, current_user.id)
    if not ministry_id:
        raise HTTPException(status_code=403, detail="No ministry assigned to your profile")

    # City scope — main office sees all, secondary site sees only their city
    city_scope = await get_agent_city_scope(db, current_user.id)

    # Company basic info + city scope check
    company = await db.fetchrow(
        """SELECT c.id, c.legal_name, c.nif, c.registration_number,
                  c.regimen_fiscal, c.commerce_type, c.is_active,
                  c.city_id,
                  ct.name AS city_name, cz.zone_code
           FROM companies c
           LEFT JOIN cities ct ON c.city_id = ct.id
           LEFT JOIN commerce_zones cz ON c.zone_id = cz.id
           WHERE c.id = $1""",
        UUID(company_id),
    )
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    # Enforce city scope — secondary site agents can't view companies outside their city
    if city_scope and company["city_id"] != city_scope:
        raise HTTPException(status_code=403, detail="Company is outside your zone")

    # Obligations for THIS ministry only (strict scoping)
    obligations = await db.fetch(
        """SELECT lo.id, lo.fee_type, lo.amount, lo.penalty_amount,
                  lo.due_date, lo.status, lo.paid_at,
                  lo.bundle_item_id,
                  cl.fiscal_year, cl.status AS license_status
           FROM license_obligations lo
           JOIN commercial_licenses cl ON lo.license_id = cl.id
           WHERE cl.company_id = $1 AND lo.ministry_id = $2
           ORDER BY cl.fiscal_year DESC, lo.due_date DESC""",
        UUID(company_id), ministry_id,
    )

    # Aggregate totals
    total_due = sum(float(r["amount"] or 0) for r in obligations)
    total_paid = sum(float(r["amount"] or 0) for r in obligations if r["status"] == "paid")
    total_overdue = sum(float(r["amount"] or 0) for r in obligations if r["status"] == "overdue")
    total_penalties = sum(float(r["penalty_amount"] or 0) for r in obligations)

    return {
        "company": dict(company),
        "ministry_id": ministry_id,
        "obligations": [dict(r) for r in obligations],
        "totals": {
            "total_due": total_due,
            "total_paid": total_paid,
            "total_overdue": total_overdue,
            "total_penalties": total_penalties,
            "balance": total_due - total_paid,
            "recovery_rate_pct": round(total_paid * 100 / total_due, 1) if total_due > 0 else 0,
            "obligation_count": len(obligations),
        },
    }


# ── ONRC Agent: National Company Lookup (read-only) ─────────────────────────

@router.get("/ministry/lookup")
async def lookup_company(
    q: str = Query(..., min_length=2, max_length=100, description="NIF, PE-XXXX, or company name"),
    db=Depends(get_database),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _=Depends(permission_required("company.view")),
):
    """Company lookup scoped to agent's city/zone.

    Search by NIF (exact or partial), registration_number (PE-XXXX), or legal_name.
    Returns basic info + existence status. Read-only — no modification possible.
    City scope: main office agents see all cities, secondary site agents see their city only.
    """
    # City scope — main office sees all, secondary site sees only their city
    city_scope = await get_agent_city_scope(db, current_user.id)

    q_trimmed = q.strip()
    q_upper = q_trimmed.upper()
    params: List[Any] = []
    conditions: List[str] = []
    idx = 1

    # NIF pattern: GE#####X or #####XX-## (e.g., GE97811B, 12345AB-01)
    _NIF_RE = re.compile(r'^GE\d{4,6}[A-Z]$|^\d{5}[A-Z]{2}-\d{2}$', re.IGNORECASE)

    # Determine search strategy based on input pattern
    if q_upper.startswith("PE-"):
        # Exact Padrón Empresarial registration number
        conditions.append(f"c.registration_number = ${idx}")
        params.append(q_upper)
        idx += 1
    elif _NIF_RE.match(q_upper):
        # Matches NIF pattern — exact match
        conditions.append(f"c.nif = ${idx}")
        params.append(q_upper)
        idx += 1
    else:
        # Name search — use websearch_to_tsquery (proper stemming) + ILIKE fallback
        escaped = q_trimmed.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        conditions.append(
            f"(c.search_vector @@ websearch_to_tsquery('spanish', ${idx})"
            f" OR c.legal_name ILIKE ${idx + 1}"
            f" OR c.nif ILIKE ${idx + 1}"
            f" OR c.registration_number ILIKE ${idx + 1})"
        )
        params.append(q_trimmed)
        params.append(f"%{escaped}%")
        idx += 2

    # City scope filter — secondary site agents see only their city
    if city_scope:
        conditions.append(f"c.city_id = ${idx}")
        params.append(city_scope)
        idx += 1

    where = " AND ".join(conditions)

    rows = await db.fetch(
        f"""SELECT c.id, c.legal_name, c.nif, c.registration_number,
                   c.forma_juridica, c.regimen_fiscal, c.commerce_type,
                   c.is_active, c.is_verified,
                   ct.name AS city_name, cz.zone_code
            FROM companies c
            LEFT JOIN cities ct ON c.city_id = ct.id
            LEFT JOIN commerce_zones cz ON c.zone_id = cz.id
            WHERE {where}
            ORDER BY c.legal_name ASC
            LIMIT 20""",
        *params,
    )

    return {
        "results": [dict(r) for r in rows],
        "count": len(rows),
        "query": q.strip(),
    }
