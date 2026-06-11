"""
USSD Configuration Repository

Data access layer for USSD configurations
Handles all database operations for ussd_configurations table
"""

from typing import Optional, List, Dict, Any
import asyncpg
from loguru import logger
import json

from ..models.ussd import (
    UssdConfigCreate,
    UssdConfigUpdate,
    UssdConfigResponse,
    UssdOperator,
    MenuNode
)


class UssdRepository:
    """Repository for USSD configuration data access"""

    async def create(
        self,
        db: asyncpg.Connection,
        config_data: UssdConfigCreate,
        user_id: int
    ) -> UssdConfigResponse:
        """
        Create a new USSD configuration

        Args:
            db: Database connection
            config_data: USSD configuration data
            user_id: ID of user creating the configuration

        Returns:
            Created USSD configuration

        Raises:
            asyncpg.UniqueViolationError: If short_code or operator_code already exists
        """
        # Convert menu_structure to JSON
        menu_json = json.dumps([menu.model_dump() for menu in config_data.menu_structure])
        auth_json = json.dumps(config_data.auth_config)

        query = """
            INSERT INTO ussd_configurations (
                operator_name,
                operator_code,
                short_code,
                api_endpoint,
                auth_config,
                menu_structure,
                session_timeout_seconds,
                max_input_length,
                is_active,
                created_by
            )
            VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb, $7, $8, $9, $10)
            RETURNING id, operator_name, operator_code, short_code, api_endpoint,
                      auth_config, menu_structure, session_timeout_seconds,
                      max_input_length, is_active, created_at, updated_at, created_by
        """

        try:
            row = await db.fetchrow(
                query,
                config_data.operator_name.value,
                config_data.operator_code,
                config_data.short_code,
                config_data.api_endpoint,
                auth_json,
                menu_json,
                config_data.session_timeout_seconds,
                config_data.max_input_length,
                config_data.is_active,
                user_id
            )

            logger.info(f"Created USSD configuration for operator {config_data.operator_name}")
            return self._row_to_response(row)

        except asyncpg.UniqueViolationError as e:
            logger.error(f"Duplicate USSD configuration: {e}")
            raise

    async def find_by_id(
        self,
        db: asyncpg.Connection,
        config_id: int
    ) -> Optional[UssdConfigResponse]:
        """
        Find USSD configuration by ID

        Args:
            db: Database connection
            config_id: Configuration ID

        Returns:
            USSD configuration or None if not found
        """
        query = """
            SELECT id, operator_name, operator_code, short_code, api_endpoint,
                   auth_config, menu_structure, session_timeout_seconds,
                   max_input_length, is_active, created_at, updated_at, created_by
            FROM ussd_configurations
            WHERE id = $1
        """

        row = await db.fetchrow(query, config_id)
        return self._row_to_response(row) if row else None

    async def find_by_operator(
        self,
        db: asyncpg.Connection,
        operator_name: UssdOperator
    ) -> Optional[UssdConfigResponse]:
        """
        Find USSD configuration by operator name

        Args:
            db: Database connection
            operator_name: Operator name

        Returns:
            USSD configuration or None if not found
        """
        query = """
            SELECT id, operator_name, operator_code, short_code, api_endpoint,
                   auth_config, menu_structure, session_timeout_seconds,
                   max_input_length, is_active, created_at, updated_at, created_by
            FROM ussd_configurations
            WHERE operator_name = $1
            ORDER BY created_at DESC
            LIMIT 1
        """

        row = await db.fetchrow(query, operator_name.value)
        return self._row_to_response(row) if row else None

    async def find_by_short_code(
        self,
        db: asyncpg.Connection,
        short_code: str
    ) -> Optional[UssdConfigResponse]:
        """
        Find USSD configuration by short code

        Args:
            db: Database connection
            short_code: USSD short code (e.g., *123#)

        Returns:
            USSD configuration or None if not found
        """
        query = """
            SELECT id, operator_name, operator_code, short_code, api_endpoint,
                   auth_config, menu_structure, session_timeout_seconds,
                   max_input_length, is_active, created_at, updated_at, created_by
            FROM ussd_configurations
            WHERE short_code = $1
        """

        row = await db.fetchrow(query, short_code)
        return self._row_to_response(row) if row else None

    async def find_all(
        self,
        db: asyncpg.Connection,
        limit: int = 100,
        offset: int = 0,
        is_active: Optional[bool] = None
    ) -> List[UssdConfigResponse]:
        """
        List all USSD configurations with pagination

        Args:
            db: Database connection
            limit: Maximum number of results
            offset: Number of results to skip
            is_active: Filter by active status (optional)

        Returns:
            List of USSD configurations
        """
        if is_active is not None:
            query = """
                SELECT id, operator_name, operator_code, short_code, api_endpoint,
                       auth_config, menu_structure, session_timeout_seconds,
                       max_input_length, is_active, created_at, updated_at, created_by
                FROM ussd_configurations
                WHERE is_active = $1
                ORDER BY created_at DESC
                LIMIT $2 OFFSET $3
            """
            rows = await db.fetch(query, is_active, limit, offset)
        else:
            query = """
                SELECT id, operator_name, operator_code, short_code, api_endpoint,
                       auth_config, menu_structure, session_timeout_seconds,
                       max_input_length, is_active, created_at, updated_at, created_by
                FROM ussd_configurations
                ORDER BY created_at DESC
                LIMIT $1 OFFSET $2
            """
            rows = await db.fetch(query, limit, offset)

        return [self._row_to_response(row) for row in rows]

    async def count(
        self,
        db: asyncpg.Connection,
        is_active: Optional[bool] = None
    ) -> int:
        """
        Count total USSD configurations

        Args:
            db: Database connection
            is_active: Filter by active status (optional)

        Returns:
            Total count
        """
        if is_active is not None:
            query = "SELECT COUNT(*) FROM ussd_configurations WHERE is_active = $1"
            return await db.fetchval(query, is_active)
        else:
            query = "SELECT COUNT(*) FROM ussd_configurations"
            return await db.fetchval(query)

    async def update(
        self,
        db: asyncpg.Connection,
        config_id: int,
        config_data: UssdConfigUpdate
    ) -> Optional[UssdConfigResponse]:
        """
        Update USSD configuration

        Args:
            db: Database connection
            config_id: Configuration ID
            config_data: Updated configuration data

        Returns:
            Updated configuration or None if not found
        """
        # Build dynamic update query
        update_fields = []
        params = []
        param_count = 1

        if config_data.operator_name is not None:
            update_fields.append(f"operator_name = ${param_count}")
            params.append(config_data.operator_name.value)
            param_count += 1

        if config_data.operator_code is not None:
            update_fields.append(f"operator_code = ${param_count}")
            params.append(config_data.operator_code)
            param_count += 1

        if config_data.short_code is not None:
            update_fields.append(f"short_code = ${param_count}")
            params.append(config_data.short_code)
            param_count += 1

        if config_data.api_endpoint is not None:
            update_fields.append(f"api_endpoint = ${param_count}")
            params.append(config_data.api_endpoint)
            param_count += 1

        if config_data.auth_config is not None:
            update_fields.append(f"auth_config = ${param_count}::jsonb")
            params.append(json.dumps(config_data.auth_config))
            param_count += 1

        if config_data.menu_structure is not None:
            update_fields.append(f"menu_structure = ${param_count}::jsonb")
            params.append(json.dumps([menu.model_dump() for menu in config_data.menu_structure]))
            param_count += 1

        if config_data.session_timeout_seconds is not None:
            update_fields.append(f"session_timeout_seconds = ${param_count}")
            params.append(config_data.session_timeout_seconds)
            param_count += 1

        if config_data.max_input_length is not None:
            update_fields.append(f"max_input_length = ${param_count}")
            params.append(config_data.max_input_length)
            param_count += 1

        if config_data.is_active is not None:
            update_fields.append(f"is_active = ${param_count}")
            params.append(config_data.is_active)
            param_count += 1

        if not update_fields:
            # No fields to update, return existing config
            return await self.find_by_id(db, config_id)

        # Always update updated_at
        update_fields.append("updated_at = CURRENT_TIMESTAMP")

        params.append(config_id)

        query = f"""
            UPDATE ussd_configurations
            SET {', '.join(update_fields)}
            WHERE id = ${param_count}
            RETURNING id, operator_name, operator_code, short_code, api_endpoint,
                      auth_config, menu_structure, session_timeout_seconds,
                      max_input_length, is_active, created_at, updated_at, created_by
        """

        try:
            row = await db.fetchrow(query, *params)
            if row:
                logger.info(f"Updated USSD configuration {config_id}")
                return self._row_to_response(row)
            return None

        except asyncpg.UniqueViolationError as e:
            logger.error(f"Duplicate values in USSD configuration update: {e}")
            raise

    async def delete(
        self,
        db: asyncpg.Connection,
        config_id: int
    ) -> bool:
        """
        Delete USSD configuration

        Args:
            db: Database connection
            config_id: Configuration ID

        Returns:
            True if deleted, False if not found
        """
        query = "DELETE FROM ussd_configurations WHERE id = $1"
        result = await db.execute(query, config_id)

        deleted = result.split()[-1] == "1"
        if deleted:
            logger.info(f"Deleted USSD configuration {config_id}")

        return deleted

    def _row_to_response(self, row: asyncpg.Record) -> UssdConfigResponse:
        """
        Convert database row to UssdConfigResponse

        Args:
            row: Database row

        Returns:
            UssdConfigResponse object
        """
        # Parse JSONB fields - handle both string and dict/list formats
        menu_structure_raw = row['menu_structure']

        # Handle string representation of JSONB
        if isinstance(menu_structure_raw, str):
            try:
                menu_structure_raw = json.loads(menu_structure_raw)
            except json.JSONDecodeError:
                logger.error(f"Failed to parse menu_structure JSON: {menu_structure_raw[:100]}")
                menu_structure_raw = []

        # Parse each menu node - handle nested string encoding
        menu_structure = []
        for menu in (menu_structure_raw or []):
            if isinstance(menu, str):
                try:
                    menu = json.loads(menu)
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse menu node: {menu[:50]}")
                    continue
            if isinstance(menu, dict):
                # Also parse options if they're strings
                if 'options' in menu and isinstance(menu['options'], str):
                    try:
                        menu['options'] = json.loads(menu['options'])
                    except json.JSONDecodeError:
                        menu['options'] = []
                menu_structure.append(MenuNode(**menu))

        auth_config_raw = row['auth_config']
        if isinstance(auth_config_raw, str):
            try:
                auth_config = json.loads(auth_config_raw)
            except json.JSONDecodeError:
                auth_config = {}
        else:
            auth_config = auth_config_raw or {}

        return UssdConfigResponse(
            id=row['id'],
            operator_name=UssdOperator(row['operator_name']),
            operator_code=row['operator_code'],
            short_code=row['short_code'],
            api_endpoint=row['api_endpoint'],
            auth_config=auth_config,
            menu_structure=menu_structure,
            session_timeout_seconds=row['session_timeout_seconds'],
            max_input_length=row['max_input_length'],
            is_active=row['is_active'],
            created_at=row['created_at'],
            updated_at=row['updated_at'],
            created_by=row['created_by']
        )
