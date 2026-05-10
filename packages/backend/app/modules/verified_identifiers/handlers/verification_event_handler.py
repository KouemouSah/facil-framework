"""
Verification Event Handler

Subscribes to REQUEST_SUBMITTED events and triggers
automatic verification of document identifiers.
"""

from typing import Dict, Any, Optional
from loguru import logger

from app.core.events.event_bus import EventBus
from app.core.events.event_types import EventType
from app.database.connection import get_db_pool

from ..services.verification_service import VerificationService, TransientVerificationError
from ..models.verified_identifier import VerificationStatus


class VerificationEventHandler:
    """
    Event handler for automatic verification of document identifiers.

    Subscribes to:
    - REQUEST_SUBMITTED: Triggers verification when a request is submitted

    Publishes:
    - VERIFICATION_REQUIRED: When identifiers are not found (needs agent attention)
    - VERIFICATION_COMPLETED: When verification completes
    """

    def __init__(self):
        """Initialize handler (service is created per-request for proper pool handling)."""
        self._subscribed = False

    async def subscribe(self) -> None:
        """Subscribe to events. Call during application startup."""
        if self._subscribed:
            return

        EventBus.subscribe(EventType.REQUEST_SUBMITTED, self.handle_request_submitted)
        self._subscribed = True
        logger.info("VerificationEventHandler subscribed to REQUEST_SUBMITTED")

    async def handle_request_submitted(self, payload: Dict[str, Any]) -> None:
        """
        Handle service request submission.

        Triggers automatic verification of all document identifiers
        in the submitted request.

        Args:
            payload: Event payload with request_id and other details
        """
        request_id = payload.get("request_id")
        if not request_id:
            logger.warning("REQUEST_SUBMITTED event missing request_id")
            return

        logger.info(f"Handling REQUEST_SUBMITTED for {request_id}")

        try:
            # Get database pool
            pool = await get_db_pool()
            service = VerificationService(pool)

            # Queue the request for verification
            await service.queue_for_verification(request_id)

            # Attempt immediate verification
            result = await service.verify_service_request(request_id)

            # If verification found issues, notify agents
            if result.status in [VerificationStatus.NOT_FOUND, VerificationStatus.PARTIAL_VERIFICATION]:
                await self._notify_agents_for_verification(
                    request_id=request_id,
                    result=result,
                    payload=payload
                )

            # Publish completion event
            await EventBus.publish(EventType.VERIFICATION_COMPLETED, {
                "request_id": request_id,
                "status": result.status.value,
                "results": {k: v.model_dump() for k, v in result.results.items()},
                "timestamp": payload.get("timestamp")
            })

        except TransientVerificationError as e:
            # Transient error - will be retried via queue
            logger.warning(f"Transient verification error for {request_id}: {e}")

        except Exception as e:
            logger.error(f"Verification failed for {request_id}: {e}", exc_info=True)
            # Update status to failed
            try:
                pool = await get_db_pool()
                service = VerificationService(pool)
                await service._update_request_verification_status(
                    request_id=request_id,
                    status=VerificationStatus.VERIFICATION_FAILED,
                    details={"error": str(e)}
                )
            except Exception as update_err:
                logger.error(f"Failed to update verification status: {update_err}")

    async def _notify_agents_for_verification(
        self,
        request_id: str,
        result: Any,
        payload: Dict[str, Any]
    ) -> None:
        """
        Send notifications to agents when verification requires attention.

        Broadcasts to all available agents in the ministry.

        Args:
            request_id: UUID of the service request
            result: Verification result
            payload: Original event payload
        """
        try:
            pool = await get_db_pool()

            # Get request details including ministry
            request_query = """
                SELECT sr.id, sr.reference, sr.workflow_code, sr.user_id,
                       fs.ministry_id, m.name_es AS ministry_name
                FROM service_requests sr
                LEFT JOIN fiscal_services fs ON sr.service_id = fs.id
                LEFT JOIN ministries m ON fs.ministry_id = m.id
                WHERE sr.id = $1
            """
            async with pool.acquire() as conn:
                request = await conn.fetchrow(request_query, request_id)

            if not request:
                logger.warning(f"Request {request_id} not found for notification")
                return

            ministry_id = request.get("ministry_id")
            if not ministry_id:
                logger.warning(f"No ministry found for request {request_id}")
                return

            # Get all available agents for this ministry (direct or via entity)
            agents_query = """
                SELECT ap.user_id, u.email, u.full_name
                FROM agent_profiles ap
                JOIN users u ON ap.user_id = u.id
                LEFT JOIN agent_workloads aw ON ap.id = aw.agent_profile_id
                LEFT JOIN entities e ON ap.entity_id = e.id
                WHERE (ap.ministry_id = $1 OR e.ministry_id = $1)
                  AND ap.is_active = TRUE
                  AND (aw.availability = 'available' OR aw.availability IS NULL)
            """
            async with pool.acquire() as conn:
                agents = await conn.fetch(agents_query, ministry_id)

            if not agents:
                logger.warning(f"No available agents for ministry {ministry_id}")
                # Fallback: try to notify supervisors
                await self._notify_supervisors(request_id, result, request)
                return

            # Collect not-found identifier types
            not_found_items = [
                k for k, v in result.results.items()
                if not v.verified
            ]

            # Broadcast notification to all available agents
            for agent in agents:
                try:
                    await EventBus.publish(EventType.VERIFICATION_REQUIRED, {
                        "request_id": request_id,
                        "request_reference": request.get("reference"),
                        "user_id": str(agent["user_id"]),
                        "agent_email": agent["email"],
                        "agent_name": agent["full_name"],
                        "ministry_id": str(ministry_id),
                        "ministry_name": request.get("ministry_name"),
                        "not_found": not_found_items,
                        "verification_status": result.status.value,
                        "message_es": f"Verificación requerida: {', '.join(not_found_items)} no encontrado en base de datos externa",
                        "message_fr": f"Vérification requise: {', '.join(not_found_items)} non trouvé dans la base de données externe",
                        "message_en": f"Verification required: {', '.join(not_found_items)} not found in external database",
                        "priority": "high"
                    })
                except Exception as e:
                    logger.error(f"Failed to notify agent {agent['user_id']}: {e}")

            logger.info(f"Notified {len(agents)} agents about verification for {request_id}")

        except Exception as e:
            logger.error(f"Failed to notify agents for {request_id}: {e}", exc_info=True)

    async def _notify_supervisors(
        self,
        request_id: str,
        result: Any,
        request: Dict[str, Any]
    ) -> None:
        """
        Fallback: Notify supervisors when no agents are available.

        Args:
            request_id: UUID of the service request
            result: Verification result
            request: Request details
        """
        try:
            pool = await get_db_pool()

            # Get supervisors
            supervisors_query = """
                SELECT id, email, full_name
                FROM users
                WHERE role = 'supervisor' AND status = 'active'
            """
            async with pool.acquire() as conn:
                supervisors = await conn.fetch(supervisors_query)

            not_found_items = [
                k for k, v in result.results.items()
                if not v.verified
            ]

            for supervisor in supervisors:
                await EventBus.publish(EventType.VERIFICATION_REQUIRED, {
                    "request_id": request_id,
                    "request_reference": request.get("reference"),
                    "user_id": str(supervisor["id"]),
                    "not_found": not_found_items,
                    "verification_status": result.status.value,
                    "message_es": f"[SUPERVISOR] Verificación requerida sin agentes disponibles: {request_id}",
                    "message_fr": f"[SUPERVISOR] Vérification requise sans agents disponibles: {request_id}",
                    "priority": "high",
                    "escalated": True
                })

            logger.info(f"Notified {len(supervisors)} supervisors about verification for {request_id}")

        except Exception as e:
            logger.error(f"Failed to notify supervisors: {e}")


# Singleton instance
_handler: Optional[VerificationEventHandler] = None


def get_verification_event_handler() -> VerificationEventHandler:
    """Get singleton handler instance."""
    global _handler
    if _handler is None:
        _handler = VerificationEventHandler()
    return _handler


async def setup_verification_handlers() -> None:
    """
    Setup verification event handlers.

    Call this during application startup.
    """
    handler = get_verification_event_handler()
    await handler.subscribe()
    logger.info("Verification event handlers configured")
