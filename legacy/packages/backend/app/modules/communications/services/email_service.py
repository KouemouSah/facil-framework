"""
Email Service for TaxasGE Backend
Handles email sending via SMTP with templating support

Module: Communications

Template Routing Strategy:
- LEGACY templates (Jinja2 files): verification_email, password_reset, etc.
- DATABASE templates: All other templates created via Admin UI
"""

import smtplib
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Optional, Dict, Any, Set, List, Tuple
from datetime import datetime
from pathlib import Path
import asyncpg
from loguru import logger

from app.modules.communications.services.template_service import get_template_service


# =============================================================================
# LEGACY TEMPLATE CODES
# These templates use the Jinja2 file-based system (templates/*.html)
# Any template NOT in this list will be fetched from the database
# =============================================================================
LEGACY_TEMPLATE_CODES: Set[str] = {
    "verification_email",
    "password_reset",
    "password_reset_confirmation",
    "2fa_code",
    "account_lockout",
    "agent_invitation",
    "admin_invitation",
}


class EmailService:
    """Service for sending emails via SMTP with template support"""

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        smtp_username: str,
        smtp_password: str,
        smtp_use_tls: bool = True,
        smtp_from_email: Optional[str] = None,
        smtp_from_name: str = "Facil Platform",
    ):
        """
        Initialize Email service

        Args:
            smtp_host: SMTP server hostname (e.g., smtp.gmail.com)
            smtp_port: SMTP server port (e.g., 587 for TLS)
            smtp_username: SMTP username (Gmail email)
            smtp_password: SMTP password (Gmail App Password)
            smtp_use_tls: Whether to use TLS (default True)
            smtp_from_email: From email address (defaults to smtp_username)
            smtp_from_name: From name displayed in email (default "Facil")
        """
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_username = smtp_username
        self.smtp_password = smtp_password
        self.smtp_use_tls = smtp_use_tls
        self.smtp_from_email = smtp_from_email or smtp_username
        self.smtp_from_name = smtp_from_name

        # Initialize template service
        self.template_service = get_template_service()

        # Validate configuration
        if not all([smtp_host, smtp_port, smtp_username, smtp_password]):
            logger.warning(
                "EmailService initialized with incomplete SMTP configuration. "
                "Some email features may not work."
            )

        logger.info(
            f"EmailService initialized: {smtp_host}:{smtp_port}, "
            f"from={self.smtp_from_email}, TLS={smtp_use_tls}"
        )

    def _create_smtp_connection(self) -> smtplib.SMTP:
        """
        Create and authenticate SMTP connection

        Returns:
            smtplib.SMTP: Authenticated SMTP connection

        Raises:
            smtplib.SMTPException: If connection or authentication fails
        """
        try:
            # Create SMTP connection
            server = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=10)

            if self.smtp_use_tls:
                server.starttls()

            # Authenticate
            server.login(self.smtp_username, self.smtp_password)

            return server

        except smtplib.SMTPException as e:
            logger.error(f"SMTP connection failed: {str(e)}")
            raise

    def send_email(
        self,
        to_email: str,
        subject: str,
        body_html: str,
        body_text: Optional[str] = None,
        attachments: Optional[List[Tuple[str, bytes, str]]] = None,
    ) -> bool:
        """
        Send an email with optional attachments

        Args:
            to_email: Recipient email address
            subject: Email subject
            body_html: Email body in HTML format
            body_text: Email body in plain text (optional, defaults to HTML stripped)
            attachments: Optional list of attachments as tuples:
                         (filename, content_bytes, mime_type)
                         Example: [("certificate.pdf", pdf_bytes, "application/pdf")]

        Returns:
            bool: True if email sent successfully, False otherwise
        """
        try:
            # Determine message structure based on attachments
            if attachments:
                # Mixed container for attachments + body
                message = MIMEMultipart("mixed")
                message["From"] = f"{self.smtp_from_name} <{self.smtp_from_email}>"
                message["To"] = to_email
                message["Subject"] = subject

                # Alternative container for text/html body
                body_part = MIMEMultipart("alternative")

                # Attach plain text version
                if body_text:
                    part_text = MIMEText(body_text, "plain", "utf-8")
                    body_part.attach(part_text)

                # Attach HTML version
                part_html = MIMEText(body_html, "html", "utf-8")
                body_part.attach(part_html)

                # Add body to main message
                message.attach(body_part)

                # Add attachments
                for filename, content, mime_type in attachments:
                    maintype, subtype = mime_type.split("/", 1)
                    attachment = MIMEBase(maintype, subtype)
                    attachment.set_payload(content)
                    encoders.encode_base64(attachment)
                    attachment.add_header(
                        "Content-Disposition",
                        "attachment",
                        filename=filename
                    )
                    message.attach(attachment)
                    logger.debug(f"Attached file: {filename} ({mime_type}, {len(content)} bytes)")

            else:
                # Simple alternative message (no attachments)
                message = MIMEMultipart("alternative")
                message["From"] = f"{self.smtp_from_name} <{self.smtp_from_email}>"
                message["To"] = to_email
                message["Subject"] = subject

                # Attach plain text version
                if body_text:
                    part_text = MIMEText(body_text, "plain", "utf-8")
                    message.attach(part_text)

                # Attach HTML version
                part_html = MIMEText(body_html, "html", "utf-8")
                message.attach(part_html)

            # Send email
            server = self._create_smtp_connection()
            server.sendmail(self.smtp_from_email, to_email, message.as_string())
            server.quit()

            attachment_info = f" with {len(attachments)} attachment(s)" if attachments else ""
            logger.info(f"Email sent successfully to {to_email}: {subject}{attachment_info}")
            return True

        except smtplib.SMTPException as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False

        except Exception as e:
            logger.error(f"Unexpected error sending email to {to_email}: {str(e)}")
            return False

    def send_verification_code(
        self,
        to_email: str,
        verification_code: str,
        user_name: Optional[str] = None,
        language: str = "es",
    ) -> bool:
        """
        Send email verification code

        Args:
            to_email: Recipient email address
            verification_code: 6-digit verification code
            user_name: User's name (optional)
            language: Language code (es/fr/en, default: es)

        Returns:
            bool: True if email sent successfully, False otherwise
        """
        from app.modules.communications.services.email_content import get_email_content

        content = get_email_content("verification_email", language)
        subject = content["subject"]

        html, plain_text = self.template_service.render_verification_email(
            user_name, verification_code, language
        )

        return self.send_email(to_email, subject, html, plain_text)

    def send_password_reset_email(
        self,
        to_email: str,
        reset_token: str,
        user_name: Optional[str] = None,
        language: str = "es",
    ) -> bool:
        """
        Send password reset email with reset link

        Args:
            to_email: Recipient email address
            reset_token: Password reset token
            user_name: User's name (optional)
            language: Language code (es/fr/en, default: es)

        Returns:
            bool: True if email sent successfully, False otherwise
        """
        from app.modules.communications.services.email_content import get_email_content
        from app.config import get_settings

        settings = get_settings()

        # Use configured frontend URL (production: taxasge.emacsah.com)
        frontend_url = settings.FRONTEND_URL

        # IMPORTANT: URL must match Next.js route structure
        reset_url = f"{frontend_url}/auth/reset-password/confirm?token={reset_token}"

        content = get_email_content("password_reset", language)
        subject = content["subject"]

        html, plain_text = self.template_service.render_password_reset_email(
            user_name, reset_url, language
        )

        return self.send_email(to_email, subject, html, plain_text)

    def send_password_reset_confirmation(
        self,
        to_email: str,
        user_name: Optional[str] = None,
        language: str = "es",
    ) -> bool:
        """
        Send password reset confirmation email

        Args:
            to_email: Recipient email address
            user_name: User's name (optional)
            language: Language code (es/fr/en, default: es)

        Returns:
            bool: True if email sent successfully, False otherwise
        """
        from app.modules.communications.services.email_content import get_email_content

        content = get_email_content("password_reset_confirmation", language)
        subject = content["subject"]

        html, plain_text = self.template_service.render_password_reset_confirmation_email(
            user_name, language
        )

        return self.send_email(to_email, subject, html, plain_text)

    def send_2fa_code(
        self,
        to_email: str,
        code: str,
        user_name: Optional[str] = None,
        language: str = "es",
    ) -> bool:
        """
        Send 2FA verification code via email (backup method)

        Args:
            to_email: Recipient email address
            code: 6-digit 2FA code
            user_name: User's name (optional)
            language: Language code (es/fr/en, default: es)

        Returns:
            bool: True if email sent successfully, False otherwise
        """
        from app.modules.communications.services.email_content import get_email_content

        content = get_email_content("2fa_code", language)
        subject = content["subject"]

        html, plain_text = self.template_service.render_2fa_code_email(
            user_name, code, language
        )

        return self.send_email(to_email, subject, html, plain_text)

    def send_account_lockout_notification(
        self,
        to_email: str,
        user_name: Optional[str] = None,
        locked_until: datetime = None,
        language: str = "es",
    ) -> bool:
        """
        Send account lockout notification email

        Args:
            to_email: Recipient email address
            user_name: User's name (optional)
            locked_until: Timestamp when account will be unlocked
            language: Language code (es/fr/en, default: es)

        Returns:
            bool: True if email sent successfully, False otherwise
        """
        from datetime import timezone as tz
        from app.modules.communications.services.email_content import get_email_content

        # Calculate remaining time
        if locked_until:
            remaining_minutes = int((locked_until - datetime.now(tz.utc)).total_seconds() / 60)
        else:
            remaining_minutes = 10

        content = get_email_content("account_lockout", language)
        subject = content["subject"]

        html, plain_text = self.template_service.render_account_lockout_email(
            user_name, remaining_minutes, language
        )

        return self.send_email(to_email, subject, html, plain_text)

    def send_agent_invitation(
        self,
        to_email: str,
        first_name: str,
        verification_code: str,
        language: str = "es",
    ) -> bool:
        """
        Send agent invitation email with verification code

        Args:
            to_email: Recipient email address
            first_name: Agent's first name
            verification_code: 6-digit verification code
            language: Language code (es/fr/en, default: es)

        Returns:
            bool: True if email sent successfully, False otherwise
        """
        from app.modules.communications.services.email_content import get_email_content
        from app.config import get_settings

        settings = get_settings()

        # Build activation URL
        frontend_url = settings.FRONTEND_URL
        activation_url = f"{frontend_url}/auth/activate-agent?email={to_email}&code={verification_code}"

        content = get_email_content("agent_invitation", language)
        subject = content["subject"]

        html, plain_text = self.template_service.render_invitation_email(
            user_name=first_name,
            verification_code=verification_code,
            activation_url=activation_url,
            invitation_type="agent",
            language=language,
        )

        return self.send_email(to_email, subject, html, plain_text)

    def send_admin_invitation(
        self,
        to_email: str,
        first_name: str,
        verification_code: str,
        language: str = "es",
    ) -> bool:
        """
        Send admin invitation email with verification code

        Args:
            to_email: Recipient email address
            first_name: Admin's first name
            verification_code: 6-digit verification code
            language: Language code (es/fr/en, default: es)

        Returns:
            bool: True if email sent successfully, False otherwise
        """
        from app.modules.communications.services.email_content import get_email_content
        from app.config import get_settings

        settings = get_settings()

        # Build activation URL
        frontend_url = settings.FRONTEND_URL
        activation_url = f"{frontend_url}/auth/activate-admin?email={to_email}&code={verification_code}"

        content = get_email_content("admin_invitation", language)
        subject = content["subject"]

        html, plain_text = self.template_service.render_invitation_email(
            user_name=first_name,
            verification_code=verification_code,
            activation_url=activation_url,
            invitation_type="admin",
            language=language,
        )

        return self.send_email(to_email, subject, html, plain_text)

    # =========================================================================
    # UNIFIED TEMPLATE SENDING (Legacy + Database routing)
    # =========================================================================

    async def send_with_template(
        self,
        db: asyncpg.Connection,
        template_code: str,
        to_email: str,
        variables: Optional[Dict[str, Any]] = None,
        language: str = "es",
    ) -> bool:
        """
        Send email using template with automatic routing.

        Routing Logic:
        - If template_code is in LEGACY_TEMPLATE_CODES → use Jinja2 file system
        - Otherwise → fetch from database (email_templates table)

        Args:
            db: Database connection (required for DB templates)
            template_code: Template code (e.g., "verification_email", "payment_failed")
            to_email: Recipient email address
            variables: Dict of variables to replace in template
            language: Language code (es/fr/en, default: es)

        Returns:
            bool: True if email sent successfully, False otherwise
        """
        variables = variables or {}

        # Check if this is a legacy template
        if template_code in LEGACY_TEMPLATE_CODES:
            return self._send_legacy_template(template_code, to_email, variables, language)
        else:
            return await self._send_database_template(db, template_code, to_email, variables, language)

    def _send_legacy_template(
        self,
        template_code: str,
        to_email: str,
        variables: Dict[str, Any],
        language: str,
    ) -> bool:
        """
        Send email using legacy Jinja2 file-based template.

        Maps template_code to the appropriate existing method.
        """
        try:
            if template_code == "verification_email":
                return self.send_verification_code(
                    to_email=to_email,
                    verification_code=variables.get("verification_code", "000000"),
                    user_name=variables.get("user_name"),
                    language=language,
                )
            elif template_code == "password_reset":
                return self.send_password_reset_email(
                    to_email=to_email,
                    reset_token=variables.get("reset_token", ""),
                    user_name=variables.get("user_name"),
                    language=language,
                )
            elif template_code == "password_reset_confirmation":
                return self.send_password_reset_confirmation(
                    to_email=to_email,
                    user_name=variables.get("user_name"),
                    language=language,
                )
            elif template_code == "2fa_code":
                return self.send_2fa_code(
                    to_email=to_email,
                    code=variables.get("code", "000000"),
                    user_name=variables.get("user_name"),
                    language=language,
                )
            elif template_code == "account_lockout":
                locked_until = variables.get("locked_until")
                if isinstance(locked_until, str):
                    locked_until = datetime.fromisoformat(locked_until)
                return self.send_account_lockout_notification(
                    to_email=to_email,
                    user_name=variables.get("user_name"),
                    locked_until=locked_until,
                    language=language,
                )
            elif template_code == "agent_invitation":
                return self.send_agent_invitation(
                    to_email=to_email,
                    first_name=variables.get("first_name", ""),
                    verification_code=variables.get("verification_code", "000000"),
                    language=language,
                )
            elif template_code == "admin_invitation":
                return self.send_admin_invitation(
                    to_email=to_email,
                    first_name=variables.get("first_name", ""),
                    verification_code=variables.get("verification_code", "000000"),
                    language=language,
                )
            else:
                logger.error(f"Unknown legacy template code: {template_code}")
                return False

        except Exception as e:
            logger.error(f"Error sending legacy template {template_code}: {e}")
            return False

    async def _send_database_template(
        self,
        db: asyncpg.Connection,
        template_code: str,
        to_email: str,
        variables: Dict[str, Any],
        language: str,
    ) -> bool:
        """
        Send email using database-stored template.

        Fetches template from email_templates table and replaces variables.
        """
        from app.modules.communications.services.email_template_service import EmailTemplateService

        try:
            template_service = EmailTemplateService()

            # Fetch template from database
            template = await template_service.get_template_by_code(db, template_code)
            if not template:
                logger.error(f"Template not found in database: {template_code}")
                return False

            # Check if template is active
            if not template.is_active:
                logger.warning(f"Template is inactive: {template_code}")
                return False

            # Get HTML content (priority: DB > legacy file)
            html_content = template.html_content
            if not html_content:
                # Legacy fallback: read from file
                html_file_path = template_service._get_template_file_path(template_code)
                if html_file_path.exists():
                    with open(html_file_path, "r", encoding="utf-8") as f:
                        html_content = f.read()
                else:
                    logger.error(f"No HTML content for template: {template_code}")
                    return False

            # Replace variables in HTML content
            for var_name, var_value in variables.items():
                placeholder = "{{" + var_name + "}}"
                html_content = html_content.replace(placeholder, str(var_value))

            # Get subject based on language
            if language == "fr":
                subject = template.subject_fr or template.subject_es
            elif language == "en":
                subject = template.subject_en or template.subject_es
            else:
                subject = template.subject_es

            # Replace variables in subject too
            for var_name, var_value in variables.items():
                placeholder = "{{" + var_name + "}}"
                subject = subject.replace(placeholder, str(var_value))

            # Generate plain text from HTML
            plain_text = self._html_to_plain_text(html_content)

            # Send the email
            return self.send_email(to_email, subject, html_content, plain_text)

        except Exception as e:
            logger.error(f"Error sending database template {template_code}: {e}")
            return False

    def _html_to_plain_text(self, html: str) -> str:
        """
        Convert HTML content to plain text.

        Simple conversion that removes HTML tags and normalizes whitespace.
        """
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', html)
        # Replace multiple whitespace with single space
        text = re.sub(r'\s+', ' ', text)
        # Replace common HTML entities
        text = text.replace('&nbsp;', ' ')
        text = text.replace('&amp;', '&')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        text = text.replace('&quot;', '"')
        return text.strip()

    def is_legacy_template(self, template_code: str) -> bool:
        """Check if a template code uses the legacy Jinja2 system."""
        return template_code in LEGACY_TEMPLATE_CODES


# ============================================================================
# FACTORY FUNCTION
# ============================================================================

def get_email_service() -> EmailService:
    """
    Get configured EmailService instance

    Returns:
        EmailService: Configured email service
    """
    from app.config import get_settings
    settings = get_settings()

    return EmailService(
        smtp_host=settings.SMTP_HOST,
        smtp_port=settings.SMTP_PORT,
        smtp_username=settings.SMTP_USERNAME,
        smtp_password=settings.SMTP_PASSWORD,
        smtp_use_tls=settings.SMTP_USE_TLS,
        smtp_from_email=settings.SMTP_FROM_EMAIL,
        smtp_from_name=settings.SMTP_FROM_NAME or "Facil Platform",
    )
