"""
Agent Routes for Service Requests.

RESTful endpoints for agents to process service requests.
Includes queue management, approval/rejection, and appointment scheduling.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path, Body, BackgroundTasks
from app.core.errors import TranslatedException, ErrorCode
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import date, time, datetime, timezone
import asyncio
import asyncpg
import json
import logging

logger = logging.getLogger(__name__)

from pydantic import BaseModel, Field

from app.config import get_settings
from app.database.connection import get_database, get_db_pool
from app.modules.auth.middleware.auth_middleware import get_current_user
from app.modules.permissions.middleware.permission_middleware import permission_required
from app.modules.users.models.user import UserResponse as User
from ..services.agent_queue_service import agent_queue_service
from ..services.appointment_scheduler import appointment_scheduler
from ..services.service_request_service import service_request_service
from ..services.workflow_engine import workflow_engine
from ..services.summary_pdf_service import SummaryPDFService
from ..models.service_request import ServiceRequestResponse
from ..models.history import (
    HistoryActionType,
    HistoryEntry,
    HistoryEntrySource,
    HistoryListResponse,
    HistoryListSummaryResponse,
    HistorySummaryItem,
    PerformerInfo,
)
from ..repositories.service_request_repository import service_request_repository
from app.core.events import EventBus, EventType
from app.modules.batch_requests.repositories.batch_repository import batch_repository
from dataclasses import dataclass


router = APIRouter(
    prefix="/agent/service-requests",
    tags=["Agent - Service Requests"]
)


# ═══════════════════════════════════════════════════════════════
# AGENT CONTEXT — single query per HTTP request
# ═══════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class AgentContext:
    """Agent profile data resolved once per HTTP request via Depends().

    Scoping rules:
    - has_global_scope (supervisor + main_office) → sees ALL sites/requests
    - is_supervisor + NOT main_office → site-level supervisor: sees own site only,
      but can manage team (see all requests at their site, not just assigned)
    - regular agent → sees own site, only their assigned requests
    """
    profile_id: Optional[UUID]
    entity_location_id: Optional[UUID]
    is_supervisor: bool
    is_main_office: bool
    user_id: UUID

    @property
    def has_profile(self) -> bool:
        return self.profile_id is not None

    @property
    def has_global_scope(self) -> bool:
        """Only supervisors at main office see all sites."""
        return self.is_supervisor and self.is_main_office


async def get_agent_context(
    current_user: User = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_database),
) -> AgentContext:
    """
    FastAPI dependency — resolves agent profile in 1 SQL query.
    FastAPI caches Depends() results per request, so this runs at most once
    even if multiple sub-dependencies or the endpoint itself inject it.
    """
    row = await db.fetchrow("""
        SELECT ap.id, ap.entity_location_id, ap.is_supervisor,
               COALESCE(el.is_main_office, false) AS is_main_office
        FROM agent_profiles ap
        LEFT JOIN entity_locations el ON el.id = ap.entity_location_id
        WHERE ap.user_id = $1 AND ap.is_active = true
        LIMIT 1
    """, current_user.id)

    if row:
        return AgentContext(
            profile_id=row['id'],
            entity_location_id=row['entity_location_id'],
            is_supervisor=row['is_supervisor'] or False,
            is_main_office=row['is_main_office'],
            user_id=current_user.id,
        )
    return AgentContext(
        profile_id=None,
        entity_location_id=None,
        is_supervisor=False,
        is_main_office=False,
        user_id=current_user.id,
    )


# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════

async def _publish_batch_completed_event(db: asyncpg.Connection, batch_id: UUID) -> None:
    """Publish BATCH_COMPLETED event with batch details for notification."""
    try:
        batch = await db.fetchrow("""
            SELECT br.reference, br.workflow_code, br.total_items,
                   br.total_amount, br.currency, br.submitted_by,
                   u.email, u.full_name
            FROM batch_requests br
            LEFT JOIN users u ON u.id = br.submitted_by
            WHERE br.id = $1
        """, batch_id)
        if batch:
            EventBus.publish_nowait(EventType.BATCH_COMPLETED, {
                "batch_id": str(batch_id),
                "batch_reference": batch["reference"],
                "user_id": str(batch["submitted_by"]),
                "user_email": batch["email"],
                "user_name": batch["full_name"] or "",
                "workflow_code": batch["workflow_code"],
                "total_items": batch["total_items"],
                "amount": float(batch["total_amount"] or 0),
                "currency": batch["currency"] or "XAF",
                "preferred_language": "es",
            })
    except Exception as e:
        logger.error(f"Failed to publish BATCH_COMPLETED for {batch_id}: {e}")


# ═══════════════════════════════════════════════════════════════
# PYDANTIC MODELS FOR AGENT ACTIONS
# ═══════════════════════════════════════════════════════════════

class AgentDecision(BaseModel):
    """Agent decision on a service request"""
    decision: str = Field(
        ...,
        pattern="^(approve|reject|request_documents)$",
        description="Decision: approve, reject, or request_documents"
    )
    comments: Optional[str] = Field(None, max_length=2000)
    rejection_reason: Optional[str] = Field(None, max_length=500)
    requested_documents: Optional[List[str]] = Field(
        default=None,
        description="List of document codes to request"
    )


class AppointmentSchedule(BaseModel):
    """Manual appointment scheduling"""
    appointment_date: date
    appointment_time: time
    location: Optional[str] = None
    notes: Optional[str] = None


class EscalationRequest(BaseModel):
    """Escalation request"""
    reason: str = Field(..., min_length=10, max_length=500)
    priority_boost: int = Field(default=10, ge=0, le=50)


# ═══════════════════════════════════════════════════════════════
# MODELS FOR ASSIGNED REQUESTS (Appointment Scheduling)
# ═══════════════════════════════════════════════════════════════

class ExistingAppointmentInfo(BaseModel):
    """Info about existing appointment for a request"""
    reservation_id: str
    date: str
    time: str
    location_name: Optional[str] = None
    status: str


class AssignedRequestForAppointment(BaseModel):
    """Service request assigned to agent, for appointment dropdown"""
    id: str
    reference: str
    citizen_name: str
    workflow_code: str
    status: str
    created_at: str
    existing_appointment: Optional[ExistingAppointmentInfo] = None


class AssignedRequestsListResponse(BaseModel):
    """List of assigned requests for appointment scheduling"""
    requests: List[AssignedRequestForAppointment]
    total: int


class QueueItemResponse(BaseModel):
    """Queue item with service request details"""
    queue_id: str
    item_type: str
    item_id: str
    workflow_code: str
    reference_number: str
    citizen_name: str
    priority_score: float
    sla_deadline: Optional[str]
    sla_status: str
    status: str
    assigned_to: Optional[str]
    created_at: str


class QueueStatsResponse(BaseModel):
    """Queue statistics"""
    pending: int
    assigned: int
    completed_today: int
    escalated: int
    sla_violations: int
    avg_processing_hours: float


# ═══════════════════════════════════════════════════════════════
# QUEUE MANAGEMENT
# ═══════════════════════════════════════════════════════════════

@router.get(
    "/queue",
    response_model=List[QueueItemResponse],
    summary="Get pending queue items",
    description="""
    Get pending service request items from the work queue.

    Returns items ordered by priority (highest first) and creation time.
    Only shows items from the agent's assigned ministry/entity.

    **Pagination:**
    - Use `page` and `page_size` for paginated results
    - Default returns all items (no limit) for agent visibility
    """
)
async def get_queue(
    entity_code: Optional[str] = Query(None, description="Filter by entity code"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(100, ge=1, le=200, description="Items per page (max 200)"),
    db: asyncpg.Connection = Depends(get_database),
    agent_ctx: AgentContext = Depends(get_agent_context),
    _=Depends(permission_required("service_request.view_queue"))
):
    # Calculate offset for pagination
    offset = (page - 1) * page_size

    # Global scope (main-office supervisor) sees all sites; others see only their site
    site_filter = None if agent_ctx.has_global_scope else agent_ctx.entity_location_id

    items = await agent_queue_service.get_pending_items(
        db=db,
        entity_code=entity_code,
        entity_location_id=site_filter,
        limit=page_size,
        offset=offset
    )

    result = []
    for item in items:
        sla_status = "on_track"
        if item.get('sla_deadline'):
            from datetime import datetime, timezone
            deadline = item['sla_deadline']
            now = datetime.now(timezone.utc)
            if deadline < now:
                sla_status = "violated"
            elif (deadline - now).total_seconds() < get_settings().QUEUE_SLA_WARNING_HOURS * 3600:
                sla_status = "at_risk"

        result.append(QueueItemResponse(
            queue_id=str(item['id']),
            item_type=item['item_type'],
            item_id=item['item_id'],
            workflow_code=item.get('workflow_code', item.get('declaration_type', '')),
            reference_number=item.get('reference_number', ''),
            citizen_name=item.get('citizen_name', 'Unknown'),
            priority_score=float(item.get('priority_score', 0)),
            sla_deadline=item['sla_deadline'].isoformat() if item.get('sla_deadline') else None,
            sla_status=sla_status,
            status=item['status'],
            assigned_to=item.get('assigned_to'),
            created_at=item['created_at'].isoformat()
        ))

    return result


@router.get(
    "/queue/stats",
    response_model=QueueStatsResponse,
    summary="Get queue statistics",
    description="Get statistics about the current queue status. Uses service_requests for workflow-based entities and service_payments for bundle collection entities."
)
async def get_queue_stats(
    entity_code: Optional[str] = Query(None, description="Filter by entity code"),
    db: asyncpg.Connection = Depends(get_database),
    agent_ctx: AgentContext = Depends(get_agent_context),
    _=Depends(permission_required("service_request.view_queue_stats"))
):
    # Resolve entity's workflow_codes to decide routing:
    #   - Bundle collection entity (workflow_codes == ['BUNDLE_PAYMENT']):
    #     count service_payments scoped by entity_code + agent (P8.2-B2).
    #     A bundle SR has a single primary_entity so the legacy
    #     service_requests-based path cannot attribute splits to AYUNT /
    #     CAMARA / MIN_* — every entity ends up seeing the same 4 bundle SRs.
    #   - Workflow-based entity (CNEDOGE_PASAPORTE, DGT, etc.): unchanged,
    #     count service_requests by workflow_code.
    entity_workflows: list = []
    if entity_code:
        raw = await db.fetchval(
            "SELECT workflow_codes FROM entities WHERE code = $1 AND is_active = true",
            entity_code
        )
        if raw:
            if isinstance(raw, str):
                import json as _json
                entity_workflows = _json.loads(raw)
            else:
                entity_workflows = list(raw)

    is_bundle_entity = (
        entity_code is not None
        and entity_workflows == ["BUNDLE_PAYMENT"]
    )

    # Distinguish payment validators (TESORO/AYUNT/CAMARA → count sp)
    # from obligation processors (MIN_* → count license_obligations).
    # Check: does ANY agent of this entity have treasury.validate_payment?
    # Uses entity_id → agent_profiles → users → role → role_permissions chain.
    is_obligation_processor = False
    if is_bundle_entity:
        has_treasury_perm = await db.fetchval("""
            SELECT EXISTS(
                SELECT 1 FROM agent_profiles ap
                JOIN users u ON u.id = ap.user_id
                JOIN role_permissions rp ON rp.role_id = u.role_id
                JOIN permissions p ON p.id = rp.permission_id
                WHERE ap.entity_id = (SELECT id FROM entities WHERE code = $1)
                  AND p.name = 'treasury.validate_payment'
                  AND ap.is_active = true
            )
        """, entity_code)
        is_obligation_processor = not has_treasury_perm

    if is_bundle_entity and is_obligation_processor:
        # ─────────────────────────────────────────────────────────────────
        # Obligation processor path (MIN_*): count license_obligations
        # via assignments. These entities process obligations AFTER payment
        # is validated — "pending" means "to process", not "to collect".
        # ─────────────────────────────────────────────────────────────────
        obl_where = []
        obl_params: list = []
        obl_join = ""

        # Entity scope: resolve ministry_id from entity
        entity_ministry = await db.fetchval(
            "SELECT ministry_id FROM entities WHERE code = $1", entity_code
        )
        if entity_ministry:
            obl_where.append(f"lo.ministry_id = ${len(obl_params) + 1}")
            obl_params.append(entity_ministry)

        # Agent scope
        if not agent_ctx.has_global_scope and not agent_ctx.is_supervisor:
            # Regular agent: only own assignments
            obl_join = f"""
                JOIN assignments a ON a.item_id = lo.id
                    AND a.item_type = 'obligation_processing'
                    AND a.agent_profile_id IN (
                        SELECT id FROM agent_profiles WHERE user_id = ${len(obl_params) + 1}::uuid
                    )
                    AND a.status IN ('assigned', 'in_progress', 'completed')
            """
            obl_params.append(agent_ctx.user_id)

        obl_where_sql = "WHERE " + " AND ".join(obl_where) if obl_where else ""

        stats = await db.fetchrow(f"""
            SELECT
                COUNT(*) FILTER (
                    WHERE lo.status IN ('processing', 'pending', 'overdue')
                ) AS pending,
                0 AS assigned,
                COUNT(*) FILTER (
                    WHERE lo.status = 'completed'
                      AND lo.updated_at > NOW() - INTERVAL '24 hours'
                ) AS completed_today,
                0 AS escalated,
                COUNT(*) FILTER (
                    WHERE lo.due_date IS NOT NULL
                      AND lo.due_date < CURRENT_DATE
                      AND lo.status NOT IN ('completed', 'cancelled')
                ) AS sla_violations,
                COALESCE(AVG(
                    EXTRACT(EPOCH FROM (lo.updated_at - lo.created_at)) / 3600
                ) FILTER (
                    WHERE lo.status = 'completed'
                      AND lo.updated_at > NOW() - INTERVAL '30 days'
                ), 0) AS avg_processing_hours
            FROM license_obligations lo
            {obl_join}
            {obl_where_sql}
        """, *obl_params)

        return QueueStatsResponse(
            pending=stats['pending'] or 0,
            assigned=stats['assigned'] or 0,
            completed_today=stats['completed_today'] or 0,
            escalated=stats['escalated'] or 0,
            sla_violations=stats['sla_violations'] or 0,
            avg_processing_hours=round(float(stats['avg_processing_hours'] or 0), 2)
        )

    if is_bundle_entity:
        # ─────────────────────────────────────────────────────────────────
        # Bundle collection entity path: count sp rows
        # ─────────────────────────────────────────────────────────────────
        sp_where = ["sp.entity_code = $1"]
        sp_params: list = [entity_code]
        agent_user_id_param = None

        # Non-supervisor agent: restrict to own assigned payments only
        if not agent_ctx.has_global_scope and not agent_ctx.is_supervisor:
            sp_where.append(
                "sp.assigned_agent_id IN ("
                "SELECT id FROM agent_profiles WHERE user_id = $2::uuid"
                ")"
            )
            sp_params.append(agent_ctx.user_id)
            agent_user_id_param = 2
        elif not agent_ctx.has_global_scope and agent_ctx.entity_location_id:
            # Entity-scoped supervisor: restrict to payments of agents at
            # their own site (already bounded by sp.entity_code = $1).
            sp_where.append(
                f"sp.assigned_agent_id IN ("
                f"SELECT id FROM agent_profiles "
                f"WHERE entity_location_id = ${len(sp_params) + 1}::uuid)"
            )
            sp_params.append(agent_ctx.entity_location_id)

        sp_where_sql = " AND ".join(sp_where)

        stats = await db.fetchrow(f"""
            SELECT
                COUNT(*) FILTER (
                    WHERE sp.workflow_status = 'pending_agent_review'
                ) AS pending,
                COUNT(*) FILTER (
                    WHERE sp.workflow_status = 'agent_reviewing'
                ) AS assigned,
                COUNT(*) FILTER (
                    WHERE sp.workflow_status = 'completed'
                      AND sp.validated_at > NOW() - INTERVAL '24 hours'
                ) AS completed_today,
                COUNT(*) FILTER (
                    WHERE sp.sla_escalated = true
                      AND sp.workflow_status NOT IN ('completed', 'cancelled_by_agent',
                          'cancelled_by_user', 'expired')
                ) AS escalated,
                COUNT(*) FILTER (
                    WHERE sp.sla_target_date IS NOT NULL
                      AND sp.sla_target_date < NOW()
                      AND sp.workflow_status NOT IN ('completed', 'cancelled_by_agent',
                          'cancelled_by_user', 'expired')
                ) AS sla_violations,
                COALESCE(AVG(
                    EXTRACT(EPOCH FROM (sp.validated_at - sp.created_at)) / 3600
                ) FILTER (
                    WHERE sp.workflow_status = 'completed'
                      AND sp.validated_at IS NOT NULL
                      AND sp.validated_at > NOW() - INTERVAL '30 days'
                ), 0) AS avg_processing_hours
            FROM service_payments sp
            WHERE {sp_where_sql}
        """, *sp_params)

        return QueueStatsResponse(
            pending=stats['pending'] or 0,
            assigned=stats['assigned'] or 0,
            completed_today=stats['completed_today'] or 0,
            escalated=stats['escalated'] or 0,
            sla_violations=stats['sla_violations'] or 0,
            avg_processing_hours=round(float(stats['avg_processing_hours'] or 0), 2)
        )

    # ─────────────────────────────────────────────────────────────────────
    # Legacy path: workflow-based entity (CNEDOGE, DGT, ITV, etc.)
    # Unchanged — preserves behaviour for non-bundle flows per project rule.
    # ─────────────────────────────────────────────────────────────────────
    conditions = ["sr.status::text NOT IN ('DRAFT', 'CANCELLED')"]
    params: list = []
    param_idx = 1

    if entity_workflows:
        conditions.append(f"sr.workflow_code = ANY(${param_idx})")
        params.append(entity_workflows)
        param_idx += 1

    # Site scope: only global-scope supervisors see all sites
    if not agent_ctx.has_global_scope and agent_ctx.entity_location_id:
        conditions.append(
            f"(sr.entity_location_id = ${param_idx} OR sr.entity_location_id IS NULL)"
        )
        params.append(agent_ctx.entity_location_id)
        param_idx += 1

    # Add agent user_id as parameter for assigned count
    agent_user_id_param = param_idx
    params.append(agent_ctx.user_id)
    param_idx += 1

    where = " AND ".join(conditions)

    stats = await db.fetchrow(f"""
        SELECT
            COUNT(*) FILTER (
                WHERE sr.status::text IN ('SUBMITTED', 'UNDER_REVIEW')
                  AND sr.assigned_to = ${agent_user_id_param}
                  AND sr.payment_status = 'completed'
            ) AS pending,
            COUNT(*) FILTER (
                WHERE sr.status::text IN ('SUBMITTED', 'UNDER_REVIEW')
                  AND sr.assigned_to = ${agent_user_id_param}
            ) AS assigned,
            COUNT(*) FILTER (
                WHERE sr.status::text IN ('COMPLETED', 'DOSSIER_VALIDE')
                  AND sr.updated_at > NOW() - INTERVAL '24 hours'
            ) AS completed_today,
            COUNT(*) FILTER (
                WHERE sr.escalated = true
                  AND sr.status::text NOT IN ('COMPLETED', 'REJECTED', 'CANCELLED', 'EXPIRED')
            ) AS escalated,
            COUNT(*) FILTER (
                WHERE sr.submitted_at IS NOT NULL
                  AND sr.status::text IN ('SUBMITTED', 'UNDER_REVIEW')
                  AND sr.submitted_at + (COALESCE(w.sla_hours, 72) * INTERVAL '1 hour') < NOW()
            ) AS sla_violations,
            COALESCE(AVG(
                EXTRACT(EPOCH FROM (sr.updated_at - sr.submitted_at)) / 3600
            ) FILTER (
                WHERE sr.status::text IN ('COMPLETED', 'DOSSIER_VALIDE')
                  AND sr.submitted_at IS NOT NULL
                  AND sr.updated_at > NOW() - INTERVAL '30 days'
            ), 0) AS avg_processing_hours
        FROM service_requests sr
        LEFT JOIN workflows w ON w.code = sr.workflow_code
        WHERE {where}
    """, *params)

    return QueueStatsResponse(
        pending=stats['pending'] or 0,
        assigned=stats['assigned'] or 0,
        completed_today=stats['completed_today'] or 0,
        escalated=stats['escalated'] or 0,
        sla_violations=stats['sla_violations'] or 0,
        avg_processing_hours=round(float(stats['avg_processing_hours'] or 0), 2)
    )


@router.get(
    "/my-queue",
    response_model=List[QueueItemResponse],
    summary="Get my assigned items",
    description="""
    Get all queue items currently assigned to the authenticated agent.

    **Pagination:**
    - Use `page` and `page_size` for paginated results
    - Default returns all assigned items (no limit)
    """
)
async def get_my_queue(
    include_completed: bool = Query(False, description="Include completed items"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(100, ge=1, le=200, description="Items per page (max 200)"),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("service_request.process"))
):
    # Calculate offset for pagination
    offset = (page - 1) * page_size

    items = await agent_queue_service.get_agent_queue(
        db=db,
        agent_id=str(current_user.id),
        include_completed=include_completed,
        limit=page_size,
        offset=offset
    )

    result = []
    for item in items:
        sla_status = "on_track"
        if item.get('sla_deadline'):
            from datetime import datetime, timezone
            deadline = item['sla_deadline']
            now = datetime.now(timezone.utc)
            if deadline < now:
                sla_status = "violated"
            elif (deadline - now).total_seconds() < get_settings().QUEUE_SLA_WARNING_HOURS * 3600:
                sla_status = "at_risk"

        result.append(QueueItemResponse(
            queue_id=str(item['id']),
            item_type=item['item_type'],
            item_id=item['item_id'],
            workflow_code=item.get('workflow_code', item.get('declaration_type', '')),
            reference_number=item.get('reference_number', ''),
            citizen_name=item.get('citizen_name', 'Unknown'),
            priority_score=float(item.get('priority_score', 0)),
            sla_deadline=item['sla_deadline'].isoformat() if item.get('sla_deadline') else None,
            sla_status=sla_status,
            status=item['status'],
            assigned_to=item.get('assigned_to'),
            created_at=item['created_at'].isoformat()
        ))

    return result


# ═══════════════════════════════════════════════════════════════
# ITEM MANAGEMENT
# ═══════════════════════════════════════════════════════════════

@router.post(
    "/queue/{queue_id}/release",
    summary="Release queue item for reassignment",
    description="""
    Release an assigned queue item back to the pending queue.

    This will trigger auto-assignment to find a new agent.
    Use this when you cannot complete the assigned task.
    """
)
async def release_item(
    queue_id: str = Path(..., description="Queue item ID"),
    reason: Optional[str] = Body(None, embed=True),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("service_request.process"))
):
    # Get queue item info before releasing
    queue_item = await db.fetchrow(
        "SELECT item_id FROM agent_work_queue WHERE id = $1 AND assigned_to = $2",
        queue_id, str(current_user.id)
    )

    if not queue_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Queue item not found or not assigned to you"
        )

    # Release the queue item
    await db.execute("""
        UPDATE agent_work_queue
        SET assigned_to = NULL,
            status = 'pending',
            updated_at = NOW()
        WHERE id = $1
        AND assigned_to = $2
    """, queue_id, str(current_user.id))

    # Also update service_request
    await db.execute("""
        UPDATE service_requests
        SET assigned_to = NULL,
            assigned_at = NULL,
            status = 'SUBMITTED',
            submitted_at = COALESCE(submitted_at, NOW()),
            updated_at = NOW()
        WHERE id = $1
    """, queue_item['item_id'])

    # Cancel the assignment record
    await db.execute("""
        UPDATE assignments
        SET status = 'cancelled',
            notes = COALESCE(notes, '') || ' [Released by agent: ' || COALESCE($2, 'no reason') || ']',
            updated_at = NOW()
        WHERE item_id = $1
        AND status IN ('assigned', 'in_progress')
    """, queue_item['item_id'], reason)

    # Re-enqueue for auto-assignment so released items don't stall
    try:
        # Get workflow_code and entity_code from the service request
        sr_info = await db.fetchrow(
            "SELECT workflow_code, entity_code FROM service_requests WHERE id = $1",
            queue_item['item_id']
        )
        if sr_info and sr_info['workflow_code'] and sr_info['entity_code']:
            from app.modules.service_requests.services.assignment_outbox_service import AssignmentOutboxService
            outbox = AssignmentOutboxService()
            await outbox.enqueue(
                db=db,
                service_request_id=queue_item['item_id'],
                workflow_code=sr_info['workflow_code'],
                entity_code=sr_info['entity_code'],
            )
            logger.info(f"Released item {queue_item['item_id']} re-enqueued for auto-assignment")
        elif sr_info:
            logger.warning(
                f"Cannot re-enqueue item {queue_item['item_id']}: "
                f"missing workflow_code={sr_info['workflow_code']} or entity_code={sr_info['entity_code']}"
            )
    except Exception as e:
        logger.warning(f"Failed to re-enqueue released item for auto-assignment: {e}")

    return {"message": "Item released back to queue for reassignment"}


# ═══════════════════════════════════════════════════════════════
# HISTORY ENDPOINTS (MUST BE BEFORE /{request_id} FOR ROUTE MATCHING)
# ═══════════════════════════════════════════════════════════════


class HistoryStatisticsResponse(BaseModel):
    """Response model for history statistics."""
    period_days: int = Field(..., description="Number of days covered")
    action_distribution: List[Dict[str, Any]] = Field(
        default_factory=list, description="Count by action type"
    )
    avg_time_by_status: List[Dict[str, Any]] = Field(
        default_factory=list, description="Average time spent in each status (hours)"
    )
    daily_activity: List[Dict[str, Any]] = Field(
        default_factory=list, description="Actions per day"
    )
    total_actions: int = Field(0, description="Total history entries")
    total_requests: int = Field(0, description="Total requests with history")
    busiest_day: Optional[str] = Field(None, description="Day with most activity")
    most_common_action: Optional[str] = Field(None, description="Most frequent action type")


@router.get(
    "/history",
    response_model=HistoryListSummaryResponse,
    summary="List service requests with history",
    description="Returns paginated list of service requests with history summary"
)
async def list_requests_with_history(
    entity_code: str = Query(..., description="Entity code (e.g., CNEDOGE_PASAPORTE)"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db=Depends(get_database),
    _=Depends(permission_required("service_request.view"))
):
    """
    Get list of service requests with history summary for the history list page.
    IMPORTANT: This route MUST be defined before /{request_id} to avoid route conflicts.

    ACCESS CONTROL:
    - Supervisor (has service_request.view_all): sees all requests in the entity
    - Agent: sees only requests assigned to them
    """
    conn = db

    # Get user ID (correct way - current_user is UserResponse, not dict)
    user_id = UUID(str(current_user.id))

    # Check if user has supervisor permission (view_all)
    has_view_all = await conn.fetchval("""
        SELECT EXISTS (
            SELECT 1 FROM user_permissions up
            JOIN permissions p ON p.id = up.permission_id
            WHERE up.user_id = $1 AND p.name = 'service_request.view_all' AND up.granted = true
            UNION
            SELECT 1 FROM users u
            JOIN role_permissions rp ON rp.role_id = u.role_id
            JOIN permissions p ON p.id = rp.permission_id
            WHERE u.id = $1 AND p.name = 'service_request.view_all' AND rp.granted = true
        )
    """, user_id) or False

    logger.info(f"[History] User {current_user.email} (supervisor={has_view_all})")

    # Get entity's workflow codes
    entity = await conn.fetchrow("""
        SELECT workflow_codes FROM entities WHERE code = $1 AND is_active = true
    """, entity_code)

    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entity {entity_code} not found"
        )

    workflow_codes = entity['workflow_codes']
    if isinstance(workflow_codes, str):
        import json as json_module
        workflow_codes = json_module.loads(workflow_codes)
    workflow_codes = [str(wf) for wf in workflow_codes] if workflow_codes else []

    if not workflow_codes:
        return HistoryListSummaryResponse(
            items=[],
            total=0,
            page=page,
            page_size=page_size,
            workflow_codes=workflow_codes,
            status_filter=status_filter
        )

    # Get history list with access control
    offset = (page - 1) * page_size
    items, total = await service_request_repository.get_history_list_for_entity(
        db=conn,
        workflow_codes=workflow_codes,
        status_filter=status_filter,
        limit=page_size,
        offset=offset,
        assigned_to_user_id=None if has_view_all else user_id
    )

    # Transform to response model
    summary_items = [
        HistorySummaryItem(
            request_id=item["request_id"],
            reference=item["reference"],
            workflow_code=item["workflow_code"],
            citizen_name=item["citizen_name"],
            current_status=item["current_status"],
            last_action=item["last_action"],
            last_action_at=item["last_action_at"],
            last_performer=item["last_performer"],
            total_actions=item["total_actions"],
            days_since_created=item["days_since_created"],
            is_stale=item["is_stale"]
        )
        for item in items
    ]

    return HistoryListSummaryResponse(
        items=summary_items,
        total=total,
        page=page,
        page_size=page_size,
        workflow_codes=workflow_codes,
        status_filter=status_filter
    )


@router.get(
    "/history/statistics",
    response_model=HistoryStatisticsResponse,
    summary="Get history statistics",
    description="Get aggregated statistics for history entries"
)
async def get_history_statistics(
    entity_code: str = Query(..., description="Entity code (e.g., CNEDOGE_PASAPORTE)"),
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    workflow_codes: Optional[List[str]] = Query(None, description="Filter by workflow codes"),
    current_user: User = Depends(get_current_user),
    db=Depends(get_database),
    _=Depends(permission_required("service_request.view"))
):
    """
    Get aggregated statistics for service request history.
    IMPORTANT: This route MUST be defined before /{request_id} to avoid route conflicts.
    """
    conn = db

    # Build workflow filter
    workflow_filter = ""
    if workflow_codes:
        workflow_list = ", ".join(f"'{w}'" for w in workflow_codes)
        workflow_filter = f"AND sr.workflow_code IN ({workflow_list})"

    # Action distribution query
    action_dist_query = f"""
        SELECT h.action, COUNT(*) as count
        FROM service_request_history h
        JOIN service_requests sr ON sr.id = h.request_id
        WHERE h.performed_at >= NOW() - INTERVAL '{days} days'
        {workflow_filter}
        GROUP BY h.action
        ORDER BY count DESC
    """

    # Average time by status (status transitions)
    time_by_status_query = f"""
        WITH status_durations AS (
            SELECT
                h.request_id,
                h.new_status as status,
                h.performed_at,
                LEAD(h.performed_at) OVER (
                    PARTITION BY h.request_id ORDER BY h.performed_at
                ) as next_action_at
            FROM service_request_history h
            JOIN service_requests sr ON sr.id = h.request_id
            WHERE h.action = 'status_change'
              AND h.performed_at >= NOW() - INTERVAL '{days} days'
            {workflow_filter}
        )
        SELECT
            status,
            ROUND(AVG(EXTRACT(EPOCH FROM (next_action_at - performed_at)) / 3600)::numeric, 2) as avg_hours,
            COUNT(*) as transitions
        FROM status_durations
        WHERE next_action_at IS NOT NULL
        GROUP BY status
        ORDER BY avg_hours DESC
    """

    # Daily activity query
    daily_activity_query = f"""
        SELECT
            DATE(h.performed_at) as activity_date,
            COUNT(*) as action_count,
            COUNT(DISTINCT h.request_id) as request_count
        FROM service_request_history h
        JOIN service_requests sr ON sr.id = h.request_id
        WHERE h.performed_at >= NOW() - INTERVAL '{days} days'
        {workflow_filter}
        GROUP BY DATE(h.performed_at)
        ORDER BY activity_date DESC
        LIMIT 30
    """

    # Total counts query
    totals_query = f"""
        SELECT
            COUNT(*) as total_actions,
            COUNT(DISTINCT h.request_id) as total_requests
        FROM service_request_history h
        JOIN service_requests sr ON sr.id = h.request_id
        WHERE h.performed_at >= NOW() - INTERVAL '{days} days'
        {workflow_filter}
    """

    # Execute queries
    action_rows = await conn.fetch(action_dist_query)
    time_rows = await conn.fetch(time_by_status_query)
    daily_rows = await conn.fetch(daily_activity_query)
    totals_row = await conn.fetchrow(totals_query)

    # Process results
    action_distribution = [
        {"action": row["action"], "count": row["count"]}
        for row in action_rows
    ]

    avg_time_by_status = [
        {"status": row["status"], "avg_hours": float(row["avg_hours"] or 0), "transitions": row["transitions"]}
        for row in time_rows
    ]

    daily_activity = [
        {"date": str(row["activity_date"]), "actions": row["action_count"], "requests": row["request_count"]}
        for row in daily_rows
    ]

    # Find busiest day
    busiest_day = None
    if daily_rows:
        max_day = max(daily_rows, key=lambda x: x["action_count"])
        busiest_day = str(max_day["activity_date"])

    # Find most common action
    most_common_action = action_distribution[0]["action"] if action_distribution else None

    return HistoryStatisticsResponse(
        period_days=days,
        action_distribution=action_distribution,
        avg_time_by_status=avg_time_by_status,
        daily_activity=daily_activity,
        total_actions=totals_row["total_actions"] if totals_row else 0,
        total_requests=totals_row["total_requests"] if totals_row else 0,
        busiest_day=busiest_day,
        most_common_action=most_common_action
    )


# ═══════════════════════════════════════════════════════════════
# MY ESCALATIONS (MUST BE BEFORE /{request_id} FOR ROUTE MATCHING)
# ═══════════════════════════════════════════════════════════════

class EscalationHistoryEntry(BaseModel):
    """Single history entry for escalation timeline"""
    action: str
    performed_at: str
    performed_by_name: Optional[str] = None
    comment: Optional[str] = None


class EscalationItemResponse(BaseModel):
    """Escalation item response for agent view"""
    id: str
    queue_id: str  # Kept for backward compat (set to request id)
    reason: str
    priority_score: float
    status: str  # service_request status
    escalation_status: str  # pending, in_review, resolved
    case_reference: str
    case_type: str
    notes: Optional[str] = None
    created_at: str
    escalated_at: str
    direction: str = "sent"  # "sent" = agent escalated, "received" = supervisor assigned
    escalated_by_name: Optional[str] = None
    citizen_name: Optional[str] = None
    history: List[EscalationHistoryEntry] = []


class PaginatedEscalationResponse(BaseModel):
    """Paginated escalation response"""
    items: List[EscalationItemResponse]
    total: int
    page: int
    page_size: int


@router.get(
    "/my-escalations",
    response_model=PaginatedEscalationResponse,
    summary="Get agent escalations (sent + received)",
    description="""
    Returns two types of escalations for the current agent:
    - **sent**: Requests the agent escalated to supervisor
    - **received**: Escalated requests the supervisor assigned to this agent

    Use `direction` filter to separate them in the UI.
    """
)
async def get_my_escalations(
    include_resolved: bool = Query(False, description="Include resolved escalations"),
    direction: Optional[str] = Query(None, description="Filter: sent | received | null (both)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("service_request.escalate"))
):
    offset = (page - 1) * page_size
    resolved_statuses = ["COMPLETED", "REJECTED", "CANCELLED", "EXPIRED"]

    # Build direction filter
    if direction == "sent":
        direction_filter = "AND sr.escalated_by = $1"
    elif direction == "received":
        direction_filter = "AND sr.assigned_to = $1 AND sr.escalated_by != $1"
    else:
        # Both: sent OR received
        direction_filter = "AND (sr.escalated_by = $1 OR (sr.assigned_to = $1 AND sr.escalated_by != $1))"

    status_filter = "AND sr.status::text != ALL($4::text[])" if not include_resolved else ""

    # Count total matching rows
    count_params: list = [current_user.id]
    if not include_resolved:
        count_params.append(resolved_statuses)
    count_status_filter = f"AND sr.status::text != ALL(${len(count_params)}::text[])" if not include_resolved else ""

    total_row = await db.fetchrow(f"""
        SELECT COUNT(*) as total
        FROM service_requests sr
        WHERE sr.escalated = true
        {direction_filter}
        {count_status_filter}
    """, *count_params)
    total = total_row['total'] if total_row else 0

    params: list = [current_user.id, page_size, offset]
    if not include_resolved:
        params.append(resolved_statuses)

    rows = await db.fetch(f"""
        SELECT
            sr.id,
            sr.reference,
            sr.workflow_code,
            sr.status::text as status,
            sr.escalation_reason,
            sr.escalated_at,
            sr.escalated_by,
            sr.assigned_to,
            sr.created_at,
            sr.notes,
            sr.priority::text as priority,
            CASE
                WHEN sr.status::text IN ('COMPLETED', 'REJECTED', 'CANCELLED', 'EXPIRED') THEN 'resolved'
                WHEN sr.assigned_to IS NOT NULL AND sr.escalated_by != sr.assigned_to THEN 'in_review'
                ELSE 'pending'
            END as escalation_status,
            CASE
                WHEN sr.escalated_by = $1 THEN 'sent'
                ELSE 'received'
            END as direction,
            escalator.full_name as escalated_by_name,
            citizen.full_name as citizen_name
        FROM service_requests sr
        LEFT JOIN users escalator ON escalator.id = sr.escalated_by
        LEFT JOIN users citizen ON citizen.id = sr.user_id
        WHERE sr.escalated = true
        {direction_filter}
        {status_filter}
        ORDER BY sr.escalated_at DESC NULLS LAST
        LIMIT $2 OFFSET $3
    """, *params)

    # Batch-fetch escalation history for all returned requests (single query)
    request_ids = [row['id'] for row in rows]
    history_map: Dict[str, List[EscalationHistoryEntry]] = {str(rid): [] for rid in request_ids}

    if request_ids:
        history_rows = await db.fetch("""
            SELECT
                h.service_request_id,
                h.action,
                h.performed_at,
                h.comment,
                COALESCE(u.full_name, u.first_name || ' ' || u.last_name) as performed_by_name
            FROM service_request_history h
            LEFT JOIN users u ON u.id = h.performed_by
            WHERE h.service_request_id = ANY($1)
            AND h.action IN ('escalated', 'escalation_assigned', 'escalation_resolved',
                             'supervisor_approve', 'supervisor_reject')
            ORDER BY h.performed_at ASC
        """, request_ids)

        for hr in history_rows:
            rid = str(hr['service_request_id'])
            if rid in history_map:
                history_map[rid].append(EscalationHistoryEntry(
                    action=hr['action'],
                    performed_at=hr['performed_at'].isoformat(),
                    performed_by_name=hr['performed_by_name'],
                    comment=hr['comment'] if hr['comment'] not in ('escalation_assigned', 'escalation_resolved', 'supervisor_approve', 'supervisor_reject') else None,
                ))

    items = [
        EscalationItemResponse(
            id=str(row['id']),
            queue_id=str(row['id']),
            reason=row['escalation_reason'] or '',
            priority_score=0.0,
            status=row['status'],
            escalation_status=row['escalation_status'],
            case_reference=row['reference'] or '',
            case_type=row['workflow_code'] or '',
            notes=row['notes'],
            created_at=row['created_at'].isoformat(),
            escalated_at=row['escalated_at'].isoformat() if row['escalated_at'] else row['created_at'].isoformat(),
            direction=row['direction'],
            escalated_by_name=row['escalated_by_name'],
            citizen_name=row['citizen_name'],
            history=history_map.get(str(row['id']), []),
        )
        for row in rows
    ]

    return PaginatedEscalationResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


# ═══════════════════════════════════════════════════════════════
# SERVICE REQUEST PROCESSING
# ═══════════════════════════════════════════════════════════════

@router.get(
    "/{request_id}",
    summary="Get service request details (agent view)",
    description="""
    Get complete details of a service request for agent review.

    Includes all documents, extraction data, form data, payment info,
    user contact details, and verification status.
    """
)
async def get_request_for_review(
    request_id: UUID = Path(..., description="Service request ID"),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("service_request.view"))
):
    # Single query: service_request + user contact + latest payment (3 JOINs, 1 round-trip)
    row = await db.fetchrow("""
        SELECT sr.*,
               u.full_name AS user_name, u.email AS user_email, u.phone_number AS user_phone,
               sp.total_amount AS pay_amount, sp.currency AS pay_currency,
               sp.payment_method AS pay_method, sp.workflow_status AS pay_workflow_status,
               sp.payment_reference AS pay_reference, sp.receipt_number AS pay_receipt,
               sp.paid_at AS pay_paid_at
        FROM service_requests sr
        JOIN users u ON u.id = sr.user_id
        LEFT JOIN LATERAL (
            SELECT total_amount, currency, payment_method, workflow_status,
                   payment_reference, receipt_number, paid_at
            FROM service_payments
            WHERE service_request_id = sr.id
            ORDER BY created_at DESC LIMIT 1
        ) sp ON true
        WHERE sr.id = $1
    """, request_id)

    if not row:
        raise TranslatedException(ErrorCode.REQUEST_NOT_FOUND)

    # Get base response from service (loads documents + tariff)
    base_response = await service_request_service.get_request(
        db=db,
        request_id=request_id,
        user_id=row['user_id'],
        is_agent=True
    )

    # Augment response with agent-specific fields
    response = base_response.model_dump(mode='json')
    response['user_name'] = row['user_name']
    response['user_email'] = row['user_email']
    response['user_phone'] = row['user_phone']
    response['verification_status'] = row.get('verification_status')
    raw_vd = row.get('verification_details')
    if raw_vd and isinstance(raw_vd, str):
        raw_vd = json.loads(raw_vd)
    response['verification_details'] = raw_vd

    if row['pay_amount'] is not None:
        response['payment_amount'] = float(row['pay_amount'])
        response['payment_currency'] = row['pay_currency']
        response['payment_method'] = row['pay_method']
        response['payment_workflow_status'] = row['pay_workflow_status']
        response['payment_reference'] = row['pay_reference']
        response['payment_receipt_number'] = row['pay_receipt']
        response['payment_paid_at'] = row['pay_paid_at'].isoformat() if row['pay_paid_at'] else None

    return response


@router.post(
    "/{request_id}/decision",
    summary="Make decision on service request",
    description="""
    Approve, reject, or request additional documents for a service request.

    **Approve:** Validates the dossier and proceeds to next workflow step.
    **Reject:** Rejects the request with a reason.
    **Request Documents:** Asks citizen for additional/corrected documents.
    """
)
async def make_decision(
    request_id: UUID = Path(..., description="Service request ID"),
    decision: AgentDecision = Body(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("service_request.process"))
):
    # ── PRE-FLIGHT: CTE fetches queue + request + idempotency check in 1 query ──
    preflight = await db.fetchrow("""
        WITH queue AS (
            SELECT id AS queue_id
            FROM agent_work_queue
            WHERE item_id = $1
              AND item_type = 'service_request'
              AND assigned_to = $2
              AND status = 'assigned'
        ),
        req AS (
            SELECT id, reference, status, workflow_code, user_id, form_data,
                   escalated, batch_id, entity_code, cita_date
            FROM service_requests
            WHERE id = $3
        ),
        already_decided AS (
            SELECT 1 AS decided
            FROM service_request_history
            WHERE service_request_id = $3
              AND action = 'status_change'
              AND new_status IN ('DOSSIER_VALIDE', 'REJECTED')
            LIMIT 1
        )
        SELECT
            q.queue_id,
            r.id AS req_id, r.reference, r.status, r.workflow_code,
            r.user_id, r.form_data, r.escalated, r.batch_id,
            r.entity_code, r.cita_date,
            ad.decided
        FROM req r
        LEFT JOIN queue q ON TRUE
        LEFT JOIN already_decided ad ON TRUE
    """, str(request_id), str(current_user.id), request_id)

    if not preflight or not preflight['req_id']:
        raise TranslatedException(ErrorCode.REQUEST_NOT_FOUND)
    if not preflight['queue_id']:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This request is not assigned to you")
    if preflight.get('decided'):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Decision already recorded for this request (idempotency)")
    if preflight.get('escalated'):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cannot process escalated request. Awaiting supervisor decision.")

    allowed_statuses = ('SUBMITTED', 'UNDER_REVIEW')
    if preflight['status'] not in allowed_statuses:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot make decision on request with status '{preflight['status']}'. Allowed: {', '.join(allowed_statuses)}"
        )

    # Store preflight results for use in branches
    queue_id = str(preflight['queue_id'])
    request_ref = preflight['reference']
    workflow_code = preflight['workflow_code']
    user_id = preflight['user_id']
    previous_status = preflight['status']
    batch_id = preflight.get('batch_id')
    entity_code = preflight.get('entity_code')
    existing_cita = preflight.get('cita_date')
    form_data_raw = preflight.get('form_data') or {}

    # ══════════════════════════════════════════════════════════════
    # APPROVE
    # ══════════════════════════════════════════════════════════════
    if decision.decision == "approve":
        # ── Pre-transaction: fetch workflow config + determine target status ──
        workflow_data = await db.fetchrow(
            "SELECT requires_appointment, name_es FROM workflows WHERE code = $1",
            workflow_code
        )
        wf_needs_cita = bool(workflow_data and workflow_data.get('requires_appointment'))

        # Check payment status
        has_payment = await db.fetchval("""
            SELECT EXISTS(SELECT 1 FROM service_payments
                          WHERE service_request_id = $1
                            AND workflow_status IN ('completed', 'approved_by_agent'))
        """, request_id)

        # Determine target status:
        # - COMPLETED: payment done + (cita booked OR no cita required)
        # - DOSSIER_VALIDE: edge case — cita required but not yet booked
        if has_payment and (existing_cita or not wf_needs_cita):
            new_status = "COMPLETED"
        elif has_payment and wf_needs_cita and not existing_cita:
            new_status = "DOSSIER_VALIDE"
        else:
            # Payment not done (shouldn't happen per business rules, but defensive)
            new_status = "DOSSIER_VALIDE"

        # ── ATOMIC TRANSACTION with FOR UPDATE (prevents race condition) ──
        async with db.transaction():
            locked = await db.fetchval("""
                SELECT id FROM service_requests
                WHERE id = $1 AND status::text = ANY($2::text[])
                FOR UPDATE
            """, request_id, list(allowed_statuses))

            if not locked:
                raise TranslatedException(ErrorCode.STATUS_CHANGED)

            await db.execute("""
                UPDATE service_requests
                SET status = $1, validated_at = NOW(), updated_at = NOW()
                WHERE id = $2
            """, new_status, request_id)

            await db.execute("""
                INSERT INTO service_request_history
                (service_request_id, action, previous_status, new_status, performed_by, comment)
                VALUES ($1, 'status_change', $2, $3, $4, $5)
            """, request_id, previous_status, new_status, current_user.id, decision.comments)

            await agent_queue_service.complete_item(
                db=db, queue_id=queue_id,
                agent_id=str(current_user.id), result_status="approved"
            )

        logger.info(f"Approved {request_ref}: {previous_status} -> {new_status}")

        # ── Post-transaction: fetch appointment info for PDF/notification ──
        appointment_info = None
        if existing_cita:
            cita_row = await db.fetchrow(
                "SELECT cita_date, cita_time, cita_location FROM service_requests WHERE id = $1",
                request_id
            )
            if cita_row and cita_row['cita_date']:
                appointment_info = {
                    "date": cita_row['cita_date'].isoformat(),
                    "time": cita_row['cita_time'].isoformat() if cita_row.get('cita_time') else "",
                    "location": cita_row.get('cita_location') or ""
                }
        elif wf_needs_cita:
            try:
                reservation = await appointment_scheduler.reserve_appointment(
                    db=db, service_request_id=request_id,
                    workflow_code=workflow_code, validation_date=date.today()
                )
                appointment_info = {
                    "date": reservation.appointment_date.isoformat(),
                    "time": reservation.appointment_time.isoformat(),
                    "location": reservation.appointment_location
                }
                # Cita was auto-reserved — advance to COMPLETED if was DOSSIER_VALIDE
                if new_status == "DOSSIER_VALIDE":
                    await db.execute("""
                        UPDATE service_requests SET status = 'COMPLETED', updated_at = NOW()
                        WHERE id = $1 AND status::text = 'DOSSIER_VALIDE'
                    """, request_id)
                    await db.execute("""
                        INSERT INTO service_request_history
                        (service_request_id, action, previous_status, new_status, performed_by, comment)
                        VALUES ($1, 'status_change', 'DOSSIER_VALIDE', 'COMPLETED', $2,
                                'Auto-advance: appointment auto-reserved, process complete')
                    """, request_id, current_user.id)
                    new_status = "COMPLETED"
                    logger.info(f"Auto-advanced {request_ref} to COMPLETED after cita auto-reservation")
            except Exception as e:
                logger.warning(f"Post-approval appointment scheduling failed for {request_id}: {e}")

        # ── BACKGROUND TASK: PDF generation + notification (frees DB connection) ──
        agent_name = f"{current_user.first_name} {current_user.last_name}"
        agent_id_str = str(current_user.id)
        background_tasks.add_task(
            _bg_approve_pdf_and_notify,
            request_id=request_id,
            request_ref=request_ref,
            workflow_code=workflow_code,
            workflow_name=workflow_data.get('name_es') or workflow_code if workflow_data else workflow_code,
            user_id=user_id,
            form_data_raw=form_data_raw,
            appointment_info=appointment_info,
            agent_name=agent_name,
            agent_id_str=agent_id_str,
            batch_id=batch_id,
            requires_appointment=bool(workflow_data and workflow_data.get('requires_appointment')),
        )

        return {
            "message": "Service request approved",
            "new_status": new_status,
            "appointment": appointment_info
        }

    # ══════════════════════════════════════════════════════════════
    # REJECT
    # ══════════════════════════════════════════════════════════════
    elif decision.decision == "reject":
        if not decision.rejection_reason:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Rejection reason is required"
            )

        history_comment = decision.rejection_reason
        if decision.comments:
            history_comment = f"{decision.rejection_reason}\n---\n{decision.comments}"

        # ── ATOMIC TRANSACTION with FOR UPDATE ──
        async with db.transaction():
            locked = await db.fetchval("""
                SELECT id FROM service_requests
                WHERE id = $1 AND status::text = ANY($2::text[])
                FOR UPDATE
            """, request_id, list(allowed_statuses))

            if not locked:
                raise TranslatedException(ErrorCode.STATUS_CHANGED)

            await db.execute("""
                UPDATE service_requests
                SET status = 'REJECTED', rejection_reason = $2,
                    validated_at = NOW(), updated_at = NOW()
                WHERE id = $1
            """, request_id, decision.rejection_reason)

            await db.execute("""
                INSERT INTO service_request_history
                (service_request_id, action, previous_status, new_status, performed_by, comment)
                VALUES ($1, 'status_change', $2, 'REJECTED', $3, $4)
            """, request_id, previous_status, current_user.id, history_comment)

            await agent_queue_service.complete_item(
                db=db, queue_id=queue_id,
                agent_id=str(current_user.id), result_status="rejected"
            )

        # ── BACKGROUND: notification + batch check ──
        agent_id_str = str(current_user.id)
        background_tasks.add_task(
            _bg_reject_notify,
            request_id=request_id,
            request_ref=request_ref,
            workflow_code=workflow_code,
            user_id=user_id,
            agent_id_str=agent_id_str,
            rejection_reason=decision.rejection_reason,
            batch_id=batch_id,
        )

        return {
            "message": "Service request rejected",
            "new_status": "REJECTED",
            "reason": decision.rejection_reason
        }

    # ══════════════════════════════════════════════════════════════
    # REQUEST DOCUMENTS
    # ══════════════════════════════════════════════════════════════
    elif decision.decision == "request_documents":
        if not decision.requested_documents and not decision.comments:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either requested documents or a comment must be provided"
            )

        # Resolve document codes to names (pre-transaction, read-only)
        history_details = {}
        doc_names = []
        if decision.requested_documents:
            history_details["requested_documents"] = decision.requested_documents
            name_rows = await db.fetch("""
                SELECT template_code, document_name_es FROM document_templates
                WHERE template_code = ANY($1::text[])
            """, decision.requested_documents)
            name_map = {r['template_code']: r['document_name_es'] for r in name_rows}
            doc_names = [name_map.get(c, c) for c in decision.requested_documents]

        history_comment = decision.comments
        if not history_comment and doc_names:
            history_comment = f"Se requiere volver a enviar: {', '.join(doc_names)}"

        # ── ATOMIC TRANSACTION with FOR UPDATE ──
        async with db.transaction():
            locked = await db.fetchval("""
                SELECT id FROM service_requests
                WHERE id = $1 AND status::text = ANY($2::text[])
                FOR UPDATE
            """, request_id, list(allowed_statuses))

            if not locked:
                raise TranslatedException(ErrorCode.STATUS_CHANGED)

            await db.execute("""
                UPDATE service_requests
                SET status = 'DOCUMENTS_REQUIRED', updated_at = NOW()
                WHERE id = $1
            """, request_id)

            await db.execute("""
                INSERT INTO service_request_history
                (service_request_id, action, previous_status, new_status, performed_by, comment, details)
                VALUES ($1, 'documents_required', $2, 'DOCUMENTS_REQUIRED', $3, $4, $5::jsonb)
            """, request_id, previous_status, current_user.id, history_comment,
                json.dumps(history_details))

            # Keep assigned_to so the SAME agent gets the dossier back
            # when the citizen re-submits documents (continuity + SLA preserved)
            await db.execute("""
                UPDATE agent_work_queue
                SET status = 'waiting_documents', updated_at = NOW()
                WHERE id = $1
            """, queue_id)

        # ── BACKGROUND: notification ──
        background_tasks.add_task(
            _bg_request_docs_notify,
            request_id=request_id,
            request_ref=request_ref,
            workflow_code=workflow_code,
            user_id=user_id,
            agent_id_str=str(current_user.id),
            history_comment=history_comment,
            requested_documents=decision.requested_documents,
        )

        return {
            "message": "Additional documents requested",
            "new_status": "DOCUMENTS_REQUIRED",
            "requested_documents": decision.requested_documents
        }


# ═══════════════════════════════════════════════════════════════
# BACKGROUND TASKS for make_decision (PDF + notifications)
# Runs AFTER HTTP response, using its own DB connection from pool.
# ═══════════════════════════════════════════════════════════════

async def _bg_approve_pdf_and_notify(
    *,
    request_id: UUID,
    request_ref: str,
    workflow_code: str,
    workflow_name: str,
    user_id: UUID,
    form_data_raw: Any,
    appointment_info: Optional[Dict],
    agent_name: str,
    agent_id_str: str,
    batch_id: Optional[UUID],
    requires_appointment: bool = False,
):
    """Background: generate validation PDF, send notification, check batch."""
    pool = await get_db_pool()
    async with pool.acquire() as db:
        try:
            # ── Parallel fetch: user + documents + payment + agent entity ──
            form_data = form_data_raw if isinstance(form_data_raw, dict) else {}
            if isinstance(form_data_raw, str):
                try:
                    form_data = json.loads(form_data_raw)
                except (json.JSONDecodeError, TypeError):
                    form_data = {}

            # Sequential queries — asyncpg forbids concurrent ops on a single connection
            user_info = await db.fetchrow(
                "SELECT id, email, first_name, last_name, phone_number, preferred_language FROM users WHERE id = $1",
                user_id
            )
            docs_rows = await db.fetch("""
                SELECT COALESCE(dt.document_name_es, srd.document_name, srd.document_code) as doc_name,
                       srd.is_valid
                FROM service_request_documents srd
                LEFT JOIN document_templates dt ON dt.template_code = srd.document_code
                WHERE srd.service_request_id = $1
            """, request_id)
            tariff_row = await db.fetchrow("""
                SELECT total_amount, workflow_status, payment_method
                FROM service_payments
                WHERE service_request_id = $1
                ORDER BY created_at DESC LIMIT 1
            """, request_id)
            agent_entity_row = await db.fetchrow("""
                SELECT el.location_name FROM entity_locations el
                JOIN agent_profiles ap ON ap.entity_location_id = el.id
                WHERE ap.user_id = $1 AND ap.is_active = true
                LIMIT 1
            """, UUID(agent_id_str))

            if not user_info:
                logger.warning(f"[bg_approve] User {user_id} not found for SR {request_id}")
                return

            language = user_info['preferred_language'] or 'es'
            agent_entity = agent_entity_row['location_name'] if agent_entity_row else 'DGI'

            # ── Build dynamic data sections from workflow ──
            data_sections = []
            photo_url = None
            solicitud_type = form_data.get('tipo_solicitud', 'expedicion')
            try:
                workflow_obj = workflow_engine.get_workflow_by_string(workflow_code)
                if workflow_obj and hasattr(workflow_obj, 'get_pdf_data_sections'):
                    from ..workflows.workflow_interface import WorkflowContext, WorkflowCode as WfCode
                    from ..models.enums import SolicitudType as SolType
                    # Resolve solicitud_type from form_data or default
                    sol_type_str = form_data.get('solicitud_type', 'expedicion')
                    try:
                        sol_type = SolType(sol_type_str)
                    except ValueError:
                        sol_type = SolType.EXPEDICION
                    ctx = WorkflowContext(
                        service_request_id=request_id,
                        user_id=user_id,
                        workflow_code=WfCode(workflow_code),
                        solicitud_type=sol_type,
                        form_data=form_data,
                    )
                    data_sections = workflow_obj.get_pdf_data_sections(ctx)
            except Exception as e:
                logger.warning(f"[bg_approve] Failed to build data_sections for {request_id}: {e}")

            # ── Fetch citizen photo from uploaded documents (photo_carnet) ──
            photo_url = None
            try:
                photo_codes = ("photo_carnet", "fotografias", "foto_carnet")
                photo_doc = await db.fetchrow("""
                    SELECT file_path FROM service_request_documents
                    WHERE service_request_id = $1 AND document_code = ANY($2::text[])
                    AND file_path IS NOT NULL
                    LIMIT 1
                """, request_id, list(photo_codes))
                if photo_doc and photo_doc['file_path']:
                    from app.modules.documents.services.firebase_storage_service import firebase_storage_service
                    photo_url = await firebase_storage_service.get_signed_url(
                        photo_doc['file_path'], expires_in=600
                    )
            except Exception as e:
                logger.warning(f"[bg_approve] Failed to fetch photo for {request_id}: {e}")

            # ── Prepare documents list ──
            documents = []
            for doc in docs_rows:
                is_verified = doc.get('is_valid', False) is True
                documents.append({
                    "name": doc['doc_name'] or 'Document',
                    "validation_status": "verified" if is_verified else "pending",
                })

            # ── Prepare tariff ──
            tariff = {
                "base_amount": float(tariff_row['total_amount']) if tariff_row and tariff_row['total_amount'] else 0,
                "additional_fees": [],
                "total_amount": float(tariff_row['total_amount']) if tariff_row and tariff_row['total_amount'] else 0,
            }
            payment_status = tariff_row['workflow_status'] if tariff_row else None

            # ── Appointment for PDF ──
            appointment_pdf = None
            if appointment_info:
                appointment_pdf = {
                    "date": appointment_info['date'],
                    "time": appointment_info['time'],
                    "location": appointment_info.get('location') or '',
                }

            # ── Generate validation certificate PDF (v2: dynamic sections + official design) ──
            pdf_attachment = None
            try:
                pdf_service = SummaryPDFService()
                pdf_bytes = await pdf_service.generate_validation_certificate_v2(
                    request_number=request_ref,
                    workflow_name=workflow_name,
                    solicitud_type=solicitud_type,
                    data_sections=data_sections,
                    documents=documents,
                    tariff=tariff,
                    appointment=appointment_pdf,
                    agent_name=agent_name,
                    agent_entity=agent_entity,
                    photo_url=photo_url,
                    payment_status=payment_status,
                    language=language,
                )
                pdf_filename = f"certificat_validation_{request_ref}.pdf"
                pdf_attachment = [(pdf_filename, pdf_bytes, "application/pdf")]
                logger.info(f"[bg_approve] Generated PDF: {pdf_filename} ({len(pdf_bytes)} bytes)")
            except Exception as e:
                logger.warning(f"[bg_approve] PDF generation failed for {request_id}: {e}")

            # ── Build next_steps message for citizen notification ──
            sr_state = await db.fetchrow(
                "SELECT status::text, cita_date, cita_time, cita_location FROM service_requests WHERE id = $1",
                request_id
            )
            current_sr_status = sr_state['status'] if sr_state else "COMPLETED"

            next_steps_es = ""
            next_steps_fr = ""
            if current_sr_status == "COMPLETED" and sr_state and sr_state.get('cita_date'):
                # Completed with appointment — tell citizen when/where to go
                cita_str = sr_state['cita_date'].strftime("%d/%m/%Y")
                hora_str = sr_state['cita_time'].strftime("%H:%M") if sr_state.get('cita_time') else ""
                loc = sr_state.get('cita_location') or (appointment_info.get('location', '') if appointment_info else '')
                next_steps_es = (
                    f"<strong>Proximos pasos:</strong> Presentese el {cita_str}"
                    f"{' a las ' + hora_str if hora_str else ''}"
                    f"{' en ' + loc if loc else ''} con los documentos originales."
                )
                next_steps_fr = (
                    f"<strong>Prochaines etapes:</strong> Presentez-vous le {cita_str}"
                    f"{' a ' + hora_str if hora_str else ''}"
                    f"{' a ' + loc if loc else ''} avec les documents originaux."
                )
            elif current_sr_status == "COMPLETED":
                # Completed without appointment — no further action needed
                next_steps_es = "<strong>Proximos pasos:</strong> Su tramite ha sido completado exitosamente."
                next_steps_fr = "<strong>Prochaines etapes:</strong> Votre demarche a ete completee avec succes."
            elif current_sr_status == "DOSSIER_VALIDE":
                # Edge case: waiting for citizen to book cita
                next_steps_es = "<strong>Proximos pasos:</strong> Su dossier esta validado. Por favor programe su cita."
                next_steps_fr = "<strong>Prochaines etapes:</strong> Votre dossier est valide. Veuillez programmer votre rendez-vous."

            next_steps = next_steps_fr if language == 'fr' else next_steps_es

            # ── Publish event ──
            event_payload = {
                "request_id": str(request_id),
                "reference": request_ref,
                "user_id": str(user_info['id']),
                "user_email": user_info['email'],
                "user_name": f"{user_info['first_name']} {user_info['last_name']}",
                "user_phone": user_info['phone_number'],
                "preferred_language": language,
                "workflow_code": workflow_code,
                "workflow_name": workflow_name,
                "agent_id": agent_id_str,
                "next_steps": next_steps,
                "appointment_date": appointment_info['date'] if appointment_info else None,
                "appointment_time": appointment_info['time'] if appointment_info else None,
                "location": appointment_info.get('location') if appointment_info else None,
                "timestamp": datetime.now().isoformat(),
            }
            if pdf_attachment:
                event_payload["attachments"] = pdf_attachment
            EventBus.publish_nowait(EventType.REQUEST_APPROVED, event_payload)

            # ── Batch auto-completion ──
            if batch_id:
                try:
                    completed = await batch_repository.check_and_complete_batch(db, batch_id)
                    if completed:
                        logger.info(f"[bg_approve] Batch auto-completed after approval of SR {request_id}")
                        await _publish_batch_completed_event(db, batch_id)
                except Exception as e:
                    logger.error(f"[bg_approve] Batch check failed for SR {request_id}: {e}")

        except Exception as e:
            logger.error(f"[bg_approve] Background task failed for SR {request_id}: {e}", exc_info=True)


async def _bg_reject_notify(
    *,
    request_id: UUID,
    request_ref: str,
    workflow_code: str,
    user_id: UUID,
    agent_id_str: str,
    rejection_reason: str,
    batch_id: Optional[UUID],
):
    """Background: send rejection notification, check batch."""
    pool = await get_db_pool()
    async with pool.acquire() as db:
        try:
            user_info = await db.fetchrow(
                "SELECT id, email, first_name, last_name, phone_number, preferred_language FROM users WHERE id = $1",
                user_id
            )
            if user_info:
                EventBus.publish_nowait(
                    EventType.REQUEST_REJECTED,
                    {
                        "request_id": str(request_id),
                        "reference": request_ref,
                        "user_id": str(user_info['id']),
                        "user_email": user_info['email'],
                        "user_name": f"{user_info['first_name']} {user_info['last_name']}",
                        "user_phone": user_info['phone_number'],
                        "preferred_language": user_info['preferred_language'] or 'es',
                        "workflow_code": workflow_code,
                        "agent_id": agent_id_str,
                        "reason": rejection_reason,
                        "rejection_reason": rejection_reason,
                        "timestamp": datetime.now().isoformat(),
                    }
                )
            if batch_id:
                completed = await batch_repository.check_and_complete_batch(db, batch_id)
                if completed:
                    logger.info(f"[bg_reject] Batch auto-completed after rejection of SR {request_id}")
                    await _publish_batch_completed_event(db, batch_id)
        except Exception as e:
            logger.error(f"[bg_reject] Background task failed for SR {request_id}: {e}", exc_info=True)


async def _bg_request_docs_notify(
    *,
    request_id: UUID,
    request_ref: str,
    workflow_code: str,
    user_id: UUID,
    agent_id_str: str,
    history_comment: Optional[str],
    requested_documents: Optional[list],
):
    """Background: send document request notification."""
    pool = await get_db_pool()
    async with pool.acquire() as db:
        try:
            user_info = await db.fetchrow(
                "SELECT id, email, first_name, last_name, phone_number, preferred_language FROM users WHERE id = $1",
                user_id
            )
            if user_info:
                event_payload = {
                    "request_id": str(request_id),
                    "reference": request_ref,
                    "user_id": str(user_info['id']),
                    "user_email": user_info['email'],
                    "user_name": f"{user_info['first_name']} {user_info['last_name']}",
                    "user_phone": user_info['phone_number'],
                    "preferred_language": user_info['preferred_language'] or 'es',
                    "workflow_code": workflow_code,
                    "agent_id": agent_id_str,
                    "comments": history_comment,
                    "timestamp": datetime.now().isoformat(),
                }
                if requested_documents:
                    event_payload["requested_documents"] = requested_documents
                EventBus.publish_nowait(EventType.REQUEST_DOCUMENTS_REQUIRED, event_payload)
        except Exception as e:
            logger.error(f"[bg_request_docs] Background task failed for SR {request_id}: {e}", exc_info=True)


# ═══════════════════════════════════════════════════════════════
# ESCALATION
# ═══════════════════════════════════════════════════════════════

@router.post(
    "/{request_id}/escalate",
    summary="Escalate service request",
    description="""
    Escalate a service request to a supervisor.

    Marks the request as escalated and records the escalation in history.
    """
)
async def escalate_request(
    request_id: UUID = Path(..., description="Service request ID"),
    escalation: EscalationRequest = Body(...),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("service_request.escalate"))
):
    # Verify request exists and belongs to agent's entity
    request = await db.fetchrow("""
        SELECT id, reference, status, entity_code, escalated
        FROM service_requests WHERE id = $1
    """, request_id)

    if not request:
        raise TranslatedException(ErrorCode.REQUEST_NOT_FOUND)

    if request['escalated']:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Service request already escalated"
        )

    # Mark as escalated + unassign agent (supervisor will reassign)
    await db.execute("""
        UPDATE service_requests
        SET escalated = true,
            escalated_at = NOW(),
            escalated_by = $2,
            escalation_reason = $3,
            assigned_to = NULL,
            updated_at = NOW()
        WHERE id = $1
    """, request_id, current_user.id, escalation.reason)

    # Mark queue item as escalated (removes from agent's active queue)
    await db.execute("""
        UPDATE agent_work_queue
        SET status = 'escalated', escalated = true, updated_at = NOW()
        WHERE item_id = $1 AND item_type = 'service_request' AND status = 'assigned'
    """, request_id)

    # Record in history for audit and citizen notifications
    previous_status = request['status']
    await db.execute("""
        INSERT INTO service_request_history
        (service_request_id, action, previous_status, new_status, performed_by, comment, details)
        VALUES ($1, 'escalated', $2, $2, $3, $4, $5::jsonb)
    """, request_id, previous_status, current_user.id, escalation.reason,
        json.dumps({"priority_boost": escalation.priority_boost}))

    # Also update agent_work_queue if a queue item exists (backward compat)
    queue_item = await db.fetchrow("""
        SELECT id FROM agent_work_queue
        WHERE item_id = $1 AND item_type = 'service_request' AND status != 'completed'
    """, request_id)
    if queue_item:
        try:
            await agent_queue_service.escalate_item(
                db=db,
                queue_id=str(queue_item['id']),
                agent_id=str(current_user.id),
                reason=escalation.reason
            )
        except Exception as e:
            logger.warning(f"Failed to enqueue escalated request {escalation.request_id}: {e}")

    return {
        "message": "Service request escalated",
        "reference": request['reference'],
        "reason": escalation.reason
    }


@router.post(
    "/{request_id}/resolve-escalation",
    summary="Resolve escalation on a service request",
    description="""
    Marks the escalated service request as resolved (de-escalates).
    Only supervisors can de-escalate. The agent who escalated cannot self-resolve.
    """,
)
async def resolve_escalation(
    request_id: UUID = Path(..., description="Service request ID"),
    db: asyncpg.Connection = Depends(get_database),
    current_user: User = Depends(get_current_user),
    _=Depends(permission_required("queue.review")),  # Supervisor-only permission
):
    """Resolve (de-escalate) a service request. Supervisor only."""
    request = await db.fetchrow(
        "SELECT id, reference, status, escalated, escalated_by FROM service_requests WHERE id = $1",
        request_id
    )
    if not request:
        raise TranslatedException(ErrorCode.REQUEST_NOT_FOUND)
    if not request['escalated']:
        raise HTTPException(status_code=409, detail="Service request is not escalated")
    # Prevent the escalating agent from self-resolving
    if request['escalated_by'] == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot resolve your own escalation. Only a supervisor can de-escalate."
        )

    await db.execute("""
        UPDATE service_requests
        SET escalated = false,
            escalated_at = NULL,
            escalated_by = NULL,
            escalation_reason = NULL,
            escalation_sla_warning_sent = false,
            escalation_sla_escalated = false,
            updated_at = NOW()
        WHERE id = $1
    """, request_id)

    # Record in history
    await db.execute("""
        INSERT INTO service_request_history
        (service_request_id, action, previous_status, new_status, performed_by, comment)
        VALUES ($1, 'escalation_resolved', $2, $2, $3, 'escalation_resolved')
    """, request_id, request['status'], current_user.id)

    return {
        "message": "Escalation resolved",
        "reference": request['reference'],
    }


# ═══════════════════════════════════════════════════════════════
# APPOINTMENT MANAGEMENT
# ═══════════════════════════════════════════════════════════════

@router.post(
    "/{request_id}/appointment",
    summary="Schedule appointment manually",
    description="""
    Manually schedule an appointment for a service request.

    Use this when automatic scheduling is not appropriate
    or when rescheduling is needed.
    """
)
async def schedule_appointment(
    request_id: UUID = Path(..., description="Service request ID"),
    schedule: AppointmentSchedule = Body(...),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("service_request.schedule_appointment"))
):
    # Check if appointment exists
    existing = await db.fetchrow("""
        SELECT id FROM appointment_reservations
        WHERE service_request_id = $1
        AND status != 'cancelled'
    """, request_id)

    if existing:
        # Reschedule
        reservation = await appointment_scheduler.reschedule_appointment(
            db=db,
            service_request_id=request_id,
            new_date=schedule.appointment_date,
            new_time=schedule.appointment_time,
            reason="Agent manual reschedule"
        )
    else:
        # Get workflow info for entity
        request = await db.fetchrow("""
            SELECT workflow_code FROM service_requests WHERE id = $1
        """, request_id)

        if not request:
            raise TranslatedException(ErrorCode.REQUEST_NOT_FOUND)

        # Reserve new appointment
        reservation = await appointment_scheduler.reserve_appointment(
            db=db,
            service_request_id=request_id,
            workflow_code=request['workflow_code'],
            validation_date=date.today()
        )

        # Update with manual date/time
        await db.execute("""
            UPDATE appointment_reservations
            SET appointment_date = $2,
                appointment_time = $3,
                location = COALESCE($4, location)
            WHERE id = $1
        """, reservation.id, schedule.appointment_date,
            schedule.appointment_time, schedule.location)

        await db.execute("""
            UPDATE service_requests
            SET cita_date = $2,
                cita_time = $3,
                cita_location = COALESCE($4, cita_location),
                updated_at = NOW()
            WHERE id = $1
        """, request_id, schedule.appointment_date,
            schedule.appointment_time, schedule.location)

    return {
        "message": "Appointment scheduled",
        "date": schedule.appointment_date.isoformat(),
        "time": schedule.appointment_time.isoformat(),
        "location": schedule.location
    }


@router.delete(
    "/{request_id}/appointment",
    summary="Cancel appointment",
    description="Cancel an existing appointment for a service request."
)
async def cancel_appointment(
    request_id: UUID = Path(..., description="Service request ID"),
    reason: Optional[str] = Body(None, embed=True),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("service_request.schedule_appointment"))
):
    # Get request info before cancellation (for notification)
    request_info = await db.fetchrow("""
        SELECT sr.user_id, sr.workflow_code,
               ah.appointment_date, ah.appointment_time, ah.location_name
        FROM service_requests sr
        LEFT JOIN appointment_holds ah ON ah.service_request_id = sr.id AND ah.status = 'confirmed'
        WHERE sr.id = $1
    """, request_id)

    cancelled = await appointment_scheduler.cancel_appointment(
        db=db,
        service_request_id=request_id,
        reason=reason or "Agent cancellation"
    )

    if not cancelled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active appointment found"
        )

    # Publish APPOINTMENT_CANCELLED event for notification
    if request_info:
        try:
            user_info = await db.fetchrow(
                "SELECT id, email, first_name, last_name, phone_number, preferred_language FROM users WHERE id = $1",
                request_info['user_id']
            )
            if user_info:
                EventBus.publish_nowait(
                    EventType.APPOINTMENT_CANCELLED,
                    {
                        "request_id": str(request_id),
                        "user_id": str(user_info['id']),
                        "user_email": user_info['email'],
                        "user_name": f"{user_info['first_name']} {user_info['last_name']}",
                        "user_phone": user_info['phone_number'],
                        "preferred_language": user_info['preferred_language'] or 'es',
                        "workflow_code": request_info['workflow_code'],
                        "appointment_date": str(request_info['appointment_date']) if request_info.get('appointment_date') else None,
                        "appointment_time": str(request_info['appointment_time']) if request_info.get('appointment_time') else None,
                        "location": request_info.get('location_name'),
                        "reason": reason or "Agent cancellation",
                        "timestamp": datetime.now().isoformat(),
                    }
                )
        except Exception as e:
            logger.warning(f"Failed to publish APPOINTMENT_CANCELLED event: {e}")

    return {"message": "Appointment cancelled"}


# ═══════════════════════════════════════════════════════════════
# APPOINTMENT MANAGEMENT
# ═══════════════════════════════════════════════════════════════

@router.get(
    "/appointments/available",
    summary="Get available appointment slots",
    description="Get list of available appointment slots for a given entity."
)
async def get_available_slots(
    entity_code: str = Query(..., description="Entity code (e.g., CNEDOGE)"),
    from_date: Optional[date] = Query(None, description="Start date (defaults to today)"),
    limit: int = Query(30, ge=1, description="Number of slots to return"),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("service_request.view"))
):
    if not from_date:
        from_date = date.today()

    slots = await appointment_scheduler.get_available_slots(
        db=db,
        entity_code=entity_code,
        from_date=from_date,
        limit=limit
    )

    return [
        {
            "date": slot.date.isoformat(),
            "start_time": slot.start_time.isoformat(),
            "end_time": slot.end_time.isoformat(),
            "slots_available": slot.slots_available
        }
        for slot in slots
    ]


# ═══════════════════════════════════════════════════════════════
# DOCUMENT VALIDATION
# ═══════════════════════════════════════════════════════════════

class DocumentValidationRequest(BaseModel):
    """Request body for document validation"""
    comment: Optional[str] = None


class DocumentRejectionRequest(BaseModel):
    """Request body for document rejection"""
    reason: str = Field(..., min_length=5, description="Rejection reason")


class VerificationChecklistUpdate(BaseModel):
    """Request body for updating agent verification checklist"""
    checklist: Dict[str, bool] = Field(
        ...,
        description="Checklist items with their completion status"
    )
    verification_status: Optional[str] = Field(
        None,
        pattern="^(pending|in_progress|verified|partial_verification|verification_failed)$",
        description="Optional verification status update"
    )
    notes: Optional[str] = Field(None, max_length=2000)


@router.post(
    "/documents/{document_id}/validate",
    summary="Validate a document",
    description="Mark a document as validated by agent."
)
async def validate_document(
    document_id: str,
    body: DocumentValidationRequest = None,
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("service_request.review"))
):
    """Validate a document uploaded by a citizen."""
    # Get document with user info from service_request_documents
    doc = await db.fetchrow("""
        SELECT srd.id, srd.uploaded_by as user_id, srd.document_code as document_type,
               srd.file_name, srd.is_valid,
               u.email, u.phone_number as phone, u.first_name, u.last_name, u.preferred_language
        FROM service_request_documents srd
        JOIN users u ON u.id = srd.uploaded_by
        WHERE srd.id = $1::uuid
    """, document_id)

    if not doc:
        raise TranslatedException(ErrorCode.DOCUMENT_NOT_FOUND)

    if doc["is_valid"] is True:
        raise HTTPException(status_code=400, detail="Document already validated")

    # Update document status
    await db.execute("""
        UPDATE service_request_documents
        SET is_valid = true,
            validated_at = NOW(),
            validated_by = $2::uuid,
            updated_at = NOW()
        WHERE id = $1::uuid
    """, document_id, str(current_user.id))

    # Publish DOCUMENT_VALIDATED event
    try:
        EventBus.publish_nowait(
            EventType.DOCUMENT_VALIDATED,
            {
                "document_id": document_id,
                "user_id": str(doc["user_id"]) if doc["user_id"] else None,
                "user_email": doc["email"],
                "user_phone": doc["phone"],
                "user_name": f"{doc['first_name'] or ''} {doc['last_name'] or ''}".strip(),
                "preferred_language": doc.get("preferred_language", "es"),
                "document_type": doc["document_type"],
                "file_name": doc["file_name"],
                "agent_id": str(current_user.id),
            }
        )
        logger.info(f"DOCUMENT_VALIDATED event published for document {document_id}")
    except Exception as e:
        logger.error(f"Failed to publish DOCUMENT_VALIDATED event: {e}")

    return {"message": "Document validated", "document_id": document_id}


@router.post(
    "/documents/{document_id}/reject",
    summary="Reject a document",
    description="Mark a document as rejected with reason."
)
async def reject_document(
    document_id: str,
    body: DocumentRejectionRequest,
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("service_request.review"))
):
    """Reject a document uploaded by a citizen."""
    # Get document with user info from service_request_documents
    doc = await db.fetchrow("""
        SELECT srd.id, srd.uploaded_by as user_id, srd.document_code as document_type,
               srd.file_name, srd.is_valid,
               u.email, u.phone_number as phone, u.first_name, u.last_name, u.preferred_language
        FROM service_request_documents srd
        JOIN users u ON u.id = srd.uploaded_by
        WHERE srd.id = $1::uuid
    """, document_id)

    if not doc:
        raise TranslatedException(ErrorCode.DOCUMENT_NOT_FOUND)

    if doc["is_valid"] is False and doc.get("validation_errors") is not None:
        raise HTTPException(status_code=400, detail="Document already rejected")

    # Update document status
    await db.execute("""
        UPDATE service_request_documents
        SET is_valid = false,
            validation_errors = jsonb_build_array(jsonb_build_object('reason', $2::text, 'agent', $3::text)),
            validated_at = NOW(),
            validated_by = $3::uuid,
            updated_at = NOW()
        WHERE id = $1::uuid
    """, document_id, body.reason, str(current_user.id))

    # Publish DOCUMENT_REJECTED event
    try:
        EventBus.publish_nowait(
            EventType.DOCUMENT_REJECTED,
            {
                "document_id": document_id,
                "user_id": str(doc["user_id"]),
                "user_email": doc["email"],
                "user_phone": doc["phone"],
                "user_name": f"{doc['first_name'] or ''} {doc['last_name'] or ''}".strip(),
                "preferred_language": doc.get("preferred_language", "es"),
                "document_type": doc["document_type"],
                "file_name": doc["file_name"],
                "reason": body.reason,
                "agent_id": str(current_user.id),
            }
        )
        logger.info(f"DOCUMENT_REJECTED event published for document {document_id}")
    except Exception as e:
        logger.error(f"Failed to publish DOCUMENT_REJECTED event: {e}")

    return {"message": "Document rejected", "document_id": document_id, "reason": body.reason}


# ═══════════════════════════════════════════════════════════════
# APPOINTMENT ATTENDANCE TRACKING
# ═══════════════════════════════════════════════════════════════

@router.post(
    "/appointments/{request_id}/mark-arrived",
    summary="Mark citizen as arrived",
    description="Agent marks that the citizen has arrived for their appointment."
)
async def mark_appointment_arrived(
    request_id: str,
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("service_request.review"))
):
    """Mark that citizen arrived for appointment."""
    # Get request with user and appointment info
    request = await db.fetchrow("""
        SELECT sr.id, sr.user_id, sr.status, sr.workflow_code, sr.reference,
               sr.cita_date as appointment_date, sr.cita_time as appointment_time,
               sr.cita_location as location,
               u.email, u.phone_number as phone, u.first_name, u.last_name, u.preferred_language
        FROM service_requests sr
        JOIN users u ON u.id = sr.user_id
        WHERE sr.id = $1::uuid
    """, request_id)

    if not request:
        raise TranslatedException(ErrorCode.REQUEST_NOT_FOUND)

    # Update appointment status
    await db.execute("""
        UPDATE service_requests
        SET appointment_status = 'arrived',
            arrived_at = NOW(),
            updated_at = NOW()
        WHERE id = $1::uuid
    """, request_id)

    # Update appointment_holds if exists
    await db.execute("""
        UPDATE appointment_holds
        SET status = 'completed', completed_at = NOW()
        WHERE service_request_id = $1::uuid AND status = 'confirmed'
    """, request_id)

    # Publish APPOINTMENT_COMPLETED event
    try:
        EventBus.publish_nowait(
            EventType.APPOINTMENT_COMPLETED,
            {
                "request_id": request_id,
                "user_id": str(request["user_id"]),
                "user_email": request["email"],
                "user_phone": request["phone"],
                "user_name": f"{request['first_name'] or ''} {request['last_name'] or ''}".strip(),
                "preferred_language": request.get("preferred_language", "es"),
                "workflow_code": request["workflow_code"],
                "reference": request["reference"],
                "appointment_date": str(request["appointment_date"]) if request.get("appointment_date") else None,
                "appointment_time": str(request["appointment_time"]) if request.get("appointment_time") else None,
                "location": request.get("location"),
                "agent_id": str(current_user.id),
            }
        )
        logger.info(f"APPOINTMENT_COMPLETED event published for request {request_id}")
    except Exception as e:
        logger.error(f"Failed to publish APPOINTMENT_COMPLETED event: {e}")

    return {"message": "Citizen marked as arrived", "request_id": request_id}


@router.post(
    "/appointments/{request_id}/mark-no-show",
    summary="Mark citizen as no-show",
    description="Agent marks that the citizen did not arrive for their appointment."
)
async def mark_appointment_no_show(
    request_id: str,
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("service_request.review"))
):
    """Mark that citizen did not arrive for appointment (no-show)."""
    # Get request with user and appointment info
    request = await db.fetchrow("""
        SELECT sr.id, sr.user_id, sr.status, sr.workflow_code, sr.reference,
               sr.cita_date as appointment_date, sr.cita_time as appointment_time,
               sr.cita_location as location,
               u.email, u.phone_number as phone, u.first_name, u.last_name, u.preferred_language
        FROM service_requests sr
        JOIN users u ON u.id = sr.user_id
        WHERE sr.id = $1::uuid
    """, request_id)

    if not request:
        raise TranslatedException(ErrorCode.REQUEST_NOT_FOUND)

    # Update appointment status
    await db.execute("""
        UPDATE service_requests
        SET appointment_status = 'no_show',
            no_show_at = NOW(),
            updated_at = NOW()
        WHERE id = $1::uuid
    """, request_id)

    # Update appointment_holds if exists
    await db.execute("""
        UPDATE appointment_holds
        SET status = 'no_show', completed_at = NOW()
        WHERE service_request_id = $1::uuid AND status = 'confirmed'
    """, request_id)

    # Publish APPOINTMENT_NO_SHOW event
    try:
        EventBus.publish_nowait(
            EventType.APPOINTMENT_NO_SHOW,
            {
                "request_id": request_id,
                "user_id": str(request["user_id"]),
                "user_email": request["email"],
                "user_phone": request["phone"],
                "user_name": f"{request['first_name'] or ''} {request['last_name'] or ''}".strip(),
                "preferred_language": request.get("preferred_language", "es"),
                "workflow_code": request["workflow_code"],
                "reference": request["reference"],
                "appointment_date": str(request["appointment_date"]) if request.get("appointment_date") else None,
                "appointment_time": str(request["appointment_time"]) if request.get("appointment_time") else None,
                "location": request.get("location"),
                "agent_id": str(current_user.id),
            }
        )
        logger.info(f"APPOINTMENT_NO_SHOW event published for request {request_id}")
    except Exception as e:
        logger.error(f"Failed to publish APPOINTMENT_NO_SHOW event: {e}")

    return {"message": "Citizen marked as no-show", "request_id": request_id}


# ═══════════════════════════════════════════════════════════════
# ENTITY SERVICE REQUESTS (Dashboard Views)
# ═══════════════════════════════════════════════════════════════

class ServiceRequestListItem(BaseModel):
    """Service request item for agent list view"""
    id: str
    reference: str
    workflow_code: str
    solicitud_type: str
    motivo: Optional[str] = None
    status: str
    priority: str
    citizen_name: str
    citizen_email: Optional[str] = None
    submitted_at: Optional[str] = None
    created_at: str
    assigned_to: Optional[str] = None
    sla_deadline: Optional[str] = None
    sla_status: str = "on_track"
    # Batch context (if created from batch submission)
    batch_id: Optional[str] = None
    batch_reference: Optional[str] = None
    # Assigned agent name (for supervisor team view)
    assigned_agent_name: Optional[str] = None
    # Escalation context
    escalation_reason: Optional[str] = None
    escalated_at: Optional[str] = None
    # True when request was returned from escalation by supervisor
    supervisor_assigned: bool = False


class ServiceRequestListResponse(BaseModel):
    """Paginated service request list response"""
    items: List[ServiceRequestListItem]
    total: int
    page: int
    page_size: int
    total_pages: int


# ═══════════════════════════════════════════════════════════════
# PREVIEW MODELS FOR SPLIT VIEW
# ═══════════════════════════════════════════════════════════════

# NOTE: RequestPreviewExtractedData (22 hardcoded fields) was removed.
# extracted_data is now a dynamic Dict[str, Any] driven by workflow_display_config.
# See _extract_preview_data_dynamic() below.


class RequestPreviewDocument(BaseModel):
    """Document info for preview (thumbnail)"""
    id: str
    code: str
    name: str
    file_url: Optional[str] = None
    mime_type: Optional[str] = None
    validation_status: str = "pending"


class RequestPreviewAppointment(BaseModel):
    """Appointment info for preview"""
    date: str
    time: str
    location_name: str
    location_address: Optional[str] = None


class PreviewDataField(BaseModel):
    """A single field in a data section"""
    label: str
    value: str


class PreviewDataSection(BaseModel):
    """A titled section of fields (mirrors get_pdf_data_sections output)"""
    title: str
    fields: List[PreviewDataField] = []


class ServiceRequestPreview(BaseModel):
    """Complete preview for split view"""
    # Request data
    id: str
    reference: str
    workflow_code: str
    workflow_label: str
    solicitud_type: str
    motivo: Optional[str] = None
    is_minor: bool = False
    status: str
    priority: str
    # SLA
    sla_deadline: Optional[str] = None
    sla_remaining_hours: Optional[float] = None
    sla_status: str = "on_track"  # on_track, warning, breached
    # Extracted data — structured sections from display_config + OCR extraction_data
    data_sections: List[PreviewDataSection] = Field(
        default_factory=list,
        description="Structured data sections from workflow config (same as citizen résumé)"
    )
    # Documents (max 4 for preview)
    documents: List[RequestPreviewDocument] = []
    documents_count: int = 0
    # Contact
    contact_name: str
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    # Appointment
    appointment: Optional[RequestPreviewAppointment] = None
    # Payment details
    payment_status: Optional[str] = None
    payment_method: Optional[str] = None
    payment_amount: Optional[float] = None
    payment_currency: Optional[str] = None
    payment_paid_at: Optional[str] = None
    payment_reference: Optional[str] = None
    payment_receipt_number: Optional[str] = None
    # Metadata
    created_at: str
    submitted_at: Optional[str] = None
    # Batch context
    batch_id: Optional[str] = None
    batch_reference: Optional[str] = None
    # Navigation
    list_index: Optional[int] = None
    list_total: Optional[int] = None


class ActionStatusMapping:
    """Map dashboard actions to database statuses.
    Approval flow: SUBMITTED → COMPLETED (direct) or DOSSIER_VALIDE (edge: cita needed).
    CITA_SCHEDULED/IN_PROGRESS are legacy statuses — kept in HISTORY for backward compat.
    """
    PENDING = ["SUBMITTED", "UNDER_REVIEW", "DOCUMENTS_REQUIRED"]
    VALIDATION = ["DOSSIER_VALIDE", "PENDING_NOTA_INGRESO", "NOTA_UPLOADED"]
    APPOINTMENTS = []  # No longer used — appointments are tracked via cita_date column
    HISTORY = ["COMPLETED", "CITA_SCHEDULED", "IN_PROGRESS", "REJECTED", "CANCELLED", "EXPIRED"]
    # Escalations uses escalated=true filter, not status-based
    ESCALATIONS = None

    @classmethod
    def get_statuses(cls, action: str) -> Optional[List[str]]:
        mapping = {
            "pending": cls.PENDING,
            "validation": cls.VALIDATION,
            "appointments": cls.APPOINTMENTS,
            "history": cls.HISTORY,
            "escalations": cls.ESCALATIONS,
        }
        return mapping.get(action.lower(), cls.PENDING)

    @classmethod
    def is_escalation(cls, action: str) -> bool:
        return action.lower() == "escalations"


@router.get(
    "/entity/{entity_code}/requests",
    response_model=ServiceRequestListResponse,
    summary="Get service requests for entity",
    description="""
    Get paginated list of service requests for a specific entity.

    **Filters:**
    - `action`: Dashboard action (pending, validation, appointments, history) - filters by status groups
    - `workflow_code`: Filter by specific workflow code
    - `solicitud_type`: Filter by solicitud type (expedicion, renovacion)
    - `motivo`: Filter by motivo for renovacion (vencimiento, perdida, robo, deterioro)
    - `search`: Search in reference number or citizen name
    - `priority`: Filter by priority (LOW, NORMAL, HIGH, URGENT)

    **Pagination:**
    - Default page size is 20
    - Returns total count for pagination UI
    """
)
async def get_entity_service_requests(
    entity_code: str = Path(..., description="Entity code (e.g., CNEDOGE_PASAPORTE)"),
    action: str = Query("pending", description="Dashboard action: pending, validation, appointments, history, escalations"),
    status_filter: Optional[str] = Query(None, alias="status", description="Direct status filter (overrides action). For custom sub-menus."),
    workflow_code: Optional[str] = Query(None, description="Filter by specific workflow code"),
    solicitud_type: Optional[str] = Query(None, description="Filter by type: expedicion, renovacion"),
    motivo: Optional[str] = Query(None, description="Filter by motivo: vencimiento, perdida, robo, deterioro"),
    search: Optional[str] = Query(None, description="Search reference or citizen name"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    agent_id: Optional[str] = Query(None, description="Filter by assigned agent ID (supervisor team view)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: asyncpg.Connection = Depends(get_database),
    agent_ctx: AgentContext = Depends(get_agent_context),
    _=Depends(permission_required("service_request.view"))
):
    """Get service requests for an entity with filters for dashboard views."""
    # Get entity's workflow codes
    entity = await db.fetchrow("""
        SELECT id, code, workflow_codes FROM entities WHERE code = $1 AND is_active = true
    """, entity_code)

    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entity {entity_code} not found"
        )

    # Parse workflow_codes from JSONB and ensure it's a proper list
    entity_workflows = entity['workflow_codes']
    if isinstance(entity_workflows, str):
        entity_workflows = json.loads(entity_workflows)
    if not entity_workflows:
        entity_workflows = []
    # Convert to list of strings for asyncpg array binding
    entity_workflows = [str(wf) for wf in entity_workflows] if entity_workflows else []

    # Build query conditions
    conditions = []
    params = []
    param_idx = 1

    # Direct status filter (for custom sub-items like "Completados")
    if status_filter:
        conditions.append(f"sr.status = ${param_idx}::service_request_status_enum")
        params.append(status_filter)
        param_idx += 1
    # Escalations use escalated=true filter instead of status-based
    elif ActionStatusMapping.is_escalation(action):
        conditions.append("sr.escalated = true")
    else:
        statuses = ActionStatusMapping.get_statuses(action)
        conditions.append(f"sr.status = ANY(${param_idx}::service_request_status_enum[])")
        params.append(statuses)
        param_idx += 1
        # Exclude escalated requests from non-escalation views (pending, validation, etc.)
        conditions.append("sr.escalated = false")

    # Filter by entity's workflow codes (unless specific workflow requested)
    if workflow_code:
        conditions.append(f"sr.workflow_code = ${param_idx}")
        params.append(workflow_code)
        param_idx += 1
    elif entity_workflows:
        # asyncpg converts Python list to PostgreSQL array automatically
        conditions.append(f"sr.workflow_code = ANY(${param_idx})")
        params.append(entity_workflows)
        param_idx += 1

    # Filter by solicitud_type
    if solicitud_type:
        conditions.append(f"sr.solicitud_type = ${param_idx}")
        params.append(solicitud_type.lower())
        param_idx += 1

    # Filter by motivo (stored in form_data)
    if motivo:
        conditions.append(f"sr.form_data->>'motivo' ILIKE ${param_idx}")
        params.append(motivo.upper())
        param_idx += 1

    # Search filter
    if search:
        conditions.append(f"""(
            sr.reference ILIKE ${param_idx}
            OR u.first_name ILIKE ${param_idx}
            OR u.last_name ILIKE ${param_idx}
            OR u.email ILIKE ${param_idx}
        )""")
        params.append(f"%{search}%")
        param_idx += 1

    # Priority filter (native enum comparison — index-friendly)
    if priority:
        conditions.append(f"sr.priority = ${param_idx}::service_request_priority_enum")
        params.append(priority.upper())
        param_idx += 1

    # Scope: 3-tier visibility
    # - Regular agent: only their own assigned requests
    # - Site supervisor (is_main_office=false): all requests at their site
    # - Global supervisor (is_main_office=true): all requests
    if not agent_ctx.is_supervisor:
        # Regular agent: only their assigned requests
        conditions.append(f"sr.assigned_to = ${param_idx}")
        params.append(agent_ctx.user_id)
        param_idx += 1
    elif not agent_ctx.has_global_scope and agent_ctx.entity_location_id:
        # Site supervisor: all requests at their site
        conditions.append(
            f"(sr.entity_location_id = ${param_idx} OR sr.entity_location_id IS NULL)"
        )
        params.append(agent_ctx.entity_location_id)
        param_idx += 1
        if agent_id:
            # Optional sub-filter by specific agent within site
            conditions.append(f"sr.assigned_to = ${param_idx}::uuid")
            params.append(agent_id)
            param_idx += 1
    elif agent_id:
        # Global supervisor: optional filter by specific assigned agent
        conditions.append(f"sr.assigned_to = ${param_idx}::uuid")
        params.append(agent_id)
        param_idx += 1

    where_clause = " AND ".join(conditions)

    # Calculate pagination
    offset = (page - 1) * page_size
    params.append(page_size)
    params.append(offset)

    # Always select escalation columns so UI can show escalation indicator in any view
    escalation_select = ",\n            sr.escalation_reason,\n            sr.escalated_at as escalated_at_ts"
    escalation_order = ""
    if ActionStatusMapping.is_escalation(action):
        escalation_order = "sr.escalated_at DESC NULLS LAST,"

    # Optimized single query: COUNT(*) OVER() avoids double scan,
    # LEFT JOINs replace correlated subqueries, native enum casts for index usage
    query = f"""
        SELECT
            sr.id,
            sr.reference,
            sr.workflow_code,
            sr.solicitud_type,
            sr.form_data->>'motivo' as motivo,
            sr.status,
            sr.priority,
            sr.created_at,
            sr.submitted_at,
            sr.assigned_to,
            CASE
                WHEN sr.submitted_at IS NOT NULL AND w.sla_hours IS NOT NULL
                THEN sr.submitted_at + (w.sla_hours * interval '1 hour')
                ELSE sr.expires_at
            END as sla_deadline,
            u.first_name,
            u.last_name,
            u.email,
            sr.batch_id,
            br.reference AS batch_reference,
            COALESCE(assigned_u.full_name, assigned_u.first_name || ' ' || assigned_u.last_name) as assigned_agent_name,
            (esc_hist.request_id IS NOT NULL AND sr.escalated = false) as supervisor_assigned,
            COUNT(*) OVER() as _total_count
            {escalation_select}
        FROM service_requests sr
        JOIN users u ON u.id = sr.user_id
        LEFT JOIN workflows w ON w.code = sr.workflow_code
        LEFT JOIN users assigned_u ON assigned_u.id = sr.assigned_to
        LEFT JOIN batch_requests br ON br.id = sr.batch_id
        LEFT JOIN LATERAL (
            SELECT srh.service_request_id as request_id
            FROM service_request_history srh
            WHERE srh.service_request_id = sr.id
              AND srh.action IN ('escalation_assigned', 'escalation_resolved')
            LIMIT 1
        ) esc_hist ON true
        WHERE {where_clause}
        ORDER BY
            {escalation_order}
            CASE sr.priority
                WHEN 'URGENT' THEN 1
                WHEN 'HIGH' THEN 2
                WHEN 'NORMAL' THEN 3
                WHEN 'LOW' THEN 4
                ELSE 5
            END,
            sr.submitted_at DESC NULLS LAST,
            sr.created_at DESC
        LIMIT ${param_idx} OFFSET ${param_idx + 1}
    """

    rows = await db.fetch(query, *params)

    # Extract total from window function (avoids separate COUNT query)
    total = rows[0]['_total_count'] if rows else 0
    total_pages = (total + page_size - 1) // page_size if total > 0 else 1

    # Transform to response
    items = []
    now = datetime.now(timezone.utc)
    for row in rows:
        sla_status = "on_track"
        if row['sla_deadline']:
            deadline = row['sla_deadline']
            if hasattr(deadline, 'replace'):
                deadline = deadline
            if deadline < now:
                sla_status = "violated"
            elif (deadline - now).total_seconds() < get_settings().QUEUE_SLA_WARNING_HOURS * 3600:
                sla_status = "at_risk"

        citizen_name = f"{row['first_name'] or ''} {row['last_name'] or ''}".strip() or "N/A"

        item = ServiceRequestListItem(
            id=str(row['id']),
            reference=row['reference'] or '',
            workflow_code=row['workflow_code'],
            solicitud_type=row['solicitud_type'] or '',
            motivo=row['motivo'],
            status=row['status'],
            priority=row['priority'] or 'NORMAL',
            citizen_name=citizen_name,
            citizen_email=row['email'],
            submitted_at=row['submitted_at'].isoformat() if row['submitted_at'] else None,
            created_at=row['created_at'].isoformat(),
            assigned_to=str(row['assigned_to']) if row['assigned_to'] else None,
            assigned_agent_name=row.get('assigned_agent_name'),
            sla_deadline=row['sla_deadline'].isoformat() if row['sla_deadline'] else None,
            sla_status=sla_status,
            batch_id=str(row['batch_id']) if row.get('batch_id') else None,
            batch_reference=row.get('batch_reference'),
        )
        # Add escalation fields when available
        if 'escalation_reason' in row.keys():
            item.escalation_reason = row['escalation_reason']
            item.escalated_at = row['escalated_at_ts'].isoformat() if row.get('escalated_at_ts') else None
        if row.get('supervisor_assigned'):
            item.supervisor_assigned = True
        items.append(item)

    return ServiceRequestListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


# ═══════════════════════════════════════════════════════════════
# REQUEST PREVIEW FOR SPLIT VIEW
# ═══════════════════════════════════════════════════════════════

def _flatten_form_data(form_data: dict) -> dict:
    """
    Flatten nested objects in form_data with dot notation prefix.
    e.g., {"dip": {"natural_de": "Malabo"}} → {"dip.natural_de": "Malabo"}

    Skips technical fields (sub_type, is_minor, solicitud_type, motivo).
    Skips arrays and deeply nested objects.
    """
    TECHNICAL_FIELDS = {'sub_type', 'is_minor', 'solicitud_type', 'motivo'}
    flat: Dict[str, Any] = {}

    for key, value in form_data.items():
        if key in TECHNICAL_FIELDS:
            continue
        if isinstance(value, dict):
            for sub_key, sub_value in value.items():
                if not isinstance(sub_value, (dict, list)):
                    flat[f"{key}.{sub_key}"] = sub_value
        elif isinstance(value, list):
            continue
        else:
            flat[key] = value

    return flat


# ═══════════════════════════════════════════════════════════════
# DISPLAY CONFIG → SPLIT-VIEW DATA SECTIONS
# ═══════════════════════════════════════════════════════════════

# System columns shown elsewhere in the preview (header, payment, etc.)
_SYSTEM_COLUMNS = {
    'reference', 'fullName', 'solicitudType', 'createdAt',
    'paymentStatus', 'totalAmount', 'assignedAgent',
}

# Human-readable section titles for document code prefixes
_SECTION_TITLES: Dict[str, str] = {
    'dip': 'Documento de Identidad (DIP)',
    'pasaporte': 'Pasaporte',
    'pasaporte_antiguo': 'Pasaporte Anterior',
    'certificado_nacimiento': 'Certificado de Nacimiento',
    'autorizacion_parental': 'Autorización Parental',
    'documento_representante_1': 'Documento Representante Legal',
    'documento_representante_2': 'Documento Segundo Representante',
    'permiso_residencia': 'Permiso de Residencia',
    'residencia_anterior': 'Residencia Anterior',
    'certificado_medico': 'Certificado Médico',
    'certificado_actual': 'Permiso de Conducir Actual',
    'contrato': 'Datos del Contrato',
    'certificado_nif': 'Certificado NIF',
    'identidad_representante': 'Identidad del Representante',
    'escritura_constitucion': 'Escritura de Constitución',
    'certificado_registro_vue': 'Certificado Registro VUE',
    'licencia_comercio': 'Licencia de Comercio',
    'autorizacion_gubernativa': 'Autorización Gubernativa',
    'sello_entrada': 'Sello de Entrada',
    'visado_entrada': 'Visado de Entrada',
    'permiso_trabajo': 'Permiso de Trabajo',
    'certificado_conducta': 'Certificado de Conducta',
    'antecedentes_penales': 'Antecedentes Penales',
    'atestacion_bancaria': 'Atestación Bancaria',
    'nif_autorizacion': 'NIF / Autorización',
    'solvencia_tributaria': 'Solvencia Tributaria',
    'certificado_reconocimiento': 'Certificado Reconocimiento Vehículo',
    'ficha_tecnica': 'Ficha Técnica',
    'seguro_vehiculo': 'Seguro del Vehículo',
    'titulo_propiedad': 'Título de Propiedad',
    'certificado_itv': 'Certificado ITV',
    'foto_vehiculo': 'Fotos del Vehículo',
    'resolucion_nombramiento': 'Resolución de Nombramiento',
    'certificado_trabajo': 'Certificado de Trabajo',
    'acta_posesion': 'Acta de Posesión',
    'carnet_expirado': 'Carnet Expirado',
    'carnet_funcionario': 'Carnet de Funcionario',
    'contrato_compraventa': 'Contrato de Compraventa',
    'cuve': 'CUVE (Certificado Único Vehículo)',
    'cuve_antigua': 'CUVE Anterior',
    'identidad_comprador': 'Identidad del Comprador',
    'identidad_propietario': 'Identidad del Propietario',
    'identidad_vendedor': 'Identidad del Vendedor',
    'itv': 'Inspección Técnica (ITV)',
    'itv_antigua': 'ITV Anterior',
    'permiso_circulacion': 'Permiso de Circulación',
}


def _humanize_field_name(field_name: str) -> str:
    """Convert snake_case field name to a human-readable label.
    e.g. 'numero_dip' → 'Número DIP', 'fecha_nacimiento' → 'Fecha Nacimiento'
    """
    KNOWN = {
        'numero_dip': 'Número DIP',
        'numero_nie': 'Número NIE',
        'numero_pasaporte': 'Número Pasaporte',
        'numero_visado': 'Número Visado',
        'numero_permiso': 'Número Permiso',
        'numero_contrato': 'Número Contrato',
        'numero_protocolo': 'Número Protocolo',
        'numero_licencia': 'Número Licencia',
        'numero_autorizacion': 'Número Autorización',
        'numero_identificacion': 'Número Identificación',
        'numero_cuenta': 'Número Cuenta',
        'numero_ri': 'Número RI',
        'nif': 'NIF',
        'apellidos': 'Apellidos',
        'nombres': 'Nombres',
        'nombre': 'Nombre',
        'nombre_completo': 'Nombre Completo',
        'sexo': 'Sexo',
        'fecha_nacimiento': 'Fecha Nacimiento',
        'fecha_emision': 'Fecha Emisión',
        'fecha_expiracion': 'Fecha Expiración',
        'fecha_expedicion': 'Fecha Expedición',
        'fecha_firma': 'Fecha Firma',
        'fecha_registro': 'Fecha Registro',
        'fecha_certificado': 'Fecha Certificado',
        'fecha_autorizacion': 'Fecha Autorización',
        'fecha_validez': 'Fecha Validez',
        'fecha_entrada': 'Fecha Entrada',
        'fecha_ultima_salida': 'Fecha Última Salida',
        'nacionalidad': 'Nacionalidad',
        'natural_de': 'Natural De',
        'lugar_nacimiento': 'Lugar Nacimiento',
        'lugar_emision': 'Lugar Emisión',
        'tipo_contrato': 'Tipo Contrato',
        'tipo_visado': 'Tipo Visado',
        'tipo_permiso': 'Tipo Permiso',
        'tipo_sello': 'Tipo Sello',
        'tipo_escritura': 'Tipo Escritura',
        'tipo_cuenta': 'Tipo Cuenta',
        'monto_total': 'Monto Total',
        'moneda': 'Moneda',
        'resultado': 'Resultado',
        'representante_legal': 'Representante Legal',
        'descripcion': 'Descripción',
        'denominacion_social': 'Denominación Social',
        'forma_juridica': 'Forma Jurídica',
        'capital_social': 'Capital Social',
        'objeto_social': 'Objeto Social',
        'razon_social': 'Razón Social',
        'actividad_economica': 'Actividad Económica',
        'actividad_principal': 'Actividad Principal',
        'clase_principal': 'Clase Principal',
        'valido_hasta': 'Válido Hasta',
        'reg_numero': 'Registro Número',
        'nombre_centro': 'Centro Médico',
        'localidad': 'Localidad',
        'municipio': 'Municipio',
        'region': 'Región',
        'nombre_notario': 'Nombre Notario',
        'nombre_entidad': 'Nombre Entidad',
        'nombre_empresa': 'Nombre Empresa',
        'nif_contratista': 'NIF Contratista',
        'nombre_banco': 'Nombre Banco',
        'codigo_pais': 'Código País',
        'duracion_dias': 'Duración (Días)',
        'numero_entradas': 'Número Entradas',
        'puesto_fronterizo': 'Puesto Fronterizo',
        'total_entradas_visibles': 'Total Entradas Visibles',
        'comunidad_vecinos': 'Comunidad Vecinos',
        'pays_emission': 'País Emisión',
        'nom_pays': 'Nombre País',
        'validez_dias': 'Validez (Días)',
        'validez_meses': 'Validez (Meses)',
        'primer_apellido': 'Primer Apellido',
        'hijo_de': 'Hijo De',
        'hija_de': 'Hija De',
        'y_de': 'Y De',
        'documento_tipo': 'Tipo Documento',
        'documento_numero': 'Número Documento',
        'parentesco': 'Parentesco',
        'actividad': 'Actividad',
        'nombre_medico': 'Nombre Médico',
        'sociedad_nombre': 'Nombre Sociedad',
        'numero_bastidor': 'Número Bastidor',
        'matricula': 'Matrícula',
        'marca': 'Marca',
        'monto': 'Monto',
        'fecha': 'Fecha',
        'cargo': 'Cargo',
        'ministerio': 'Ministerio',
        'tipo_combustible': 'Tipo Combustible',
        'valedero_hasta': 'Valedero Hasta',
    }
    if field_name in KNOWN:
        return KNOWN[field_name]
    # Fallback: capitalize each word
    return field_name.replace('_', ' ').title()


async def _build_preview_data_sections(
    workflow_code: str,
    form_data: dict,
    db: asyncpg.Connection,
    request_id=None,
) -> List[PreviewDataSection]:
    """
    Build structured data sections from workflow_display_config.list_columns
    + composite data (form_data + extraction_data from DB).

    Architecture:
    - Single query fetches display_config + extraction_data in 1 round-trip
    - Columns grouped by document prefix → titled sections
    - System columns (reference, fullName, etc.) excluded (shown elsewhere)
    - Null values filtered out → conditional docs (mineur, renovación) naturally handled

    Returns empty list on error (graceful degradation).
    """
    try:
        # Single query: display_config + extraction_data in 1 round-trip
        if request_id:
            row = await db.fetchrow("""
                SELECT
                    wdc.list_columns,
                    COALESCE(
                        (SELECT jsonb_object_agg(srd.document_code, srd.extraction_data)
                         FROM service_request_documents srd
                         WHERE srd.service_request_id = $2
                           AND srd.extraction_data IS NOT NULL
                           AND srd.extraction_data != '{}'::jsonb),
                        '{}'::jsonb
                    ) as all_extractions
                FROM workflow_display_config wdc
                WHERE wdc.workflow_code = $1
            """, workflow_code, request_id)
        else:
            row = await db.fetchrow("""
                SELECT wdc.list_columns, '{}'::jsonb as all_extractions
                FROM workflow_display_config wdc
                WHERE wdc.workflow_code = $1
            """, workflow_code)

        if not row:
            return []

        configured_columns = row['list_columns']
        if not configured_columns or (isinstance(configured_columns, str) and configured_columns == '[]'):
            return []
        if isinstance(configured_columns, str):
            configured_columns = json.loads(configured_columns)

        # Build composite data (form_data + extraction_data per document)
        all_extractions = row['all_extractions']
        if isinstance(all_extractions, str):
            all_extractions = json.loads(all_extractions)

        composite: Dict[str, Any] = dict(form_data) if form_data else {}
        for doc_code, ext_data in all_extractions.items():
            if isinstance(ext_data, str):
                ext_data = json.loads(ext_data)
            clean = {k: v for k, v in ext_data.items()
                     if not k.startswith('_') and not isinstance(v, (dict, list))}
            if clean:
                composite[doc_code] = clean

        # Flatten to dot-notation
        flat_data = _flatten_form_data(composite)

        # Group columns by prefix (document_code) preserving order
        from collections import OrderedDict
        sections_map: OrderedDict[str, List[tuple]] = OrderedDict()

        for col_id in configured_columns:
            # Skip system columns (shown in header/payment/etc.)
            if col_id in _SYSTEM_COLUMNS:
                continue

            # Resolve value
            value = flat_data.get(col_id)

            # Also try form_data flat keys for unprefixed columns
            if value is None and '.' not in col_id:
                value = (form_data or {}).get(col_id)

            # Skip null/empty values
            if value is None or value == '' or value == 'null':
                continue

            # Determine section (prefix) and field name
            if '.' in col_id:
                prefix, field_name = col_id.split('.', 1)
            else:
                prefix = '_general'
                field_name = col_id

            if prefix not in sections_map:
                sections_map[prefix] = []

            label = _humanize_field_name(field_name)
            sections_map[prefix].append((label, str(value)))

        # Convert to Pydantic models
        result = []
        for prefix, fields in sections_map.items():
            if not fields:
                continue
            title = _SECTION_TITLES.get(prefix, prefix.replace('_', ' ').title())
            if prefix == '_general':
                title = 'Información General'
            result.append(PreviewDataSection(
                title=title,
                fields=[PreviewDataField(label=lbl, value=val) for lbl, val in fields],
            ))

        return result

    except Exception as e:
        logger.warning(f"_build_preview_data_sections failed for {workflow_code}: {e}")
        return []


@router.get(
    "/entity/{entity_code}/requests/{request_id}/preview",
    response_model=ServiceRequestPreview,
    summary="Get request preview for split view",
    description="""
    Get lightweight preview of a service request for the split view.
    Returns essential data for quick review without loading full detail page.

    Includes:
    - Request metadata (reference, status, priority, SLA)
    - Extracted data from form_data (dynamically based on type)
    - Documents (max 4 thumbnails)
    - Contact info (email, phone)
    - Appointment info if scheduled
    """
)
async def get_request_preview(
    entity_code: str = Path(..., description="Entity code (e.g., CNEDOGE_PASAPORTE)"),
    request_id: UUID = Path(..., description="Service request ID"),
    list_index: Optional[int] = Query(None, description="Current index in list for navigation"),
    list_total: Optional[int] = Query(None, description="Total items in list for navigation"),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("service_request.view"))
):
    """Get service request preview for split view."""
    # Main query with all necessary joins (including payment + assignment for system columns)
    query = """
        SELECT
            sr.id,
            sr.reference,
            sr.workflow_code,
            w.name_es as workflow_label,
            sr.solicitud_type,
            sr.form_data,
            sr.status,
            sr.priority,
            sr.created_at,
            sr.submitted_at,
            w.sla_hours,
            u.first_name,
            u.last_name,
            u.email,
            u.phone_number,
            ar.appointment_date,
            ar.appointment_time,
            el.location_name,
            el.location_address,
            sp.workflow_status AS payment_status,
            sp.total_amount,
            sp.payment_method,
            sp.currency AS payment_currency,
            sp.paid_at AS payment_paid_at,
            sp.payment_reference,
            sp.receipt_number AS payment_receipt_number,
            agent_u.first_name || ' ' || agent_u.last_name AS assigned_agent_name,
            sr.batch_id,
            (SELECT reference FROM batch_requests WHERE id = sr.batch_id) AS batch_reference
        FROM service_requests sr
        JOIN users u ON u.id = sr.user_id
        LEFT JOIN workflows w ON w.code = sr.workflow_code
        LEFT JOIN appointment_reservations ar ON ar.service_request_id = sr.id
            AND ar.status NOT IN ('cancelled', 'expired')
        LEFT JOIN entity_locations el ON el.id = ar.entity_location_id
        LEFT JOIN service_payments sp ON sp.service_request_id = sr.id
        LEFT JOIN assignments a ON a.item_id = sr.id
            AND a.status IN ('assigned', 'in_progress')
        LEFT JOIN agent_profiles ap ON ap.id = a.agent_profile_id
        LEFT JOIN users agent_u ON agent_u.id = ap.user_id
        WHERE sr.id = $1
    """

    row = await db.fetchrow(query, request_id)

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service request {request_id} not found"
        )

    # Parse form_data
    form_data = row['form_data'] or {}
    if isinstance(form_data, str):
        form_data = json.loads(form_data)

    # Calculate SLA
    sla_deadline = None
    sla_remaining_hours = None
    sla_status = "on_track"

    if row['submitted_at'] and row['sla_hours']:
        from datetime import timedelta
        sla_deadline = row['submitted_at'] + timedelta(hours=row['sla_hours'])
        now = datetime.now(timezone.utc)
        deadline_naive = sla_deadline if sla_deadline.tzinfo else sla_deadline

        remaining = (deadline_naive - now).total_seconds() / 3600
        sla_remaining_hours = round(remaining, 1)

        if remaining < 0:
            sla_status = "violated"
        elif remaining < 6:
            sla_status = "at_risk"

    # Get documents for split-view preview (compact list, max 8 covers all workflows)
    docs_query = """
        SELECT id, document_code, file_name, file_path, mime_type, is_valid
        FROM service_request_documents
        WHERE service_request_id = $1
        ORDER BY created_at ASC
        LIMIT 8
    """
    doc_rows = await db.fetch(docs_query, request_id)

    documents = [
        RequestPreviewDocument(
            id=str(d['id']),
            code=d['document_code'] or 'unknown',
            name=d['file_name'] or 'Document',
            file_url=d['file_path'],
            mime_type=d['mime_type'],
            validation_status='validated' if d['is_valid'] is True else ('rejected' if d['is_valid'] is False else 'pending')
        )
        for d in doc_rows
    ]

    # Get total document count
    docs_count = await db.fetchval("""
        SELECT COUNT(*) FROM service_request_documents
        WHERE service_request_id = $1
    """, request_id)

    # Build appointment info
    appointment = None
    if row['appointment_date'] and row['appointment_time']:
        appointment = RequestPreviewAppointment(
            date=row['appointment_date'].isoformat(),
            time=row['appointment_time'].strftime('%H:%M'),
            location_name=row['location_name'] or 'Location TBD',
            location_address=row['location_address']
        )

    # Build contact name
    contact_name = f"{row['first_name'] or ''} {row['last_name'] or ''}".strip() or "N/A"

    # Build structured data sections from display_config + composite data
    data_sections = await _build_preview_data_sections(
        workflow_code=row['workflow_code'],
        form_data=form_data,
        db=db,
        request_id=request_id,
    )

    return ServiceRequestPreview(
        id=str(row['id']),
        reference=row['reference'],
        workflow_code=row['workflow_code'],
        workflow_label=row['workflow_label'] or row['workflow_code'],
        solicitud_type=row['solicitud_type'] or '',
        motivo=form_data.get('motivo'),
        is_minor=form_data.get('is_minor', False) or False,
        status=row['status'],
        priority=row['priority'] or 'NORMAL',
        sla_deadline=sla_deadline.isoformat() if sla_deadline else None,
        sla_remaining_hours=sla_remaining_hours,
        sla_status=sla_status,
        data_sections=data_sections,
        documents=documents,
        documents_count=docs_count or 0,
        contact_name=contact_name,
        contact_email=row['email'],
        contact_phone=row['phone_number'],
        appointment=appointment,
        payment_status=row['payment_status'],
        payment_method=row['payment_method'],
        payment_amount=float(row['total_amount']) if row['total_amount'] else None,
        payment_currency=row['payment_currency'] or 'XAF',
        payment_paid_at=row['payment_paid_at'].isoformat() if row.get('payment_paid_at') else None,
        payment_reference=row['payment_reference'],
        payment_receipt_number=row.get('payment_receipt_number'),
        created_at=row['created_at'].isoformat(),
        submitted_at=row['submitted_at'].isoformat() if row['submitted_at'] else None,
        batch_id=str(row['batch_id']) if row.get('batch_id') else None,
        batch_reference=row.get('batch_reference'),
        list_index=list_index,
        list_total=list_total
    )


# ═══════════════════════════════════════════════════════════════
# WORKFLOW SCHEMA & AGENT VERIFICATION
# ═══════════════════════════════════════════════════════════════

class WorkflowSchemaResponse(BaseModel):
    """Workflow display schema for agent view"""
    code: str
    name: str
    formDisplaySchema: Optional[dict] = None
    agentChecklist: Optional[List[dict]] = None


@router.get(
    "/workflows/{workflow_code}/schema",
    response_model=WorkflowSchemaResponse,
    summary="Get workflow display schema",
    description="""
    Get the workflow configuration including:
    - formDisplaySchema: Layout for displaying submitted form data (2-column layout)
    - agentChecklist: List of verification items for the agent

    This is used by the agent dashboard to render the request detail view.
    """
)
async def get_workflow_schema(
    workflow_code: str = Path(..., description="Workflow code (e.g., PASAPORTE_NUEVO)"),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("service_request.view"))
):
    """Get workflow display schema and agent checklist."""
    row = await db.fetchrow("""
        SELECT code, name_es, config
        FROM workflows
        WHERE code = $1 AND is_active = TRUE
    """, workflow_code)

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow {workflow_code} not found"
        )

    config = row['config'] or {}
    if isinstance(config, str):
        config = json.loads(config)

    agent_checklist = config.get('agentChecklist')

    # If no checklist in DB config, extract from Python workflow class (confirmation step)
    if not agent_checklist:
        wf = workflow_engine.get_workflow_by_string(workflow_code)
        if wf and hasattr(wf, '_steps'):
            for step in wf._steps:
                if step.step_type.value == "confirmation" and step.config.get('agent_checklist'):
                    raw_items = step.config['agent_checklist']
                    agent_checklist = [
                        {
                            "id": item["id"],
                            "label": item.get("label_es", item.get("label", "")),
                            "required": item.get("required", False),
                        }
                        for item in raw_items
                    ]
                    break

    return WorkflowSchemaResponse(
        code=row['code'],
        name=row['name_es'],
        formDisplaySchema=config.get('formDisplaySchema'),
        agentChecklist=agent_checklist
    )


class VerificationResponse(BaseModel):
    """Response for verification update"""
    message: str
    request_id: str
    verification_status: str
    checklist_completed: int
    checklist_total: int


@router.patch(
    "/{request_id}/verification",
    response_model=VerificationResponse,
    summary="Update agent verification checklist",
    description="""
    Update the agent's verification checklist for a service request.

    The checklist is stored in service_requests.verification_details as JSON.
    Optionally update the verification_status (pending, in_progress, verified, etc.)

    **Checklist format:**
    ```json
    {
      "checklist": {
        "identity_verified": true,
        "documents_complete": true,
        "photo_valid": false
      },
      "verification_status": "in_progress",
      "notes": "Waiting for photo validation"
    }
    ```
    """
)
async def update_verification_checklist(
    request_id: UUID = Path(..., description="Service request ID"),
    body: VerificationChecklistUpdate = Body(...),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("service_request.review"))
):
    """Update verification checklist for a service request."""
    # Verify request exists and agent has access
    request = await db.fetchrow("""
        SELECT id, status, verification_details, verification_status
        FROM service_requests
        WHERE id = $1
    """, request_id)

    if not request:
        raise TranslatedException(ErrorCode.REQUEST_NOT_FOUND)

    # Prepare verification_details
    current_details = request['verification_details'] or {}
    if isinstance(current_details, str):
        current_details = json.loads(current_details)

    # Update with new checklist
    verification_details = {
        **current_details,
        "checklist": body.checklist,
        "last_updated_by": str(current_user.id),
        "last_updated_at": datetime.now(timezone.utc).isoformat()
    }

    if body.notes:
        verification_details["notes"] = body.notes

    # Determine verification_status
    new_status = body.verification_status or request['verification_status'] or 'in_progress'

    # Count completed items
    checklist_completed = sum(1 for v in body.checklist.values() if v is True)
    checklist_total = len(body.checklist)

    # Auto-set status based on checklist completion
    if not body.verification_status:
        if checklist_completed == checklist_total and checklist_total > 0:
            new_status = 'verified'
        elif checklist_completed > 0:
            new_status = 'in_progress'

    # Update database
    await db.execute("""
        UPDATE service_requests
        SET verification_details = $2::jsonb,
            verification_status = $3,
            updated_at = NOW()
        WHERE id = $1
    """, request_id, json.dumps(verification_details), new_status)

    # Detect if checklist actually changed vs only notes
    old_checklist = current_details.get("checklist", {})
    checklist_changed = body.checklist != old_checklist

    if checklist_changed:
        # Log checklist update (include note in comment if present)
        await db.execute("""
            INSERT INTO service_request_history
            (service_request_id, action, performed_by, comment, details)
            VALUES ($1, 'verification_updated', $2, $3, $4::jsonb)
        """, request_id, current_user.id, body.notes, json.dumps({
            "verification_status": new_status,
            "checklist_completed": checklist_completed,
            "checklist_total": checklist_total
        }))

    # If only notes changed (no checklist change), log as note_added
    if body.notes and body.notes.strip() and not checklist_changed:
        await db.execute("""
            INSERT INTO service_request_history
            (service_request_id, action, performed_by, comment)
            VALUES ($1, 'note_added', $2, $3)
        """, request_id, current_user.id, body.notes.strip())

    return VerificationResponse(
        message="Verification updated successfully",
        request_id=str(request_id),
        verification_status=new_status,
        checklist_completed=checklist_completed,
        checklist_total=checklist_total
    )


# ═══════════════════════════════════════════════════════════════
# DASHBOARD WIDGETS - Data endpoints for dynamic dashboard
# ═══════════════════════════════════════════════════════════════

class UrgentRequestItem(BaseModel):
    """Urgent request item for dashboard widget"""
    id: str
    reference: str
    workflow_code: str
    solicitud_type: str
    priority: str
    status: str
    citizen_name: str
    sla_status: str  # on_track, at_risk, violated
    sla_deadline: Optional[str] = None
    submitted_at: Optional[str] = None
    assigned_to: Optional[str] = None


class UrgentRequestsWidgetResponse(BaseModel):
    """Response for urgent requests widget"""
    items: List[UrgentRequestItem]
    total_urgent: int
    total_high: int
    total_assigned: int


@router.get(
    "/dashboard/widgets/urgent",
    response_model=UrgentRequestsWidgetResponse,
    summary="Get urgent requests for dashboard widget",
    description="""
    Get urgent (URGENT/HIGH priority) and assigned requests for the dashboard widget.
    Returns top items sorted by priority and SLA deadline.

    Use `limit` to control number of items (default: 10, use 0 for all).
    """
)
async def get_urgent_requests_widget(
    entity_code: str = Query(..., description="Entity code (e.g., CNEDOGE_PASAPORTE)"),
    limit: int = Query(10, ge=0, description="Max items to return (0 = all)"),
    include_assigned: bool = Query(True, description="Include assigned requests"),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    agent_ctx: AgentContext = Depends(get_agent_context),
    _=Depends(permission_required("service_request.view"))
):
    """Get urgent and assigned requests for dashboard widget.
    Scoped to agent's site (entity_location_id) unless global supervisor.
    """

    # Get entity's workflow codes
    entity = await db.fetchrow("""
        SELECT workflow_codes FROM entities WHERE code = $1 AND is_active = true
    """, entity_code)

    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entity {entity_code} not found"
        )

    # Parse workflow_codes from JSONB
    workflow_codes = entity['workflow_codes']
    if isinstance(workflow_codes, str):
        workflow_codes = json.loads(workflow_codes)
    if not workflow_codes:
        workflow_codes = []
    workflow_codes = [str(wf) for wf in workflow_codes] if workflow_codes else []

    if not workflow_codes:
        return UrgentRequestsWidgetResponse(
            items=[],
            total_urgent=0,
            total_high=0,
            total_assigned=0
        )

    # Build conditions for urgent/high priority OR assigned
    priority_condition = "sr.priority::text IN ('URGENT', 'HIGH')"
    assigned_condition = "sr.assigned_to IS NOT NULL" if include_assigned else "FALSE"

    # Site-scope: regular agents and site supervisors see only their site
    site_filter = ""
    query_params = [workflow_codes]
    if not agent_ctx.is_supervisor:
        # Regular agent: only requests assigned to them
        site_filter = "AND sr.assigned_to = $2"
        query_params.append(agent_ctx.user_id)
    elif not agent_ctx.has_global_scope and agent_ctx.entity_location_id:
        # Site supervisor: all requests at their site
        site_filter = "AND (sr.entity_location_id = $2 OR sr.entity_location_id IS NULL)"
        query_params.append(agent_ctx.entity_location_id)
    # Global supervisor: no site filter (sees all)

    # Main query with SLA calculation
    limit_clause = f"LIMIT {limit}" if limit > 0 else ""

    query = f"""
        SELECT
            sr.id,
            sr.reference,
            sr.workflow_code,
            sr.solicitud_type,
            sr.priority,
            sr.status,
            sr.assigned_to,
            sr.submitted_at,
            COALESCE(u.first_name || ' ' || u.last_name, 'N/A') as citizen_name,
            CASE
                WHEN sr.submitted_at IS NOT NULL AND w.sla_hours IS NOT NULL
                THEN sr.submitted_at + (w.sla_hours * interval '1 hour')
                ELSE sr.expires_at
            END as sla_deadline
        FROM service_requests sr
        JOIN users u ON u.id = sr.user_id
        LEFT JOIN workflows w ON w.code = sr.workflow_code
        WHERE sr.workflow_code = ANY($1)
          AND sr.status::text NOT IN ('DRAFT', 'COMPLETED', 'CANCELLED', 'REJECTED', 'EXPIRED', 'PAYMENT_PENDING')
          AND sr.payment_status = 'completed'
          AND ({priority_condition} OR {assigned_condition})
          {site_filter}
        ORDER BY
            CASE sr.priority
                WHEN 'URGENT' THEN 1
                WHEN 'HIGH' THEN 2
                ELSE 3
            END,
            sr.submitted_at ASC NULLS LAST
        {limit_clause}
    """

    rows = await db.fetch(query, *query_params)

    # Calculate SLA status and build response
    now = datetime.now(timezone.utc)
    items = []
    for row in rows:
        sla_status = "on_track"
        sla_deadline_str = None
        if row['sla_deadline']:
            deadline = row['sla_deadline']
            if hasattr(deadline, 'replace'):
                deadline = deadline
            sla_deadline_str = deadline.isoformat()
            if deadline < now:
                sla_status = "violated"
            elif (deadline - now).total_seconds() < get_settings().QUEUE_SLA_WARNING_HOURS * 3600:
                sla_status = "at_risk"

        items.append(UrgentRequestItem(
            id=str(row['id']),
            reference=row['reference'] or '',
            workflow_code=row['workflow_code'],
            solicitud_type=row['solicitud_type'] or '',
            priority=row['priority'] or 'NORMAL',
            status=row['status'],
            citizen_name=row['citizen_name'].strip() or 'N/A',
            sla_status=sla_status,
            sla_deadline=sla_deadline_str,
            submitted_at=row['submitted_at'].isoformat() if row['submitted_at'] else None,
            assigned_to=str(row['assigned_to']) if row['assigned_to'] else None
        ))

    # Get totals (same site scope)
    totals = await db.fetchrow(f"""
        SELECT
            COUNT(*) FILTER (WHERE sr.priority::text = 'URGENT') as total_urgent,
            COUNT(*) FILTER (WHERE sr.priority::text = 'HIGH') as total_high,
            COUNT(*) FILTER (WHERE sr.assigned_to IS NOT NULL) as total_assigned
        FROM service_requests sr
        WHERE sr.workflow_code = ANY($1)
          AND sr.status::text NOT IN ('DRAFT', 'COMPLETED', 'CANCELLED', 'REJECTED', 'EXPIRED', 'PAYMENT_PENDING')
          AND sr.payment_status = 'completed'
          {site_filter}
    """, *query_params)

    return UrgentRequestsWidgetResponse(
        items=items,
        total_urgent=totals['total_urgent'] or 0,
        total_high=totals['total_high'] or 0,
        total_assigned=totals['total_assigned'] or 0
    )


class AppointmentItem(BaseModel):
    """Appointment item for dashboard widget"""
    id: str
    reference: str
    workflow_code: str
    solicitud_type: str
    citizen_name: str
    cita_date: str
    cita_time: Optional[str] = None
    cita_location: Optional[str] = None
    status: str
    is_past: bool = False  # True if time has passed


class TodayAppointmentsWidgetResponse(BaseModel):
    """Response for today's appointments widget"""
    items: List[AppointmentItem]
    total_today: int
    completed_today: int
    upcoming_count: int


