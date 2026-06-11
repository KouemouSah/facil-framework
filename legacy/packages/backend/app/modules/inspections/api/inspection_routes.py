"""Inspection Routes — API endpoints for field inspections.

Prefix: /api/v1/inspections

11 endpoints for field agents + supervisor dashboard + cron.
"""

import logging
from typing import Optional
from uuid import UUID
from datetime import date, timezone

from fastapi import APIRouter, HTTPException, Depends, Query, Request, UploadFile, File, Form
from fastapi.responses import JSONResponse

from app.core.idempotency import (
    check_idempotency_or_replay,
    store_idempotency_result,
)
from app.database.connection import get_database
from app.modules.auth.middleware.auth_middleware import get_current_user
from app.modules.users.models.user import UserResponse
from app.modules.permissions.middleware.permission_middleware import (
    permission_required,
)
from app.modules.inspections.models.inspection import (
    InspectionCreate,
    InspectionUpdate,
    InspectionCompleteRequest,
    MiseEnDemeureRequest,
    SealProposeRequest,
    SealApproveRequest,
    FieldCollectRequest,
    InspectionResponse,
    InspectionListResponse,
    InspectionListItem,
    InspectionStats,
    SupervisorDashboardResponse,
    ReconciliationResponse,
    ReconciliationItem,
    LicenseVerificationResponse,
)
from app.modules.inspections.services.inspection_service import (
    InspectionService,
)
from app.modules.inspections.repositories.inspection_repository import (
    InspectionRepository,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/inspections", tags=["Field Inspections"])


# Centralized cron authentication (fail-closed)
from app.core.cron_auth import verify_cron_auth  # noqa: F401 — used as Depends()


# ============================================================
# Static paths BEFORE /{id}
# ============================================================


@router.post("/", response_model=InspectionResponse, status_code=201)
async def create_inspection(
    data: InspectionCreate,
    request: Request,
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("inspection.create")),
):
    """Create a new field inspection for a commercial license.

    Plan P3: Idempotency-Key header supported (secondary defense — primary
    protection is the UNIQUE(agent_id, company_id, inspection_date) constraint).
    """
    user_uuid = UUID(current_user.id)

    # Idempotency replay guard
    cached = await check_idempotency_or_replay(
        request, user_uuid, endpoint_key="create_inspection",
    )
    if cached is not None:
        return JSONResponse(
            content=cached,
            headers={"Idempotency-Replay": "true"},
            status_code=201,
        )

    try:
        async with db.transaction():
            result = await InspectionService.create_inspection(
                db, user_uuid,
                data.license_id, data.company_id,
                notes=data.notes,
                mission_id=data.mission_id,
                zone_id=data.zone_id,
            )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        err_str = str(e).lower()
        if "unique" in err_str or "duplicate" in err_str:
            raise HTTPException(
                status_code=409,
                detail="An inspection already exists for this company today. "
                       "You can only create one inspection per company per day."
            )
        raise

    # Store result for future replay (24h)
    # Serialize Pydantic response once for JSON caching
    response_body = InspectionResponse(**result).model_dump(mode="json")
    await store_idempotency_result(
        request, user_uuid, endpoint_key="create_inspection", result=response_body,
    )
    return InspectionResponse(**result)


@router.get("/", response_model=InspectionListResponse)
async def list_inspections(
    inspection_date: Optional[date] = Query(None),
    status: Optional[str] = Query(None),
    agent_id: Optional[UUID] = Query(None),
    zone_code: Optional[str] = Query(None),
    result: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    search: Optional[str] = Query(None, max_length=100),
    has_payment: Optional[bool] = Query(None),
    has_med: Optional[bool] = Query(None),
    has_seal: Optional[bool] = Query(None),
    sort_by: Optional[str] = Query(None, pattern="^(inspection_date|created_at|payment_amount|company_name|status|result)$"),
    sort_dir: Optional[str] = Query("desc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("inspection.view_own")),
):
    """List inspections with advanced filters. Supervisors see entity-wide."""
    try:
        ctx = await InspectionService.resolve_inspector_context(
            db, UUID(current_user.id)
        )
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))

    filters = {
        "inspection_date": inspection_date, "status": status,
        "agent_id": agent_id, "zone_code": zone_code, "result": result,
        "date_from": date_from, "date_to": date_to, "search": search,
        "has_payment": has_payment, "has_med": has_med, "has_seal": has_seal,
        "sort_by": sort_by, "sort_dir": sort_dir or "desc",
    }

    if ctx["is_supervisor"]:
        items, total = await InspectionRepository.list_by_entity(
            db, ctx["entity_id"],
            page=page, page_size=page_size,
            **{k: v for k, v in filters.items() if v is not None},
        )
    else:
        items, total = await InspectionRepository.list_by_agent(
            db, UUID(current_user.id),
            inspection_date=inspection_date,
            date_from=date_from,
            date_to=date_to,
            status=status,
            result=result,
            search=search,
            page=page, page_size=page_size,
        )

    return InspectionListResponse(
        items=[InspectionListItem(**item) for item in items],
        total=total, page=page, page_size=page_size,
    )


