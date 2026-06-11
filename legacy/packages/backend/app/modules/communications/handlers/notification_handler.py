"""
Notification Event Handler
==========================
Handles events from the EventBus and sends appropriate notifications.

Maps event types to notification templates and sends via:
- Email (via CommunicationService)
- SMS (via SmsSendingService + Infobip)
- Push notifications (via PushSendingService + Firebase)

@module communications/handlers/notification_handler
@version 2.0.0 - Implemented SMS and Push channels
"""

import asyncio
from datetime import datetime
from typing import Dict, Optional, Any, List, Tuple
from dataclasses import dataclass
from enum import Enum
from loguru import logger

from app.config import settings
from app.core.events import EventBus, EventType, EventPayload
from app.database.connection import db_manager
from app.modules.communications.services.communication_service import CommunicationService
from app.modules.communications.services.sms_sending_service import get_sms_sending_service
from app.modules.communications.services.push_sending_service import get_push_sending_service
from app.modules.communications.models.communication import CommunicationType


class NotificationChannel(str, Enum):
    """Available notification channels."""
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    IN_APP = "in_app"


@dataclass
class NotificationConfig:
    """Configuration for a notification triggered by an event."""
    template_code: str
    channels: List[NotificationChannel]
    priority: str = "normal"  # low, normal, high, critical
    subject_key: Optional[str] = None  # i18n key for email subject
    requires_user_prefs: bool = True  # Check user notification preferences
    sms_template_code: Optional[str] = None  # Override template code for SMS (uses UPPERCASE codes)


# =============================================================================
# EVENT TO NOTIFICATION MAPPING
# =============================================================================

