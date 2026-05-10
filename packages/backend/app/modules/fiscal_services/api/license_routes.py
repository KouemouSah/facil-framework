"""License Routes — API endpoints for commercial licenses (OMS).

Prefix: /api/v1/licenses
"""

import logging
from enum import Enum

logger = logging.getLogger(__name__)

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional
from uuid import UUID

from dataclasses import dataclass

from app.database.connection import get_database
from app.modules.auth.middleware.auth_middleware import get_current_user
from app.modules.users.models.user import UserResponse
from app.modules.permissions.middleware.permission_middleware import permission_required


# Centralized cron authentication (fail-closed)
from app.core.cron_auth import verify_cron_auth  # noqa: F401 — used as Depends()
from app.modules.fiscal_services.models.licenses import (
    LicenseCreate,
    LicenseUpdate,
    LicenseRenewRequest,
    LicenseStatus,
    ObligationStatus,
    LicenseResponse,
    LicenseListResponse,
    LicenseSummary,
    ObligationResponse,
    ObligationListResponse,
    ObligationStatusUpdate,
    BatchObligationStatusUpdate,
    ComplianceEventResponse,
    ComplianceEventListResponse,
)
from app.modules.fiscal_services.services.license_service import LicenseService


class FeeTypeFilter(str, Enum):
    """Allowed fee_type values for query filtering."""
    tesoro = "tesoro"
    municipal = "municipal"
    chamber = "chamber"


router = APIRouter(prefix="/licenses", tags=["Commercial Licenses"])


# ============================================================
# Agent scope — FastAPI dependency (resolved once per request)
# ============================================================

@dataclass(frozen=True)
class AgentScope:
    """Immutable agent scope resolved once per HTTP request via Depends().

    FastAPI caches Depends() results within a single request, so even if
    multiple endpoints or helpers reference get_agent_scope, the DB query
    runs only ONCE.
    """
    city_id: Optional[UUID]
    fee_type: Optional[str]
    ministry_id: Optional[int]
    processing_mode: Optional[str]
    is_scoped: bool

    UNSCOPED = None  # Sentinel, set after class definition

    def verify_license(self, license_row: dict) -> None:
        """IDOR check: raises 403 if license is outside agent's city scope."""
        if not self.is_scoped or self.city_id is None:
            return
        license_city = license_row.get("city_id")
        if license_city and license_city != self.city_id:
            raise HTTPException(
                status_code=403,
                detail="License is outside your zone scope"
            )


# Class-level sentinel for unscoped access
AgentScope.UNSCOPED = AgentScope(
    city_id=None, fee_type=None, ministry_id=None,
    processing_mode=None, is_scoped=False,
)


async def get_agent_scope(
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
) -> AgentScope:
    """FastAPI dependency: resolve agent's entity/city/fee_type/ministry scope.

    Resolved ONCE per request (FastAPI caches Depends results).
    For non-agent users (admin, citizen), returns UNSCOPED (no filtering).
    For agents, queries OmsAgentService.resolve_agent_context() (1 SQL query).
    On unexpected DB errors, fails hard (500) to prevent data leaks.
    """
    if current_user.role not in ("agent", "supervisor"):
        return AgentScope.UNSCOPED

    try:
        from app.modules.fiscal_services.services.oms_agent_service import (
            OmsAgentService,
        )
        ctx = await OmsAgentService.resolve_agent_context(
            db, UUID(current_user.id)
        )
        return AgentScope(
            city_id=ctx.get("queue_city_id"),
            fee_type=ctx.get("queue_fee_type"),
            ministry_id=ctx.get("queue_ministry_id"),
            processing_mode=ctx.get("queue_processing_mode"),
            is_scoped=True,
        )
    except ValueError:
        # Expected: user is not an OMS agent (citizen, admin, non-OMS agent)
        return AgentScope.UNSCOPED
    except Exception as e:
        # Unexpected DB/infra error — fail hard to prevent data leak
        logger.error(f"Agent scope resolution failed for {current_user.id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Could not resolve agent scope"
        )


# ============================================================
# Static paths BEFORE /{license_id}
# ============================================================