@router.get(
    "/dashboard/widgets/appointments",
    response_model=TodayAppointmentsWidgetResponse,
    summary="Get today's appointments for dashboard widget",
    description="""
    Get all appointments scheduled for today for the dashboard widget.
    Returns appointments sorted by time.
    """
)
async def get_today_appointments_widget(
    entity_code: str = Query(..., description="Entity code (e.g., CNEDOGE_PASAPORTE)"),
    include_past: bool = Query(True, description="Include past appointments from today"),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("service_request.view"))
):
    """Get today's appointments for dashboard widget."""

    # Get entity's workflow codes
    entity = await db.fetchrow("""
        SELECT workflow_codes FROM entities WHERE code = $1 AND is_active = true
    """, entity_code)

    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entity {entity_code} not found"
        )

    workflow_codes = entity['workflow_codes']
    if isinstance(workflow_codes, str):
        workflow_codes = json.loads(workflow_codes)
    if not workflow_codes:
        workflow_codes = []
    workflow_codes = [str(wf) for wf in workflow_codes] if workflow_codes else []

    if not workflow_codes:
        return TodayAppointmentsWidgetResponse(
            items=[],
            total_today=0,
            completed_today=0,
            upcoming_count=0
        )

    # Query today's appointments (no limit - show all)
    query = """
        SELECT
            sr.id,
            sr.reference,
            sr.workflow_code,
            sr.solicitud_type,
            sr.cita_date,
            sr.cita_time,
            sr.cita_location,
            sr.status,
            COALESCE(u.first_name || ' ' || u.last_name, 'N/A') as citizen_name
        FROM service_requests sr
        JOIN users u ON u.id = sr.user_id
        WHERE sr.workflow_code = ANY($1)
          AND sr.cita_date = CURRENT_DATE
        ORDER BY sr.cita_time ASC NULLS LAST
    """

    rows = await db.fetch(query, workflow_codes)

    # Build response with is_past calculation
    now = datetime.now(timezone.utc)
    current_time = now.time()
    items = []
    upcoming_count = 0
    completed_count = 0

    for row in rows:
        is_past = False
        if row['cita_time']:
            is_past = row['cita_time'] < current_time

        if row['status'] in ('COMPLETED', 'CANCELLED'):
            completed_count += 1
        elif not is_past:
            upcoming_count += 1

        # Skip past if not requested
        if is_past and not include_past:
            continue

        items.append(AppointmentItem(
            id=str(row['id']),
            reference=row['reference'] or '',
            workflow_code=row['workflow_code'],
            solicitud_type=row['solicitud_type'] or '',
            citizen_name=row['citizen_name'].strip() or 'N/A',
            cita_date=row['cita_date'].isoformat() if row['cita_date'] else '',
            cita_time=row['cita_time'].strftime('%H:%M') if row['cita_time'] else None,
            cita_location=row['cita_location'],
            status=row['status'],
            is_past=is_past
        ))

    return TodayAppointmentsWidgetResponse(
        items=items,
        total_today=len(rows),
        completed_today=completed_count,
        upcoming_count=upcoming_count
    )