@router.get("/stats", response_model=InspectionStats)
async def get_inspection_stats(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("inspection.view_own")),
):
    """Get inspection stats for current agent or entity."""
    try:
        ctx = await InspectionService.resolve_inspector_context(
            db, UUID(current_user.id)
        )
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))

    if ctx["is_supervisor"]:
        stats = await InspectionRepository.get_stats(
            db, entity_id=ctx["entity_id"],
            date_from=date_from, date_to=date_to,
        )
    else:
        stats = await InspectionRepository.get_stats(
            db, agent_id=UUID(current_user.id),
            date_from=date_from, date_to=date_to,
        )

    return InspectionStats(**stats)


@router.get("/reconcile", response_model=ReconciliationResponse)
async def get_reconciliation(
    target_date: Optional[date] = Query(None),
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("inspection.collect_payment")),
):
    """Get agent's cash collections for reconciliation."""
    items, total_amount = await InspectionRepository.get_unreconciled_cash(
        db, UUID(current_user.id), target_date=target_date,
    )
    return ReconciliationResponse(
        items=[ReconciliationItem(**item) for item in items],
        total_amount=total_amount,
        total_count=len(items),
    )


@router.get("/reconcile/supervisor")
async def get_supervisor_reconciliation(
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("inspection.reconcile_validate")),
):
    """Supervisor: list field collections pending reconciliation.

    Returns all service_payments with workflow_status='field_collected'
    scoped to the supervisor's entity.
    """
    try:
        ctx = await InspectionService.resolve_inspector_context(
            db, UUID(current_user.id)
        )
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))

    if not ctx["is_supervisor"]:
        raise HTTPException(status_code=403, detail="Supervisor only")

    # CTE: pending field collections + agent info + company info
    rows = await db.fetch("""
        WITH pending_field AS (
            SELECT sp.id, sp.payment_reference, sp.total_amount,
                   sp.collected_by, sp.field_inspection_id,
                   sp.entity_code, sp.fee_type,
                   sp.created_at,
                   u.full_name AS agent_name,
                   fi.company_id, fi.inspection_date
            FROM service_payments sp
            JOIN users u ON u.id = sp.collected_by
            LEFT JOIN field_inspections fi ON fi.id = sp.field_inspection_id
            WHERE sp.collection_type = 'field'
              AND sp.workflow_status = 'field_collected'
              AND sp.entity_code = $1
        )
        SELECT pf.*,
               c.legal_name AS company_name,
               COALESCE(c.nif, c.registration_number) AS company_nif
        FROM pending_field pf
        LEFT JOIN companies c ON c.id = pf.company_id
        ORDER BY pf.created_at ASC
    """, ctx["entity_code"])

    items = [dict(r) for r in rows]
    total = sum(r.get("total_amount") or 0 for r in items)

    return {
        "items": items,
        "total_amount": float(total),
        "total_count": len(items),
        "entity_code": ctx["entity_code"],
    }