@router.post("/cron/flag-overdue")
async def cron_flag_overdue(
    db=Depends(get_database),
    _=Depends(verify_cron_auth),
):
    """Cron: flag overdue obligations past due_date. Run daily.

    Authentication: X-Cron-Secret header (Cloud Scheduler).
    """
    async with db.transaction():
        count = await LicenseService.flag_overdue_obligations(db)
    return {"flagged": count}


@router.post("/cron/apply-penalties")
async def cron_apply_penalties(
    db=Depends(get_database),
    _=Depends(verify_cron_auth),
):
    """Cron: calculate and apply penalties on overdue obligations. Run weekly/monthly.

    Authentication: X-Cron-Secret header (Cloud Scheduler).
    """
    async with db.transaction():
        count = await LicenseService.apply_penalties(db)
    return {"updated": count}


@router.post("/cron/obligation-reminders")
async def cron_obligation_reminders(
    db=Depends(get_database),
    _=Depends(verify_cron_auth),
):
    """Cron: check obligation deadlines and send tiered reminders.

    J-15: reminder to company owners (email)
    J+1: overdue notice to company + agent (email)
    J+30: escalation to supervisors (email)

    Authentication: X-Cron-Secret header (Cloud Scheduler). Run daily.
    """
    from app.modules.fiscal_services.services.oms_reminder_service import (
        oms_reminder_service,
    )

    logger.info("Cron: OMS obligation reminders started")
    result = await oms_reminder_service.run_reminder_check(db)
    logger.info("Cron: OMS obligation reminders completed: %s", result)
    return result


@router.post("/cron/renewal-reminders")
async def cron_renewal_reminders(
    db=Depends(get_database),
    _=Depends(verify_cron_auth),
):
    """Cron: send renewal reminders for completed licenses from previous year.

    Checks companies that completed FY-1 but don't have a license for current year.
    Sends email + push notification to company owners.

    Authentication: X-Cron-Secret header. Run daily (effective January-March).
    """
    count = await LicenseService.check_renewal_reminders(db)
    return {"reminders_sent": count}


@router.get("/compliance-summary")
async def get_compliance_summary(
    fiscal_year: int = Query(..., ge=2020, le=2100),
    db=Depends(get_database),
    scope: AgentScope = Depends(get_agent_scope),
    _: None = Depends(permission_required("fiscal_service.view_bundles")),
):
    """Pre-aggregated compliance summary by fee_type for a fiscal year.

    Agent scope: filters by agent's fee_type/city_id/ministry_id.
    Returns 1 row per fee_type with counts, amounts, recovery %, and
    overdue companies list. Replaces N+1 client-side aggregation.
    """
    from app.modules.fiscal_services.repositories.license_repository import (
        LicenseRepository,
    )

    result = await LicenseRepository.get_compliance_summary(
        db, fiscal_year,
        city_id=scope.city_id,
        fee_type=scope.fee_type,
    )
    return {"items": result, "fiscal_year": fiscal_year}


@router.get("/stats")
async def get_license_stats(
    fiscal_year: Optional[int] = Query(None, ge=2020, le=2100),
    db=Depends(get_database),
    scope: AgentScope = Depends(get_agent_scope),
    _: None = Depends(permission_required("fiscal_service.view_bundles")),
):
    """Dashboard stats scoped by agent entity/city/fee_type/ministry.

    Agent scope: auto-filtered. Admin/citizen: global stats.
    """
    stats = await LicenseService.get_dashboard_stats(
        db, fiscal_year=fiscal_year,
        city_id=scope.city_id, fee_type=scope.fee_type,
        ministry_id=scope.ministry_id,
        processing_mode=scope.processing_mode,
    )
    return stats


