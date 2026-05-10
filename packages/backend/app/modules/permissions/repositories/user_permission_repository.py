"""
UserPermission Repository - Database operations for user-specific permissions (asyncpg version)
"""
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime
import asyncpg

from app.modules.permissions.models.user_permission import (
    UserPermissionCreate,
    UserPermissionUpdate,
)


def _row_to_dict(record: asyncpg.Record) -> Dict[str, Any]:
    """
    Convert asyncpg Record to dict.

    UUIDs are kept as-is (Pydantic handles the conversion).
    """
    if record is None:
        return None
    return dict(record)


class UserPermissionRepository:
    """Repository for user permission CRUD operations using asyncpg"""

    def __init__(self, db_connection: asyncpg.Connection):
        """
        Initialize repository with database connection

        Args:
            db_connection: asyncpg connection object
        """
        self.db = db_connection

    async def get_by_user_and_permission(
        self,
        user_id: str,
        permission_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get user permission by user ID and permission ID

        Args:
            user_id: User UUID
            permission_id: Permission UUID

        Returns:
            UserPermission dict or None if not found
        """
        result = await self.db.fetchrow("""
            SELECT user_id, permission_id, granted, granted_by, granted_at,
                   expires_at, reason,
                   CASE
                       WHEN expires_at IS NOT NULL AND expires_at < NOW() THEN TRUE
                       ELSE FALSE
                   END as is_expired
            FROM user_permissions
            WHERE user_id = $1 AND permission_id = $2
        """, user_id, permission_id)

        return _row_to_dict(result) if result else None

    async def get_by_user(
        self,
        user_id: str,
        include_expired: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get all permissions for a user

        Args:
            user_id: User UUID
            include_expired: Whether to include expired permissions

        Returns:
            List of user permission dicts
        """
        query = """
            SELECT user_id, permission_id, granted, granted_by, granted_at,
                   expires_at, reason,
                   CASE
                       WHEN expires_at IS NOT NULL AND expires_at < NOW() THEN TRUE
                       ELSE FALSE
                   END as is_expired
            FROM user_permissions
            WHERE user_id = $1
        """

        if not include_expired:
            query += " AND (expires_at IS NULL OR expires_at >= NOW())"

        query += " ORDER BY granted_at DESC"

        results = await self.db.fetch(query, user_id)
        return [_row_to_dict(row) for row in results]

    async def get_by_user_with_details(
        self,
        user_id: str,
        include_expired: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get user permissions with full details (user, permission, granted_by info)

        Args:
            user_id: User UUID
            include_expired: Whether to include expired permissions

        Returns:
            List of detailed user permission dicts
        """
        query = """
            SELECT
                up.user_id,
                u.email as user_email,
                u.full_name as user_full_name,
                up.permission_id,
                p.name as permission_name,
                p.resource as permission_resource,
                p.action as permission_action,
                p.is_critical as permission_is_critical,
                up.granted,
                up.granted_by,
                gb.full_name as granted_by_name,
                up.granted_at,
                up.expires_at,
                up.reason,
                CASE
                    WHEN up.expires_at IS NOT NULL AND up.expires_at < NOW() THEN TRUE
                    ELSE FALSE
                END as is_expired
            FROM user_permissions up
            INNER JOIN users u ON up.user_id = u.id
            INNER JOIN permissions p ON up.permission_id = p.id
            LEFT JOIN users gb ON up.granted_by = gb.id
            WHERE up.user_id = $1
        """

        if not include_expired:
            query += " AND (up.expires_at IS NULL OR up.expires_at >= NOW())"

        query += " ORDER BY up.granted_at DESC"

        results = await self.db.fetch(query, user_id)
        return [_row_to_dict(row) for row in results]

    async def get_expired_permissions(self, limit: int = 500, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Get expired permissions with pagination

        Args:
            limit: Max results (default 500)
            offset: Pagination offset

        Returns:
            List of expired user permission dicts
        """
        results = await self.db.fetch("""
            SELECT user_id, permission_id, granted, granted_by, granted_at,
                   expires_at, reason, TRUE as is_expired
            FROM user_permissions
            WHERE expires_at IS NOT NULL AND expires_at < NOW()
            ORDER BY expires_at DESC
            LIMIT $1 OFFSET $2
        """, limit, offset)

        return [_row_to_dict(row) for row in results]

    async def create(
        self,
        user_permission: UserPermissionCreate
    ) -> Dict[str, Any]:
        """
        Create a new user permission

        Args:
            user_permission: User permission data

        Returns:
            Created user permission dict
        """
        result = await self.db.fetchrow("""
            INSERT INTO user_permissions (
                user_id, permission_id, granted, granted_by, expires_at, reason
            )
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (user_id, permission_id) DO UPDATE
            SET granted = EXCLUDED.granted,
                granted_by = EXCLUDED.granted_by,
                granted_at = NOW(),
                expires_at = EXCLUDED.expires_at,
                reason = EXCLUDED.reason
            RETURNING user_id, permission_id, granted, granted_by, granted_at,
                      expires_at, reason,
                      CASE
                          WHEN expires_at IS NOT NULL AND expires_at < NOW() THEN TRUE
                          ELSE FALSE
                      END as is_expired
        """, str(user_permission.user_id), str(user_permission.permission_id),
            user_permission.granted, str(user_permission.granted_by) if user_permission.granted_by else None,
            user_permission.expires_at, user_permission.reason)

        return _row_to_dict(result)

    async def update(
        self,
        user_id: str,
        permission_id: str,
        user_permission: UserPermissionUpdate
    ) -> Optional[Dict[str, Any]]:
        """
        Update an existing user permission

        Args:
            user_id: User UUID
            permission_id: Permission UUID
            user_permission: Updated permission data

        Returns:
            Updated user permission dict or None if not found
        """
        # Build dynamic update query
        update_fields = []
        params = []
        param_count = 0

        if user_permission.granted is not None:
            param_count += 1
            update_fields.append(f"granted = ${param_count}")
            params.append(user_permission.granted)

        if user_permission.expires_at is not None:
            param_count += 1
            update_fields.append(f"expires_at = ${param_count}")
            params.append(user_permission.expires_at)

        if user_permission.reason is not None:
            param_count += 1
            update_fields.append(f"reason = ${param_count}")
            params.append(user_permission.reason)

        if not update_fields:
            # No fields to update
            return await self.get_by_user_and_permission(user_id, permission_id)

        param_count += 1
        params.append(user_id)
        param_count += 1
        params.append(permission_id)

        query = f"""
            UPDATE user_permissions
            SET {', '.join(update_fields)}
            WHERE user_id = ${param_count - 1} AND permission_id = ${param_count}
            RETURNING user_id, permission_id, granted, granted_by, granted_at,
                      expires_at, reason,
                      CASE
                          WHEN expires_at IS NOT NULL AND expires_at < NOW() THEN TRUE
                          ELSE FALSE
                      END as is_expired
        """

        result = await self.db.fetchrow(query, *params)
        return _row_to_dict(result) if result else None

    async def delete(self, user_id: str, permission_id: str) -> bool:
        """
        Delete a user permission (revoke)

        Args:
            user_id: User UUID
            permission_id: Permission UUID

        Returns:
            True if deleted, False if not found
        """
        result = await self.db.execute("""
            DELETE FROM user_permissions
            WHERE user_id = $1 AND permission_id = $2
        """, user_id, permission_id)

        return "DELETE 1" in result

    async def cleanup_expired(self) -> int:
        """
        Delete all expired permissions

        Returns:
            Number of deleted permissions
        """
        result = await self.db.execute("""
            DELETE FROM user_permissions
            WHERE expires_at IS NOT NULL AND expires_at < NOW()
        """)

        # Parse "DELETE X" to get count
        if "DELETE" in result:
            try:
                return int(result.split()[1])
            except (IndexError, ValueError):
                return 0
        return 0

    async def has_permission(
        self,
        user_id: str,
        permission_name: str
    ) -> bool:
        """
        Check if user has a specific permission (via role or override)

        Args:
            user_id: User UUID
            permission_name: Permission name (e.g., "assignment.view")

        Returns:
            True if user has permission, False otherwise
        """
        # Check user override first (highest priority)
        user_override = await self.db.fetchval("""
            SELECT EXISTS (
                SELECT 1
                FROM user_permissions up
                INNER JOIN permissions p ON up.permission_id = p.id
                WHERE up.user_id = $1
                  AND p.name = $2
                  AND up.granted = TRUE
                  AND (up.expires_at IS NULL OR up.expires_at >= NOW())
            )
        """, user_id, permission_name)

        if user_override:
            return True

        # Check role permissions with hierarchy (recursive CTE)
        role_permission = await self.db.fetchval("""
            WITH RECURSIVE role_chain AS (
                SELECT r.id, r.parent_role_id
                FROM users u
                JOIN roles r ON r.id = u.role_id
                WHERE u.id = $1
                UNION ALL
                SELECT parent.id, parent.parent_role_id
                FROM roles parent
                JOIN role_chain child ON child.parent_role_id = parent.id
            )
            SELECT EXISTS (
                SELECT 1
                FROM role_permissions rp
                JOIN permissions p ON rp.permission_id = p.id
                WHERE rp.role_id IN (SELECT id FROM role_chain)
                  AND p.name = $2
                  AND rp.granted = TRUE
                  AND NOT EXISTS (
                      SELECT 1
                      FROM user_permissions up2
                      JOIN permissions p2 ON up2.permission_id = p2.id
                      WHERE up2.user_id = $1
                        AND p2.name = $2
                        AND up2.granted = FALSE
                  )
            )
        """, user_id, permission_name)

        return role_permission or False

    async def get_user_permissions_summary(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get summary of user's permissions (role + overrides)

        Args:
            user_id: User UUID

        Returns:
            Summary dict with counts and details
        """
        result = await self.db.fetchrow("""
            WITH RECURSIVE role_chain AS (
                SELECT r.id, r.parent_role_id
                FROM users u
                JOIN roles r ON r.id = u.role_id
                WHERE u.id = $1
                UNION ALL
                SELECT parent.id, parent.parent_role_id
                FROM roles parent
                JOIN role_chain child ON child.parent_role_id = parent.id
            ),
            role_perms AS (
                SELECT COUNT(*) as role_count
                FROM role_permissions rp
                WHERE rp.role_id IN (SELECT id FROM role_chain)
                  AND rp.granted = TRUE
            ),
            user_overrides AS (
                SELECT COUNT(*) as override_count
                FROM user_permissions
                WHERE user_id = $1
                  AND (expires_at IS NULL OR expires_at >= NOW())
            ),
            expired_count AS (
                SELECT COUNT(*) as expired
                FROM user_permissions
                WHERE user_id = $1
                  AND expires_at IS NOT NULL
                  AND expires_at < NOW()
            )
            SELECT
                u.id as user_id,
                u.email as user_email,
                r.code as role_code,
                r.name as role_name,
                COALESCE(rp.role_count, 0) as role_permissions_count,
                COALESCE(uo.override_count, 0) as user_overrides_count,
                COALESCE(rp.role_count, 0) + COALESCE(uo.override_count, 0) as total_permissions,
                COALESCE(ec.expired, 0) > 0 as has_expired_permissions
            FROM users u
            LEFT JOIN roles r ON u.role_id = r.id
            LEFT JOIN role_perms rp ON TRUE
            LEFT JOIN user_overrides uo ON TRUE
            LEFT JOIN expired_count ec ON TRUE
            WHERE u.id = $1
        """, user_id)

        return _row_to_dict(result) if result else None

    async def get_all_permission_names(self, user_id: str) -> List[str]:
        """
        Get all permission names for a user (combining role and user-specific permissions).

        This returns the effective set of permissions, accounting for:
        1. Role permissions (from role_permissions via user's role_id)
        2. User-specific granted permissions (user_permissions where granted=true)
        3. User-specific denied permissions are excluded (user_permissions where granted=false)

        Args:
            user_id: User UUID

        Returns:
            List of permission names the user has
        """
        # Optimized CTE query with role hierarchy support
        # Resolves: user role + parent roles (recursive) → permissions - user denies + user grants
        # Performance: <10ms vs 50-200ms (4-way JOIN + UNION)
        results = await self.db.fetch("""
            WITH RECURSIVE role_chain AS MATERIALIZED (
                -- Start with user's direct role
                SELECT r.id, r.parent_role_id
                FROM users u
                JOIN roles r ON r.id = u.role_id
                WHERE u.id = $1

                UNION ALL

                -- Walk up the hierarchy (e.g., admin_agents → admin)
                SELECT parent.id, parent.parent_role_id
                FROM roles parent
                JOIN role_chain child ON child.parent_role_id = parent.id
            ),
            role_perms AS MATERIALIZED (
                -- Collect permissions from all roles in the chain
                SELECT DISTINCT p.name
                FROM role_permissions rp
                JOIN permissions p ON rp.permission_id = p.id
                WHERE rp.role_id IN (SELECT id FROM role_chain)
                  AND rp.granted = TRUE
            ),
            user_denies AS MATERIALIZED (
                SELECT p.name
                FROM user_permissions up
                JOIN permissions p ON up.permission_id = p.id
                WHERE up.user_id = $1
                  AND up.granted = FALSE
                  AND (up.expires_at IS NULL OR up.expires_at >= NOW())
            ),
            user_grants AS MATERIALIZED (
                SELECT p.name
                FROM user_permissions up
                JOIN permissions p ON up.permission_id = p.id
                WHERE up.user_id = $1
                  AND up.granted = TRUE
                  AND (up.expires_at IS NULL OR up.expires_at >= NOW())
            )
            -- Role permissions (including inherited) minus user denies
            SELECT name FROM role_perms
            WHERE name NOT IN (SELECT name FROM user_denies)
            UNION
            -- Plus user-specific grants (UNION deduplicates automatically)
            SELECT name FROM user_grants
        """, user_id)

        return [row['name'] for row in results]

    async def has_permission_scoped(
        self,
        user_id: str,
        permission_name: str,
        entity_code: Optional[str] = None,
    ) -> bool:
        """
        Check if user has a permission, optionally scoped to an entity.

        Scope resolution:
        - scope IS NULL → global permission (matches any entity)
        - scope->>'entity_code' = entity_code → scoped match
        - scope->'entity_codes' @> '["entity_code"]' → multi-entity scoped match

        Args:
            user_id: User UUID
            permission_name: Permission name (e.g., "service_requests.approve")
            entity_code: Optional entity code to check scope against

        Returns:
            True if user has permission (globally or for the given entity)
        """
        # User override first (highest priority)
        user_override = await self.db.fetchval("""
            SELECT EXISTS (
                SELECT 1
                FROM user_permissions up
                JOIN permissions p ON up.permission_id = p.id
                WHERE up.user_id = $1
                  AND p.name = $2
                  AND up.granted = TRUE
                  AND (up.expires_at IS NULL OR up.expires_at >= NOW())
                  AND (
                      up.scope IS NULL
                      OR ($3 IS NULL)
                      OR up.scope->>'entity_code' = $3
                      OR up.scope->'entity_codes' @> to_jsonb($3::text)
                  )
            )
        """, user_id, permission_name, entity_code)

        if user_override:
            return True

        # Check deny
        user_deny = await self.db.fetchval("""
            SELECT EXISTS (
                SELECT 1
                FROM user_permissions up
                JOIN permissions p ON up.permission_id = p.id
                WHERE up.user_id = $1
                  AND p.name = $2
                  AND up.granted = FALSE
                  AND (up.expires_at IS NULL OR up.expires_at >= NOW())
            )
        """, user_id, permission_name)

        if user_deny:
            return False

        # Role permissions with hierarchy + scope
        return await self.db.fetchval("""
            WITH RECURSIVE role_chain AS (
                SELECT r.id, r.parent_role_id
                FROM users u
                JOIN roles r ON r.id = u.role_id
                WHERE u.id = $1
                UNION ALL
                SELECT parent.id, parent.parent_role_id
                FROM roles parent
                JOIN role_chain child ON child.parent_role_id = parent.id
            )
            SELECT EXISTS (
                SELECT 1
                FROM role_permissions rp
                JOIN permissions p ON rp.permission_id = p.id
                WHERE rp.role_id IN (SELECT id FROM role_chain)
                  AND p.name = $2
                  AND rp.granted = TRUE
                  AND (
                      rp.scope IS NULL
                      OR ($3 IS NULL)
                      OR rp.scope->>'entity_code' = $3
                      OR rp.scope->'entity_codes' @> to_jsonb($3::text)
                  )
            )
        """, user_id, permission_name, entity_code) or False
