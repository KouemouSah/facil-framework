"""
SMS Templates API Routes - CRUD endpoints for SMS template management

Endpoints:
- GET /communications/sms-templates - List all SMS templates
- GET /communications/sms-templates/{id} - Get template by ID
- GET /communications/sms-templates/code/{code} - Get template by code
- POST /communications/sms-templates - Create new template
- PUT /communications/sms-templates/{id} - Update template
- DELETE /communications/sms-templates/{id} - Delete template
- GET /communications/sms-templates/categories - Get categories with counts
- POST /communications/sms-templates/render - Render template with variables
- POST /communications/sms-templates/calculate-chars - Calculate character count

Module: Communications (SMS Templates Management)
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
import asyncpg
from loguru import logger

from app.database.connection import get_database
from app.modules.auth.middleware.auth_middleware import get_current_user
from app.modules.users.models.user import UserResponse
from ..models.sms_template import (
    SmsTemplateCreate,
    SmsTemplateUpdate,
    SmsTemplateResponse,
    SmsTemplateListResponse,
    SmsCharacterCount,
    SmsTemplateRenderRequest,
    SmsTemplateRenderResponse,
    SmsTemplateCategory
)
from ..services.sms_template_service import SmsTemplateService


router = APIRouter(prefix="/communications/sms-templates", tags=["SMS Templates"])


# ============================================================================
# CRUD ENDPOINTS
# ============================================================================

@router.get("", response_model=SmsTemplateListResponse)
async def list_sms_templates(
    category: Optional[str] = Query(None, description="Filter by category"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    search: Optional[str] = Query(None, description="Search in code, names, content"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: asyncpg.Connection = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
):
    """
    List SMS templates with pagination and filters

    Requires authentication. Admin or supervisor access recommended.

    Query Parameters:
    - **category**: Filter by template category (auth, notifications, payments, etc.)
    - **is_active**: Filter by active status (true/false)
    - **search**: Search in template code, names, and content
    - **page**: Page number (default: 1)
    - **page_size**: Items per page (default: 20, max: 100)

    Returns:
    - List of SMS templates with pagination metadata
    """
    service = SmsTemplateService()

    try:
        result = await service.list_templates(
            db,
            category=category,
            is_active=is_active,
            search=search,
            page=page,
            page_size=page_size
        )

        logger.info(
            f"User {current_user.id} listed SMS templates "
            f"(page {page}, {len(result.templates)} results)"
        )

        return result

    except Exception as e:
        logger.error(f"Error listing SMS templates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{template_id}", response_model=SmsTemplateResponse)
async def get_sms_template(
    template_id: int,
    db: asyncpg.Connection = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
):
    """
    Get SMS template by ID

    Requires authentication.

    Path Parameters:
    - **template_id**: Template ID

    Returns:
    - SMS template details
    """
    service = SmsTemplateService()

    template = await service.get_template_by_id(db, template_id)

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SMS template not found: {template_id}"
        )

    logger.info(f"User {current_user.id} retrieved SMS template {template_id}")

    return template


@router.get("/code/{template_code}", response_model=SmsTemplateResponse)
async def get_sms_template_by_code(
    template_code: str,
    db: asyncpg.Connection = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
):
    """
    Get SMS template by unique code

    Requires authentication.

    Path Parameters:
    - **template_code**: Unique template code (e.g., AUTH_VERIFICATION_CODE)

    Returns:
    - SMS template details
    """
    service = SmsTemplateService()

    template = await service.get_template_by_code(db, template_code)

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SMS template not found: {template_code}"
        )

    logger.info(f"User {current_user.id} retrieved SMS template {template_code}")

    return template


@router.post("", response_model=SmsTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_sms_template(
    template_data: SmsTemplateCreate,
    db: asyncpg.Connection = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
):
    """
    Create a new SMS template

    Requires authentication. Admin access recommended.

    Request Body:
    - **template_code**: Unique template code (UPPERCASE_WITH_UNDERSCORES)
    - **name_es/fr/en**: Template names in multiple languages
    - **content_es/fr/en**: SMS content with {{variable}} placeholders
    - **variables**: List of variable names used in template
    - **category**: Template category
    - **max_segments**: Maximum allowed SMS segments (1-10)
    - **is_active**: Whether template is active

    Returns:
    - Created SMS template
    """
    service = SmsTemplateService()

    try:
        user_id = current_user.id

        template = await service.create_template(db, template_data, created_by=user_id)

        logger.info(
            f"User {user_id} created SMS template: {template_data.template_code}"
        )

        return template

    except asyncpg.UniqueViolationError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Template code already exists: {template_data.template_code}"
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating SMS template: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{template_id}", response_model=SmsTemplateResponse)
async def update_sms_template(
    template_id: int,
    template_data: SmsTemplateUpdate,
    db: asyncpg.Connection = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
):
    """
    Update an SMS template

    Requires authentication. Admin access recommended.

    Path Parameters:
    - **template_id**: Template ID to update

    Request Body:
    - All fields are optional
    - Only provided fields will be updated

    Returns:
    - Updated SMS template
    """
    service = SmsTemplateService()

    try:
        user_id = current_user.id

        template = await service.update_template(
            db,
            template_id,
            template_data,
            updated_by=user_id
        )

        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"SMS template not found: {template_id}"
            )

        logger.info(f"User {user_id} updated SMS template: {template_id}")

        return template

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating SMS template: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sms_template(
    template_id: int,
    db: asyncpg.Connection = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
):
    """
    Delete an SMS template

    Requires authentication. Admin access required.

    Path Parameters:
    - **template_id**: Template ID to delete

    Returns:
    - 204 No Content on success
    """
    service = SmsTemplateService()

    deleted = await service.delete_template(db, template_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SMS template not found: {template_id}"
        )

    logger.info(f"User {current_user.id} deleted SMS template: {template_id}")

    return None


# ============================================================================
# UTILITY ENDPOINTS
# ============================================================================

@router.get("/categories/list")
async def get_sms_template_categories(
    db: asyncpg.Connection = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
):
    """
    Get list of template categories with counts

    Returns:
    - List of categories with template counts
    """
    service = SmsTemplateService()

    try:
        categories = await service.get_categories(db)

        # Also include enum categories with 0 count if not present
        all_categories = []
        existing_cats = {cat["category"] for cat in categories}

        for enum_cat in SmsTemplateCategory:
            matching = next(
                (c for c in categories if c["category"] == enum_cat.value),
                None
            )
            if matching:
                all_categories.append(matching)
            else:
                all_categories.append({
                    "category": enum_cat.value,
                    "total_templates": 0,
                    "active_templates": 0
                })

        return {
            "categories": all_categories,
            "total": len(all_categories)
        }

    except Exception as e:
        logger.error(f"Error getting SMS template categories: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/render", response_model=SmsTemplateRenderResponse)
async def render_sms_template(
    request: SmsTemplateRenderRequest,
    db: asyncpg.Connection = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
):
    """
    Render SMS template with variable substitution

    Use this to preview how a template will look with actual data.

    Request Body:
    - **template_code**: Template code to render
    - **language**: Language code (es, fr, en)
    - **variables**: Dictionary of variable values

    Returns:
    - Rendered SMS content with character count
    """
    service = SmsTemplateService()

    try:
        result = await service.render_template(db, request)

        logger.info(
            f"User {current_user.id} rendered template "
            f"{request.template_code} ({request.language})"
        )

        return result

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error rendering SMS template: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/calculate-chars", response_model=SmsCharacterCount)
async def calculate_character_count(
    content: str = Query(..., description="SMS content to analyze"),
    current_user: UserResponse = Depends(get_current_user),
):
    """
    Calculate character count and SMS segmentation for content

    Useful for real-time character counting in UI.

    Query Parameters:
    - **content**: SMS content to analyze

    Returns:
    - Character count, segment count, and remaining characters
    """
    service = SmsTemplateService()

    try:
        result = service.calculate_character_count(content)

        return result

    except Exception as e:
        logger.error(f"Error calculating character count: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# HEALTHCHECK
# ============================================================================

@router.get("/health")
async def health_check():
    """
    Health check endpoint for SMS templates service

    Returns:
    - Service status
    """
    return {
        "status": "healthy",
        "service": "sms-templates",
        "version": "1.0.0"
    }
