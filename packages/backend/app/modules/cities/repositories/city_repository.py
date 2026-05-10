"""
City Repository.

Data access layer for cities and entities tables.
"""

from typing import List, Optional
from uuid import UUID
import logging

from asyncpg import Connection
from app.modules.cities.models.city import (
    CityCreate, CityUpdate, CityResponse, CitySimple,
    EntityCreate, EntityUpdate, EntityResponse, EntitySimple,
)

logger = logging.getLogger(__name__)


class CityRepository:
    """Repository for city operations."""

    def __init__(self, db: Connection):
        self.db = db

    async def get_all_cities(
        self,
        region: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> List[CityResponse]:
        """Get all cities with optional filters."""
        query = """
            SELECT id, name, region, description, is_capital, is_active,
                   created_at, updated_at
            FROM cities
            WHERE 1=1
        """
        params = []
        param_idx = 1

        if region:
            query += f" AND region = ${param_idx}"
            params.append(region)
            param_idx += 1

        if is_active is not None:
            query += f" AND is_active = ${param_idx}"
            params.append(is_active)
            param_idx += 1

        query += " ORDER BY is_capital DESC, name ASC"

        rows = await self.db.fetch(query, *params)
        return [CityResponse(**dict(row)) for row in rows]

    async def get_cities_simple(self, is_active: bool = True) -> List[CitySimple]:
        """Get simplified city list for dropdowns."""
        query = """
            SELECT id, name, region, is_capital
            FROM cities
            WHERE is_active = $1
            ORDER BY is_capital DESC, name ASC
        """
        rows = await self.db.fetch(query, is_active)
        return [CitySimple(**dict(row)) for row in rows]

    async def get_city_by_id(self, city_id: UUID) -> Optional[CityResponse]:
        """Get a city by ID."""
        query = """
            SELECT id, name, region, description, is_capital, is_active,
                   created_at, updated_at
            FROM cities
            WHERE id = $1
        """
        row = await self.db.fetchrow(query, city_id)
        return CityResponse(**dict(row)) if row else None

    async def get_city_by_name(self, name: str) -> Optional[CityResponse]:
        """Get a city by name."""
        query = """
            SELECT id, name, region, description, is_capital, is_active,
                   created_at, updated_at
            FROM cities
            WHERE LOWER(name) = LOWER($1)
        """
        row = await self.db.fetchrow(query, name)
        return CityResponse(**dict(row)) if row else None

    async def create_city(
        self,
        data: CityCreate,
        created_by: Optional[UUID] = None
    ) -> CityResponse:
        """Create a new city."""
        query = """
            INSERT INTO cities (name, region, description, is_capital, is_active, created_by)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id, name, region, description, is_capital, is_active,
                      created_at, updated_at
        """
        row = await self.db.fetchrow(
            query,
            data.name,
            data.region,
            data.description,
            data.is_capital,
            data.is_active,
            created_by,
        )
        return CityResponse(**dict(row))

    async def update_city(
        self,
        city_id: UUID,
        data: CityUpdate,
        updated_by: Optional[UUID] = None
    ) -> Optional[CityResponse]:
        """Update a city."""
        # Build dynamic update query
        updates = []
        params = []
        param_idx = 1

        if data.name is not None:
            updates.append(f"name = ${param_idx}")
            params.append(data.name)
            param_idx += 1

        if data.region is not None:
            updates.append(f"region = ${param_idx}")
            params.append(data.region)
            param_idx += 1

        if data.description is not None:
            updates.append(f"description = ${param_idx}")
            params.append(data.description)
            param_idx += 1

        if data.is_capital is not None:
            updates.append(f"is_capital = ${param_idx}")
            params.append(data.is_capital)
            param_idx += 1

        if data.is_active is not None:
            updates.append(f"is_active = ${param_idx}")
            params.append(data.is_active)
            param_idx += 1

        if not updates:
            return await self.get_city_by_id(city_id)

        updates.append(f"updated_by = ${param_idx}")
        params.append(updated_by)
        param_idx += 1

        updates.append("updated_at = NOW()")

        params.append(city_id)
        query = f"""
            UPDATE cities
            SET {', '.join(updates)}
            WHERE id = ${param_idx}
            RETURNING id, name, region, description, is_capital, is_active,
                      created_at, updated_at
        """
        row = await self.db.fetchrow(query, *params)
        return CityResponse(**dict(row)) if row else None

    async def delete_city(self, city_id: UUID) -> bool:
        """Delete a city."""
        query = "DELETE FROM cities WHERE id = $1"
        result = await self.db.execute(query, city_id)
        return "DELETE 1" in result

    async def count_cities(self, is_active: Optional[bool] = None) -> int:
        """Count cities."""
        query = "SELECT COUNT(*) FROM cities"
        params = []
        if is_active is not None:
            query += " WHERE is_active = $1"
            params.append(is_active)
        row = await self.db.fetchrow(query, *params)
        return row["count"] if row else 0


class EntityRepository:
    """Repository for entity operations.

    Updated to support:
    - entity_type (entity/department)
    - parent_entity_id (FK for departments)
    - ministry_id (FK to ministries)
    - workflow_codes (JSONB array)
    """

    def __init__(self, db: Connection):
        self.db = db

    # =========================================================================
    # BASE FIELDS for all queries
    # =========================================================================
    _BASE_FIELDS = """
        e.id, e.code, e.name, e.description,
        e.entity_type::text as entity_type,
        e.parent_entity_id, e.ministry_id,
        COALESCE(e.workflow_codes, '[]'::jsonb) as workflow_codes,
        e.is_active, e.created_at, e.updated_at
    """

    _DETAILS_FIELDS = """
        e.id, e.code, e.name, e.description,
        e.entity_type::text as entity_type,
        e.parent_entity_id, e.ministry_id,
        COALESCE(e.workflow_codes, '[]'::jsonb) as workflow_codes,
        e.is_active, e.created_at, e.updated_at,
        pe.code as parent_entity_code,
        pe.name as parent_entity_name,
        m.ministry_code,
        m.name_es as ministry_name,
        CASE
            WHEN e.workflow_codes IS NOT NULL AND jsonb_array_length(e.workflow_codes) > 0
            THEN e.workflow_codes
            WHEN pe.workflow_codes IS NOT NULL AND jsonb_array_length(pe.workflow_codes) > 0
            THEN pe.workflow_codes
            ELSE '[]'::jsonb
        END as resolved_workflow_codes,
        CASE
            WHEN e.workflow_codes IS NOT NULL AND jsonb_array_length(e.workflow_codes) > 0
            THEN jsonb_array_length(e.workflow_codes)
            WHEN pe.workflow_codes IS NOT NULL AND jsonb_array_length(pe.workflow_codes) > 0
            THEN jsonb_array_length(pe.workflow_codes)
            ELSE 0
        END as workflow_count
    """

    # =========================================================================
    # READ OPERATIONS
    # =========================================================================

    async def get_all_entities(
        self,
        entity_type: Optional[str] = None,
        ministry_id: Optional[int] = None,
        parent_entity_id: Optional[UUID] = None,
        is_active: Optional[bool] = None,
    ) -> List[dict]:
        """Get all entities with optional filters."""
        query = f"""
            SELECT {self._BASE_FIELDS}
            FROM entities e
            WHERE 1=1
        """
        params = []
        param_idx = 1

        if entity_type is not None:
            query += f" AND e.entity_type = ${param_idx}::entity_type_enum"
            params.append(entity_type)
            param_idx += 1

        if ministry_id is not None:
            query += f" AND e.ministry_id = ${param_idx}"
            params.append(ministry_id)
            param_idx += 1

        if parent_entity_id is not None:
            query += f" AND e.parent_entity_id = ${param_idx}"
            params.append(parent_entity_id)
            param_idx += 1

        if is_active is not None:
            query += f" AND e.is_active = ${param_idx}"
            params.append(is_active)
            param_idx += 1

        query += " ORDER BY e.entity_type, e.code ASC"

        rows = await self.db.fetch(query, *params)
        return [self._row_to_dict(row) for row in rows]

    async def get_all_entities_with_details(
        self,
        entity_type: Optional[str] = None,
        ministry_id: Optional[int] = None,
        is_active: Optional[bool] = None,
    ) -> List[dict]:
        """Get all entities with parent and ministry details."""
        query = f"""
            SELECT {self._DETAILS_FIELDS}
            FROM entities e
            LEFT JOIN entities pe ON pe.id = e.parent_entity_id
            LEFT JOIN ministries m ON m.id = e.ministry_id
            WHERE 1=1
        """
        params = []
        param_idx = 1

        if entity_type is not None:
            query += f" AND e.entity_type = ${param_idx}::entity_type_enum"
            params.append(entity_type)
            param_idx += 1

        if ministry_id is not None:
            query += f" AND e.ministry_id = ${param_idx}"
            params.append(ministry_id)
            param_idx += 1

        if is_active is not None:
            query += f" AND e.is_active = ${param_idx}"
            params.append(is_active)
            param_idx += 1

        query += " ORDER BY e.entity_type, e.code ASC"

        rows = await self.db.fetch(query, *params)
        return [self._row_to_dict_with_details(row) for row in rows]

    async def get_entities_simple(self, is_active: bool = True) -> List[dict]:
        """Get simplified entity list for dropdowns."""
        query = """
            SELECT id, code, name, entity_type::text as entity_type
            FROM entities
            WHERE is_active = $1
            ORDER BY entity_type, code ASC
        """
        rows = await self.db.fetch(query, is_active)
        return [dict(row) for row in rows]

    async def get_entity_by_id(self, entity_id: UUID) -> Optional[dict]:
        """Get an entity by ID."""
        query = f"""
            SELECT {self._BASE_FIELDS}
            FROM entities e
            WHERE e.id = $1
        """
        row = await self.db.fetchrow(query, entity_id)
        return self._row_to_dict(row) if row else None

    async def get_entity_by_id_with_details(self, entity_id: UUID) -> Optional[dict]:
        """Get an entity by ID with parent and ministry details."""
        query = f"""
            SELECT {self._DETAILS_FIELDS}
            FROM entities e
            LEFT JOIN entities pe ON pe.id = e.parent_entity_id
            LEFT JOIN ministries m ON m.id = e.ministry_id
            WHERE e.id = $1
        """
        row = await self.db.fetchrow(query, entity_id)
        return self._row_to_dict_with_details(row) if row else None

    async def get_entity_by_code(self, code: str) -> Optional[dict]:
        """Get an entity by code."""
        query = f"""
            SELECT {self._BASE_FIELDS}
            FROM entities e
            WHERE UPPER(e.code) = UPPER($1)
        """
        row = await self.db.fetchrow(query, code)
        return self._row_to_dict(row) if row else None

    # =========================================================================
    # CREATE OPERATIONS
    # =========================================================================

    async def create_entity(
        self,
        data: EntityCreate,
        created_by: Optional[UUID] = None
    ) -> dict:
        """Create a new entity."""
        import json

        # Note: RETURNING clause cannot use alias prefix like SELECT queries
        query = """
            INSERT INTO entities (
                code, name, description, entity_type, parent_entity_id,
                ministry_id, workflow_codes, is_active, created_by
            )
            VALUES ($1, $2, $3, $4::entity_type_enum, $5, $6, $7::jsonb, $8, $9)
            RETURNING
                id, code, name, description,
                entity_type::text as entity_type,
                parent_entity_id, ministry_id,
                COALESCE(workflow_codes, '[]'::jsonb) as workflow_codes,
                is_active, created_at, updated_at
        """
        row = await self.db.fetchrow(
            query,
            data.code,
            data.name,
            data.description,
            data.entity_type.value if hasattr(data.entity_type, 'value') else data.entity_type,
            data.parent_entity_id,
            data.ministry_id,
            json.dumps(data.workflow_codes) if data.workflow_codes else '[]',
            data.is_active,
            created_by,
        )
        return self._row_to_dict(row)

    # =========================================================================
    # UPDATE OPERATIONS
    # =========================================================================

    async def update_entity(
        self,
        entity_id: UUID,
        data: EntityUpdate,
        updated_by: Optional[UUID] = None
    ) -> Optional[dict]:
        """Update an entity."""
        import json

        updates = []
        params = []
        param_idx = 1

        if data.code is not None:
            updates.append(f"code = ${param_idx}")
            params.append(data.code)
            param_idx += 1

        if data.name is not None:
            updates.append(f"name = ${param_idx}")
            params.append(data.name)
            param_idx += 1

        if data.description is not None:
            updates.append(f"description = ${param_idx}")
            params.append(data.description)
            param_idx += 1

        if data.entity_type is not None:
            updates.append(f"entity_type = ${param_idx}::entity_type_enum")
            params.append(data.entity_type.value if hasattr(data.entity_type, 'value') else data.entity_type)
            param_idx += 1

        if data.parent_entity_id is not None:
            updates.append(f"parent_entity_id = ${param_idx}")
            params.append(data.parent_entity_id)
            param_idx += 1

        if data.ministry_id is not None:
            updates.append(f"ministry_id = ${param_idx}")
            params.append(data.ministry_id)
            param_idx += 1

        if data.workflow_codes is not None:
            updates.append(f"workflow_codes = ${param_idx}::jsonb")
            params.append(json.dumps(data.workflow_codes))
            param_idx += 1

        if data.is_active is not None:
            updates.append(f"is_active = ${param_idx}")
            params.append(data.is_active)
            param_idx += 1

        if not updates:
            return await self.get_entity_by_id(entity_id)

        updates.append(f"updated_by = ${param_idx}")
        params.append(updated_by)
        param_idx += 1

        updates.append("updated_at = NOW()")

        params.append(entity_id)
        query = f"""
            UPDATE entities e
            SET {', '.join(updates)}
            WHERE e.id = ${param_idx}
            RETURNING {self._BASE_FIELDS}
        """
        row = await self.db.fetchrow(query, *params)
        return self._row_to_dict(row) if row else None

    # =========================================================================
    # DELETE OPERATIONS
    # =========================================================================

    async def delete_entity(self, entity_id: UUID) -> bool:
        """Delete an entity."""
        query = "DELETE FROM entities WHERE id = $1"
        result = await self.db.execute(query, entity_id)
        return "DELETE 1" in result

    # =========================================================================
    # COUNT & VALIDATION
    # =========================================================================

    async def count_entities(
        self,
        entity_type: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> int:
        """Count entities."""
        query = "SELECT COUNT(*) FROM entities WHERE 1=1"
        params = []
        param_idx = 1

        if entity_type is not None:
            query += f" AND entity_type = ${param_idx}::entity_type_enum"
            params.append(entity_type)
            param_idx += 1

        if is_active is not None:
            query += f" AND is_active = ${param_idx}"
            params.append(is_active)
            param_idx += 1

        row = await self.db.fetchrow(query, *params)
        return row["count"] if row else 0

    async def validate_workflow_codes(self, workflow_codes: List[str]) -> tuple[bool, List[str]]:
        """
        Validate that all workflow codes exist in the workflows table.

        Returns:
            Tuple of (is_valid, invalid_codes)
        """
        if not workflow_codes:
            return True, []

        placeholders = ', '.join([f'${i+1}' for i in range(len(workflow_codes))])
        query = f"""
            SELECT code FROM workflows
            WHERE code IN ({placeholders}) AND is_active = true
        """
        rows = await self.db.fetch(query, *workflow_codes)
        valid_codes = {row['code'] for row in rows}
        invalid_codes = [code for code in workflow_codes if code not in valid_codes]

        return len(invalid_codes) == 0, invalid_codes

    async def get_departments_by_parent(self, parent_entity_id: UUID) -> List[dict]:
        """Get all departments under a parent entity."""
        query = f"""
            SELECT {self._BASE_FIELDS}
            FROM entities e
            WHERE e.parent_entity_id = $1
            AND e.entity_type = 'department'
            AND e.is_active = true
            ORDER BY e.code ASC
        """
        rows = await self.db.fetch(query, parent_entity_id)
        return [self._row_to_dict(row) for row in rows]

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _row_to_dict(self, row) -> dict:
        """Convert a row to dict with proper workflow_codes handling."""
        import json

        data = dict(row)
        # Handle JSONB workflow_codes
        if 'workflow_codes' in data:
            wc = data['workflow_codes']
            if isinstance(wc, str):
                data['workflow_codes'] = json.loads(wc)
            elif wc is None:
                data['workflow_codes'] = []
            elif isinstance(wc, list):
                data['workflow_codes'] = wc
            else:
                data['workflow_codes'] = list(wc) if wc else []
        return data

    def _row_to_dict_with_details(self, row) -> dict:
        """Convert a row with details to dict."""
        import json

        data = dict(row)
        # Handle JSONB fields
        for field in ['workflow_codes', 'resolved_workflow_codes']:
            if field in data:
                wc = data[field]
                if isinstance(wc, str):
                    data[field] = json.loads(wc)
                elif wc is None:
                    data[field] = []
                elif isinstance(wc, list):
                    data[field] = wc
                else:
                    data[field] = list(wc) if wc else []
        return data
