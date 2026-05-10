"""
Role Service - Business logic for role management
"""
from typing import List, Optional, Dict, Any
from fastapi import HTTPException, status, Depends

from app.database.connection import get_database
from app.modules.permissions.repositories.role_repository import RoleRepository
from app.modules.permissions.repositories.permission_repository import PermissionRepository
from app.modules.permissions.models.role import (
    RoleCreate,
    RoleUpdate,
)


class RoleService:
    """Service for role operations"""

    def __init__(
        self,
        role_repo: RoleRepository,
        permission_repo: PermissionRepository
    ):
        """
        Initialize service with repositories

        Args:
            role_repo: Role repository
            permission_repo: Permission repository
        """
        self.role_repo = role_repo
        self.permission_repo = permission_repo

    async def get_role_by_id(self, role_id: str) -> Optional[Dict[str, Any]]:
        """
        Get role by ID

        Args:
            role_id: Role UUID

        Returns:
            Role dict or None
        """
        return await self.role_repo.get_by_id(role_id)

    async def get_role_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        """
        Get role by code

        Args:
            code: Role code

        Returns:
            Role dict or None
        """
        return await self.role_repo.get_by_code(code)

    async def get_role_with_permissions(self, role_id: str) -> Optional[Dict[str, Any]]:
        """
        Get role with associated permissions

        Args:
            role_id: Role UUID

        Returns:
            Role dict with permissions list or None
        """
        return await self.role_repo.get_with_permissions(role_id)

    async def get_all_roles(
        self,
        entity_type: Optional[str] = None,
        is_system: Optional[bool] = None,
        page: int = 1,
        page_size: int = 100
    ) -> Dict[str, Any]:
        """
        Get all roles with pagination

        Args:
            entity_type: Filter by entity type
            is_system: Filter by system role flag
            page: Page number (1-indexed)
            page_size: Results per page

        Returns:
            Dict with roles list and pagination info
        """
        offset = (page - 1) * page_size

        roles = await self.role_repo.get_all(
            entity_type=entity_type,
            is_system=is_system,
            limit=page_size,
            offset=offset
        )

        total = await self.role_repo.count(
            entity_type=entity_type,
            is_system=is_system
        )

        total_pages = (total + page_size - 1) // page_size

        return {
            "roles": roles,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages
        }

    async def get_system_roles(self) -> List[Dict[str, Any]]:
        """
        Get all system roles

        Returns:
            List of system roles
        """
        return await self.role_repo.get_system_roles()

    async def get_custom_roles(self) -> List[Dict[str, Any]]:
        """
        Get all custom (non-system) roles

        Returns:
            List of custom roles
        """
        return await self.role_repo.get_custom_roles()

    async def get_agent_rbac_roles(self) -> List[Dict[str, Any]]:
        """
        Get all predefined RBAC roles for agents

        These are system roles with entity_type='agent' that define
        what permissions an agent has. Used during agent creation.

        Returns:
            List of agent RBAC roles (dgi_validator, dgi_approver,
            ministry_validator, ministry_approver, auditor, supervisor_agent)
        """
        return await self.role_repo.get_agent_rbac_roles()

    async def create_role(
        self,
        role: RoleCreate,
        created_by: str
    ) -> Dict[str, Any]:
        """
        Create a new custom role

        Args:
            role: Role data
            created_by: User ID who is creating the role

        Returns:
            Created role dict

        Raises:
            HTTPException: 409 Conflict if role code already exists
        """
        # Check if role code already exists
        existing = await self.role_repo.get_by_code(role.code)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Role with code '{role.code}' already exists"
            )

        return await self.role_repo.create(role, created_by)

    async def update_role(
        self,
        role_id: str,
        role: RoleUpdate
    ) -> Dict[str, Any]:
        """
        Update a role

        Args:
            role_id: Role UUID
            role: Updated role data

        Returns:
            Updated role dict

        Raises:
            HTTPException: 404 Not Found if role doesn't exist
            HTTPException: 403 Forbidden if trying to update system role
        """
        try:
            updated = await self.role_repo.update(role_id, role)

            if not updated:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Role with id '{role_id}' not found"
                )

            return updated
        except ValueError as e:
            if "system role" in str(e).lower():
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot update system roles"
                )
            raise

    async def delete_role(self, role_id: str) -> bool:
        """
        Delete a role

        Args:
            role_id: Role UUID

        Returns:
            True if deleted

        Raises:
            HTTPException: 404 Not Found if role doesn't exist
            HTTPException: 403 Forbidden if trying to delete system role
        """
        try:
            deleted = await self.role_repo.delete(role_id)

            if not deleted:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Role with id '{role_id}' not found"
                )

            return True
        except ValueError as e:
            if "system role" in str(e).lower():
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot delete system roles"
                )
            raise

    async def assign_permissions_to_role(
        self,
        role_id: str,
        permission_ids: List[str],
        granted: bool = True,
        assigned_by: str = None
    ) -> Dict[str, Any]:
        """
        Assign multiple permissions to a role

        Args:
            role_id: Role UUID
            permission_ids: List of permission UUIDs
            granted: True to grant, False to deny
            assigned_by: User ID who is making the assignment

        Returns:
            Dict with assignment results

        Raises:
            HTTPException: 404 Not Found if role doesn't exist
        """
        # Verify role exists
        role = await self.role_repo.get_by_id(role_id)
        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Role with id '{role_id}' not found"
            )

        # Batch-validate all permissions exist (1 query instead of N)
        existing = await self.permission_repo.db.fetch(
            "SELECT id::text FROM permissions WHERE id = ANY($1::uuid[])",
            permission_ids
        )
        existing_ids = {str(row['id']) for row in existing}
        invalid_permissions = [pid for pid in permission_ids if pid not in existing_ids]

        if invalid_permissions:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Permissions not found: {', '.join(invalid_permissions)}"
            )

        # Batch-assign permissions (1 query instead of N)
        assigned_count = await self.role_repo.assign_permissions_batch(
            role_id, permission_ids, granted, assigned_by
        )

        return {
            "role_id": role_id,
            "assigned_count": assigned_count,
            "granted": granted
        }

    async def remove_permissions_from_role(
        self,
        role_id: str,
        permission_ids: List[str]
    ) -> Dict[str, Any]:
        """
        Remove permissions from a role

        Args:
            role_id: Role UUID
            permission_ids: List of permission UUIDs to remove

        Returns:
            Dict with removal results

        Raises:
            HTTPException: 404 Not Found if role doesn't exist
        """
        # Verify role exists
        role = await self.role_repo.get_by_id(role_id)
        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Role with id '{role_id}' not found"
            )

        # Batch-remove permissions (1 query instead of N)
        removed_count = await self.role_repo.remove_permissions_batch(role_id, permission_ids)

        return {
            "role_id": role_id,
            "removed_count": removed_count
        }

    async def get_role_permissions(self, role_id: str) -> List[str]:
        """
        Get list of permission IDs for a role

        Args:
            role_id: Role UUID

        Returns:
            List of permission UUIDs

        Raises:
            HTTPException: 404 Not Found if role doesn't exist
        """
        role = await self.role_repo.get_by_id(role_id)
        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Role with id '{role_id}' not found"
            )

        return await self.role_repo.get_role_permissions(role_id)

    async def assign_role_to_user(
        self,
        user_id: str,
        role_id: str
    ) -> bool:
        """
        Assign a role to a user (updates users.role_id)

        Args:
            user_id: User UUID
            role_id: Role UUID

        Returns:
            True if assigned

        Note: This would need access to user repository
        """
        # This functionality should be in a UserService
        # For now, it's a placeholder
        raise NotImplementedError("Use UserService.assign_role() instead")


# Helper function for use in dependencies
async def get_role_service(db_connection=Depends(get_database)) -> RoleService:
    """
    Create role service with repositories

    Args:
        db_connection: Database connection (injected via FastAPI Depends)

    Returns:
        RoleService instance
    """
    role_repo = RoleRepository(db_connection)
    permission_repo = PermissionRepository(db_connection)

    return RoleService(role_repo, permission_repo)
