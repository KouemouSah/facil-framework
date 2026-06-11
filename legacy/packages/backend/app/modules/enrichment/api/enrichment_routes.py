"""
Enrichment API routes — cron processing + admin management + approval workflow.

Cron: POST /enrichment/cron/process (X-Cron-Secret auth)
Admin: POST /enrichment/admin/seed-batch, GET /enrichment/admin/stats
Approval: GET /enrichment/admin/pending-drafts, PUT /enrichment/admin/review/{id}
Progress: GET /enrichment/admin/progress (poll for background processing status)
"""

import asyncio
import json
from typing import Any, Dict, List, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger

from app.core.cache import check_rate_limit, get_cache, invalidate_services_cache
from app.database.connection import get_database
from app.modules.auth.dependencies import get_current_user, permission_required
from app.modules.users.models.user import UserResponse
from app.modules.enrichment.models.enrichment import (
    BulkVisibilityRequest,
    BulkVisibilityResponse,
    EnrichmentProcessResult,
    EnrichmentProgressResponse,
    EnrichmentReviewRequest,
    EnrichmentReviewResponse,
    EnrichmentSeedResult,
    EnrichmentStats,
    PendingDraftItem,
)
from app.modules.enrichment.repositories.enrichment_repository import (
    EnrichmentRepository,
)
from app.modules.enrichment.services.enrichment_service import (
    get_enrichment_service,
)

# Reuse cron auth from existing cron routes
from app.modules.service_requests.api.cron_routes import verify_cron_auth

router = APIRouter(prefix="/enrichment", tags=["Enrichment"])


# ============================================================================
# CRON ENDPOINT — called by Cloud Scheduler every 5 minutes (safety net)
# ============================================================================

@router.post(
    "/cron/process",
    response_model=EnrichmentProcessResult,
    summary="Process enrichment queue batch (cron safety net)",
    description="Processes up to 20 pending enrichment tasks via Gemini Flash. "
    "Called by Cloud Scheduler every 5 minutes as a safety net.",
)
async def process_enrichment_batch(
    _auth: bool = Depends(verify_cron_auth),
    db=Depends(get_database),
):
    """Process a batch of pending enrichment tasks (sequential, backward compat)."""
    service = get_enrichment_service()

    result = await service.process_batch(db, limit=20)

    # Refresh materialized view if any tasks completed
    if result.get("processed", 0) > 0:
        try:
            async with db.transaction():
                await db.execute("SET LOCAL statement_timeout = '120000'")
                await db.execute(
                    "REFRESH MATERIALIZED VIEW CONCURRENTLY mv_services_translated"
                )
            logger.info("mv_services_translated refreshed after enrichment")
        except Exception as e:
            logger.warning(f"MV refresh CONCURRENTLY failed: {e}")
            try:
                await db.execute("REFRESH MATERIALIZED VIEW mv_services_translated")
                logger.info("mv_services_translated refreshed (non-concurrent fallback)")
            except Exception as e2:
                logger.error(f"MV refresh fallback also failed: {e2}")

        await invalidate_services_cache()

    return EnrichmentProcessResult(**result)


# ============================================================================
# ADMIN — Progress Monitoring (poll endpoint for background processing)
# ============================================================================

@router.get(
    "/admin/progress",
    response_model=EnrichmentProgressResponse,
    summary="Get background enrichment processing progress",
)
async def get_enrichment_progress(
    current_user: UserResponse = Depends(get_current_user),
    _perm: None = Depends(permission_required("fiscal_service.view")),
):
    """Poll for enrichment agent progress. Frontend calls this every 2s during processing."""
    cache = get_cache()
    progress = await cache.get("enrichment:progress")
    if not progress:
        return EnrichmentProgressResponse(status="idle")
    return EnrichmentProgressResponse(**progress)


# ============================================================================
# ADMIN — Manual Processing Trigger (Option A)
# ============================================================================

