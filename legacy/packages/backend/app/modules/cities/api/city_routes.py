"""
City API Routes.

Endpoints for cities and entities management.

Updated to support:
- entity_type (entity/department)
- parent_entity_id (hierarchy)
- ministry_id (FK to ministries)
- workflow_codes (JSONB array)
"""

from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status

import json as _json
from loguru import logger

from asyncpg import Connection
from app.database.connection import get_database
from app.modules.auth.middleware.auth_middleware import get_current_user, require_admin
from app.modules.users.models.user import UserResponse
from app.modules.cities.services.city_service import CityService, EntityService
from app.core.cache import invalidate_role_menu_cache, invalidate_workflow_mappings_cache
from app.modules.cities.models.city import (
    CityCreate, CityUpdate, CityResponse, CitySimple, CityListResponse,
    EntityCreate, EntityUpdate, EntityResponse, EntitySimple, EntityListResponse,
    EntityWithDetails, EntityWithDetailsListResponse, EntityType,
)

router = APIRouter(tags=["cities"])


async def _auto_seed_display_configs(db: Connection, workflow_codes: list) -> int:
    """Auto-create display configs for workflow codes that don't have one yet.
    Returns number of configs created."""
    if not workflow_codes:
        return 0
    created = 0
    for code in workflow_codes:
        existing = await db.fetchval(
            "SELECT 1 FROM workflow_display_config WHERE workflow_code = $1", code
        )
        if not existing:
            try:
                await db.execute("""
                    INSERT INTO workflow_display_config (
                        workflow_code, list_columns, preview_sections, labels, is_active
                    ) VALUES ($1, $2::jsonb, $3::jsonb, '{}'::jsonb, true)
                """,
                    code,
                    _json.dumps(["reference", "fullName", "createdAt", "status", "priority"]),
                    _json.dumps(["info", "extractedData", "documents", "contact"]),
                )
                created += 1
            except Exception as e:
                logger.warning(f"Auto-seed display config for {code} failed: {e}")
    if created:
        logger.info(f"Auto-seeded {created} display config(s) for entity workflow_codes")
    return created


# ============================================================================
# City Endpoints
# ============================================================================

