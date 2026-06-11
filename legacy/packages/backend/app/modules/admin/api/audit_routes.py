"""
Audit Log Routes - Audit Trail API

Provides read-only access to audit logs for administrators
Used by the frontend audit-logs-admin module

Routes:
- /api/v1/audit-logs - List and filter audit logs
- /api/v1/audit-logs/{id} - Get single audit log
- /api/v1/audit-logs/stats - Get audit statistics
- /api/v1/users/{user_id}/audit-logs - Get logs for a specific user
"""

from fastapi import APIRouter, HTTPException, Depends, status, Query, Path
from typing import List, Optional
from datetime import datetime
from loguru import logger

from app.modules.admin.models.admin import (
    AuditLogResponse,
    AuditLogFilter,
)
from app.modules.admin.repositories.audit_repository import AuditRepository
from app.modules.auth.middleware.auth_middleware import get_current_user
from app.modules.permissions.middleware.permission_middleware import permission_required
from app.database.connection import get_database

# =============================================================================
# ROUTER & DEPENDENCIES
# =============================================================================

router = APIRouter(tags=["Audit Logs"])
audit_repository = AuditRepository()


# =============================================================================
# RESPONSE MODELS
# =============================================================================

from pydantic import BaseModel
from typing import Dict, Any


class AuditLogListResponse(BaseModel):
    """Paginated audit logs response"""
    items: List[AuditLogResponse]
    total: int
    page: int
    page_size: int
    pages: int


class AuditLogStats(BaseModel):
    """Audit log statistics"""
    total_logs: int
    by_action: Dict[str, int]
    by_entity_type: Dict[str, int]


# =============================================================================
# AUDIT LOG ENDPOINTS
# =============================================================================

@router.get("", response_model=AuditLogListResponse)
async def list_audit_logs(
    action: Optional[str] = Query(None, description="Filter by action (create, update, delete, login, etc.)"),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    resource_type: Optional[str] = Query(None, alias="entity_type", description="Filter by resource/entity type"),
    success: Optional[bool] = Query(None, description="Filter by success status (not implemented yet)"),
    start_date: Optional[datetime] = Query(None, description="Filter from date"),
    end_date: Optional[datetime] = Query(None, description="Filter to date"),
    search: Optional[str] = Query(None, description="Search in entity_id or action"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    current_user=Depends(get_current_user),
    db=Depends(get_database),
    _: None = Depends(permission_required("audit.view")),
):
    """
    List audit logs with filters

    Requires audit.view permission
    """
    try:
        offset = (page - 1) * page_size

        # Use repository method
        logs, total = await audit_repository.list(
            conn=db,
            user_id=user_id,
            entity_type=resource_type,
            entity_id=search,  # Use search as entity_id filter
            action=action,
            start_date=start_date,
            end_date=end_date,
            limit=page_size,
            offset=offset,
        )

        items = []
        for i, log in enumerate(logs):
            try:
                items.append(AuditLogResponse(**log))
            except Exception as item_err:
                logger.warning(f"Skipping audit log #{i} (id={log.get('id')}): {item_err}")
                continue
        pages = (total + page_size - 1) // page_size

        return AuditLogListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        )

    except Exception as e:
        logger.error(f"Error listing audit logs: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving audit logs"
        )


@router.get("/stats", response_model=AuditLogStats)
async def get_audit_stats(
    start_date: Optional[datetime] = Query(None, description="Stats from date"),
    end_date: Optional[datetime] = Query(None, description="Stats to date"),
    current_user=Depends(get_current_user),
    db=Depends(get_database),
    _: None = Depends(permission_required("audit.view_stats")),
):
    """
    Get audit log statistics

    Requires audit.view_stats permission
    """
    try:
        stats = await audit_repository.get_stats(
            conn=db,
            start_date=start_date,
            end_date=end_date,
        )

        return AuditLogStats(**stats)

    except Exception as e:
        logger.error(f"Error getting audit stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving audit statistics"
        )


# =============================================================================
# GEMINI / AI COST MONITORING
# =============================================================================


