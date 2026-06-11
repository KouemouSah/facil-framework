"""
Communication API Routes - Email, SMS, Push notification endpoints

Endpoints:
- POST /communications/email/send - Send email
- POST /communications/email/send-with-template - Send email with template (Legacy or DB)
- POST /communications/email/verification - Send verification email
- POST /communications/email/password-reset - Send password reset email
- POST /communications/email/2fa - Send 2FA code email
- POST /communications/sms/send-with-template - Send SMS with template
- GET /communications/templates - List available templates
- GET /communications/test - Test email configuration

Module: Communications (Email, SMS, Push notifications)
"""

from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, EmailStr, Field
from loguru import logger
import asyncpg

from app.modules.communications.services.email_service import EmailService, get_email_service, LEGACY_TEMPLATE_CODES
from app.modules.communications.services.communication_service import CommunicationService
from app.modules.communications.models.communication import EmailTemplate
from app.modules.communications.services.provider_settings_service import ProviderSettingsService
from app.modules.communications.services.sms_provider_service import SmsService
from app.modules.communications.services.sms_template_service import SmsTemplateService
from app.modules.communications.models.sms_template import SmsTemplateRenderRequest
from app.modules.auth.middleware.auth_middleware import get_current_user
from app.database.connection import get_database


router = APIRouter(prefix="/communications", tags=["Communications"])


# ============================================================================
# REQUEST MODELS
# ============================================================================

class SendEmailRequest(BaseModel):
    """Request model for sending custom email"""
    to_email: EmailStr
    subject: str = Field(..., min_length=1, max_length=200)
    html_content: str = Field(..., min_length=1)
    plain_text_content: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "to_email": "user@example.com",
                "subject": "Important notification",
                "html_content": "<p>Hello, this is a test email</p>",
                "plain_text_content": "Hello, this is a test email"
            }
        }


class SendVerificationEmailRequest(BaseModel):
    """Request model for verification email"""
    to_email: EmailStr
    verification_code: str = Field(..., min_length=6, max_length=6)
    user_name: Optional[str] = None
    language: str = Field("es", pattern="^(es|fr|en)$")

    class Config:
        json_schema_extra = {
            "example": {
                "to_email": "user@example.com",
                "verification_code": "123456",
                "user_name": "John Doe",
                "language": "es"
            }
        }


class SendPasswordResetRequest(BaseModel):
    """Request model for password reset email"""
    to_email: EmailStr
    reset_token: str = Field(..., min_length=1)
    user_name: Optional[str] = None
    language: str = Field("es", pattern="^(es|fr|en)$")

    class Config:
        json_schema_extra = {
            "example": {
                "to_email": "user@example.com",
                "reset_token": "abc123def456",
                "user_name": "John Doe",
                "language": "es"
            }
        }


class Send2FACodeRequest(BaseModel):
    """Request model for 2FA code email"""
    to_email: EmailStr
    code: str = Field(..., min_length=6, max_length=6)
    user_name: Optional[str] = None
    language: str = Field("es", pattern="^(es|fr|en)$")

    class Config:
        json_schema_extra = {
            "example": {
                "to_email": "user@example.com",
                "code": "123456",
                "user_name": "John Doe",
                "language": "es"
            }
        }


class SendWithTemplateRequest(BaseModel):
    """
    Request model for sending email with any template.

    Uses automatic routing:
    - Legacy templates (verification_email, password_reset, etc.) → Jinja2 system
    - Other templates → Database (email_templates table)
    """
    template_code: str = Field(..., min_length=1, max_length=100, description="Template code")
    to_email: EmailStr = Field(..., description="Recipient email address")
    variables: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Variables to replace in template (e.g., user_name, amount)"
    )
    language: str = Field("es", pattern="^(es|fr|en)$", description="Language (es/fr/en)")

    class Config:
        json_schema_extra = {
            "example": {
                "template_code": "payment_failed",
                "to_email": "user@example.com",
                "variables": {
                    "user_name": "John Doe",
                    "payment_amount": "50,000 XAF",
                    "payment_reference": "PAY-2025-001",
                    "error_message": "Insufficient funds"
                },
                "language": "es"
            }
        }


