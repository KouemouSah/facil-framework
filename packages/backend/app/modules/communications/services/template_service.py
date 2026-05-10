"""
Template Service - Renders email templates with Jinja2

Handles:
- Template loading and rendering
- Internationalization (es/fr/en)
- Dynamic content injection
- Logo URL configuration

Module: Communications
"""

from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
from jinja2 import Environment, FileSystemLoader, select_autoescape
from loguru import logger


class TemplateService:
    """Service for rendering email templates with i18n support"""

    def __init__(self):
        """Initialize Jinja2 environment"""
        # Template directory
        template_dir = Path(__file__).parent.parent / "templates"

        # Initialize Jinja2
        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        logger.info(f"TemplateService initialized with templates from: {template_dir}")

    def render_template(
        self,
        template_name: str,
        context: Dict[str, Any],
        language: str = "es",
    ) -> str:
        """
        Render email template with context

        Args:
            template_name: Template filename (e.g., "verification_email.html")
            context: Template variables
            language: Language code (es/fr/en)

        Returns:
            Rendered HTML string
        """
        try:
            # Get logo URL from settings
            from app.config import get_settings
            settings = get_settings()

            # Dynamic site URL from settings (never hardcode domain)
            frontend_url = getattr(settings, 'FRONTEND_URL', 'https://taxasge.emacsah.com')

            # Logo: served from frontend CDN (Firebase Hosting) — fast, no CORS issues
            # Fallback to Firebase Storage if FRONTEND_URL is not set
            logo_url = f"{frontend_url}/logo_hd.png"
            # Extract domain from URL for display (e.g., "taxasge.emacsah.com")
            from urllib.parse import urlparse
            site_domain = urlparse(frontend_url).netloc or frontend_url

            # Add common variables
            common_context = {
                "language": language,
                "logo_url": logo_url,
                "current_year": datetime.now().year,
                "site_url": frontend_url,
                "site_domain": site_domain,
                **context,  # User-provided context
            }

            # Render template
            template = self.env.get_template(template_name)
            html = template.render(**common_context)

            logger.debug(f"Rendered template '{template_name}' in language '{language}'")
            return html

        except Exception as e:
            logger.error(f"Error rendering template '{template_name}': {str(e)}")
            raise

    def render_verification_email(
        self,
        user_name: Optional[str],
        verification_code: str,
        language: str = "es",
    ) -> tuple[str, str]:
        """
        Render email verification template

        Args:
            user_name: User's name (optional)
            verification_code: 6-digit code
            language: Language code

        Returns:
            Tuple of (html, plain_text)
        """
        from app.modules.communications.services.email_content import get_email_content

        content = get_email_content("verification_email", language)

        greeting = content["greeting"].format(user_name=user_name) if user_name else content["greeting_default"]

        context = {
            "subject": content["subject"],
            "title": content["title"],
            "greeting": greeting,
            "message": content["message"],
            "verification_code": verification_code,
            "expiry_label": content["expiry_label"],
            "expiry_time": content["expiry_time"],
            "ignore_text": content["ignore_text"],
            "footer_text": content["footer_text"],
            "support_text": content["support_text"],
            "rights_reserved": content["rights_reserved"],
        }

        html = self.render_template("verification_email.html", context, language)
        plain_text = self._html_to_plain_text(context)

        return html, plain_text

    def render_password_reset_email(
        self,
        user_name: Optional[str],
        reset_url: str,
        language: str = "es",
    ) -> tuple[str, str]:
        """
        Render password reset email template

        Args:
            user_name: User's name (optional)
            reset_url: Password reset URL
            language: Language code

        Returns:
            Tuple of (html, plain_text)
        """
        from app.modules.communications.services.email_content import get_email_content

        content = get_email_content("password_reset", language)

        greeting = content["greeting"].format(user_name=user_name) if user_name else content["greeting_default"]

        context = {
            "subject": content["subject"],
            "title": content["title"],
            "greeting": greeting,
            "message": content["message"],
            "reset_url": reset_url,
            "button_text": content["button_text"],
            "or_copy_text": content["or_copy_text"],
            "expiry_label": content["expiry_label"],
            "expiry_time": content["expiry_time"],
            "ignore_text": content["ignore_text"],
            "footer_text": content["footer_text"],
            "support_text": content["support_text"],
            "rights_reserved": content["rights_reserved"],
        }

        html = self.render_template("password_reset.html", context, language)
        plain_text = self._html_to_plain_text(context)

        return html, plain_text

    def render_password_reset_confirmation_email(
        self,
        user_name: Optional[str],
        language: str = "es",
    ) -> tuple[str, str]:
        """
        Render password reset confirmation template

        Args:
            user_name: User's name (optional)
            language: Language code

        Returns:
            Tuple of (html, plain_text)
        """
        from app.modules.communications.services.email_content import get_email_content

        content = get_email_content("password_reset_confirmation", language)

        greeting = content["greeting"].format(user_name=user_name) if user_name else content["greeting_default"]

        # Login URL from settings
        from app.config import get_settings
        settings = get_settings()

        if settings.ENVIRONMENT == "production":
            login_url = "https://taxasge-prod.web.app/login"
        elif settings.ENVIRONMENT == "staging":
            login_url = "https://taxasge-dev.web.app/login"
        else:
            login_url = "http://localhost:3000/login"

        context = {
            "subject": content["subject"],
            "title": content["title"],
            "greeting": greeting,
            "message": content["message"],
            "login_message": content["login_message"],
            "login_url": login_url,
            "button_text": content["button_text"],
            "warning_text": content["warning_text"],
            "footer_text": content["footer_text"],
            "support_text": content["support_text"],
            "rights_reserved": content["rights_reserved"],
        }

        html = self.render_template("password_reset_confirmation.html", context, language)
        plain_text = self._html_to_plain_text(context)

        return html, plain_text

    def render_2fa_code_email(
        self,
        user_name: Optional[str],
        code: str,
        language: str = "es",
    ) -> tuple[str, str]:
        """
        Render 2FA code email template

        Args:
            user_name: User's name (optional)
            code: 6-digit 2FA code
            language: Language code

        Returns:
            Tuple of (html, plain_text)
        """
        from app.modules.communications.services.email_content import get_email_content

        content = get_email_content("2fa_code", language)

        greeting = content["greeting"].format(user_name=user_name) if user_name else content["greeting_default"]

        context = {
            "subject": content["subject"],
            "title": content["title"],
            "greeting": greeting,
            "message": content["message"],
            "code": code,
            "expiry_label": content["expiry_label"],
            "expiry_time": content["expiry_time"],
            "security_warning": content["security_warning"],
            "footer_text": content["footer_text"],
            "support_text": content["support_text"],
            "rights_reserved": content["rights_reserved"],
        }

        html = self.render_template("2fa_code.html", context, language)
        plain_text = self._html_to_plain_text(context)

        return html, plain_text

    def render_account_lockout_email(
        self,
        user_name: Optional[str],
        remaining_minutes: int,
        language: str = "es",
    ) -> tuple[str, str]:
        """
        Render account lockout notification template

        Args:
            user_name: User's name (optional)
            remaining_minutes: Minutes until unlock
            language: Language code

        Returns:
            Tuple of (html, plain_text)
        """
        from app.modules.communications.services.email_content import get_email_content

        content = get_email_content("account_lockout", language)

        greeting = content["greeting"].format(user_name=user_name) if user_name else content["greeting_default"]

        lockout_duration = content["lockout_duration"].format(minutes=remaining_minutes)
        if_you_message = content["if_you_message"].format(minutes=remaining_minutes)

        context = {
            "subject": content["subject"],
            "title": content["title"],
            "greeting": greeting,
            "message": content["message"],
            "lockout_duration": lockout_duration,
            "if_you_label": content["if_you_label"],
            "if_you_message": if_you_message,
            "if_not_you_label": content["if_not_you_label"],
            "if_not_you_message": content["if_not_you_message"],
            "footer_text": content["footer_text"],
            "support_text": content["support_text"],
            "rights_reserved": content["rights_reserved"],
        }

        html = self.render_template("account_lockout.html", context, language)
        plain_text = self._html_to_plain_text(context)

        return html, plain_text

    def render_invitation_email(
        self,
        user_name: Optional[str],
        verification_code: str,
        activation_url: str,
        invitation_type: str,  # "agent" or "admin"
        language: str = "es",
    ) -> tuple[str, str]:
        """
        Render agent/admin invitation email template

        Args:
            user_name: User's name (optional)
            verification_code: 6-digit code
            activation_url: URL to activate the account
            invitation_type: "agent" or "admin"
            language: Language code

        Returns:
            Tuple of (html, plain_text)
        """
        from app.modules.communications.services.email_content import get_email_content

        template_code = f"{invitation_type}_invitation"
        content = get_email_content(template_code, language)

        greeting = content["greeting"].format(user_name=user_name) if user_name else content["greeting_default"]

        context = {
            "subject": content["subject"],
            "title": content["title"],
            "greeting": greeting,
            "message": content["message"],
            "instructions": content["instructions"],
            "verification_code": verification_code,
            "activation_url": activation_url,
            "button_text": content["button_text"],
            "or_copy_text": content["or_copy_text"],
            "expiry_label": content["expiry_label"],
            "expiry_time": content["expiry_time"],
            "ignore_text": content["ignore_text"],
            "footer_text": content["footer_text"],
            "support_text": content["support_text"],
            "rights_reserved": content["rights_reserved"],
        }

        # Use invitation_email.html template (we'll create it)
        # For now, fallback to verification_email.html with button
        html = self.render_template("invitation_email.html", context, language)
        plain_text = self._html_to_plain_text(context)

        return html, plain_text

    def _html_to_plain_text(self, context: Dict[str, Any]) -> str:
        """
        Generate plain text version from context

        Args:
            context: Template context

        Returns:
            Plain text version
        """
        # Simple plain text generation
        # In production, you might want to use a library like html2text
        lines = []

        if "title" in context:
            lines.append(context["title"])
            lines.append("")

        if "greeting" in context:
            lines.append(context["greeting"])
            lines.append("")

        if "message" in context:
            lines.append(context["message"])
            lines.append("")

        if "verification_code" in context:
            lines.append(f"Code: {context['verification_code']}")
            lines.append("")

        if "code" in context:
            lines.append(f"Code: {context['code']}")
            lines.append("")

        if "reset_url" in context:
            lines.append(f"Reset URL: {context['reset_url']}")
            lines.append("")

        if "activation_url" in context:
            lines.append(f"Activation URL: {context['activation_url']}")
            lines.append("")

        if "footer_text" in context:
            lines.append("---")
            lines.append(context["footer_text"])

        return "\n".join(lines)


# ============================================================================
# FACTORY FUNCTION
# ============================================================================

def get_template_service() -> TemplateService:
    """
    Get TemplateService instance

    Returns:
        TemplateService: Template service
    """
    return TemplateService()
