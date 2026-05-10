"""
Notification Templates API Routes

Endpoints for managing notification templates (admin only)
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
import asyncpg
from loguru import logger

from app.database.connection import get_database
from app.modules.communications.models.notification_template import (
    NotificationTemplateCreate,
    NotificationTemplateUpdate,
    NotificationTemplateResponse,
    NotificationTemplateListResponse,
    NotificationPreviewRequest,
    NotificationPreviewResponse,
)
from app.modules.communications.services.notification_template_service import (
    NotificationTemplateService,
)
from app.modules.auth.middleware.auth_middleware import get_current_user
from app.modules.users.models.user import UserResponse


router = APIRouter(prefix="/communications/notification-templates", tags=["Notification Templates"])
service = NotificationTemplateService()


# ============================================================================
# CREATE NOTIFICATION TEMPLATE
# ============================================================================

@router.post(
    "",
    response_model=NotificationTemplateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create notification template",
    description="Create a new notification template (admin only)"
)
async def create_notification_template(
    template_data: NotificationTemplateCreate,
    db: asyncpg.Connection = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Create a new notification template

    - **template_code**: Unique template code (alphanumeric, hyphens, underscores)
    - **name_**: Template names in multiple languages
    - **title_**: Notification titles in multiple languages
    - **body_**: Notification bodies with {{variable}} placeholders
    - **icon**: Lucide icon name (optional)
    - **action_url**: URL for notification action (optional)
    - **variables**: List of variable names used in template
    - **notification_type**: Type of notification (info, success, warning, error)
    - **priority**: Priority level (low, normal, high, urgent)
    """
    try:
        user_id = current_user.id
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User ID not found in token"
            )

        template = await service.create_template(db, template_data, user_id)
        return template

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating notification template: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create notification template"
        )


# ============================================================================
# GET NOTIFICATION TEMPLATE BY ID
# ============================================================================

@router.get(
    "/{template_id}",
    response_model=NotificationTemplateResponse,
    summary="Get notification template",
    description="Get notification template by ID"
)
async def get_notification_template(
    template_id: int,
    db: asyncpg.Connection = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Get notification template by ID

    Args:
        template_id: Template ID

    Returns:
        Notification template details
    """
    return await service.get_template_by_id(db, template_id)


# ============================================================================
# GET NOTIFICATION TEMPLATE BY CODE
# ============================================================================

@router.get(
    "/code/{template_code}",
    response_model=NotificationTemplateResponse,
    summary="Get notification template by code",
    description="Get notification template by template code"
)
async def get_notification_template_by_code(
    template_code: str,
    db: asyncpg.Connection = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Get notification template by template code

    Args:
        template_code: Template code

    Returns:
        Notification template details
    """
    return await service.get_template_by_code(db, template_code)


# ============================================================================
# LIST NOTIFICATION TEMPLATES
# ============================================================================

@router.get(
    "",
    response_model=NotificationTemplateListResponse,
    summary="List notification templates",
    description="List all notification templates with pagination and filters"
)
async def list_notification_templates(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    notification_type: Optional[str] = Query(None, description="Filter by notification type"),
    search: Optional[str] = Query(None, description="Search in template code and names"),
    db: asyncpg.Connection = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user)
):
    """
    List notification templates with pagination and filters

    Query parameters:
    - **page**: Page number (1-indexed)
    - **page_size**: Items per page (max 100)
    - **is_active**: Filter by active status
    - **notification_type**: Filter by notification type (info, success, warning, error)
    - **search**: Search in template code and names

    Returns:
        Paginated list of notification templates
    """
    templates, total, total_pages = await service.list_templates(
        db,
        page=page,
        page_size=page_size,
        is_active=is_active,
        notification_type=notification_type,
        search=search
    )

    return NotificationTemplateListResponse(
        templates=templates,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


# ============================================================================
# UPDATE NOTIFICATION TEMPLATE
# ============================================================================

@router.put(
    "/{template_id}",
    response_model=NotificationTemplateResponse,
    summary="Update notification template",
    description="Update notification template (admin only)"
)
async def update_notification_template(
    template_id: int,
    template_data: NotificationTemplateUpdate,
    db: asyncpg.Connection = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Update notification template

    Args:
        template_id: Template ID
        template_data: Updated template data

    Returns:
        Updated notification template
    """
    return await service.update_template(db, template_id, template_data)


# ============================================================================
# DELETE NOTIFICATION TEMPLATE
# ============================================================================

@router.delete(
    "/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete notification template",
    description="Delete notification template (admin only)"
)
async def delete_notification_template(
    template_id: int,
    db: asyncpg.Connection = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Delete notification template

    Args:
        template_id: Template ID

    Returns:
        No content on success
    """
    await service.delete_template(db, template_id)
    return None


# ============================================================================
# PREVIEW NOTIFICATION
# ============================================================================

@router.post(
    "/preview",
    response_model=NotificationPreviewResponse,
    summary="Preview notification",
    description="Preview notification with variable substitution"
)
async def preview_notification(
    preview_request: NotificationPreviewRequest,
    db: asyncpg.Connection = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Preview notification with variable substitution

    - **template_id**: Template ID to preview
    - **language**: Language for preview (es, fr, en)
    - **variables**: Variable values for substitution

    Returns:
        Rendered notification preview
    """
    return await service.preview_notification(db, preview_request)


# ============================================================================
# GET ACTIVE TEMPLATES
# ============================================================================

@router.get(
    "/active/list",
    response_model=list[NotificationTemplateResponse],
    summary="Get active templates",
    description="Get all active notification templates"
)
async def get_active_templates(
    db: asyncpg.Connection = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Get all active notification templates

    Returns:
        List of active notification templates
    """
    return await service.get_active_templates(db)
