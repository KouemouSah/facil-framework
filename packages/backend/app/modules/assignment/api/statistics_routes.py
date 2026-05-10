"""
Statistics Routes - Analytics and Reporting for Assignment Module
Provides statistical insights and performance metrics

Author: Claude Code
Date: 2025-11-16
Version: 1.0 - Initial implementation
"""

from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field

from app.modules.auth.middleware.auth_middleware import get_current_user
from app.modules.users.models.user import UserResponse
from app.modules.assignment.models.assignment_history import (
    Assignment,
    AgentAssignmentStats
)
from app.modules.assignment.models.agent_workload import (
    AgentPerformanceMetrics,
    AgentWorkload
)
from app.modules.assignment.repositories.assignment_repository import (
    AssignmentRepository,
    get_assignment_repository
)
from app.modules.assignment.repositories.workload_repository import (
    WorkloadRepository,
    get_workload_repository
)
from app.core.database import get_db_connection

# Permission middleware - use permission_required (dependency) instead of require_permission (decorator)
# The decorator requires permission_service in kwargs, the dependency handles it automatically
from app.modules.permissions.middleware import permission_required
from app.modules.permissions.services.permission_service import PermissionService, get_permission_service

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/statistics", tags=["statistics"])


# ============================================================================
# REQUEST/RESPONSE SCHEMAS
# ============================================================================

class TeamPerformanceResponse(BaseModel):
    """Team performance metrics"""
    entity_type: str
    entity_id: Optional[str]
    period_days: int
    total_assignments: int
    completed_assignments: int
    pending_assignments: int
    in_progress_assignments: int
    avg_completion_time_hours: float
    avg_quality_score: float
    success_rate: float
    deadline_compliance_rate: float
    auto_assignment_rate: float
    top_performers: List[Dict[str, Any]]
    performance_trends: Dict[str, Any]


class ComparisonMetrics(BaseModel):
    """Comparison between periods or entities"""
    metric_name: str
    current_value: float
    previous_value: float
    change_percentage: float
    trend: str  # "up", "down", "stable"


class PerformanceTrendsResponse(BaseModel):
    """Performance trends over time"""
    period_start: datetime
    period_end: datetime
    granularity: str  # "daily", "weekly", "monthly"
    data_points: List[Dict[str, Any]]


class ExportRequest(BaseModel):
    """Request to export statistics"""
    format: str = Field(..., pattern="^(pdf|excel|json)$")
    period_days: int = Field(30, ge=1, le=365)
    include_charts: bool = True
    include_raw_data: bool = False


# ============================================================================
# AGENT CONTEXT HELPER (Migration 048 - Unified agent role)
# ============================================================================

async def get_agent_context(user_id: str, db) -> Dict[str, Any]:
    """
    Get agent context from agent_profiles table.

    Returns:
        dict with keys:
        - is_supervisor: bool
        - agent_type: 'ministry_agent' or 'entity_agent'
        - ministry_id: int or None (for ministry_agent)
        - entity_id: UUID or None (for entity_agent)
        - entity_type: 'ministry' or 'entity' (derived from agent_type)
        - ministry_code: str or None (e.g., 'TREASURY')
    """
    query = """
        SELECT
            ap.is_supervisor,
            ap.agent_type,
            ap.ministry_id,
            ap.entity_id,
            m.ministry_code
        FROM agent_profiles ap
        LEFT JOIN ministries m ON ap.ministry_id = m.id
        WHERE ap.user_id = $1 AND ap.is_active = true
    """
    result = await db.fetchrow(query, user_id)

    if not result:
        return {
            "is_supervisor": False,
            "agent_type": None,
            "ministry_id": None,
            "entity_id": None,
            "entity_type": None,
            "ministry_code": None,
        }

    # entity_type is derived directly from agent_type
    agent_type = result.get("agent_type")
    entity_type = "ministry" if agent_type == "ministry_agent" else "entity"

    return {
        "is_supervisor": result.get("is_supervisor", False),
        "agent_type": agent_type,
        "ministry_id": result.get("ministry_id"),
        "entity_id": result.get("entity_id"),
        "entity_type": entity_type,
        "ministry_code": result.get("ministry_code"),
    }


