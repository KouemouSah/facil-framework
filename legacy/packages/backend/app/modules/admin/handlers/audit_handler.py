"""
Audit Event Handler
===================
Handles events from the EventBus and creates audit log entries.

Automatically logs significant events for compliance and debugging.

@module admin/handlers/audit_handler
"""

from typing import Dict, Optional, Any, Set
from dataclasses import dataclass
from loguru import logger

from app.core.events import EventBus, EventType, EventPayload
from app.modules.admin.models import AuditLogCreate
from app.modules.admin.repositories.audit_repository import AuditRepository
from app.database.connection import get_db_pool


@dataclass
class AuditConfig:
    """Configuration for audit logging of an event."""
    entity_type: str
    action: str
    include_old_values: bool = False
    include_new_values: bool = True


# =============================================================================
# EVENT TO AUDIT MAPPING
# =============================================================================

EVENT_AUDIT_MAP: Dict[EventType, AuditConfig] = {
    # Payment Events
    EventType.PAYMENT_COMPLETED: AuditConfig(
        entity_type="payment",
        action="payment_completed"
    ),
    EventType.PAYMENT_FAILED: AuditConfig(
        entity_type="payment",
        action="payment_failed"
    ),
    EventType.PAYMENT_CASH_PENDING: AuditConfig(
        entity_type="payment",
        action="cash_payment_pending"
    ),
    EventType.PAYMENT_CASH_VALIDATED: AuditConfig(
        entity_type="payment",
        action="cash_payment_validated"
    ),
    EventType.PAYMENT_CASH_REJECTED: AuditConfig(
        entity_type="payment",
        action="cash_payment_rejected"
    ),
    EventType.PAYMENT_REFUNDED: AuditConfig(
        entity_type="payment",
        action="payment_refunded"
    ),
    # Note: PAYMENT_LOCKED/UNLOCKED removed - lock mechanism obsolete with auto-assignment

    # Service Request Events
    EventType.REQUEST_SUBMITTED: AuditConfig(
        entity_type="service_request",
        action="request_submitted"
    ),
    EventType.REQUEST_APPROVED: AuditConfig(
        entity_type="service_request",
        action="request_approved"
    ),
    EventType.REQUEST_REJECTED: AuditConfig(
        entity_type="service_request",
        action="request_rejected"
    ),
    EventType.REQUEST_COMPLETED: AuditConfig(
        entity_type="service_request",
        action="request_completed"
    ),
    EventType.REQUEST_CANCELLED: AuditConfig(
        entity_type="service_request",
        action="request_cancelled"
    ),
    EventType.REQUEST_ESCALATED: AuditConfig(
        entity_type="service_request",
        action="request_escalated"
    ),
    EventType.REQUEST_ASSIGNED: AuditConfig(
        entity_type="service_request",
        action="request_assigned"
    ),

    # Document Events
    EventType.DOCUMENT_UPLOADED: AuditConfig(
        entity_type="document",
        action="document_uploaded"
    ),
    EventType.DOCUMENT_VALIDATED: AuditConfig(
        entity_type="document",
        action="document_validated"
    ),
    EventType.DOCUMENT_REJECTED: AuditConfig(
        entity_type="document",
        action="document_rejected"
    ),

    # Appointment Events
    EventType.APPOINTMENT_BOOKED: AuditConfig(
        entity_type="appointment",
        action="appointment_booked"
    ),
    EventType.APPOINTMENT_CONFIRMED: AuditConfig(
        entity_type="appointment",
        action="appointment_confirmed"
    ),
    EventType.APPOINTMENT_CANCELLED: AuditConfig(
        entity_type="appointment",
        action="appointment_cancelled"
    ),
    EventType.APPOINTMENT_COMPLETED: AuditConfig(
        entity_type="appointment",
        action="appointment_completed"
    ),
    EventType.APPOINTMENT_NO_SHOW: AuditConfig(
        entity_type="appointment",
        action="appointment_no_show"
    ),

    # User Events
    EventType.USER_REGISTERED: AuditConfig(
        entity_type="user",
        action="user_registered"
    ),
    EventType.USER_VERIFIED: AuditConfig(
        entity_type="user",
        action="user_verified"
    ),
    EventType.USER_PASSWORD_RESET: AuditConfig(
        entity_type="user",
        action="password_reset_requested"
    ),
    EventType.USER_2FA_ENABLED: AuditConfig(
        entity_type="user",
        action="2fa_enabled"
    ),

    # Declaration Events
    EventType.DECLARATION_SUBMITTED: AuditConfig(
        entity_type="declaration",
        action="declaration_submitted"
    ),
    EventType.DECLARATION_VALIDATED: AuditConfig(
        entity_type="declaration",
        action="declaration_validated"
    ),
    EventType.DECLARATION_REJECTED: AuditConfig(
        entity_type="declaration",
        action="declaration_rejected"
    ),

    # SLA Events
    EventType.SLA_WARNING: AuditConfig(
        entity_type="sla",
        action="sla_warning"
    ),
    EventType.SLA_BREACH: AuditConfig(
        entity_type="sla",
        action="sla_breach"
    ),

    # System Events
    EventType.SYSTEM_ERROR: AuditConfig(
        entity_type="system",
        action="system_error"
    ),
}


