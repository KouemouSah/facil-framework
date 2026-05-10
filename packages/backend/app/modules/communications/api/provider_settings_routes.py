"""
Communication Provider Settings API Routes

Endpoints for managing communication provider configurations.
"""

from fastapi import APIRouter, Depends, Query, status
from typing import Optional
import asyncpg

from ..models.provider_settings import (
    CommunicationProviderType,
    ProviderSettingsCreate,
    ProviderSettingsUpdate,
    ProviderSettingsResponse,
    ProviderSettingsListResponse,
    ProviderTestRequest,
    ProviderTestResponse
)
from ..services.provider_settings_service import ProviderSettingsService
from app.database.connection import get_database
from app.modules.auth.middleware.auth_middleware import get_current_user
from app.modules.users.models.user import UserResponse
from app.modules.permissions.middleware.permission_middleware import permission_required

router = APIRouter(prefix="/communications/providers", tags=["Communication Providers"])
service = ProviderSettingsService()


@router.post(
    "",
    response_model=ProviderSettingsResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Provider Configuration"
)
async def create_provider(
    data: ProviderSettingsCreate,
    db: asyncpg.Connection = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("communication.manage"))
):
    """
    Create a new communication provider configuration.

    Requires `manage:communications` permission.
    """
    return await service.create_provider(db, data, current_user.id)


@router.get(
    "",
    response_model=ProviderSettingsListResponse,
    summary="List Provider Configurations"
)
async def list_providers(
    provider_type: Optional[CommunicationProviderType] = Query(
        None, description="Filter by provider type"
    ),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: asyncpg.Connection = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("communication.view"))
):
    """
    List all communication provider configurations.

    Requires `read:communications` permission.
    """
    providers, total = await service.list_providers(
        db, provider_type, is_active, limit, offset
    )
    return ProviderSettingsListResponse(providers=providers, total=total)


@router.get(
    "/{provider_id}",
    response_model=ProviderSettingsResponse,
    summary="Get Provider Configuration"
)
async def get_provider(
    provider_id: int,
    db: asyncpg.Connection = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("communication.view"))
):
    """
    Get a provider configuration by ID.

    Requires `read:communications` permission.
    """
    return await service.get_provider(db, provider_id)


@router.get(
    "/code/{provider_code}",
    response_model=ProviderSettingsResponse,
    summary="Get Provider by Code"
)
async def get_provider_by_code(
    provider_code: str,
    db: asyncpg.Connection = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("communication.view"))
):
    """
    Get a provider configuration by code.

    Requires `read:communications` permission.
    """
    return await service.get_provider_by_code(db, provider_code)


@router.get(
    "/default/{provider_type}",
    response_model=Optional[ProviderSettingsResponse],
    summary="Get Default Provider for Type"
)
async def get_default_provider(
    provider_type: CommunicationProviderType,
    db: asyncpg.Connection = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("communication.view"))
):
    """
    Get the default provider for a specific type.

    Requires `read:communications` permission.
    """
    return await service.get_default_provider(db, provider_type)


@router.put(
    "/{provider_id}",
    response_model=ProviderSettingsResponse,
    summary="Update Provider Configuration"
)
async def update_provider(
    provider_id: int,
    data: ProviderSettingsUpdate,
    db: asyncpg.Connection = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("communication.manage"))
):
    """
    Update a provider configuration.

    Requires `manage:communications` permission.
    """
    return await service.update_provider(db, provider_id, data, current_user.id)


@router.delete(
    "/{provider_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Provider Configuration"
)
async def delete_provider(
    provider_id: int,
    db: asyncpg.Connection = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("communication.manage"))
):
    """
    Delete a provider configuration.

    Requires `manage:communications` permission.
    """
    await service.delete_provider(db, provider_id)
    return None


@router.post(
    "/test",
    response_model=ProviderTestResponse,
    summary="Test Provider Connection"
)
async def test_provider(
    request: ProviderTestRequest,
    db: asyncpg.Connection = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("communication.manage"))
):
    """
    Test a provider connection.

    Requires `manage:communications` permission.
    """
    return await service.test_provider(
        db, request.provider_code, request.test_recipient
    )