async def _get_agent_profile_id_for_user(user_id: str, db) -> Optional[UUID]:
    """
    Get agent_profile_id from user_id.

    Migration 054: agent_profile_id is the primary identifier, not user_id.
    """
    query = """
        SELECT id FROM agent_profiles
        WHERE user_id = $1 AND is_active = true
    """
    result = await db.fetchrow(query, UUID(user_id))
    return result['id'] if result else None


# ============================================================================
# ENDPOINTS - AGENT STATISTICS
# ============================================================================

@router.get("/agent/{agent_profile_id}", response_model=AgentAssignmentStats)
async def get_agent_statistics(
    agent_profile_id: UUID,
    period_days: int = Query(30, ge=1, le=365, description="Statistics period in days"),
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_db_connection),
    _: None = Depends(permission_required("agent.view_performance"))
):
    """
    **Get comprehensive statistics for an agent**

    Permissions:
    - Requires: agents.view_performance

    Returns:
    - Total assignments (period)
    - Completed assignments
    - Avg processing time (hours)
    - Avg quality score (0-10)
    - Success rate (0-1)
    - Deadline compliance rate (0-1)
    - Breakdown by status
    - Breakdown by item_type

    Query Parameters:
    - period_days: Statistics period (default: 30, max: 365)

    Migration 053/054: Uses agent_profile_id instead of agent_id
    """

    # Authorization check - admins and supervisors can view any stats
    is_admin = current_user.role == "admin"

    # Check if user is a supervisor via agent_profiles
    agent_ctx = await get_agent_context(current_user.id, db) if not is_admin else {}
    is_supervisor = is_admin or agent_ctx.get("is_supervisor", False)

    # Check if current user is viewing their own stats
    user_agent_profile_id = await _get_agent_profile_id_for_user(current_user.id, db)
    is_own_stats = user_agent_profile_id and str(agent_profile_id) == str(user_agent_profile_id)

    if not (is_own_stats or is_supervisor):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own statistics"
        )

    assignment_repo = get_assignment_repository(db)

    try:
        stats = await assignment_repo.get_agent_stats(db, agent_profile_id, period_days)

        logger.info(
            f"Agent statistics loaded for {agent_profile_id} (period: {period_days} days) "
            f"by {current_user.email}"
        )

        return stats

    except Exception as e:
        logger.error(f"Error getting agent statistics: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get agent statistics"
        )


