"""
Base repository pattern for TaxasGE Backend
Generic repository with PostgreSQL support
"""

from abc import ABC, abstractmethod
from typing import TypeVar, Generic, List, Optional, Dict, Any
from uuid import uuid4
import asyncpg
from datetime import datetime, timezone
from loguru import logger

from app.database.connection import db_manager, get_database

T = TypeVar('T')


class BaseRepository(ABC, Generic[T]):
    """Abstract base repository class with PostgreSQL support"""

    def __init__(self, table_name: str):
        self.table_name = table_name
        self.db_manager = db_manager

    @abstractmethod
    def _map_to_model(self, data: Dict[str, Any]) -> T:
        """Map database row to model instance"""
        pass

    @abstractmethod
    def _map_from_model(self, model: T) -> Dict[str, Any]:
        """Map model instance to database row"""
        pass

    async def find_by_id(self, id: str, conn: Optional[asyncpg.Connection] = None) -> Optional[T]:
        """
        Find entity by ID

        Args:
            id: Entity ID
            conn: Optional database connection (if None, uses db_manager)

        Returns:
            Optional[T]: Entity if found, None otherwise
        """
        try:
            query = f"SELECT * FROM {self.table_name} WHERE id = $1"

            if conn:
                result = await conn.fetchrow(query, id)
            else:
                result = await self.db_manager.execute_single(query, id)

            if result:
                return self._map_to_model(dict(result))

        except Exception as e:
            logger.error(f"❌ Error finding {self.table_name} by ID {id}: {e}")

        return None

    async def find_all(
        self,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        conn: Optional[asyncpg.Connection] = None,
        use_supabase: bool = True  # Deprecated: kept for backward compatibility
    ) -> List[T]:
        """
        Find all entities with optional filtering

        Args:
            filters: Dictionary of column=value filters
            order_by: ORDER BY clause (e.g., "created_at DESC")
            limit: Maximum number of results
            offset: Number of results to skip
            conn: Optional database connection (if None, uses db_manager)
            use_supabase: Deprecated parameter, kept for backward compatibility.
                         Always uses PostgreSQL directly.

        Returns:
            List[T]: List of entities
        """
        try:
            # Build PostgreSQL query
            query_parts = [f"SELECT * FROM {self.table_name}"]
            params = []
            param_count = 0

            # Add WHERE conditions
            if filters:
                conditions = []
                for key, value in filters.items():
                    param_count += 1
                    conditions.append(f"{key} = ${param_count}")
                    params.append(value)
                query_parts.append(f"WHERE {' AND '.join(conditions)}")

            # Add ORDER BY (sanitized — only allow column-like patterns)
            if order_by:
                import re
                # Validate: only alphanumeric, underscores, dots, spaces, ASC/DESC
                if re.match(r'^[a-zA-Z_][a-zA-Z0-9_.\s,]*(?: (?:ASC|DESC))?$', order_by.strip(), re.IGNORECASE):
                    query_parts.append(f"ORDER BY {order_by}")
                else:
                    query_parts.append("ORDER BY created_at DESC")

            # Add LIMIT and OFFSET
            if limit:
                param_count += 1
                query_parts.append(f"LIMIT ${param_count}")
                params.append(limit)

            if offset:
                param_count += 1
                query_parts.append(f"OFFSET ${param_count}")
                params.append(offset)

            query = " ".join(query_parts)

            if conn:
                results = await conn.fetch(query, *params)
            else:
                results = await self.db_manager.execute_query(query, *params)

            return [self._map_to_model(dict(row)) for row in results]

        except Exception as e:
            logger.error(f"❌ Error finding all {self.table_name}: {e}")
            return []

    async def create(self, model: T, conn: Optional[asyncpg.Connection] = None) -> Optional[T]:
        """
        Create new entity

        Args:
            model: Entity model to create
            conn: Optional database connection (if None, uses db_manager)

        Returns:
            Optional[T]: Created entity if successful, None otherwise
        """
        try:
            data = self._map_from_model(model)

            # Add ID if not present
            if "id" not in data or not data["id"]:
                data["id"] = str(uuid4())

            # Add timestamps
            now = datetime.now(timezone.utc)
            data["created_at"] = now
            data["updated_at"] = now

            # Build INSERT query
            columns = list(data.keys())
            placeholders = [f"${i+1}" for i in range(len(columns))]
            values = list(data.values())

            query = f"""
                INSERT INTO {self.table_name} ({', '.join(columns)})
                VALUES ({', '.join(placeholders)})
                RETURNING *
            """

            if conn:
                result = await conn.fetchrow(query, *values)
            else:
                result = await self.db_manager.execute_single(query, *values)

            if result:
                return self._map_to_model(dict(result))

        except Exception as e:
            logger.error(f"❌ Error creating {self.table_name}: {e}")

        return None

    async def update(
        self,
        id: str,
        updates: Dict[str, Any],
        conn: Optional[asyncpg.Connection] = None,
        use_supabase: bool = True  # Deprecated: kept for backward compatibility
    ) -> Optional[T]:
        """
        Update entity by ID

        Args:
            id: Entity ID
            updates: Dictionary of column=value updates
            conn: Optional database connection (if None, uses db_manager)
            use_supabase: Deprecated parameter, kept for backward compatibility.
                         Always uses PostgreSQL directly.

        Returns:
            Optional[T]: Updated entity if successful, None otherwise
        """
        try:
            # Add updated timestamp
            updates["updated_at"] = datetime.now(timezone.utc)

            # Build UPDATE query
            set_clauses = []
            params = []
            param_count = 0

            for key, value in updates.items():
                param_count += 1
                set_clauses.append(f"{key} = ${param_count}")
                params.append(value)

            param_count += 1
            params.append(id)

            query = f"""
                UPDATE {self.table_name}
                SET {', '.join(set_clauses)}
                WHERE id = ${param_count}
                RETURNING *
            """

            if conn:
                result = await conn.fetchrow(query, *params)
            else:
                result = await self.db_manager.execute_single(query, *params)

            if result:
                return self._map_to_model(dict(result))

        except Exception as e:
            logger.error(f"❌ Error updating {self.table_name} {id}: {e}")

        return None

    async def delete(self, id: str, conn: Optional[asyncpg.Connection] = None) -> bool:
        """
        Delete entity by ID

        Args:
            id: Entity ID
            conn: Optional database connection (if None, uses db_manager)

        Returns:
            bool: True if deleted successfully, False otherwise
        """
        try:
            query = f"DELETE FROM {self.table_name} WHERE id = $1"

            if conn:
                result = await conn.execute(query, id)
            else:
                result = await self.db_manager.execute_command(query, id)

            return "DELETE 1" in result

        except Exception as e:
            logger.error(f"❌ Error deleting {self.table_name} {id}: {e}")
            return False

    async def count(
        self,
        filters: Optional[Dict[str, Any]] = None,
        conn: Optional[asyncpg.Connection] = None,
        use_supabase: bool = True  # Deprecated: kept for backward compatibility
    ) -> int:
        """
        Count entities with optional filtering

        Args:
            filters: Dictionary of column=value filters
            conn: Optional database connection (if None, uses db_manager)
            use_supabase: Deprecated parameter, kept for backward compatibility.
                         Always uses PostgreSQL directly.

        Returns:
            int: Number of entities matching filters
        """
        try:
            # Build COUNT query
            query_parts = [f"SELECT COUNT(*) FROM {self.table_name}"]
            params = []
            param_count = 0

            if filters:
                conditions = []
                for key, value in filters.items():
                    param_count += 1
                    conditions.append(f"{key} = ${param_count}")
                    params.append(value)
                query_parts.append(f"WHERE {' AND '.join(conditions)}")

            query = " ".join(query_parts)

            if conn:
                result = await conn.fetchval(query, *params)
            else:
                result = await self.db_manager.execute_scalar(query, *params)

            return result or 0

        except Exception as e:
            logger.error(f"❌ Error counting {self.table_name}: {e}")
            return 0

    async def search(
        self,
        search_query: str,
        search_columns: List[str],
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 20,
        conn: Optional[asyncpg.Connection] = None
    ) -> List[T]:
        """
        Full-text search in specified columns using ILIKE

        Args:
            search_query: Search term
            search_columns: Columns to search in
            filters: Additional filters
            limit: Maximum results
            conn: Optional database connection (if None, uses db_manager)

        Returns:
            List[T]: List of matching entities
        """
        try:
            # PostgreSQL ILIKE search
            search_conditions = []
            params = [f"%{search_query}%"] * len(search_columns)
            param_count = 0

            for column in search_columns:
                param_count += 1
                search_conditions.append(f"{column} ILIKE ${param_count}")

            query_parts = [
                f"SELECT * FROM {self.table_name}",
                f"WHERE ({' OR '.join(search_conditions)})"
            ]

            # Add additional filters
            if filters:
                for key, value in filters.items():
                    param_count += 1
                    query_parts.append(f"AND {key} = ${param_count}")
                    params.append(value)

            query_parts.append(f"LIMIT {limit}")
            query = " ".join(query_parts)

            if conn:
                results = await conn.fetch(query, *params)
            else:
                results = await self.db_manager.execute_query(query, *params)

            return [self._map_to_model(dict(row)) for row in results]

        except Exception as e:
            logger.error(f"❌ Error searching {self.table_name}: {e}")
            return []

    async def exists(self, id: str, conn: Optional[asyncpg.Connection] = None) -> bool:
        """
        Check if entity exists by ID

        Args:
            id: Entity ID
            conn: Optional database connection (if None, uses db_manager)

        Returns:
            bool: True if entity exists, False otherwise
        """
        try:
            entity = await self.find_by_id(id, conn)
            return entity is not None
        except Exception as e:
            logger.error(f"❌ Error checking existence of {self.table_name} {id}: {e}")
            return False

    async def bulk_create(self, models: List[T], conn: Optional[asyncpg.Connection] = None) -> List[T]:
        """
        Create multiple entities

        Args:
            models: List of entities to create
            conn: Optional database connection (if None, uses db_manager)

        Returns:
            List[T]: List of created entities
        """
        created_models = []
        for model in models:
            created = await self.create(model, conn)
            if created:
                created_models.append(created)
        return created_models

    async def bulk_update(
        self,
        updates_list: List[Dict[str, Any]],
        conn: Optional[asyncpg.Connection] = None
    ) -> List[T]:
        """
        Update multiple entities

        Args:
            updates_list: List of update dictionaries with 'id' key
            conn: Optional database connection (if None, uses db_manager)

        Returns:
            List[T]: List of updated entities
        """
        updated_models = []
        for update_data in updates_list:
            if "id" not in update_data:
                continue
            entity_id = update_data.pop("id")
            updated = await self.update(entity_id, update_data, conn)
            if updated:
                updated_models.append(updated)
        return updated_models