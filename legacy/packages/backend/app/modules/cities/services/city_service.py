"""
City Service.

Business logic layer for cities and entities management.
"""

from typing import List, Optional
from uuid import UUID
import logging

from asyncpg import Connection
from app.modules.cities.repositories.city_repository import CityRepository, EntityRepository
from app.modules.cities.models.city import (
    CityCreate, CityUpdate, CityResponse, CitySimple, CityListResponse,
    EntityCreate, EntityUpdate, EntityResponse, EntitySimple, EntityListResponse,
    EntityWithDetails, EntityWithDetailsListResponse, EntityType,
)

logger = logging.getLogger(__name__)


class CityService:
    """Service for city operations."""

    def __init__(self, db: Connection):
        self.repository = CityRepository(db)

    async def get_all_cities(
        self,
        region: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> CityListResponse:
        """Get all cities with optional filters."""
        cities = await self.repository.get_all_cities(region=region, is_active=is_active)
        return CityListResponse(items=cities, total=len(cities))

    async def get_cities_simple(self, is_active: bool = True) -> List[CitySimple]:
        """Get simplified city list for dropdowns."""
        return await self.repository.get_cities_simple(is_active)

    async def get_city_by_id(self, city_id: UUID) -> Optional[CityResponse]:
        """Get a city by ID."""
        return await self.repository.get_city_by_id(city_id)

    async def get_city_by_name(self, name: str) -> Optional[CityResponse]:
        """Get a city by name."""
        return await self.repository.get_city_by_name(name)

    async def create_city(
        self,
        data: CityCreate,
        created_by: Optional[UUID] = None
    ) -> CityResponse:
        """Create a new city."""
        # Check if city already exists
        existing = await self.repository.get_city_by_name(data.name)
        if existing:
            raise ValueError(f"City '{data.name}' already exists")

        return await self.repository.create_city(data, created_by)

    async def update_city(
        self,
        city_id: UUID,
        data: CityUpdate,
        updated_by: Optional[UUID] = None
    ) -> Optional[CityResponse]:
        """Update a city."""
        # Check if city exists
        existing = await self.repository.get_city_by_id(city_id)
        if not existing:
            return None

        # Check for name conflict if name is being updated
        if data.name and data.name.lower() != existing.name.lower():
            conflict = await self.repository.get_city_by_name(data.name)
            if conflict:
                raise ValueError(f"City '{data.name}' already exists")

        return await self.repository.update_city(city_id, data, updated_by)

    async def delete_city(self, city_id: UUID) -> bool:
        """Delete a city."""
        return await self.repository.delete_city(city_id)


class EntityService:
    """Service for entity operations.

    Supports the updated entity model with:
    - entity_type (entity/department)
    - parent_entity_id (hierarchy)
    - ministry_id (FK to ministries)
    - workflow_codes (JSONB array)
    """

    def __init__(self, db: Connection):
        self.repository = EntityRepository(db)

    # =========================================================================
    # READ OPERATIONS
    # =========================================================================

    async def get_all_entities(
        self,
        entity_type: Optional[EntityType] = None,
        ministry_id: Optional[int] = None,
        is_active: Optional[bool] = None,
    ) -> EntityListResponse:
        """Get all entities with optional filters."""
        entity_type_str = entity_type.value if entity_type else None
        entities = await self.repository.get_all_entities(
            entity_type=entity_type_str,
            ministry_id=ministry_id,
            is_active=is_active
        )
        return EntityListResponse(
            items=[EntityResponse(**e) for e in entities],
            total=len(entities)
        )

    async def get_all_entities_with_details(
        self,
        entity_type: Optional[EntityType] = None,
        ministry_id: Optional[int] = None,
        is_active: Optional[bool] = None,
    ) -> EntityWithDetailsListResponse:
        """Get all entities with parent and ministry details."""
        entity_type_str = entity_type.value if entity_type else None
        entities = await self.repository.get_all_entities_with_details(
            entity_type=entity_type_str,
            ministry_id=ministry_id,
            is_active=is_active
        )
        return EntityWithDetailsListResponse(
            items=[EntityWithDetails(**e) for e in entities],
            total=len(entities)
        )

    async def get_entities_simple(self, is_active: bool = True) -> List[EntitySimple]:
        """Get simplified entity list for dropdowns."""
        entities = await self.repository.get_entities_simple(is_active)
        return [EntitySimple(**e) for e in entities]

    async def get_entity_by_id(self, entity_id: UUID) -> Optional[EntityResponse]:
        """Get an entity by ID."""
        entity = await self.repository.get_entity_by_id(entity_id)
        return EntityResponse(**entity) if entity else None

    async def get_entity_by_id_with_details(self, entity_id: UUID) -> Optional[EntityWithDetails]:
        """Get an entity by ID with parent and ministry details."""
        entity = await self.repository.get_entity_by_id_with_details(entity_id)
        return EntityWithDetails(**entity) if entity else None

    async def get_entity_by_code(self, code: str) -> Optional[EntityResponse]:
        """Get an entity by code."""
        entity = await self.repository.get_entity_by_code(code)
        return EntityResponse(**entity) if entity else None

    async def get_departments_by_parent(self, parent_entity_id: UUID) -> List[EntityResponse]:
        """Get all departments under a parent entity."""
        departments = await self.repository.get_departments_by_parent(parent_entity_id)
        return [EntityResponse(**d) for d in departments]

    # =========================================================================
    # CREATE OPERATIONS
    # =========================================================================

    async def create_entity(
        self,
        data: EntityCreate,
        created_by: Optional[UUID] = None
    ) -> EntityResponse:
        """Create a new entity."""
        # Check if entity already exists
        existing = await self.repository.get_entity_by_code(data.code)
        if existing:
            raise ValueError(f"Entity '{data.code}' already exists")

        # Validate department has parent
        if data.entity_type == EntityType.DEPARTMENT and not data.parent_entity_id:
            raise ValueError("Departments must have a parent_entity_id")

        # Validate parent exists if provided
        if data.parent_entity_id:
            parent = await self.repository.get_entity_by_id(data.parent_entity_id)
            if not parent:
                raise ValueError(f"Parent entity '{data.parent_entity_id}' not found")

        # Validate workflow_codes if provided
        if data.workflow_codes:
            is_valid, invalid_codes = await self.repository.validate_workflow_codes(data.workflow_codes)
            if not is_valid:
                raise ValueError(f"Invalid workflow codes: {', '.join(invalid_codes)}")

        result = await self.repository.create_entity(data, created_by)
        return EntityResponse(**result)

    # =========================================================================
    # UPDATE OPERATIONS
    # =========================================================================

    async def update_entity(
        self,
        entity_id: UUID,
        data: EntityUpdate,
        updated_by: Optional[UUID] = None
    ) -> Optional[EntityResponse]:
        """Update an entity."""
        # Check if entity exists
        existing = await self.repository.get_entity_by_id(entity_id)
        if not existing:
            return None

        # Check for code conflict if code is being updated
        if data.code and data.code.upper() != existing['code'].upper():
            conflict = await self.repository.get_entity_by_code(data.code)
            if conflict:
                raise ValueError(f"Entity '{data.code}' already exists")

        # Validate parent if changing to department
        new_type = data.entity_type if data.entity_type else existing.get('entity_type')
        new_parent = data.parent_entity_id if data.parent_entity_id is not None else existing.get('parent_entity_id')

        if new_type == EntityType.DEPARTMENT.value and not new_parent:
            raise ValueError("Departments must have a parent_entity_id")

        # Validate workflow_codes if provided — only validate NEW codes
        # (existing codes may reference deactivated workflows and should not block edits)
        if data.workflow_codes:
            existing_codes = set(existing.get('workflow_codes') or [])
            new_codes = [c for c in data.workflow_codes if c not in existing_codes]
            if new_codes:
                is_valid, invalid_codes = await self.repository.validate_workflow_codes(new_codes)
                if not is_valid:
                    raise ValueError(f"Invalid workflow codes: {', '.join(invalid_codes)}")

        result = await self.repository.update_entity(entity_id, data, updated_by)
        return EntityResponse(**result) if result else None

    # =========================================================================
    # DELETE OPERATIONS
    # =========================================================================

    async def delete_entity(self, entity_id: UUID) -> bool:
        """Delete an entity."""
        return await self.repository.delete_entity(entity_id)