@router.get("/agent/{agent_profile_id}/performance", response_model=AgentPerformanceMetrics)
async def get_agent_performance(
    agent_profile_id: UUID,
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_db_connection),
    _: None = Depends(permission_required("agent.view_performance"))
):
    """
    **Get real-time performance metrics for an agent**

    Permissions:
    - Requires: agents.view_performance

    Returns:
    - Current workload metrics
    - Avg processing time
    - Quality score average
    - Success rate
    - Deadline compliance rate

    Note: This data comes from agent_workloads table (real-time)

    Migration 053/054: Uses agent_profile_id instead of agent_id
    """

    # Authorization check - admins and supervisors can view any metrics
    is_admin = current_user.role == "admin"

    # Check if user is a supervisor via agent_profiles
    agent_ctx = await get_agent_context(current_user.id, db) if not is_admin else {}
    is_supervisor = is_admin or agent_ctx.get("is_supervisor", False)

    # Check if current user is viewing their own metrics
    user_agent_profile_id = await _get_agent_profile_id_for_user(current_user.id, db)
    is_own_metrics = user_agent_profile_id and str(agent_profile_id) == str(user_agent_profile_id)

    if not (is_own_metrics or is_supervisor):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own performance metrics"
        )

    workload_repo = get_workload_repository(db)

    try:
        workload = await workload_repo.get_agent_workload(db, agent_profile_id)

        if not workload:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No workload data found for agent_profile {agent_profile_id}"
            )

        # Compute real metrics from agent_workflow_proficiency + assignments
        on_time_rate = await db.fetchval("""
            SELECT COALESCE(
                COUNT(*) FILTER (WHERE completed_at IS NOT NULL
                    AND deadline IS NOT NULL AND completed_at <= deadline) * 1.0
                / NULLIF(COUNT(*) FILTER (WHERE completed_at IS NOT NULL
                    AND deadline IS NOT NULL), 0),
                0.0
            )
            FROM assignments WHERE agent_profile_id = $1
              AND assigned_at >= NOW() - INTERVAL '30 days'
        """, agent_profile_id)

        # Rejection rate = 1.0 - success_rate (from agent_workloads, updated by feedback loop)
        rejection_rate = max(0.0, 1.0 - float(workload.success_rate or 0))

        # Quality score: composite from proficiency data (avg success × 0.6 + speed × 0.4)
        quality_row = await db.fetchrow("""
            SELECT AVG(success_rate) as avg_sr, AVG(avg_processing_hours) as avg_h
            FROM agent_workflow_proficiency WHERE agent_profile_id = $1
        """, agent_profile_id)
        if quality_row and quality_row['avg_sr'] is not None:
            quality_score = (
                float(quality_row['avg_sr']) / 100.0 * 0.6
                + max(0.0, 1.0 - float(quality_row['avg_h'] or 24) / 48.0) * 0.4
            ) * 10.0
        else:
            quality_score = 0.0

        # Convert to AgentPerformanceMetrics
        metrics = AgentPerformanceMetrics(
            agent_profile_id=workload.agent_profile_id,
            agent_name=workload.agent_name,
            period="current",
            declarations_processed=workload.current_assignments,
            average_time_to_complete_hours=workload.avg_processing_time_hours or 0.0,
            on_time_completion_rate=float(on_time_rate or 0.0),
            rejection_rate=rejection_rate,
            quality_score=round(quality_score, 2),
        )

        logger.info(
            f"Agent performance metrics loaded for {agent_profile_id} by {current_user.email}"
        )

        return metrics

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting agent performance: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get agent performance metrics"
        )


@router.get("/agent/{agent_profile_id}/trends", response_model=PerformanceTrendsResponse)
async def get_agent_trends(
    agent_profile_id: UUID,
    period_days: int = Query(30, ge=7, le=180, description="Trend period in days"),
    granularity: str = Query("daily", pattern="^(daily|weekly)$"),
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_db_connection),
    _: None = Depends(permission_required("agent.view_performance"))
):
    """
    **Get performance trends for an agent over time**

    Permissions:
    - Requires: agents.view_performance

    Returns:
    - Time-series data of performance metrics
    - Granularity: daily or weekly
    - Includes: completions, quality, processing time

    Query Parameters:
    - period_days: Trend period (default: 30, min: 7, max: 180)
    - granularity: "daily" or "weekly" (default: daily)

    Migration 053/054: Uses agent_profile_id instead of agent_id
    """

    # Authorization check - admins and supervisors can view any trends
    is_admin = current_user.role == "admin"

    # Check if user is a supervisor via agent_profiles
    agent_ctx = await get_agent_context(current_user.id, db) if not is_admin else {}
    is_supervisor = is_admin or agent_ctx.get("is_supervisor", False)

    # Check if current user is viewing their own trends
    user_agent_profile_id = await _get_agent_profile_id_for_user(current_user.id, db)
    is_own_trends = user_agent_profile_id and str(agent_profile_id) == str(user_agent_profile_id)

    if not (is_own_trends or is_supervisor):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own trends"
        )

    period_start = datetime.now(timezone.utc) - timedelta(days=period_days)
    period_end = datetime.now(timezone.utc)

    # Real time-series query from assignments + service_requests
    trunc_unit = 'day' if granularity == 'daily' else 'week'
    trend_rows = await db.fetch("""
        SELECT
            date_trunc($3::text, a.completed_at) AS period,
            COUNT(*) AS processed,
            COUNT(*) FILTER (WHERE sr.status IN ('approved', 'completed')) AS approved,
            COUNT(*) FILTER (WHERE sr.status = 'rejected') AS rejected,
            COALESCE(AVG(EXTRACT(EPOCH FROM (a.completed_at - a.assigned_at)) / 3600), 0)
                AS avg_processing_hours,
            COALESCE(
                COUNT(*) FILTER (WHERE a.deadline IS NOT NULL
                    AND a.completed_at <= a.deadline) * 100.0
                / NULLIF(COUNT(*) FILTER (WHERE a.deadline IS NOT NULL), 0), 100
            ) AS sla_compliance_pct
        FROM assignments a
        LEFT JOIN service_requests sr ON sr.id::text = a.item_id
        WHERE a.agent_profile_id = $1
          AND a.completed_at >= $2
          AND a.completed_at IS NOT NULL
        GROUP BY date_trunc($3::text, a.completed_at)
        ORDER BY period
    """, agent_profile_id, period_start, trunc_unit)

    data_points = [
        {
            "period": str(row["period"].date()) if row["period"] else "",
            "processed": row["processed"],
            "approved": row["approved"],
            "rejected": row["rejected"],
            "avg_processing_hours": round(float(row["avg_processing_hours"]), 1),
            "sla_compliance_pct": round(float(row["sla_compliance_pct"]), 1),
        }
        for row in trend_rows
    ]

    response = PerformanceTrendsResponse(
        period_start=period_start,
        period_end=period_end,
        granularity=granularity,
        data_points=data_points,
    )

    logger.info(
        f"Agent trends loaded for {agent_profile_id} (period: {period_days} days, granularity: {granularity}) "
        f"by {current_user.email}"
    )

    return response


