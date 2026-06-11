"""
Agent Queue Service for Service Requests.

Integrates service_requests with the agent_work_queue system.
Enables agents to receive, process, and manage service requests.

Routes by entity_code (direct) instead of ministry_id (indirect).
Priority scores from workflows.priority_weight (DB) instead of hardcoded dicts.
"""
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import asyncpg
from loguru import logger

from app.config import get_settings
from ..workflows.workflow_interface import PredefinedWorkflow

# All workflows are now v2 (PredefinedWorkflow)
AnyWorkflow = PredefinedWorkflow


class AgentQueueService:
    """
    Service for managing service_requests in the agent work queue.

    This service bridges the service_requests module with the agents module,
    allowing service requests to be processed through the same queue as declarations.

    Routing: entity_code direct (migration 131).
    Priority: workflows.priority_weight (migration 131).
    Constants: from Settings (config.py).
    """

    # Item type identifier for service_requests in agent_work_queue
    ITEM_TYPE = "service_request"

    def __init__(self):
        settings = get_settings()
        self.DEFAULT_SLA_HOURS = settings.QUEUE_DEFAULT_SLA_HOURS
        self.ESCALATION_BOOST = settings.QUEUE_ESCALATION_BOOST
        self.SLA_WARNING_HOURS = settings.QUEUE_SLA_WARNING_HOURS

    async def add_to_queue(
        self,
        db: asyncpg.Connection,
        service_request_id: UUID,
        workflow_code: str,
        entity_code: str,
        workflow_instance: Optional[AnyWorkflow] = None,
        priority_boost: int = 0
    ) -> Dict[str, Any]:
        """
        Add a service_request to the agent work queue.

        Called when a service_request transitions to SUBMITTED status.

        Args:
            db: Database connection
            service_request_id: The service request ID
            workflow_code: The workflow code (e.g., PASAPORTE_NUEVO)
            entity_code: The responsible entity code (e.g., CNEDOGE_PASAPORTE)
            workflow_instance: Optional workflow instance for custom settings
            priority_boost: Additional priority points

        Returns:
            The created queue item
        """
        # Calculate priority score from workflows.priority_weight (DB)
        priority_score = await self._calculate_priority(
            db=db,
            workflow_code=workflow_code,
            workflow_instance=workflow_instance,
            priority_boost=priority_boost
        )

        # Calculate complexity score (for predictive escalation routing)
        complexity_score = await self._calculate_complexity(
            db=db,
            service_request_id=service_request_id,
            workflow_code=workflow_code,
        )

        # Calculate SLA deadline
        sla_deadline = await self._calculate_sla_deadline(
            db=db,
            workflow_code=workflow_code,
            workflow_instance=workflow_instance
        )

        # Check if already in queue (active or waiting for documents)
        existing = await db.fetchrow("""
            SELECT id, status, assigned_to FROM agent_work_queue
            WHERE item_type = $1 AND item_id = $2
            AND status NOT IN ('completed', 'cancelled')
        """, self.ITEM_TYPE, service_request_id)

        if existing:
            # If waiting_documents → reactivate same entry (same agent, SLA preserved)
            if existing['status'] == 'waiting_documents':
                await db.execute("""
                    UPDATE agent_work_queue
                    SET status = 'assigned', updated_at = NOW()
                    WHERE id = $1
                """, existing['id'])
                logger.info(
                    f"Service request {service_request_id} reactivated in queue "
                    f"(was waiting_documents, same agent {existing['assigned_to']})"
                )
            else:
                logger.warning(
                    f"Service request {service_request_id} already in queue: {existing['id']}"
                )
            return await self._get_queue_item(db, existing['id'])

        # Insert into queue with entity_code (direct routing)
        row = await db.fetchrow("""
            INSERT INTO agent_work_queue (
                item_type,
                item_id,
                entity_code,
                declaration_type,
                priority_score,
                complexity_score,
                sla_deadline,
                status,
                created_at,
                updated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, 'pending', NOW(), NOW())
            RETURNING *
        """, self.ITEM_TYPE, service_request_id, entity_code,
            workflow_code, int(priority_score), complexity_score, sla_deadline)

        logger.info(
            f"Added service_request {service_request_id} to queue. "
            f"Entity: {entity_code}, Priority: {priority_score}, SLA: {sla_deadline}"
        )

        return dict(row)

    async def _calculate_priority(
        self,
        db: asyncpg.Connection,
        workflow_code: str,
        workflow_instance: Optional[AnyWorkflow],
        priority_boost: int,
        created_at: Optional[datetime] = None
    ) -> Decimal:
        """
        Calculate priority score for the queue item.

        Reads priority_weight directly from workflows table (migration 131).
        Includes age-based boost (ported from legacy assignment_service).
        """
        settings = get_settings()

        # Get workflow info from database
        workflow = await db.fetchrow("""
            SELECT priority_weight, sla_hours
            FROM workflows
            WHERE code = $1
        """, workflow_code)

        base_score = Decimal("50")  # Default

        if workflow:
            # Use priority_weight from DB (set per-category by migration 131)
            pw = workflow.get('priority_weight')
            if pw is not None:
                base_score = Decimal(str(pw))

            # Higher priority for shorter SLAs
            sla_hours = workflow.get('sla_hours', self.DEFAULT_SLA_HOURS)
            if sla_hours <= 24:
                base_score += Decimal("20")
            elif sla_hours <= 48:
                base_score += Decimal("10")

        # Age-based boost: older items get higher priority
        # Ported from legacy agents/services/assignment_service.calculate_priority_score()
        if created_at:
            age_hours = (datetime.now(timezone.utc) - created_at).total_seconds() / 3600
            if age_hours > 72:
                base_score += Decimal(str(settings.QUEUE_AGE_BOOST_72H))
            elif age_hours > 48:
                base_score += Decimal(str(settings.QUEUE_AGE_BOOST_48H))
            elif age_hours > 24:
                base_score += Decimal(str(settings.QUEUE_AGE_BOOST_24H))

        # Check workflow instance for custom priority override
        if workflow_instance is not None:
            custom_priority = getattr(workflow_instance, 'queue_priority', None)
            if custom_priority is not None:
                base_score = Decimal(str(custom_priority))

        # Add boost
        base_score += Decimal(str(priority_boost))

        return base_score

    async def _calculate_complexity(
        self,
        db: asyncpg.Connection,
        service_request_id: UUID,
        workflow_code: str,
    ) -> int:
        """Compute complexity_score from real signals (not administrative priority_level).

        Formula (0-100):
          - workflow_weight (30%): priority_weight from workflows table
          - doc_count (30%): number of uploaded documents (more docs = more complex)
          - amount_tier (40%): payment amount tiers (higher amount = more scrutiny)

        Used by predictive escalation in auto_assignment_service._score_and_select()
        to avoid routing complex items to underperforming agents.
        """
        row = await db.fetchrow("""
            SELECT
                COALESCE(w.priority_weight, 50) AS wf_weight,
                (SELECT COUNT(*) FROM service_request_documents srd
                 WHERE srd.service_request_id = $1) AS doc_count,
                COALESCE(sp.total_amount, 0) AS amount
            FROM workflows w
            LEFT JOIN service_payments sp ON sp.service_request_id = $1
                AND sp.status NOT IN ('cancelled', 'failed')
            WHERE w.code = $2
            LIMIT 1
        """, service_request_id, workflow_code)

        if not row:
            return 50  # Default mid-range

        # Workflow weight component (30%): priority_weight 0-100 → 0-30
        wf_score = float(row['wf_weight']) * 0.3

        # Document count component (30%): more docs = more complex, capped at 10
        doc_score = min(int(row['doc_count']), 10) * 3.0  # Max 30pts

        # Payment amount tier component (40%): higher amount = more scrutiny
        amount = float(row['amount'])
        if amount > 500000:
            amount_score = 40.0
        elif amount > 100000:
            amount_score = 30.0
        elif amount > 50000:
            amount_score = 20.0
        elif amount > 10000:
            amount_score = 10.0
        else:
            amount_score = 5.0

        total = int(wf_score + doc_score + amount_score)
        return min(100, max(0, total))

    async def _calculate_sla_deadline(
        self,
        db: asyncpg.Connection,
        workflow_code: str,
        workflow_instance: Optional[AnyWorkflow]
    ) -> datetime:
        """Calculate SLA deadline for the service request."""

        sla_hours = self.DEFAULT_SLA_HOURS

        # Check database workflow
        db_sla = await db.fetchval("""
            SELECT sla_hours FROM workflows WHERE code = $1
        """, workflow_code)

        if db_sla:
            sla_hours = db_sla

        # Check workflow instance (takes precedence)
        if workflow_instance is not None:
            instance_sla = getattr(workflow_instance, 'sla_hours', None)
            if instance_sla is not None:
                sla_hours = instance_sla

        return datetime.now(timezone.utc) + timedelta(hours=sla_hours)

    async def _get_queue_item(
        self,
        db: asyncpg.Connection,
        queue_id: str
    ) -> Dict[str, Any]:
        """Get queue item by ID."""
        row = await db.fetchrow("""
            SELECT * FROM agent_work_queue WHERE id = $1
        """, queue_id)
        return dict(row) if row else {}

    async def get_pending_items(
        self,
        db: asyncpg.Connection,
        entity_code: Optional[str] = None,
        ministry_id: Optional[int] = None,
        entity_location_id: Optional[UUID] = None,
        limit: int = 1000,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get pending service_request items from the queue.

        Returns items ordered by priority (highest first) and creation time.

        Args:
            db: Database connection
            entity_code: Entity code filter (primary routing)
            ministry_id: Deprecated, kept for backward compatibility
            entity_location_id: Filter by specific site (NULL = show all for entity)
            limit: Maximum items to return (default: 1000 for agents to see all)
            offset: Offset for pagination
        """
        query = """
            SELECT
                q.*,
                sr.reference AS reference_number,
                sr.workflow_code,
                sr.status as request_status,
                sr.created_at as request_created_at,
                u.full_name as citizen_name,
                u.email as citizen_email
            FROM agent_work_queue q
            JOIN service_requests sr ON sr.id = q.item_id
            JOIN users u ON u.id = sr.user_id
            WHERE q.item_type = $1
            AND q.status = 'pending'
        """
        params: list = [self.ITEM_TYPE]
        param_idx = 2

        if entity_code:
            query += f" AND q.entity_code = ${param_idx}"
            params.append(entity_code)
            param_idx += 1

        if entity_location_id:
            # Show requests at this site + unrouted requests (NULL = legacy/no location)
            query += f" AND (sr.entity_location_id = ${param_idx} OR sr.entity_location_id IS NULL)"
            params.append(entity_location_id)
            param_idx += 1

        query += f"""
            ORDER BY q.priority_score DESC, q.created_at ASC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        params.extend([limit, offset])

        rows = await db.fetch(query, *params)
        return [dict(row) for row in rows]

    async def complete_item(
        self,
        db: asyncpg.Connection,
        queue_id: str,
        agent_id: str,
        result_status: str = "approved"
    ) -> Dict[str, Any]:
        """
        Mark a queue item as completed.

        Args:
            queue_id: The queue item ID
            agent_id: The completing agent ID
            result_status: The result (approved, rejected, etc.)
        """
        row = await db.fetchrow("""
            UPDATE agent_work_queue
            SET status = 'completed',
                completed_at = NOW(),
                completed_by = $2,
                updated_at = NOW()
            WHERE id = $1
            AND assigned_to = $2
            RETURNING *
        """, queue_id, agent_id)

        if not row:
            raise ValueError("Queue item not found or not assigned to this agent")

        logger.info(
            f"Completed queue item {queue_id} by agent {agent_id}. "
            f"Result: {result_status}"
        )

        # Feedback loop: record completion for multi-criteria scoring.
        # CRITICAL: wrapped in a SAVEPOINT so that any SQL error inside
        # feedback recording does NOT poison the outer transaction.
        # Without a savepoint, a PostgreSQL error (even caught by try-except)
        # marks the transaction as "aborted" and the final COMMIT silently
        # becomes a ROLLBACK — losing the approval status change.
        try:
            from app.modules.assignment.services.assignment_feedback_service import feedback_service
            processing_hours = None
            if row.get("assigned_at") and row.get("completed_at"):
                delta = row["completed_at"] - row["assigned_at"]
                processing_hours = delta.total_seconds() / 3600
            workflow_code = row.get("declaration_type")
            agent_profile_id = await db.fetchval(
                "SELECT id FROM agent_profiles WHERE user_id = $1 AND is_active = true",
                agent_id,
            )
            if agent_profile_id and workflow_code:
                async with db.transaction():  # SAVEPOINT when nested
                    await feedback_service.record_completion(
                        db, agent_profile_id, workflow_code,
                        processing_hours or 0,
                    )
        except Exception as e:
            logger.warning(f"Feedback recording failed (non-blocking): {e}")

        return dict(row)

    async def escalate_item(
        self,
        db: asyncpg.Connection,
        queue_id: str,
        agent_id: str,
        reason: str
    ) -> Dict[str, Any]:
        """
        Escalate a queue item.

        Increases priority by ESCALATION_BOOST (from settings) and marks for supervisor attention.
        """
        row = await db.fetchrow(f"""
            UPDATE agent_work_queue
            SET escalated = true,
                escalated_at = NOW(),
                escalated_by = $2,
                escalation_reason = $3,
                priority_score = priority_score + $4,
                status = 'pending',
                assigned_to = NULL,
                updated_at = NOW()
            WHERE id = $1
            RETURNING *
        """, queue_id, agent_id, reason, self.ESCALATION_BOOST)

        if not row:
            raise ValueError("Queue item not found")

        # Update service_request notes to track escalation
        await db.execute("""
            UPDATE service_requests
            SET notes = COALESCE(notes, '') || E'\n[ESCALATED] ' || $2,
                updated_at = NOW()
            WHERE id = $1
        """, row['item_id'], reason)

        logger.warning(
            f"Escalated queue item {queue_id}. Reason: {reason}"
        )

        # Feedback loop: record escalation for multi-criteria scoring
        # SAVEPOINT protects the outer transaction from feedback SQL errors
        try:
            from app.modules.assignment.services.assignment_feedback_service import feedback_service
            workflow_code = row.get("declaration_type")
            agent_profile_id = await db.fetchval(
                "SELECT id FROM agent_profiles WHERE user_id = $1 AND is_active = true",
                agent_id,
            )
            if agent_profile_id and workflow_code:
                async with db.transaction():  # SAVEPOINT when nested
                    await feedback_service.record_escalation(
                        db, agent_profile_id, workflow_code,
                    )
        except Exception as e:
            logger.warning(f"Feedback recording failed (non-blocking): {e}")

        return dict(row)

    async def get_agent_queue(
        self,
        db: asyncpg.Connection,
        agent_id: str,
        include_completed: bool = False,
        limit: int = 1000,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get all queue items assigned to an agent.

        Args:
            db: Database connection
            agent_id: The agent's user ID
            include_completed: Whether to include completed items
            limit: Maximum items to return (default: 1000 for agents to see all)
            offset: Offset for pagination
        """
        status_filter = "AND q.status IN ('assigned', 'pending') AND COALESCE(q.escalated, false) = false"
        if include_completed:
            status_filter = ""

        rows = await db.fetch(f"""
            SELECT
                q.*,
                sr.reference AS reference_number,
                sr.workflow_code,
                sr.status as request_status,
                sr.form_data,
                u.full_name as citizen_name
            FROM agent_work_queue q
            JOIN service_requests sr ON sr.id = q.item_id
            JOIN users u ON u.id = sr.user_id
            WHERE q.item_type = $1
            AND q.assigned_to = $2
            {status_filter}
            ORDER BY q.priority_score DESC, q.assigned_at DESC
            LIMIT $3 OFFSET $4
        """, self.ITEM_TYPE, agent_id, limit, offset)

        return [dict(row) for row in rows]

    async def get_queue_stats(
        self,
        db: asyncpg.Connection,
        entity_code: Optional[str] = None,
        ministry_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get queue statistics for an entity.
        """
        where_clause = "WHERE item_type = $1"
        params: list = [self.ITEM_TYPE]

        if entity_code:
            where_clause += " AND entity_code = $2"
            params.append(entity_code)

        stats = await db.fetchrow(f"""
            SELECT
                COUNT(*) FILTER (WHERE status = 'pending') as pending_count,
                COUNT(*) FILTER (WHERE status = 'assigned') as assigned_count,
                COUNT(*) FILTER (WHERE status = 'completed'
                                 AND completed_at > NOW() - INTERVAL '24 hours') as completed_today,
                COUNT(*) FILTER (WHERE escalated = true
                                 AND status != 'completed') as escalated_count,
                COUNT(*) FILTER (WHERE sla_deadline < NOW()
                                 AND status != 'completed') as sla_violations,
                AVG(EXTRACT(EPOCH FROM (completed_at - created_at)) / 3600)
                    FILTER (WHERE status = 'completed') as avg_processing_hours
            FROM agent_work_queue
            {where_clause}
        """, *params)

        return {
            "pending": stats['pending_count'] or 0,
            "assigned": stats['assigned_count'] or 0,
            "completed_today": stats['completed_today'] or 0,
            "escalated": stats['escalated_count'] or 0,
            "sla_violations": stats['sla_violations'] or 0,
            "avg_processing_hours": round(stats['avg_processing_hours'] or 0, 2)
        }

    async def check_sla_status(
        self,
        db: asyncpg.Connection,
        queue_id: str
    ) -> Dict[str, Any]:
        """
        Check SLA status for a queue item.
        Uses SLA_WARNING_HOURS from settings instead of hardcoded 6 hours.
        """
        row = await db.fetchrow("""
            SELECT
                id,
                sla_deadline,
                created_at,
                status,
                CASE
                    WHEN status = 'completed' THEN 'completed'
                    WHEN sla_deadline < NOW() THEN 'violated'
                    WHEN sla_deadline < NOW() + ($2 * interval '1 hour') THEN 'at_risk'
                    ELSE 'on_track'
                END as sla_status,
                EXTRACT(EPOCH FROM (sla_deadline - NOW())) / 3600 as hours_remaining
            FROM agent_work_queue
            WHERE id = $1
        """, queue_id, self.SLA_WARNING_HOURS)

        if not row:
            raise ValueError("Queue item not found")

        return {
            "queue_id": row['id'],
            "sla_deadline": row['sla_deadline'].isoformat() if row['sla_deadline'] else None,
            "status": row['sla_status'],
            "hours_remaining": round(row['hours_remaining'] or 0, 2)
        }

    async def recalculate_pending_priorities(
        self,
        db: asyncpg.Connection,
        entity_code: Optional[str] = None,
    ) -> int:
        """
        Recalculate priority scores for pending items based on age.

        IDEMPOTENT: Recalculates the full score (base + age boost) each run,
        not an incremental addition. Safe to call at any frequency.

        Formula: priority_score = workflows.priority_weight + SLA_boost + age_boost
        (Same as _calculate_priority but applied in batch via SQL.)

        Args:
            db: Database connection
            entity_code: Optional entity filter (None = all entities)

        Returns:
            Number of items updated
        """
        settings = get_settings()

        params: list = [
            self.ITEM_TYPE,
            settings.QUEUE_AGE_BOOST_72H,
            settings.QUEUE_AGE_BOOST_48H,
            settings.QUEUE_AGE_BOOST_24H,
            self.DEFAULT_SLA_HOURS,
        ]
        where_extra = ""
        param_idx = 6

        if entity_code:
            where_extra = f" AND q.entity_code = ${param_idx}"
            params.append(entity_code)
            param_idx += 1

        # Recalculate full score: base (priority_weight) + SLA boost + age boost
        result = await db.execute(f"""
            UPDATE agent_work_queue q
            SET priority_score = (
                COALESCE(w.priority_weight, 50)
                + CASE
                    WHEN COALESCE(w.sla_hours, $5) <= 24 THEN 20
                    WHEN COALESCE(w.sla_hours, $5) <= 48 THEN 10
                    ELSE 0
                END
                + CASE
                    WHEN q.created_at < NOW() - INTERVAL '72 hours' THEN $2
                    WHEN q.created_at < NOW() - INTERVAL '48 hours' THEN $3
                    WHEN q.created_at < NOW() - INTERVAL '24 hours' THEN $4
                    ELSE 0
                END
            ),
            updated_at = NOW()
            FROM workflows w
            WHERE w.code = q.declaration_type
            AND q.status = 'pending'
            AND q.item_type = $1
            AND q.created_at < NOW() - INTERVAL '24 hours'
            {where_extra}
        """, *params)

        count = int(result.split()[-1]) if result and 'UPDATE' in result else 0
        if count > 0:
            logger.info(f"Recalculated priorities for {count} pending queue items")
        return count

    async def remove_from_queue(
        self,
        db: asyncpg.Connection,
        service_request_id: UUID,
        reason: str = "cancelled"
    ) -> bool:
        """
        Remove a service_request from the queue.

        Used when a request is cancelled or no longer needs agent processing.
        """
        result = await db.execute("""
            UPDATE agent_work_queue
            SET status = 'cancelled',
                updated_at = NOW()
            WHERE item_type = $1
            AND item_id = $2
            AND status NOT IN ('completed', 'cancelled')
        """, self.ITEM_TYPE, service_request_id)

        removed = 'UPDATE 1' in result
        if removed:
            logger.info(f"Removed service_request {service_request_id} from queue. Reason: {reason}")

        return removed


# Singleton instance
agent_queue_service = AgentQueueService()