class WorkflowDistributionItem(BaseModel):
    """Workflow distribution item"""
    workflow_code: str
    solicitud_type: str
    label: str  # Human-readable label
    count: int
    percentage: float


class WorkflowDistributionWidgetResponse(BaseModel):
    """Response for workflow distribution widget"""
    items: List[WorkflowDistributionItem]
    total: int


@router.get(
    "/dashboard/widgets/distribution",
    response_model=WorkflowDistributionWidgetResponse,
    summary="Get workflow distribution for dashboard widget",
    description="""
    Get the distribution of active requests by workflow type.
    Returns all workflow types with counts and percentages.
    """
)
async def get_workflow_distribution_widget(
    entity_code: str = Query(..., description="Entity code (e.g., CNEDOGE_PASAPORTE)"),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("service_request.view"))
):
    """Get workflow distribution for dashboard widget."""

    # Get entity's workflow codes
    entity = await db.fetchrow("""
        SELECT workflow_codes FROM entities WHERE code = $1 AND is_active = true
    """, entity_code)

    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entity {entity_code} not found"
        )

    workflow_codes = entity['workflow_codes']
    if isinstance(workflow_codes, str):
        workflow_codes = json.loads(workflow_codes)
    if not workflow_codes:
        workflow_codes = []
    workflow_codes = [str(wf) for wf in workflow_codes] if workflow_codes else []

    if not workflow_codes:
        return WorkflowDistributionWidgetResponse(items=[], total=0)

    # Query distribution INCLUDING all workflow codes (even with 0 count)
    # Use UNION to ensure all workflows appear
    query = """
        WITH workflow_list AS (
            -- Get all workflows for the entity with their names
            SELECT
                w.code as workflow_code,
                w.name_es as workflow_name
            FROM workflows w
            WHERE w.code = ANY($1)
        ),
        request_counts AS (
            -- Count active requests per workflow/type
            SELECT
                sr.workflow_code,
                sr.solicitud_type,
                COUNT(*) as count
            FROM service_requests sr
            WHERE sr.workflow_code = ANY($1)
              AND sr.status::text NOT IN ('DRAFT', 'CANCELLED', 'EXPIRED')
            GROUP BY sr.workflow_code, sr.solicitud_type
        )
        SELECT
            wl.workflow_code,
            COALESCE(rc.solicitud_type, 'expedicion') as solicitud_type,
            wl.workflow_name,
            COALESCE(rc.count, 0) as count
        FROM workflow_list wl
        LEFT JOIN request_counts rc
            ON wl.workflow_code = rc.workflow_code
        ORDER BY count DESC, wl.workflow_code
    """

    rows = await db.fetch(query, workflow_codes)

    # Calculate total and percentages
    total = sum(row['count'] for row in rows)

    # Build human-readable labels based on workflow code patterns
    def get_label(workflow_code: str, solicitud_type: str) -> str:
        # Extract type from workflow code (e.g., PASAPORTE_RENOVACION -> Renovación)
        code_lower = workflow_code.lower()

        if 'renovacion' in code_lower or 'renewal' in code_lower:
            return 'Renovación'
        elif 'perdida' in code_lower or 'loss' in code_lower:
            return 'Pérdida'
        elif 'robo' in code_lower or 'theft' in code_lower:
            return 'Robo'
        elif 'deterioro' in code_lower or 'damage' in code_lower:
            return 'Deterioro'
        elif 'duplicado' in code_lower or 'duplicate' in code_lower:
            return 'Duplicado'
        elif 'nuevo' in code_lower or 'new' in code_lower or 'primera' in code_lower:
            return 'Nuevo'
        elif 'canje' in code_lower or 'exchange' in code_lower:
            return 'Canje'
        elif 'extension' in code_lower:
            return 'Extensión'
        elif 'transferencia' in code_lower:
            return 'Transferencia'
        elif 'cambio' in code_lower:
            return 'Cambio'
        elif solicitud_type == 'renovacion':
            return 'Renovación'
        elif solicitud_type == 'expedicion':
            return 'Nuevo'
        else:
            # Fallback: use last part of workflow code
            parts = workflow_code.split('_')
            return parts[-1].title() if len(parts) > 1 else workflow_code

    items = []
    for row in rows:
        workflow_code = row['workflow_code']
        solicitud_type = row['solicitud_type'] or 'expedicion'

        label = get_label(workflow_code, solicitud_type)
        percentage = (row['count'] / total * 100) if total > 0 else 0

        items.append(WorkflowDistributionItem(
            workflow_code=workflow_code,
            solicitud_type=solicitud_type,
            label=label,
            count=row['count'],
            percentage=round(percentage, 1)
        ))

    return WorkflowDistributionWidgetResponse(items=items, total=total)