@router.post(
    "/admin/process-now",
    response_model=EnrichmentProgressResponse,
    summary="Manually trigger full enrichment queue processing",
    description="Starts background processing of ALL pending tasks with concurrent Gemini calls. "
    "Poll GET /admin/progress for real-time updates.",
)
async def admin_process_now(
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database),
    _perm: None = Depends(permission_required("fiscal_service.create")),
):
    """Admin-triggered processing — fires concurrent agent in background."""
    user_id = current_user.id

    is_allowed, _ = await check_rate_limit(
        identifier=str(user_id),
        endpoint="/enrichment/admin/process-now",
        max_requests=3,
        window_seconds=60,
    )
    if not is_allowed:
        raise HTTPException(
            status_code=429,
            detail="Process-now can only be called 3 times per minute. Wait for tasks to complete.",
        )

    service = get_enrichment_service()

    # Check if already running
    cache = get_cache()
    progress = await cache.get("enrichment:progress")
    if progress and progress.get("status") == "running":
        logger.info(f"Admin {user_id} tried process-now but agent is already running")
        return EnrichmentProgressResponse(**progress)

    # Count pending for immediate feedback
    total_pending = await EnrichmentRepository.count_pending(db)
    if total_pending == 0:
        return EnrichmentProgressResponse(status="idle", total=0)

    # Fire-and-forget: start concurrent processing in background
    asyncio.create_task(service.process_all_pending())

    logger.info(
        f"Admin {user_id} triggered process-now: {total_pending} pending tasks → "
        f"background agent started"
    )

    return EnrichmentProgressResponse(
        status="running",
        total=total_pending,
        processed=0,
        failed=0,
    )


# ============================================================================
# ADMIN ENDPOINTS — Seed (Option B: auto-triggers processing after seed)
# ============================================================================

@router.post(
    "/admin/seed-batch",
    response_model=EnrichmentSeedResult,
    summary="Seed enrichment queue + auto-process all (Option B)",
)
async def seed_enrichment_batch(
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database),
    _perm: None = Depends(permission_required("fiscal_service.create")),
):
    """
    Enqueue tasks for all active services + auto-trigger concurrent processing.
    One-click flow: Seed → Processing starts automatically in background.
    Poll GET /admin/progress for real-time updates.
    """
    user_id = current_user.id

    is_allowed, remaining = await check_rate_limit(
        identifier=str(user_id),
        endpoint="/enrichment/admin/seed-batch",
        max_requests=1,
        window_seconds=60,
    )
    if not is_allowed:
        raise HTTPException(
            status_code=429,
            detail="Seed-batch can only be called once per minute. Try again shortly.",
        )

    counts = await EnrichmentRepository.seed_descriptions(db)
    total_enqueued = counts["descriptions"] + counts["translations"] + counts.get("keywords", 0)

    logger.info(
        f"Admin {user_id} triggered enrichment seed: "
        f"{counts['descriptions']} descriptions, {counts['translations']} translations, "
        f"{counts.get('keywords', 0)} keywords"
    )

    # Option B: Auto-trigger concurrent processing in background
    auto_processing = False
    if total_enqueued > 0:
        service = get_enrichment_service()
        asyncio.create_task(service.process_all_pending())
        auto_processing = True
        logger.info(f"Enrichment agent auto-started: {total_enqueued} tasks enqueued")

    return EnrichmentSeedResult(
        enqueued_descriptions=counts["descriptions"],
        enqueued_translations=counts["translations"],
        enqueued_keywords=counts.get("keywords", 0),
        auto_processing=auto_processing,
    )


@router.post(
    "/admin/seed-ministries",
    summary="Seed ministry descriptions + auto-process (Option B)",
)
async def seed_ministry_descriptions(
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database),
    _perm: None = Depends(permission_required("fiscal_service.create")),
):
    """
    Enqueue ministry descriptions + auto-trigger concurrent processing.
    One-click flow: Seed → Processing starts automatically in background.
    """
    user_id = current_user.id

    is_allowed, remaining = await check_rate_limit(
        identifier=str(user_id),
        endpoint="/enrichment/admin/seed-ministries",
        max_requests=1,
        window_seconds=60,
    )
    if not is_allowed:
        raise HTTPException(
            status_code=429,
            detail="Seed-ministries can only be called once per minute.",
        )

    count = await EnrichmentRepository.seed_ministry_descriptions(db)

    logger.info(f"Admin {user_id} triggered ministry seed: {count} enqueued")

    # Option B: Auto-trigger concurrent processing
    auto_processing = False
    if count > 0:
        service = get_enrichment_service()
        asyncio.create_task(service.process_all_pending())
        auto_processing = True
        logger.info(f"Enrichment agent auto-started: {count} ministry tasks enqueued")

    return {
        "enqueued_ministry_descriptions": count,
        "auto_processing": auto_processing,
    }