@router.get("/my-scope", response_model=LicenseListResponse)
async def list_my_scope_licenses(
    fiscal_year: Optional[int] = Query(None, ge=2020, le=2100),
    status: Optional[LicenseStatus] = Query(None),
    search: Optional[str] = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("fiscal_service.view_bundles")),
):
    """Supervisor OMS: list licenses scoped to entity_location cities.

    Uses agent_profiles.entity_id → entity_locations.city_id to filter
    licenses by the supervisor's assigned cities. This ensures supervisors
    only see licenses within their jurisdiction.
    """
    from app.modules.companies.repositories import CompanyRepository

    # Resolve entity → city_ids
    profile = await db.fetchrow(
        "SELECT entity_id, is_supervisor FROM agent_profiles "
        "WHERE user_id = $1 AND is_active = true",
        UUID(current_user.id),
    )
    if not profile or not profile["entity_id"]:
        return LicenseListResponse(items=[], total=0, page=page, page_size=page_size)

    city_ids = await CompanyRepository().get_entity_city_ids(db, str(profile["entity_id"]))
    if not city_ids:
        return LicenseListResponse(items=[], total=0, page=page, page_size=page_size)

    # Build scoped query
    year = fiscal_year or __import__("datetime").date.today().year
    conditions = ["cl.fiscal_year = $1", "c.city_id = ANY($2)"]
    params: list = [year, city_ids]
    idx = 3

    if status:
        conditions.append(f"cl.status = ${idx}")
        params.append(status.value)
        idx += 1
    if search:
        conditions.append(f"c.legal_name ILIKE ${idx}")
        params.append(f"%{search}%")
        idx += 1

    where = " AND ".join(conditions)
    total = await db.fetchval(
        f"SELECT COUNT(*) FROM commercial_licenses cl "
        f"JOIN companies c ON cl.company_id = c.id WHERE {where}",
        *params,
    )

    offset = (page - 1) * page_size
    rows = await db.fetch(
        f"""SELECT cl.*, c.legal_name as company_name, c.commerce_type,
                   c.nif, cz.zone_code
            FROM commercial_licenses cl
            JOIN companies c ON cl.company_id = c.id
            LEFT JOIN commerce_zones cz ON c.zone_id = cz.id
            WHERE {where}
            ORDER BY cl.updated_at DESC
            LIMIT ${idx} OFFSET ${idx + 1}""",
        *params, page_size, offset,
    )

    return LicenseListResponse(
        items=[LicenseResponse(**dict(r)) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/", response_model=LicenseListResponse)
async def list_licenses(
    company_id: Optional[UUID] = Query(None),
    bundle_id: Optional[UUID] = Query(None),
    fiscal_year: Optional[int] = Query(None, ge=2020, le=2100),
    status: Optional[LicenseStatus] = Query(None),
    search: Optional[str] = Query(None, max_length=100),
    sort_by: Optional[str] = Query(None, regex="^(company_name|fiscal_year|status|total_amount|amount_paid|compliance_score|deadline|created_at|zone_code)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db=Depends(get_database),
    scope: AgentScope = Depends(get_agent_scope),
    _: None = Depends(permission_required("fiscal_service.view_bundles")),
):
    """List commercial licenses with filters, sorting, and pagination.

    sort_by: whitelisted column name. sort_order: asc|desc.
    Agent scope: auto-filtered by agent's city, fee_type, or ministry.
    """
    licenses, total = await LicenseService.list_licenses(
        db, company_id=company_id, bundle_id=bundle_id,
        fiscal_year=fiscal_year, status=status.value if status else None,
        search=search, page=page, page_size=page_size,
        city_id=scope.city_id, fee_type=scope.fee_type,
        ministry_id=scope.ministry_id,
        processing_mode=scope.processing_mode,
        sort_by=sort_by, sort_order=sort_order,
    )
    return LicenseListResponse(
        items=[LicenseSummary(**lic) for lic in licenses],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/", response_model=LicenseResponse, status_code=201)
async def open_license(
    data: LicenseCreate,
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("fiscal_service.manage_bundles")),
):
    """Open a new commercial license dossier.

    Atomic: creates the license + generates all obligations from bundle items
    for the specified zone. Snapshots penalty/deadline configs at creation time.
    """
    try:
        async with db.transaction():
            license_row = await LicenseService.open_license(
                db, data.model_dump(), user_id=UUID(current_user.id),
            )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Emit LICENSE_ISSUED event AFTER transaction commits (no DB conn held).
    # PDF attachment is NOT included here — it should be generated by a
    # background task or lazy-attached by the event handler.
    # TODO: Add background task to generate PDF and attach to email.
    notification = license_row.pop("_notification", None)
    if notification:
        try:
            from app.core.events import EventBus, EventType
            EventBus.publish_nowait(EventType.LICENSE_ISSUED, notification)
            logger.info(f"LICENSE_ISSUED event emitted for {notification.get('license_ref')}")
        except Exception as evt_err:
            logger.warning(f"LICENSE_ISSUED event emission failed: {evt_err}")

    return LicenseResponse(**license_row)


# ============================================================
# License detail — /{license_id}
# ============================================================

@router.get("/{license_id}", response_model=LicenseResponse)
async def get_license(
    license_id: UUID,
    db=Depends(get_database),
    scope: AgentScope = Depends(get_agent_scope),
    _: None = Depends(permission_required("fiscal_service.view_bundles")),
):
    """Get a single license with enriched company/bundle/zone names.

    Agent scope: verifies license is within agent's city scope (IDOR protection).
    """
    license_row = await LicenseService.get_license(db, license_id)
    if not license_row:
        raise HTTPException(status_code=404, detail="License not found")

    scope.verify_license(license_row)

    return LicenseResponse(**license_row)


@router.put("/{license_id}", response_model=LicenseResponse)
async def update_license(
    license_id: UUID,
    data: LicenseUpdate,
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("fiscal_service.manage_bundles")),
):
    """Update license status (admin action: suspend, close)."""
    try:
        async with db.transaction():
            result = await LicenseService.update_license_admin(
                db, license_id, data.status.value,
                user_id=UUID(current_user.id),
            )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail="License not found")
    return LicenseResponse(**result)


# ============================================================
# Obligations
# ============================================================

@router.get("/{license_id}/obligations", response_model=ObligationListResponse)
async def list_obligations(
    license_id: UUID,
    fee_type: Optional[FeeTypeFilter] = Query(None),
    status: Optional[ObligationStatus] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    db=Depends(get_database),
    scope: AgentScope = Depends(get_agent_scope),
    _: None = Depends(permission_required("fiscal_service.view_bundles")),
):
    """List obligations for a license, with optional fee_type/status filter.

    Entity scoping: OMS agents automatically see only their entity's scope.
    - AYUNTAMIENTO/CAMARA → fee_type filter (municipal/chamber)
    - MIN_* → ministry_id filter
    - Polyvalent → all (consolidated only already filtered at license level)
    Admin and citizens see all obligations. Explicit fee_type param overrides.
    """
    license_row = await LicenseService.get_license(db, license_id)
    if not license_row:
        raise HTTPException(status_code=404, detail="License not found")

    # Auto-scope by agent's context when no explicit filter requested
    effective_fee_type = fee_type.value if fee_type else None
    effective_ministry_id = None

    if scope.is_scoped:
        if not effective_fee_type and scope.fee_type:
            effective_fee_type = scope.fee_type
        if scope.ministry_id is not None:
            effective_ministry_id = scope.ministry_id

    obligations, total, kpis = await LicenseService.list_obligations(
        db, license_id, fee_type=effective_fee_type,
        ministry_id=effective_ministry_id,
        status=status.value if status else None,
        page=page, page_size=page_size,
    )
    return ObligationListResponse(
        items=[ObligationResponse(**o) for o in obligations],
        total=total,
        page=page,
        page_size=page_size,
        **kpis,
    )


@router.get("/{license_id}/obligations/summary")
async def get_obligations_summary(
    license_id: UUID,
    db=Depends(get_database),
    scope: AgentScope = Depends(get_agent_scope),
    _: None = Depends(permission_required("fiscal_service.view_bundles")),
):
    """Get obligations grouped by fee_type with sub-totals."""
    license_row = await LicenseService.get_license(db, license_id)
    if not license_row:
        raise HTTPException(status_code=404, detail="License not found")

    scope.verify_license(license_row)

    summary = await LicenseService.get_obligations_summary(db, license_id)
    return summary


@router.get("/{license_id}/obligations/{obligation_id}", response_model=ObligationResponse)
async def get_obligation(
    license_id: UUID,
    obligation_id: UUID,
    db=Depends(get_database),
    scope: AgentScope = Depends(get_agent_scope),
    _: None = Depends(permission_required("fiscal_service.view_bundles")),
):
    """Get a single obligation with enriched service/ministry names.

    IDOR: verifies license scope before returning.
    """
    obligation = await LicenseService.get_obligation(db, obligation_id)
    if not obligation:
        raise HTTPException(status_code=404, detail="Obligation not found")
    if obligation["license_id"] != license_id:
        raise HTTPException(status_code=404, detail="Obligation not found")

    license_row = await LicenseService.get_license(db, license_id)
    if license_row:
        scope.verify_license(license_row)

    return ObligationResponse(**obligation)


@router.post("/{license_id}/obligations/batch-update")
async def batch_update_obligations(
    license_id: UUID,
    data: BatchObligationStatusUpdate,
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    scope: AgentScope = Depends(get_agent_scope),
    _: None = Depends(permission_required("fiscal_service.process_obligations")),
):
    """Batch update multiple obligations at once (e.g., grouped payment).

    All obligations must belong to the specified license (IDOR protection).
    All must support the same status transition.
    """
    # IDOR: verify license scope before batch operation
    license_row = await LicenseService.get_license(db, license_id)
    if not license_row:
        raise HTTPException(status_code=404, detail="License not found")
    scope.verify_license(license_row)

    try:
        async with db.transaction():
            results = await LicenseService.batch_update_obligation_status(
                db, license_id, data.obligation_ids,
                data.model_dump(exclude={"obligation_ids"}, exclude_unset=True),
                user_id=UUID(current_user.id),
            )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return {
        "updated": len(results),
        "items": [ObligationResponse(**r) for r in results],
    }


@router.put("/{license_id}/obligations/{obligation_id}", response_model=ObligationResponse)
async def update_obligation_status(
    license_id: UUID,
    obligation_id: UUID,
    data: ObligationStatusUpdate,
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    scope: AgentScope = Depends(get_agent_scope),
    _: None = Depends(permission_required("fiscal_service.process_obligations")),
):
    """Update obligation status (payment validated, agent processed, etc.).

    Validates status transitions. Auto-recalculates parent license counters.
    Verifies obligation belongs to the specified license (IDOR + scope protection).
    """
    # IDOR: verify license scope before mutation
    license_row = await LicenseService.get_license(db, license_id)
    if not license_row:
        raise HTTPException(status_code=404, detail="License not found")
    scope.verify_license(license_row)

    try:
        async with db.transaction():
            result = await LicenseService.update_obligation_status(
                db, obligation_id, data.model_dump(exclude_unset=True),
                user_id=UUID(current_user.id),
                expected_license_id=license_id,
            )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    if not result:
        raise HTTPException(status_code=404, detail="Obligation not found")
    return ObligationResponse(**result)


# ============================================================
# Events (audit trail)
# ============================================================

@router.get("/{license_id}/events", response_model=ComplianceEventListResponse)
async def list_compliance_events(
    license_id: UUID,
    event_type: Optional[str] = Query(None, max_length=30),
    obligation_id: Optional[UUID] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("fiscal_service.view_bundles")),
):
    """List compliance events for a license (audit timeline)."""
    license_row = await LicenseService.get_license(db, license_id)
    if not license_row:
        raise HTTPException(status_code=404, detail="License not found")

    events, total = await LicenseService.list_events(
        db, license_id, event_type=event_type,
        obligation_id=obligation_id, page=page, page_size=page_size,
    )
    return ComplianceEventListResponse(
        items=[ComplianceEventResponse(**e) for e in events],
        total=total,
        page=page,
        page_size=page_size,
    )