class AlertItem(BaseModel):
    """Alert item for dashboard widget"""
    id: str
    type: str  # sla_warning, documents_pending, assignment_needed, system
    severity: str  # info, warning, error
    title: str
    message: str
    request_id: Optional[str] = None
    request_reference: Optional[str] = None
    action_url: Optional[str] = None
    created_at: str


class AlertsWidgetResponse(BaseModel):
    """Response for alerts widget"""
    items: List[AlertItem]
    total_warnings: int
    total_errors: int


@router.get(
    "/dashboard/widgets/alerts",
    response_model=AlertsWidgetResponse,
    summary="Get system alerts for dashboard widget",
    description="""
    Get active alerts for the dashboard widget.
    Includes SLA warnings, pending documents, and system notifications.
    """
)
async def get_alerts_widget(
    entity_code: str = Query(..., description="Entity code (e.g., CNEDOGE_PASAPORTE)"),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("service_request.view"))
):
    """Get system alerts for dashboard widget."""

    # Get entity's workflow codes
    entity = await db.fetchrow("""
        SELECT workflow_codes FROM entities WHERE code = $1 AND is_active = true
    """, entity_code)

    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entity {entity_code} not found"
        )

    workflow_codes = entity['workflow_codes']
    if isinstance(workflow_codes, str):
        workflow_codes = json.loads(workflow_codes)
    if not workflow_codes:
        workflow_codes = []
    workflow_codes = [str(wf) for wf in workflow_codes] if workflow_codes else []

    alerts = []
    now = datetime.now(timezone.utc)

    # Build entity slug for action URLs (UPPER_SNAKE → lower-kebab)
    entity_slug = entity_code.lower().replace('_', '-')
    # Special case: TESORO → treasury (matches frontend slugToEntityCode)
    if entity_code == 'TESORO':
        entity_slug = 'treasury'

    if workflow_codes:
        # 1. SLA Violations (error severity)
        sla_violated = await db.fetch("""
            SELECT
                sr.id,
                sr.reference,
                sr.workflow_code,
                sr.submitted_at,
                w.sla_hours
            FROM service_requests sr
            LEFT JOIN workflows w ON w.code = sr.workflow_code
            WHERE sr.workflow_code = ANY($1)
              AND sr.status::text NOT IN ('DRAFT', 'COMPLETED', 'CANCELLED', 'REJECTED', 'EXPIRED', 'PAYMENT_PENDING')
              AND sr.payment_status = 'completed'
              AND sr.submitted_at IS NOT NULL
              AND w.sla_hours IS NOT NULL
              AND sr.submitted_at + (w.sla_hours * interval '1 hour') < NOW()
        """, workflow_codes)

        for row in sla_violated:
            alerts.append(AlertItem(
                id=f"sla_violated_{row['id']}",
                type="sla_warning",
                severity="error",
                title="SLA Vencido",
                message=f"La solicitud {row['reference']} ha superado el tiempo de SLA",
                request_id=str(row['id']),
                request_reference=row['reference'],
                action_url=f"/dashboard/agent/{entity_slug}/request/{row['id']}",
                created_at=now.isoformat()
            ))

        # 2. SLA At Risk (warning severity) - within 6 hours
        sla_at_risk = await db.fetch("""
            SELECT
                sr.id,
                sr.reference,
                sr.workflow_code,
                sr.submitted_at,
                w.sla_hours,
                sr.submitted_at + (w.sla_hours * interval '1 hour') as deadline
            FROM service_requests sr
            LEFT JOIN workflows w ON w.code = sr.workflow_code
            WHERE sr.workflow_code = ANY($1)
              AND sr.status::text NOT IN ('DRAFT', 'COMPLETED', 'CANCELLED', 'REJECTED', 'EXPIRED', 'PAYMENT_PENDING')
              AND sr.payment_status = 'completed'
              AND sr.submitted_at IS NOT NULL
              AND w.sla_hours IS NOT NULL
              AND sr.submitted_at + (w.sla_hours * interval '1 hour') > NOW()
              AND sr.submitted_at + (w.sla_hours * interval '1 hour') < NOW() + interval '6 hours'
        """, workflow_codes)

        for row in sla_at_risk:
            deadline = row['deadline']
            hours_left = (deadline - now).total_seconds() / 3600
            alerts.append(AlertItem(
                id=f"sla_risk_{row['id']}",
                type="sla_warning",
                severity="warning",
                title="SLA en Riesgo",
                message=f"La solicitud {row['reference']} vence en {hours_left:.1f} horas",
                request_id=str(row['id']),
                request_reference=row['reference'],
                action_url=f"/dashboard/agent/{entity_slug}/request/{row['id']}",
                created_at=now.isoformat()
            ))

        # 3. Documents pending (info severity)
        docs_pending = await db.fetch("""
            SELECT
                sr.id,
                sr.reference
            FROM service_requests sr
            WHERE sr.workflow_code = ANY($1)
              AND sr.status::text = 'DOCUMENTS_REQUIRED'
        """, workflow_codes)

        for row in docs_pending:
            alerts.append(AlertItem(
                id=f"docs_pending_{row['id']}",
                type="documents_pending",
                severity="info",
                title="Documentos Pendientes",
                message=f"La solicitud {row['reference']} está esperando documentos",
                request_id=str(row['id']),
                request_reference=row['reference'],
                action_url=f"/dashboard/agent/{entity_slug}/request/{row['id']}",
                created_at=now.isoformat()
            ))

    # Count by severity
    total_warnings = sum(1 for a in alerts if a.severity == 'warning')
    total_errors = sum(1 for a in alerts if a.severity == 'error')

    # Sort: errors first, then warnings, then info
    severity_order = {'error': 0, 'warning': 1, 'info': 2}
    alerts.sort(key=lambda a: severity_order.get(a.severity, 3))

    return AlertsWidgetResponse(
        items=alerts,
        total_warnings=total_warnings,
        total_errors=total_errors
    )


