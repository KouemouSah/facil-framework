"""
Assignment Outbox Service
=========================
Implements the Transactional Outbox pattern for guaranteed delivery
of entity agent assignment events after payment completion.

Instead of fire-and-forget EventBus.publish_nowait(PAYMENT_COMPLETED),
the payment validation endpoint INSERTs into assignment_outbox in the
same DB transaction. A cron job (every 1 min) processes pending items.

Constants are read from Settings (config.py) for env-var configurability.

@module service_requests/services/assignment_outbox_service
"""

import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

import asyncpg

from app.config import get_settings

logger = logging.getLogger(__name__)


class AssignmentOutboxService:
    """
    Manages the assignment outbox for guaranteed delivery.

    Methods:
        enqueue()              - Insert outbox item (same txn as payment validation)
        process_pending_items() - Process pending items (cron, every 1 min)
        run_health_check()     - Detect orphans and stuck items (cron, every 5 min)
    """

    def __init__(self):
        settings = get_settings()
        self.RETRY_DELAYS_SECONDS = [
            int(x) for x in settings.OUTBOX_RETRY_DELAYS.split(",")
        ]
        self.BATCH_SIZE = settings.OUTBOX_BATCH_SIZE
        self.ORPHAN_THRESHOLD_MINUTES = settings.OUTBOX_ORPHAN_THRESHOLD_MINUTES
        self.STALE_PROCESSING_MINUTES = settings.OUTBOX_STALE_PROCESSING_MINUTES

    async def enqueue(
        self,
        db: asyncpg.Connection,
        service_request_id: UUID,
        workflow_code: str,
        entity_code: str,
        entity_location_id: Optional[UUID] = None,
        payment_id: Optional[str] = None,
        payment_method: Optional[str] = None,
        batch_id: Optional[UUID] = None,
    ) -> Optional[UUID]:
        """
        Insert an outbox item. MUST be called within the same transaction
        as the payment validation/completion for guaranteed delivery.

        Uses ON CONFLICT DO NOTHING on the unique partial index (idempotent).

        Returns:
            UUID of created outbox item, or None if duplicate exists.
        """
        try:
            row = await db.fetchrow(
                """
                INSERT INTO assignment_outbox (
                    service_request_id, workflow_code, entity_code,
                    entity_location_id, payment_id, payment_method, batch_id,
                    status, retry_count, next_retry_at,
                    created_at, updated_at
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7,
                    'pending', 0, NOW(), NOW(), NOW()
                )
                ON CONFLICT (service_request_id)
                    WHERE status IN ('pending', 'processing', 'completed')
                DO NOTHING
                RETURNING id
                """,
                service_request_id,
                workflow_code,
                entity_code,
                entity_location_id,
                payment_id,
                payment_method,
                batch_id,
            )

            if row:
                logger.info(
                    f"Outbox: enqueued {row['id']} for SR {service_request_id} "
                    f"(entity={entity_code}, workflow={workflow_code})"
                )
                return row["id"]
            else:
                logger.info(
                    f"Outbox: item already exists for SR {service_request_id}, skipping"
                )
                return None

        except Exception as e:
            logger.error(
                f"Outbox: failed to enqueue SR {service_request_id}: {e}",
                exc_info=True,
            )
            raise  # Let caller's transaction rollback

    async def process_pending_items(
        self,
        db: asyncpg.Connection,
    ) -> Dict[str, int]:
        """
        Process pending outbox items. Called by cron every 1 minute.

        Uses SELECT FOR UPDATE SKIP LOCKED for distributed safety:
        multiple Cloud Run instances can run simultaneously, each
        picks up different items (no overlap).

        Returns:
            Dict with counts: processed, failed, skipped, dead_letter
        """
        results = {"processed": 0, "failed": 0, "skipped": 0, "dead_letter": 0}

        # Fetch + lock pending items in a transaction
        async with db.transaction():
            items = await db.fetch(
                """
                SELECT id, service_request_id, workflow_code, entity_code,
                       entity_location_id, payment_id, payment_method,
                       retry_count, max_retries, batch_id
                FROM assignment_outbox
                WHERE status = 'pending'
                  AND next_retry_at <= NOW()
                ORDER BY created_at ASC
                LIMIT $1
                FOR UPDATE SKIP LOCKED
                """,
                self.BATCH_SIZE,
            )

            if not items:
                return results

            logger.info(f"Outbox: processing {len(items)} pending items")

            # Mark as 'processing' to release lock quickly
            item_ids = [item["id"] for item in items]
            await db.execute(
                """
                UPDATE assignment_outbox
                SET status = 'processing', locked_at = NOW(), updated_at = NOW()
                WHERE id = ANY($1)
                """,
                item_ids,
            )

        # Process each item outside the lock transaction
        for item in items:
            try:
                await self._process_single_item(db, item)

                await db.execute(
                    """
                    UPDATE assignment_outbox
                    SET status = 'completed', processed_at = NOW(), updated_at = NOW()
                    WHERE id = $1
                    """,
                    item["id"],
                )
                results["processed"] += 1

            except Exception as e:
                retry_count = item["retry_count"] + 1
                max_retries = item["max_retries"]

                if retry_count >= max_retries:
                    await db.execute(
                        """
                        UPDATE assignment_outbox
                        SET status = 'dead_letter', retry_count = $2,
                            last_error = $3, updated_at = NOW()
                        WHERE id = $1
                        """,
                        item["id"],
                        retry_count,
                        str(e)[:1000],
                    )
                    results["dead_letter"] += 1
                    logger.error(
                        f"Outbox: item {item['id']} → dead_letter after {retry_count} retries. "
                        f"SR: {item['service_request_id']}. Error: {e}"
                    )
                else:
                    delay_idx = min(
                        retry_count - 1, len(self.RETRY_DELAYS_SECONDS) - 1
                    )
                    base_delay = self.RETRY_DELAYS_SECONDS[delay_idx]
                    # Add jitter (0-20% of base delay) to prevent thundering herd
                    jitter = random.uniform(0, base_delay * 0.2)
                    delay = base_delay + jitter
                    next_retry = datetime.now(timezone.utc) + timedelta(seconds=delay)

                    await db.execute(
                        """
                        UPDATE assignment_outbox
                        SET status = 'pending', retry_count = $2,
                            next_retry_at = $3, last_error = $4, updated_at = NOW()
                        WHERE id = $1
                        """,
                        item["id"],
                        retry_count,
                        next_retry,
                        str(e)[:1000],
                    )
                    results["failed"] += 1
                    logger.warning(
                        f"Outbox: item {item['id']} failed (retry {retry_count}/{max_retries}), "
                        f"next retry at +{delay}s. Error: {e}"
                    )

        logger.info(
            f"Outbox: complete — {results['processed']} processed, "
            f"{results['failed']} retrying, {results['dead_letter']} dead-lettered"
        )
        return results

    async def _process_single_item(
        self,
        db: asyncpg.Connection,
        item: dict,
    ) -> None:
        """
        Process a single outbox item. Replicates the logic from
        AgentQueueEventHandler.handle_payment_completed() but with
        proper error propagation for retry.

        All mutations (queue + assign + status transition) are wrapped
        in a single transaction for atomicity: either all succeed or
        all rollback (preventing partial state like queue entry without
        status transition).

        Steps:
        1. Verify service_request exists and payment_status='completed'
        2. Skip if already assigned (idempotency)
        3. Add to agent_work_queue
        4. Auto-assign to entity agent
        5. Transition PAID → SUBMITTED
        """
        service_request_id = item["service_request_id"]
        entity_code = item["entity_code"]
        workflow_code = item["workflow_code"]
        entity_location_id = item.get("entity_location_id")

        # 1. Verify service_request state (read outside transaction for early exit)
        sr = await db.fetchrow(
            """
            SELECT id, reference, status, payment_status, assigned_to,
                   workflow_code, entity_code
            FROM service_requests
            WHERE id = $1
            """,
            service_request_id,
        )

        if not sr:
            raise ValueError(f"Service request not found: {service_request_id}")

        # Skip if already assigned and past PAID (idempotency)
        if sr["assigned_to"] is not None and sr["status"] != "PAID":
            logger.info(
                f"Outbox: SR {sr['reference']} already assigned "
                f"(status={sr['status']}). Marking completed."
            )
            return

        # Skip if payment not completed (not retryable)
        if sr["payment_status"] != "completed":
            logger.warning(
                f"Outbox: SR {sr['reference']} payment_status='{sr['payment_status']}', "
                f"expected 'completed'. Marking completed (not retryable)."
            )
            return

        # Use outbox values (authoritative), fall back to SR
        effective_entity_code = entity_code or sr["entity_code"]
        effective_workflow_code = workflow_code or sr["workflow_code"]

        if not effective_entity_code or not effective_workflow_code:
            raise ValueError(
                f"SR {sr['reference']} missing entity_code={effective_entity_code} "
                f"or workflow_code={effective_workflow_code}"
            )

        # ATOMIC: queue + assign + status transition in one transaction
        async with db.transaction():
            # 2. Add to agent_work_queue
            from app.modules.service_requests.services.agent_queue_service import (
                agent_queue_service,
            )

            queue_item = await agent_queue_service.add_to_queue(
                db=db,
                service_request_id=service_request_id,
                workflow_code=effective_workflow_code,
                entity_code=effective_entity_code,
                priority_boost=0,
            )

            logger.info(
                f"Outbox: SR {sr['reference']} added to queue "
                f"(item={queue_item.get('id')}, entity={effective_entity_code})"
            )

            # 3. Auto-assign to entity agent
            from app.modules.assignment.services.auto_assignment_service import (
                AutoAssignmentService,
            )

            auto_assignment = AutoAssignmentService()
            assignment = await auto_assignment.auto_assign_item(
                db=db,
                item_id=service_request_id,
                item_type="service_request",
                item_data={
                    "workflow_code": effective_workflow_code,
                    "entity_code": effective_entity_code,
                },
                entity_type="entity",
                entity_id=None,
                priority_level=5,
                entity_code=effective_entity_code,
                entity_location_id=entity_location_id,
                complexity_score=queue_item.get("complexity_score"),
            )

            if assignment:
                # Sync assigned_to on service_requests + agent_work_queue
                agent_user_id = await db.fetchval(
                    "SELECT user_id FROM agent_profiles WHERE id = $1",
                    assignment.agent_profile_id,
                )
                if agent_user_id:
                    await db.execute(
                        """
                        UPDATE service_requests
                        SET assigned_to = $1, assigned_at = NOW(), updated_at = NOW()
                        WHERE id = $2
                        """,
                        agent_user_id,
                        service_request_id,
                    )
                    # Sync agent_work_queue so make_decision + Pendientes/Completados work
                    await db.execute(
                        """
                        UPDATE agent_work_queue
                        SET assigned_to = $1, assigned_at = NOW(),
                            status = 'assigned', updated_at = NOW()
                        WHERE item_id = $2
                          AND item_type = 'service_request'
                          AND assigned_to IS NULL
                        """,
                        agent_user_id,
                        service_request_id,
                    )

                logger.info(
                    f"Outbox: SR {sr['reference']} auto-assigned to "
                    f"agent {assignment.agent_profile_id} (user {agent_user_id})"
                )
            else:
                logger.warning(
                    f"Outbox: no agent available for SR {sr['reference']} "
                    f"(entity={effective_entity_code}). Pending manual assignment."
                )

            # 4. Transition PAID → SUBMITTED
            # SUBMITTED is in ActionStatusMapping.PENDING → visible in agent dashboard
            # Transition even without agent so supervisors can see and manually assign
            updated = await db.fetchval(
                """
                UPDATE service_requests
                SET status = 'SUBMITTED', submitted_at = COALESCE(submitted_at, NOW()), updated_at = NOW()
                WHERE id = $1 AND status = 'PAID'
                RETURNING id
                """,
                service_request_id,
            )

            if updated:
                logger.info(
                    f"Outbox: SR {sr['reference']} PAID → SUBMITTED"
                    + (
                        f" (agent {assignment.agent_profile_id})"
                        if assignment
                        else " (no agent, pending manual)"
                    )
                )

    async def run_health_check(
        self,
        db: asyncpg.Connection,
    ) -> Dict[str, Any]:
        """
        Runtime health check for the assignment pipeline.
        Called by cron every 5 minutes.

        Detects:
        1. PAID requests >ORPHAN_THRESHOLD_MINUTES without assignment AND not in outbox
        2. Dead letter outbox items
        3. Stale 'processing' items (crashed instance)

        Actions:
        - Orphans: re-enqueue into outbox
        - Stale processing: reset to pending
        - Dead letters: log for supervisor
        """
        results: Dict[str, Any] = {
            "orphans_found": 0,
            "orphans_requeued": 0,
            "dead_letters": 0,
            "stale_processing_reset": 0,
        }

        # 1. Find orphaned PAID requests not in outbox
        orphans = await db.fetch(
            """
            SELECT sr.id, sr.reference, sr.workflow_code, sr.entity_code,
                   sr.entity_location_id, sr.payment_status,
                   sp.id AS payment_id, sp.payment_method
            FROM service_requests sr
            JOIN service_payments sp ON sp.service_request_id = sr.id
                AND sp.status = 'completed'
            WHERE sr.status = 'PAID'
              AND sr.payment_status = 'completed'
              AND sr.assigned_to IS NULL
              AND sr.created_at < NOW() - ($1 * interval '1 minute')
              AND NOT EXISTS (
                  SELECT 1 FROM assignment_outbox ao
                  WHERE ao.service_request_id = sr.id
                    AND ao.status IN ('pending', 'processing')
              )
              AND NOT EXISTS (
                  SELECT 1 FROM agent_work_queue awq
                  WHERE awq.item_id = sr.id
                    AND awq.item_type = 'service_request'
                    AND awq.status NOT IN ('completed', 'cancelled')
              )
            ORDER BY sr.created_at ASC
            LIMIT 100
            """,
            self.ORPHAN_THRESHOLD_MINUTES,
        )

        results["orphans_found"] = len(orphans)

        for orphan in orphans:
            try:
                entity_code = orphan["entity_code"]

                # Resolve entity_code if NULL
                if not entity_code and orphan["entity_location_id"]:
                    entity_code = await db.fetchval(
                        "SELECT entity_code FROM entity_locations "
                        "WHERE id = $1 AND is_active = true",
                        orphan["entity_location_id"],
                    )
                if not entity_code and orphan["workflow_code"]:
                    entity_code = await db.fetchval(
                        """
                        SELECT code FROM entities
                        WHERE workflow_codes ? $1 AND is_active = true
                          AND entity_type = 'department'
                        LIMIT 1
                        """,
                        orphan["workflow_code"],
                    )

                if not entity_code:
                    logger.error(
                        f"Health check: cannot resolve entity_code "
                        f"for {orphan['reference']}"
                    )
                    continue

                # Persist entity_code if it was NULL
                if not orphan["entity_code"]:
                    await db.execute(
                        "UPDATE service_requests SET entity_code = $1, "
                        "updated_at = NOW() WHERE id = $2",
                        entity_code,
                        orphan["id"],
                    )

                outbox_id = await self.enqueue(
                    db=db,
                    service_request_id=orphan["id"],
                    workflow_code=orphan["workflow_code"],
                    entity_code=entity_code,
                    entity_location_id=orphan["entity_location_id"],
                    payment_id=str(orphan["payment_id"]) if orphan["payment_id"] else None,
                    payment_method=orphan["payment_method"],
                )

                if outbox_id:
                    results["orphans_requeued"] += 1
                    logger.info(
                        f"Health check: re-enqueued orphan {orphan['reference']}"
                    )

            except Exception as e:
                logger.error(
                    f"Health check: failed to re-enqueue {orphan['reference']}: {e}"
                )

        # 2. Count dead letters
        dead_count = await db.fetchval(
            "SELECT COUNT(*) FROM assignment_outbox WHERE status = 'dead_letter'"
        )
        results["dead_letters"] = dead_count or 0

        if dead_count and dead_count > 0:
            logger.error(
                f"Health check: {dead_count} dead letter items in outbox! "
                f"Supervisor attention required."
            )

        # 3. Reset stale 'processing' items (crashed instance)
        stale_result = await db.execute(
            """
            UPDATE assignment_outbox
            SET status = 'pending',
                next_retry_at = NOW(),
                last_error = 'Reset by health check: stale processing state',
                updated_at = NOW()
            WHERE status = 'processing'
              AND locked_at < NOW() - ($1 * interval '1 minute')
            """,
            self.STALE_PROCESSING_MINUTES,
        )
        stale_count = int(stale_result.split()[-1]) if stale_result else 0
        results["stale_processing_reset"] = stale_count

        if stale_count > 0:
            logger.warning(
                f"Health check: reset {stale_count} stale 'processing' outbox items"
            )

        return results


# Singleton
assignment_outbox_service = AssignmentOutboxService()
