"""Filter Presets & Export Routes — API endpoints for filter presets and data export.

Prefix: /api/v1/inspections

7 endpoints: 4 filter preset CRUD + 3 export (CSV inspections, CSV agents, PDF report).
"""

import logging
from typing import Optional
from uuid import UUID
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Depends, Query

from app.database.connection import get_database
from app.modules.auth.middleware.auth_middleware import get_current_user
from app.modules.users.models.user import UserResponse
from app.modules.permissions.middleware.permission_middleware import (
    permission_required,
)
from app.modules.inspections.models.filter_preset import (
    FilterPresetCreate,
    FilterPresetUpdate,
    FilterPresetResponse,
    FilterPresetListResponse,
)
from app.modules.inspections.services.filter_preset_service import (
    FilterPresetService,
)
from app.modules.inspections.services.export_service import (
    InspectionExportService,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/inspections", tags=["Inspection Filters & Export"])


# ============================================================
# Filter Presets — CRUD
# ============================================================


@router.post("/filter-presets", status_code=201)
async def create_preset(
    data: FilterPresetCreate,
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("inspection.manage_filter_presets")),
):
    """Create a new filter preset for a supervisor table."""
    try:
        result = await FilterPresetService.create_preset(
            db, UUID(current_user.id), data.model_dump(),
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return FilterPresetResponse(**result)


@router.get("/filter-presets")
async def list_presets(
    table_key: Optional[str] = Query(None),
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("inspection.manage_filter_presets")),
):
    """List current user's filter presets, optionally filtered by table_key."""
    try:
        items = await FilterPresetService.list_presets(
            db, UUID(current_user.id), table_key,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return FilterPresetListResponse(
        items=[FilterPresetResponse(**i) for i in items],
        total=len(items),
    )


@router.put("/filter-presets/{preset_id}")
async def update_preset(
    preset_id: UUID,
    data: FilterPresetUpdate,
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("inspection.manage_filter_presets")),
):
    """Update an existing filter preset (IDOR-protected: owner only)."""
    try:
        result = await FilterPresetService.update_preset(
            db, UUID(current_user.id), preset_id,
            data.model_dump(exclude_unset=True),
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return FilterPresetResponse(**result)


@router.delete("/filter-presets/{preset_id}", status_code=204)
async def delete_preset(
    preset_id: UUID,
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("inspection.manage_filter_presets")),
):
    """Delete a filter preset (IDOR-protected: owner only)."""
    try:
        await FilterPresetService.delete_preset(
            db, UUID(current_user.id), preset_id,
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


# ============================================================
# Export — CSV & PDF
# ============================================================


@router.get("/export/csv")
async def export_inspections_csv(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    agent_id: Optional[UUID] = Query(None),
    zone_code: Optional[str] = Query(None),
    result: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    has_payment: Optional[bool] = Query(None),
    has_med: Optional[bool] = Query(None),
    has_seal: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("inspection.export")),
):
    """Export inspections as CSV (UTF-8 BOM for Excel compatibility)."""
    # A04: Rate limit expensive export operations (5 per minute)
    from app.core.cache import check_rate_limit
    allowed, _ = await check_rate_limit(
        current_user.id, "/inspections/export", max_requests=5, window_seconds=60,
    )
    if not allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded for export")

    from app.modules.inspections.services.inspection_service import InspectionService

    try:
        ctx = await InspectionService.resolve_inspector_context(
            db, UUID(current_user.id),
        )
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))

    filters = {k: v for k, v in {
        "date_from": date_from, "date_to": date_to, "agent_id": agent_id,
        "zone_code": zone_code, "result": result, "status": status,
        "has_payment": has_payment, "has_med": has_med, "has_seal": has_seal,
        "search": search,
    }.items() if v is not None}

    try:
        csv_bytes = await InspectionExportService.export_inspections_csv(
            db, ctx["entity_id"], filters,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    from fastapi.responses import Response
    filename = f"inspections_{date_from or 'all'}_{date_to or 'today'}.csv"
    return Response(
        content=csv_bytes,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export/agents-csv")
async def export_agents_csv(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("inspection.export")),
):
    """Export agent performance as CSV."""
    from app.modules.inspections.services.inspection_service import InspectionService

    try:
        ctx = await InspectionService.resolve_inspector_context(
            db, UUID(current_user.id),
        )
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))

    df = date_from or (date.today() - timedelta(days=30))
    dt = date_to or date.today()

    try:
        csv_bytes = await InspectionExportService.export_agents_csv(
            db, ctx["entity_id"], df, dt,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    from fastapi.responses import Response
    return Response(
        content=csv_bytes,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="agents_performance_{df}_{dt}.csv"',
        },
    )


@router.get("/export/pdf")
async def export_inspections_pdf(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    agent_id: Optional[UUID] = Query(None),
    zone_code: Optional[str] = Query(None),
    result: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("inspection.export")),
):
    """Export inspection report as PDF."""
    from app.modules.inspections.services.inspection_service import InspectionService

    try:
        ctx = await InspectionService.resolve_inspector_context(
            db, UUID(current_user.id),
        )
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))

    filters = {k: v for k, v in {
        "date_from": date_from, "date_to": date_to, "agent_id": agent_id,
        "zone_code": zone_code, "result": result, "status": status,
    }.items() if v is not None}

    # Retrieve supervisor's digital signature for PDF signing
    # Uses the last captured signature from their field inspections
    supervisor_name = current_user.full_name or ""
    supervisor_sig = await db.fetchval("""
        SELECT agent_signature FROM field_inspections
        WHERE agent_id = $1 AND agent_signature IS NOT NULL
        ORDER BY created_at DESC LIMIT 1
    """, UUID(current_user.id))

    try:
        pdf_bytes = await InspectionExportService.export_inspections_pdf(
            db, ctx["entity_id"], filters, ctx["entity_code"],
            supervisor_name=supervisor_name,
            supervisor_signature=supervisor_sig,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    from fastapi.responses import Response
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="rapport_inspections.pdf"',
        },
    )