# ═══════════════════════════════════════════════════════════════
# WIDGET: PERSONAL STATS (Uses v_agent_performance_summary)
# ═══════════════════════════════════════════════════════════════

class PersonalStatsItem(BaseModel):
    """Personal statistics for an agent"""
    agent_profile_id: Optional[str] = None
    current_month_processed: int = 0
    current_month_approved: int = 0
    current_month_rejected: int = 0
    current_month_escalated: int = 0
    avg_processing_minutes: Optional[float] = None
    sla_respected_count: int = 0
    sla_missed_count: int = 0
    sla_respect_percentage: Optional[float] = None
    approval_rate: Optional[float] = None
    rejection_rate: Optional[float] = None
    escalation_rate: Optional[float] = None
    last_action_at: Optional[str] = None


class PersonalStatsWidgetResponse(BaseModel):
    """Response for personal stats widget"""
    stats: PersonalStatsItem
    period_label: str = "Este mes"


@router.get(
    "/dashboard/widgets/personal-stats",
    response_model=PersonalStatsWidgetResponse,
    summary="Get personal performance stats for current agent"
)
async def get_personal_stats_widget(
    current_user: User = Depends(get_current_user),
    db=Depends(get_database)
):
    """
    Get personal performance statistics from v_agent_performance_summary.
    Uses the view to get pre-calculated metrics.
    """
    user_id = UUID(str(current_user.id))

    conn = db
    # Query the view directly
    row = await conn.fetchrow("""
        SELECT
            agent_profile_id::text,
            COALESCE(current_month_processed, 0) as current_month_processed,
            COALESCE(current_month_approved, 0) as current_month_approved,
            COALESCE(current_month_rejected, 0) as current_month_rejected,
            COALESCE(current_month_escalated, 0) as current_month_escalated,
            avg_processing_minutes,
            COALESCE(sla_respected_count, 0) as sla_respected_count,
            COALESCE(sla_missed_count, 0) as sla_missed_count,
            sla_respect_percentage,
            approval_rate,
            rejection_rate,
            escalation_rate,
            last_action_at
        FROM v_agent_performance_summary
        WHERE user_id = $1
    """, user_id)

    if row:
        stats = PersonalStatsItem(
            agent_profile_id=row['agent_profile_id'],
            current_month_processed=row['current_month_processed'],
            current_month_approved=row['current_month_approved'],
            current_month_rejected=row['current_month_rejected'],
            current_month_escalated=row['current_month_escalated'],
            avg_processing_minutes=float(row['avg_processing_minutes']) if row['avg_processing_minutes'] else None,
            sla_respected_count=row['sla_respected_count'],
            sla_missed_count=row['sla_missed_count'],
            sla_respect_percentage=float(row['sla_respect_percentage']) if row['sla_respect_percentage'] else None,
            approval_rate=float(row['approval_rate']) if row['approval_rate'] else None,
            rejection_rate=float(row['rejection_rate']) if row['rejection_rate'] else None,
            escalation_rate=float(row['escalation_rate']) if row['escalation_rate'] else None,
            last_action_at=row['last_action_at'].isoformat() if row['last_action_at'] else None
        )
    else:
        stats = PersonalStatsItem()

    return PersonalStatsWidgetResponse(stats=stats, period_label="Este mes")


