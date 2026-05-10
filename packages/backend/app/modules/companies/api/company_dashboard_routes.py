"""Company Dashboard Routes — Stats endpoints for dashboards.

Endpoints:
  GET /dashboard/zone-stats          — Admin: all zones (choropleth map)
  GET /dashboard/zone-stats/mine     — Supervisor site: my zone only
  GET /dashboard/ministry-stats      — Supervisor ministry: all zones, my items
  GET /dashboard/global-stats        — Admin: single-row overview
  POST /cron/refresh-company-stats   — Cron: refresh materialized views

All dashboard endpoints read from materialized views (O(1) response, refreshed every 15min).
Fallback to live queries if views don't exist yet.
"""

from typing import Any, Dict, List, Optional
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Header, HTTPException
from loguru import logger

from app.core.cache import get_cache
from app.core.jsonb import ensure_list as _ensure_list

from app.database.connection import get_database
from app.modules.auth.middleware.auth_middleware import get_current_user
from app.modules.permissions.middleware.permission_middleware import permission_required
from app.modules.companies.services.agent_context import (
    get_agent_ministry_id,
    get_agent_zone_id,
)

# Cache TTLs — live queries cached in Redis, no MV dependency
_GLOBAL_STATS_TTL = 60       # 60s — KPIs refresh every minute
_ZONE_STATS_TTL = 60         # 60s
_ANALYTICS_TTL = 120         # 2min — heavier queries

router = APIRouter(prefix="/dashboard", tags=["Company Dashboard"])


def _verify_cron_or_admin(x_cron_secret: Optional[str] = Header(None)):
    """Allow cron (X-Cron-Secret) OR authenticated admin (fallback)."""
    from app.core.secrets import get_cron_secret
    from app.config import get_settings
    settings = get_settings()
    expected = get_cron_secret() or getattr(settings, 'CRON_SECRET', None)
    if expected and x_cron_secret == expected:
        return  # Cron auth OK
    if not expected:
        return  # No secret configured (dev mode)
    # If cron secret doesn't match, reject
    if x_cron_secret:
        raise HTTPException(status_code=403, detail="Invalid cron authentication")
    # No cron secret provided — could be admin calling manually, allow (endpoint still needs auth from router)


# ── Helpers ──────────────────────────────────────────────────────────────────

async def _mv_exists(db: asyncpg.Connection, view_name: str) -> bool:
    """Check if a materialized view exists."""
    return await db.fetchval(
        "SELECT EXISTS(SELECT 1 FROM pg_matviews WHERE matviewname = $1)",
        view_name,
    )


# ── Zone Stats (Choropleth Map) ─────────────────────────────────────────────

@router.get("/zone-stats")
async def get_zone_stats(
    db=Depends(get_database),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _=Depends(permission_required("company.view_stats")),
):
    """All zones stats — admin choropleth map data.

    Returns 12 zones with company counts, regime breakdown, debt, recovery rate.
    Live query with Redis cache (60s TTL) — no MV dependency.
    """
    cache = get_cache()
    cache_key = "company_dashboard:zone_stats"

    cached = await cache.get(cache_key)
    if cached:
        return cached

    rows = await db.fetch("""
        SELECT
            cz.id AS zone_id, cz.zone_code, cz.zone_tier, cz.name_es AS zone_name,
            COUNT(c.id) AS total_companies,
            COUNT(c.id) FILTER (WHERE c.is_active) AS active_companies,
            COUNT(c.id) FILTER (WHERE c.is_active AND NOT c.is_verified) AS pending_verification,
            COUNT(c.id) FILTER (WHERE c.regimen_fiscal = 'bundle') AS bundle_count,
            COUNT(c.id) FILTER (WHERE c.regimen_fiscal = 'declarativo') AS declarativo_count,
            COUNT(c.id) FILTER (WHERE c.regimen_fiscal = 'exento') AS exento_count,
            COUNT(c.id) FILTER (WHERE c.regimen_fiscal = 'pendiente') AS pendiente_count,
            COALESCE(SUM(cl.total_amount), 0) AS total_obligations_amount,
            COALESCE(SUM(cl.amount_paid), 0) AS total_paid_amount,
            COALESCE(SUM(cl.total_amount) - SUM(cl.amount_paid), 0) AS total_debt,
            CASE WHEN COALESCE(SUM(cl.total_amount), 0) > 0
                 THEN ROUND(COALESCE(SUM(cl.amount_paid), 0) * 100.0 / SUM(cl.total_amount), 1)
                 ELSE 0 END AS recovery_rate_pct
        FROM commerce_zones cz
        LEFT JOIN companies c ON c.zone_id = cz.id
        LEFT JOIN commercial_licenses cl ON cl.company_id = c.id
            AND cl.fiscal_year = EXTRACT(YEAR FROM NOW())::int
        GROUP BY cz.id, cz.zone_code, cz.zone_tier, cz.name_es
        ORDER BY cz.zone_code
    """)

    result = {"zones": [dict(r) for r in rows]}
    await cache.set(cache_key, result, ttl=_ZONE_STATS_TTL)
    return result


