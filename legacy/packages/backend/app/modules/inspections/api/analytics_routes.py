"""Inspection Analytics Routes — API endpoints for analytics dashboards.

Prefix: /api/v1/inspections/analytics

6 endpoints for supervisor analytics (agent performance, zones, trends, compare, priority).
Rate-limited: 20 requests/minute per user (A04: expensive aggregation queries).
"""

import logging
from typing import Optional
from uuid import UUID
from datetime import date

from fastapi import APIRouter, HTTPException, Depends, Query

from app.database.connection import get_database
from app.modules.auth.middleware.auth_middleware import get_current_user
from app.modules.users.models.user import UserResponse
from app.modules.permissions.middleware.permission_middleware import (
    permission_required,
)
from app.modules.inspections.models.analytics import (
    AgentPerformanceResponse,
    AgentDetailResponse,
    ZoneAnalyticsResponse,
    TrendResponse,
    CompareResponse,
    PriorityZonesResponse,
)
from app.modules.inspections.services.analytics_service import (
    AnalyticsService,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/inspections/analytics", tags=["Inspection Analytics"])


# ============================================================
# Agent Performance
# ============================================================


@router.get("/agents")
async def get_agent_performance(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("inspection.view_analytics")),
):
    """Get agent performance list with metrics (supervisor-only)."""
    # A04: Rate limit expensive analytics queries
    from app.core.cache import check_rate_limit
    allowed, _ = await check_rate_limit(
        current_user.id, "/inspections/analytics", max_requests=20, window_seconds=60,
    )
    if not allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded for analytics")

    try:
        result = await AnalyticsService.get_agent_performance(
            db, UUID(current_user.id), date_from, date_to, page, page_size,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return AgentPerformanceResponse(**result)


@router.get("/agents/{agent_id}")
async def get_agent_detail(
    agent_id: UUID,
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("inspection.view_analytics")),
):
    """Get detailed performance breakdown for a single agent."""
    try:
        result = await AnalyticsService.get_agent_detail(
            db, UUID(current_user.id), agent_id, date_from, date_to,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return AgentDetailResponse(**result)


# ============================================================
# Zone Analytics
# ============================================================


@router.get("/zones")
async def get_zone_analytics(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("inspection.view_analytics")),
):
    """Get zone-level analytics with conformity rates and coverage status."""
    try:
        result = await AnalyticsService.get_zone_analytics(
            db, UUID(current_user.id), date_from, date_to,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Zone analytics error: {e}")
        return ZoneAnalyticsResponse(items=[], total_zones=0, covered_zones=0, stale_zones=0)
    return ZoneAnalyticsResponse(**result)


# ============================================================
# Trends
# ============================================================


@router.get("/trends")
async def get_trends(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    granularity: str = Query("weekly", pattern="^(daily|weekly|monthly)$"),
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("inspection.view_analytics")),
):
    """Get time series trend data (daily/weekly/monthly)."""
    try:
        result = await AnalyticsService.get_trends(
            db, UUID(current_user.id), date_from, date_to, granularity,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return TrendResponse(**result)


# ============================================================
# Comparison
# ============================================================


@router.get("/compare")
async def get_comparison(
    compare_type: str = Query(..., pattern="^(agents|zones|periods)$"),
    id1: str = Query(...),
    id2: str = Query(...),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("inspection.view_analytics")),
):
    """Compare two agents, zones, or time periods side by side."""
    try:
        result = await AnalyticsService.get_comparison(
            db, UUID(current_user.id), compare_type, [id1, id2],
            date_from, date_to,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return CompareResponse(**result)


# ============================================================
# Priority Zones
# ============================================================


@router.get("/priority-zones")
async def get_priority_zones(
    limit: int = Query(20, ge=1, le=100),
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("inspection.view_analytics")),
):
    """Get priority zones ranked by inspection urgency."""
    try:
        result = await AnalyticsService.get_priority_zones(
            db, UUID(current_user.id), limit,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return PriorityZonesResponse(**result)


# ============================================================
# Mission Analytics
# ============================================================


@router.get("/missions")
async def get_mission_analytics(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    entity_location_id: Optional[UUID] = Query(None, description="Filter by site"),
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("inspection.view_analytics")),
):
    """Mission analytics: KPIs, trends, top agents, stale zones."""
    from datetime import timedelta
    from app.modules.inspections.services.inspection_service import InspectionService
    from app.modules.inspections.repositories.mission_repository import MissionRepository

    try:
        ctx = await InspectionService.resolve_inspector_context(
            db, UUID(current_user.id),
        )
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))

    # Defaults: last 8 weeks
    _date_to = date_to or date.today()
    _date_from = date_from or (_date_to - timedelta(weeks=8))

    # Location scoping — city-scoped entities always forced to own location
    CITY_SCOPED = {"AYUNTAMIENTO", "CAMARA_COMERCIO"}
    is_city_scoped = ctx.get("entity_code", "") in CITY_SCOPED
    loc = entity_location_id
    if not loc and (is_city_scoped or not ctx.get("is_main_office", False)):
        loc = ctx.get("entity_location_id")

    result = await MissionRepository.get_mission_analytics(
        db, ctx["entity_id"], _date_from, _date_to,
        entity_location_id=loc,
    )
    return result
