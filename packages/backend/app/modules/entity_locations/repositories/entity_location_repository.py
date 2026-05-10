"""
Entity Location Repository - Database operations using asyncpg.

Handles all CRUD operations for entity_locations table.
"""

import json
from typing import Optional, List, Dict, Any
from uuid import UUID
from asyncpg import Connection

from ..models.entity_location import (
    EntityLocationCreate,
    EntityLocationUpdate,
)


class EntityLocationRepository:
    """Repository for entity_locations table operations."""

    def __init__(self, db: Connection):
        self.db = db

    async def get_all(
        self,
        entity_code: Optional[str] = None,
        city: Optional[str] = None,
        region: Optional[str] = None,
        is_active: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[List[Dict[str, Any]], int]:
        """Get all entity locations with optional filters and pagination."""
        conditions = []
        params = []
        param_idx = 1

        if entity_code:
            conditions.append(f"entity_code = ${param_idx}")
            params.append(entity_code.upper())
            param_idx += 1

        if city:
            conditions.append(f"city = ${param_idx}")
            params.append(city)
            param_idx += 1

        if region:
            conditions.append(f"region = ${param_idx}")
            params.append(region)
            param_idx += 1

        if is_active is not None:
            conditions.append(f"is_active = ${param_idx}")
            params.append(is_active)
            param_idx += 1

        where_clause = " AND ".join(conditions) if conditions else "TRUE"

        # Count total
        count_query = f"SELECT COUNT(*) FROM entity_locations WHERE {where_clause}"
        total = await self.db.fetchval(count_query, *params)

        # Get paginated results
        offset = (page - 1) * page_size
        query = f"""
            SELECT
                id, entity_code, city, region, location_name, location_address,
                phone, email, is_main_office, is_active, operating_hours, notes,
                created_at, updated_at, created_by, updated_by
            FROM entity_locations
            WHERE {where_clause}
            ORDER BY entity_code, is_main_office DESC, city
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        params.extend([page_size, offset])

        rows = await self.db.fetch(query, *params)
        items = [dict(row) for row in rows]

        return items, total

    async def get_by_id(self, location_id: UUID) -> Optional[Dict[str, Any]]:
        """Get a single entity location by ID."""
        query = """
            SELECT
                id, entity_code, city, region, location_name, location_address,
                phone, email, is_main_office, is_active, operating_hours, notes,
                created_at, updated_at, created_by, updated_by
            FROM entity_locations
            WHERE id = $1
        """
        row = await self.db.fetchrow(query, location_id)
        return dict(row) if row else None

    async def get_by_entity_code(
        self,
        entity_code: str,
        active_only: bool = True
    ) -> List[Dict[str, Any]]:
        """Get all locations for a specific entity."""
        query = """
            SELECT
                id, entity_code, city, region, location_name, location_address,
                phone, email, is_main_office, is_active, operating_hours, notes,
                created_at, updated_at
            FROM entity_locations
            WHERE entity_code = $1
        """
        if active_only:
            query += " AND is_active = TRUE"
        query += " ORDER BY is_main_office DESC, city"

        rows = await self.db.fetch(query, entity_code.upper())
        return [dict(row) for row in rows]

    async def get_by_entity_and_city(
        self,
        entity_code: str,
        city: str
    ) -> Optional[Dict[str, Any]]:
        """Get a specific location by entity code and city."""
        query = """
            SELECT
                id, entity_code, city, region, location_name, location_address,
                phone, email, is_main_office, is_active, operating_hours, notes,
                created_at, updated_at, created_by, updated_by
            FROM entity_locations
            WHERE entity_code = $1 AND city = $2
        """
        row = await self.db.fetchrow(query, entity_code.upper(), city)
        return dict(row) if row else None

    async def create(
        self,
        data: EntityLocationCreate,
        created_by: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """Create a new entity location."""
        # Validate city against cities table (source of truth)
        city_row = await self.db.fetchrow(
            "SELECT id, region FROM cities WHERE LOWER(name) = LOWER($1)",
            data.city
        )
        if not city_row:
            available = await self.db.fetch("SELECT name FROM cities ORDER BY name")
            city_names = [r['name'] for r in available]
            raise ValueError(
                f"Ciudad '{data.city}' no existe. Ciudades disponibles: {', '.join(city_names)}"
            )
        region = city_row['region']
        city_id = city_row['id']

        # Resolve entity_id from entity_code
        entity_id = await self.db.fetchval(
            "SELECT id FROM entities WHERE code = $1",
            data.entity_code.upper()
        )

        operating_hours = None
        if data.operating_hours:
            operating_hours = json.dumps(data.operating_hours.model_dump())

        query = """
            INSERT INTO entity_locations (
                entity_code, entity_id, city, city_id, region,
                location_name, location_address,
                phone, email, is_main_office, is_active, operating_hours, notes,
                created_by
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12::jsonb, $13, $14)
            RETURNING
                id, entity_code, city, city_id, region, location_name, location_address,
                phone, email, is_main_office, is_active, operating_hours, notes,
                created_at, updated_at, created_by, updated_by
        """
        row = await self.db.fetchrow(
            query,
            data.entity_code.upper(),
            entity_id,
            data.city,
            city_id,
            region,
            data.location_name,
            data.location_address,
            data.phone,
            data.email,
            data.is_main_office,
            data.is_active,
            operating_hours,
            data.notes,
            created_by,
        )
        return dict(row)

    async def update(
        self,
        location_id: UUID,
        data: EntityLocationUpdate,
        updated_by: Optional[UUID] = None
    ) -> Optional[Dict[str, Any]]:
        """Update an entity location."""
        # Build dynamic update query
        updates = []
        params = []
        param_idx = 1

        update_data = data.model_dump(exclude_unset=True)

        # Validate city against cities table if being changed
        if 'city' in update_data and update_data['city'] is not None:
            city_row = await self.db.fetchrow(
                "SELECT id, region FROM cities WHERE LOWER(name) = LOWER($1)",
                update_data['city']
            )
            if not city_row:
                available = await self.db.fetch("SELECT name FROM cities ORDER BY name")
                city_names = [r['name'] for r in available]
                raise ValueError(
                    f"Ciudad '{update_data['city']}' no existe. "
                    f"Ciudades disponibles: {', '.join(city_names)}"
                )
            # Auto-set region and city_id from cities table
            update_data['region'] = city_row['region']
            update_data['city_id'] = city_row['id']

        for field, value in update_data.items():
            if field == "operating_hours" and value is not None:
                value = json.dumps(value)
                updates.append(f"operating_hours = ${param_idx}::jsonb")
            else:
                updates.append(f"{field} = ${param_idx}")
            params.append(value)
            param_idx += 1

        if not updates:
            # Nothing to update
            return await self.get_by_id(location_id)

        # Add updated_by
        updates.append(f"updated_by = ${param_idx}")
        params.append(updated_by)
        param_idx += 1

        # Add location_id
        params.append(location_id)

        query = f"""
            UPDATE entity_locations
            SET {", ".join(updates)}, updated_at = NOW()
            WHERE id = ${param_idx}
            RETURNING
                id, entity_code, city, region, location_name, location_address,
                phone, email, is_main_office, is_active, operating_hours, notes,
                created_at, updated_at, created_by, updated_by
        """
        row = await self.db.fetchrow(query, *params)
        return dict(row) if row else None

    async def delete(self, location_id: UUID) -> bool:
        """Delete an entity location."""
        # Check all FK dependencies (NO ACTION constraints)
        slot_count = await self.db.fetchval(
            "SELECT COUNT(*) FROM appointment_slot_configs WHERE entity_location_id = $1",
            location_id
        )
        if slot_count > 0:
            raise ValueError(
                f"Cannot delete: {slot_count} slot config(s) reference this location"
            )

        hold_count = await self.db.fetchval(
            "SELECT COUNT(*) FROM appointment_holds WHERE entity_location_id = $1",
            location_id
        )
        if hold_count > 0:
            raise ValueError(
                f"Cannot delete: {hold_count} appointment hold(s) reference this location"
            )

        reservation_count = await self.db.fetchval(
            "SELECT COUNT(*) FROM appointment_reservations WHERE entity_location_id = $1",
            location_id
        )
        if reservation_count > 0:
            raise ValueError(
                f"Cannot delete: {reservation_count} appointment reservation(s) reference this location"
            )

        query = "DELETE FROM entity_locations WHERE id = $1"
        result = await self.db.execute(query, location_id)
        return result == "DELETE 1"

    async def toggle_active(
        self,
        location_id: UUID,
        updated_by: Optional[UUID] = None
    ) -> Optional[Dict[str, Any]]:
        """Toggle the is_active status of a location."""
        query = """
            UPDATE entity_locations
            SET is_active = NOT is_active, updated_by = $2, updated_at = NOW()
            WHERE id = $1
            RETURNING
                id, entity_code, city, region, location_name, location_address,
                phone, email, is_main_office, is_active, operating_hours, notes,
                created_at, updated_at, created_by, updated_by
        """
        row = await self.db.fetchrow(query, location_id, updated_by)
        return dict(row) if row else None

    async def exists(self, entity_code: str, city: str) -> bool:
        """Check if a location already exists for this entity+city combination."""
        query = """
            SELECT EXISTS(
                SELECT 1 FROM entity_locations
                WHERE entity_code = $1 AND city = $2
            )
        """
        return await self.db.fetchval(query, entity_code.upper(), city)

    async def get_slot_count(self, location_id: UUID) -> int:
        """Get the number of slot configs using this location."""
        return await self.db.fetchval(
            "SELECT COUNT(*) FROM appointment_slot_configs WHERE entity_location_id = $1",
            location_id
        ) or 0

    async def get_by_city(self, city: str, active_only: bool = True) -> List[Dict[str, Any]]:
        """Get all locations in a specific city."""
        query = """
            SELECT
                id, entity_code, city, region, location_name, location_address,
                phone, email, is_main_office, is_active
            FROM entity_locations
            WHERE city = $1
        """
        if active_only:
            query += " AND is_active = TRUE"
        query += " ORDER BY entity_code, is_main_office DESC"

        rows = await self.db.fetch(query, city)
        return [dict(row) for row in rows]

    async def get_by_region(self, region: str, active_only: bool = True) -> List[Dict[str, Any]]:
        """Get all locations in a specific region."""
        query = """
            SELECT
                id, entity_code, city, region, location_name, location_address,
                phone, email, is_main_office, is_active
            FROM entity_locations
            WHERE region = $1
        """
        if active_only:
            query += " AND is_active = TRUE"
        query += " ORDER BY entity_code, city"

        rows = await self.db.fetch(query, region)
        return [dict(row) for row in rows]

    async def get_distinct_entity_codes(self) -> List[str]:
        """Get all distinct entity codes from entity_locations table.

        Returns:
            List of distinct entity codes (sorted alphabetically)
        """
        rows = await self.db.fetch("""
            SELECT DISTINCT entity_code
            FROM entity_locations
            WHERE entity_code IS NOT NULL
            ORDER BY entity_code
        """)
        return [row['entity_code'] for row in rows]

    async def get_distinct_cities(self) -> List[str]:
        """Get all distinct cities from entity_locations table.

        Returns:
            List of distinct cities (sorted alphabetically)
        """
        rows = await self.db.fetch("""
            SELECT DISTINCT city
            FROM entity_locations
            WHERE city IS NOT NULL
            ORDER BY city
        """)
        return [row['city'] for row in rows]
