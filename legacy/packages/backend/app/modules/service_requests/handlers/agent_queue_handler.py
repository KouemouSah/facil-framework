"""
Agent Queue Event Handler
=========================
Handles events related to payment completion and adds service requests
to the agent work queue for processing.

Business Logic:
- When a payment is COMPLETED (either via electronic payment or Treasury validation),
  the corresponding service_request should be added to agent_work_queue
- This ensures agents only see requests that have been PAID
- The agent can then process the dossier (validate documents, schedule appointments, etc.)
- After assignment, status transitions from PAID → SUBMITTED (visible in agent dashboard)

@module service_requests/handlers/agent_queue_handler
"""

import logging
from typing import Optional
from uuid import UUID

from app.core.events import EventBus, EventType, EventPayload
from app.database.connection import get_db_connection, release_db_connection

logger = logging.getLogger(__name__)


class AgentQueueEventHandler:
    """
    Event handler that adds service requests to agent work queue
    after payment is completed.

    This handler listens to:
    - PAYMENT_COMPLETED: Triggered when any payment (BANGE, cash, check) is completed

    When triggered:
    - Fetches the service_request details
    - Adds it to agent_work_queue with appropriate priority
    - Auto-assigns to entity agent via AutoAssignmentService
    - Transitions status: PAID → SUBMITTED
    """

    def __init__(self):
        """Initialize the agent queue event handler."""
        self._registered = False
        logger.info("AgentQueueEventHandler initialized")

    def register(self) -> None:
        """
        Register event handlers with the EventBus.
        Should be called once at application startup.
        """
        if self._registered:
            logger.warning("AgentQueueEventHandler already registered")
            return

        # Subscribe to payment completion event
        EventBus.subscribe(EventType.PAYMENT_COMPLETED, self.handle_payment_completed)
        logger.info("AgentQueueEventHandler: registered for PAYMENT_COMPLETED")

        self._registered = True

    async def handle_payment_completed(self, payload: EventPayload) -> None:
        """
        Handle PAYMENT_COMPLETED event — FALLBACK SAFETY NET.

        The primary path for entity agent assignment is now the assignment_outbox
        (transactional INSERT + cron processing). This EventBus handler only runs
        as a fallback if the outbox INSERT failed or for backward compatibility
        (e.g., BANGE processor still publishes this event).

        If an outbox entry already exists for this service_request, this handler
        skips processing (cron will handle it).
        """
        service_request_id = payload.get("service_request_id")
        payment_id = payload.get("payment_id")
        payment_method = payload.get("payment_method", "unknown")

        if not service_request_id:
            logger.warning(
                f"PAYMENT_COMPLETED event missing service_request_id: {payload}"
            )
            return

        logger.info(
            f"Processing PAYMENT_COMPLETED for service_request={service_request_id}, "
            f"payment={payment_id}, method={payment_method}"
        )

        conn = None
        try:
            # Get database connection
            conn = await get_db_connection()

            # Check if outbox already handles this SR (primary path)
            outbox_exists = await conn.fetchval("""
                SELECT 1 FROM assignment_outbox
                WHERE service_request_id = $1
                  AND status IN ('pending', 'processing', 'completed')
            """, UUID(service_request_id))

            if outbox_exists:
                logger.debug(
                    f"Outbox entry exists for {service_request_id}, "
                    f"skipping EventBus handler (cron will process)"
                )
                return

            logger.warning(
                f"No outbox entry for {service_request_id}, "
                f"running EventBus fallback handler"
            )

            # Import here to avoid circular imports
            from app.modules.service_requests.services.agent_queue_service import (
                agent_queue_service
            )

            # Fetch service request details
            sr = await conn.fetchrow("""
                SELECT
                    id,
                    reference,
                    workflow_code,
                    entity_code,
                    entity_location_id,
                    status,
                    payment_status,
                    assigned_to
                FROM service_requests
                WHERE id = $1
            """, UUID(service_request_id))

            if not sr:
                logger.error(
                    f"Service request not found: {service_request_id}"
                )
                return

            # Check if payment is actually completed
            if sr["payment_status"] != "completed":
                logger.warning(
                    f"Service request {sr['reference']} payment_status is "
                    f"'{sr['payment_status']}', expected 'completed'. Skipping queue addition."
                )
                return

            # Skip if already assigned (idempotency guard)
            if sr["assigned_to"] is not None and sr["status"] != "PAID":
                logger.info(
                    f"Service request {sr['reference']} already assigned "
                    f"(status={sr['status']}). Skipping duplicate processing."
                )
                return

            workflow_code = sr["workflow_code"]
            entity_code = sr["entity_code"]

            if not workflow_code or not entity_code:
                logger.error(
                    f"Service request {sr['reference']} missing workflow_code "
                    f"or entity_code. workflow_code={workflow_code}, entity_code={entity_code}"
                )
                return

            # Add to agent work queue
            queue_item = await agent_queue_service.add_to_queue(
                db=conn,
                service_request_id=UUID(service_request_id),
                workflow_code=workflow_code,
                entity_code=entity_code,
                priority_boost=0  # Standard priority, can be adjusted based on payment method
            )

            logger.info(
                f"Service request {sr['reference']} added to agent queue. "
                f"Queue item ID: {queue_item.get('id')}, "
                f"Priority: {queue_item.get('priority_score')}, "
                f"Entity: {entity_code}"
            )

            # Trigger auto-assignment using entity_code for deterministic routing
            # CRITICAL: entity_code (not workflow_code) determines the target entity.
            # For multi-entity workflows (e.g., RESIDENCIA handled by EXTRANJERIA + CNEDOGE),
            # workflow_code lookup is nondeterministic. entity_code is set at persist time
            # from PredefinedWorkflow.entity_code and is authoritative.
            from app.modules.assignment.services.auto_assignment_service import AutoAssignmentService

            auto_assignment_service = AutoAssignmentService()
            assignment = await auto_assignment_service.auto_assign_item(
                db=conn,
                item_id=UUID(service_request_id),
                item_type="service_request",
                item_data={
                    "workflow_code": workflow_code,
                    "entity_code": entity_code,
                },
                entity_type="entity",
                entity_id=None,
                priority_level=5,
                entity_code=entity_code,  # Deterministic: use entity_code, not workflow_code
                entity_location_id=sr["entity_location_id"],  # Site-based routing
            )

            if assignment:
                # Sync assigned_to on service_requests + agent_work_queue
                agent_user_id = await conn.fetchval(
                    "SELECT user_id FROM agent_profiles WHERE id = $1",
                    assignment.agent_profile_id
                )
                if agent_user_id:
                    await conn.execute("""
                        UPDATE service_requests
                        SET assigned_to = $1, assigned_at = NOW(), updated_at = NOW()
                        WHERE id = $2
                    """, agent_user_id, UUID(service_request_id))
                    # Sync agent_work_queue so make_decision + Pendientes/Completados work
                    await conn.execute("""
                        UPDATE agent_work_queue
                        SET assigned_to = $1, assigned_at = NOW(),
                            status = 'assigned', updated_at = NOW()
                        WHERE item_id = $2
                          AND item_type = 'service_request'
                          AND assigned_to IS NULL
                    """, agent_user_id, UUID(service_request_id))

                logger.info(
                    f"Service request {sr['reference']} auto-assigned to agent "
                    f"{assignment.agent_profile_id} (user {agent_user_id}) "
                    f"via PAYMENT_COMPLETED handler"
                )
            else:
                logger.warning(
                    f"No agent available for service request {sr['reference']} "
                    f"(entity: {entity_code}, workflow: {workflow_code})"
                )

            # Transition status: PAID → SUBMITTED (now ready for entity agent processing)
            # SUBMITTED is in ActionStatusMapping.PENDING → visible in agent dashboard
            # Transition even without agent so supervisors can see and manually assign
            await conn.execute("""
                UPDATE service_requests
                SET status = 'SUBMITTED',
                    submitted_at = NOW(),
                    updated_at = NOW()
                WHERE id = $1 AND status = 'PAID'
            """, UUID(service_request_id))

            logger.info(
                f"Service request {sr['reference']} status: PAID → SUBMITTED"
                + (f" (assigned to {assignment.agent_profile_id})" if assignment else " (no agent, pending manual assignment)")
            )

        except Exception as e:
            logger.error(
                f"Failed to add service request {service_request_id} to agent queue: {e}",
                exc_info=True
            )
        finally:
            if conn:
                await release_db_connection(conn)


