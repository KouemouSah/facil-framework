"""
Permission Repository - Database operations for permissions (asyncpg version)
"""
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime
import asyncpg

from app.modules.permissions.models.permission import (
    PermissionCreate,
    PermissionUpdate,
    PermissionResponse,
)


def _row_to_dict(record: asyncpg.Record) -> Dict[str, Any]:
    """
    Convert asyncpg Record to dict.

    UUIDs are kept as-is (Pydantic handles the conversion).
    """
    if record is None:
        return None
    return dict(record)


class PermissionRepository:
    """Repository for permission CRUD operations using asyncpg"""

    def __init__(self, db_connection: asyncpg.Connection):
        """
        Initialize repository with database connection

        Args:
            db_connection: asyncpg connection object
        """
        self.db = db_connection

    async def get_by_id(self, permission_id: str) -> Optional[Dict[str, Any]]:
        """
        Get permission by ID

        Args:
            permission_id: Permission UUID

        Returns:
            Permission dict or None if not found
        """
        result = await self.db.fetchrow("""
            SELECT id, name, resource, action, description, is_critical,
                   module_name, created_at, updated_at
            FROM permissions
            WHERE id = $1
        """, permission_id)

        return _row_to_dict(result) if result else None

    async def get_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get permission by unique name

        Args:
            name: Permission name (e.g., "assignment.reassign_in_progress")

        Returns:
            Permission dict or None if not found
        """
        result = await self.db.fetchrow("""
            SELECT id, name, resource, action, description, is_critical,
                   module_name, created_at, updated_at
            FROM permissions
            WHERE name = $1
        """, name)

        return _row_to_dict(result) if result else None

    async def get_all(
        self,
        module_name: Optional[str] = None,
        resource: Optional[str] = None,
        is_critical: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get all permissions with optional filters

        Args:
            module_name: Filter by module name
            resource: Filter by resource
            is_critical: Filter by critical flag
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of permission dicts
        """
        query = """
            SELECT id, name, resource, action, description, is_critical,
                   module_name, created_at, updated_at
            FROM permissions
            WHERE 1=1
        """
        params = []
        param_count = 0

        if module_name is not None:
            param_count += 1
            query += f" AND module_name = ${param_count}"
            params.append(module_name)

        if resource is not None:
            param_count += 1
            query += f" AND resource = ${param_count}"
            params.append(resource)

        if is_critical is not None:
            param_count += 1
            query += f" AND is_critical = ${param_count}"
            params.append(is_critical)

        query += f" ORDER BY module_name, resource, action LIMIT ${param_count + 1} OFFSET ${param_count + 2}"
        params.extend([limit, offset])

        results = await self.db.fetch(query, *params)
        return [_row_to_dict(row) for row in results]

    async def count(
        self,
        module_name: Optional[str] = None,
        resource: Optional[str] = None,
        is_critical: Optional[bool] = None
    ) -> int:
        """
        Count permissions with optional filters

        Args:
            module_name: Filter by module name
            resource: Filter by resource
            is_critical: Filter by critical flag

        Returns:
            Total count
        """
        query = "SELECT COUNT(*) FROM permissions WHERE 1=1"
        params = []
        param_count = 0

        if module_name is not None:
            param_count += 1
            query += f" AND module_name = ${param_count}"
            params.append(module_name)

        if resource is not None:
            param_count += 1
            query += f" AND resource = ${param_count}"
            params.append(resource)

        if is_critical is not None:
            param_count += 1
            query += f" AND is_critical = ${param_count}"
            params.append(is_critical)

        result = await self.db.fetchval(query, *params)
        return result or 0

    async def get_by_module(self, module_name: str) -> List[Dict[str, Any]]:
        """
        Get all permissions for a specific module

        Args:
            module_name: Module name

        Returns:
            List of permission dicts
        """
        return await self.get_all(module_name=module_name, limit=1000)

    async def get_grouped_by_module(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get all permissions grouped by module

        Returns:
            Dict with module names as keys and permission lists as values
        """
        results = await self.db.fetch("""
            SELECT id, name, resource, action, description, is_critical,
                   module_name, created_at, updated_at
            FROM permissions
            ORDER BY module_name, resource, action
        """)

        grouped = {}
        for row in results:
            module = row['module_name'] or 'unknown'
            if module not in grouped:
                grouped[module] = []
            grouped[module].append(_row_to_dict(row))

        return grouped

    async def create(self, permission: PermissionCreate) -> Dict[str, Any]:
        """
        Create a new permission

        Args:
            permission: Permission data

        Returns:
            Created permission dict

        Raises:
            asyncpg.UniqueViolationError: If permission name already exists
        """
        result = await self.db.fetchrow("""
            INSERT INTO permissions (name, resource, action, description, is_critical, module_name)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id, name, resource, action, description, is_critical,
                      module_name, created_at, updated_at
        """, permission.name, permission.resource, permission.action,
            permission.description, permission.is_critical, permission.module_name)

        return _row_to_dict(result)

    async def bulk_create(self, permissions: List[PermissionCreate]) -> List[Dict[str, Any]]:
        """
        Create multiple permissions at once

        Args:
            permissions: List of permission data

        Returns:
            List of created permission dicts
        """
        created_permissions = []

        for permission in permissions:
            result = await self.db.fetchrow("""
                INSERT INTO permissions (name, resource, action, description, is_critical, module_name)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (name) DO NOTHING
                RETURNING id, name, resource, action, description, is_critical,
                          module_name, created_at, updated_at
            """, permission.name, permission.resource, permission.action,
                permission.description, permission.is_critical, permission.module_name)

            if result:
                created_permissions.append(_row_to_dict(result))

        return created_permissions

    async def update(self, permission_id: str, permission: PermissionUpdate) -> Optional[Dict[str, Any]]:
        """
        Update an existing permission

        Args:
            permission_id: Permission UUID
            permission: Updated permission data

        Returns:
            Updated permission dict or None if not found
        """
        # Build dynamic update query
        update_fields = []
        params = []
        param_count = 0

        if permission.description is not None:
            param_count += 1
            update_fields.append(f"description = ${param_count}")
            params.append(permission.description)

        if permission.is_critical is not None:
            param_count += 1
            update_fields.append(f"is_critical = ${param_count}")
            params.append(permission.is_critical)

        if permission.module_name is not None:
            param_count += 1
            update_fields.append(f"module_name = ${param_count}")
            params.append(permission.module_name)

        if not update_fields:
            # No fields to update
            return await self.get_by_id(permission_id)

        update_fields.append("updated_at = NOW()")
        param_count += 1
        params.append(permission_id)

        query = f"""
            UPDATE permissions
            SET {', '.join(update_fields)}
            WHERE id = ${param_count}
            RETURNING id, name, resource, action, description, is_critical,
                      module_name, created_at, updated_at
        """

        result = await self.db.fetchrow(query, *params)
        return _row_to_dict(result) if result else None

    async def delete(self, permission_id: str) -> bool:
        """
        Delete a permission

        Args:
            permission_id: Permission UUID

        Returns:
            True if deleted, False if not found
        """
        result = await self.db.execute("""
            DELETE FROM permissions
            WHERE id = $1
        """, permission_id)

        return "DELETE 1" in result

    async def exists(self, name: str) -> bool:
        """
        Check if a permission exists by name

        Args:
            name: Permission name

        Returns:
            True if exists, False otherwise
        """
        result = await self.db.fetchval("""
            SELECT EXISTS(SELECT 1 FROM permissions WHERE name = $1)
        """, name)

        return result or False

    async def get_critical_permissions(self) -> List[Dict[str, Any]]:
        """
        Get all critical permissions

        Returns:
            List of critical permission dicts
        """
        return await self.get_all(is_critical=True, limit=1000)

    # ========================================================================
    # METHODS USING DATABASE VIEWS - Optimized queries with pre-joined data
    # ========================================================================

    async def get_user_effective_permissions(
        self,
        user_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get user's effective permissions using v_user_effective_permissions view

        This view includes:
        - User info (email, name, role)
        - Explicit permissions granted
        - All accessible modules
        - Role capability level
        - Admin flag

        Args:
            user_id: User UUID

        Returns:
            Complete user permissions data or None
        """
        result = await self.db.fetchrow("""
            SELECT * FROM v_user_effective_permissions
            WHERE user_id = $1
        """, user_id)
        return _row_to_dict(result) if result else None

    async def list_users_effective_permissions(
        self,
        role: Optional[str] = None,
        is_admin: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[List[Dict[str, Any]], int]:
        """
        List users with their effective permissions

        Args:
            role: Optional filter by role
            is_admin: Optional filter admins
            limit: Max results
            offset: Pagination offset

        Returns:
            Tuple of (users list, total count)
        """
        where_conditions = []
        params = []

        if role:
            where_conditions.append(f"role = ${len(params) + 1}")
            params.append(role)

        if is_admin is not None:
            where_conditions.append(f"is_admin = ${len(params) + 1}")
            params.append(is_admin)

        where_clause = f"WHERE {' AND '.join(where_conditions)}" if where_conditions else ""

        # Count query
        count_query = f"""
            SELECT COUNT(*) FROM v_user_effective_permissions
            {where_clause}
        """
        total = await self.db.fetchval(count_query, *params)

        # Data query
        params.extend([limit, offset])
        data_query = f"""
            SELECT * FROM v_user_effective_permissions
            {where_clause}
            ORDER BY role, email
            LIMIT ${len(params) - 1} OFFSET ${len(params)}
        """

        results = await self.db.fetch(data_query, *params)
        users = [_row_to_dict(r) for r in results]

        return users, total

    async def get_permission_usage_analytics(
        self,
        permission_id: Optional[str] = None,
        module: Optional[str] = None,
        usage_category: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get permission usage analytics using v_permission_usage_analytics view

        This view includes:
        - Grant statistics by permission
        - User distribution by role
        - Usage categories (UNUSED, RARELY_USED, etc.)
        - Recommendations for permission lifecycle

        Args:
            permission_id: Optional filter by permission
            module: Optional filter by module
            usage_category: Optional filter (UNUSED, RARELY_USED, MODERATELY_USED, WIDELY_USED)
            limit: Max results

        Returns:
            List of permission analytics
        """
        where_conditions = []
        params = []

        if permission_id:
            where_conditions.append(f"permission_id = ${len(params) + 1}")
            params.append(permission_id)

        if module:
            where_conditions.append(f"module = ${len(params) + 1}")
            params.append(module)

        if usage_category:
            where_conditions.append(f"usage_category = ${len(params) + 1}")
            params.append(usage_category)

        where_clause = f"WHERE {' AND '.join(where_conditions)}" if where_conditions else ""

        params.append(limit)
        query = f"""
            SELECT * FROM v_permission_usage_analytics
            {where_clause}
            ORDER BY users_with_permission DESC
            LIMIT ${len(params)}
        """

        results = await self.db.fetch(query, *params)
        return [_row_to_dict(r) for r in results]

    async def detect_overprivileged_users(
        self,
        min_risk_score: int = 20,
        risk_level: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Detect overprivileged users using v_overprivileged_users_detection view

        This view includes:
        - Risk score calculation
        - Permission counts by type
        - Risk levels (LOW, MEDIUM, HIGH, CRITICAL)
        - Recommendations for remediation

        Args:
            min_risk_score: Minimum risk score threshold
            risk_level: Optional filter (LOW, MEDIUM, HIGH, CRITICAL)
            limit: Max results

        Returns:
            List of potentially overprivileged users
        """
        where_conditions = [f"risk_score >= ${1}"]
        params = [min_risk_score]

        if risk_level:
            where_conditions.append(f"risk_level = ${len(params) + 1}")
            params.append(risk_level)

        where_clause = f"WHERE {' AND '.join(where_conditions)}"

        params.append(limit)
        query = f"""
            SELECT * FROM v_overprivileged_users_detection
            {where_clause}
            ORDER BY risk_score DESC
            LIMIT ${len(params)}
        """

        results = await self.db.fetch(query, *params)
        return [_row_to_dict(r) for r in results]