# ============================================================================
# TEAM STATISTICS - HELPERS
# ============================================================================


async def _calc_auto_assignment_rate(db, period_days: int) -> float:
    """Calculate % of assignments made automatically vs total."""
    row = await db.fetchrow("""
        SELECT
            COUNT(*) FILTER (WHERE assignment_method = 'auto') AS auto_count,
            COUNT(*) AS total_count
        FROM assignments
        WHERE assigned_at >= NOW() - ($1 * INTERVAL '1 day')
    """, period_days)
    if not row or not row["total_count"]:
        return 0.0
    return round(float(row["auto_count"]) / float(row["total_count"]) * 100.0, 1)


async def _calc_performance_trends(db, period_days: int) -> dict:
    """Daily completions + avg processing hours over period."""
    rows = await db.fetch("""
        SELECT
            date_trunc('day', completed_at)::date AS day,
            COUNT(*) AS completions,
            ROUND(AVG(EXTRACT(EPOCH FROM (completed_at - assigned_at)) / 3600.0)::numeric, 1) AS avg_hours
        FROM assignments
        WHERE completed_at IS NOT NULL
          AND completed_at >= NOW() - ($1 * INTERVAL '1 day')
        GROUP BY day
        ORDER BY day
    """, period_days)
    return {
        "daily": [
            {
                "date": str(r["day"]),
                "completions": r["completions"],
                "avg_processing_hours": float(r["avg_hours"] or 0),
            }
            for r in rows
        ]
    }


# ============================================================================
# ENDPOINTS - TEAM STATISTICS
# ============================================================================