# ============================================================================
# ADMIN — Stats
# ============================================================================

@router.get(
    "/admin/stats",
    response_model=EnrichmentStats,
    summary="Get enrichment queue statistics and service coverage",
)
async def get_enrichment_stats(
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database),
    _perm: None = Depends(permission_required("fiscal_service.view")),
):
    """Return queue stats + service description/translation coverage."""
    stats = await EnrichmentRepository.get_stats(db)
    return EnrichmentStats(**stats)


@router.get(
    "/admin/recent",
    summary="Get recent completed/failed enrichment tasks",
)
async def get_recent_enrichments(
    limit: int = Query(default=20, ge=1, le=100),
    status_filter: Literal["all", "completed", "failed", "pending"] = Query(default="all"),
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database),
    _perm: None = Depends(permission_required("fiscal_service.view")),
):
    """Return recent tasks with output preview. Filterable by status."""
    status_clause = ""
    params: list = []
    idx = 1

    if status_filter != "all":
        status_clause = f"AND eq.status = ${idx}"
        params.append(status_filter)
        idx += 1

    params.append(limit)

    rows = await db.fetch(
        f"""
        SELECT eq.id, eq.fiscal_service_id, eq.task_type, eq.status,
               eq.tokens_used, eq.output_data, eq.error_message,
               eq.attempts, eq.processed_at, eq.created_at,
               fs.service_code, fs.name_es,
               m.ministry_code, m.name_es as ministry_name
        FROM enrichment_queue eq
        LEFT JOIN fiscal_services fs ON fs.id = eq.fiscal_service_id
            AND eq.task_type != 'generate_ministry_description'
        LEFT JOIN ministries m ON m.id = eq.fiscal_service_id
            AND eq.task_type = 'generate_ministry_description'
        WHERE 1=1 {status_clause}
        ORDER BY eq.processed_at DESC NULLS LAST, eq.created_at DESC
        LIMIT ${idx}
        """,
        *params,
    )
    return [dict(r) for r in rows]


# ============================================================================
# APPROVAL WORKFLOW — Review AI-generated descriptions
# ============================================================================

@router.get(
    "/admin/pending-drafts",
    response_model=List[PendingDraftItem],
    summary="List services with AI draft descriptions awaiting approval",
)
async def get_pending_drafts(
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database),
    _perm: None = Depends(permission_required("fiscal_service.view")),
):
    """Return services with description_source='ai_draft' (pending admin review)."""
    rows = await db.fetch("""
        SELECT fs.id, fs.service_code, fs.name_es, fs.description_es,
               fs.description_source, fs.updated_at,
               c.name_es as category_name,
               m.name_es as ministry_name
        FROM fiscal_services fs
        LEFT JOIN categories c ON c.id = fs.category_id
        LEFT JOIN sectors s ON s.id = c.sector_id
        LEFT JOIN ministries m ON m.id = s.ministry_id
        WHERE fs.description_source = 'ai_draft'
          AND fs.status = 'active'
        ORDER BY fs.updated_at DESC
    """)
    return [PendingDraftItem(**dict(r)) for r in rows]


@router.get(
    "/admin/pending-ministry-drafts",
    summary="List ministries with AI draft descriptions awaiting approval",
)
async def get_pending_ministry_drafts(
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database),
    _perm: None = Depends(permission_required("fiscal_service.view")),
):
    """Return ministries with description_source='ai_draft'."""
    rows = await db.fetch("""
        SELECT m.id, m.ministry_code as service_code, m.name_es,
               m.description_es, m.description_source, m.updated_at
        FROM ministries m
        WHERE m.description_source = 'ai_draft'
        ORDER BY m.updated_at DESC
    """)
    return [dict(r) for r in rows]


