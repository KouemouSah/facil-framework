"""
Entity Location Service - Business logic for entity locations.

Handles validation, business rules, and orchestrates repository operations.
"""

import math
from typing import Optional, List
from uuid import UUID
from asyncpg import Connection

from ..models.entity_location import (
    EntityLocationCreate,
    EntityLocationUpdate,
    EntityLocationResponse,
    EntityLocationListResponse,
    OperatingHours,
)
from ..repositories.entity_location_repository import EntityLocationRepository


class EntityLocationService:
    """Service for entity location business logic."""

    def __init__(self, db: Connection):
        self.db = db
        self.repository = EntityLocationRepository(db)

    async def get_all(
        self,
        entity_code: Optional[str] = None,
        city: Optional[str] = None,
        region: Optional[str] = None,
        is_active: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> EntityLocationListResponse:
        """Get all entity locations with filters and pagination."""
        items, total = await self.repository.get_all(
            entity_code=entity_code,
            city=city,
            region=region,
            is_active=is_active,
            page=page,
            page_size=page_size,
        )

        # Parse operating_hours from JSONB
        response_items = []
        for item in items:
            response_items.append(self._to_response(item))

        total_pages = math.ceil(total / page_size) if total > 0 else 1

        return EntityLocationListResponse(
            items=response_items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    async def get_by_id(self, location_id: UUID) -> Optional[EntityLocationResponse]:
        """Get a single entity location by ID."""
        item = await self.repository.get_by_id(location_id)
        if not item:
            return None
        return self._to_response(item)

    async def get_by_entity_code(
        self,
        entity_code: str,
        active_only: bool = True
    ) -> List[EntityLocationResponse]:
        """Get all locations for a specific entity."""
        items = await self.repository.get_by_entity_code(
            entity_code=entity_code,
            active_only=active_only
        )
        return [self._to_response(item) for item in items]

    async def create(
        self,
        data: EntityLocationCreate,
        created_by: Optional[UUID] = None
    ) -> EntityLocationResponse:
        """Create a new entity location."""
        # Check if location already exists
        exists = await self.repository.exists(data.entity_code, data.city)
        if exists:
            raise ValueError(
                f"A location already exists for {data.entity_code} in {data.city}"
            )

        item = await self.repository.create(data, created_by)
        return self._to_response(item)

    async def update(
        self,
        location_id: UUID,
        data: EntityLocationUpdate,
        updated_by: Optional[UUID] = None
    ) -> Optional[EntityLocationResponse]:
        """Update an entity location."""
        # Check if location exists
        existing = await self.repository.get_by_id(location_id)
        if not existing:
            return None

        item = await self.repository.update(location_id, data, updated_by)
        if not item:
            return None
        return self._to_response(item)

    async def delete(self, location_id: UUID) -> bool:
        """Delete an entity location."""
        # Check if location exists
        existing = await self.repository.get_by_id(location_id)
        if not existing:
            raise ValueError("Location not found")

        # Check for dependent slots
        slot_count = await self.repository.get_slot_count(location_id)
        if slot_count > 0:
            raise ValueError(
                f"Cannot delete: {slot_count} slot configurations are using this location. "
                "Please delete or reassign the slots first."
            )

        return await self.repository.delete(location_id)

    async def toggle_active(
        self,
        location_id: UUID,
        updated_by: Optional[UUID] = None
    ) -> Optional[EntityLocationResponse]:
        """Toggle the active status of a location."""
        item = await self.repository.toggle_active(location_id, updated_by)
        if not item:
            return None
        return self._to_response(item)

    async def get_by_city(
        self,
        city: str,
        active_only: bool = True
    ) -> List[EntityLocationResponse]:
        """Get all locations in a specific city."""
        items = await self.repository.get_by_city(city, active_only)
        return [self._to_response(item) for item in items]

    async def get_by_region(
        self,
        region: str,
        active_only: bool = True
    ) -> List[EntityLocationResponse]:
        """Get all locations in a specific region."""
        items = await self.repository.get_by_region(region, active_only)
        return [self._to_response(item) for item in items]

    def _to_response(self, item: dict) -> EntityLocationResponse:
        """Convert a database row to a response model."""
        # Parse operating_hours if it's a dict/JSON
        operating_hours = None
        if item.get("operating_hours"):
            oh_data = item["operating_hours"]
            if isinstance(oh_data, str):
                import json
                oh_data = json.loads(oh_data)
            if isinstance(oh_data, dict):
                operating_hours = OperatingHours(**oh_data)

        return EntityLocationResponse(
            id=item["id"],
            entity_code=item["entity_code"],
            city=item["city"],
            region=item["region"],
            location_name=item["location_name"],
            location_address=item.get("location_address"),
            phone=item.get("phone"),
            email=item.get("email"),
            is_main_office=item["is_main_office"],
            is_active=item["is_active"],
            operating_hours=operating_hours,
            notes=item.get("notes"),
            created_at=item["created_at"],
            updated_at=item["updated_at"],
        )
