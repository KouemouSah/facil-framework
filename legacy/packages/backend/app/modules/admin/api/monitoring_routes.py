"""
Admin Operations Center + legacy Monitoring Endpoints.

Operations Center: aggregated business metrics (payments, agents, pipeline, integrations).
Legacy Monitoring: pg_stat_statements, pg_stat_activity, pg_locks (kept as fallback).
Protected by admin.monitoring permission.
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Dict, Any
from enum import Enum
from datetime import datetime, timezone
import asyncio
import asyncpg
from loguru import logger

from app.modules.auth.middleware.auth_middleware import get_current_user
from app.modules.permissions.middleware.permission_middleware import permission_required
from app.database.connection import get_database, db_manager

router = APIRouter(tags=["Admin - Monitoring"])


@router.get("/slow-queries")
async def get_slow_queries(
    limit: int = Query(20, le=50),
    min_calls: int = Query(5, ge=1),
    db: asyncpg.Connection = Depends(get_database),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _=Depends(permission_required("admin.monitoring")),
):
    """Top N slowest queries by mean execution time from pg_stat_statements."""
    rows = await db.fetch("""
        SELECT
            queryid,
            LEFT(query, 300) AS query_preview,
            calls,
            ROUND(total_exec_time::numeric, 2) AS total_exec_time_ms,
            ROUND(mean_exec_time::numeric, 2) AS mean_exec_time_ms,
            ROUND(max_exec_time::numeric, 2) AS max_exec_time_ms,
            ROUND(stddev_exec_time::numeric, 2) AS stddev_exec_time_ms,
            rows AS total_rows,
            shared_blks_hit,
            shared_blks_read,
            ROUND(
                shared_blks_hit::numeric
                / NULLIF(shared_blks_hit + shared_blks_read, 0) * 100, 2
            ) AS cache_hit_ratio
        FROM pg_stat_statements
        WHERE calls >= $1
          AND query NOT LIKE '%pg_stat%'
        ORDER BY mean_exec_time DESC
        LIMIT $2
    """, min_calls, limit)

    total_tracked = await db.fetchval(
        "SELECT COUNT(*) FROM pg_stat_statements"
    )

    return {
        "queries": [dict(r) for r in rows],
        "total_tracked": total_tracked,
    }


@router.get("/frequent-queries")
async def get_frequent_queries(
    limit: int = Query(20, le=50),
    db: asyncpg.Connection = Depends(get_database),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _=Depends(permission_required("admin.monitoring")),
):
    """Top N most-called queries from pg_stat_statements."""
    rows = await db.fetch("""
        SELECT
            queryid,
            LEFT(query, 300) AS query_preview,
            calls,
            ROUND(total_exec_time::numeric, 2) AS total_exec_time_ms,
            ROUND(mean_exec_time::numeric, 2) AS mean_exec_time_ms,
            rows AS total_rows,
            ROUND(
                shared_blks_hit::numeric
                / NULLIF(shared_blks_hit + shared_blks_read, 0) * 100, 2
            ) AS cache_hit_ratio
        FROM pg_stat_statements
        WHERE query NOT LIKE '%pg_stat%'
        ORDER BY calls DESC
        LIMIT $1
    """, limit)

    return {"queries": [dict(r) for r in rows]}


@router.get("/connection-pool")
async def get_connection_pool_stats(
    current_user: Dict[str, Any] = Depends(get_current_user),
    _=Depends(permission_required("admin.monitoring")),
):
    """Asyncpg connection pool metrics."""
    pool = db_manager.pool
    if not pool:
        return {"error": "Pool not initialized"}

    return {
        "min_size": pool.get_min_size(),
        "max_size": pool.get_max_size(),
        "current_size": pool.get_size(),
        "free_connections": pool.get_idle_size(),
        "used_connections": pool.get_size() - pool.get_idle_size(),
    }


@router.get("/database-stats")
async def get_database_stats(
    db: asyncpg.Connection = Depends(get_database),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _=Depends(permission_required("admin.monitoring")),
):
    """Table sizes, row estimates, and unused indexes."""
    tables = await db.fetch("""
        SELECT c.relname AS table_name,
               pg_size_pretty(pg_total_relation_size(c.oid)) AS total_size,
               pg_size_pretty(pg_relation_size(c.oid)) AS data_size,
               pg_size_pretty(pg_indexes_size(c.oid)) AS index_size,
               s.n_live_tup AS row_estimate
        FROM pg_class c
        JOIN pg_stat_user_tables s ON c.relname = s.relname
        WHERE c.relkind = 'r'
        ORDER BY pg_total_relation_size(c.oid) DESC
        LIMIT 30
    """)

    unused_indexes = await db.fetch("""
        SELECT schemaname,
               relname AS table_name,
               indexrelname AS index_name,
               pg_size_pretty(pg_relation_size(i.indexrelid)) AS size,
               idx_scan AS scan_count
        FROM pg_stat_user_indexes i
        JOIN pg_index pi ON i.indexrelid = pi.indexrelid
        WHERE idx_scan < 10
          AND NOT pi.indisunique
          AND pg_relation_size(i.indexrelid) > 8192
        ORDER BY pg_relation_size(i.indexrelid) DESC
        LIMIT 20
    """)

    return {
        "tables": [dict(r) for r in tables],
        "unused_indexes": [dict(r) for r in unused_indexes],
    }


@router.get("/lock-status")
async def get_lock_status(
    db: asyncpg.Connection = Depends(get_database),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _=Depends(permission_required("admin.monitoring")),
):
    """Current PostgreSQL lock status and active connections."""
    active_connections = await db.fetch("""
        SELECT pid, state,
               LEFT(query, 200) AS query,
               ROUND(EXTRACT(EPOCH FROM (NOW() - query_start))::numeric, 1) AS query_seconds,
               wait_event_type,
               wait_event
        FROM pg_stat_activity
        WHERE state != 'idle'
          AND pid != pg_backend_pid()
        ORDER BY query_start ASC
    """)

    lock_counts = await db.fetch("""
        SELECT mode, COUNT(*) AS count, granted
        FROM pg_locks
        WHERE pid != pg_backend_pid()
        GROUP BY mode, granted
        ORDER BY count DESC
    """)

    return {
        "active_connections": [dict(r) for r in active_connections],
        "lock_counts": [dict(r) for r in lock_counts],
    }


# ============================================================================
# OPERATIONS CENTER ENDPOINTS
# ============================================================================


@router.get("/operations/dashboard")
async def get_operations_dashboard(
    current_user: Dict[str, Any] = Depends(get_current_user),
    _=Depends(permission_required("admin.monitoring")),
):
    """Aggregated operational dashboard: payments, agents, pipeline, locks."""
    from app.core.cache import get_cache

    cache = get_cache()
    cache_key = "admin:ops:dashboard"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    # Run 4 independent queries in parallel using separate pool connections
    pool = db_manager.pool
    if not pool:
        raise HTTPException(status_code=503, detail="Database pool not initialized")

    async def _query_payments():
        async with pool.acquire() as conn:
            return await conn.fetch("""
                SELECT
                    sp.entity_code,
                    COUNT(*) FILTER (WHERE sp.workflow_status IN
                        ('pending_agent_review', 'agent_reviewing', 'auto_processing', 'submitted')
                    ) as pending_count,
                    COALESCE(SUM(sp.total_amount) FILTER (WHERE sp.workflow_status IN
                        ('pending_agent_review', 'agent_reviewing', 'auto_processing', 'submitted')
                    ), 0) as pending_amount,
                    ROUND(COALESCE(AVG(EXTRACT(EPOCH FROM (NOW() - sp.created_at)) / 3600)
                        FILTER (WHERE sp.workflow_status IN ('pending_agent_review', 'agent_reviewing')
                    ), 0)::numeric, 1) as avg_wait_hours,
                    COUNT(*) FILTER (WHERE sp.sla_target_date IS NOT NULL
                        AND sp.sla_target_date < NOW()
                        AND sp.workflow_status NOT IN
                            ('completed', 'cancelled_by_user', 'cancelled_by_agent', 'expired')
                    ) as sla_violated_count
                FROM service_payments sp
                WHERE sp.workflow_status NOT IN
                    ('completed', 'cancelled_by_user', 'cancelled_by_agent', 'expired')
                GROUP BY sp.entity_code
                ORDER BY pending_count DESC
            """)

    async def _query_agents():
        async with pool.acquire() as conn:
            return await conn.fetchrow("""
                SELECT
                    COUNT(*) as total_agents,
                    COUNT(*) FILTER (WHERE aw.availability = 'available'
                        AND aw.workload_status NOT IN ('unavailable', 'overloaded')
                    ) as agents_available,
                    COUNT(*) FILTER (WHERE aw.workload_status = 'overloaded') as agents_overloaded,
                    COUNT(*) FILTER (WHERE aw.availability != 'available') as agents_unavailable,
                    COUNT(*) FILTER (
                        WHERE GREATEST(
                            COALESCE(aw.last_assignment_at, ap.created_at),
                            COALESCE(aw.last_completion_at, ap.created_at)
                        ) < NOW() - INTERVAL '48 hours'
                        AND aw.availability = 'available'
                    ) as agents_inactive_48h,
                    ROUND(COALESCE(AVG(aw.capacity_percentage), 0)::numeric, 1) as avg_capacity
                FROM agent_profiles ap
                JOIN agent_workloads aw ON aw.agent_profile_id = ap.id
                WHERE ap.is_active = true
            """)

    async def _query_pipeline():
        async with pool.acquire() as conn:
            return await conn.fetchrow("""
                SELECT
                    COUNT(*) FILTER (WHERE sr.status = 'SUBMITTED') as submitted,
                    COUNT(*) FILTER (WHERE sr.status = 'UNDER_REVIEW') as under_review,
                    COUNT(*) FILTER (WHERE sr.status = 'IN_PROGRESS') as in_progress,
                    COUNT(*) FILTER (WHERE sr.status IN ('PAYMENT_PENDING', 'PAYMENT_PROCESSING')
                    ) as payment_phase,
                    COUNT(*) FILTER (WHERE sr.status = 'PAID') as paid,
                    COUNT(*) FILTER (WHERE sr.escalated = true
                        AND sr.status NOT IN ('COMPLETED', 'CANCELLED', 'REJECTED', 'EXPIRED')
                    ) as active_escalations,
                    COUNT(*) FILTER (WHERE sr.priority IN ('URGENT', 'HIGH')
                        AND sr.status NOT IN ('COMPLETED', 'CANCELLED', 'REJECTED', 'EXPIRED')
                    ) as high_priority,
                    COUNT(*) FILTER (WHERE sr.created_at >= NOW() - INTERVAL '24 hours'
                    ) as new_24h,
                    COUNT(*) FILTER (WHERE sr.status IN ('COMPLETED', 'DOSSIER_VALIDE')
                        AND sr.updated_at >= NOW() - INTERVAL '24 hours'
                    ) as completed_24h
                FROM service_requests sr
                WHERE sr.status != 'DRAFT'
            """)

    async def _query_stale_locks():
        async with pool.acquire() as conn:
            return await conn.fetchval("""
                SELECT COUNT(*) FROM service_payments sp
                WHERE sp.assigned_agent_id IS NOT NULL
                  AND sp.assigned_at < NOW() - INTERVAL '4 hours'
                  AND sp.workflow_status = 'agent_reviewing'
            """)

    payment_rows, agent_row, pipeline_row, stale_locks = await asyncio.gather(
        _query_payments(), _query_agents(), _query_pipeline(), _query_stale_locks()
    )

    by_entity = [dict(r) for r in payment_rows]
    total_pending = sum(r["pending_count"] for r in by_entity)
    total_pending_amount = float(sum(r["pending_amount"] for r in by_entity))

    # Pool stats (synchronous, no query needed)
    pool_stats = {
        "max_size": pool.get_max_size(),
        "current_size": pool.get_size(),
        "free": pool.get_idle_size(),
        "used": pool.get_size() - pool.get_idle_size(),
    }

    result = {
        "payments": {
            "by_entity": by_entity,
            "total_pending": total_pending,
            "total_pending_amount": total_pending_amount,
        },
        "agents": dict(agent_row) if agent_row else {
            "total_agents": 0, "agents_available": 0, "agents_overloaded": 0,
            "agents_unavailable": 0, "agents_inactive_48h": 0, "avg_capacity": 0,
        },
        "pipeline": dict(pipeline_row) if pipeline_row else {
            "submitted": 0, "under_review": 0, "in_progress": 0,
            "payment_phase": 0, "paid": 0, "active_escalations": 0,
            "high_priority": 0, "new_24h": 0, "completed_24h": 0,
        },
        "stale_locks": stale_locks or 0,
        "pool": pool_stats,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }

    await cache.set(cache_key, result, ttl=30)
    return result


@router.get("/operations/integrations")
async def get_integration_health(
    current_user: Dict[str, Any] = Depends(get_current_user),
    _=Depends(permission_required("admin.monitoring")),
):
    """Health status of all external integrations: DB, Redis, BANGE, Gemini."""
    from app.core.cache import get_cache

    cache = get_cache()
    cache_key = "admin:ops:integrations"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    # 1. Database — real connectivity check via pool
    db_status = "ok"
    try:
        pool = db_manager.pool
        if pool:
            async with pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
        else:
            db_status = "error: pool not initialized"
    except Exception as e:
        db_status = f"error: {str(e)[:100]}"

    # 2. Redis
    redis_result = {"status": "unknown"}
    try:
        from app.core.cache import get_cache_health
        redis_result = await get_cache_health()
        redis_status = redis_result.get("redis_status", "unknown")
    except Exception as e:
        redis_status = f"error: {str(e)[:100]}"
        redis_result = {"status": redis_status}

    # 3. BANGE
    bange_status = "unknown"
    bange_ms = None
    try:
        from app.modules.payments.services.bange_service import bange_service
        import time
        start = time.monotonic()
        bange_ok = await asyncio.wait_for(bange_service.health_check(), timeout=5.0)
        bange_ms = round((time.monotonic() - start) * 1000)
        bange_status = "ok" if bange_ok else "error"
    except asyncio.TimeoutError:
        bange_status = "timeout"
    except Exception as e:
        bange_status = f"error: {str(e)[:100]}"

    # 4. Gemini (SDK availability check only)
    try:
        from google.cloud import aiplatform  # noqa: F401
        gemini_status = "available"
    except ImportError:
        gemini_status = "unavailable"

    result = {
        "database": {"status": db_status},
        "redis": {
            "status": redis_status,
            "type": redis_result.get("cache_type", "unknown"),
            "enabled": redis_result.get("redis_enabled", False),
        },
        "bange": {"status": bange_status, "response_ms": bange_ms},
        "gemini": {"status": gemini_status},
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }

    await cache.set(cache_key, result, ttl=15)
    return result


class CronJobName(str, Enum):
    treasury_refresh_views = "treasury_refresh_views"
    cleanup_expired_holds = "cleanup_expired_holds"
    workload_rebalance = "workload_rebalance"
    assignment_health_check = "assignment_health_check"


# Whitelist for REFRESH MATERIALIZED VIEW — prevents SQL injection
_ALLOWED_MATERIALIZED_VIEWS = frozenset({
    "mv_treasury_daily_kpis",
    "mv_reconciliation_stats",
    "mv_agent_daily_workload",
    "mv_services_translated",
})


@router.post("/operations/trigger/{job_name}")
async def trigger_cron_job(
    job_name: CronJobName,
    db: asyncpg.Connection = Depends(get_database),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _=Depends(permission_required("admin.monitoring")),
):
    """Manually trigger a CRON job. Rate limited to 1 per minute per job."""
    from app.core.cache import get_cache

    cache = get_cache()
    rate_key = f"admin:ops:trigger:{job_name.value}"
    if await cache.get(rate_key):
        raise HTTPException(
            status_code=429,
            detail=f"Job {job_name.value} was triggered recently. Wait 60 seconds.",
        )

    # Set rate-limit BEFORE execution to prevent double-trigger during long jobs
    await cache.set(rate_key, {"triggered": True}, ttl=60)

    user_email = current_user.get("email", "unknown")
    logger.info(f"CRON_MANUAL_TRIGGER: {job_name.value} by {user_email}")

    result: Dict[str, Any] = {}

    if job_name == CronJobName.treasury_refresh_views:
        await db.execute("SET LOCAL statement_timeout = '300000'")
        refreshed = []
        errors = []
        for view in _ALLOWED_MATERIALIZED_VIEWS:
            try:
                # view is from frozen whitelist — safe for string interpolation
                await db.execute(
                    f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view}"
                )
                refreshed.append(view)
            except Exception as e:
                errors.append({"view": view, "error": str(e)[:200]})
        result = {"refreshed": refreshed, "errors": errors}

    elif job_name == CronJobName.cleanup_expired_holds:
        released = await db.fetchval("""
            WITH updated AS (
                UPDATE appointment_holds
                SET status = 'expired'
                WHERE status = 'held'
                  AND expires_at < NOW()
                RETURNING id
            )
            SELECT COUNT(*) FROM updated
        """)
        result = {"released_count": released or 0}

    elif job_name == CronJobName.workload_rebalance:
        try:
            from app.modules.assignment.services.workload_rebalance_service import (
                rebalance_entity_workload,
            )
            entities = await db.fetch(
                "SELECT DISTINCT e.code AS entity_code "
                "FROM agent_profiles ap "
                "JOIN entities e ON e.id = ap.entity_id "
                "WHERE ap.is_active = true AND ap.entity_id IS NOT NULL"
            )
            total_reassigned = 0
            for row in entities:
                try:
                    r = await rebalance_entity_workload(db, row["entity_code"])
                    if r and isinstance(r, dict):
                        total_reassigned += r.get("reassigned", 0)
                except Exception as e:
                    logger.warning(f"Rebalance {row['entity_code']} failed: {e}")
            result = {"total_reassigned": total_reassigned, "entities_processed": len(entities)}
        except ImportError:
            result = {"error": "workload_rebalance_service not available"}

    elif job_name == CronJobName.assignment_health_check:
        try:
            from app.modules.service_requests.services.assignment_outbox_service import (
                assignment_outbox_service,
            )
            r = await assignment_outbox_service.run_health_check(db)
            result = r if isinstance(r, dict) else {"status": "completed"}
        except ImportError:
            result = {"error": "assignment_outbox_service not available"}

    return {
        "job": job_name.value,
        "result": result,
        "triggered_by": user_email,
        "triggered_at": datetime.now(timezone.utc).isoformat(),
    }