# ═══════════════════════════════════════════════════════════════
# WIDGET: TEAM WORKLOAD (Uses v_agents_workload_dashboard)
# For supervisors only
# ═══════════════════════════════════════════════════════════════

class TeamMemberWorkload(BaseModel):
    """Workload info for a team member"""
    agent_profile_id: str
    full_name: str
    email: Optional[str] = None
    current_assignments: int = 0
    max_concurrent_assignments: int = 10
    capacity_percentage: Optional[float] = None
    load_level: str = "normal"  # low/normal/high/critical
    workload_status: str = "available"
    availability: str = "available"
    current_month_processed: int = 0
    sla_respect_percentage: Optional[float] = None


class TeamWorkloadWidgetResponse(BaseModel):
    """Response for team workload widget"""
    members: List[TeamMemberWorkload]
    total_agents: int = 0
    available_agents: int = 0
    overloaded_agents: int = 0
    avg_capacity: Optional[float] = None


@router.get(
    "/dashboard/widgets/team-workload",
    response_model=TeamWorkloadWidgetResponse,
    summary="Get team workload for supervisors"
)
async def get_team_workload_widget(
    entity_code: str = Query(..., description="Entity code to filter"),
    current_user: User = Depends(get_current_user),
    db=Depends(get_database),
    _=Depends(permission_required("agent.view_team"))
):
    """
    Get team workload from v_agents_workload_dashboard.
    Only for supervisors - shows all agents in their entity.
    """
    conn = db
    # Query the view for the entity
    rows = await conn.fetch("""
        SELECT
            agent_profile_id::text,
            full_name,
            email,
            COALESCE(current_assignments, 0) as current_assignments,
            COALESCE(max_concurrent_assignments, 10) as max_concurrent_assignments,
            capacity_percentage,
            COALESCE(load_level, 'normal') as load_level,
            COALESCE(workload_status, 'available') as workload_status,
            COALESCE(availability, 'available') as availability,
            COALESCE(current_month_processed, 0) as current_month_processed,
            sla_respect_percentage
        FROM v_agents_workload_dashboard
        WHERE entity_code = $1
          AND is_active = true
        ORDER BY capacity_percentage DESC NULLS LAST
    """, entity_code)

    members = []
    total_capacity = 0
    capacity_count = 0

    for row in rows:
        member = TeamMemberWorkload(
            agent_profile_id=row['agent_profile_id'],
            full_name=row['full_name'] or 'N/A',
            email=row['email'],
            current_assignments=row['current_assignments'],
            max_concurrent_assignments=row['max_concurrent_assignments'],
            capacity_percentage=float(row['capacity_percentage']) if row['capacity_percentage'] else None,
            load_level=row['load_level'],
            workload_status=row['workload_status'],
            availability=row['availability'],
            current_month_processed=row['current_month_processed'],
            sla_respect_percentage=float(row['sla_respect_percentage']) if row['sla_respect_percentage'] else None
        )
        members.append(member)

        if row['capacity_percentage'] is not None:
            total_capacity += float(row['capacity_percentage'])
            capacity_count += 1

    available_count = sum(1 for m in members if m.availability == 'available')
    overloaded_count = sum(1 for m in members if m.load_level in ('high', 'critical'))
    avg_cap = total_capacity / capacity_count if capacity_count > 0 else None

    return TeamWorkloadWidgetResponse(
        members=members,
        total_agents=len(members),
        available_agents=available_count,
        overloaded_agents=overloaded_count,
        avg_capacity=avg_cap
    )


# ═══════════════════════════════════════════════════════════════
# WIDGET: ESCALATIONS (reads service_requests WHERE escalated = true)
# For supervisors only
# ═══════════════════════════════════════════════════════════════

# Map service_request priority enum to widget escalation levels
_PRIORITY_TO_LEVEL = {
    'URGENT': 'critical',
    'HIGH': 'high',
    'NORMAL': 'medium',
    'LOW': 'low',
}


class EscalationItem(BaseModel):
    """Escalation item from service_requests.
    When escalated=true, escalation_reason/escalated_at/escalated_by are guaranteed
    non-null by CHECK constraint chk_escalation_fields_populated (migration 114).
    """
    request_id: str
    reference: str
    workflow_code: Optional[str] = None
    total_amount: Optional[float] = None        # LEFT JOIN payment — truly optional
    escalation_level: str                        # always computed from priority
    escalation_reason: str                       # guaranteed by CHECK constraint
    escalated_at: str                            # guaranteed by CHECK constraint
    hours_since_escalation: float = 0.0          # always computed from escalated_at
    escalated_by_name: str                       # guaranteed by CHECK + INNER JOIN
    assigned_to_name: Optional[str] = None       # truly optional (not yet assigned)


class EscalationsWidgetResponse(BaseModel):
    """Response for escalations widget"""
    items: List[EscalationItem]
    total_escalations: int = 0
    critical_count: int = 0
    high_count: int = 0


@router.get(
    "/dashboard/widgets/escalations",
    response_model=EscalationsWidgetResponse,
    summary="Get pending escalations for supervisors"
)
async def get_escalations_widget(
    entity_code: Optional[str] = Query(None, description="Entity code to filter"),
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db=Depends(get_database),
    _=Depends(permission_required("agent.view_escalations"))
):
    """
    Get pending escalations from service_requests WHERE escalated = true.
    Scoped to entity's workflow_codes. Only for supervisors.
    """
    conditions = ["sr.escalated = true"]
    params: list = []
    param_idx = 1

    # Scope to entity's workflow_codes
    if entity_code:
        entity = await db.fetchrow(
            "SELECT workflow_codes FROM entities WHERE code = $1",
            entity_code
        )
        if entity and entity['workflow_codes']:
            wf_codes = entity['workflow_codes']
            if isinstance(wf_codes, str):
                wf_codes = json.loads(wf_codes)
            conditions.append(f"sr.workflow_code = ANY(${param_idx})")
            params.append([str(c) for c in wf_codes])
            param_idx += 1

    where_clause = " AND ".join(conditions)
    params.append(limit)

    rows = await db.fetch(f"""
        SELECT
            sr.id,
            sr.reference,
            sr.workflow_code,
            sr.priority,
            sr.escalation_reason,
            sr.escalated_at,
            sr.escalated_by,
            sr.assigned_to,
            ROUND(EXTRACT(EPOCH FROM (NOW() - sr.escalated_at)) / 3600, 2) as hours_since_escalation,
            esc_user.first_name || ' ' || esc_user.last_name as escalated_by_name,
            asgn_user.first_name || ' ' || asgn_user.last_name as assigned_to_name,
            sp.total_amount
        FROM service_requests sr
        JOIN users esc_user ON esc_user.id = sr.escalated_by
        LEFT JOIN users asgn_user ON asgn_user.id = sr.assigned_to
        LEFT JOIN service_payments sp ON sp.service_request_id = sr.id
            AND sp.status != 'cancelled'
        WHERE {where_clause}
        ORDER BY
            CASE sr.priority
                WHEN 'URGENT' THEN 1 WHEN 'HIGH' THEN 2
                WHEN 'NORMAL' THEN 3 ELSE 4
            END ASC,
            sr.escalated_at ASC
        LIMIT ${param_idx}
    """, *params)

    items = []
    critical_count = 0
    high_count = 0

    for row in rows:
        level = _PRIORITY_TO_LEVEL.get(str(row['priority']), 'medium')
        if level == 'critical':
            critical_count += 1
        elif level == 'high':
            high_count += 1

        items.append(EscalationItem(
            request_id=str(row['id']),
            reference=row['reference'] or 'N/A',
            workflow_code=row['workflow_code'],
            total_amount=float(row['total_amount']) if row['total_amount'] else None,
            escalation_level=level,
            escalation_reason=row['escalation_reason'],
            escalated_at=row['escalated_at'].isoformat(),
            hours_since_escalation=float(row['hours_since_escalation']),
            escalated_by_name=row['escalated_by_name'],
            assigned_to_name=row['assigned_to_name'],
        ))

    return EscalationsWidgetResponse(
        items=items,
        total_escalations=len(items),
        critical_count=critical_count,
        high_count=high_count
    )


# ═══════════════════════════════════════════════════════════════
# WIDGET: PENDING PAYMENTS (Uses v_pending_payment_validations)
# For treasury agents
# ═══════════════════════════════════════════════════════════════

class PendingPaymentItem(BaseModel):
    """Pending payment item"""
    payment_id: str
    payment_reference: str
    request_reference: Optional[str] = None
    workflow_code: Optional[str] = None
    user_name: Optional[str] = None
    payment_method: Optional[str] = None
    total_amount: Optional[float] = None
    currency: str = "XAF"
    hours_waiting: Optional[float] = None
    assigned_to_name: Optional[str] = None
    created_at: str


class PendingPaymentsWidgetResponse(BaseModel):
    """Response for pending payments widget"""
    items: List[PendingPaymentItem]
    total_pending: int = 0
    total_amount: Optional[float] = None
    avg_waiting_hours: Optional[float] = None


@router.get(
    "/dashboard/widgets/pending-payments",
    response_model=PendingPaymentsWidgetResponse,
    summary="Get pending payment validations for treasury"
)
async def get_pending_payments_widget(
    workflow_code: Optional[str] = Query(None, description="Filter by workflow code"),
    workflow_status: Optional[str] = Query(None, description="Filter by workflow status (e.g. pending_agent_review, agent_reviewing, approved_by_agent, completed)"),
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db=Depends(get_database),
    _=Depends(permission_required("treasury.view_payment"))
):
    """
    Get payment validations for the dashboard widget.

    Scope (P8.2-B1.4 — fix cross-entity leak observed on dashboard while the
    validation list was correctly scoped):

      - Regular agent: only own assigned payments (assigned_agent_id = me)
      - Entity supervisor: own entity only (sp.entity_code = my entity)
      - Global (treasury.view_all): all entities

    Previously this widget used `v_pending_payment_validations` with no
    filter, so every treasury agent saw every pending payment regardless
    of assignment or entity. That caused tesoreria.ge and tesorobata to
    both see the full set of 3 bundle splits in their agent dashboard.
    """
    from app.modules.service_requests.api.admin_routes import _get_treasury_context

    conn = db

    tctx = await _get_treasury_context(conn, current_user.id)
    is_global = tctx.has_global_scope
    is_supervisor = is_global or tctx.is_supervisor

    # Build WHERE clauses common to all branches
    where_parts: list = []
    params: list = []

    effective_status = workflow_status or "pending_agent_review"
    where_parts.append(f"sp.workflow_status = ${len(params) + 1}")
    params.append(effective_status)

    if workflow_code:
        where_parts.append(f"sr.workflow_code = ${len(params) + 1}")
        params.append(workflow_code)

    # Entity / agent scoping
    if not is_supervisor:
        # Regular agent: only own assigned payments
        if not tctx.profile_id:
            return PendingPaymentsWidgetResponse(
                items=[], total_pending=0, total_amount=None, avg_waiting_hours=None,
            )
        where_parts.append(f"sp.assigned_agent_id = ${len(params) + 1}::uuid")
        params.append(tctx.profile_id)
    elif not is_global and tctx.entity_code:
        # Entity supervisor: own entity only (by payment ownership, not assignee)
        where_parts.append(f"sp.entity_code = ${len(params) + 1}")
        params.append(tctx.entity_code)
    # Global scope: no extra filter

    where_sql = " AND ".join(where_parts)

    base_query = f"""
        SELECT
            sp.id::text AS payment_id,
            sp.payment_reference,
            sr.reference AS request_reference,
            sr.workflow_code,
            COALESCE(u.full_name, u.first_name || ' ' || u.last_name) AS user_name,
            sp.payment_method::text,
            sp.total_amount,
            sp.currency,
            EXTRACT(EPOCH FROM (NOW() - sp.created_at)) / 3600 AS hours_waiting,
            COALESCE(au.full_name, au.first_name || ' ' || au.last_name) AS assigned_to_name,
            sp.created_at
        FROM service_payments sp
        LEFT JOIN service_requests sr ON sr.id = sp.service_request_id
        LEFT JOIN users u ON u.id = sp.user_id
        LEFT JOIN agent_profiles ap ON ap.id = sp.assigned_agent_id
        LEFT JOIN users au ON au.id = ap.user_id
        WHERE {where_sql}
        ORDER BY sp.created_at DESC
        LIMIT ${len(params) + 1}
    """
    params.append(limit)
    rows = await conn.fetch(base_query, *params)

    items = []
    total_amt = 0
    total_hours = 0
    hours_count = 0

    for row in rows:
        if row['total_amount']:
            total_amt += float(row['total_amount'])
        if row['hours_waiting']:
            total_hours += float(row['hours_waiting'])
            hours_count += 1

        items.append(PendingPaymentItem(
            payment_id=row['payment_id'],
            payment_reference=row['payment_reference'] or 'N/A',
            request_reference=row['request_reference'],
            workflow_code=row['workflow_code'],
            user_name=row['user_name'],
            payment_method=row['payment_method'],
            total_amount=float(row['total_amount']) if row['total_amount'] else None,
            currency=row['currency'] or 'XAF',
            hours_waiting=float(row['hours_waiting']) if row['hours_waiting'] else None,
            assigned_to_name=row['assigned_to_name'],
            created_at=row['created_at'].isoformat() if row['created_at'] else ''
        ))

    return PendingPaymentsWidgetResponse(
        items=items,
        total_pending=len(items),
        total_amount=total_amt if total_amt > 0 else None,
        avg_waiting_hours=total_hours / hours_count if hours_count > 0 else None
    )


# ═══════════════════════════════════════════════════════════════
# WIDGET: ANOMALY SUMMARY (Uses v_anomaly_summary)
# For treasury/supervisors
# ═══════════════════════════════════════════════════════════════

class AnomalySummaryItem(BaseModel):
    """Anomaly summary by type"""
    anomaly_type: str
    severity: str
    status: str
    count: int
    total_affected: Optional[float] = None


class AnomalySummaryWidgetResponse(BaseModel):
    """Response for anomaly summary widget"""
    items: List[AnomalySummaryItem]
    total_open: int = 0
    total_critical: int = 0
    total_amount_affected: Optional[float] = None


@router.get(
    "/dashboard/widgets/anomaly-summary",
    response_model=AnomalySummaryWidgetResponse,
    summary="Get payment anomaly summary"
)
async def get_anomaly_summary_widget(
    current_user: User = Depends(get_current_user),
    db=Depends(get_database),
    _=Depends(permission_required("treasury_anomaly.view"))
):
    """
    Get anomaly summary from v_anomaly_summary.
    For treasury agents and supervisors.
    """
    conn = db
    rows = await conn.fetch("""
        SELECT
            anomaly_type::text,
            severity::text,
            status::text,
            count,
            total_affected
        FROM v_anomaly_summary
        WHERE status::text IN ('open', 'investigating')
        ORDER BY
            CASE severity::text
                WHEN 'critical' THEN 1
                WHEN 'high' THEN 2
                WHEN 'medium' THEN 3
                WHEN 'low' THEN 4
                ELSE 5
            END,
            count DESC
    """)

    items = []
    total_open = 0
    total_critical = 0
    total_amount = 0

    for row in rows:
        count = int(row['count'])
        total_open += count

        if row['severity'] == 'critical':
            total_critical += count

        if row['total_affected']:
            total_amount += float(row['total_affected'])

        items.append(AnomalySummaryItem(
            anomaly_type=row['anomaly_type'],
            severity=row['severity'],
            status=row['status'],
            count=count,
            total_affected=float(row['total_affected']) if row['total_affected'] else None
        ))

    return AnomalySummaryWidgetResponse(
        items=items,
        total_open=total_open,
        total_critical=total_critical,
        total_amount_affected=total_amount if total_amount > 0 else None
    )


# ═══════════════════════════════════════════════════════════════
# WIDGET: CALENDAR WEEK (Weekly appointments view)
# ═══════════════════════════════════════════════════════════════

class WeekAppointmentItem(BaseModel):
    """Appointment item for weekly calendar"""
    id: str
    reference: str
    workflow_code: str
    solicitud_type: str
    citizen_name: str
    cita_date: str
    cita_time: Optional[str] = None
    cita_location: Optional[str] = None
    status: str
    appointment_status: Optional[str] = None