@router.get("/team/performance", response_model=TeamPerformanceResponse)
async def get_team_performance(
    period_days: int = Query(30, ge=1, le=365, description="Statistics period in days"),
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_db_connection),
    _: None = Depends(permission_required("dashboard.team_stats"))
):
    """
    **Get team performance metrics**

    Permissions:
    - Requires: dashboard.team_stats

    Returns:
    - Aggregate statistics for all agents in team
    - Top performers (top 5)
    - Performance trends
    - Auto-assignment rate

    Query Parameters:
    - period_days: Statistics period (default: 30, max: 365)

    Migration 048: Uses unified 'agent' role with agent_profiles for filtering
    """

    # Get agent context from agent_profiles
    # Admin sees all (no filtering by ministry/entity)
    if current_user.role == "admin":
        agent_ctx = {"entity_type": None, "ministry_id": None, "entity_id": None, "is_supervisor": True}
    else:
        agent_ctx = await get_agent_context(current_user.id, db)

    entity_type = agent_ctx.get("entity_type")
    entity_id = agent_ctx.get("ministry_id") or agent_ctx.get("entity_id")

    assignment_repo = get_assignment_repository(db)
    workload_repo = get_workload_repository(db)

    try:
        # TODO: Implement team aggregation query
        # For now, aggregate from individual agent stats

        # Get all agents in team - uses unified 'agent' role
        # Returns List[AgentWorkload] objects
        agents_data = await workload_repo.get_available_agents(db, max_workload_pct=100.0)

        # Aggregate stats
        total_assignments = 0
        completed_assignments = 0
        pending_assignments = 0
        in_progress_assignments = 0
        total_quality = 0.0
        total_processing_time = 0.0
        total_success = 0.0
        total_deadline_compliance = 0.0

        agent_performances = []

        for agent_workload in agents_data:
            # AgentWorkload uses agent_profile_id (Migration 054)
            agent_profile_id = agent_workload.agent_profile_id
            stats = await assignment_repo.get_agent_stats(db, agent_profile_id, period_days)

            total_assignments += stats.total_assignments
            completed_assignments += stats.completed_assignments
            pending_assignments += stats.by_status.get("assigned", 0)
            in_progress_assignments += stats.by_status.get("in_progress", 0)

            if stats.completed_assignments > 0:
                total_quality += stats.quality_score_avg * stats.completed_assignments
                total_processing_time += stats.avg_processing_time_hours * stats.completed_assignments
                total_success += stats.success_rate * stats.completed_assignments
                total_deadline_compliance += stats.deadline_compliance_rate * stats.completed_assignments

            agent_performances.append({
                "agent_profile_id": str(agent_profile_id),
                "agent_name": agent_workload.agent_name,
                "total_assignments": stats.total_assignments,
                "completed_assignments": stats.completed_assignments,
                "avg_quality_score": stats.quality_score_avg,
                "success_rate": stats.success_rate,
                "performance_score": (
                    stats.success_rate * 0.5 +
                    (stats.quality_score_avg / 10.0) * 0.3 +
                    stats.deadline_compliance_rate * 0.2
                )
            })

        # Calculate averages
        avg_quality = total_quality / max(completed_assignments, 1)
        avg_processing_time = total_processing_time / max(completed_assignments, 1)
        success_rate = total_success / max(completed_assignments, 1)
        deadline_compliance = total_deadline_compliance / max(completed_assignments, 1)

        # Sort top performers
        top_performers = sorted(
            agent_performances,
            key=lambda x: x["performance_score"],
            reverse=True
        )[:5]

        response = TeamPerformanceResponse(
            entity_type=entity_type,
            entity_id=entity_id,
            period_days=period_days,
            total_assignments=total_assignments,
            completed_assignments=completed_assignments,
            pending_assignments=pending_assignments,
            in_progress_assignments=in_progress_assignments,
            avg_completion_time_hours=avg_processing_time,
            avg_quality_score=avg_quality,
            success_rate=success_rate,
            deadline_compliance_rate=deadline_compliance,
            auto_assignment_rate=await _calc_auto_assignment_rate(db, period_days),
            top_performers=top_performers,
            performance_trends=await _calc_performance_trends(db, period_days)
        )

        logger.info(
            f"Team performance loaded for {entity_type}/{entity_id} (period: {period_days} days) "
            f"by supervisor {current_user.email}"
        )

        return response

    except Exception as e:
        logger.error(f"Error getting team performance: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get team performance"
        )