EVENT_NOTIFICATION_MAP: Dict[EventType, NotificationConfig] = {
    # Payment Events
    # Note: sms_template_code uses UPPERCASE to match existing templates from migration 012
    EventType.PAYMENT_COMPLETED: NotificationConfig(
        template_code="payment_completed",
        channels=[NotificationChannel.EMAIL, NotificationChannel.SMS, NotificationChannel.PUSH],
        priority="high",
        subject_key="notifications.payment.completed.subject",
        sms_template_code="PAYMENT_RECEIVED"  # Reuses existing template from migration 012
    ),
    EventType.PAYMENT_FAILED: NotificationConfig(
        template_code="payment_failed",
        channels=[NotificationChannel.EMAIL, NotificationChannel.SMS],
        priority="high",
        subject_key="notifications.payment.failed.subject",
        sms_template_code="PAYMENT_FAILED"
    ),
    EventType.PAYMENT_CASH_PENDING: NotificationConfig(
        template_code="payment_cash_pending",
        channels=[NotificationChannel.EMAIL, NotificationChannel.SMS],
        priority="normal",
        subject_key="notifications.payment.cash_pending.subject",
        sms_template_code="PAYMENT_CASH_PENDING"
    ),
    EventType.PAYMENT_CASH_VALIDATED: NotificationConfig(
        template_code="payment_cash_validated",
        channels=[NotificationChannel.EMAIL, NotificationChannel.SMS, NotificationChannel.PUSH],
        priority="high",
        subject_key="notifications.payment.cash_validated.subject",
        sms_template_code="PAYMENT_CASH_VALIDATED"
    ),
    EventType.PAYMENT_CASH_REJECTED: NotificationConfig(
        template_code="payment_cash_rejected",
        channels=[NotificationChannel.EMAIL, NotificationChannel.SMS],
        priority="high",
        subject_key="notifications.payment.cash_rejected.subject",
        sms_template_code="PAYMENT_CASH_REJECTED"
    ),
    EventType.PAYMENT_MANUAL_ESCALATED: NotificationConfig(
        template_code="payment_escalated",
        channels=[NotificationChannel.EMAIL, NotificationChannel.SMS],
        priority="critical",
        subject_key="notifications.payment.escalated.subject",
        sms_template_code="PAYMENT_ESCALATED"
    ),

    # License Events (OMS Bundle)
    EventType.LICENSE_COMPLETED: NotificationConfig(
        template_code="LICENSE_GENERATED",
        channels=[NotificationChannel.EMAIL],
        priority="high",
        subject_key="notifications.license.completed.subject",
    ),
    EventType.OBLIGATION_OVERDUE: NotificationConfig(
        template_code="obligation_overdue",
        channels=[NotificationChannel.EMAIL, NotificationChannel.SMS, NotificationChannel.PUSH],
        priority="high",
        subject_key="notifications.obligation.overdue.subject",
        sms_template_code="OBLIGATION_OVERDUE",
    ),
    EventType.OBLIGATION_PENALTY_APPLIED: NotificationConfig(
        template_code="obligation_penalty_applied",
        channels=[NotificationChannel.EMAIL, NotificationChannel.PUSH],
        priority="high",
        subject_key="notifications.obligation.penalty.subject",
        sms_template_code="OBLIGATION_PENALTY_APPLIED",
    ),
    EventType.OBLIGATION_REMINDER_SENT: NotificationConfig(
        template_code="obligation_reminder",
        channels=[NotificationChannel.EMAIL, NotificationChannel.PUSH],
        priority="normal",
        subject_key="notifications.obligation.reminder.subject",
        sms_template_code="OBLIGATION_REMINDER",
    ),
    EventType.OBLIGATION_PROCESSED: NotificationConfig(
        template_code="obligation_processed",
        channels=[NotificationChannel.PUSH],
        priority="normal",
        subject_key="notifications.obligation.processed.subject",
        requires_user_prefs=False,  # Always notify (progress is important)
        # NOTE: No DB template needed for PUSH-only — the push_sending_service
        # uses payload fields (service_name, amount) directly. If template
        # lookup fails, the handler falls back to generic push text.
    ),

    # Service Request Events
    EventType.REQUEST_SUBMITTED: NotificationConfig(
        template_code="request_submitted",
        channels=[NotificationChannel.EMAIL, NotificationChannel.SMS, NotificationChannel.PUSH],
        priority="normal",
        subject_key="notifications.request.submitted.subject",
        sms_template_code="REQUEST_SUBMITTED"
    ),
    EventType.REQUEST_APPROVED: NotificationConfig(
        template_code="request_approved",
        channels=[NotificationChannel.EMAIL, NotificationChannel.SMS, NotificationChannel.PUSH],
        priority="high",
        subject_key="notifications.request.approved.subject",
        sms_template_code="REQUEST_APPROVED"
    ),
    EventType.REQUEST_REJECTED: NotificationConfig(
        template_code="request_rejected",
        channels=[NotificationChannel.EMAIL, NotificationChannel.SMS],
        priority="high",
        subject_key="notifications.request.rejected.subject",
        sms_template_code="REQUEST_REJECTED"
    ),
    EventType.REQUEST_COMPLETED: NotificationConfig(
        template_code="request_completed",
        channels=[NotificationChannel.EMAIL, NotificationChannel.SMS, NotificationChannel.PUSH],
        priority="high",
        subject_key="notifications.request.completed.subject",
        sms_template_code="REQUEST_COMPLETED"
    ),
    EventType.REQUEST_DOCUMENTS_REQUIRED: NotificationConfig(
        template_code="documents_required",
        channels=[NotificationChannel.EMAIL, NotificationChannel.SMS],
        priority="high",
        subject_key="notifications.request.documents_required.subject",
        sms_template_code="DOCUMENTS_REQUIRED"
    ),
    EventType.REQUEST_CANCELLED: NotificationConfig(
        template_code="request_cancelled",
        channels=[NotificationChannel.EMAIL, NotificationChannel.SMS],
        priority="normal",
        subject_key="notifications.request.cancelled.subject",
        sms_template_code="REQUEST_CANCELLED"
    ),

    # Document Events
    EventType.DOCUMENT_VALIDATED: NotificationConfig(
        template_code="document_validated",
        channels=[NotificationChannel.EMAIL, NotificationChannel.SMS, NotificationChannel.PUSH],
        priority="normal",
        subject_key="notifications.document.validated.subject",
        sms_template_code="DOCUMENT_VALIDATED"
    ),
    EventType.DOCUMENT_REJECTED: NotificationConfig(
        template_code="document_rejected",
        channels=[NotificationChannel.EMAIL, NotificationChannel.SMS],
        priority="high",
        subject_key="notifications.document.rejected.subject",
        sms_template_code="DOCUMENT_REJECTED"
    ),

    # Appointment Events
    EventType.APPOINTMENT_BOOKED: NotificationConfig(
        template_code="appointment_booked",
        channels=[NotificationChannel.EMAIL, NotificationChannel.SMS, NotificationChannel.PUSH],
        priority="high",
        subject_key="notifications.appointment.booked.subject",
        sms_template_code="APPOINTMENT_BOOKED"
    ),
    EventType.APPOINTMENT_CONFIRMED: NotificationConfig(
        template_code="appointment_confirmed",
        channels=[NotificationChannel.EMAIL, NotificationChannel.SMS, NotificationChannel.PUSH],
        priority="high",
        subject_key="notifications.appointment.confirmed.subject",
        sms_template_code="APPOINTMENT_CONFIRMED"
    ),
    EventType.APPOINTMENT_CANCELLED: NotificationConfig(
        template_code="appointment_cancelled",
        channels=[NotificationChannel.EMAIL, NotificationChannel.SMS],
        priority="high",
        subject_key="notifications.appointment.cancelled.subject",
        sms_template_code="APPOINTMENT_CANCELLED"
    ),
    EventType.APPOINTMENT_REMINDER: NotificationConfig(
        template_code="appointment_reminder",
        channels=[NotificationChannel.EMAIL, NotificationChannel.SMS, NotificationChannel.PUSH],
        priority="high",
        subject_key="notifications.appointment.reminder.subject",
        sms_template_code="APPOINTMENT_REMINDER"  # Reuses existing template from migration 012
    ),
    EventType.APPOINTMENT_COMPLETED: NotificationConfig(
        template_code="appointment_completed",
        channels=[NotificationChannel.EMAIL],
        priority="normal",
        subject_key="notifications.appointment.completed.subject"
    ),
    EventType.APPOINTMENT_NO_SHOW: NotificationConfig(
        template_code="appointment_no_show",
        channels=[NotificationChannel.EMAIL, NotificationChannel.SMS],
        priority="high",
        subject_key="notifications.appointment.no_show.subject",
        sms_template_code="APPOINTMENT_NO_SHOW"
    ),
    EventType.APPOINTMENT_RESCHEDULED: NotificationConfig(
        template_code="appointment_rescheduled",
        channels=[NotificationChannel.EMAIL, NotificationChannel.SMS, NotificationChannel.PUSH],
        priority="high",
        subject_key="notifications.appointment.rescheduled.subject",
        sms_template_code="APPOINTMENT_RESCHEDULED"
    ),

    # Declaration Events
    EventType.DECLARATION_SUBMITTED: NotificationConfig(
        template_code="declaration_submitted",
        channels=[NotificationChannel.EMAIL, NotificationChannel.PUSH],
        priority="normal",
        subject_key="notifications.declaration.submitted.subject"
    ),
    EventType.DECLARATION_VALIDATED: NotificationConfig(
        template_code="declaration_validated",
        channels=[NotificationChannel.EMAIL, NotificationChannel.SMS, NotificationChannel.PUSH],
        priority="high",
        subject_key="notifications.declaration.validated.subject",
        sms_template_code="DECLARATION_STATUS"  # Reuses existing template from migration 012
    ),
    EventType.DECLARATION_REJECTED: NotificationConfig(
        template_code="declaration_rejected",
        channels=[NotificationChannel.EMAIL, NotificationChannel.SMS],
        priority="high",
        subject_key="notifications.declaration.rejected.subject",
        sms_template_code="DECLARATION_STATUS"  # Reuses existing template from migration 012
    ),

    # SLA Events
    EventType.SLA_WARNING: NotificationConfig(
        template_code="sla_warning",
        channels=[NotificationChannel.EMAIL, NotificationChannel.PUSH],
        priority="high",
        subject_key="notifications.sla.warning.subject",
        requires_user_prefs=False  # Always notify agents
    ),
    EventType.SLA_BREACH: NotificationConfig(
        template_code="sla_breach",
        channels=[NotificationChannel.EMAIL, NotificationChannel.SMS, NotificationChannel.PUSH],
        priority="critical",
        subject_key="notifications.sla.breach.subject",
        requires_user_prefs=False,  # Always notify agents
        sms_template_code="SECURITY_ALERT"  # Reuses existing template from migration 012
    ),

    # User Security Events
    EventType.USER_PASSWORD_CHANGED: NotificationConfig(
        template_code="password_changed",
        channels=[NotificationChannel.EMAIL, NotificationChannel.SMS],
        priority="high",
        subject_key="notifications.user.password_changed.subject",
        requires_user_prefs=False,  # Always notify for security
        sms_template_code="SECURITY_PASSWORD_CHANGED"
    ),

    # User Registration Events
    EventType.USER_REGISTERED: NotificationConfig(
        template_code="user_welcome",
        channels=[NotificationChannel.EMAIL],
        priority="normal",
        subject_key="notifications.user.welcome.subject"
    ),

    # Batch Events
    EventType.BATCH_SUBMITTED: NotificationConfig(
        template_code="batch_submitted",
        channels=[NotificationChannel.EMAIL],
        priority="normal",
        subject_key="notifications.batch.submitted.subject"
    ),
    EventType.BATCH_COMPLETED: NotificationConfig(
        template_code="batch_completed",
        channels=[NotificationChannel.EMAIL],
        priority="high",
        subject_key="notifications.batch.completed.subject"
    ),

    # License Events
    EventType.LICENSE_ISSUED: NotificationConfig(
        template_code="LICENSE_GENERATED",
        channels=[NotificationChannel.EMAIL, NotificationChannel.SMS],
        priority="normal",
        subject_key="notifications.license.issued.subject",
        sms_template_code="LICENSE_GENERATED",
    ),

    # Field Inspection Events
    EventType.INSPECTION_COMPLETED: NotificationConfig(
        template_code="inspection_completed",
        channels=[NotificationChannel.EMAIL, NotificationChannel.PUSH],
        priority="normal",
        subject_key="notifications.inspection.completed.subject",
    ),
    EventType.MISE_EN_DEMEURE_ISSUED: NotificationConfig(
        template_code="mise_en_demeure_issued",
        channels=[NotificationChannel.EMAIL, NotificationChannel.SMS, NotificationChannel.PUSH],
        priority="high",
        subject_key="notifications.inspection.med.subject",
        sms_template_code="MISE_EN_DEMEURE",
    ),
    EventType.SEAL_PROPOSED: NotificationConfig(
        template_code="seal_proposed",
        channels=[NotificationChannel.EMAIL, NotificationChannel.PUSH],
        priority="high",
        subject_key="notifications.inspection.seal_proposed.subject",
        requires_user_prefs=False,  # Always notify supervisors
    ),
    EventType.SEAL_APPROVED: NotificationConfig(
        template_code="seal_approved",
        channels=[NotificationChannel.EMAIL, NotificationChannel.SMS, NotificationChannel.PUSH],
        priority="critical",
        subject_key="notifications.inspection.seal_approved.subject",
        sms_template_code="SEAL_APPROVED_SMS",
    ),

    # Field Mission Events
    EventType.MISSION_AGENT_ASSIGNED: NotificationConfig(
        template_code="mission_agent_assigned",
        channels=[NotificationChannel.EMAIL, NotificationChannel.SMS, NotificationChannel.PUSH],
        priority="high",
        subject_key="notifications.mission.assigned.subject",
        sms_template_code="MISSION_ASSIGNED",
        requires_user_prefs=False,
    ),
    EventType.MISSION_STARTED: NotificationConfig(
        template_code="mission_started",
        channels=[NotificationChannel.PUSH],
        priority="normal",
    ),
    EventType.MISSION_COMPLETED: NotificationConfig(
        template_code="mission_completed_summary",
        channels=[NotificationChannel.EMAIL],
        priority="normal",
        subject_key="notifications.mission.completed.subject",
    ),
    EventType.MISSION_CANCELLED: NotificationConfig(
        template_code="mission_cancelled",
        channels=[NotificationChannel.EMAIL, NotificationChannel.PUSH],
        priority="high",
        subject_key="notifications.mission.cancelled.subject",
        sms_template_code="MISSION_CANCELLED_SMS",
    ),
    EventType.MISSION_REMINDER: NotificationConfig(
        template_code="mission_daily_reminder",
        channels=[NotificationChannel.SMS, NotificationChannel.PUSH],
        priority="high",
        sms_template_code="MISSION_REMINDER",
        requires_user_prefs=False,
    ),
}