class DayAppointments(BaseModel):
    """Appointments for a single day"""
    date: str  # ISO date string
    day_name: str  # lunes, martes, etc.
    day_number: int  # 1-31
    is_today: bool = False
    is_past: bool = False
    appointments: List[WeekAppointmentItem] = []
    count: int = 0


class CalendarWeekWidgetResponse(BaseModel):
    """Response for weekly calendar widget"""
    week_start: str
    week_end: str
    days: List[DayAppointments]
    total_week: int = 0
    today_count: int = 0


@router.get(
    "/dashboard/widgets/calendar-week",
    response_model=CalendarWeekWidgetResponse,
    summary="Get weekly appointments for calendar widget"
)
async def get_calendar_week_widget(
    entity_code: str = Query(..., description="Entity code (e.g., CNEDOGE_PASAPORTE)"),
    week_offset: int = Query(0, description="Week offset from current (0=this week, 1=next, -1=previous)"),
    current_user: User = Depends(get_current_user),
    db=Depends(get_database),
    _=Depends(permission_required("service_request.view"))
):
    """
    Get appointments for the week displayed in a calendar format.
    Returns appointments grouped by day for a 7-day view.
    """
    from datetime import timedelta
    import locale

    # Spanish day names
    day_names_es = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']

    conn = db
    # Get entity's workflow codes
    entity = await conn.fetchrow("""
        SELECT workflow_codes FROM entities WHERE code = $1 AND is_active = true
    """, entity_code)

    if not entity:
        raise TranslatedException(ErrorCode.NOT_FOUND)

    # Handle workflow_codes - ensure it's a list (JSONB can sometimes return as string)
    workflow_codes = entity['workflow_codes'] or []
    if isinstance(workflow_codes, str):
        import json
        try:
            workflow_codes = json.loads(workflow_codes)
        except (json.JSONDecodeError, TypeError):
            workflow_codes = []
    if not isinstance(workflow_codes, list):
        workflow_codes = []

    # Calculate week boundaries
    today = date.today()
    # Start of current week (Monday)
    week_start = today - timedelta(days=today.weekday())
    # Apply offset
    week_start = week_start + timedelta(weeks=week_offset)
    week_end = week_start + timedelta(days=6)

    # Query appointments for the week
    rows = await conn.fetch("""
        SELECT
            sr.id::text,
            sr.reference,
            sr.workflow_code,
            sr.solicitud_type,
            COALESCE(u.full_name, u.email, 'N/A') as citizen_name,
            sr.cita_date,
            sr.cita_time,
            sr.cita_location,
            sr.status,
            sr.appointment_status
        FROM service_requests sr
        JOIN users u ON u.id = sr.user_id
        WHERE sr.workflow_code = ANY($1)
          AND sr.cita_date BETWEEN $2 AND $3
          AND sr.status NOT IN ('CANCELLED', 'REJECTED', 'EXPIRED')
        ORDER BY sr.cita_date, sr.cita_time ASC NULLS LAST
    """, workflow_codes, week_start, week_end)

    # Group by date
    appointments_by_date: Dict[date, List[WeekAppointmentItem]] = {}
    for row in rows:
        cita_date = row['cita_date']
        if cita_date not in appointments_by_date:
            appointments_by_date[cita_date] = []

        appointments_by_date[cita_date].append(WeekAppointmentItem(
            id=row['id'],
            reference=row['reference'],
            workflow_code=row['workflow_code'],
            solicitud_type=row['solicitud_type'],
            citizen_name=row['citizen_name'],
            cita_date=row['cita_date'].isoformat(),
            cita_time=row['cita_time'].strftime('%H:%M') if row['cita_time'] else None,
            cita_location=row['cita_location'],
            status=row['status'],
            appointment_status=row['appointment_status']
        ))

    # Build 7-day structure
    days = []
    total_week = 0
    today_count = 0

    for i in range(7):
        day_date = week_start + timedelta(days=i)
        day_appointments = appointments_by_date.get(day_date, [])
        count = len(day_appointments)
        total_week += count

        is_today = day_date == today
        if is_today:
            today_count = count

        days.append(DayAppointments(
            date=day_date.isoformat(),
            day_name=day_names_es[day_date.weekday()],
            day_number=day_date.day,
            is_today=is_today,
            is_past=day_date < today,
            appointments=day_appointments,
            count=count
        ))

    return CalendarWeekWidgetResponse(
        week_start=week_start.isoformat(),
        week_end=week_end.isoformat(),
        days=days,
        total_week=total_week,
        today_count=today_count
    )


# ═══════════════════════════════════════════════════════════════
# WIDGET: CALENDAR SLOTS (Available slots summary)
# Shows slot availability per day for quick dashboard view
# ═══════════════════════════════════════════════════════════════

class DaySlotSummary(BaseModel):
    """Summary of slot availability for a single day"""
    date: str
    day_name: str
    day_number: int
    is_today: bool = False
    is_past: bool = False
    is_blocked: bool = False
    total_slots: int = 0
    booked_slots: int = 0
    available_slots: int = 0
    fill_percentage: float = 0.0
    status: str = "available"  # available, limited, full, closed


class LocationInfo(BaseModel):
    """Location info for the widget"""
    id: str
    name: str
    city: str


class CalendarSlotsWidgetResponse(BaseModel):
    """Response for calendar slots widget"""
    week_start: str
    week_end: str
    entity_code: str
    location: Optional[LocationInfo] = None
    locations_available: List[LocationInfo] = []
    days: List[DaySlotSummary]
    total_available: int = 0
    total_booked: int = 0
    total_capacity: int = 0


async def _get_scoped_locations(
    conn, entity_code: str, agent_ctx: AgentContext
) -> list:
    """
    Get entity locations scoped by agent site.
    Non-supervisors only see their own site; supervisors see all.
    Uses pre-resolved AgentContext (no extra SQL query).
    Returns list of LocationInfo objects.
    """
    # Security: no agent profile = no locations (never fall through to "all")
    if not agent_ctx.has_profile:
        return []

    if not agent_ctx.has_global_scope and agent_ctx.entity_location_id:
        rows = await conn.fetch("""
            SELECT id::text, location_name, city
            FROM entity_locations
            WHERE entity_code = $1 AND is_active = true AND id = $2
            ORDER BY is_main_office DESC, location_name
        """, entity_code, agent_ctx.entity_location_id)
    else:
        rows = await conn.fetch("""
            SELECT id::text, location_name, city
            FROM entity_locations
            WHERE entity_code = $1 AND is_active = true
            ORDER BY is_main_office DESC, location_name
        """, entity_code)

    return [
        LocationInfo(id=row['id'], name=row['location_name'], city=row['city'])
        for row in rows
    ]


@router.get(
    "/dashboard/widgets/calendar-slots",
    response_model=CalendarSlotsWidgetResponse,
    summary="Get slot availability summary for dashboard widget"
)
async def get_calendar_slots_widget(
    entity_code: str = Query(..., description="Entity code (e.g., CNEDOGE_PASAPORTE)"),
    week_offset: int = Query(0, description="Week offset (0=current, 1=next, -1=prev)"),
    location_id: Optional[UUID] = Query(None, description="Filter by location"),
    agent_ctx: AgentContext = Depends(get_agent_context),
    db=Depends(get_database),
    _=Depends(permission_required("service_request.view"))
):
    """
    Get slot availability summary for dashboard widget.
    Shows available vs booked slots per day for the week.

    Capacity rules:
    - Priority 1: appointment_slot_configs.max_appointments_per_slot (configured)
    - Priority 2: Default = 2 if not configured
    """
    from datetime import timedelta

    DEFAULT_MAX_PER_SLOT = 2
    day_names_es = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']

    conn = db
    # Get entity locations (scoped by agent site)
    locations_available = await _get_scoped_locations(conn, entity_code, agent_ctx)

    # Determine which location to use
    selected_location = None
    entity_location_id = None
    if location_id:
        for loc in locations_available:
            if loc.id == str(location_id):
                selected_location = loc
                entity_location_id = location_id
                break
    elif locations_available:
        selected_location = locations_available[0]
        entity_location_id = UUID(selected_location.id)

    # Calculate week boundaries
    today = date.today()
    week_start = today - timedelta(days=today.weekday())  # Monday
    week_start = week_start + timedelta(weeks=week_offset)
    week_end = week_start + timedelta(days=6)

    # Get slot configs for all days of week
    slot_configs = {}
    config_rows = await conn.fetch("""
        SELECT
            day_of_week,
            start_time,
            end_time,
            slot_duration_minutes,
            max_appointments_per_slot
        FROM appointment_slot_configs
        WHERE entity_code = $1
          AND is_active = true
          AND (entity_location_id IS NULL OR entity_location_id = $2)
        ORDER BY day_of_week
    """, entity_code, entity_location_id)

    for row in config_rows:
        slot_configs[row['day_of_week']] = {
            'start_time': row['start_time'],
            'end_time': row['end_time'],
            'duration': row['slot_duration_minutes'] or 30,
            'max_per_slot': row['max_appointments_per_slot'] or DEFAULT_MAX_PER_SLOT
        }

    # Get blocked dates
    blocked_dates = set()
    blocked_rows = await conn.fetch("""
        SELECT blocked_date
        FROM appointment_blocked_dates
        WHERE (entity_code = $1 OR entity_code = 'ALL')
          AND blocked_date BETWEEN $2 AND $3
    """, entity_code, week_start, week_end)
    for row in blocked_rows:
        blocked_dates.add(row['blocked_date'])

    # Get booked appointments count per day
    bookings_query = """
        SELECT
            ar.appointment_date,
            COUNT(*) as booked_count
        FROM appointment_reservations ar
        LEFT JOIN entity_locations el ON ar.entity_location_id = el.id
        WHERE el.entity_code = $1
          AND ar.appointment_date BETWEEN $2 AND $3
          AND ar.status NOT IN ('cancelled', 'expired')
    """
    params = [entity_code, week_start, week_end]

    if entity_location_id:
        bookings_query += " AND ar.entity_location_id = $4"
        params.append(entity_location_id)

    bookings_query += " GROUP BY ar.appointment_date"

    bookings_rows = await conn.fetch(bookings_query, *params)
    bookings_by_date = {row['appointment_date']: row['booked_count'] for row in bookings_rows}

    # Build 7-day structure
    days = []
    total_available = 0
    total_booked = 0
    total_capacity = 0

    for i in range(7):
        day_date = week_start + timedelta(days=i)
        day_of_week = day_date.weekday()  # 0=Monday
        is_today = day_date == today
        is_past = day_date < today
        is_blocked = day_date in blocked_dates
        is_weekend = day_of_week >= 5  # Saturday/Sunday

        # Get config for this day (day_of_week in DB is 0-6 for Mon-Sun)
        config = slot_configs.get(day_of_week)

        if is_blocked or is_weekend or not config:
            # No slots available
            days.append(DaySlotSummary(
                date=day_date.isoformat(),
                day_name=day_names_es[day_of_week],
                day_number=day_date.day,
                is_today=is_today,
                is_past=is_past,
                is_blocked=is_blocked,
                total_slots=0,
                booked_slots=0,
                available_slots=0,
                fill_percentage=0,
                status="closed"
            ))
            continue

        # Calculate total slots for the day
        start = config['start_time']
        end = config['end_time']
        duration = config['duration']
        max_per_slot = config['max_per_slot']

        # Count time slots in the day
        start_minutes = start.hour * 60 + start.minute
        end_minutes = end.hour * 60 + end.minute
        num_slots = (end_minutes - start_minutes) // duration

        total_day_capacity = num_slots * max_per_slot
        booked = bookings_by_date.get(day_date, 0)
        available = max(0, total_day_capacity - booked)

        fill_pct = (booked / total_day_capacity * 100) if total_day_capacity > 0 else 0

        # Determine status
        if is_past:
            status = "closed"
        elif available == 0:
            status = "full"
        elif fill_pct >= 80:
            status = "limited"
        else:
            status = "available"

        days.append(DaySlotSummary(
            date=day_date.isoformat(),
            day_name=day_names_es[day_of_week],
            day_number=day_date.day,
            is_today=is_today,
            is_past=is_past,
            is_blocked=False,
            total_slots=total_day_capacity,
            booked_slots=booked,
            available_slots=available,
            fill_percentage=round(fill_pct, 1),
            status=status
        ))

        if not is_past:
            total_available += available
            total_booked += booked
            total_capacity += total_day_capacity

    return CalendarSlotsWidgetResponse(
        week_start=week_start.isoformat(),
        week_end=week_end.isoformat(),
        entity_code=entity_code,
        location=selected_location,
        locations_available=locations_available,
        days=days,
        total_available=total_available,
        total_booked=total_booked,
        total_capacity=total_capacity
    )


# ═══════════════════════════════════════════════════════════════
# PHASE 5.3: APPOINTMENTS PAGE ENDPOINTS
# ═══════════════════════════════════════════════════════════════

class SlotTimeDetail(BaseModel):
    """Individual time slot with availability"""
    time: str  # HH:MM format
    available: int
    booked: int
    capacity: int
    is_available: bool


class DaySlotDetail(BaseModel):
    """Day with detailed time slots"""
    date: str
    day_name: str
    day_number: int
    is_today: bool = False
    is_past: bool = False
    is_blocked: bool = False
    slots: List[SlotTimeDetail] = []
    total_available: int = 0
    total_booked: int = 0
    total_capacity: int = 0


class SlotsCalendarResponse(BaseModel):
    """Detailed slots calendar for scheduling"""
    week_start: str
    week_end: str
    entity_code: str
    location: Optional[LocationInfo] = None
    locations_available: List[LocationInfo] = []
    days: List[DaySlotDetail]
    total_available: int = 0
    total_capacity: int = 0


class TodayAppointmentDetail(BaseModel):
    """Detailed appointment for today view"""
    id: str
    request_id: str
    reference: str
    workflow_code: str
    citizen_name: str
    citizen_email: Optional[str] = None
    citizen_phone: Optional[str] = None
    appointment_time: str
    status: str
    location_name: str
    location_id: str
    notes: Optional[str] = None
    created_at: str


class TodayAppointmentsListResponse(BaseModel):
    """Today's appointments list"""
    date: str
    entity_code: str
    location: Optional[LocationInfo] = None
    appointments: List[TodayAppointmentDetail]
    total: int
    completed: int
    pending: int
    cancelled: int


class AgentBookingRequest(BaseModel):
    """Agent booking for citizen"""
    request_id: UUID = Field(..., description="Service request ID")
    entity_location_id: UUID = Field(..., description="Location ID")
    appointment_date: date = Field(..., description="Appointment date")
    appointment_time: time = Field(..., description="Appointment time")


class AgentBookingResponse(BaseModel):
    """Agent booking response"""
    success: bool
    reservation_id: Optional[str] = None
    appointment_date: Optional[str] = None
    appointment_time: Optional[str] = None
    location_name: Optional[str] = None
    error: Optional[str] = None


class RescheduleRequest(BaseModel):
    """Reschedule appointment request"""
    new_date: date = Field(..., description="New appointment date")
    new_time: time = Field(..., description="New appointment time")
    reason: Optional[str] = Field(None, max_length=500, description="Reason for rescheduling")


class RescheduleResponse(BaseModel):
    """Reschedule response"""
    success: bool
    old_date: Optional[str] = None
    old_time: Optional[str] = None
    new_date: Optional[str] = None
    new_time: Optional[str] = None
    error: Optional[str] = None


@router.get(
    "/appointments/today-list",
    response_model=TodayAppointmentsListResponse,
    summary="Get today's appointments for agent view"
)
async def get_today_appointments_list(
    entity_code: str = Query(..., description="Entity code"),
    location_id: Optional[UUID] = Query(None, description="Filter by location"),
    agent_ctx: AgentContext = Depends(get_agent_context),
    db=Depends(get_database),
    _=Depends(permission_required("service_request.view"))
):
    """
    Get detailed list of today's appointments for the agent's entity.
    Used in the "Aujourd'hui" tab of appointments page.
    """
    today = date.today()

    conn = db
    # Get entity locations (scoped by agent site)
    locations_available = await _get_scoped_locations(conn, entity_code, agent_ctx)

    # Determine selected location
    selected_location = None
    entity_location_id = None
    if location_id:
        for loc in locations_available:
            if loc.id == str(location_id):
                selected_location = loc
                entity_location_id = location_id
                break
    elif locations_available:
        selected_location = locations_available[0]
        entity_location_id = UUID(selected_location.id)

    # Build query for today's appointments
    query = """
        SELECT
            ar.id::text as reservation_id,
            ar.service_request_id::text as request_id,
            sr.reference,
            sr.workflow_code,
            ar.appointment_time::text,
            ar.status,
            ar.completion_notes as notes,
            ar.created_at,
            el.id::text as location_id,
            el.location_name,
            u.first_name,
            u.last_name,
            u.email,
            u.phone_number
        FROM appointment_reservations ar
        JOIN entity_locations el ON ar.entity_location_id = el.id
        JOIN service_requests sr ON ar.service_request_id = sr.id
        JOIN users u ON sr.user_id = u.id
        WHERE el.entity_code = $1
          AND ar.appointment_date = $2
          AND ar.status != 'expired'
    """
    params = [entity_code, today]

    if entity_location_id:
        query += " AND ar.entity_location_id = $3"
        params.append(entity_location_id)

    query += " ORDER BY ar.appointment_time ASC"

    rows = await conn.fetch(query, *params)

    # Build response
    appointments = []
    completed = 0
    pending = 0
    cancelled = 0

    for row in rows:
        status = row['status']
        if status == 'completed':
            completed += 1
        elif status == 'cancelled':
            cancelled += 1
        else:
            pending += 1

        appointments.append(TodayAppointmentDetail(
            id=row['reservation_id'],
            request_id=row['request_id'],
            reference=row['reference'] or '',
            workflow_code=row['workflow_code'] or '',
            citizen_name=f"{row['first_name'] or ''} {row['last_name'] or ''}".strip() or 'N/A',
            citizen_email=row['email'],
            citizen_phone=row['phone_number'],
            appointment_time=row['appointment_time'],
            status=status,
            location_name=row['location_name'],
            location_id=row['location_id'],
            notes=row['notes'],
            created_at=row['created_at'].isoformat()
        ))

    return TodayAppointmentsListResponse(
        date=today.isoformat(),
        entity_code=entity_code,
        location=selected_location,
        appointments=appointments,
        total=len(appointments),
        completed=completed,
        pending=pending,
        cancelled=cancelled
    )


@router.get(
    "/appointments/slots-detailed",
    response_model=SlotsCalendarResponse,
    summary="Get detailed slots calendar for scheduling"
)
async def get_slots_detailed(
    entity_code: str = Query(..., description="Entity code"),
    week_offset: int = Query(0, description="Week offset (0=current, 1=next, -1=prev)"),
    location_id: Optional[UUID] = Query(None, description="Filter by location"),
    agent_ctx: AgentContext = Depends(get_agent_context),
    db=Depends(get_database),
    _=Depends(permission_required("service_request.view"))
):
    """
    Get detailed slots with individual time availability.
    Used in the "Planifier" tab for scheduling appointments.
    Shows each time slot with its availability count.
    """
    from datetime import timedelta

    DEFAULT_MAX_PER_SLOT = 2
    day_names_es = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']

    conn = db

    # Get entity locations (scoped by agent site)
    locations_available = await _get_scoped_locations(conn, entity_code, agent_ctx)

    # Determine selected location
    selected_location = None
    entity_location_id = None
    if location_id:
        for loc in locations_available:
            if loc.id == str(location_id):
                selected_location = loc
                entity_location_id = location_id
                break
    elif locations_available:
        selected_location = locations_available[0]
        entity_location_id = UUID(selected_location.id)

    # Calculate week boundaries
    today = date.today()
    week_start = today - timedelta(days=today.weekday())  # Monday
    week_start = week_start + timedelta(weeks=week_offset)
    week_end = week_start + timedelta(days=6)

    # Get slot configs
    slot_configs = {}
    config_rows = await conn.fetch("""
        SELECT
            day_of_week,
            start_time,
            end_time,
            slot_duration_minutes,
            max_appointments_per_slot
        FROM appointment_slot_configs
        WHERE entity_code = $1
          AND is_active = true
          AND (entity_location_id IS NULL OR entity_location_id = $2)
        ORDER BY day_of_week
    """, entity_code, entity_location_id)

    for row in config_rows:
        slot_configs[row['day_of_week']] = {
            'start_time': row['start_time'],
            'end_time': row['end_time'],
            'duration': row['slot_duration_minutes'] or 30,
            'max_per_slot': row['max_appointments_per_slot'] or DEFAULT_MAX_PER_SLOT
        }

    # Get blocked dates
    blocked_dates = set()
    blocked_rows = await conn.fetch("""
        SELECT blocked_date
        FROM appointment_blocked_dates
        WHERE (entity_code = $1 OR entity_code = 'ALL')
          AND blocked_date BETWEEN $2 AND $3
    """, entity_code, week_start, week_end)
    for row in blocked_rows:
        blocked_dates.add(row['blocked_date'])

    # Get booked appointments per slot
    bookings_query = """
        SELECT
            ar.appointment_date,
            ar.appointment_time,
            COUNT(*) as booked_count
        FROM appointment_reservations ar
        LEFT JOIN entity_locations el ON ar.entity_location_id = el.id
        WHERE el.entity_code = $1
          AND ar.appointment_date BETWEEN $2 AND $3
          AND ar.status NOT IN ('cancelled', 'expired')
    """
    params = [entity_code, week_start, week_end]

    if entity_location_id:
        bookings_query += " AND ar.entity_location_id = $4"
        params.append(entity_location_id)

    bookings_query += " GROUP BY ar.appointment_date, ar.appointment_time"

    bookings_rows = await conn.fetch(bookings_query, *params)

    # Build bookings lookup: {date: {time: count}}
    bookings_map = {}
    for row in bookings_rows:
        d = row['appointment_date']
        t = row['appointment_time']
        if d not in bookings_map:
            bookings_map[d] = {}
        bookings_map[d][t] = row['booked_count']

    # Build 7-day structure with time slots
    days = []
    grand_total_available = 0
    grand_total_capacity = 0

    for i in range(7):
        day_date = week_start + timedelta(days=i)
        day_of_week = day_date.weekday()
        is_today = day_date == today
        is_past = day_date < today
        is_blocked = day_date in blocked_dates
        is_weekend = day_of_week >= 5

        config = slot_configs.get(day_of_week)

        if is_blocked or is_weekend or not config:
            days.append(DaySlotDetail(
                date=day_date.isoformat(),
                day_name=day_names_es[day_of_week],
                day_number=day_date.day,
                is_today=is_today,
                is_past=is_past,
                is_blocked=is_blocked,
                slots=[],
                total_available=0,
                total_booked=0,
                total_capacity=0
            ))
            continue

        # Generate time slots for the day
        start = config['start_time']
        end = config['end_time']
        duration = config['duration']
        max_per_slot = config['max_per_slot']

        slots = []
        current_time = datetime.combine(day_date, start)
        end_time = datetime.combine(day_date, end)
        day_bookings = bookings_map.get(day_date, {})

        day_available = 0
        day_booked = 0
        day_capacity = 0

        while current_time < end_time:
            slot_time = current_time.time()
            booked = day_bookings.get(slot_time, 0)
            available = max(0, max_per_slot - booked)
            is_slot_available = available > 0 and not is_past

            slots.append(SlotTimeDetail(
                time=slot_time.strftime('%H:%M'),
                available=available if not is_past else 0,
                booked=booked,
                capacity=max_per_slot,
                is_available=is_slot_available
            ))

            if not is_past:
                day_available += available
                day_booked += booked
                day_capacity += max_per_slot

            current_time += timedelta(minutes=duration)

        days.append(DaySlotDetail(
            date=day_date.isoformat(),
            day_name=day_names_es[day_of_week],
            day_number=day_date.day,
            is_today=is_today,
            is_past=is_past,
            is_blocked=False,
            slots=slots,
            total_available=day_available,
            total_booked=day_booked,
            total_capacity=day_capacity
        ))

        grand_total_available += day_available
        grand_total_capacity += day_capacity

    return SlotsCalendarResponse(
        week_start=week_start.isoformat(),
        week_end=week_end.isoformat(),
        entity_code=entity_code,
        location=selected_location,
        locations_available=locations_available,
        days=days,
        total_available=grand_total_available,
        total_capacity=grand_total_capacity
    )


# ═══════════════════════════════════════════════════════════════
# ENDPOINT: MY ASSIGNED REQUESTS FOR APPOINTMENT
# Returns requests assigned to the current agent for the dropdown
# ═══════════════════════════════════════════════════════════════

@router.get(
    "/appointments/my-assigned",
    response_model=AssignedRequestsListResponse,
    summary="Get agent's assigned requests for appointment scheduling"
)
async def get_my_assigned_for_appointment(
    entity_code: str = Query(..., description="Entity code (e.g., CNEDOGE_PASAPORTE)"),
    include_with_appointment: bool = Query(False, description="Include requests that already have an appointment"),
    current_user: User = Depends(get_current_user),
    db=Depends(get_database),
    _=Depends(permission_required("service_request.view"))
):
    """
    Get service requests assigned to the current agent for appointment scheduling.
    Returns requests eligible for appointments (certain statuses) with info about existing appointments.
    """
    conn = db
    user_id = UUID(str(current_user.id))

    # Get entity's workflow codes
    entity = await conn.fetchrow("""
        SELECT workflow_codes FROM entities WHERE code = $1 AND is_active = true
    """, entity_code)

    if not entity:
        raise TranslatedException(ErrorCode.NOT_FOUND)

    # Handle workflow_codes - ensure it's a list (JSONB can sometimes return as string)
    workflow_codes = entity['workflow_codes'] or []
    if isinstance(workflow_codes, str):
        import json
        try:
            workflow_codes = json.loads(workflow_codes)
        except (json.JSONDecodeError, TypeError):
            workflow_codes = []
    if not isinstance(workflow_codes, list):
        workflow_codes = []

    # Statuses eligible for appointments
    eligible_statuses = ['PAYMENT_PENDING', 'PAID', 'SUBMITTED', 'UNDER_REVIEW', 'DOSSIER_VALIDE']

    # Query assigned requests with existing appointment info
    query = """
        SELECT
            sr.id::text,
            sr.reference,
            sr.workflow_code,
            sr.status,
            sr.created_at,
            COALESCE(u.full_name, CONCAT(u.first_name, ' ', u.last_name), u.email, 'N/A') as citizen_name,
            ar.id::text as reservation_id,
            ar.appointment_date::text as appointment_date,
            ar.appointment_time::text as appointment_time,
            ar.status as appointment_status,
            el.location_name
        FROM service_requests sr
        JOIN users u ON u.id = sr.user_id
        LEFT JOIN appointment_reservations ar ON ar.service_request_id = sr.id
            AND ar.status NOT IN ('cancelled', 'expired')
        LEFT JOIN entity_locations el ON el.id = ar.entity_location_id
        WHERE sr.workflow_code = ANY($1)
          AND sr.assigned_to = $2
          AND sr.status::text = ANY($3::text[])
    """

    params = [workflow_codes, user_id, eligible_statuses]

    # Filter by appointment status if needed
    if not include_with_appointment:
        query += " AND ar.id IS NULL"

    query += " ORDER BY sr.created_at DESC LIMIT 100"

    rows = await conn.fetch(query, *params)

    # Transform to response
    requests = []
    for row in rows:
        existing_appointment = None
        if row['reservation_id']:
            existing_appointment = ExistingAppointmentInfo(
                reservation_id=row['reservation_id'],
                date=row['appointment_date'],
                time=row['appointment_time'][:5] if row['appointment_time'] else '',
                location_name=row['location_name'],
                status=row['appointment_status']
            )

        requests.append(AssignedRequestForAppointment(
            id=row['id'],
            reference=row['reference'],
            citizen_name=row['citizen_name'],
            workflow_code=row['workflow_code'],
            status=row['status'],
            created_at=row['created_at'].isoformat(),
            existing_appointment=existing_appointment
        ))

    return AssignedRequestsListResponse(
        requests=requests,
        total=len(requests)
    )