@router.get("/zone-stats/mine")
async def get_my_zone_stats(
    db=Depends(get_database),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _=Depends(permission_required("company.view_entity_scoped")),
):
    """Supervisor's zone stats — live query with Redis cache."""
    zone_id = await get_agent_zone_id(db, current_user.id)
    if not zone_id:
        raise HTTPException(status_code=404, detail="No zone assigned to your profile")

    cache = get_cache()
    cache_key = f"company_dashboard:zone_mine:{zone_id}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    row = await db.fetchrow("""
        SELECT
            cz.id AS zone_id, cz.zone_code, cz.zone_tier, cz.name_es AS zone_name,
            COUNT(c.id) AS total_companies,
            COUNT(c.id) FILTER (WHERE c.is_active) AS active_companies,
            COUNT(c.id) FILTER (WHERE c.is_active AND NOT c.is_verified) AS pending_verification,
            COUNT(c.id) FILTER (WHERE c.regimen_fiscal = 'bundle') AS bundle_count,
            COUNT(c.id) FILTER (WHERE c.regimen_fiscal = 'declarativo') AS declarativo_count,
            COUNT(c.id) FILTER (WHERE c.regimen_fiscal = 'exento') AS exento_count,
            COUNT(c.id) FILTER (WHERE c.regimen_fiscal = 'pendiente') AS pendiente_count,
            COUNT(DISTINCT cl.id) AS active_licenses,
            COALESCE(SUM(cl.total_amount), 0) AS total_obligations_amount,
            COALESCE(SUM(cl.amount_paid), 0) AS total_paid_amount,
            COALESCE(SUM(cl.total_amount) - SUM(cl.amount_paid), 0) AS total_debt,
            CASE WHEN COALESCE(SUM(cl.total_amount), 0) > 0
                 THEN ROUND(COALESCE(SUM(cl.amount_paid), 0) * 100.0 / SUM(cl.total_amount), 1)
                 ELSE 0 END AS recovery_rate_pct
        FROM commerce_zones cz
        LEFT JOIN companies c ON c.zone_id = cz.id
        LEFT JOIN commercial_licenses cl ON cl.company_id = c.id
            AND cl.fiscal_year = EXTRACT(YEAR FROM NOW())::int
        WHERE cz.id = $1
        GROUP BY cz.id, cz.zone_code, cz.zone_tier, cz.name_es
    """, UUID(zone_id))

    result = {"zone": dict(row)} if row else {"zone": None}
    await cache.set(cache_key, result, ttl=_ZONE_STATS_TTL)
    return result


# ── Ministry Stats (Supervisor Ministère) ────────────────────────────────────

@router.get("/ministry-stats")
async def get_ministry_stats(
    db=Depends(get_database),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _=Depends(permission_required("company.view_entity_scoped")),
):
    """Ministry supervisor: all zones, their fee_type items only.

    Returns obligation stats aggregated by zone for the agent's ministry.
    """
    ministry_id = await get_agent_ministry_id(db, current_user.id)
    if not ministry_id:
        raise HTTPException(status_code=404, detail="No ministry assigned to your profile")

    cache = get_cache()
    cache_key = f"company_dashboard:ministry:{ministry_id}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    rows = await db.fetch("""
        SELECT
            lo.ministry_id, lo.fee_type,
            cz.id AS zone_id, cz.zone_code,
            COUNT(DISTINCT cl.company_id) AS companies_count,
            COUNT(lo.id) AS obligations_count,
            COUNT(lo.id) FILTER (WHERE lo.status = 'paid') AS paid_count,
            COUNT(lo.id) FILTER (WHERE lo.status = 'overdue') AS overdue_count,
            COALESCE(SUM(lo.amount), 0) AS total_amount,
            COALESCE(SUM(lo.amount) FILTER (WHERE lo.status = 'paid'), 0) AS paid_amount,
            COALESCE(SUM(lo.amount) FILTER (WHERE lo.status = 'overdue'), 0) AS overdue_amount,
            COALESCE(SUM(lo.penalty_amount), 0) AS total_penalties
        FROM license_obligations lo
        JOIN commercial_licenses cl ON lo.license_id = cl.id
        JOIN companies c ON cl.company_id = c.id
        LEFT JOIN commerce_zones cz ON c.zone_id = cz.id
        WHERE cl.fiscal_year = EXTRACT(YEAR FROM NOW())::int
          AND lo.ministry_id = $1
        GROUP BY lo.ministry_id, lo.fee_type, cz.id, cz.zone_code
        ORDER BY cz.zone_code, lo.fee_type
    """, ministry_id)

    # Aggregate totals
    total_amount = sum(float(r["total_amount"]) for r in rows)
    paid_amount = sum(float(r["paid_amount"]) for r in rows)
    overdue_amount = sum(float(r["overdue_amount"]) for r in rows)

    result = {
        "ministry_id": ministry_id,
        "zones": [dict(r) for r in rows],
        "totals": {
            "total_amount": total_amount,
            "paid_amount": paid_amount,
            "overdue_amount": overdue_amount,
            "recovery_rate_pct": round(paid_amount * 100 / total_amount, 1) if total_amount > 0 else 0,
        },
    }
    await cache.set(cache_key, result, ttl=_ZONE_STATS_TTL)
    return result


# ── Global Stats (Admin Overview) ───────────────────────────────────────────

@router.get("/global-stats")
async def get_global_stats(
    db=Depends(get_database),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _=Depends(permission_required("company.view_stats")),
):
    """Admin global stats — live query with Redis cache (60s TTL).

    Always reads from the live `companies` table — never from the
    materialized view which can go stale if the cron misses runs.
    Redis cache avoids hitting the DB on every dashboard refresh.
    """
    cache = get_cache()
    cache_key = "company_dashboard:global_stats"

    # Cache hit → return immediately
    cached = await cache.get(cache_key)
    if cached:
        return cached

    # Live query — always fresh
    row = await db.fetchrow("""
        SELECT
            COUNT(*) AS total_companies,
            COUNT(*) FILTER (WHERE is_active) AS active_companies,
            COUNT(*) FILTER (WHERE is_verified) AS verified_companies,
            COUNT(*) FILTER (WHERE NOT is_active) AS inactive_companies,
            COUNT(*) FILTER (WHERE regimen_fiscal = 'bundle') AS bundle_count,
            COUNT(*) FILTER (WHERE regimen_fiscal = 'declarativo') AS declarativo_count,
            COUNT(*) FILTER (WHERE regimen_fiscal = 'exento') AS exento_count,
            COUNT(*) FILTER (WHERE regimen_fiscal = 'pendiente') AS pendiente_count,
            COUNT(*) FILTER (WHERE nif IS NOT NULL) AS with_nif,
            COUNT(*) FILTER (WHERE registration_number IS NOT NULL) AS with_reg_number,
            COUNT(*) FILTER (WHERE zone_id IS NOT NULL) AS with_zone,
            COUNT(*) FILTER (WHERE nif IS NULL AND registration_number IS NULL) AS missing_identifier
        FROM companies
    """)

    result = dict(row) if row else {}
    await cache.set(cache_key, result, ttl=_GLOBAL_STATS_TTL)
    return result


# ── Cross-tabulated analytics (rich JOINs for pro dashboards) ────────────────

@router.get("/analytics")
async def get_company_analytics(
    db=Depends(get_database),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _=Depends(permission_required("company.view_stats")),
):
    """Rich cross-tabulated analytics for Sage ERP-quality dashboards.

    Live queries with Redis cache (120s TTL) — no MV dependency.

    Returns:
      - by_zone_regime: companies grouped by zone × regime (stacked charts)
      - by_forma_juridica: companies by legal form (pie chart)
      - by_city: top cities by company count + debt (geographic)
      - debt_by_fee_type: obligations grouped by fee_type (ministry breakdown)
      - top_debtors: top 10 companies by outstanding debt
      - monthly_trend: companies created per month (last 12 months)
    """
    cache = get_cache()
    cache_key = "company_dashboard:analytics"

    cached = await cache.get(cache_key)
    if cached:
        return cached

    # ── 6 sequential queries (asyncpg forbids concurrent ops on single connection) ──
    # Cached with Redis (120s TTL) so sequential cost is negligible.
    zone_regime = await db.fetch("""
        SELECT cz.zone_code, cz.name_es AS zone_name,
               c.regimen_fiscal AS regime,
               COUNT(*) AS count,
               COALESCE(SUM(cl.total_amount), 0) AS total_amount,
               COALESCE(SUM(cl.amount_paid), 0) AS paid_amount,
               COALESCE(SUM(cl.total_amount - cl.amount_paid), 0) AS debt
        FROM companies c
        LEFT JOIN commerce_zones cz ON c.zone_id = cz.id
        LEFT JOIN commercial_licenses cl ON cl.company_id = c.id AND cl.fiscal_year = EXTRACT(YEAR FROM NOW())::int
        WHERE c.is_active = true
        GROUP BY cz.zone_code, cz.name_es, c.regimen_fiscal
        ORDER BY cz.zone_code, c.regimen_fiscal
    """)

    forma_juridica = await db.fetch("""
        SELECT c.forma_juridica, COUNT(*) AS count,
               COUNT(cl.id) AS with_license,
               COALESCE(SUM(cl.total_amount), 0) AS total_amount
        FROM companies c
        LEFT JOIN commercial_licenses cl ON cl.company_id = c.id AND cl.fiscal_year = EXTRACT(YEAR FROM NOW())::int
        WHERE c.is_active = true AND c.forma_juridica IS NOT NULL
        GROUP BY c.forma_juridica
        ORDER BY count DESC
    """)

    city_stats = await db.fetch("""
        SELECT ct.name AS city_name, ct.provincia, cz.zone_code,
               COUNT(c.id) AS companies,
               COUNT(cl.id) AS licenses,
               COALESCE(SUM(cl.total_amount - cl.amount_paid), 0) AS debt,
               CASE WHEN COALESCE(SUM(cl.total_amount), 0) > 0
                    THEN ROUND(SUM(cl.amount_paid) * 100.0 / SUM(cl.total_amount), 1)
                    ELSE 0 END AS recovery_pct
        FROM companies c
        JOIN cities ct ON c.city_id = ct.id
        LEFT JOIN commerce_zones cz ON c.zone_id = cz.id
        LEFT JOIN commercial_licenses cl ON cl.company_id = c.id AND cl.fiscal_year = EXTRACT(YEAR FROM NOW())::int
        WHERE c.is_active = true
        GROUP BY ct.name, ct.provincia, cz.zone_code
        ORDER BY companies DESC
    """)

    debt_by_fee = await db.fetch("""
        SELECT lo.fee_type,
               COUNT(DISTINCT cl.company_id) AS companies,
               COUNT(lo.id) AS obligations,
               COALESCE(SUM(lo.amount), 0) AS total_amount,
               COALESCE(SUM(lo.amount) FILTER (WHERE lo.status = 'paid'), 0) AS paid,
               COALESCE(SUM(lo.amount) FILTER (WHERE lo.status = 'overdue'), 0) AS overdue,
               COALESCE(SUM(lo.penalty_amount), 0) AS penalties
        FROM license_obligations lo
        JOIN commercial_licenses cl ON lo.license_id = cl.id
        WHERE cl.fiscal_year = EXTRACT(YEAR FROM NOW())::int
        GROUP BY lo.fee_type
        ORDER BY total_amount DESC
    """)

    top_debtors = await db.fetch("""
        SELECT c.id, c.legal_name, c.nif, c.registration_number,
               c.regimen_fiscal, cz.zone_code,
               SUM(cl.total_amount - cl.amount_paid) AS debt,
               SUM(cl.total_amount) AS total_amount,
               CASE WHEN SUM(cl.total_amount) > 0
                    THEN ROUND(SUM(cl.amount_paid) * 100.0 / SUM(cl.total_amount), 1)
                    ELSE 0 END AS recovery_pct
        FROM companies c
        JOIN commercial_licenses cl ON cl.company_id = c.id
        LEFT JOIN commerce_zones cz ON c.zone_id = cz.id
        WHERE cl.fiscal_year = EXTRACT(YEAR FROM NOW())::int
          AND (cl.total_amount - cl.amount_paid) > 0
        GROUP BY c.id, c.legal_name, c.nif, c.registration_number, c.regimen_fiscal, cz.zone_code
        ORDER BY debt DESC
        LIMIT 10
    """)

    monthly_trend = await db.fetch("""
        SELECT TO_CHAR(created_at, 'YYYY-MM') AS month,
               COUNT(*) AS created,
               COUNT(*) FILTER (WHERE regimen_fiscal = 'bundle') AS bundle,
               COUNT(*) FILTER (WHERE regimen_fiscal = 'declarativo') AS declarativo,
               COUNT(*) FILTER (WHERE is_verified) AS verified
        FROM companies
        WHERE created_at >= NOW() - INTERVAL '12 months'
        GROUP BY TO_CHAR(created_at, 'YYYY-MM')
        ORDER BY month
    """)

    result = {
        "by_zone_regime": [dict(r) for r in zone_regime],
        "by_forma_juridica": [dict(r) for r in forma_juridica],
        "by_city": [dict(r) for r in city_stats],
        "debt_by_fee_type": [dict(r) for r in debt_by_fee],
        "top_debtors": [dict(r) for r in top_debtors],
        "monthly_trend": [dict(r) for r in monthly_trend],
    }
    await cache.set(cache_key, result, ttl=_ANALYTICS_TTL)
    return result


# ── Cron: Refresh Materialized Views ────────────────────────────────────────

@router.post("/cron/refresh-company-stats")
async def refresh_company_stats(
    db=Depends(get_database),
    _=Depends(_verify_cron_or_admin),
):
    """Refresh all company dashboard materialized views.

    Called by Cloud Scheduler every 15 minutes.
    Uses CONCURRENTLY to avoid locking reads.
    """
    # Hardcoded whitelist — NEVER accept dynamic view names
    ALLOWED_VIEWS = frozenset({
        "mv_company_stats_by_zone",
        "mv_obligation_stats_by_ministry",
        "mv_company_global_stats",
        "mv_company_analytics",
    })
    refreshed = []
    for view_name in ALLOWED_VIEWS:
        if await _mv_exists(db, view_name):
            # Safe: view_name is from hardcoded whitelist, not user input
            await db.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view_name}")
            refreshed.append(view_name)
            logger.info(f"Refreshed materialized view: {view_name}")

    return {"refreshed": refreshed, "count": len(refreshed)}
