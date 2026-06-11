"""
WhatsApp Service for TaxasGE Backend
Handles WhatsApp Business API integration via webhook configurations

Module: Communications
Author: TaxasGE Development Team
"""

import asyncpg
import httpx
from typing import Optional, List, Dict, Any
from datetime import datetime
from loguru import logger
from enum import Enum

from ..models.webhook import WebhookResponse, AuthType
from ..repositories.webhook_repository import WebhookRepository


# =============================================================================
# EVENT CONSTANTS - Webhook Triggers
# =============================================================================

class WhatsAppEvents(str, Enum):
    """WhatsApp webhook event types that trigger notifications"""
    # User lifecycle events
    USER_REGISTERED = "user.registered"
    USER_VERIFIED = "user.verified"
    USER_PASSWORD_RESET = "user.password_reset"

    # Declaration events
    DECLARATION_SUBMITTED = "declaration.submitted"
    DECLARATION_APPROVED = "declaration.approved"
    DECLARATION_REJECTED = "declaration.rejected"
    DECLARATION_STATUS_CHANGED = "declaration.status_changed"

    # Payment events
    PAYMENT_PENDING = "payment.pending"
    PAYMENT_SUCCESS = "payment.success"
    PAYMENT_FAILED = "payment.failed"
    PAYMENT_REFUNDED = "payment.refunded"

    # Appointment events
    APPOINTMENT_SCHEDULED = "appointment.scheduled"
    APPOINTMENT_REMINDER = "appointment.reminder"
    APPOINTMENT_CANCELLED = "appointment.cancelled"

    # Support ticket events
    TICKET_CREATED = "support.ticket_created"
    TICKET_UPDATED = "support.ticket_updated"
    TICKET_RESOLVED = "support.ticket_resolved"
    TICKET_RESPONSE = "support.ticket_response"


# =============================================================================
# WHATSAPP TEMPLATE NAMES
# =============================================================================

class WhatsAppTemplates(str, Enum):
    """Pre-approved WhatsApp Business template names"""
    WELCOME = "welcome_message"
    VERIFICATION_CODE = "verification_code"
    DECLARATION_STATUS = "declaration_status_update"
    PAYMENT_CONFIRMATION = "payment_confirmation"
    PAYMENT_FAILED = "payment_failed_notification"
    APPOINTMENT_REMINDER = "appointment_reminder"
    SUPPORT_TICKET_UPDATE = "support_ticket_update"
    PASSWORD_RESET = "password_reset_code"


# =============================================================================
# WHATSAPP SERVICE CLASS
# =============================================================================