# Map template_code → push notification type for mobile deep linking
# Mobile parseNotificationDeepLink expects these type values
_TEMPLATE_TO_PUSH_TYPE: Dict[str, str] = {
    "inspection_completed": "INSPECTION_COMPLETED",
    "mise_en_demeure_issued": "MISE_EN_DEMEURE_ISSUED",
    "seal_proposed": "SEAL_PROPOSED",
    "seal_approved": "SEAL_APPROVED",
    "payment_completed": "PAYMENT_COMPLETED",
    "request_submitted": "REQUEST_SUBMITTED",
    "request_approved": "REQUEST_APPROVED",
    "request_rejected": "REQUEST_REJECTED",
    "mission_agent_assigned": "MISSION_AGENT_ASSIGNED",
    "mission_started": "MISSION_STARTED",
    "mission_cancelled": "MISSION_CANCELLED",
    "mission_daily_reminder": "MISSION_REMINDER",
}


class NotificationEventHandler:
    """
    Event handler that sends notifications based on events.

    Responsibilities:
    - Listen to relevant events from EventBus
    - Map events to notification templates
    - Send notifications via appropriate channels
    - Respect user notification preferences
    """

    def __init__(self):
        """Initialize the notification handler."""
        self.communication_service = CommunicationService()
        self._registered = False
        logger.info("NotificationEventHandler initialized")

    def register(self) -> None:
        """
        Register all event handlers with the EventBus.
        Should be called once at application startup.
        """
        if self._registered:
            logger.warning("NotificationEventHandler already registered")
            return

        for event_type in EVENT_NOTIFICATION_MAP.keys():
            EventBus.subscribe(event_type, self.handle_event)
            logger.debug(f"Registered notification handler for {event_type.value}")

        self._registered = True
        logger.info(
            f"NotificationEventHandler registered for {len(EVENT_NOTIFICATION_MAP)} event types"
        )

    async def handle_event(self, payload: EventPayload) -> None:
        """
        Handle an event and send appropriate notifications.

        Args:
            payload: The event payload containing all relevant data
        """
        event_type_str = payload.get("event_type", "")

        try:
            event_type = EventType(event_type_str)
        except ValueError:
            logger.warning(f"Unknown event type: {event_type_str}")
            return

        config = EVENT_NOTIFICATION_MAP.get(event_type)
        if not config:
            logger.debug(f"No notification config for {event_type_str}")
            return

        logger.info(
            f"Processing notification for {event_type_str}, "
            f"channels: {[c.value for c in config.channels]}"
        )

        # Extract user info from payload
        user_id = payload.get("user_id")
        user_email = payload.get("user_email")
        user_phone = payload.get("user_phone")
        user_name = payload.get("user_name")
        language = payload.get("preferred_language", "es")

        # Build template context from payload
        context = self._build_template_context(payload)

        # Send to each channel
        for channel in config.channels:
            try:
                await self._send_notification(
                    channel=channel,
                    config=config,
                    user_id=user_id,
                    user_email=user_email,
                    user_phone=user_phone,
                    user_name=user_name,
                    language=language,
                    context=context
                )
            except Exception as e:
                logger.error(
                    f"Failed to send {channel.value} notification for "
                    f"{event_type_str}: {e}"
                )

    async def _send_notification(
        self,
        channel: NotificationChannel,
        config: NotificationConfig,
        user_id: Optional[str],
        user_email: Optional[str],
        user_phone: Optional[str],
        user_name: Optional[str],
        language: str,
        context: Dict[str, Any]
    ) -> bool:
        """
        Send a notification via a specific channel.

        Args:
            channel: The notification channel
            config: Notification configuration
            user_id: User UUID (for push notifications)
            user_email: User's email address
            user_phone: User's phone number
            user_name: User's display name
            language: Preferred language (es, fr, en)
            context: Template context variables

        Returns:
            True if notification was sent successfully
        """
        if channel == NotificationChannel.EMAIL:
            if not user_email:
                logger.warning("Cannot send email: no email address")
                return False

            # Fetch DB template once for both subject and content
            db_template = await self._fetch_db_template(config.template_code)

            # Get subject based on language (DB first, fallback to hardcoded)
            subject = self._get_subject(config, language, context, db_template=db_template)

            # Render template content (DB first, fallback to inline)
            content = await self._render_template(
                config.template_code,
                language,
                context,
                db_template=db_template
            )

            if not content:
                logger.warning(
                    f"No template content for {config.template_code} ({language})"
                )
                return False

            # Build metadata with optional attachments
            # Attachments format: List[Tuple[str, bytes, str]] - (filename, content, mime_type)
            metadata: Dict[str, Any] = {
                "language": language,
                "user_name": user_name
            }

            # Extract attachments from context if present
            # These are passed from the event payload (e.g., PDF certificates)
            attachments: Optional[List[Tuple[str, bytes, str]]] = context.get("attachments")
            if attachments:
                metadata["attachments"] = attachments
                logger.info(f"Email includes {len(attachments)} attachment(s)")

            # Send via communication service (run in thread pool since it's sync)
            loop = asyncio.get_running_loop()
            success = await loop.run_in_executor(
                None,
                lambda: self.communication_service.send_communication(
                    channel=CommunicationType.EMAIL,
                    recipient=user_email,
                    subject=subject,
                    content=content,
                    metadata=metadata
                )
            )

            if success:
                attachment_info = f" with {len(attachments)} attachment(s)" if attachments else ""
                logger.info(f"Email sent to {user_email} ({config.template_code}){attachment_info}")
            return success

        elif channel == NotificationChannel.SMS:
            if not user_phone:
                logger.debug("Cannot send SMS: no phone number")
                return False

            # Use specific SMS template code if defined, otherwise fall back to email template code
            sms_template_code = config.sms_template_code or config.template_code.upper()

            # Send SMS via SmsSendingService
            try:
                sms_service = get_sms_sending_service()
                async with db_manager.get_connection() as db:
                    result = await sms_service.send_sms(
                        db=db,
                        phone=user_phone,
                        template_code=sms_template_code,
                        variables=context,
                        language=language
                    )

                if result.success:
                    logger.info(
                        f"SMS sent to {user_phone} "
                        f"(template: {sms_template_code}, message_id: {result.message_id})"
                    )
                    return True
                else:
                    logger.warning(
                        f"SMS failed for {user_phone}: {result.error} "
                        f"(template: {sms_template_code})"
                    )
                    return False

            except Exception as e:
                logger.error(f"SMS sending error for {user_phone}: {e}")
                return False

        elif channel == NotificationChannel.PUSH:
            if not user_id:
                logger.debug("Cannot send push: no user_id")
                return False

            # Get notification title and body
            db_template = await self._fetch_db_template(config.template_code)
            title = self._get_subject(config, language, context, db_template=db_template)
            body = await self._get_push_body(config, language, context)

            # Send push notification via PushSendingService
            try:
                push_service = get_push_sending_service()

                if not push_service.is_available():
                    logger.warning("[PUSH] Firebase not available, skipping")
                    return False

                async with db_manager.get_connection() as db:
                    # Map template_code to notification type for mobile deep linking
                    push_type = _TEMPLATE_TO_PUSH_TYPE.get(
                        config.template_code, config.template_code.upper()
                    )

                    result = await push_service.send_to_user(
                        db=db,
                        user_id=user_id,
                        title=title,
                        body=body,
                        data={
                            "type": push_type,
                            "template_code": config.template_code,
                            "priority": config.priority,
                            **{k: str(v) for k, v in context.items() if v is not None and isinstance(v, (str, int, float))}
                        }
                    )

                if result.success:
                    logger.info(
                        f"Push sent to user {user_id} "
                        f"(template: {config.template_code}, message_id: {result.message_id})"
                    )
                    return True
                else:
                    logger.debug(
                        f"Push failed for user {user_id}: {result.error} "
                        f"(template: {config.template_code})"
                    )
                    return False

            except Exception as e:
                logger.error(f"Push sending error for user {user_id}: {e}")
                return False

        elif channel == NotificationChannel.IN_APP:
            # In-app notification would be implemented here
            logger.debug(f"In-app notification queued ({config.template_code})")
            # TODO: Implement in-app notifications
            return True

        return False

    def _build_template_context(self, payload: EventPayload) -> Dict[str, Any]:
        """
        Build template context from event payload.

        Provides both new-style variable names (appointment_date, receipt_number)
        AND legacy names (date, time, reference) for backwards compatibility
        with existing SMS templates from migration 012.

        Args:
            payload: Event payload

        Returns:
            Dictionary of template variables
        """
        from datetime import datetime

        # Get appointment date/time
        appointment_date = payload.get("appointment_date")
        appointment_time = payload.get("appointment_time")

        # Generate formatted date for payments (PAYMENT_RECEIVED uses {{date}})
        # Priority: payload.date > payload.timestamp > now()
        payment_date = payload.get("date")
        if not payment_date:
            if payload.get("timestamp"):
                try:
                    ts = payload.get("timestamp")
                    if isinstance(ts, str):
                        payment_date = ts[:10]  # Extract YYYY-MM-DD
                    elif isinstance(ts, datetime):
                        payment_date = ts.strftime("%d/%m/%Y")
                except Exception:
                    payment_date = datetime.now().strftime("%d/%m/%Y")
            else:
                payment_date = datetime.now().strftime("%d/%m/%Y")

        return {
            # User info
            "user_name": payload.get("user_name", "Usuario"),
            "user_email": payload.get("user_email", ""),

            # Payment info - new style
            "amount": payload.get("amount"),
            "currency": payload.get("currency", "XAF"),
            "payment_method": payload.get("payment_method"),
            "receipt_number": payload.get("receipt_number"),
            "payment_id": payload.get("payment_id"),

            # Reference: service request reference first, then payment reference, then receipt
            "reference": payload.get("reference") or payload.get("payment_reference") or payload.get("receipt_number"),
            "payment_reference": payload.get("payment_reference"),
            "request_reference": payload.get("request_reference"),
            "date": payment_date,  # For PAYMENT_RECEIVED {{date}}

            # Request info
            "request_id": payload.get("request_id"),
            "service_code": payload.get("service_code"),
            "workflow_code": payload.get("workflow_code"),
            "service": payload.get("workflow_code"),  # For APPOINTMENT_REMINDER {{service}}

            # Document info
            "document_type": payload.get("document_type"),
            "file_name": payload.get("file_name"),

            # Appointment info - new style
            "appointment_date": appointment_date,
            "appointment_time": appointment_time,
            "location": payload.get("location"),

            # Appointment reschedule info (for APPOINTMENT_RESCHEDULED)
            "old_date": payload.get("old_date"),
            "old_time": payload.get("old_time"),
            "new_date": payload.get("new_date"),
            "new_time": payload.get("new_time"),

            # Appointment info - legacy style (for APPOINTMENT_REMINDER template)
            # Note: Only set these if we have appointment data (not payment date)
            "time": appointment_time,  # For {{time}} in SMS templates

            # Reason/notes
            "reason": payload.get("reason"),
            "notes": payload.get("notes"),

            # Timestamp
            "timestamp": payload.get("timestamp"),

            # Attachments for email (List[Tuple[filename, bytes, mime_type]])
            # Used for PDF certificates, receipts, etc.
            "attachments": payload.get("attachments"),

            # Batch info
            "batch_id": payload.get("batch_id"),
            "batch_reference": payload.get("batch_reference"),
            "total_items": payload.get("total_items"),
            "items_count": payload.get("items_count"),
            "beneficiary_names": payload.get("beneficiary_names", []),

            # Verification URL (HMAC-signed link for receipt/request verification)
            "verification_url": payload.get("verification_url"),

            # Global template variables
            "current_year": str(datetime.now().year),
            "site_url": getattr(settings, 'FRONTEND_URL', 'https://taxasge.emacsah.com').rstrip('/'),

            # Any additional metadata
            **(payload.get("metadata") or {}),
        }

    async def _fetch_db_template(self, template_code: str) -> Optional[Dict[str, Any]]:
        """
        Fetch email template from the database.

        Returns:
            Dict with html_content, subject_es/fr/en or None if not found
        """
        try:
            async with db_manager.get_connection() as db:
                row = await db.fetchrow(
                    "SELECT html_content, subject_es, subject_fr, subject_en "
                    "FROM email_templates "
                    "WHERE template_code = $1 AND is_active = true",
                    template_code
                )
                if row:
                    return dict(row)
        except Exception as e:
            logger.warning(f"DB template fetch failed for '{template_code}': {e}")
        return None

    def _get_subject(
        self,
        config: NotificationConfig,
        language: str,
        context: Dict[str, Any],
        db_template: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Get email subject from DB template.

        Args:
            config: Notification configuration
            language: Language code
            context: Template context
            db_template: Optional DB template row

        Returns:
            Email subject string from DB, or generic fallback
        """
        if db_template:
            lang_key = f"subject_{language}"
            db_subject = db_template.get(lang_key) or db_template.get("subject_es")
            if db_subject:
                return db_subject

        logger.warning(f"No DB subject for template '{config.template_code}' ({language})")
        return "Facil Platform - Notificación"

    async def _render_template(
        self,
        template_code: str,
        language: str,
        context: Dict[str, Any],
        db_template: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Render email template from DB (email_templates table).

        No inline fallback — all email templates must exist in the database.

        Args:
            template_code: Template identifier
            language: Language code
            context: Template variables
            db_template: Optional pre-fetched DB template row

        Returns:
            Rendered HTML content or None if template not found
        """
        if not db_template or not db_template.get("html_content"):
            logger.warning(
                f"No DB email template for '{template_code}' — "
                f"email will NOT be sent. Create it in email_templates table."
            )
            return None

        try:
            import re
            html = db_template["html_content"]

            # Format amount for display before substitution
            render_context = dict(context)
            if render_context.get("amount") is not None:
                try:
                    amt = float(render_context["amount"])
                    render_context["amount"] = f"{int(amt):,}".replace(",", " ")
                except (ValueError, TypeError):
                    pass

            # Substitute {{var}} with context values
            for key, value in render_context.items():
                if value is not None and not isinstance(value, (list, dict, tuple, bytes)):
                    html = html.replace("{{" + key + "}}", str(value))

            # Clean any unreplaced {{variables}}
            html = re.sub(r'\{\{[a-zA-Z_]+\}\}', '', html)

            logger.debug(f"Rendered DB template '{template_code}' for language '{language}'")
            return html
        except Exception as e:
            logger.error(f"Failed to render DB template '{template_code}': {e}")
            return None

    async def _get_push_body(
        self,
        config: NotificationConfig,
        language: str,
        context: Dict[str, Any]
    ) -> str:
        """
        Get push notification body text from DB email template.

        Strips HTML tags and truncates for push notification limits.
        """
        import re

        # Fetch DB template and extract plain text from HTML
        db_template = await self._fetch_db_template(config.template_code)
        if db_template and db_template.get("html_content"):
            html = db_template["html_content"]

            # Substitute variables
            render_context = dict(context)
            if render_context.get("amount") is not None:
                try:
                    amt = float(render_context["amount"])
                    render_context["amount"] = f"{int(amt):,}".replace(",", " ")
                except (ValueError, TypeError):
                    pass

            for key, value in render_context.items():
                if value is not None and not isinstance(value, (list, dict, tuple, bytes)):
                    html = html.replace("{{" + key + "}}", str(value))

            html = re.sub(r'\{\{[a-zA-Z_]+\}\}', '', html)

            # Strip HTML to plain text
            text = re.sub(r'<br\s*/?>', ' ', html)
            text = re.sub(r'<[^>]+>', '', text)
            text = re.sub(r'\s+', ' ', text).strip()

            # Truncate for push notification
            if len(text) > 180:
                text = text[:177] + "..."
            return text

        # Generic fallback if no DB template
        return "Tiene una nueva notificación de Facil Platform."


# =============================================================================
# REGISTRATION FUNCTION
# =============================================================================

def register_notification_handlers() -> NotificationEventHandler:
    """
    Register all notification handlers with the EventBus.
    Should be called once at application startup.

    Returns:
        The registered NotificationEventHandler instance
    """
    handler = NotificationEventHandler()
    handler.register()
    return handler