@router.put(
    "/admin/review/{service_id}",
    response_model=EnrichmentReviewResponse,
    summary="Approve or reject an AI-generated service description",
)
async def review_service_description(
    service_id: int,
    body: EnrichmentReviewRequest,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database),
    _perm: None = Depends(permission_required("fiscal_service.create")),
):
    """
    Approve: description_source → 'ai_approved', description_visible → true.
    Reject: description_es → NULL, description_source → NULL.
    """
    user_id = current_user.id

    row = await db.fetchrow(
        "SELECT id, description_source FROM fiscal_services WHERE id = $1",
        service_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Service not found")
    if row["description_source"] != "ai_draft":
        raise HTTPException(
            status_code=409,
            detail=f"Service description_source is '{row['description_source']}', not 'ai_draft'",
        )

    if body.action == "approve":
        if body.edited_text:
            await db.execute(
                """
                UPDATE fiscal_services
                SET description_es = $1, description_source = 'ai_approved',
                    description_visible = true, updated_at = NOW()
                WHERE id = $2 AND description_source = 'ai_draft'
                """,
                body.edited_text.strip(),
                service_id,
            )
        else:
            await db.execute(
                """
                UPDATE fiscal_services
                SET description_source = 'ai_approved',
                    description_visible = true, updated_at = NOW()
                WHERE id = $1 AND description_source = 'ai_draft'
                """,
                service_id,
            )
        new_source = "ai_approved"
    else:
        await db.execute(
            """
            UPDATE fiscal_services
            SET description_es = NULL, description_source = NULL,
                description_visible = false, updated_at = NOW()
            WHERE id = $1 AND description_source = 'ai_draft'
            """,
            service_id,
        )
        new_source = None

    await invalidate_services_cache()
    logger.info(
        f"Admin {user_id} {body.action}d description for service {service_id}"
    )

    return EnrichmentReviewResponse(
        service_id=service_id,
        action=body.action,
        previous_source="ai_draft",
        new_source=new_source,
    )


@router.put(
    "/admin/review-ministry/{ministry_id}",
    summary="Approve or reject an AI-generated ministry description",
)
async def review_ministry_description(
    ministry_id: int,
    body: EnrichmentReviewRequest,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database),
    _perm: None = Depends(permission_required("fiscal_service.create")),
):
    """Approve or reject ministry AI draft description."""
    user_id = current_user.id

    row = await db.fetchrow(
        "SELECT id, description_source FROM ministries WHERE id = $1",
        ministry_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Ministry not found")
    if row["description_source"] != "ai_draft":
        raise HTTPException(
            status_code=409,
            detail=f"Ministry description_source is '{row['description_source']}', not 'ai_draft'",
        )

    if body.action == "approve":
        if body.edited_text:
            await db.execute(
                """UPDATE ministries
                SET description_es = $1, description_source = 'ai_approved', updated_at = NOW()
                WHERE id = $2""",
                body.edited_text.strip(),
                ministry_id,
            )
        else:
            await db.execute(
                """UPDATE ministries
                SET description_source = 'ai_approved', updated_at = NOW()
                WHERE id = $1""",
                ministry_id,
            )
    else:
        await db.execute(
            """UPDATE ministries
            SET description_es = NULL, description_source = NULL, updated_at = NOW()
            WHERE id = $1""",
            ministry_id,
        )

    logger.info(f"Admin {user_id} {body.action}d ministry description {ministry_id}")
    return {"ministry_id": ministry_id, "action": body.action}


@router.post(
    "/admin/approve-all",
    summary="Bulk approve all AI draft descriptions",
)
async def approve_all_drafts(
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database),
    _perm: None = Depends(permission_required("fiscal_service.create")),
):
    """Approve all services and ministries with description_source='ai_draft'."""
    user_id = current_user.id

    is_allowed, _ = await check_rate_limit(
        identifier=str(user_id),
        endpoint="/enrichment/admin/approve-all",
        max_requests=1,
        window_seconds=60,
    )
    if not is_allowed:
        raise HTTPException(status_code=429, detail="Approve-all limited to once per minute.")

    async with db.transaction():
        svc_result = await db.execute(
            """UPDATE fiscal_services
            SET description_source = 'ai_approved', description_visible = true, updated_at = NOW()
            WHERE description_source = 'ai_draft' AND status = 'active'"""
        )
        svc_count = int(svc_result.split()[-1]) if svc_result else 0

        min_result = await db.execute(
            """UPDATE ministries
            SET description_source = 'ai_approved', updated_at = NOW()
            WHERE description_source = 'ai_draft'"""
        )
        min_count = int(min_result.split()[-1]) if min_result else 0

        if svc_count > 0 or min_count > 0:
            await db.execute(
                """INSERT INTO audit_logs (user_id, entity_type, entity_id, action, new_values, created_at)
                VALUES ($1::uuid, 'fiscal_services', 'bulk_approve', 'enrichment_bulk_approve',
                    $2::jsonb, NOW())""",
                str(user_id),
                json.dumps({
                    "approved_services": svc_count,
                    "approved_ministries": min_count,
                }),
            )

    if svc_count > 0:
        await invalidate_services_cache()

    logger.info(
        f"Admin {user_id} bulk approved: {svc_count} services, {min_count} ministries"
    )
    return {
        "approved_services": svc_count,
        "approved_ministries": min_count,
    }