@router.post("/reconcile/supervisor/{payment_id}/validate")
async def validate_field_reconciliation(
    payment_id: UUID,
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("inspection.reconcile_validate")),
):
    """Supervisor validates a field cash collection (double validation).

    Confirms the agent has reversed the cash to the treasury.
    Transitions: field_collected → completed → on_payment_completed → routing.
    """
    try:
        ctx = await InspectionService.resolve_inspector_context(
            db, UUID(current_user.id)
        )
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))

    if not ctx["is_supervisor"]:
        raise HTTPException(status_code=403, detail="Supervisor only")

    # Double validation: field_collected → completed
    # Then trigger the SAME post-payment pipeline as normal
    try:
        async with db.transaction():
            # Lock payment row — NOWAIT prevents 2 supervisors validating simultaneously.
            # If another transaction holds the lock, raises asyncpg.LockNotAvailableError
            # immediately instead of waiting (OWASP A04: race condition prevention).
            payment = await db.fetchrow("""
                SELECT id, workflow_status, entity_code, collection_type
                FROM service_payments
                WHERE id = $1
                FOR UPDATE NOWAIT
            """, payment_id)

            if not payment:
                raise HTTPException(status_code=404, detail="Payment not found")
            if payment["workflow_status"] != "field_collected":
                raise HTTPException(
                    status_code=422,
                    detail=f"Payment is not in 'field_collected' status (current: {payment['workflow_status']})"
                )
            if payment["entity_code"] != ctx["entity_code"]:
                raise HTTPException(status_code=403, detail="Payment belongs to another entity")

            # 1. Update payment to completed
            await db.execute("""
                UPDATE service_payments
                SET workflow_status = 'completed',
                    status = 'completed',
                    validated_by_agent_id = $1,
                    validated_at = NOW(),
                    paid_at = NOW(),
                    updated_at = NOW()
                WHERE id = $2 AND workflow_status = 'field_collected'
            """, UUID(current_user.id), payment_id)

            # 2. Trigger obligation routing (SAME as treasury validation)
            from app.modules.fiscal_services.services.license_service import (
                LicenseService,
            )
            routed = await LicenseService.on_payment_completed(db, str(payment_id))

            # 3. Audit trail
            from app.modules.inspections.services.inspection_service import _log_audit
            await _log_audit(
                db, UUID(current_user.id),
                "FIELD_RECONCILIATION_VALIDATED",
                "service_payment", str(payment_id),
                {"entity_code": ctx["entity_code"], "routed_obligations": routed},
            )

            logger.info(
                f"Field reconciliation validated: payment {payment_id} "
                f"by supervisor {current_user.id}, {routed} obligations routed"
            )

    except HTTPException:
        raise
    except Exception as e:
        err_str = str(e).lower()
        if "lock" in err_str and ("not available" in err_str or "nowait" in err_str):
            raise HTTPException(
                status_code=409,
                detail="This payment is being validated by another supervisor. Please try again."
            )
        logger.error(f"Field reconciliation failed: {e}")
        raise HTTPException(status_code=500, detail="Reconciliation validation failed")

    return {
        "payment_id": str(payment_id),
        "status": "completed",
        "routed_obligations": routed,
        "validated_by": current_user.id,
    }


@router.get("/verify")
async def verify_license(
    license_id: Optional[UUID] = Query(None),
    nif: Optional[str] = Query(None, max_length=20, description="NIF (GExxxxx) or registration number (PE-xxxxxx)"),
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("inspection.create")),
):
    """Verify a license for field inspection (by license_id, NIF, or registration number).

    OWASP A04: Rate-limited to 30 requests/minute per agent to prevent NIF enumeration.
    """
    # Rate limit: 30 req/min per user
    try:
        from app.core.cache import check_rate_limit
        allowed, remaining = await check_rate_limit(
            current_user.id, "/inspections/verify", 30, 60
        )
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Try again in 1 minute.",
                headers={"Retry-After": "60"},
            )
    except ImportError:
        pass  # Cache not available — skip rate limit (dev mode)

    try:
        result = await InspectionService.verify_license_for_agent(
            db, UUID(current_user.id),
            license_id=license_id, nif=nif,
        )
    except ValueError as e:
        err = str(e)
        if "not found" in err.lower():
            raise HTTPException(status_code=404, detail=err)
        raise HTTPException(status_code=422, detail=err)
    return result


@router.get("/supervisor/dashboard", response_model=SupervisorDashboardResponse)
async def get_supervisor_dashboard(
    entity_location_id: Optional[UUID] = Query(None, description="Filter stats by site location"),
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("inspection.view_entity")),
):
    """Supervisor inspection dashboard with KPIs, alerts, pending seals.

    Main-office supervisors can pass entity_location_id to scope stats
    to a specific site. Without it, shows all locations aggregated.
    Non-main-office supervisors are always scoped to their own site.
    """
    try:
        result = await InspectionService.get_supervisor_dashboard(
            db, UUID(current_user.id),
            entity_location_id=entity_location_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    return SupervisorDashboardResponse(**result)


@router.get("/supervisor/live-status")
async def get_live_agent_status(
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("inspection.view_entity")),
):
    """Real-time agent status for supervisor: active/idle/offline + live counters.

    Cached in Redis for 30s. Rate limited to 30 req/min.
    """
    from app.core.cache import check_rate_limit
    allowed, remaining = await check_rate_limit(
        current_user.id, "live_status", 30, 60
    )
    if not allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    try:
        ctx = await InspectionService.resolve_inspector_context(
            db, UUID(current_user.id)
        )
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))

    if not ctx["is_supervisor"]:
        raise HTTPException(status_code=403, detail="Supervisor only")

    # Location scoping — city-scoped entities always forced to own location
    CITY_SCOPED = {"AYUNTAMIENTO", "CAMARA_COMERCIO"}
    is_city_scoped = ctx.get("entity_code", "") in CITY_SCOPED
    location_id = None
    if is_city_scoped or not ctx.get("is_main_office", False):
        location_id = ctx.get("entity_location_id")

    result = await InspectionService.get_live_agent_status(
        db, ctx["entity_id"], entity_location_id=location_id
    )
    return result


