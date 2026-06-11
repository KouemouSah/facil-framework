"""
Entity Location API Routes.

Provides CRUD endpoints for entity locations management.
Admin endpoints require authentication, public endpoints for location selection.
"""

from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from asyncpg import Connection

from app.database.connection import get_database
from app.modules.auth.middleware.auth_middleware import get_current_user, require_admin
from app.modules.users.models.user import UserResponse

from ..models.entity_location import (
    EntityLocationCreate,
    EntityLocationUpdate,
    EntityLocationResponse,
    EntityLocationListResponse,
    VALID_REGIONS,
)
from ..services.entity_location_service import EntityLocationService
from ..repositories.entity_location_repository import EntityLocationRepository
from app.core.cache import invalidate_role_menu_cache, invalidate_workflow_mappings_cache


router = APIRouter(prefix="/entity-locations", tags=["Entity Locations"])


# ============================================================================
# PUBLIC ENDPOINTS (for location selection by citizens)
# ============================================================================

@router.get(
    "/by-entity/{entity_code}",
    response_model=List[EntityLocationResponse],
    summary="Get locations by entity code",
    description="Returns all active locations for a specific entity. Used for location selection.",
)
async def get_locations_by_entity(
    entity_code: str,
    db: Connection = Depends(get_database),
) -> List[EntityLocationResponse]:
    """Get all active locations for a specific entity."""
    entity_code = entity_code.upper().strip()
    if len(entity_code) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Entity code must be at least 2 characters",
        )

    service = EntityLocationService(db)
    return await service.get_by_entity_code(entity_code, active_only=True)


@router.get(
    "/by-city/{city}",
    response_model=List[EntityLocationResponse],
    summary="Get locations by city",
    description="Returns all active locations in a specific city.",
)
async def get_locations_by_city(
    city: str,
    db: Connection = Depends(get_database),
) -> List[EntityLocationResponse]:
    """Get all active locations in a specific city."""
    city = city.strip().title()
    if len(city) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="City name must be at least 2 characters",
        )

    service = EntityLocationService(db)
    return await service.get_by_city(city, active_only=True)


@router.get(
    "/by-region/{region}",
    response_model=List[EntityLocationResponse],
    summary="Get locations by region",
    description="Returns all active locations in a specific region (Insular or Continental).",
)
async def get_locations_by_region(
    region: str,
    db: Connection = Depends(get_database),
) -> List[EntityLocationResponse]:
    """Get all active locations in a specific region."""
    region = region.strip().title()
    if region not in VALID_REGIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid region. Must be one of: {VALID_REGIONS}",
        )

    service = EntityLocationService(db)
    return await service.get_by_region(region, active_only=True)


# ============================================================================
# UTILITY ENDPOINTS (must be before /{location_id} to avoid route conflicts)
# ============================================================================

@router.get(
    "/meta/entities",
    response_model=List[str],
    summary="Get entity codes from locations",
    description="Returns all distinct entity codes from entity_locations table.",
)
async def get_entity_codes(
    db: Connection = Depends(get_database),
) -> List[str]:
    """Get list of distinct entity codes from entity_locations."""
    repo = EntityLocationRepository(db)
    return await repo.get_distinct_entity_codes()


@router.get(
    "/meta/cities",
    response_model=List[str],
    summary="Get cities from locations",
    description="Returns all distinct cities from entity_locations table.",
)
async def get_cities(
    db: Connection = Depends(get_database),
) -> List[str]:
    """Get list of distinct cities from entity_locations."""
    repo = EntityLocationRepository(db)
    return await repo.get_distinct_cities()


# ============================================================================
# ADMIN ENDPOINTS (require authentication)
# ============================================================================

@router.get(
    "",
    response_model=EntityLocationListResponse,
    summary="List all entity locations",
    description="Returns paginated list of all entity locations with optional filters. Admin only.",
)
async def list_entity_locations(
    entity_code: Optional[str] = Query(None, description="Filter by entity code"),
    city: Optional[str] = Query(None, description="Filter by city"),
    region: Optional[str] = Query(None, description="Filter by region"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Connection = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
) -> EntityLocationListResponse:
    """List all entity locations with pagination and filters."""
    service = EntityLocationService(db)
    return await service.get_all(
        entity_code=entity_code,
        city=city,
        region=region,
        is_active=is_active,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{location_id}",
    response_model=EntityLocationResponse,
    summary="Get entity location by ID",
    description="Returns a single entity location by its ID. Admin only.",
)
async def get_entity_location(
    location_id: UUID,
    db: Connection = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
) -> EntityLocationResponse:
    """Get a single entity location by ID."""
    service = EntityLocationService(db)
    location = await service.get_by_id(location_id)
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity location not found",
        )
    return location


@router.post(
    "",
    response_model=EntityLocationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create entity location",
    description="Creates a new entity location. Admin only.",
)
async def create_entity_location(
    data: EntityLocationCreate,
    db: Connection = Depends(get_database),
    current_user: UserResponse = Depends(require_admin),
) -> EntityLocationResponse:
    """Create a new entity location."""
    service = EntityLocationService(db)
    try:
        result = await service.create(data, created_by=current_user.id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
    # Entity locations affect agent routing → invalidate agent menu caches
    await invalidate_workflow_mappings_cache()
    await invalidate_role_menu_cache("_all_")
    return result


@router.put(
    "/{location_id}",
    response_model=EntityLocationResponse,
    summary="Update entity location",
    description="Updates an existing entity location. Admin only.",
)
async def update_entity_location(
    location_id: UUID,
    data: EntityLocationUpdate,
    db: Connection = Depends(get_database),
    current_user: UserResponse = Depends(require_admin),
) -> EntityLocationResponse:
    """Update an existing entity location."""
    service = EntityLocationService(db)
    location = await service.update(location_id, data, updated_by=current_user.id)
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity location not found",
        )
    await invalidate_workflow_mappings_cache()
    await invalidate_role_menu_cache("_all_")
    return location


@router.delete(
    "/{location_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete entity location",
    description="Deletes an entity location. Fails if slots reference it. Admin only.",
)
async def delete_entity_location(
    location_id: UUID,
    db: Connection = Depends(get_database),
    current_user: UserResponse = Depends(require_admin),
) -> None:
    """Delete an entity location."""
    service = EntityLocationService(db)
    try:
        deleted = await service.delete(location_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Entity location not found",
            )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    await invalidate_workflow_mappings_cache()
    await invalidate_role_menu_cache("_all_")


@router.patch(
    "/{location_id}/toggle-active",
    response_model=EntityLocationResponse,
    summary="Toggle location active status",
    description="Toggles the is_active status of a location. Admin only.",
)
async def toggle_location_active(
    location_id: UUID,
    db: Connection = Depends(get_database),
    current_user: UserResponse = Depends(require_admin),
) -> EntityLocationResponse:
    """Toggle the active status of a location."""
    service = EntityLocationService(db)
    location = await service.toggle_active(location_id, updated_by=current_user.id)
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity location not found",
        )
    await invalidate_workflow_mappings_cache()
    await invalidate_role_menu_cache("_all_")
    return location
