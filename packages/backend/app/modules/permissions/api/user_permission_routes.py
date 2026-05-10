"""
User Permission API Routes - REST endpoints for user-specific permissions
"""
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from uuid import UUID

from app.modules.auth.middleware.auth_middleware import get_current_user
from app.core.database import get_db_connection
from app.modules.users.models.user import UserResponse
from app.modules.permissions.models.user_permission import (
    UserPermissionCreate,
    UserPermissionUpdate,
    UserPermissionResponse,
    UserPermissionWithDetails,
    GrantPermissionToUserRequest,
    RevokePermissionFromUserRequest,
    UserPermissionsSummary,
)
from app.modules.permissions.repositories.user_permission_repository import (
    UserPermissionRepository,
)
from app.modules.permissions.services.permission_service import (
    PermissionService,
    get_permission_service,
)
from app.modules.permissions.middleware.permission_middleware import require_permission
from app.core.cache import invalidate_user_permissions_cache


router = APIRouter(prefix="/user-permissions", tags=["User Permissions"])


def get_user_permission_repo(db_connection=Depends(get_db_connection)) -> UserPermissionRepository:
    """Dependency to get user permission repository"""
    return UserPermissionRepository(db_connection)


@router.get("/user/{user_id}", response_model=List[UserPermissionWithDetails])
@require_permission("user_permissions.view")
async def get_user_permissions(
    user_id: UUID,
    include_expired: bool = Query(False, description="Include expired permissions"),
    current_user: UserResponse = Depends(get_current_user),
    user_permission_repo: UserPermissionRepository = Depends(get_user_permission_repo),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """
    Get all user-specific permissions for a user

    Requires: user_permissions.view

    Args:
        user_id: User UUID
        include_expired: Whether to include expired permissions

    Returns:
        List of user permissions with details (permission name, granted by, etc.)
    """
    permissions = await user_permission_repo.get_by_user_with_details(
        str(user_id),
        include_expired=include_expired
    )

    return permissions


@router.get("/user/{user_id}/summary", response_model=UserPermissionsSummary)
@require_permission("user_permissions.view")
async def get_user_permissions_summary(
    user_id: UUID,
    current_user: UserResponse = Depends(get_current_user),
    user_permission_repo: UserPermissionRepository = Depends(get_user_permission_repo),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """
    Get comprehensive summary of user's permissions

    Requires: user_permissions.view

    Args:
        user_id: User UUID

    Returns:
        Summary with role permissions, user grants, and user denies
    """
    summary = await user_permission_repo.get_user_permissions_summary(str(user_id))

    if not summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id '{user_id}' not found"
        )

    return summary


@router.post("/grant", response_model=UserPermissionResponse, status_code=status.HTTP_201_CREATED)
@require_permission("user_permissions.grant")
async def grant_permission_to_user(
    request: GrantPermissionToUserRequest,
    current_user: UserResponse = Depends(get_current_user),
    user_permission_repo: UserPermissionRepository = Depends(get_user_permission_repo),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """
    Grant a specific permission to a user

    Requires: user_permissions.grant (critical permission)

    This creates a user-specific permission grant that overrides role permissions.
    Can be temporary (with expires_at) or permanent (without expires_at).

    Args:
        request: Grant request with user_id, permission_id, optional expiration

    Returns:
        Created user permission

    Raises:
        404: User or permission not found
    """
    # Validate expiration date if provided
    if request.expires_at and request.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Expiration date must be in the future"
        )

    user_permission = UserPermissionCreate(
        user_id=request.user_id,
        permission_id=request.permission_id,
        granted=True,
        granted_by=UUID(current_user.id),
        expires_at=request.expires_at,
        reason=request.reason
    )

    created = await user_permission_repo.create(user_permission)

    if not created:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to grant permission"
        )

    # Invalidate cached permissions for this user
    await invalidate_user_permissions_cache(str(request.user_id))

    return created


@router.post("/revoke", response_model=dict)
@require_permission("user_permissions.revoke")
async def revoke_permission_from_user(
    request: RevokePermissionFromUserRequest,
    current_user: UserResponse = Depends(get_current_user),
    user_permission_repo: UserPermissionRepository = Depends(get_user_permission_repo),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """
    Revoke a permission from a user

    Requires: user_permissions.revoke (critical permission)

    This removes a user-specific permission grant. If the user had this permission
    via role, they will lose access. Can also be used to explicitly deny a permission
    that the user would otherwise have via role.

    Args:
        request: Revoke request with user_id and permission_id

    Returns:
        Success confirmation

    Raises:
        404: User permission not found
    """
    deleted = await user_permission_repo.delete(
        str(request.user_id),
        str(request.permission_id)
    )

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User permission not found for user '{request.user_id}' and permission '{request.permission_id}'"
        )

    # Invalidate cached permissions for this user
    await invalidate_user_permissions_cache(str(request.user_id))

    return {
        "success": True,
        "message": "Permission revoked successfully",
        "user_id": str(request.user_id),
        "permission_id": str(request.permission_id)
    }