@router.post("/cron/auto-approve-seals")
async def cron_auto_approve_seals(
    db=Depends(get_database),
    _=Depends(verify_cron_auth),
):
    """Cron: auto-approve seals pending >24h. Run every 6h."""
    async with db.transaction():
        count = await InspectionService.auto_approve_expired_seals(db)
    return {"auto_approved": count}


# ============================================================
# Dynamic paths — /{id}
# NOTE: Mission routes registered as SEPARATE router in main.py
# with prefix /api/v1/inspections/missions to avoid catch-all conflict.
# ============================================================


@router.get("/{inspection_id}", response_model=InspectionResponse)
async def get_inspection(
    inspection_id: UUID,
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("inspection.view_own")),
):
    """Get inspection detail — IDOR-protected (agent sees own, supervisor sees entity)."""
    inspection = await InspectionRepository.get_by_id(db, inspection_id)
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")

    try:
        ctx = await InspectionService.resolve_inspector_context(
            db, UUID(current_user.id)
        )
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))

    # IDOR: agent sees own, supervisor sees entity
    if not ctx["is_supervisor"] and inspection["agent_id"] != UUID(current_user.id):
        raise HTTPException(status_code=403, detail="Cannot view another agent's inspection")
    if ctx["is_supervisor"] and inspection["entity_id"] != ctx["entity_id"]:
        raise HTTPException(status_code=403, detail="Inspection belongs to another entity")

    return InspectionResponse(**inspection)


@router.put("/{inspection_id}", response_model=InspectionResponse)
async def update_inspection(
    inspection_id: UUID,
    data: InspectionUpdate,
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("inspection.create")),
):
    """Update inspection during field work (photos, GPS, notes, activity)."""
    try:
        async with db.transaction():
            result = await InspectionService.update_inspection(
                db, inspection_id, UUID(current_user.id),
                data.model_dump(exclude_unset=True),
            )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return InspectionResponse(**result)


@router.post("/{inspection_id}/complete", response_model=InspectionResponse)
async def complete_inspection(
    inspection_id: UUID,
    data: InspectionCompleteRequest,
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("inspection.create")),
):
    """Complete an inspection (mark as conforme/non_conforme)."""
    try:
        async with db.transaction():
            result = await InspectionService.complete_inspection(
                db, inspection_id, UUID(current_user.id),
                notes=data.notes,
            )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return InspectionResponse(**result)


@router.post("/{inspection_id}/mise-en-demeure", response_model=InspectionResponse)
async def issue_mise_en_demeure(
    inspection_id: UUID,
    data: MiseEnDemeureRequest,
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("inspection.mise_en_demeure")),
):
    """Issue a formal notice (mise en demeure) with 72h deadline."""
    try:
        async with db.transaction():
            result = await InspectionService.issue_mise_en_demeure(
                db, inspection_id, UUID(current_user.id),
                obligation_ids=data.obligation_ids,
                deadline_hours=data.deadline_hours,
                notes=data.notes,
            )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return InspectionResponse(**result)


@router.post("/{inspection_id}/seal", response_model=InspectionResponse)
async def propose_seal(
    inspection_id: UUID,
    data: SealProposeRequest,
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("inspection.seal_propose")),
):
    """Propose sealing a business (requires supervisor approval)."""
    try:
        async with db.transaction():
            result = await InspectionService.propose_seal(
                db, inspection_id, UUID(current_user.id),
                reason=data.reason.value,
                notes=data.notes,
                photo=data.photo,
            )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return InspectionResponse(**result)


