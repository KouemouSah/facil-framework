"""
Payment Assignment Event Handler
================================
Handles auto-assignment of manual payments (Cash/Check) to Treasury agents.

Business Logic:
- When a manual payment is created (PAYMENT_MANUAL_PENDING event),
  auto-assign it to an available Treasury agent
- Uses AutoAssignmentService with site-based routing (entity_location_id)
- Fallback: site exact → floating agents → entity-wide

@module payments/handlers/payment_assignment_handler
"""

import logging
from typing import Optional
from uuid import UUID

from app.core.events import EventBus, EventType, EventPayload
from app.database.connection import get_db_connection, release_db_connection
from app.modules.assignment.services.auto_assignment_service import AutoAssignmentService

logger = logging.getLogger(__name__)


class PaymentAssignmentHandler:
    """
    Event handler that auto-assigns manual payments to validator agents.

    This handler listens to:
    - PAYMENT_MANUAL_PENDING: Triggered when Cash/Check payment is created

    When triggered:
    - Uses target_entity_code from the payload if present (bundle flow:
      TESORO / AYUNTAMIENTO / CAMARA_COMERCIO per obligation group)
    - Falls back to TESORO for legacy non-bundle manual payments where the
      producer does not propagate target_entity_code
    - Selects the agent with lowest workload within that entity
    - Creates assignment with item_type = 'payment_validation'
    """

    # Fallback for legacy non-bundle manual payments that do not propagate
    # their validator entity in the event payload. Bundle flows MUST pass
    # target_entity_code via context.metadata to avoid misrouting municipal
    # and chamber payments to the Treasury queue.
    DEFAULT_VALIDATOR_ENTITY_CODE = "TESORO"

    def __init__(self):
        """Initialize the payment assignment handler."""
        self._registered = False
        logger.info("PaymentAssignmentHandler initialized")

    def register(self) -> None:
        """
        Register event handlers with the EventBus.
        Should be called once at application startup.
        """
        if self._registered:
            logger.warning("PaymentAssignmentHandler already registered")
            return

        # Subscribe to manual payment pending event
        EventBus.subscribe(EventType.PAYMENT_MANUAL_PENDING, self.handle_manual_payment_pending)
        logger.info("PaymentAssignmentHandler: registered for PAYMENT_MANUAL_PENDING")

        self._registered = True

    async def handle_manual_payment_pending(self, payload: EventPayload) -> None:
        """
        Handle PAYMENT_MANUAL_PENDING event.

        When a manual payment is created:
        1. Find available Treasury agents
        2. Select agent with lowest workload
        3. Create assignment record

        Args:
            payload: Event payload containing:
                - payment_id: UUID of the payment
                - service_request_id: UUID of the service request
                - user_id: User who made the payment
                - amount: Payment amount
                - payment_method: 'cash' or 'check'
        """
        payment_id = payload.get("payment_id")
        service_request_id = payload.get("service_request_id")
        payment_method = payload.get("payment_method", "unknown")
        amount = payload.get("amount", 0)
        target_entity_code = (
            payload.get("target_entity_code")
            or self.DEFAULT_VALIDATOR_ENTITY_CODE
        )

        if not payment_id:
            logger.warning(
                f"PAYMENT_MANUAL_PENDING event missing payment_id: {payload}"
            )
            return

        logger.info(
            f"Processing PAYMENT_MANUAL_PENDING for payment={payment_id}, "
            f"service_request={service_request_id}, method={payment_method}, "
            f"amount={amount}, target_entity={target_entity_code}"
        )

        conn = None
        try:
            conn = await get_db_connection()

            # 1. Check if assignment already exists (duplicate guard)
            existing = await conn.fetchval("""
                SELECT id FROM assignments
                WHERE item_id = $1::uuid AND item_type = 'payment_validation'
            """, payment_id)

            if existing:
                logger.info(f"Payment {payment_id} already assigned, skipping")
                return

            # 2. Resolve target entity location (explicit > city auto > fallback).
            # For bundle workflows, target_entity_code is TESORO, AYUNTAMIENTO
            # or CAMARA_COMERCIO depending on which entity_group the payment
            # belongs to — the location lookup must respect that.
            target_location_id = payload.get("treasury_location_id")

            if not target_location_id and service_request_id:
                target_location_id = await conn.fetchval("""
                    SELECT tel.id
                    FROM service_requests sr
                    JOIN entity_locations sr_el ON sr_el.id = sr.entity_location_id
                    JOIN entity_locations tel ON tel.city_id = sr_el.city_id
                        AND tel.entity_code = $2
                        AND tel.is_active = true
                    WHERE sr.id = $1::uuid
                    LIMIT 1
                """, service_request_id, target_entity_code)

            if target_location_id:
                logger.info(
                    f"{target_entity_code} location resolved: "
                    f"{target_location_id} "
                    f"(explicit={'treasury_location_id' in (payload or {})})"
                )

            # 3. Auto-assign via AutoAssignmentService (site-based routing with fallback)
            assignment_service = AutoAssignmentService()
            assignment = await assignment_service.auto_assign_item(
                db=conn,
                item_id=UUID(str(payment_id)),
                item_type="payment_validation",
                item_data={"amount": amount, "payment_method": payment_method},
                entity_code=target_entity_code,
                entity_location_id=target_location_id,
                priority_level=5,
            )

            if not assignment:
                logger.warning(
                    f"No available {target_entity_code} agents for payment "
                    f"{payment_id}. Payment will remain unassigned in the queue."
                )
                return

            agent_profile_id = assignment.agent_profile_id

            # 4. Update service_payments with assigned agent + entity_code + assigned_at
            # entity_code must reflect the VALIDATOR entity (TESORO, AYUNTAMIENTO, etc.)
            # not the workflow entity (DGT, CNEDOGE, etc.) — otherwise dashboard
            # stats queries that filter on sp.entity_code miss the payment.
            await conn.execute("""
                UPDATE service_payments
                SET assigned_agent_id = $1,
                    entity_code = $3,
                    assigned_at = NOW(),
                    updated_at = NOW()
                WHERE id = $2::uuid
            """, agent_profile_id, payment_id, target_entity_code)

            logger.info(
                f"Payment {payment_id} auto-assigned to {target_entity_code} "
                f"agent (agent_profile_id: {agent_profile_id}). "
                f"Assignment ID: {assignment.id}, "
                f"location_id: {target_location_id}"
            )

        except Exception as e:
            logger.error(
                f"Failed to auto-assign payment {payment_id} to Treasury agent: {e}",
                exc_info=True
            )
        finally:
            if conn:
                await release_db_connection(conn)


# Global handler instance
_handler: Optional[PaymentAssignmentHandler] = None


def register_payment_assignment_handlers() -> PaymentAssignmentHandler:
    """
    Register payment assignment handlers with the EventBus.
    Should be called once at application startup.

    Returns:
        The registered PaymentAssignmentHandler instance
    """
    global _handler
    if _handler is None:
        _handler = PaymentAssignmentHandler()
        _handler.register()
    return _handler
