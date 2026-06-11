"""
Permission Service - Business logic for permission checking and management

Includes Redis cache integration for frequently accessed permission data.
"""
from typing import List, Optional, Dict, Any, Set
from fastapi import HTTPException, status, Depends
from loguru import logger

from app.database.connection import get_database
from app.modules.permissions.repositories.permission_repository import PermissionRepository
from app.modules.permissions.repositories.role_repository import RoleRepository
from app.modules.permissions.repositories.user_permission_repository import UserPermissionRepository
from app.modules.permissions.models.permission import (
    PermissionCreate,
    PermissionUpdate,
    PermissionResponse,
)
from app.repositories.user_repository import UserRepository
from app.core.cache import (
    get_permissions_cache,
    CacheKeys,
    invalidate_user_permissions_cache,
    invalidate_all_permissions_cache,
)


class PermissionService:
    """Service for permission operations"""

    def __init__(
        self,
        permission_repo: PermissionRepository,
        role_repo: RoleRepository,
        user_permission_repo: UserPermissionRepository
    ):
        """
        Initialize service with repositories

        Args:
            permission_repo: Permission repository
            role_repo: Role repository
            user_permission_repo: User permission repository
        """
        self.permission_repo = permission_repo
        self.role_repo = role_repo
        self.user_permission_repo = user_permission_repo
        self.user_repo = UserRepository()

    async def get_cached_user_permissions(self, user_id: str) -> Set[str]:
        """
        Get user's permission names with caching.

        Uses Redis cache (10 min TTL) to avoid repeated database queries.

        Args:
            user_id: User UUID

        Returns:
            Set of permission names
        """
        cache = get_permissions_cache()
        cache_key = CacheKeys.user_permissions(user_id)

        # Try cache first
        cached = await cache.get(cache_key)
        if cached is not None:
            logger.debug(f"Permission cache HIT for user {user_id}")
            return set(cached)

        # Cache miss - fetch from database
        logger.debug(f"Permission cache MISS for user {user_id}")
        permission_names = await self.user_permission_repo.get_all_permission_names(user_id)

        # Store in cache
        await cache.set(cache_key, permission_names, ttl=600)  # 10 minutes

        return set(permission_names)

    async def has_permission(
        self,
        user_id: str,
        permission_name: str,
        user: Optional[Any] = None
    ) -> bool:
        """
        Check if a user has a specific permission

        This checks:
        1. **ADMIN AUTO-APPROVAL**: If user is admin, automatically return True
        2. **SUPERVISOR AUTO-APPROVAL**: If user is supervisor (agent_profiles.is_supervisor=true),
           automatically grant permissions for their entity scope
        3. User-specific permission overrides (highest priority)
        4. Role-based permissions (if no override)

        Uses Redis cache for permission lookups (10 min TTL).

        Args:
            user_id: User UUID
            permission_name: Permission name (e.g., "assignment.reassign_in_progress")
            user: Optional pre-fetched UserResponse (avoids redundant DB query)

        Returns:
            True if user has permission, False otherwise
        """
        # CRITICAL: Admins have ALL permissions automatically
        try:
            # Reuse pre-fetched user from middleware — eliminates redundant DB query
            if user is None:
                user = await self.user_repo.find_by_id(user_id)
            if user:
                # Check role - handle both UserRole enum and string values
                user_role = user.role.value if hasattr(user.role, 'value') else str(user.role)
                if user_role == "admin":
                    logger.debug(f"Admin user {user_id} auto-granted permission: {permission_name}")
                    return True

                # Check if user is a supervisor (agent_profiles.is_supervisor = true)
                # Supervisors get all permissions within their entity scope
                if user_role == "agent":
                    is_supervisor = await self._check_is_supervisor(user_id, permission_name)
                    if is_supervisor:
                        logger.debug(f"Supervisor {user_id} auto-granted permission: {permission_name}")
                        return True

        except Exception as e:
            logger.warning(f"Could not check admin/supervisor status for user {user_id}: {e}")

        # For non-admins and non-supervisors, check cached permissions
        try:
            user_permissions = await self.get_cached_user_permissions(user_id)
            return permission_name in user_permissions
        except Exception as e:
            logger.warning(f"Cache lookup failed, falling back to direct query: {e}")
            return await self.user_permission_repo.has_permission(user_id, permission_name)

    async def _check_is_supervisor(self, user_id: str, permission_name: str) -> bool:
        """
        Check if user is a supervisor and the permission is within their scope.

        Supervisors (agent_profiles.is_supervisor = true) automatically get:
        1. Generic supervisory permissions (agent, assignment, dashboard, etc.)
        2. Permissions matching their entity's workflow permission modules
        3. Permissions granted via their role (checked via normal flow)

        This is fully dynamic - no hardcoded entity codes.

        Args:
            user_id: User UUID
            permission_name: Permission name to check

        Returns:
            True if user is supervisor with access to this permission scope
        """
        try:
            # Query agent_profiles to check is_supervisor and get entity's permission modules
            query = """
                SELECT
                    ap.is_supervisor,
                    e.code as entity_code,
                    r.code as role_code,
                    -- Get permission modules from role_permissions for this user's role
                    (
                        SELECT array_agg(DISTINCT p.module_name)
                        FROM role_permissions rp
                        JOIN permissions p ON rp.permission_id = p.id
                        JOIN users u ON u.role_id = rp.role_id
                        WHERE u.id = $1 AND p.module_name IS NOT NULL
                    ) as role_modules
                FROM agent_profiles ap
                LEFT JOIN entities e ON ap.entity_id = e.id
                LEFT JOIN users u ON ap.user_id = u.id
                LEFT JOIN roles r ON u.role_id = r.id
                WHERE ap.user_id = $1 AND ap.is_active = true
            """
            result = await self.user_permission_repo.db.fetchrow(query, user_id)

            if not result or not result.get('is_supervisor'):
                return False

            # Get the permission prefix (e.g., "treasury" from "treasury.validate_payment")
            perm_prefix = permission_name.split('.')[0] if '.' in permission_name else permission_name

            # Generic permissions that ALL supervisors can access
            generic_prefixes = ['agent', 'assignment', 'dashboard', 'escalations', 'reports', 'rules', 'stats', 'workload']
            if perm_prefix in generic_prefixes:
                return True

            # Check if permission module is in supervisor's role modules
            role_modules = result.get('role_modules') or []
            if perm_prefix in role_modules:
                return True

            # Supervisors can also access service_requests if they have any entity
            entity_code = result.get('entity_code')
            if entity_code and perm_prefix in ['service_requests', 'appointments']:
                return True

            return False

        except Exception as e:
            logger.warning(f"Error checking supervisor status for {user_id}: {e}")
            return False

    async def check_permission(
        self,
        user_id: str,
        permission_name: str,
        raise_exception: bool = True
    ) -> bool:
        """
        Check if user has permission and optionally raise exception if not

        Args:
            user_id: User UUID
            permission_name: Permission name
            raise_exception: If True, raises HTTPException on permission denied

        Returns:
            True if has permission

        Raises:
            HTTPException: 403 Forbidden if no permission and raise_exception=True
        """
        has_perm = await self.has_permission(user_id, permission_name)

        if not has_perm and raise_exception:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission_name} required"
            )

        return has_perm

    async def get_user_permissions(
        self,
        user_id: str,
        include_role_permissions: bool = True
    ) -> List[str]:
        """
        Get all permission names for a user

        Uses get_all_permission_names() which resolves role hierarchy + user
        overrides in a single optimized CTE query instead of N+1 queries.

        Args:
            user_id: User UUID
            include_role_permissions: Include permissions from role

        Returns:
            List of permission names
        """
        # Single optimized query: role chain (recursive CTE) + user grants - user denies
        # This replaces the previous N+1 loop (1 query per permission)
        return await self.user_permission_repo.get_all_permission_names(user_id)

    async def get_permission_by_id(self, permission_id: str) -> Optional[Dict[str, Any]]:
        """
        Get permission by ID

        Args:
            permission_id: Permission UUID

        Returns:
            Permission dict or None
        """
        return await self.permission_repo.get_by_id(permission_id)

    async def get_permission_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get permission by name

        Args:
            name: Permission name

        Returns:
            Permission dict or None
        """
        return await self.permission_repo.get_by_name(name)

    async def get_all_permissions(
        self,
        module_name: Optional[str] = None,
        resource: Optional[str] = None,
        is_critical: Optional[bool] = None,
        page: int = 1,
        page_size: int = 100
    ) -> Dict[str, Any]:
        """
        Get all permissions with pagination

        Args:
            module_name: Filter by module
            resource: Filter by resource
            is_critical: Filter by critical flag
            page: Page number (1-indexed)
            page_size: Results per page

        Returns:
            Dict with permissions list and pagination info
        """
        offset = (page - 1) * page_size

        permissions = await self.permission_repo.get_all(
            module_name=module_name,
            resource=resource,
            is_critical=is_critical,
            limit=page_size,
            offset=offset
        )

        total = await self.permission_repo.count(
            module_name=module_name,
            resource=resource,
            is_critical=is_critical
        )

        total_pages = (total + page_size - 1) // page_size

        return {
            "permissions": permissions,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages
        }

    async def get_permissions_by_module(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get all permissions grouped by module

        Returns:
            Dict with module names as keys
        """
        return await self.permission_repo.get_grouped_by_module()

    async def create_permission(self, permission: PermissionCreate) -> Dict[str, Any]:
        """
        Create a new permission

        Args:
            permission: Permission data

        Returns:
            Created permission dict

        Raises:
            HTTPException: 409 Conflict if permission name already exists
        """
        # Check if permission already exists
        existing = await self.permission_repo.get_by_name(permission.name)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Permission '{permission.name}' already exists"
            )

        result = await self.permission_repo.create(permission)

        # Invalidate all permissions cache (new permission might affect role assignments)
        await invalidate_all_permissions_cache()

        return result

    async def bulk_create_permissions(
        self,
        permissions: List[PermissionCreate]
    ) -> List[Dict[str, Any]]:
        """
        Create multiple permissions at once

        Args:
            permissions: List of permission data

        Returns:
            List of created permissions (duplicates are skipped)
        """
        return await self.permission_repo.bulk_create(permissions)

    async def update_permission(
        self,
        permission_id: str,
        permission: PermissionUpdate
    ) -> Dict[str, Any]:
        """
        Update a permission

        Args:
            permission_id: Permission UUID
            permission: Updated permission data

        Returns:
            Updated permission dict

        Raises:
            HTTPException: 404 Not Found if permission doesn't exist
        """
        updated = await self.permission_repo.update(permission_id, permission)

        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Permission with id '{permission_id}' not found"
            )

        # Invalidate all permissions cache (permission change affects all users with this permission)
        await invalidate_all_permissions_cache()

        return updated

    async def delete_permission(self, permission_id: str) -> bool:
        """
        Delete a permission

        Args:
            permission_id: Permission UUID

        Returns:
            True if deleted

        Raises:
            HTTPException: 404 Not Found if permission doesn't exist
        """
        deleted = await self.permission_repo.delete(permission_id)

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Permission with id '{permission_id}' not found"
            )

        # Invalidate all permissions cache
        await invalidate_all_permissions_cache()

        return True

    async def get_critical_permissions(self) -> List[Dict[str, Any]]:
        """
        Get all critical permissions

        Returns:
            List of critical permissions
        """
        return await self.permission_repo.get_critical_permissions()

    async def get_user_permissions_summary(self, user_id: str) -> Dict[str, Any]:
        """
        Get summary of user's permissions

        Args:
            user_id: User UUID

        Returns:
            Summary dict with counts
        """
        return await self.user_permission_repo.get_user_permissions_summary(user_id)


# Factory function for creating service with explicit db connection
def create_permission_service(db_connection) -> PermissionService:
    """
    Create permission service with repositories (for direct calls with db_connection).

    Args:
        db_connection: Database connection

    Returns:
        PermissionService instance
    """
    permission_repo = PermissionRepository(db_connection)
    role_repo = RoleRepository(db_connection)
    user_permission_repo = UserPermissionRepository(db_connection)

    return PermissionService(permission_repo, role_repo, user_permission_repo)


# Dependency function for use with Depends() in route definitions
async def get_permission_service(db_connection=Depends(get_database)) -> PermissionService:
    """
    FastAPI dependency for permission service.

    Use this with Depends(get_permission_service) in route function signatures.

    Args:
        db_connection: Database connection (injected via Depends)

    Returns:
        PermissionService instance
    """
    return create_permission_service(db_connection)