@router.post("/{inspection_id}/seal/approve", response_model=InspectionResponse)
async def approve_seal(
    inspection_id: UUID,
    data: SealApproveRequest,
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("inspection.seal_approve")),
):
    """Supervisor approves or rejects a seal proposal."""
    try:
        async with db.transaction():
            result = await InspectionService.approve_seal(
                db, inspection_id, UUID(current_user.id),
                approved=data.approved,
                notes=data.notes,
            )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return InspectionResponse(**result)


@router.post("/{inspection_id}/collect")
async def collect_payment(
    inspection_id: UUID,
    data: FieldCollectRequest,
    request: Request,
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("inspection.collect_payment")),
):
    """Collect field payment (cash or mobile money).

    Plan P3 — INSPECTION_BUNDLE_P3_DETAIL.md:
      - Idempotency-Key header supported (24h replay window) — OWASP A04
      - Rate-limited 20/min/user (defense in depth, field network retries)
      - Fee_type/ministry scope enforced in CollectionService (OWASP A04)
    """
    from app.modules.inspections.services.collection_service import (
        CollectionService,
    )

    user_uuid = UUID(current_user.id)

    # Rate limit (Plan P3 Q4 revised): 20 collect calls / min / user
    try:
        from app.core.cache import check_rate_limit
        allowed, _remaining = await check_rate_limit(
            current_user.id, "/inspections/collect", 20, 60
        )
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded for field collection. Retry in 1 minute.",
                headers={"Retry-After": "60"},
            )
    except ImportError:
        pass  # Cache not available in dev mode

    # Idempotency: replay guard (Plan P3 — D1)
    cached = await check_idempotency_or_replay(
        request, user_uuid, endpoint_key="collect_payment",
    )
    if cached is not None:
        return JSONResponse(
            content=cached,
            headers={"Idempotency-Replay": "true"},
        )

    try:
        async with db.transaction():
            result = await CollectionService.collect_field_payment(
                db, inspection_id, user_uuid,
                obligation_ids=data.obligation_ids,
                method=data.method,
                amount=data.amount,
                phone_number=data.phone_number,
                notes=data.notes,
            )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Store result for future replay (24h)
    await store_idempotency_result(
        request, user_uuid, endpoint_key="collect_payment", result=result,
    )
    return result


# ============================================================
# Photo Upload (Firebase Storage — batch on validation)
# Pattern: Photos uploaded to Firebase only when inspection is finalized.
# During field work, photos are sent as multipart form data to this endpoint
# which uploads them immediately to Firebase and records them.
# This ensures photos are persisted even if the agent loses connection later.
# ============================================================


@router.post("/{inspection_id}/photos")
async def upload_inspection_photo(
    inspection_id: UUID,
    file: UploadFile = File(...),
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("inspection.create")),
):
    """Upload a photo for an inspection to Firebase Storage.

    Photos are uploaded immediately to Firebase (not deferred) to prevent
    data loss if the agent loses connection during field work.
    Registered in uploaded_files table with related_to_type='field_inspection'.
    """
    inspection = await InspectionRepository.get_by_id(db, inspection_id)
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")
    if inspection["agent_id"] != UUID(current_user.id):
        raise HTTPException(status_code=403, detail="Cannot upload to another agent's inspection")
    if inspection["status"] != "in_progress":
        raise HTTPException(status_code=422, detail="Cannot upload photos to completed inspection")

    # Limit number of photos per inspection
    MAX_PHOTOS = 10
    current_photos = inspection.get("photos") or []
    if len(current_photos) >= MAX_PHOTOS:
        raise HTTPException(
            status_code=422,
            detail=f"Maximum {MAX_PHOTOS} photos per inspection"
        )

    if not file.content_type or file.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(status_code=422, detail="Only JPEG, PNG, WebP images allowed")

    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=422, detail="Photo must be under 5MB")

    try:
        from app.modules.documents.services.storage_service import (
            firebase_storage_service, ensure_storage_initialized,
        )
        import hashlib
        from datetime import datetime as dt

        await ensure_storage_initialized()

        photo_index = len(inspection.get("photos") or []) + 1
        result = await firebase_storage_service.upload_user_document(
            user_id=current_user.id,
            application_id=str(inspection_id),
            file=content,
            metadata={
                "filename": f"inspection-photo-{photo_index}.jpg",
                "mime_type": file.content_type,
                "uploadedBy": current_user.id,
                "uploadedAt": dt.now(timezone.utc).isoformat(),
                "applicationId": str(inspection_id),
                "documentType": "inspection_photo",
            }
        )

        file_hash = hashlib.sha256(content).hexdigest()
        await db.execute("""
            INSERT INTO uploaded_files (
                user_id, file_path, file_name, file_size_bytes, mime_type,
                file_url, file_hash, related_to_type, related_to_id,
                access_level, uploaded_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, 'field_inspection', $8, 'private', NOW())
            ON CONFLICT (file_path) DO NOTHING
        """,
            UUID(current_user.id), result.file_path,
            f"inspection-photo-{photo_index}.jpg", len(content),
            file.content_type, result.file_url, file_hash, inspection_id,
        )

        current_photos = inspection.get("photos") or []
        current_photos.append(result.file_url)
        await InspectionRepository.update(db, inspection_id, {"photos": current_photos})

        return {
            "url": result.file_url,
            "file_path": result.file_path,
            "file_size": len(content),
            "photo_index": photo_index,
        }

    except Exception as e:
        logger.error(f"Photo upload failed: {e}")
        raise HTTPException(status_code=500, detail="Photo upload failed")