# ============================================================
# License ERP Operations
# ============================================================

@router.post("/{license_id}/renew", response_model=LicenseResponse, status_code=201)
async def renew_license(
    license_id: UUID,
    data: LicenseRenewRequest,
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    scope: AgentScope = Depends(get_agent_scope),
    _: None = Depends(permission_required("fiscal_service.manage_bundles")),
):
    """Renew a license for a new fiscal year.

    Creates a new dossier from the previous year's bundle/zone/company.
    Auto-populates previous_year_paid on the new obligations.
    """
    # IDOR: verify license scope
    license_row = await LicenseService.get_license(db, license_id)
    if not license_row:
        raise HTTPException(status_code=404, detail="License not found")
    scope.verify_license(license_row)

    try:
        async with db.transaction():
            new_license = await LicenseService.renew_license(
                db, license_id, data.fiscal_year,
                user_id=UUID(current_user.id),
            )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Emit LICENSE_ISSUED event AFTER transaction commits (same pattern as open_license).
    notification = new_license.pop("_notification", None)
    if notification:
        try:
            from app.core.events import EventBus, EventType
            EventBus.publish_nowait(EventType.LICENSE_ISSUED, notification)
            logger.info(f"LICENSE_ISSUED event emitted for {notification.get('license_ref')}")
        except Exception as evt_err:
            logger.warning(f"LICENSE_ISSUED event emission failed: {evt_err}")

    return LicenseResponse(**new_license)