class GeminiUsageStats(BaseModel):
    """Gemini API usage statistics"""
    total_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    error_count: int = 0
    fallback_count: int = 0
    avg_processing_time_ms: float = 0.0
    avg_confidence: float = 0.0
    daily_breakdown: List[Dict[str, Any]] = []
    by_workflow: List[Dict[str, Any]] = []
    by_document_category: List[Dict[str, Any]] = []


@router.get("/gemini-stats", response_model=GeminiUsageStats)
async def get_gemini_usage_stats(
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    current_user=Depends(get_current_user),
    db=Depends(get_database),
    _: None = Depends(permission_required("audit.view_stats")),
):
    """
    Get Gemini AI API usage statistics for cost monitoring.

    Queries gemini_processing_logs table for token usage, cost estimation,
    error rates, and breakdown by workflow/document type.

    Cached 60s per days param. Requires audit.view_stats permission.
    """
    from app.core.cache import get_cache

    cache = get_cache()
    cache_key = f"admin:gemini-stats:{days}"
    cached = await cache.get(cache_key)
    if cached:
        return GeminiUsageStats(**cached)

    try:
        # Gemini Flash pricing (USD per 1M tokens) — from Google AI pricing page
        INPUT_RATE = 0.075   # $0.075 per 1M input tokens
        OUTPUT_RATE = 0.30   # $0.30 per 1M output tokens

        # Use parameterized interval: $1::int * interval '1 day'
        interval_clause = "$1::int * interval '1 day'"

        # Overall stats
        overall_query = f"""
            SELECT
                COUNT(*) as total_calls,
                COALESCE(SUM(input_tokens), 0)::bigint as total_input_tokens,
                COALESCE(SUM(output_tokens), 0)::bigint as total_output_tokens,
                COALESCE(SUM(COALESCE(input_tokens, 0) + COALESCE(output_tokens, 0)), 0)::bigint as total_tokens,
                COUNT(*) FILTER (WHERE has_error = true) as error_count,
                COUNT(*) FILTER (WHERE used_fallback = true) as fallback_count,
                COALESCE(AVG(processing_time_ms), 0)::numeric as avg_processing_time_ms,
                COALESCE(AVG(extraction_confidence) FILTER (WHERE extraction_confidence IS NOT NULL), 0)::numeric as avg_confidence
            FROM gemini_processing_logs
            WHERE created_at >= NOW() - {interval_clause}
        """
        overall = await db.fetchrow(overall_query, days)

        total_input = int(overall['total_input_tokens']) if overall else 0
        total_output = int(overall['total_output_tokens']) if overall else 0
        estimated_cost = (total_input * INPUT_RATE + total_output * OUTPUT_RATE) / 1_000_000

        # Daily breakdown (for chart)
        daily_query = f"""
            SELECT
                created_at::date as day,
                COUNT(*) as calls,
                COALESCE(SUM(COALESCE(input_tokens, 0) + COALESCE(output_tokens, 0)), 0)::bigint as tokens,
                COUNT(*) FILTER (WHERE has_error = true) as errors
            FROM gemini_processing_logs
            WHERE created_at >= NOW() - {interval_clause}
            GROUP BY created_at::date
            ORDER BY day DESC
            LIMIT 60
        """
        daily_rows = await db.fetch(daily_query, days)
        daily_breakdown = [
            {"day": str(r['day']), "calls": r['calls'], "tokens": int(r['tokens']), "errors": r['errors']}
            for r in daily_rows
        ]

        # By workflow
        workflow_query = f"""
            SELECT
                COALESCE(workflow_code, 'unknown') as workflow,
                COUNT(*) as calls,
                COALESCE(SUM(COALESCE(input_tokens, 0) + COALESCE(output_tokens, 0)), 0)::bigint as tokens
            FROM gemini_processing_logs
            WHERE created_at >= NOW() - {interval_clause}
            GROUP BY workflow_code
            ORDER BY tokens DESC
            LIMIT 15
        """
        wf_rows = await db.fetch(workflow_query, days)
        by_workflow = [
            {"workflow": r['workflow'], "calls": r['calls'], "tokens": int(r['tokens'])}
            for r in wf_rows
        ]

        # By document category
        category_query = f"""
            SELECT
                COALESCE(document_category, 'other') as category,
                COUNT(*) as calls,
                COALESCE(SUM(COALESCE(input_tokens, 0) + COALESCE(output_tokens, 0)), 0)::bigint as tokens,
                COALESCE(AVG(extraction_confidence) FILTER (WHERE extraction_confidence IS NOT NULL), 0)::numeric as avg_confidence
            FROM gemini_processing_logs
            WHERE created_at >= NOW() - {interval_clause}
            GROUP BY document_category
            ORDER BY tokens DESC
        """
        cat_rows = await db.fetch(category_query, days)
        by_document_category = [
            {"category": r['category'], "calls": r['calls'], "tokens": int(r['tokens']),
             "avg_confidence": float(round(r['avg_confidence'], 2))}
            for r in cat_rows
        ]

        result = GeminiUsageStats(
            total_calls=overall['total_calls'] if overall else 0,
            total_input_tokens=total_input,
            total_output_tokens=total_output,
            total_tokens=total_input + total_output,
            estimated_cost_usd=round(estimated_cost, 4),
            error_count=overall['error_count'] if overall else 0,
            fallback_count=overall['fallback_count'] if overall else 0,
            avg_processing_time_ms=float(round(overall['avg_processing_time_ms'], 1)) if overall else 0,
            avg_confidence=float(round(overall['avg_confidence'], 2)) if overall else 0,
            daily_breakdown=daily_breakdown,
            by_workflow=by_workflow,
            by_document_category=by_document_category,
        )

        await cache.set(cache_key, result.model_dump(), ttl=60)
        return result

    except Exception as e:
        logger.error(f"Error getting Gemini usage stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving Gemini usage statistics"
        )