@router.post("/deny", response_model=UserPermissionResponse, status_code=status.HTTP_201_CREATED)
@require_permission("user_permissions.grant")
async def deny_permission_to_user(
    user_id: UUID,
    permission_id: UUID,
    reason: Optional[str] = None,
    current_user: UserResponse = Depends(get_current_user),
    user_permission_repo: UserPermissionRepository = Depends(get_user_permission_repo),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """
    Explicitly deny a permission to a user

    Requires: user_permissions.grant (critical permission)

    This creates an explicit DENY that overrides role permissions.
    Use this when a user should NOT have a permission even if their role grants it.

    Args:
        user_id: User UUID
        permission_id: Permission UUID
        reason: Optional reason for the denial

    Returns:
        Created user permission (with granted=False)

    Raises:
        404: User or permission not found
    """
    user_permission = UserPermissionCreate(
        user_id=user_id,
        permission_id=permission_id,
        granted=False,  # Explicit DENY
        granted_by=UUID(current_user.id),
        expires_at=None,  # Denies are typically permanent
        reason=reason or "Explicit permission denial"
    )

    created = await user_permission_repo.create(user_permission)

    if not created:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to deny permission"
        )

    # Invalidate cached permissions for this user
    await invalidate_user_permissions_cache(str(user_id))

    return created


@router.put("/{user_id}/{permission_id}", response_model=UserPermissionResponse)
@require_permission("user_permissions.update")
async def update_user_permission(
    user_id: UUID,
    permission_id: UUID,
    update_data: UserPermissionUpdate,
    current_user: UserResponse = Depends(get_current_user),
    user_permission_repo: UserPermissionRepository = Depends(get_user_permission_repo),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """
    Update a user-specific permission

    Requires: user_permissions.update (critical permission)

    Can update granted flag, expiration date, or reason.

    Args:
        user_id: User UUID
        permission_id: Permission UUID
        update_data: Fields to update

    Returns:
        Updated user permission

    Raises:
        404: User permission not found
        400: Invalid expiration date
    """
    # Validate expiration date if provided
    if update_data.expires_at and update_data.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Expiration date must be in the future"
        )

    updated = await user_permission_repo.update(
        str(user_id),
        str(permission_id),
        update_data
    )

    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User permission not found for user '{user_id}' and permission '{permission_id}'"
        )

    # Invalidate cached permissions for this user
    await invalidate_user_permissions_cache(str(user_id))

    return updated


@router.get("/expired", response_model=List[UserPermissionWithDetails])
@require_permission("user_permissions.view")
async def get_expired_permissions(
    limit: int = Query(500, ge=1, le=1000, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    current_user: UserResponse = Depends(get_current_user),
    user_permission_repo: UserPermissionRepository = Depends(get_user_permission_repo),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """
    Get expired user permissions (paginated)

    Requires: user_permissions.view

    Returns:
        List of expired permissions across all users
    """
    expired = await user_permission_repo.get_expired_permissions(limit=limit, offset=offset)
    return expired


@router.post("/cleanup-expired", response_model=dict)
@require_permission("user_permissions.cleanup")
async def cleanup_expired_permissions(
    current_user: UserResponse = Depends(get_current_user),
    user_permission_repo: UserPermissionRepository = Depends(get_user_permission_repo),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """
    Remove all expired user permissions

    Requires: user_permissions.cleanup (critical permission)

    This is a maintenance operation that deletes expired temporal permissions.
    Should be run periodically (e.g., daily via cron job).

    Returns:
        Count of deleted permissions
    """
    deleted_count = await user_permission_repo.cleanup_expired()

    return {
        "success": True,
        "message": f"Cleaned up {deleted_count} expired permissions",
        "deleted_count": deleted_count,
        "cleaned_at": datetime.now(timezone.utc).isoformat()
    }


@router.get("/check/{user_id}/{permission_name}", response_model=dict)
@require_permission("user_permissions.view")
async def check_user_has_permission(
    user_id: UUID,
    permission_name: str,
    current_user: UserResponse = Depends(get_current_user),
    user_permission_repo: UserPermissionRepository = Depends(get_user_permission_repo),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """
    Check if a user has a specific permission

    Requires: user_permissions.view

    This checks both role permissions and user-specific overrides.

    Args:
        user_id: User UUID
        permission_name: Permission name (e.g., "assignment.create")

    Returns:
        Dict with has_permission boolean and source (role/user/none)
    """
    has_perm = await user_permission_repo.has_permission(
        str(user_id),
        permission_name
    )

    return {
        "user_id": str(user_id),
        "permission_name": permission_name,
        "has_permission": has_perm
    }


@router.get("/{user_id}/{permission_id}", response_model=UserPermissionResponse)
@require_permission("user_permissions.view")
async def get_user_permission(
    user_id: UUID,
    permission_id: UUID,
    current_user: UserResponse = Depends(get_current_user),
    user_permission_repo: UserPermissionRepository = Depends(get_user_permission_repo),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """
    Get a specific user permission

    Requires: user_permissions.view

    Args:
        user_id: User UUID
        permission_id: Permission UUID

    Returns:
        User permission details

    Raises:
        404: User permission not found
    """
    user_perm = await user_permission_repo.get_by_user_and_permission(
        str(user_id),
        str(permission_id)
    )

    if not user_perm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User permission not found for user '{user_id}' and permission '{permission_id}'"
        )

    return user_perm