@router.patch(
    "/admin/bulk-visibility",
    response_model=BulkVisibilityResponse,
    summary="Bulk toggle description_visible for fiscal services",
)
async def bulk_toggle_visibility(
    body: BulkVisibilityRequest,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database),
    _perm: None = Depends(permission_required("fiscal_service.create")),
):
    """Bulk set description_visible = true/false for active fiscal services."""
    user_id = current_user.id

    is_allowed, _ = await check_rate_limit(
        identifier=str(user_id),
        endpoint="/enrichment/admin/bulk-visibility",
        max_requests=3,
        window_seconds=60,
    )
    if not is_allowed:
        raise HTTPException(status_code=429, detail="Bulk visibility limited to 3 times per minute.")

    conditions = ["status = 'active'"]
    params: list = [body.visible]
    idx = 2

    filters_applied: Dict[str, Any] = {"visible": body.visible}

    if body.description_source is not None:
        conditions.append(f"description_source = ${idx}")
        params.append(body.description_source)
        filters_applied["description_source"] = body.description_source
        idx += 1

    if body.ministry_id is not None:
        conditions.append(f"""category_id IN (
            SELECT c.id FROM categories c
            JOIN sectors s ON s.id = c.sector_id
            WHERE s.ministry_id = ${idx}
        )""")
        params.append(body.ministry_id)
        filters_applied["ministry_id"] = body.ministry_id
        idx += 1

    where_clause = " AND ".join(conditions)

    async with db.transaction():
        result = await db.execute(
            f"""UPDATE fiscal_services
            SET description_visible = $1, updated_at = NOW()
            WHERE {where_clause}""",
            *params,
        )
        affected = int(result.split()[-1]) if result else 0

        if affected > 0:
            await db.execute(
                """INSERT INTO audit_logs (user_id, entity_type, entity_id, action, new_values, created_at)
                VALUES ($1::uuid, 'fiscal_services', 'bulk_visibility', 'enrichment_bulk_visibility',
                    $2::jsonb, NOW())""",
                str(user_id),
                json.dumps({"affected": affected, **filters_applied}),
            )

    if affected > 0:
        await invalidate_services_cache()

    logger.info(
        f"Admin {user_id} bulk visibility: {affected} services → visible={body.visible} "
        f"(filters: {filters_applied})"
    )

    return BulkVisibilityResponse(
        affected=affected,
        visible=body.visible,
        filters_applied=filters_applied,
    )


@router.get(
    "/admin/ministries",
    summary="List ministries with service counts for bulk filters",
)
async def list_ministries_for_filter(
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database),
    _perm: None = Depends(permission_required("fiscal_service.view")),
):
    """Return ministries with active service counts for the bulk visibility filter."""
    rows = await db.fetch("""
        SELECT m.id, m.name_es, COUNT(fs.id) as service_count
        FROM ministries m
        JOIN sectors s ON s.ministry_id = m.id
        JOIN categories c ON c.sector_id = s.id
        JOIN fiscal_services fs ON fs.category_id = c.id AND fs.status = 'active'
        GROUP BY m.id, m.name_es
        ORDER BY m.name_es
    """)
    return [dict(r) for r in rows]


@router.post(
    "/admin/retry/{task_id}",
    summary="Retry a failed enrichment task",
)
async def retry_failed_task(
    task_id: UUID,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database),
    _perm: None = Depends(permission_required("fiscal_service.create")),
):
    """Reset a failed task back to pending for reprocessing."""
    result = await db.execute(
        """
        UPDATE enrichment_queue
        SET status = 'pending', attempts = 0, error_message = NULL,
            processed_at = NULL
        WHERE id = $1 AND status = 'failed'
        """,
        task_id,
    )
    if result == "UPDATE 0":
        raise HTTPException(
            status_code=404,
            detail="Task not found or not in 'failed' status",
        )

    logger.info(f"Admin {current_user.id} retried task {task_id}")
    return {"task_id": str(task_id), "new_status": "pending"}
