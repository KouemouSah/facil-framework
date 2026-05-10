"""
Email Templates API Routes - FastAPI endpoints for email template management

Endpoints:
- GET    /email-templates - List all templates
- GET    /email-templates/search - Search templates
- GET    /email-templates/{id} - Get single template
- GET    /email-templates/{id}/preview - Get HTML content
- POST   /email-templates - Create template
- PUT    /email-templates/{id} - Update template
- DELETE /email-templates/{id} - Delete template
- POST   /email-templates/{id}/send-test - Send test email with template
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from typing import Optional, Dict, Any
from pydantic import BaseModel, EmailStr, Field
import asyncpg
from loguru import logger

from app.database.connection import get_database
from app.modules.auth.middleware.auth_middleware import get_current_user
from app.modules.permissions.middleware.permission_middleware import permission_required
from app.modules.users.models.user import UserResponse
from ..models.email_template import (
    EmailTemplateCreate,
    EmailTemplateUpdate,
    EmailTemplateResponse,
    EmailTemplateListResponse,
    EmailTemplatePreview,
)
from ..services.email_template_service import EmailTemplateService
from ..services.email_service import EmailService


class SendTestEmailRequest(BaseModel):
    """Request model for sending a test email with a template"""
    to_email: EmailStr = Field(..., description="Recipient email address")
    test_variables: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Test values for template variables"
    )
    language: str = Field("es", pattern="^(es|fr|en)$", description="Language for subject/name")

    class Config:
        json_schema_extra = {
            "example": {
                "to_email": "test@example.com",
                "test_variables": {
                    "user_name": "John Doe",
                    "amount": "10,000 XAF",
                    "date": "20/12/2025"
                },
                "language": "es"
            }
        }


class SendTestEmailResponse(BaseModel):
    """Response for test email sending"""
    success: bool
    message: str
    to_email: str
    template_code: str

router = APIRouter(prefix="/communications/email-templates", tags=["Email Templates"])
service = EmailTemplateService()


# =============================================================================
# PUBLIC ENDPOINTS (Read-only for authenticated users)
# =============================================================================


@router.get("", response_model=EmailTemplateListResponse)
async def list_email_templates(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Page size"),
    category: Optional[str] = Query(None, description="Filter by category"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    db: asyncpg.Connection = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
):
    """
    List all email templates with pagination and filters

    - **page**: Page number (starts at 1)
    - **page_size**: Number of templates per page (max 100)
    - **category**: Optional category filter
    - **is_active**: Optional active status filter
    """
    templates, total = await service.list_templates(
        db, category=category, is_active=is_active, page=page, page_size=page_size
    )

    total_pages = (total + page_size - 1) // page_size

    return EmailTemplateListResponse(
        templates=templates,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/search", response_model=EmailTemplateListResponse)
async def search_email_templates(
    q: str = Query(..., min_length=1, description="Search query"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Page size"),
    db: asyncpg.Connection = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
):
    """
    Search email templates by name or code

    - **q**: Search query (minimum 1 character)
    - **page**: Page number (starts at 1)
    - **page_size**: Number of templates per page (max 100)
    """
    templates, total = await service.search_templates(
        db, search_term=q, page=page, page_size=page_size
    )

    total_pages = (total + page_size - 1) // page_size

    return EmailTemplateListResponse(
        templates=templates,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{template_id}", response_model=EmailTemplateResponse)
async def get_email_template(
    template_id: int,
    db: asyncpg.Connection = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
):
    """
    Get a single email template by ID

    - **template_id**: Template ID
    """
    template = await service.get_template(db, template_id)

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template with ID {template_id} not found",
        )

    return template


@router.get("/{template_id}/preview", response_model=EmailTemplatePreview)
async def get_email_template_preview(
    template_id: int,
    db: asyncpg.Connection = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
):
    """
    Get HTML content preview for an email template

    - **template_id**: Template ID
    """
    template = await service.get_template(db, template_id)

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template with ID {template_id} not found",
        )

    html_content = await service.get_template_html(db, template_id)

    if not html_content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"HTML file for template {template_id} not found",
        )

    return EmailTemplatePreview(
        template_code=template.template_code,
        html_content=html_content,
        variables=template.variables,
    )


# =============================================================================
# ADMIN ENDPOINTS (Require permissions)
# =============================================================================


@router.post(
    "",
    response_model=EmailTemplateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_email_template(
    template_data: EmailTemplateCreate,
    db: asyncpg.Connection = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("communication.manage")),
):
    """
    Create a new email template

    Requires permission: communications.manage

    - **template_code**: Unique template code
    - **name_es**: Template name in Spanish (required)
    - **subject_es**: Email subject in Spanish (required)
    - **html_content**: HTML content for the template
    - **variables**: List of template variables
    - **category**: Optional category
    """
    try:
        template = await service.create_template(db, template_data, current_user.id)
        logger.info(
            f"Email template created: {template.template_code} by user {current_user.id}"
        )
        return template
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create email template: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create email template",
        )


@router.put("/{template_id}", response_model=EmailTemplateResponse)
async def update_email_template(
    template_id: int,
    template_data: EmailTemplateUpdate,
    db: asyncpg.Connection = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("communication.manage")),
):
    """
    Update an existing email template

    Requires permission: communications.manage

    - **template_id**: Template ID to update
    - All fields are optional
    - If html_content is provided, the HTML file will be updated
    """
    try:
        template = await service.update_template(
            db, template_id, template_data, current_user.id
        )

        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Template with ID {template_id} not found",
            )

        logger.info(
            f"Email template updated: ID {template_id} by user {current_user.id}"
        )
        return template
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update email template: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update email template",
        )


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_email_template(
    template_id: int,
    db: asyncpg.Connection = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("communication.manage")),
):
    """
    Delete an email template

    Requires permission: communications.manage

    - **template_id**: Template ID to delete
    - This will delete both the database record and the HTML file
    """
    try:
        success = await service.delete_template(db, template_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Template with ID {template_id} not found",
            )

        logger.info(
            f"Email template deleted: ID {template_id} by user {current_user.id}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete email template: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete email template",
        )


@router.post(
    "/{template_id}/send-test",
    response_model=SendTestEmailResponse,
    summary="Send Test Email",
)
async def send_test_email(
    template_id: int,
    request: SendTestEmailRequest,
    background_tasks: BackgroundTasks,
    db: asyncpg.Connection = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("communication.manage")),
):
    """
    Send a test email using a specific template.

    Requires permission: communications.manage

    - **template_id**: Template ID to use
    - **to_email**: Recipient email address
    - **test_variables**: Values to replace template variables (optional)
    - **language**: Language for subject (es, fr, en)
    """
    # Get the template
    template = await service.get_template(db, template_id)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template with ID {template_id} not found",
        )

    # Get HTML content
    html_content = await service.get_template_html(db, template_id)
    if not html_content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"HTML file for template {template_id} not found",
        )

    # Replace variables in HTML content
    if request.test_variables:
        for var_name, var_value in request.test_variables.items():
            placeholder = "{{" + var_name + "}}"
            html_content = html_content.replace(placeholder, str(var_value))

    # Get subject based on language
    if request.language == "fr":
        subject = template.subject_fr or template.subject_es
    elif request.language == "en":
        subject = template.subject_en or template.subject_es
    else:
        subject = template.subject_es

    # Add [TEST] prefix to subject
    subject = f"[TEST] {subject}"

    try:
        email_service = EmailService()

        # Send email in background
        background_tasks.add_task(
            email_service.send_email,
            request.to_email,
            subject,
            html_content,
            None  # No plain text version for test
        )

        logger.info(
            f"Test email queued: template={template.template_code}, "
            f"to={request.to_email}, by user={current_user.id}"
        )

        return SendTestEmailResponse(
            success=True,
            message="Test email queued for sending",
            to_email=request.to_email,
            template_code=template.template_code,
        )

    except Exception as e:
        logger.error(f"Failed to queue test email: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send test email: {str(e)}",
        )