@router.post(
    "/appointments/book-for-citizen",
    response_model=AgentBookingResponse,
    summary="Agent books appointment for citizen"
)
async def book_for_citizen(
    booking: AgentBookingRequest,
    agent_ctx: AgentContext = Depends(get_agent_context),
    db=Depends(get_database),
    _=Depends(permission_required("service_request.schedule_appointment"))
):
    """
    Agent books an appointment on behalf of a citizen.
    This bypasses the hold mechanism and creates a direct reservation.
    Triggers APPOINTMENT_BOOKED event for notifications.
    """
    conn = db

    # Security: must have an agent profile
    if not agent_ctx.has_profile:
        return AgentBookingResponse(
            success=False,
            error="Perfil de agente no encontrado"
        )

    # Verify service request exists and get details
    request = await conn.fetchrow("""
        SELECT
            sr.id,
            sr.user_id,
            sr.workflow_code,
            sr.status,
            sr.reference,
            u.email,
            u.phone_number,
            u.first_name,
            u.last_name,
            u.preferred_language
        FROM service_requests sr
        JOIN users u ON sr.user_id = u.id
        WHERE sr.id = $1
    """, booking.request_id)

    if not request:
        return AgentBookingResponse(
            success=False,
            error="Service request not found"
        )

    # Verify location exists
    location = await conn.fetchrow("""
        SELECT id, location_name, city, entity_code
        FROM entity_locations
        WHERE id = $1 AND is_active = true
    """, booking.entity_location_id)

    if not location:
        return AgentBookingResponse(
            success=False,
            error="Location not found or inactive"
        )

    # Site scope: only global supervisors can book on any site
    if not agent_ctx.has_global_scope and agent_ctx.entity_location_id:
        if booking.entity_location_id != agent_ctx.entity_location_id:
            return AgentBookingResponse(
                success=False,
                error="No autorizado: solo puede reservar citas en su sitio asignado"
            )

    # Check slot availability
    booked_count = await conn.fetchval("""
        SELECT COUNT(*)
        FROM appointment_reservations
        WHERE entity_location_id = $1
          AND appointment_date = $2
          AND appointment_time = $3
          AND status NOT IN ('cancelled', 'expired')
    """, booking.entity_location_id, booking.appointment_date, booking.appointment_time)

    # Get max capacity from config
    config = await conn.fetchrow("""
        SELECT max_appointments_per_slot
        FROM appointment_slot_configs
        WHERE entity_code = $1
          AND day_of_week = $2
          AND is_active = true
          AND (entity_location_id IS NULL OR entity_location_id = $3)
        LIMIT 1
    """, location['entity_code'], booking.appointment_date.weekday(), booking.entity_location_id)

    max_per_slot = (config['max_appointments_per_slot'] if config else None) or 2

    if booked_count >= max_per_slot:
        return AgentBookingResponse(
            success=False,
            error=f"Slot is full (capacity: {max_per_slot})"
        )

    # Check if request already has an appointment
    existing = await conn.fetchrow("""
        SELECT id FROM appointment_reservations
        WHERE service_request_id = $1
          AND status NOT IN ('cancelled', 'expired')
    """, booking.request_id)

    if existing:
        return AgentBookingResponse(
            success=False,
            error="Service request already has an active appointment. Use reschedule instead."
        )

    # Create reservation
    reservation_id = await conn.fetchval("""
        INSERT INTO appointment_reservations (
            service_request_id,
            entity_location_id,
            appointment_date,
            appointment_time,
            status,
            created_at
        ) VALUES ($1, $2, $3, $4, 'confirmed', NOW())
        RETURNING id::text
    """, booking.request_id, booking.entity_location_id,
        booking.appointment_date, booking.appointment_time)

    # Update service request with appointment info
    await conn.execute("""
        UPDATE service_requests
        SET cita_date = $2,
            cita_time = $3,
            cita_location = $4,
            updated_at = NOW()
        WHERE id = $1
    """, booking.request_id, booking.appointment_date,
        booking.appointment_time, location['location_name'])

    # Publish APPOINTMENT_BOOKED event
    try:
        EventBus.publish_nowait(
            EventType.APPOINTMENT_BOOKED,
            {
                "request_id": str(booking.request_id),
                "user_id": str(request['user_id']),
                "user_email": request['email'],
                "user_name": f"{request['first_name'] or ''} {request['last_name'] or ''}".strip(),
                "user_phone": request['phone_number'],
                "preferred_language": request.get('preferred_language', 'es'),
                "workflow_code": request['workflow_code'],
                "appointment_date": booking.appointment_date.isoformat(),
                "appointment_time": booking.appointment_time.strftime('%H:%M'),
                "location": location['location_name'],
                "booked_by_agent": True,
                "agent_id": str(agent_ctx.user_id),
                "timestamp": datetime.now().isoformat(),
            }
        )
        logger.info(f"APPOINTMENT_BOOKED event published for request {booking.request_id} (agent booking)")
    except Exception as e:
        logger.error(f"Failed to publish APPOINTMENT_BOOKED event: {e}")

    return AgentBookingResponse(
        success=True,
        reservation_id=reservation_id,
        appointment_date=booking.appointment_date.isoformat(),
        appointment_time=booking.appointment_time.strftime('%H:%M'),
        location_name=location['location_name']
    )


@router.patch(
    "/appointments/{reservation_id}/reschedule",
    response_model=RescheduleResponse,
    summary="Reschedule an existing appointment"
)
async def reschedule_appointment(
    reservation_id: UUID = Path(..., description="Appointment reservation ID"),
    reschedule: RescheduleRequest = Body(...),
    current_user: User = Depends(get_current_user),
    db=Depends(get_database),
    _=Depends(permission_required("service_request.update"))
):
    """
    Reschedule an existing appointment to a new date/time.
    Triggers APPOINTMENT_RESCHEDULED event for notifications.
    """
    conn = db
    # Get existing reservation
    existing = await conn.fetchrow("""
        SELECT
            ar.id,
            ar.service_request_id,
            ar.entity_location_id,
            ar.appointment_date,
            ar.appointment_time,
            ar.status,
            el.entity_code,
            el.location_name,
            sr.user_id,
            sr.workflow_code,
            u.email,
            u.phone_number,
            u.first_name,
            u.last_name,
            u.preferred_language
        FROM appointment_reservations ar
        JOIN entity_locations el ON ar.entity_location_id = el.id
        JOIN service_requests sr ON ar.service_request_id = sr.id
        JOIN users u ON sr.user_id = u.id
        WHERE ar.id = $1
    """, reservation_id)

    if not existing:
        return RescheduleResponse(
            success=False,
            error="Appointment not found"
        )

    if existing['status'] in ('cancelled', 'expired', 'completed'):
        return RescheduleResponse(
            success=False,
            error=f"Cannot reschedule appointment with status: {existing['status']}"
        )

    # Check new slot availability
    booked_count = await conn.fetchval("""
        SELECT COUNT(*)
        FROM appointment_reservations
        WHERE entity_location_id = $1
          AND appointment_date = $2
          AND appointment_time = $3
          AND status NOT IN ('cancelled', 'expired')
          AND id != $4
    """, existing['entity_location_id'], reschedule.new_date,
        reschedule.new_time, reservation_id)

    # Get max capacity
    config = await conn.fetchrow("""
        SELECT max_appointments_per_slot
        FROM appointment_slot_configs
        WHERE entity_code = $1
          AND day_of_week = $2
          AND is_active = true
          AND (entity_location_id IS NULL OR entity_location_id = $3)
        LIMIT 1
    """, existing['entity_code'], reschedule.new_date.weekday(),
        existing['entity_location_id'])

    max_per_slot = (config['max_appointments_per_slot'] if config else None) or 2

    if booked_count >= max_per_slot:
        return RescheduleResponse(
            success=False,
            error=f"New slot is full (capacity: {max_per_slot})"
        )

    old_date = existing['appointment_date']
    old_time = existing['appointment_time']

    # Update reservation
    await conn.execute("""
        UPDATE appointment_reservations
        SET appointment_date = $2,
            appointment_time = $3,
            notes = COALESCE(notes, '') || ' [Rescheduled: ' || COALESCE($4, 'no reason') || ']',
            updated_at = NOW()
        WHERE id = $1
    """, reservation_id, reschedule.new_date, reschedule.new_time, reschedule.reason)

    # Update service request
    await conn.execute("""
        UPDATE service_requests
        SET cita_date = $2,
            cita_time = $3,
            updated_at = NOW()
        WHERE id = $1
    """, existing['service_request_id'], reschedule.new_date, reschedule.new_time)

    # Publish APPOINTMENT_RESCHEDULED event
    try:
        EventBus.publish_nowait(
            EventType.APPOINTMENT_RESCHEDULED,
            {
                "request_id": str(existing['service_request_id']),
                "reservation_id": str(reservation_id),
                "user_id": str(existing['user_id']),
                "user_email": existing['email'],
                "user_name": f"{existing['first_name'] or ''} {existing['last_name'] or ''}".strip(),
                "user_phone": existing['phone_number'],
                "preferred_language": existing.get('preferred_language', 'es'),
                "workflow_code": existing['workflow_code'],
                "old_date": old_date.isoformat(),
                "old_time": old_time.strftime('%H:%M') if old_time else None,
                "new_date": reschedule.new_date.isoformat(),
                "new_time": reschedule.new_time.strftime('%H:%M'),
                "location": existing['location_name'],
                "rescheduled_by_agent": True,
                "agent_id": str(current_user.id),
                "reason": reschedule.reason,
                "timestamp": datetime.now().isoformat(),
            }
        )
        logger.info(f"APPOINTMENT_RESCHEDULED event published for reservation {reservation_id}")
    except Exception as e:
        logger.error(f"Failed to publish APPOINTMENT_RESCHEDULED event: {e}")

    return RescheduleResponse(
        success=True,
        old_date=old_date.isoformat(),
        old_time=old_time.strftime('%H:%M') if old_time else None,
        new_date=reschedule.new_date.isoformat(),
        new_time=reschedule.new_time.strftime('%H:%M')
    )


@router.get(
    "/appointments/{reservation_id}",
    summary="Get appointment details"
)
async def get_appointment_detail(
    reservation_id: UUID = Path(..., description="Appointment reservation ID"),
    current_user: User = Depends(get_current_user),
    db=Depends(get_database),
    _=Depends(permission_required("service_request.view"))
):
    """Get detailed appointment information."""
    conn = db
    row = await conn.fetchrow("""
        SELECT
            ar.id::text as reservation_id,
            ar.service_request_id::text as request_id,
            ar.appointment_date,
            ar.appointment_time,
            ar.status,
            ar.completion_notes as notes,
            ar.created_at,
            ar.updated_at,
            el.id::text as location_id,
            el.location_name,
            el.location_address,
            el.city,
            el.entity_code,
            sr.reference,
            sr.workflow_code,
            u.first_name,
            u.last_name,
            u.email,
            u.phone_number
        FROM appointment_reservations ar
        JOIN entity_locations el ON ar.entity_location_id = el.id
        JOIN service_requests sr ON ar.service_request_id = sr.id
        JOIN users u ON sr.user_id = u.id
        WHERE ar.id = $1
    """, reservation_id)

    if not row:
        raise TranslatedException(ErrorCode.NOT_FOUND)

    return {
        "id": row['reservation_id'],
        "request_id": row['request_id'],
        "reference": row['reference'],
        "workflow_code": row['workflow_code'],
        "citizen": {
            "name": f"{row['first_name'] or ''} {row['last_name'] or ''}".strip(),
            "email": row['email'],
            "phone": row['phone_number']
        },
        "appointment": {
            "date": row['appointment_date'].isoformat(),
            "time": row['appointment_time'].strftime('%H:%M') if row['appointment_time'] else None,
            "status": row['status']
        },
        "location": {
            "id": row['location_id'],
            "name": row['location_name'],
            "address": row['location_address'],
            "city": row['city'],
            "entity_code": row['entity_code']
        },
        "notes": row['notes'],
        "created_at": row['created_at'].isoformat(),
        "updated_at": row['updated_at'].isoformat() if row['updated_at'] else None
    }


@router.post(
    "/appointments/{reservation_id}/cancel",
    summary="Cancel an appointment reservation",
    description="Cancel an existing appointment reservation by reservation ID."
)
async def cancel_appointment_by_reservation(
    reservation_id: UUID = Path(..., description="Appointment reservation ID"),
    reason: Optional[str] = Body(None, embed=True),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("service_request.schedule_appointment"))
):
    # Find the reservation
    reservation = await db.fetchrow("""
        SELECT ar.id, ar.service_request_id, ar.status, ar.appointment_date, ar.appointment_time,
               el.location_name, sr.user_id, sr.workflow_code
        FROM appointment_reservations ar
        JOIN service_requests sr ON ar.service_request_id = sr.id
        LEFT JOIN entity_locations el ON ar.entity_location_id = el.id
        WHERE ar.id = $1
    """, reservation_id)

    if not reservation:
        raise TranslatedException(ErrorCode.NOT_FOUND)

    if reservation['status'] == 'cancelled':
        raise HTTPException(status_code=409, detail="Appointment already cancelled")

    # Cancel the reservation
    await db.execute("""
        UPDATE appointment_reservations
        SET status = 'cancelled',
            cancelled_at = NOW(),
            cancelled_by = $2,
            cancellation_reason = $3,
            updated_at = NOW()
        WHERE id = $1
    """, reservation_id, current_user.id, reason or "Agent cancellation")

    # Release corresponding hold if exists
    await db.execute("""
        UPDATE appointment_holds
        SET status = 'released', released_at = NOW(), updated_at = NOW()
        WHERE service_request_id = $1 AND status = 'confirmed'
    """, reservation['service_request_id'])

    # Record in history
    await db.execute("""
        INSERT INTO service_request_history
        (service_request_id, action, previous_status, new_status, performed_by, comment)
        VALUES ($1, 'appointment_cancelled', 'CITA_SCHEDULED', 'CITA_SCHEDULED', $2, $3)
    """, reservation['service_request_id'], current_user.id,
        reason or "Appointment cancelled by agent")

    # Publish cancellation event (non-blocking)
    try:
        user_info = await db.fetchrow(
            "SELECT id, email, first_name, last_name, phone_number, preferred_language FROM users WHERE id = $1",
            reservation['user_id']
        )
        if user_info:
            EventBus.publish_nowait(
                EventType.APPOINTMENT_CANCELLED,
                {
                    "request_id": str(reservation['service_request_id']),
                    "user_id": str(user_info['id']),
                    "user_email": user_info['email'],
                    "user_name": f"{user_info['first_name']} {user_info['last_name']}",
                    "user_phone": user_info['phone_number'],
                    "preferred_language": user_info['preferred_language'] or 'es',
                    "workflow_code": reservation['workflow_code'],
                    "appointment_date": str(reservation['appointment_date']),
                    "appointment_time": str(reservation['appointment_time']) if reservation['appointment_time'] else None,
                    "location": reservation['location_name'],
                    "reason": reason or "Agent cancellation",
                    "timestamp": datetime.now().isoformat(),
                }
            )
    except Exception as e:
        logger.warning(f"Failed to publish APPOINTMENT_CANCELLED event: {e}")

    return {"message": "Appointment cancelled"}


@router.post(
    "/appointments/{reservation_id}/complete",
    summary="Mark appointment as completed",
    description="Mark an appointment as completed after the citizen has been attended."
)
async def complete_appointment_by_reservation(
    reservation_id: UUID = Path(..., description="Appointment reservation ID"),
    notes: Optional[str] = Body(None, embed=True),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("service_request.schedule_appointment"))
):
    # Find the reservation
    reservation = await db.fetchrow("""
        SELECT ar.id, ar.service_request_id, ar.status,
               sr.status::text as sr_status
        FROM appointment_reservations ar
        JOIN service_requests sr ON ar.service_request_id = sr.id
        WHERE ar.id = $1
    """, reservation_id)

    if not reservation:
        raise TranslatedException(ErrorCode.NOT_FOUND)

    if reservation['status'] == 'completed':
        raise HTTPException(status_code=409, detail="Appointment already completed")

    if reservation['status'] == 'cancelled':
        raise HTTPException(status_code=409, detail="Cannot complete a cancelled appointment")

    # Mark as completed
    await db.execute("""
        UPDATE appointment_reservations
        SET status = 'completed',
            completed_at = NOW(),
            completed_by = $2,
            completion_notes = $3,
            updated_at = NOW()
        WHERE id = $1
    """, reservation_id, current_user.id, notes)

    # Update service request status — advance non-terminal statuses to COMPLETED
    sr_status = reservation['sr_status']
    if sr_status not in ('COMPLETED', 'REJECTED', 'CANCELLED', 'EXPIRED'):
        await db.execute("""
            UPDATE service_requests
            SET status = 'COMPLETED', updated_at = NOW()
            WHERE id = $1
        """, reservation['service_request_id'])

    # Record in history
    await db.execute("""
        INSERT INTO service_request_history
        (service_request_id, action, previous_status, new_status, performed_by, comment)
        VALUES ($1, 'appointment_completed', $2, 'COMPLETED', $3, $4)
    """, reservation['service_request_id'], sr_status, current_user.id,
        notes or "Appointment completed")

    return {"message": "Appointment completed"}


# ═══════════════════════════════════════════════════════════════
# SINGLE REQUEST HISTORY ENDPOINT
# ═══════════════════════════════════════════════════════════════


@router.get(
    "/{request_id}/history",
    response_model=HistoryListResponse,
    summary="Get service request history timeline",
    description="Returns the complete history/audit trail for a service request"
)
async def get_request_history(
    request_id: UUID = Path(..., description="Service request ID"),
    action_type: Optional[HistoryActionType] = Query(
        None,
        description="Filter by action type"
    ),
    from_date: Optional[date] = Query(None, description="Filter from date"),
    to_date: Optional[date] = Query(None, description="Filter to date"),
    include_system: bool = Query(True, description="Include system actions"),
    include_ocr: bool = Query(True, description="Include OCR processing logs"),
    include_assignments: bool = Query(True, description="Include assignment history"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db=Depends(get_database),
    _=Depends(permission_required("service_request.view"))
):
    """
    Get the complete history timeline for a service request.

    Returns all recorded events including:
    - Status changes
    - Document uploads
    - Agent assignments
    - Appointment scheduling
    - Verification updates
    - Payment events

    Events are ordered by date descending (most recent first).
    """
    conn = db
    user_id = UUID(str(current_user.id))

    # Get service request with history summary
    request_data = await service_request_repository.get_request_with_history_summary(
        conn, request_id
    )

    if not request_data:
        raise TranslatedException(ErrorCode.REQUEST_NOT_FOUND)

    # Access control: non-supervisor agents can only see history of requests assigned to them
    has_view_all = await conn.fetchval("""
        SELECT EXISTS (
            SELECT 1 FROM users u
            JOIN role_permissions rp ON rp.role_id = u.role_id
            JOIN permissions p ON p.id = rp.permission_id
            WHERE u.id = $1 AND p.name = 'service_request.view_all' AND rp.granted = true
            UNION
            SELECT 1 FROM user_permissions up
            JOIN permissions p ON p.id = up.permission_id
            WHERE up.user_id = $1 AND p.name = 'service_request.view_all' AND up.granted = true
        )
    """, user_id) or False

    if not has_view_all:
        assigned_to = request_data.get("assigned_to")
        is_direct_assignee = assigned_to is not None and UUID(str(assigned_to)) == user_id

        # Bundle SRs have split payments assigned to different entities.
        # An agent may not be the SR's assigned_to but still have a
        # service_payment assigned to them on this SR.
        is_split_assignee = False
        if not is_direct_assignee:
            is_split_assignee = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT 1 FROM service_payments sp
                    JOIN agent_profiles ap ON ap.id::text = sp.assigned_agent_id
                    WHERE sp.service_request_id = $1
                      AND ap.user_id = $2
                )
            """, request_id, user_id) or False

        if not is_direct_assignee and not is_split_assignee:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view history of requests assigned to you"
            )

    # Build filters
    action_types = [action_type.value] if action_type else None
    from_date_str = from_date.isoformat() if from_date else None
    to_date_str = to_date.isoformat() + "T23:59:59" if to_date else None

    # Get history entries
    offset = (page - 1) * page_size
    entries, total = await service_request_repository.get_request_history(
        db=conn,
        request_id=request_id,
        action_types=action_types,
        from_date=from_date_str,
        to_date=to_date_str,
        include_system=include_system,
        include_ocr=include_ocr,
        include_assignments=include_assignments,
        limit=page_size,
        offset=offset
    )

    # Transform entries to response model
    history_entries = []
    for entry in entries:
        performer = None
        if entry.get("performed_by"):
            pb = entry["performed_by"]
            performer = PerformerInfo(
                user_id=pb.get("user_id"),
                full_name=pb.get("full_name"),
                email=pb.get("email"),
                role=pb.get("role"),
                is_system=pb.get("is_system", False)
            )

        # Parse source to enum
        source_str = entry.get("source")
        entry_source = None
        if source_str:
            try:
                entry_source = HistoryEntrySource(source_str)
            except ValueError:
                entry_source = None

        history_entries.append(HistoryEntry(
            id=entry["id"],
            action=entry["action"],
            action_source=None,  # Can be added later
            source=entry_source,
            previous_status=entry.get("previous_status"),
            new_status=entry.get("new_status"),
            details=entry.get("details", {}),
            comment=entry.get("comment"),
            performed_by=performer,
            performed_at=entry["performed_at"],
            ip_address=entry.get("ip_address")
        ))

    return HistoryListResponse(
        request_id=request_id,
        reference=request_data.get("reference", ""),
        workflow_code=request_data.get("workflow_code", ""),
        solicitud_type=request_data.get("solicitud_type"),
        citizen_name=request_data.get("citizen_name", "N/A"),
        current_status=request_data.get("status", ""),
        entries=history_entries,
        total=total,
        page=page,
        page_size=page_size,
        total_status_changes=request_data.get("total_status_changes", 0),
        total_documents=request_data.get("total_documents", 0),
        total_assignments=request_data.get("total_assignments", 0),
        first_action_at=request_data.get("first_action_at"),
        last_action_at=request_data.get("last_action_at")
    )


# ═══════════════════════════════════════════════════════════════
# HISTORY EXPORT ENDPOINTS
# ═══════════════════════════════════════════════════════════════

from fastapi.responses import StreamingResponse
from ..services.history_export_service import history_export_service


@router.get(
    "/{request_id}/history/export",
    summary="Export service request history",
    description="Export the history timeline as CSV or PDF"
)
async def export_request_history(
    request_id: UUID = Path(..., description="Service request ID"),
    format: str = Query("csv", description="Export format: csv or pdf"),
    include_ocr: bool = Query(True, description="Include OCR processing logs"),
    include_assignments: bool = Query(True, description="Include assignment history"),
    current_user: User = Depends(get_current_user),
    db=Depends(get_database),
    _=Depends(permission_required("service_request.view"))
):
    """
    Export the complete history timeline for a service request.

    Supports:
    - CSV format (Excel compatible with UTF-8 BOM)
    - PDF format (formatted timeline document)
    """
    conn = db
    user_id = UUID(str(current_user.id))

    # Get service request info
    request_data = await service_request_repository.get_request_with_history_summary(
        conn, request_id
    )

    if not request_data:
        raise TranslatedException(ErrorCode.REQUEST_NOT_FOUND)

    # Access control: non-supervisor agents can only export history of requests assigned to them
    has_view_all = await conn.fetchval("""
        SELECT EXISTS (
            SELECT 1 FROM users u
            JOIN role_permissions rp ON rp.role_id = u.role_id
            JOIN permissions p ON p.id = rp.permission_id
            WHERE u.id = $1 AND p.name = 'service_request.view_all' AND rp.granted = true
            UNION
            SELECT 1 FROM user_permissions up
            JOIN permissions p ON p.id = up.permission_id
            WHERE up.user_id = $1 AND p.name = 'service_request.view_all' AND up.granted = true
        )
    """, user_id) or False

    if not has_view_all:
        assigned_to = request_data.get("assigned_to")
        is_direct_assignee = assigned_to is not None and UUID(str(assigned_to)) == user_id

        is_split_assignee = False
        if not is_direct_assignee:
            is_split_assignee = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT 1 FROM service_payments sp
                    JOIN agent_profiles ap ON ap.id::text = sp.assigned_agent_id
                    WHERE sp.service_request_id = $1
                      AND ap.user_id = $2
                )
            """, request_id, user_id) or False

        if not is_direct_assignee and not is_split_assignee:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only export history of requests assigned to you"
            )

    # Get all history entries (no pagination for export)
    entries, total = await service_request_repository.get_request_history(
        db=conn,
        request_id=request_id,
        include_ocr=include_ocr,
        include_assignments=include_assignments,
        limit=1000,  # Reasonable limit for export
        offset=0
    )

    # Prepare request info
    request_info = {
        "reference": request_data.get("reference", ""),
        "workflow_code": request_data.get("workflow_code", ""),
        "citizen_name": request_data.get("citizen_name", "N/A"),
        "current_status": request_data.get("status", ""),
    }

    # Generate export based on format
    if format.lower() == "pdf":
        try:
            content = await history_export_service.export_history_pdf(entries, request_info)
            filename = f"historial_{request_info['reference']}.pdf"
            media_type = "application/pdf"
        except RuntimeError as e:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail=str(e)
            )
    else:
        # Default to CSV
        content = await history_export_service.export_history_csv(entries, request_info)
        filename = f"historial_{request_info['reference']}.csv"
        media_type = "text/csv; charset=utf-8"

    return StreamingResponse(
        iter([content]),
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(content)),
        }
    )


# ═══════════════════════════════════════════════════════════════
# WIDGET: RECENT ACTIVITY
# Shows recent actions performed by the current agent
# ═══════════════════════════════════════════════════════════════

class RecentActivityItem(BaseModel):
    """A single recent activity entry"""
    id: str
    action_type: str
    item_type: str = "service_request"
    reference: str
    created_at: str


@router.get(
    "/dashboard/widgets/recent-activity",
    response_model=List[RecentActivityItem],
    summary="Get recent actions by current agent"
)
async def get_recent_activity_widget(
    limit: int = Query(5, ge=1, le=20, description="Number of recent actions to return"),
    current_user: User = Depends(get_current_user),
    db=Depends(get_database),
    _=Depends(permission_required("service_request.view"))
):
    """
    Get the most recent actions performed by the current agent
    from service_request_history.
    """
    user_id = UUID(str(current_user.id))

    rows = await db.fetch("""
        SELECT
            h.id::text AS id,
            h.action AS action_type,
            COALESCE(sr.reference, 'REQ-?') AS reference,
            h.performed_at
        FROM service_request_history h
        LEFT JOIN service_requests sr ON sr.id = h.service_request_id
        WHERE h.performed_by = $1
        ORDER BY h.performed_at DESC
        LIMIT $2
    """, user_id, limit)

    return [
        RecentActivityItem(
            id=row["id"],
            action_type=row["action_type"],
            reference=row["reference"],
            created_at=row["performed_at"].isoformat() if row["performed_at"] else "",
        )
        for row in rows
    ]