# =============================================================================
# SINGLE AUDIT LOG (must be AFTER /stats and /gemini-stats to avoid catch-all)
# =============================================================================

@router.get("/{audit_id}", response_model=AuditLogResponse)
async def get_audit_log(
    audit_id: str = Path(..., description="Audit log ID"),
    current_user=Depends(get_current_user),
    db=Depends(get_database),
    _: None = Depends(permission_required("audit.view")),
):
    """
    Get a single audit log by ID

    Requires audit.view permission
    """
    try:
        log = await audit_repository.get_by_id(conn=db, audit_id=audit_id)

        if not log:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Audit log {audit_id} not found"
            )

        return AuditLogResponse(**log)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting audit log {audit_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving audit log"
        )


@router.get("/entity/{entity_type}/{entity_id}", response_model=List[AuditLogResponse])
async def get_audit_logs_by_entity(
    entity_type: str = Path(..., description="Entity type (user, declaration, etc.)"),
    entity_id: str = Path(..., description="Entity ID"),
    limit: int = Query(50, ge=1, le=200, description="Maximum logs to return"),
    current_user=Depends(get_current_user),
    db=Depends(get_database),
    _: None = Depends(permission_required("audit.view")),
):
    """
    Get all audit logs for a specific entity

    Requires audit.view permission
    """
    try:
        logs = await audit_repository.get_by_entity(
            conn=db,
            entity_type=entity_type,
            entity_id=entity_id,
            limit=limit,
        )

        return [AuditLogResponse(**log) for log in logs]

    except Exception as e:
        logger.error(f"Error getting audit logs for {entity_type}/{entity_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving audit logs"
        )


# =============================================================================
# USER AUDIT LOGS (nested route)
# =============================================================================

user_audit_router = APIRouter(tags=["User Audit Logs"])


@user_audit_router.get("/{user_id}/audit-logs", response_model=List[AuditLogResponse])
async def get_user_audit_logs(
    user_id: str = Path(..., description="User ID"),
    action: Optional[str] = Query(None, description="Filter by action"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    current_user=Depends(get_current_user),
    db=Depends(get_database),
    _: None = Depends(permission_required("audit.view")),
):
    """
    Get audit logs for a specific user

    Requires audit.view permission

    This endpoint is mounted at /api/v1/users/{user_id}/audit-logs
    """
    try:
        offset = (page - 1) * page_size

        logs, _ = await audit_repository.list(
            conn=db,
            user_id=user_id,
            action=action,
            limit=page_size,
            offset=offset,
        )

        return [AuditLogResponse(**log) for log in logs]

    except Exception as e:
        logger.error(f"Error getting audit logs for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving user audit logs"
        )