@router.post("/{license_id}/check-previous-year")
async def check_previous_year(
    license_id: UUID,
    db=Depends(get_database),
    scope: AgentScope = Depends(get_agent_scope),
    _: None = Depends(permission_required("fiscal_service.view_bundles")),
):
    """Check previous year compliance for all obligations in this license.

    Non-blocking, informational. Sets previous_year_paid = true/false/NULL
    based on whether the same item was paid in fiscal_year-1.
    New companies will have NULL (no data).
    """
    license_row = await LicenseService.get_license(db, license_id)
    if not license_row:
        raise HTTPException(status_code=404, detail="License not found")
    scope.verify_license(license_row)

    async with db.transaction():
        count = await LicenseService.check_previous_year_compliance(db, license_id)
    return {"checked": count, "license_id": str(license_id)}


# ── PDF Download ─────────────────────────────────────────────────────────────

@router.get("/{license_id}/download-pdf")
async def download_license_pdf(
    license_id: UUID,
    language: str = Query("es", regex="^(es|fr|en)$"),
    db=Depends(get_database),
    scope: AgentScope = Depends(get_agent_scope),
    _=Depends(permission_required("fiscal_service.view_bundles")),
):
    """Download commercial license dossier as PDF.

    Generates A4 PDF with company info, obligations table, totals, QR code.
    IDOR: verifies agent scope before generating PDF.
    """
    from fastapi.responses import Response
    from app.modules.fiscal_services.services.license_pdf_service import license_pdf_service

    # IDOR: verify license scope
    license_row = await LicenseService.get_license(db, license_id)
    if license_row:
        scope.verify_license(license_row)

    try:
        pdf_bytes = await license_pdf_service.generate_license_pdf(
            db, str(license_id), language
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="license-{license_id}.pdf"',
        },
    )