@router.get("/team/workload")
async def get_team_workload(
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_db_connection),
    _: None = Depends(permission_required("agent.view_workload"))
):
    """
    **Get team workload balance report**

    Permissions:
    - Requires: agents.view_workload

    Returns:
    - Total agents
    - Available/busy/overloaded/unavailable counts
    - Total assignments
    - Avg assignments per agent
    - Balance score (0-100)
    - Rebalancing needed flag

    Balance Score:
    - 100 = Perfect balance (all agents have same workload)
    - 70-99 = Good balance
    - 50-69 = Moderate imbalance
    - <50 = High imbalance (rebalancing recommended)

    Migration 053/054: Uses agent_profile_id
    """

    # Get agent context from agent_profiles
    # Admin sees all (no filtering by ministry/entity)
    if current_user.role == "admin":
        agent_ctx = {"entity_type": None, "ministry_id": None, "entity_id": None, "is_supervisor": True}
    else:
        agent_ctx = await get_agent_context(current_user.id, db)

    entity_type = agent_ctx.get("entity_type")
    entity_id = agent_ctx.get("ministry_id") or agent_ctx.get("entity_id")

    workload_repo = get_workload_repository(db)

    try:
        # Get all agents - returns List[AgentWorkload]
        agents = await workload_repo.get_available_agents(db, max_workload_pct=100.0)

        if not agents:
            return {
                "total_agents": 0,
                "available_count": 0,
                "busy_count": 0,
                "overloaded_count": 0,
                "total_assignments": 0,
                "avg_assignments_per_agent": 0.0,
                "balance_score": 100.0,
                "rebalancing_needed": False
            }

        # Calculate workload metrics
        total_assignments = sum(a.current_assignments for a in agents)
        available_count = sum(1 for a in agents if a.workload_status == "available")
        busy_count = sum(1 for a in agents if a.workload_status in ["normal", "busy"])
        overloaded_count = sum(1 for a in agents if a.workload_status == "overloaded")

        avg_assignments = total_assignments / len(agents) if agents else 0
        workloads = [a.current_assignments for a in agents]
        max_workload = max(workloads) if workloads else 0
        min_workload = min(workloads) if workloads else 0

        # Simple balance score: 100 - (max - min) * 10, clamped to 0-100
        balance_score = max(0, min(100, 100 - (max_workload - min_workload) * 10))
        rebalancing_needed = balance_score < 50 or overloaded_count > 0

        report = {
            "total_agents": len(agents),
            "available_count": available_count,
            "busy_count": busy_count,
            "overloaded_count": overloaded_count,
            "total_assignments": total_assignments,
            "avg_assignments_per_agent": round(avg_assignments, 2),
            "min_assignments": min_workload,
            "max_assignments": max_workload,
            "balance_score": round(balance_score, 2),
            "rebalancing_needed": rebalancing_needed
        }

        logger.info(
            f"Team workload balance loaded for {entity_type}/{entity_id} "
            f"by supervisor {current_user.email}"
        )

        return report

    except Exception as e:
        logger.error(f"Error getting team workload: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get team workload balance"
        )


# ============================================================================
# ENDPOINTS - SUPERVISOR STATISTICS
# ============================================================================

@router.get("/supervisor/{supervisor_profile_id}")
async def get_supervisor_statistics(
    supervisor_profile_id: UUID,
    period_days: int = Query(30, ge=1, le=365, description="Statistics period in days"),
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_db_connection),
    _: None = Depends(permission_required("dashboard.view"))
):
    """
    **Get statistics for a supervisor**

    Permissions:
    - Requires: dashboard.view

    Returns:
    - Total assignments created (manual)
    - Total reassignments
    - Team size
    - Team assignments

    Query Parameters:
    - period_days: Statistics period (default: 30, max: 365)

    Migration 054: Uses supervisor_profile_id (agent_profile with is_supervisor=true)
    """

    # Authorization check - compare agent_profile_ids
    is_admin = current_user.role == "admin"
    user_agent_profile_id = await _get_agent_profile_id_for_user(current_user.id, db)
    is_own_stats = user_agent_profile_id and str(supervisor_profile_id) == str(user_agent_profile_id)

    if not (is_own_stats or is_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own statistics"
        )

    try:
        # Use repository method instead of inline SQL (Architecture 3-tier)
        assignment_repo = get_assignment_repository(db)
        stats = await assignment_repo.get_supervisor_stats(db, supervisor_profile_id, period_days)

        logger.info(
            f"Supervisor statistics loaded for {supervisor_profile_id} (period: {period_days} days) "
            f"by {current_user.email}"
        )

        return stats

    except Exception as e:
        logger.error(f"Error getting supervisor statistics: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get supervisor statistics"
        )


# ============================================================================
# ENDPOINTS - COMPARISON & TRENDS
# ============================================================================