@router.get("/cities", response_model=CityListResponse)
async def get_cities(
    region: Optional[str] = Query(None, description="Filter by region (Insular/Continental)"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    db: Connection = Depends(get_database),
):
    """Get all cities with optional filters."""
    service = CityService(db)
    return await service.get_all_cities(region=region, is_active=is_active)


@router.get("/cities/simple", response_model=List[CitySimple])
async def get_cities_simple(
    is_active: bool = Query(True, description="Filter by active status"),
    db: Connection = Depends(get_database),
):
    """Get simplified city list for dropdowns."""
    service = CityService(db)
    return await service.get_cities_simple(is_active)


@router.get("/cities/{city_id}", response_model=CityResponse)
async def get_city(
    city_id: UUID,
    db: Connection = Depends(get_database),
):
    """Get a city by ID."""
    service = CityService(db)
    city = await service.get_city_by_id(city_id)
    if not city:
        raise HTTPException(status_code=404, detail="City not found")
    return city


@router.post("/cities", response_model=CityResponse, status_code=status.HTTP_201_CREATED)
async def create_city(
    data: CityCreate,
    db: Connection = Depends(get_database),
    current_user: UserResponse = Depends(require_admin),
):
    """Create a new city. Requires admin role."""
    service = CityService(db)
    try:
        return await service.create_city(data, created_by=current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/cities/{city_id}", response_model=CityResponse)
async def update_city(
    city_id: UUID,
    data: CityUpdate,
    db: Connection = Depends(get_database),
    current_user: UserResponse = Depends(require_admin),
):
    """Update a city. Requires admin role."""
    service = CityService(db)
    try:
        city = await service.update_city(city_id, data, updated_by=current_user.id)
        if not city:
            raise HTTPException(status_code=404, detail="City not found")
        return city
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/cities/{city_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_city(
    city_id: UUID,
    db: Connection = Depends(get_database),
    current_user: UserResponse = Depends(require_admin),
):
    """Delete a city. Requires admin role."""
    service = CityService(db)
    deleted = await service.delete_city(city_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="City not found")


# ============================================================================
# Entity Endpoints
# ============================================================================

@router.get("/entities", response_model=EntityListResponse)
async def get_entities(
    entity_type: Optional[EntityType] = Query(None, description="Filter by entity type (entity/department)"),
    ministry_id: Optional[int] = Query(None, description="Filter by ministry ID"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    db: Connection = Depends(get_database),
):
    """Get all entities with optional filters."""
    service = EntityService(db)
    return await service.get_all_entities(
        entity_type=entity_type,
        ministry_id=ministry_id,
        is_active=is_active
    )


@router.get("/entities/with-details", response_model=EntityWithDetailsListResponse)
async def get_entities_with_details(
    entity_type: Optional[EntityType] = Query(None, description="Filter by entity type (entity/department)"),
    ministry_id: Optional[int] = Query(None, description="Filter by ministry ID"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    db: Connection = Depends(get_database),
):
    """Get all entities with parent and ministry details joined."""
    service = EntityService(db)
    return await service.get_all_entities_with_details(
        entity_type=entity_type,
        ministry_id=ministry_id,
        is_active=is_active
    )


@router.get("/entities/simple", response_model=List[EntitySimple])
async def get_entities_simple(
    is_active: bool = Query(True, description="Filter by active status"),
    db: Connection = Depends(get_database),
):
    """Get simplified entity list for dropdowns."""
    service = EntityService(db)
    return await service.get_entities_simple(is_active)


@router.get("/entities/{entity_id}", response_model=EntityResponse)
async def get_entity(
    entity_id: UUID,
    db: Connection = Depends(get_database),
):
    """Get an entity by ID."""
    service = EntityService(db)
    entity = await service.get_entity_by_id(entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity


@router.get("/entities/{entity_id}/details", response_model=EntityWithDetails)
async def get_entity_with_details(
    entity_id: UUID,
    db: Connection = Depends(get_database),
):
    """Get an entity by ID with parent and ministry details."""
    service = EntityService(db)
    entity = await service.get_entity_by_id_with_details(entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity


@router.get("/entities/{entity_id}/departments", response_model=List[EntityResponse])
async def get_entity_departments(
    entity_id: UUID,
    db: Connection = Depends(get_database),
):
    """Get all departments under a parent entity."""
    service = EntityService(db)
    # First verify parent exists
    parent = await service.get_entity_by_id(entity_id)
    if not parent:
        raise HTTPException(status_code=404, detail="Entity not found")
    return await service.get_departments_by_parent(entity_id)


@router.post("/entities", response_model=EntityResponse, status_code=status.HTTP_201_CREATED)
async def create_entity(
    data: EntityCreate,
    db: Connection = Depends(get_database),
    current_user: UserResponse = Depends(require_admin),
):
    """
    Create a new entity. Requires admin role.

    - For entity_type='department', parent_entity_id is required
    - workflow_codes must reference existing codes in workflows table
    """
    service = EntityService(db)
    try:
        result = await service.create_entity(data, created_by=current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    # Auto-seed display configs for new workflow codes + invalidate caches
    if data.workflow_codes:
        await _auto_seed_display_configs(db, data.workflow_codes)
        await invalidate_workflow_mappings_cache()
        await invalidate_role_menu_cache("_all_")
    return result


@router.patch("/entities/{entity_id}", response_model=EntityResponse)
async def update_entity(
    entity_id: UUID,
    data: EntityUpdate,
    db: Connection = Depends(get_database),
    current_user: UserResponse = Depends(require_admin),
):
    """Update an entity. Requires admin role."""
    service = EntityService(db)
    try:
        entity = await service.update_entity(entity_id, data, updated_by=current_user.id)
        if not entity:
            raise HTTPException(status_code=404, detail="Entity not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    # Auto-seed display configs if workflow_codes changed + invalidate caches
    if data.workflow_codes is not None:
        await _auto_seed_display_configs(db, data.workflow_codes)
        await invalidate_workflow_mappings_cache()
        await invalidate_role_menu_cache("_all_")
    return entity


@router.delete("/entities/{entity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entity(
    entity_id: UUID,
    db: Connection = Depends(get_database),
    current_user: UserResponse = Depends(require_admin),
):
    """Delete an entity. Requires admin role."""
    service = EntityService(db)
    deleted = await service.delete_entity(entity_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Entity not found")
