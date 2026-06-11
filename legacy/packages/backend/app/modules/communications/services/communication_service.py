"""
Communication Service - Orchestrates all communication channels

Handles routing to appropriate communication channel:
- Email (implemented)
- SMS (future)
- Push notifications (future)
- Webhooks (future)

Module: Communications
Architecture: 3-tier (Routes → Services → External APIs)
"""

from typing import Optional, Dict, Any, List, Tuple
from loguru import logger

from app.modules.communications.models.communication import (
    CommunicationType,
    EmailTemplate,
)
from app.modules.communications.services.email_service import get_email_service


class CommunicationService:
    """
    Orchestrates communication across multiple channels

    Responsibilities:
    - Route communications to appropriate channel
    - Log communication attempts
    - Handle failures and retries (future)
    - Track delivery status (future)
    """

    def __init__(self):
        """Initialize communication service"""
        self.email_service = get_email_service()
        logger.info("CommunicationService initialized")

    def send_communication(
        self,
        channel: CommunicationType,
        recipient: str,
        subject: Optional[str],
        content: str,
        template: Optional[EmailTemplate] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Send communication via specified channel

        Args:
            channel: Communication channel type
            recipient: Recipient (email, phone, device_token)
            subject: Subject (for email)
            content: Message content
            template: Template used (for email)
            metadata: Additional metadata

        Returns:
            bool: True if sent successfully, False otherwise
        """
        try:
            if channel == CommunicationType.EMAIL:
                return self._send_email(recipient, subject, content, metadata)

            elif channel == CommunicationType.SMS:
                logger.warning("SMS communication not yet implemented")
                return False

            elif channel == CommunicationType.PUSH:
                logger.warning("Push notification not yet implemented")
                return False

            elif channel == CommunicationType.WEBHOOK:
                logger.warning("Webhook communication not yet implemented")
                return False

            else:
                logger.error(f"Unknown communication channel: {channel}")
                return False

        except Exception as e:
            logger.error(f"Error sending {channel} communication: {str(e)}")
            return False

    def _send_email(
        self,
        recipient: str,
        subject: Optional[str],
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Send email communication

        Args:
            recipient: Email address
            subject: Email subject
            content: HTML content
            metadata: Additional metadata including:
                - body_text: Optional plain text version
                - attachments: Optional list of tuples (filename, bytes, mime_type)

        Returns:
            bool: True if sent successfully
        """
        if not subject:
            logger.error("Email subject is required")
            return False

        # Extract plain text from metadata if available
        body_text = metadata.get("body_text") if metadata else None

        # Extract attachments from metadata if available
        # Format: List[Tuple[str, bytes, str]] - (filename, content, mime_type)
        attachments: Optional[List[Tuple[str, bytes, str]]] = None
        if metadata and "attachments" in metadata:
            attachments = metadata.get("attachments")
            if attachments:
                logger.info(f"Email includes {len(attachments)} attachment(s)")

        return self.email_service.send_email(
            to_email=recipient,
            subject=subject,
            body_html=content,
            body_text=body_text,
            attachments=attachments,
        )

    # ========================================================================
    # CONVENIENCE METHODS FOR COMMON USE CASES
    # ========================================================================

    def send_verification_email(
        self, email: str, code: str, user_name: Optional[str] = None
    ) -> bool:
        """Send email verification code"""
        return self.email_service.send_verification_code(email, code, user_name)

    def send_password_reset_email(
        self, email: str, reset_token: str, user_name: Optional[str] = None
    ) -> bool:
        """Send password reset email"""
        return self.email_service.send_password_reset_email(email, reset_token, user_name)

    def send_password_reset_confirmation_email(
        self, email: str, user_name: Optional[str] = None
    ) -> bool:
        """Send password reset confirmation"""
        return self.email_service.send_password_reset_confirmation(email, user_name)

    def send_2fa_email(
        self, email: str, code: str, user_name: Optional[str] = None
    ) -> bool:
        """Send 2FA code via email"""
        return self.email_service.send_2fa_code(email, code, user_name)

    def send_account_lockout_email(
        self, email: str, user_name: Optional[str] = None, locked_until = None
    ) -> bool:
        """Send account lockout notification"""
        return self.email_service.send_account_lockout_notification(
            email, user_name, locked_until
        )