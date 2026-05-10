"""
Push Templates API Routes - CRUD endpoints for push notification templates

Endpoints:
- GET /push-templates - List all templates
- GET /push-templates/{id} - Get template by ID
- GET /push-templates/code/{code} - Get template by code
- POST /push-templates - Create new template
- PUT /push-templates/{id} - Update template
- DELETE /push-templates/{id} - Delete template
- GET /push-templates/stats - Get statistics
- POST /push-templates/{id}/preview - Preview template with sample data

Module: Communications
"""

from typing import Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, Query, status
from loguru import logger

from app.database.connection import get_database
from app.modules.auth.middleware.auth_middleware import get_current_user
from app.modules.users.models.user import UserResponse

from ..models.push_template import (
    PushTemplateCreate,
    PushTemplateUpdate,
    PushTemplateResponse,
    PushTemplateListResponse,
    PushNotificationPreview,
    PlatformEnum
)
from ..services.push_template_service import PushTemplateService


router = APIRouter(prefix="/communications/push-templates", tags=["Communications - Push Templates"])


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post("", response_model=PushTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_push_template(
    template_data: PushTemplateCreate,
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Create new push notification template

    Requires authentication. Admin only.

    Args:
        template_data: Template data

    Returns:
        Created template

    Raises:
        400: If validation fails or template_code already exists
        401: If not authenticated
        403: If not admin
    """
    service = PushTemplateService()

    try:
        user_id = current_user.id
        template = await service.create_template(db, template_data, user_id)

        logger.info(
            f"Push template created by user {user_id}",
            template_id=template.id,
            template_code=template.template_code
        )

        return template

    except ValueError as e:
        logger.error(f"Error creating push template: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error creating push template: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create push template"
        )


@router.get("", response_model=PushTemplateListResponse)
async def list_push_templates(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    platform: Optional[PlatformEnum] = Query(None, description="Filter by platform"),
    search: Optional[str] = Query(None, description="Search in template code and names"),
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user)
):
    """
    List push notification templates with pagination and filters

    Requires authentication. Admin only.

    Args:
        page: Page number
        page_size: Items per page
        is_active: Filter by active status
        platform: Filter by platform
        search: Search query

    Returns:
        List of templates with pagination
    """
    service = PushTemplateService()

    try:
        templates = await service.list_templates(
            db,
            page=page,
            page_size=page_size,
            is_active=is_active,
            platform=platform,
            search=search
        )

        return templates

    except Exception as e:
        logger.error(f"Error listing push templates: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list push templates"
        )


@router.get("/stats")
async def get_push_template_stats(
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Get push template statistics

    Requires authentication. Admin only.

    Returns:
        Statistics dictionary with counts by status and platform
    """
    service = PushTemplateService()

    try:
        stats = await service.get_stats(db)
        return stats

    except Exception as e:
        logger.error(f"Error getting push template stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get statistics"
        )


@router.get("/code/{template_code}", response_model=PushTemplateResponse)
async def get_push_template_by_code(
    template_code: str,
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Get push template by code

    Requires authentication.

    Args:
        template_code: Template code

    Returns:
        Template

    Raises:
        404: If template not found
    """
    service = PushTemplateService()

    try:
        template = await service.get_template_by_code(db, template_code)
        return template

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting push template by code: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get push template"
        )


@router.get("/{template_id}", response_model=PushTemplateResponse)
async def get_push_template(
    template_id: int,
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Get push template by ID

    Requires authentication. Admin only.

    Args:
        template_id: Template ID

    Returns:
        Template

    Raises:
        404: If template not found
    """
    service = PushTemplateService()

    try:
        template = await service.get_template(db, template_id)
        return template

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting push template: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get push template"
        )


@router.put("/{template_id}", response_model=PushTemplateResponse)
async def update_push_template(
    template_id: int,
    template_data: PushTemplateUpdate,
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Update push notification template

    Requires authentication. Admin only.

    Args:
        template_id: Template ID
        template_data: Update data

    Returns:
        Updated template

    Raises:
        404: If template not found
        400: If validation fails
    """
    service = PushTemplateService()

    try:
        template = await service.update_template(db, template_id, template_data)

        logger.info(
            f"Push template updated by user {current_user.id}",
            template_id=template_id,
            template_code=template.template_code
        )

        return template

    except ValueError as e:
        status_code = status.HTTP_404_NOT_FOUND if "not found" in str(e).lower() else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating push template: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update push template"
        )


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_push_template(
    template_id: int,
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Delete push notification template

    Requires authentication. Admin only.

    Args:
        template_id: Template ID

    Raises:
        404: If template not found
    """
    service = PushTemplateService()

    try:
        await service.delete_template(db, template_id)

        logger.info(
            f"Push template deleted by user {current_user.id}",
            template_id=template_id
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting push template: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete push template"
        )


@router.post("/{template_id}/preview", response_model=PushNotificationPreview)
async def preview_push_template(
    template_id: int,
    language: str = Query("es", pattern="^(es|fr|en)$", description="Language code"),
    variables: Optional[Dict[str, str]] = None,
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Preview push notification with sample data

    Requires authentication. Admin only.

    Args:
        template_id: Template ID
        language: Language code (es/fr/en)
        variables: Variable values for preview

    Returns:
        Preview with rendered content

    Raises:
        404: If template not found
    """
    service = PushTemplateService()

    try:
        # Get template
        template = await service.get_template(db, template_id)

        # Generate preview
        preview = service.preview_template(template, language, variables)

        return preview

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error previewing push template: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to preview push template"
        )