# Global handler instance
_handler: Optional[AgentQueueEventHandler] = None


def register_agent_queue_handlers() -> AgentQueueEventHandler:
    """
    Register agent queue handlers with the EventBus.
    Should be called once at application startup.

    Returns:
        The registered AgentQueueEventHandler instance
    """
    global _handler
    if _handler is None:
        _handler = AgentQueueEventHandler()
        _handler.register()
    return _handler


async def repair_orphaned_paid_requests() -> int:
    """
    Self-healing: Find PAID requests that were never assigned to entity agents
    (due to missing PAYMENT_COMPLETED event before this fix) and re-publish the event.

    Called once at backend startup. Idempotent:
    - Skips requests already in agent_work_queue
    - Skips requests already assigned (assigned_to IS NOT NULL)
    - Resolves entity_code from entity_location_id or workflow_code if NULL

    Returns:
        Number of requests repaired
    """
    conn = None
    try:
        conn = await get_db_connection()

        # Find orphaned PAID requests (paid but never assigned to entity agent)
        orphans = await conn.fetch("""
            SELECT sr.id, sr.reference, sr.workflow_code, sr.entity_code,
                   sr.entity_location_id, sr.payment_status,
                   sp.id AS payment_id, sp.total_amount, sp.payment_method,
                   sr.user_id
            FROM service_requests sr
            JOIN service_payments sp ON sp.service_request_id = sr.id
                AND sp.status = 'completed'
            WHERE sr.status = 'PAID'
              AND sr.payment_status = 'completed'
              AND sr.assigned_to IS NULL
              AND NOT EXISTS (
                  SELECT 1 FROM agent_work_queue awq
                  WHERE awq.item_id = sr.id AND awq.item_type = 'service_request'
              )
              AND NOT EXISTS (
                  SELECT 1 FROM assignment_outbox ao
                  WHERE ao.service_request_id = sr.id
                    AND ao.status IN ('pending', 'processing')
              )
            ORDER BY sr.created_at ASC
        """)

        if not orphans:
            logger.info("Startup repair: no orphaned PAID requests found")
            return 0

        logger.warning(
            f"Startup repair: found {len(orphans)} orphaned PAID requests, repairing..."
        )

        repaired = 0
        for sr in orphans:
            try:
                entity_code = sr["entity_code"]

                # Resolve entity_code if NULL — try entity_location first, then workflow
                if not entity_code and sr["entity_location_id"]:
                    entity_code = await conn.fetchval(
                        "SELECT entity_code FROM entity_locations "
                        "WHERE id = $1 AND is_active = true",
                        sr["entity_location_id"]
                    )

                if not entity_code and sr["workflow_code"]:
                    entity_code = await conn.fetchval("""
                        SELECT code FROM entities
                        WHERE workflow_codes ? $1
                          AND is_active = true
                          AND entity_type = 'department'
                        LIMIT 1
                    """, sr["workflow_code"])

                if not entity_code:
                    logger.error(
                        f"Startup repair: cannot resolve entity_code for "
                        f"{sr['reference']}, skipping"
                    )
                    continue

                # Persist entity_code if it was NULL
                if not sr["entity_code"]:
                    await conn.execute(
                        "UPDATE service_requests SET entity_code = $1, "
                        "updated_at = NOW() WHERE id = $2",
                        entity_code, sr["id"]
                    )
                    logger.info(
                        f"Startup repair: set entity_code={entity_code} "
                        f"for {sr['reference']}"
                    )

                # Enqueue into assignment outbox (persistent, cron-processed)
                from app.modules.service_requests.services.assignment_outbox_service import (
                    assignment_outbox_service,
                )
                await assignment_outbox_service.enqueue(
                    db=conn,
                    service_request_id=sr["id"],
                    workflow_code=sr["workflow_code"],
                    entity_code=entity_code,
                    entity_location_id=sr["entity_location_id"],
                    payment_id=str(sr["payment_id"]) if sr["payment_id"] else None,
                    payment_method=sr["payment_method"] or "cash",
                )
                repaired += 1
                logger.info(
                    f"Startup repair: enqueued outbox for "
                    f"{sr['reference']} (entity={entity_code})"
                )

            except Exception as e:
                logger.error(
                    f"Startup repair: failed to repair {sr['reference']}: {e}",
                    exc_info=True
                )

        logger.info(
            f"Startup repair complete: {repaired}/{len(orphans)} requests repaired"
        )
        return repaired

    except Exception as e:
        logger.error(f"Startup repair failed: {e}", exc_info=True)
        return 0
    finally:
        if conn:
            await release_db_connection(conn)