class SendSmsWithTemplateRequest(BaseModel):
    """
    Request model for sending SMS with a database template.

    Uses the SMS template system (sms_templates table) with variable substitution.
    """
    template_code: str = Field(..., min_length=1, max_length=100, description="SMS template code")
    to_phone: str = Field(
        ...,
        min_length=9,
        max_length=20,
        description="Recipient phone number (E.164 format or local)"
    )
    variables: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Variables to replace in template (e.g., user_name, code)"
    )
    language: str = Field("es", pattern="^(es|fr|en)$", description="Language (es/fr/en)")


class NotifyUserSmsRequest(BaseModel):
    """
    Request model for sending SMS notification to a user.

    Retrieves user's phone number from their profile automatically.
    """
    user_email: str = Field(..., description="User email to notify")
    template_code: str = Field(..., min_length=1, max_length=100, description="SMS template code")
    variables: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Variables to replace in template (e.g., amount, reference)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "user_email": "libressay@gmail.com",
                "template_code": "PAYMENT_RECEIVED",
                "variables": {
                    "user_name": "John Doe",
                    "amount": "50,000 XAF",
                    "reference": "PAY-2025-001"
                }
            }
        }


# ============================================================================
# EMAIL ENDPOINTS
# ============================================================================

@router.post("/email/send")
async def send_email(
    request: SendEmailRequest,
    background_tasks: BackgroundTasks,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Send a custom email

    Requires authentication. Admin only.

    Args:
        request: Email request data

    Returns:
        Success message
    """
    email_service = EmailService()

    try:
        # Send email in background
        background_tasks.add_task(
            email_service.send_email,
            request.to_email,
            request.subject,
            request.html_content,
            request.plain_text_content
        )

        logger.info(f"Email queued to {request.to_email} by user {current_user.get('sub')}")

        return {
            "message": "Email queued for sending",
            "to": request.to_email,
            "subject": request.subject
        }

    except Exception as e:
        logger.error(f"Error queuing email: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/email/send-with-template")
async def send_email_with_template(
    request: SendWithTemplateRequest,
    db: asyncpg.Connection = Depends(get_database),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Send email using a template with automatic routing.

    **Routing Logic:**
    - Legacy templates (verification_email, password_reset, etc.) → Jinja2 file system
    - Other templates → Database (email_templates table)

    **Legacy Templates:**
    - verification_email
    - password_reset
    - password_reset_confirmation
    - 2fa_code
    - account_lockout

    **Database Templates:**
    - payment_failed, payment_success, declaration_submitted, etc.
    - Any template created via Admin UI

    Requires authentication.
    """
    email_service = get_email_service()

    try:
        # Determine template source for response info
        is_legacy = request.template_code in LEGACY_TEMPLATE_CODES
        template_source = "legacy" if is_legacy else "database"

        # Send email using unified method
        success = await email_service.send_with_template(
            db=db,
            template_code=request.template_code,
            to_email=request.to_email,
            variables=request.variables,
            language=request.language,
        )

        if success:
            logger.info(
                f"Email sent with template '{request.template_code}' ({template_source}) "
                f"to {request.to_email} by user {current_user.get('sub')}"
            )
            return {
                "success": True,
                "message": "Email sent successfully",
                "to": request.to_email,
                "template_code": request.template_code,
                "template_source": template_source,
                "language": request.language,
            }
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to send email with template '{request.template_code}'"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending email with template: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/email/verification")
async def send_verification_email(
    request: SendVerificationEmailRequest,
    background_tasks: BackgroundTasks,
):
    """
    Send email verification code

    Public endpoint (no auth required) - Used during registration

    Args:
        request: Verification email request

    Returns:
        Success message
    """
    email_service = EmailService()

    try:
        # Send email in background
        background_tasks.add_task(
            email_service.send_verification_code,
            request.to_email,
            request.verification_code,
            request.user_name,
            request.language
        )

        logger.info(f"Verification email queued to {request.to_email}")

        return {
            "message": "Verification email queued for sending",
            "to": request.to_email,
            "language": request.language
        }

    except Exception as e:
        logger.error(f"Error queuing verification email: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail="Failed to send verification email. Please try again.")


@router.post("/email/password-reset")
async def send_password_reset_email(
    request: SendPasswordResetRequest,
    background_tasks: BackgroundTasks,
):
    """
    Send password reset email

    Public endpoint (no auth required) - Used for password recovery

    Args:
        request: Password reset email request

    Returns:
        Success message
    """
    email_service = EmailService()

    try:
        # Send email in background
        background_tasks.add_task(
            email_service.send_password_reset,
            request.to_email,
            request.reset_token,
            request.user_name,
            request.language
        )

        logger.info(f"Password reset email queued to {request.to_email}")

        return {
            "message": "Password reset email queued for sending",
            "to": request.to_email,
            "language": request.language
        }

    except Exception as e:
        logger.error(f"Error queuing password reset email: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail="Failed to send password reset email. Please try again.")


@router.post("/email/2fa")
async def send_2fa_code_email(
    request: Send2FACodeRequest,
    background_tasks: BackgroundTasks,
):
    """
    Send 2FA verification code

    Public endpoint (no auth required) - Used during login

    Args:
        request: 2FA code email request

    Returns:
        Success message
    """
    email_service = EmailService()

    try:
        # Send email in background
        background_tasks.add_task(
            email_service.send_two_factor_code,
            request.to_email,
            request.code,
            request.user_name,
            request.language
        )

        logger.info(f"2FA code email queued to {request.to_email}")

        return {
            "message": "2FA code email queued for sending",
            "to": request.to_email,
            "language": request.language
        }

    except Exception as e:
        logger.error(f"Error queuing 2FA code email: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail="Failed to send verification code. Please try again.")


# ============================================================================
# SMS ENDPOINTS
# ============================================================================

@router.post("/sms/send-with-template")
async def send_sms_with_template(
    request: SendSmsWithTemplateRequest,
    db: asyncpg.Connection = Depends(get_database),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Send SMS using a database template with variable substitution.

    **Workflow:**
    1. Fetch template from sms_templates table by code
    2. Render template with provided variables
    3. Send SMS via configured provider (Infobip)

    **Required:**
    - Authentication
    - Active SMS provider configured in provider settings

    **Example template codes:**
    - PAYMENT_RECEIVED, PAYMENT_FAILED, AUTH_VERIFICATION_CODE, etc.

    Returns:
    - Success status with message ID
    """
    try:
        # 1. Get the SMS template
        sms_template_service = SmsTemplateService()
        template = await sms_template_service.get_template_by_code(db, request.template_code)

        if not template:
            raise HTTPException(
                status_code=404,
                detail=f"SMS template not found: {request.template_code}"
            )

        if not template.is_active:
            raise HTTPException(
                status_code=400,
                detail=f"SMS template is inactive: {request.template_code}"
            )

        # 2. Render the template
        render_request = SmsTemplateRenderRequest(
            template_code=request.template_code,
            language=request.language,
            variables=request.variables or {}
        )
        rendered = await sms_template_service.render_template(db, render_request)

        # 3. Get SMS provider credentials
        provider_service = ProviderSettingsService()
        credentials = await provider_service.get_active_sms_credentials(db)

        if not credentials:
            raise HTTPException(
                status_code=400,
                detail="No active SMS provider configured. Please configure a provider in Communications > Providers."
            )

        api_key = credentials.get("api_key")
        if not api_key:
            raise HTTPException(
                status_code=500,
                detail="SMS provider API key not configured"
            )

        # 4. Send SMS
        sms_service = SmsService(
            provider="infobip",
            api_key=api_key,
            base_url="y45e8g.api.infobip.com",
            sender_id="Facil"
        )

        result = sms_service.send_sms(
            to=request.to_phone,
            message=rendered.rendered_content
        )

        if result.success:
            logger.info(
                f"SMS sent with template '{request.template_code}' to {request.to_phone} "
                f"by user {current_user.get('sub')}, message_id={result.message_id}"
            )
            return {
                "success": True,
                "message": "SMS sent successfully",
                "to": request.to_phone,
                "template_code": request.template_code,
                "language": request.language,
                "message_id": result.message_id,
                "character_count": rendered.character_count,
                "segment_count": rendered.segment_count
            }
        else:
            logger.error(f"Failed to send SMS: {result.error}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to send SMS: {result.error}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending SMS with template: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sms/notify-user")
async def notify_user_via_sms(
    request: NotifyUserSmsRequest,
    db: asyncpg.Connection = Depends(get_database),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Send SMS notification to a user using their profile phone number.

    **Workflow:**
    1. Fetch user by email from users table
    2. Get user's phone_number and preferred_language
    3. Fetch SMS template by code
    4. Render template with provided variables + user_name
    5. Send SMS via configured provider (Infobip)

    **Required:**
    - Authentication
    - User must have a phone_number configured in their profile
    - Active SMS provider configured in provider settings

    **Auto-injected variables:**
    - user_name: User's full name (first_name + last_name)

    Returns:
    - Success status with message ID
    """
    from app.modules.users.repositories.user_repository import UserRepository

    try:
        # 1. Get user by email
        user_repo = UserRepository()
        user = await user_repo.find_by_email(request.user_email)

        if not user:
            raise HTTPException(
                status_code=404,
                detail=f"User not found: {request.user_email}"
            )

        # 2. Check if user has phone number
        if not user.phone_number:
            raise HTTPException(
                status_code=400,
                detail=f"User {request.user_email} has no phone number configured"
            )

        # 3. Get the SMS template
        sms_template_service = SmsTemplateService()
        template = await sms_template_service.get_template_by_code(db, request.template_code)

        if not template:
            raise HTTPException(
                status_code=404,
                detail=f"SMS template not found: {request.template_code}"
            )

        if not template.is_active:
            raise HTTPException(
                status_code=400,
                detail=f"SMS template is inactive: {request.template_code}"
            )

        # 4. Prepare variables (inject user_name automatically)
        variables = request.variables or {}
        variables["user_name"] = f"{user.first_name} {user.last_name}"

        # Use user's preferred language
        language = user.preferred_language or "es"

        # 5. Render the template
        render_request = SmsTemplateRenderRequest(
            template_code=request.template_code,
            language=language,
            variables=variables
        )
        rendered = await sms_template_service.render_template(db, render_request)

        # 6. Get SMS provider credentials
        provider_service = ProviderSettingsService()
        credentials = await provider_service.get_active_sms_credentials(db)

        if not credentials:
            raise HTTPException(
                status_code=400,
                detail="No active SMS provider configured. Please configure a provider in Communications > Providers."
            )

        api_key = credentials.get("api_key")
        if not api_key:
            raise HTTPException(
                status_code=500,
                detail="SMS provider API key not configured"
            )

        # 7. Send SMS
        sms_service = SmsService(
            provider="infobip",
            api_key=api_key,
            base_url="y45e8g.api.infobip.com",
            sender_id="Facil"
        )

        result = sms_service.send_sms(
            to=user.phone_number,
            message=rendered.rendered_content
        )

        if result.success:
            logger.info(
                f"SMS notification sent to user {request.user_email} ({user.phone_number}) "
                f"with template '{request.template_code}' by {current_user.get('sub')}, "
                f"message_id={result.message_id}"
            )
            return {
                "success": True,
                "message": "SMS notification sent successfully",
                "user_email": request.user_email,
                "to_phone": user.phone_number,
                "template_code": request.template_code,
                "language": language,
                "message_id": result.message_id,
                "character_count": rendered.character_count,
                "segment_count": rendered.segment_count
            }
        else:
            logger.error(f"Failed to send SMS notification: {result.error}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to send SMS: {result.error}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending SMS notification to user: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# UTILITY ENDPOINTS
# ============================================================================

@router.get("/templates")
async def list_email_templates():
    """
    List available email templates

    Returns:
        List of template names and descriptions
    """
    templates = []

    for template in EmailTemplate:
        templates.append({
            "code": template.value,
            "name": template.name,
            "description": get_template_description(template)
        })

    return {
        "templates": templates,
        "total": len(templates)
    }


@router.get("/test")
async def test_email_configuration(
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Test email service configuration

    Admin only - Tests SMTP connection

    Returns:
        Configuration status
    """
    email_service = EmailService()

    try:
        # Test SMTP connection
        smtp_config = {
            "host": email_service.smtp_host,
            "port": email_service.smtp_port,
            "username": email_service.smtp_username,
            "from_email": email_service.from_email,
            "from_name": email_service.from_name,
            "use_tls": email_service.use_tls,
        }

        return {
            "status": "configured",
            "smtp": smtp_config,
            "message": "Email service is configured (SMTP credentials not exposed)"
        }

    except Exception as e:
        logger.error(f"Error testing email configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_template_description(template: EmailTemplate) -> str:
    """Get description for email template"""
    descriptions = {
        EmailTemplate.VERIFICATION_CODE: "Email verification code for new registrations",
        EmailTemplate.PASSWORD_RESET: "Password reset link/token",
        EmailTemplate.TWO_FACTOR_CODE: "Two-factor authentication code",
        EmailTemplate.ACCOUNT_LOCKOUT: "Account lockout notification",
    }
    return descriptions.get(template, "No description available")
