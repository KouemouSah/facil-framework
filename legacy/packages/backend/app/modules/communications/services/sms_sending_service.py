"""
SMS Sending Service - Centralized async SMS sending
====================================================

Provides a unified async interface for sending SMS messages.
Used by NotificationEventHandler and other components.

This service:
- Fetches SMS templates from database
- Renders templates with variables
- Gets provider credentials from database
- Sends via Infobip (or mock for testing)

@module communications/services/sms_sending_service
@version 1.0.0
"""

import asyncpg
from typing import Optional, Dict, Any
from dataclasses import dataclass
from loguru import logger

from .sms_template_service import SmsTemplateService
from .sms_provider_service import SmsService, SmsResult, SmsDeliveryStatus
from .provider_settings_service import ProviderSettingsService
from ..models.sms_template import SmsTemplateRenderRequest


@dataclass
class SmsSendResult:
    """Result of an SMS send operation."""
    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None
    template_code: Optional[str] = None
    phone: Optional[str] = None


class SmsSendingService:
    """
    Centralized service for sending SMS messages.

    Usage:
        service = SmsSendingService()
        result = await service.send_sms(
            db=db_connection,
            phone="+240222123456",
            template_code="PAYMENT_RECEIVED",
            variables={"amount": "5000", "reference": "REF-123"},
            language="es"
        )
    """

    def __init__(self):
        self.template_service = SmsTemplateService()
        self.provider_service = ProviderSettingsService()
        self._sms_service: Optional[SmsService] = None
        self._cached_credentials: Optional[Dict[str, Any]] = None

    async def send_sms(
        self,
        db: asyncpg.Connection,
        phone: str,
        template_code: str,
        variables: Dict[str, Any],
        language: str = "es"
    ) -> SmsSendResult:
        """
        Send an SMS using a database template.

        Args:
            db: Database connection
            phone: Recipient phone number (E.164 format preferred)
            template_code: SMS template code (e.g., "PAYMENT_RECEIVED")
            variables: Template variables for substitution
            language: Language code (es, fr, en)

        Returns:
            SmsSendResult with success status and details
        """
        if not phone:
            logger.warning("[SMS] No phone number provided")
            return SmsSendResult(
                success=False,
                error="No phone number provided",
                template_code=template_code
            )

        try:
            # Step 1: Get and validate template
            logger.debug(f"[SMS] Fetching template: {template_code}")
            template = await self.template_service.get_template_by_code(db, template_code)

            if not template:
                logger.error(f"[SMS] Template not found: {template_code}")
                return SmsSendResult(
                    success=False,
                    error=f"Template not found: {template_code}",
                    template_code=template_code,
                    phone=phone
                )

            if not template.is_active:
                logger.warning(f"[SMS] Template inactive: {template_code}")
                return SmsSendResult(
                    success=False,
                    error=f"Template is inactive: {template_code}",
                    template_code=template_code,
                    phone=phone
                )

            # Step 2: Render template
            logger.debug(f"[SMS] Rendering template with language={language}")
            render_request = SmsTemplateRenderRequest(
                template_code=template_code,
                language=language,
                variables=variables
            )

            try:
                rendered = await self.template_service.render_template(db, render_request)
            except ValueError as e:
                logger.error(f"[SMS] Template render error: {e}")
                return SmsSendResult(
                    success=False,
                    error=f"Template render error: {str(e)}",
                    template_code=template_code,
                    phone=phone
                )

            # Step 3: Get SMS provider credentials
            credentials = await self._get_sms_credentials(db)
            if not credentials:
                logger.error("[SMS] No SMS provider credentials configured")
                return SmsSendResult(
                    success=False,
                    error="No SMS provider credentials configured",
                    template_code=template_code,
                    phone=phone
                )

            # Step 4: Send SMS
            sms_service = self._get_sms_service(credentials)
            logger.info(f"[SMS] Sending to {phone}, template={template_code}")

            result = sms_service.send_sms(
                to=phone,
                message=rendered.rendered_content
            )

            if result.success:
                logger.info(
                    f"[SMS] SUCCESS: Sent to {phone}, "
                    f"message_id={result.message_id}, "
                    f"template={template_code}"
                )
                return SmsSendResult(
                    success=True,
                    message_id=result.message_id,
                    template_code=template_code,
                    phone=phone
                )
            else:
                logger.error(
                    f"[SMS] FAILED: {phone}, "
                    f"error={result.error}, "
                    f"template={template_code}"
                )
                return SmsSendResult(
                    success=False,
                    error=result.error or "SMS send failed",
                    template_code=template_code,
                    phone=phone
                )

        except Exception as e:
            logger.exception(f"[SMS] Unexpected error: {e}")
            return SmsSendResult(
                success=False,
                error=f"Unexpected error: {str(e)}",
                template_code=template_code,
                phone=phone
            )

    async def send_raw_sms(
        self,
        db: asyncpg.Connection,
        phone: str,
        message: str
    ) -> SmsSendResult:
        """
        Send a raw SMS message without template.

        Args:
            db: Database connection (for credentials)
            phone: Recipient phone number
            message: Raw SMS content

        Returns:
            SmsSendResult with success status
        """
        if not phone:
            return SmsSendResult(success=False, error="No phone number provided")

        if not message:
            return SmsSendResult(success=False, error="No message content provided")

        try:
            credentials = await self._get_sms_credentials(db)
            if not credentials:
                return SmsSendResult(
                    success=False,
                    error="No SMS provider credentials configured",
                    phone=phone
                )

            sms_service = self._get_sms_service(credentials)
            result = sms_service.send_sms(to=phone, message=message)

            return SmsSendResult(
                success=result.success,
                message_id=result.message_id,
                error=result.error,
                phone=phone
            )

        except Exception as e:
            logger.exception(f"[SMS] Raw send error: {e}")
            return SmsSendResult(
                success=False,
                error=str(e),
                phone=phone
            )

    async def _get_sms_credentials(
        self,
        db: asyncpg.Connection
    ) -> Optional[Dict[str, Any]]:
        """Get SMS provider credentials from database."""
        try:
            return await self.provider_service.get_active_sms_credentials(db)
        except Exception as e:
            logger.error(f"[SMS] Failed to get credentials: {e}")
            return None

    def _get_sms_service(self, credentials: Dict[str, Any]) -> SmsService:
        """Get or create SMS service with credentials."""
        api_key = credentials.get("api_key")

        # Create new service (could add caching if needed)
        return SmsService(
            provider="infobip",
            api_key=api_key,
            base_url="y45e8g.api.infobip.com",
            sender_id="Facil"
        )


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_sms_sending_service: Optional[SmsSendingService] = None


def get_sms_sending_service() -> SmsSendingService:
    """Get singleton SmsSendingService instance."""
    global _sms_sending_service
    if _sms_sending_service is None:
        _sms_sending_service = SmsSendingService()
    return _sms_sending_service