class AuditEventHandler:
    """
    Event handler that creates audit log entries.

    Responsibilities:
    - Listen to relevant events from EventBus
    - Create audit log entries in the database
    - Extract relevant entity information from payload
    """

    def __init__(self):
        """Initialize the audit handler."""
        self.repository = AuditRepository()
        self._registered = False
        logger.info("AuditEventHandler initialized")

    def register(self) -> None:
        """
        Register all event handlers with the EventBus.
        Should be called once at application startup.
        """
        if self._registered:
            logger.warning("AuditEventHandler already registered")
            return

        for event_type in EVENT_AUDIT_MAP.keys():
            EventBus.subscribe(event_type, self.handle_event)
            logger.debug(f"Registered audit handler for {event_type.value}")

        self._registered = True
        logger.info(
            f"AuditEventHandler registered for {len(EVENT_AUDIT_MAP)} event types"
        )

    async def handle_event(self, payload: EventPayload) -> None:
        """
        Handle an event and create an audit log entry.

        Args:
            payload: The event payload containing all relevant data
        """
        event_type_str = payload.get("event_type", "")

        try:
            event_type = EventType(event_type_str)
        except ValueError:
            logger.warning(f"Unknown event type for audit: {event_type_str}")
            return

        config = EVENT_AUDIT_MAP.get(event_type)
        if not config:
            logger.debug(f"No audit config for {event_type_str}")
            return

        # Extract entity ID based on entity type
        entity_id = self._get_entity_id(config.entity_type, payload)
        if not entity_id:
            logger.warning(
                f"No entity ID found for {event_type_str}, skipping audit"
            )
            return

        # Build new_values from relevant payload fields
        new_values = self._build_audit_values(config.entity_type, payload)

        # Create audit log entry
        audit_log = AuditLogCreate(
            user_id=payload.get("user_id") or payload.get("agent_id"),
            entity_type=config.entity_type,
            entity_id=entity_id,
            action=config.action,
            old_values=None,  # We don't track old values in event-based audit
            new_values=new_values if config.include_new_values else None,
            ip_address=payload.get("metadata", {}).get("ip_address"),
            user_agent=payload.get("metadata", {}).get("user_agent"),
        )

        # Save to database
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                result = await self.repository.create(conn, audit_log)
                logger.info(
                    f"Audit log created: {config.entity_type}/{config.action} "
                    f"for entity {entity_id}"
                )
        except Exception as e:
            logger.error(f"Failed to create audit log: {e}")

    def _get_entity_id(
        self,
        entity_type: str,
        payload: EventPayload
    ) -> Optional[str]:
        """
        Extract entity ID from payload based on entity type.

        Args:
            entity_type: The type of entity
            payload: Event payload

        Returns:
            Entity ID or None
        """
        id_mapping = {
            "payment": "payment_id",
            "service_request": "request_id",
            "document": "document_id",
            "appointment": "appointment_id",
            "user": "user_id",
            "declaration": "declaration_id",
            "sla": "request_id",  # SLA events are related to requests
            "system": "request_id",  # Fallback to request_id
        }

        id_field = id_mapping.get(entity_type, "request_id")
        return payload.get(id_field)

    def _build_audit_values(
        self,
        entity_type: str,
        payload: EventPayload
    ) -> Dict[str, Any]:
        """
        Build audit values dictionary from payload.

        Args:
            entity_type: The type of entity
            payload: Event payload

        Returns:
            Dictionary of values to log
        """
        # Common fields to always include
        values: Dict[str, Any] = {
            "timestamp": payload.get("timestamp"),
        }

        # Entity-specific fields
        if entity_type == "payment":
            values.update({
                "amount": payload.get("amount"),
                "currency": payload.get("currency"),
                "payment_method": payload.get("payment_method"),
                "receipt_number": payload.get("receipt_number"),
                "request_id": payload.get("request_id"),
            })

        elif entity_type == "service_request":
            values.update({
                "service_code": payload.get("service_code"),
                "workflow_code": payload.get("workflow_code"),
                "current_step": payload.get("current_step"),
                "reason": payload.get("reason"),
            })

        elif entity_type == "document":
            values.update({
                "document_type": payload.get("document_type"),
                "file_name": payload.get("file_name"),
                "request_id": payload.get("request_id"),
            })

        elif entity_type == "appointment":
            values.update({
                "appointment_date": payload.get("appointment_date"),
                "appointment_time": payload.get("appointment_time"),
                "location": payload.get("location"),
                "request_id": payload.get("request_id"),
            })

        elif entity_type == "user":
            values.update({
                "user_email": payload.get("user_email"),
                "user_name": payload.get("user_name"),
            })

        elif entity_type == "declaration":
            values.update({
                "declaration_type": payload.get("metadata", {}).get("declaration_type"),
                "amount": payload.get("amount"),
            })

        elif entity_type == "sla":
            values.update({
                "service_code": payload.get("service_code"),
                "sla_hours": payload.get("metadata", {}).get("sla_hours"),
                "elapsed_hours": payload.get("metadata", {}).get("elapsed_hours"),
            })

        # Remove None values
        return {k: v for k, v in values.items() if v is not None}


# =============================================================================
# REGISTRATION FUNCTION
# =============================================================================

def register_audit_handlers() -> AuditEventHandler:
    """
    Register all audit handlers with the EventBus.
    Should be called once at application startup.

    Returns:
        The registered AuditEventHandler instance
    """
    handler = AuditEventHandler()
    handler.register()
    return handler