# ============================================================
# Batch operations (admin only)
# ============================================================

@router.post("/admin/renew-batch")
async def renew_batch(
    fiscal_year: int = Query(..., ge=2020, le=2100, description="Target fiscal year"),
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("fiscal_service.manage_bundles")),
):
    """Batch-renew all complete licenses for a new fiscal year.

    Finds all licenses with status='complete' for current year and creates
    new dossiers for the target fiscal year. Skips if target year already exists.

    Returns a report with success/skipped/failed counts.
    """
    from datetime import date as _date

    current_year = _date.today().year
    if fiscal_year <= current_year - 1:
        raise HTTPException(
            status_code=422,
            detail=f"Target year {fiscal_year} is too old. Must be >= {current_year}",
        )

    # Find all complete licenses for the previous year
    source_year = fiscal_year - 1
    candidates = await db.fetch(
        "SELECT id, company_id, bundle_id FROM commercial_licenses "
        "WHERE status = 'complete' AND fiscal_year = $1",
        source_year,
    )

    results = {"renewed": 0, "skipped": 0, "failed": 0, "errors": []}

    for lic in candidates:
        # Check if target year already exists
        dup = await db.fetchval(
            "SELECT id FROM commercial_licenses "
            "WHERE company_id = $1 AND bundle_id = $2 AND fiscal_year = $3",
            lic["company_id"], lic["bundle_id"], fiscal_year,
        )
        if dup:
            results["skipped"] += 1
            continue

        try:
            async with db.transaction():
                await LicenseService.renew_license(
                    db, lic["id"], fiscal_year,
                    user_id=UUID(current_user.id),
                )
            results["renewed"] += 1
        except Exception as e:
            results["failed"] += 1
            results["errors"].append({
                "license_id": str(lic["id"]),
                "error": str(e),
            })
            logger.warning(f"Batch renew failed for {lic['id']}: {e}")

    logger.info(
        f"Batch renewal to {fiscal_year}: "
        f"{results['renewed']} renewed, {results['skipped']} skipped, "
        f"{results['failed']} failed (from {len(candidates)} candidates)"
    )

    return {
        "fiscal_year": fiscal_year,
        "source_year": source_year,
        "candidates": len(candidates),
        **results,
    }