@router.get("/comparison", response_model=List[ComparisonMetrics])
async def get_comparison_metrics(
    metric_type: str = Query(..., pattern="^(performance|workload|quality|speed)$"),
    current_period_days: int = Query(30, ge=7, le=90),
    previous_period_days: int = Query(30, ge=7, le=90),
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_db_connection),
    _: None = Depends(permission_required("reports.view"))
):
    """
    **Compare metrics between two periods**

    Permissions:
    - Requires: reports.view

    Returns:
    - List of metric comparisons
    - Current vs previous period
    - Change percentage
    - Trend direction (up/down/stable)

    Query Parameters:
    - metric_type: Type of metrics to compare
      - performance: Success rate, quality
      - workload: Assignments, capacity
      - quality: Quality scores, validation rates
      - speed: Processing times, completion rates
    - current_period_days: Current period length (default: 30)
    - previous_period_days: Previous period length (default: 30)
    """

    # TODO: Implement comparison logic
    # For now, return placeholder

    comparisons = []

    logger.info(
        f"Comparison metrics loaded (type: {metric_type}) by supervisor {current_user.email}"
    )

    return comparisons


# ============================================================================
# ENDPOINTS - EXPORT
# ============================================================================

@router.post("/export")
async def export_statistics(
    request: ExportRequest,
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_db_connection),
    _: None = Depends(permission_required("reports.generate"))
):
    """
    **Export statistics in various formats**

    Permissions:
    - Requires: reports.generate

    Request Body:
    - format: "pdf", "excel", or "json"
    - period_days: Statistics period (1-365)
    - include_charts: Include visualizations (PDF/Excel only)
    - include_raw_data: Include raw data (all formats)

    Returns:
    - File download URL or file content

    Note: This is a placeholder - actual implementation requires
    PDF/Excel generation libraries
    """

    # TODO: Implement export logic
    # - PDF: Use reportlab or weasyprint
    # - Excel: Use openpyxl or xlsxwriter
    # - JSON: Direct serialization

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Export functionality not yet implemented"
    )


# ============================================================================
# ENDPOINTS - REAL-TIME DASHBOARD DATA
# ============================================================================

@router.get("/realtime/summary")
async def get_realtime_summary(
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_db_connection),
    _: None = Depends(permission_required("dashboard.view"))
):
    """
    **Get real-time summary for dashboard**

    Permissions:
    - Requires: dashboard.view

    Returns:
    - Current active assignments
    - Current pending assignments
    - Agents available vs busy
    - Overdue count
    - Alerts count

    Note: Optimized for frequent polling (every 30-60 seconds)
    Uses materialized views for performance

    Migration 048: Uses unified 'agent' role with agent_profiles for filtering
    """

    # Get agent context from agent_profiles
    # Admin sees all (no filtering by ministry/entity)
    if current_user.role == "admin":
        agent_ctx = {"entity_type": None, "ministry_id": None, "entity_id": None, "is_supervisor": True}
    else:
        agent_ctx = await get_agent_context(current_user.id, db)

    entity_type = agent_ctx.get("entity_type")
    entity_id = agent_ctx.get("ministry_id") or agent_ctx.get("entity_id")

    assignment_repo = get_assignment_repository(db)
    workload_repo = get_workload_repository(db)

    try:
        # Get active assignments
        active_assignments = await assignment_repo.get_active_assignments(db, agent_profile_id=None)
        pending = [a for a in active_assignments if a.status.value == "assigned"]
        in_progress = [a for a in active_assignments if a.status.value == "in_progress"]
        overdue = await assignment_repo.get_overdue_assignments(db)

        # Get agent availability - returns List[AgentWorkload] objects
        agents = await workload_repo.get_available_agents(db, max_workload_pct=100.0)

        available_count = sum(1 for a in agents if a.workload_status == "available")
        busy_count = sum(1 for a in agents if a.workload_status in ["normal", "busy"])
        overloaded_count = sum(1 for a in agents if a.workload_status == "overloaded")

        summary = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "active_assignments": len(active_assignments),
            "pending_assignments": len(pending),
            "in_progress_assignments": len(in_progress),
            "overdue_assignments": len(overdue),
            "total_agents": len(agents),
            "available_agents": available_count,
            "busy_agents": busy_count,
            "overloaded_agents": overloaded_count,
            "alerts": overloaded_count + len(overdue)
        }

        logger.debug(f"Real-time summary loaded for {entity_type}/{entity_id}")

        return summary

    except Exception as e:
        logger.error(f"Error getting real-time summary: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get real-time summary"
        )
