"""
USSD Configuration API Routes

Endpoints for managing USSD configurations for mobile operators

Endpoints:
- POST /communications/ussd - Create USSD configuration
- GET /communications/ussd - List all configurations
- GET /communications/ussd/{id} - Get configuration by ID
- GET /communications/ussd/operator/{operator} - Get by operator
- PUT /communications/ussd/{id} - Update configuration
- DELETE /communications/ussd/{id} - Delete configuration
- POST /communications/ussd/validate - Validate menu structure

Module: Communications (USSD)
"""

from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from loguru import logger
import asyncpg

from app.database.connection import get_database
from app.modules.auth.middleware.auth_middleware import get_current_user
from app.modules.users.models.user import UserResponse

from ..models.ussd import (
    UssdConfigCreate,
    UssdConfigUpdate,
    UssdConfigResponse,
    UssdConfigListResponse,
    UssdOperator,
    MenuNode,
    MenuValidationResult
)
from ..services.ussd_service import UssdService


router = APIRouter(prefix="/communications/ussd", tags=["Communications - USSD"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class ValidateMenuRequest(BaseModel):
    """Request model for menu validation"""
    menu_structure: List[MenuNode]


class DeleteResponse(BaseModel):
    """Response for delete operation"""
    message: str
    id: int


# ============================================================================
# USSD CONFIGURATION ENDPOINTS
# ============================================================================

@router.post(
    "",
    response_model=UssdConfigResponse,
    status_code=status.HTTP_201_CREATED
)
async def create_ussd_config(
    config_data: UssdConfigCreate,
    db: asyncpg.Connection = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Create new USSD configuration

    Creates a USSD configuration for a mobile operator with menu structure.

    **Required permissions:** `create:ussd_configs` or admin role

    **Args:**
    - operator_name: Mobile operator (getesa, muni, other_api_sms)
    - operator_code: Operator identification code
    - short_code: USSD short code (format: *XXX#)
    - menu_structure: Menu tree structure with navigation
    - session_timeout_seconds: Session timeout (30-600 seconds)
    - max_input_length: Maximum input length (1-500 characters)

    **Returns:**
    - Created USSD configuration with ID

    **Raises:**
    - 400: Invalid menu structure or duplicate short code
    - 401: Not authenticated
    - 403: Insufficient permissions
    """
    service = UssdService()

    # Get user ID from token
    user_id = current_user.id
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user token"
        )

    try:
        config = await service.create_config(db, config_data, user_id)
        logger.info(
            f"User {user_id} created USSD config {config.id} "
            f"for {config.operator_name}"
        )
        return config

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating USSD config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create USSD configuration"
        )


@router.get("", response_model=UssdConfigListResponse)
async def list_ussd_configs(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    db: asyncpg.Connection = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user)
):
    """
    List USSD configurations

    Returns paginated list of USSD configurations.

    **Required permissions:** `read:ussd_configs` or admin role

    **Query Parameters:**
    - page: Page number (default: 1)
    - page_size: Items per page (default: 20, max: 100)
    - is_active: Filter by active status (optional)

    **Returns:**
    - Paginated list of USSD configurations

    **Raises:**
    - 401: Not authenticated
    - 403: Insufficient permissions
    """
    service = UssdService()

    try:
        configs = await service.list_configs(db, page, page_size, is_active)
        return configs

    except Exception as e:
        logger.error(f"Error listing USSD configs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list USSD configurations"
        )


@router.get("/{config_id}", response_model=UssdConfigResponse)
async def get_ussd_config(
    config_id: int,
    db: asyncpg.Connection = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Get USSD configuration by ID

    Returns detailed USSD configuration including full menu structure.

    **Required permissions:** `read:ussd_configs` or admin role

    **Args:**
    - config_id: Configuration ID

    **Returns:**
    - USSD configuration details

    **Raises:**
    - 401: Not authenticated
    - 403: Insufficient permissions
    - 404: Configuration not found
    """
    service = UssdService()

    try:
        config = await service.get_config(db, config_id)
        return config

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting USSD config {config_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve USSD configuration"
        )


@router.get("/operator/{operator}", response_model=UssdConfigResponse)
async def get_ussd_config_by_operator(
    operator: UssdOperator,
    db: asyncpg.Connection = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Get USSD configuration by operator

    Returns the most recent configuration for a specific operator.

    **Required permissions:** `read:ussd_configs` or admin role

    **Args:**
    - operator: Operator name (getesa, muni, other_api_sms)

    **Returns:**
    - USSD configuration for operator

    **Raises:**
    - 401: Not authenticated
    - 403: Insufficient permissions
    - 404: Configuration not found for operator
    """
    service = UssdService()

    try:
        config = await service.get_config_by_operator(db, operator)
        return config

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting USSD config for operator {operator}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve USSD configuration"
        )


@router.put("/{config_id}", response_model=UssdConfigResponse)
async def update_ussd_config(
    config_id: int,
    config_data: UssdConfigUpdate,
    db: asyncpg.Connection = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Update USSD configuration

    Updates an existing USSD configuration. All fields are optional.

    **Required permissions:** `update:ussd_configs` or admin role

    **Args:**
    - config_id: Configuration ID
    - config_data: Updated configuration data

    **Returns:**
    - Updated USSD configuration

    **Raises:**
    - 400: Invalid data or duplicate values
    - 401: Not authenticated
    - 403: Insufficient permissions
    - 404: Configuration not found
    """
    service = UssdService()

    try:
        config = await service.update_config(db, config_id, config_data)
        logger.info(
            f"User {current_user.id} updated USSD config {config_id}"
        )
        return config

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating USSD config {config_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update USSD configuration"
        )


@router.delete("/{config_id}", response_model=DeleteResponse)
async def delete_ussd_config(
    config_id: int,
    db: asyncpg.Connection = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Delete USSD configuration

    Permanently deletes a USSD configuration.

    **Required permissions:** `delete:ussd_configs` or admin role

    **Args:**
    - config_id: Configuration ID

    **Returns:**
    - Success message

    **Raises:**
    - 401: Not authenticated
    - 403: Insufficient permissions
    - 404: Configuration not found
    """
    service = UssdService()

    try:
        await service.delete_config(db, config_id)
        logger.info(
            f"User {current_user.id} deleted USSD config {config_id}"
        )
        return DeleteResponse(
            message="USSD configuration deleted successfully",
            id=config_id
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting USSD config {config_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete USSD configuration"
        )


# ============================================================================
# VALIDATION ENDPOINT
# ============================================================================

@router.post("/validate", response_model=MenuValidationResult)
async def validate_menu_structure(
    request: ValidateMenuRequest,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Validate USSD menu structure

    Validates menu structure without saving. Checks for:
    - Root menu existence
    - Valid navigation paths
    - Circular references
    - Unreachable menus
    - Duplicate keys

    **Required permissions:** Authenticated user

    **Args:**
    - menu_structure: Menu tree structure to validate

    **Returns:**
    - Validation result with errors and warnings

    **Raises:**
    - 401: Not authenticated
    """
    service = UssdService()

    try:
        result = await service.validate_menu(request.menu_structure)
        return result

    except Exception as e:
        logger.error(f"Error validating menu structure: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to validate menu structure"
        )


# ============================================================================
# UTILITY ENDPOINTS
# ============================================================================

@router.get("/operators/list", response_model=List[Dict[str, str]])
async def list_operators():
    """
    List available mobile operators

    Returns list of supported mobile operators in Equatorial Guinea.

    **Public endpoint** - No authentication required

    **Returns:**
    - List of operators with name and description
    """
    operators = [
        {
            "value": UssdOperator.GETESA.value,
            "name": "Getesa",
            "description": "Getesa Mobile Network"
        },
        {
            "value": UssdOperator.MUNI.value,
            "name": "Muni",
            "description": "Muni Mobile Network"
        },
        {
            "value": UssdOperator.OTHER_API_SMS.value,
            "name": "Other API SMS",
            "description": "Other SMS Gateway API"
        }
    ]
    return operators