@router.delete("/{inspection_id}/photos/{photo_index}")
async def delete_inspection_photo(
    inspection_id: UUID,
    photo_index: int,
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("inspection.create")),
):
    """Delete a photo from an inspection by index (0-based)."""
    inspection = await InspectionRepository.get_by_id(db, inspection_id)
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")
    if inspection["agent_id"] != UUID(current_user.id):
        raise HTTPException(status_code=403, detail="Not your inspection")
    if inspection["status"] != "in_progress":
        raise HTTPException(status_code=422, detail="Cannot modify completed inspection")

    photos = list(inspection.get("photos") or [])
    if photo_index < 0 or photo_index >= len(photos):
        raise HTTPException(status_code=404, detail="Photo index out of range")

    removed_url = photos.pop(photo_index)

    # Remove from Firebase Storage
    try:
        from app.modules.documents.services.storage_service import (
            firebase_storage_service, ensure_storage_initialized,
        )
        await ensure_storage_initialized()
        # Extract file_path from URL and delete
        await db.execute(
            "DELETE FROM uploaded_files WHERE file_url = $1 AND user_id = $2",
            removed_url, UUID(current_user.id),
        )
    except Exception as e:
        logger.warning(f"Failed to cleanup photo from storage: {e}")

    await InspectionRepository.update(db, inspection_id, {"photos": photos})
    return {"removed": removed_url, "remaining": len(photos)}


# ============================================================
# PDF Downloads
# ============================================================


@router.get("/{inspection_id}/download-report")
async def download_inspection_report(
    inspection_id: UUID,
    language: str = Query("es", pattern="^(es|fr|en)$"),
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("inspection.view_own")),
):
    """Download inspection report as PDF."""
    from fastapi.responses import Response
    from app.modules.inspections.services.inspection_pdf_service import (
        inspection_pdf_service,
    )

    try:
        pdf_bytes = await inspection_pdf_service.generate_inspection_report(
            db, str(inspection_id), language,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        logger.error(f"PDF generation failed: {e}")
        raise HTTPException(status_code=500, detail="PDF generation failed")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="inspection-{inspection_id}.pdf"',
        },
    )


@router.get("/{inspection_id}/download-med")
async def download_med_pdf(
    inspection_id: UUID,
    language: str = Query("es", pattern="^(es|fr|en)$"),
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("inspection.mise_en_demeure")),
):
    """Download mise en demeure as PDF."""
    from fastapi.responses import Response
    from app.modules.inspections.services.inspection_pdf_service import (
        inspection_pdf_service,
    )

    try:
        pdf_bytes = await inspection_pdf_service.generate_med_pdf(
            db, str(inspection_id), language,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        logger.error(f"PDF generation failed: {e}")
        raise HTTPException(status_code=500, detail="PDF generation failed")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="med-{inspection_id}.pdf"',
        },
    )


@router.get("/{inspection_id}/download-seal")
async def download_seal_pdf(
    inspection_id: UUID,
    language: str = Query("es", pattern="^(es|fr|en)$"),
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("inspection.seal_approve")),
):
    """Download seal report (PV de scellé) as PDF."""
    from fastapi.responses import Response
    from app.modules.inspections.services.inspection_pdf_service import (
        inspection_pdf_service,
    )

    try:
        pdf_bytes = await inspection_pdf_service.generate_seal_pdf(
            db, str(inspection_id), language,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        logger.error(f"PDF generation failed: {e}")
        raise HTTPException(status_code=500, detail="PDF generation failed")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="seal-pv-{inspection_id}.pdf"',
        },
    )