class WhatsAppService:
    """
    Service for sending WhatsApp messages via Meta Business API

    Uses webhook configurations to manage API credentials and templates.
    All messages are sent through the webhook system for logging and retry support.
    """

    # Meta Graph API base URL
    GRAPH_API_BASE = "https://graph.facebook.com/v17.0"

    def __init__(self):
        self.repository = WebhookRepository()
        self._http_client: Optional[httpx.AsyncClient] = None

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client with connection pooling"""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=30.0)
        return self._http_client

    async def close(self):
        """Close HTTP client connection"""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()

    # =========================================================================
    # TEMPLATE MESSAGE METHODS
    # =========================================================================

    async def send_template_message(
        self,
        db: asyncpg.Connection,
        to_phone: str,
        template_name: str,
        language_code: str = "es",
        variables: Optional[Dict[str, Any]] = None,
        event_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send a WhatsApp template message

        Args:
            db: Database connection
            to_phone: Recipient phone number (with country code)
            template_name: WhatsApp pre-approved template name
            language_code: Language code (es, fr, en)
            variables: Template variable substitutions
            event_type: Event that triggered this message

        Returns:
            Dict with success status and response details
        """
        try:
            phone = self._normalize_phone_number(to_phone)
            components = self._build_template_components(variables or {})

            payload = {
                "messaging_product": "whatsapp",
                "to": phone,
                "type": "template",
                "template": {
                    "name": template_name,
                    "language": {"code": language_code},
                    "components": components
                }
            }

            # Find active WhatsApp webhook configuration
            webhooks = await self.repository.find_by_event(
                db,
                event_type or WhatsAppEvents.USER_REGISTERED.value
            )

            whatsapp_webhook = None
            for webhook in webhooks:
                if webhook.get("webhook_type") == "whatsapp":
                    whatsapp_webhook = webhook
                    break

            if not whatsapp_webhook:
                logger.warning(f"No active WhatsApp webhook found for event: {event_type}")
                return {
                    "success": False,
                    "error": "No WhatsApp webhook configuration found"
                }

            result = await self._execute_whatsapp_request(
                whatsapp_webhook,
                payload,
                event_type
            )

            return result

        except Exception as e:
            logger.error(f"Failed to send WhatsApp template message: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    async def send_text_message(
        self,
        db: asyncpg.Connection,
        to_phone: str,
        message: str,
        preview_url: bool = False
    ) -> Dict[str, Any]:
        """
        Send a plain text WhatsApp message (for customer-initiated conversations)
        """
        try:
            phone = self._normalize_phone_number(to_phone)

            payload = {
                "messaging_product": "whatsapp",
                "to": phone,
                "type": "text",
                "text": {
                    "body": message,
                    "preview_url": preview_url
                }
            }

            webhooks = await self.repository.find_all(
                db,
                limit=1,
                webhook_type="whatsapp",
                is_active=True
            )

            if not webhooks:
                return {
                    "success": False,
                    "error": "No WhatsApp webhook configuration found"
                }

            result = await self._execute_whatsapp_request(webhooks[0], payload, "text_message")
            return result

        except Exception as e:
            logger.error(f"Failed to send WhatsApp text message: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    # =========================================================================
    # CONVENIENCE METHODS FOR COMMON NOTIFICATIONS
    # =========================================================================

    async def send_welcome_message(
        self,
        db: asyncpg.Connection,
        to_phone: str,
        user_name: str,
        language: str = "es"
    ) -> Dict[str, Any]:
        """Send welcome message to newly registered user"""
        return await self.send_template_message(
            db=db,
            to_phone=to_phone,
            template_name=WhatsAppTemplates.WELCOME.value,
            language_code=language,
            variables={"user_name": user_name},
            event_type=WhatsAppEvents.USER_REGISTERED.value
        )

    async def send_verification_code(
        self,
        db: asyncpg.Connection,
        to_phone: str,
        code: str,
        language: str = "es"
    ) -> Dict[str, Any]:
        """Send verification code via WhatsApp"""
        return await self.send_template_message(
            db=db,
            to_phone=to_phone,
            template_name=WhatsAppTemplates.VERIFICATION_CODE.value,
            language_code=language,
            variables={"verification_code": code},
            event_type=WhatsAppEvents.USER_VERIFIED.value
        )

    async def send_declaration_status_update(
        self,
        db: asyncpg.Connection,
        to_phone: str,
        declaration_reference: str,
        new_status: str,
        language: str = "es"
    ) -> Dict[str, Any]:
        """Send declaration status update notification"""
        status_translations = {
            "es": {
                "submitted": "Enviada",
                "processing": "En Proceso",
                "accepted": "Aceptada",
                "rejected": "Rechazada",
                "amended": "Modificada"
            },
            "fr": {
                "submitted": "Soumise",
                "processing": "En cours",
                "accepted": "Acceptee",
                "rejected": "Rejetee",
                "amended": "Modifiee"
            },
            "en": {
                "submitted": "Submitted",
                "processing": "Processing",
                "accepted": "Accepted",
                "rejected": "Rejected",
                "amended": "Amended"
            }
        }

        status_text = status_translations.get(language, status_translations["es"]).get(
            new_status.lower(), new_status
        )

        return await self.send_template_message(
            db=db,
            to_phone=to_phone,
            template_name=WhatsAppTemplates.DECLARATION_STATUS.value,
            language_code=language,
            variables={
                "declaration_reference": declaration_reference,
                "status": status_text
            },
            event_type=WhatsAppEvents.DECLARATION_STATUS_CHANGED.value
        )

    async def send_payment_confirmation(
        self,
        db: asyncpg.Connection,
        to_phone: str,
        amount: str,
        reference: str,
        payment_date: str,
        language: str = "es"
    ) -> Dict[str, Any]:
        """Send payment confirmation notification"""
        return await self.send_template_message(
            db=db,
            to_phone=to_phone,
            template_name=WhatsAppTemplates.PAYMENT_CONFIRMATION.value,
            language_code=language,
            variables={
                "amount": amount,
                "reference": reference,
                "date": payment_date
            },
            event_type=WhatsAppEvents.PAYMENT_SUCCESS.value
        )

    async def send_payment_failed(
        self,
        db: asyncpg.Connection,
        to_phone: str,
        amount: str,
        reference: str,
        reason: Optional[str] = None,
        language: str = "es"
    ) -> Dict[str, Any]:
        """Send payment failure notification"""
        return await self.send_template_message(
            db=db,
            to_phone=to_phone,
            template_name=WhatsAppTemplates.PAYMENT_FAILED.value,
            language_code=language,
            variables={
                "amount": amount,
                "reference": reference,
                "reason": reason or "Error en el procesamiento"
            },
            event_type=WhatsAppEvents.PAYMENT_FAILED.value
        )

    async def send_appointment_reminder(
        self,
        db: asyncpg.Connection,
        to_phone: str,
        appointment_date: str,
        appointment_time: str,
        location: str,
        service_name: str,
        language: str = "es"
    ) -> Dict[str, Any]:
        """Send appointment reminder notification"""
        return await self.send_template_message(
            db=db,
            to_phone=to_phone,
            template_name=WhatsAppTemplates.APPOINTMENT_REMINDER.value,
            language_code=language,
            variables={
                "date": appointment_date,
                "time": appointment_time,
                "location": location,
                "service": service_name
            },
            event_type=WhatsAppEvents.APPOINTMENT_REMINDER.value
        )

    async def send_support_ticket_update(
        self,
        db: asyncpg.Connection,
        to_phone: str,
        ticket_id: str,
        new_status: str,
        language: str = "es"
    ) -> Dict[str, Any]:
        """Send support ticket status update"""
        return await self.send_template_message(
            db=db,
            to_phone=to_phone,
            template_name=WhatsAppTemplates.SUPPORT_TICKET_UPDATE.value,
            language_code=language,
            variables={
                "ticket_id": ticket_id,
                "status": new_status
            },
            event_type=WhatsAppEvents.TICKET_UPDATED.value
        )

    # =========================================================================
    # PRIVATE HELPER METHODS
    # =========================================================================

    def _normalize_phone_number(self, phone: str) -> str:
        """Normalize phone number to E.164 format without + prefix"""
        cleaned = ''.join(c for c in phone if c.isdigit() or c == '+')
        if cleaned.startswith('+'):
            cleaned = cleaned[1:]
        # Add Equatorial Guinea country code if missing
        if not cleaned.startswith('240') and len(cleaned) == 9:
            cleaned = '240' + cleaned
        return cleaned

    def _build_template_components(
        self,
        variables: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Build WhatsApp template components from variables"""
        if not variables:
            return []

        body_params = []
        for key, value in variables.items():
            body_params.append({
                "type": "text",
                "text": str(value)
            })

        components = []
        if body_params:
            components.append({
                "type": "body",
                "parameters": body_params
            })

        return components

    async def _execute_whatsapp_request(
        self,
        webhook: Dict[str, Any],
        payload: Dict[str, Any],
        event_type: Optional[str]
    ) -> Dict[str, Any]:
        """Execute WhatsApp API request using webhook configuration"""
        try:
            client = await self._get_http_client()

            headers = dict(webhook.get("headers", {})) if webhook.get("headers") else {}
            headers.setdefault("Content-Type", "application/json")

            # Add authentication
            auth_type = webhook.get("auth_type")
            auth_config = webhook.get("auth_config", {})

            if auth_type == "bearer":
                bearer_token = auth_config.get("bearer_token")
                if bearer_token:
                    headers["Authorization"] = f"Bearer {bearer_token}"
            elif auth_type == "api_key":
                api_key = auth_config.get("api_key")
                api_key_header = auth_config.get("api_key_header", "X-API-Key")
                if api_key:
                    headers[api_key_header] = api_key

            response = await client.post(
                webhook.get("endpoint_url", ""),
                json=payload,
                headers=headers,
                timeout=webhook.get("timeout_seconds", 30)
            )

            response_text = response.text[:1000] if response.text else ""

            if response.status_code < 400:
                logger.info(
                    f"WhatsApp message sent successfully",
                    extra={
                        "to": payload.get("to"),
                        "event": event_type,
                        "status_code": response.status_code
                    }
                )
                return {
                    "success": True,
                    "status_code": response.status_code,
                    "response": response_text,
                    "message_id": self._extract_message_id(response_text)
                }
            else:
                logger.error(
                    f"WhatsApp API error: {response.status_code}",
                    extra={
                        "to": payload.get("to"),
                        "event": event_type,
                        "response": response_text
                    }
                )
                return {
                    "success": False,
                    "status_code": response.status_code,
                    "error": response_text
                }

        except httpx.TimeoutException:
            logger.error(f"WhatsApp request timeout")
            return {
                "success": False,
                "error": "Request timeout"
            }
        except httpx.RequestError as e:
            logger.error(f"WhatsApp request error: {str(e)}")
            return {
                "success": False,
                "error": f"Request error: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Unexpected WhatsApp error: {str(e)}")
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}"
            }

    def _extract_message_id(self, response_text: str) -> Optional[str]:
        """Extract message ID from WhatsApp API response"""
        try:
            import json
            data = json.loads(response_text)
            messages = data.get("messages", [])
            if messages and len(messages) > 0:
                return messages[0].get("id")
        except Exception:
            pass
        return None


# =============================================================================
# EVENT EMITTER INTEGRATION
# =============================================================================

class WhatsAppEventEmitter:
    """
    Event emitter for triggering WhatsApp notifications

    Usage:
        emitter = WhatsAppEventEmitter()
        await emitter.emit(db, WhatsAppEvents.PAYMENT_SUCCESS, {
            "phone": "+240222123456",
            "amount": "50,000 XAF",
            "reference": "PAY-2024-001"
        })
    """

    def __init__(self):
        self.whatsapp_service = WhatsAppService()

    async def emit(
        self,
        db: asyncpg.Connection,
        event: WhatsAppEvents,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Emit an event and trigger corresponding WhatsApp notification
        """
        phone = data.get("phone")
        if not phone:
            return {"success": False, "error": "Phone number required"}

        language = data.get("language", "es")

        if event == WhatsAppEvents.USER_REGISTERED:
            return await self.whatsapp_service.send_welcome_message(
                db, phone, data.get("user_name", "Usuario"), language
            )

        elif event == WhatsAppEvents.USER_VERIFIED:
            return await self.whatsapp_service.send_verification_code(
                db, phone, data.get("code", ""), language
            )

        elif event in [
            WhatsAppEvents.DECLARATION_SUBMITTED,
            WhatsAppEvents.DECLARATION_APPROVED,
            WhatsAppEvents.DECLARATION_REJECTED,
            WhatsAppEvents.DECLARATION_STATUS_CHANGED
        ]:
            return await self.whatsapp_service.send_declaration_status_update(
                db, phone,
                data.get("declaration_reference", ""),
                data.get("status", ""),
                language
            )

        elif event == WhatsAppEvents.PAYMENT_SUCCESS:
            return await self.whatsapp_service.send_payment_confirmation(
                db, phone,
                data.get("amount", ""),
                data.get("reference", ""),
                data.get("date", datetime.now().strftime("%Y-%m-%d")),
                language
            )

        elif event == WhatsAppEvents.PAYMENT_FAILED:
            return await self.whatsapp_service.send_payment_failed(
                db, phone,
                data.get("amount", ""),
                data.get("reference", ""),
                data.get("reason"),
                language
            )

        elif event == WhatsAppEvents.APPOINTMENT_REMINDER:
            return await self.whatsapp_service.send_appointment_reminder(
                db, phone,
                data.get("date", ""),
                data.get("time", ""),
                data.get("location", ""),
                data.get("service", ""),
                language
            )

        elif event in [
            WhatsAppEvents.TICKET_CREATED,
            WhatsAppEvents.TICKET_UPDATED,
            WhatsAppEvents.TICKET_RESOLVED,
            WhatsAppEvents.TICKET_RESPONSE
        ]:
            return await self.whatsapp_service.send_support_ticket_update(
                db, phone,
                data.get("ticket_id", ""),
                data.get("status", ""),
                language
            )

        else:
            logger.warning(f"Unhandled WhatsApp event: {event}")
            return {"success": False, "error": f"Unhandled event: {event}"}


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================

def get_whatsapp_service() -> WhatsAppService:
    """Get WhatsApp service instance"""
    return WhatsAppService()


def get_whatsapp_event_emitter() -> WhatsAppEventEmitter:
    """Get WhatsApp event emitter instance"""
    return WhatsAppEventEmitter()
