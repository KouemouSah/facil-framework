"""
Permission API Routes - REST endpoints for permission management
"""
from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status, Query
from uuid import UUID

from app.modules.auth.middleware.auth_middleware import get_current_user
from app.core.database import get_db_connection
from app.modules.users.models.user import UserResponse
from app.modules.permissions.models.permission import (
    PermissionCreate,
    PermissionUpdate,
    PermissionResponse,
    PermissionListResponse,
    PermissionsByModuleResponse,
)
from app.modules.permissions.services.permission_service import (
    PermissionService,
    get_permission_service,
)
from app.modules.permissions.middleware.permission_middleware import require_permission


router = APIRouter(prefix="/permissions", tags=["Permissions"])


@router.get("", response_model=PermissionListResponse)
@require_permission("permissions.view")
async def get_all_permissions(
    module_name: Optional[str] = Query(None, description="Filter by module name"),
    is_critical: Optional[bool] = Query(None, description="Filter by critical flag"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=500, description="Results per page (max 500 for permissions catalog)"),
    current_user: UserResponse = Depends(get_current_user),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """
    Get all permissions with pagination and filtering

    Requires: permissions.view
    """
    result = await permission_service.get_all_permissions(
        module_name=module_name,
        is_critical=is_critical,
        page=page,
        page_size=page_size
    )

    return PermissionListResponse(**result)


@router.get("/grouped-by-module", response_model=List[PermissionsByModuleResponse])
@require_permission("permissions.view")
async def get_permissions_grouped_by_module(
    current_user: UserResponse = Depends(get_current_user),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """
    Get all permissions grouped by module

    Requires: permissions.view

    Returns:
        List of modules with their permissions
    """
    grouped = await permission_service.get_permissions_by_module()

    return [
        PermissionsByModuleResponse(
            module_name=module,
            permissions=perms,
            total=len(perms)
        )
        for module, perms in grouped.items()
    ]


@router.get("/critical", response_model=List[PermissionResponse])
@require_permission("permissions.view")
async def get_critical_permissions(
    current_user: UserResponse = Depends(get_current_user),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """
    Get all critical permissions

    Requires: permissions.view

    Returns:
        List of critical permissions that require special authorization
    """
    critical = await permission_service.get_critical_permissions()
    return critical


@router.get("/module/{module_name}", response_model=List[PermissionResponse])
@require_permission("permissions.view")
async def get_permissions_by_module(
    module_name: str,
    current_user: UserResponse = Depends(get_current_user),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """
    Get all permissions for a specific module

    Requires: permissions.view

    Args:
        module_name: Module name (e.g., "assignment", "declarations")

    Returns:
        List of permissions for the module
    """
    permissions = await permission_service.get_permissions_by_module(module_name)
    return permissions


@router.get("/{permission_id}", response_model=PermissionResponse)
@require_permission("permissions.view")
async def get_permission_by_id(
    permission_id: UUID,
    current_user: UserResponse = Depends(get_current_user),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """
    Get permission by ID

    Requires: permissions.view

    Args:
        permission_id: Permission UUID

    Returns:
        Permission details

    Raises:
        404: Permission not found
    """
    permission = await permission_service.get_permission_by_id(str(permission_id))

    if not permission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Permission with id '{permission_id}' not found"
        )

    return permission


@router.post("", response_model=PermissionResponse, status_code=status.HTTP_201_CREATED)
@require_permission("permissions.create")
async def create_permission(
    permission: PermissionCreate,
    current_user: UserResponse = Depends(get_current_user),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """
    Create a new permission

    Requires: permissions.create (critical permission)

    Args:
        permission: Permission data

    Returns:
        Created permission

    Raises:
        409: Permission with same name already exists
    """
    created = await permission_service.create_permission(permission)
    return created


@router.post("/bulk", response_model=List[PermissionResponse], status_code=status.HTTP_201_CREATED)
@require_permission("permissions.create")
async def bulk_create_permissions(
    permissions: List[PermissionCreate],
    current_user: UserResponse = Depends(get_current_user),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """
    Bulk create multiple permissions

    Requires: permissions.create (critical permission)

    Args:
        permissions: List of permission data

    Returns:
        List of created permissions (skips duplicates)

    Note:
        Uses ON CONFLICT DO NOTHING - duplicates are skipped
    """
    created = await permission_service.bulk_create_permissions(permissions)
    return created


@router.put("/{permission_id}", response_model=PermissionResponse)
@require_permission("permissions.update")
async def update_permission(
    permission_id: UUID,
    permission: PermissionUpdate,
    current_user: UserResponse = Depends(get_current_user),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """
    Update a permission

    Requires: permissions.update (critical permission)

    Args:
        permission_id: Permission UUID
        permission: Updated permission data

    Returns:
        Updated permission

    Raises:
        404: Permission not found
    """
    updated = await permission_service.update_permission(
        str(permission_id),
        permission
    )

    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Permission with id '{permission_id}' not found"
        )

    return updated


@router.delete("/{permission_id}", status_code=status.HTTP_204_NO_CONTENT)
@require_permission("permissions.delete")
async def delete_permission(
    permission_id: UUID,
    current_user: UserResponse = Depends(get_current_user),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """
    Delete a permission

    Requires: permissions.delete (critical permission)

    Args:
        permission_id: Permission UUID

    Raises:
        404: Permission not found
        409: Permission is in use (has role/user assignments)
    """
    deleted = await permission_service.delete_permission(str(permission_id))

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Permission with id '{permission_id}' not found"
        )

    return None


@router.get("/user/{user_id}/check/{permission_name}", response_model=dict)
@require_permission("permissions.view")
async def check_user_permission(
    user_id: UUID,
    permission_name: str,
    current_user: UserResponse = Depends(get_current_user),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """
    Check if a user has a specific permission

    Requires: permissions.view

    Args:
        user_id: User UUID
        permission_name: Permission name (e.g., "assignment.create")

    Returns:
        Dict with has_permission boolean
    """
    has_perm = await permission_service.has_permission(
        str(user_id),
        permission_name
    )

    return {
        "user_id": str(user_id),
        "permission_name": permission_name,
        "has_permission": has_perm
    }


@router.get("/user/{user_id}/summary", response_model=dict)
@require_permission("permissions.view")
async def get_user_permissions_summary(
    user_id: UUID,
    current_user: UserResponse = Depends(get_current_user),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """
    Get comprehensive summary of user's permissions

    Requires: permissions.view

    Args:
        user_id: User UUID

    Returns:
        Summary with role permissions and user-specific grants/denies
    """
    summary = await permission_service.get_user_permissions_summary(str(user_id))
    return summary


@router.get("/anomalies/overprivileged", response_model=dict)
@require_permission("admin.view_security")
async def detect_overprivileged_users(
    min_risk_score: int = Query(20, ge=0, le=100, description="Minimum risk score"),
    risk_level: Optional[str] = Query(None, description="Filter by risk level (LOW, MEDIUM, HIGH, CRITICAL)"),
    limit: int = Query(50, ge=1, le=200, description="Max results"),
    current_user: UserResponse = Depends(get_current_user),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """
    Detect overprivileged users based on permission anomalies.

    Requires: admin.view_security

    Uses the v_overprivileged_users_detection view with risk scoring:
    - +1 per extra user grant
    - +5 per critical user grant
    - +10 if >50% more permissions than role average
    - +15 if >10 critical permissions

    Returns users with risk_score, risk_level, and recommendations.
    """
    users = await permission_service.repo.detect_overprivileged_users(
        min_risk_score=min_risk_score,
        risk_level=risk_level,
        limit=limit,
    )
    # Serialize UUIDs
    for u in users:
        if 'user_id' in u:
            u['user_id'] = str(u['user_id'])
    return {
        "overprivileged_users": users,
        "count": len(users),
        "filters": {
            "min_risk_score": min_risk_score,
            "risk_level": risk_level,
        },
    }


# =============================================================================
# PERMISSION SIMULATOR
# =============================================================================


class SimulateRolePermissionRequest(BaseModel):
    """Request body for role permission simulation."""
    role_id: str
    permission_names: List[str]
    action: str  # "grant" or "revoke"


class SimulateUserRoleChangeRequest(BaseModel):
    """Request body for user role change simulation."""
    user_id: str
    new_role_id: str


@router.post("/simulate/role-permission")
@require_permission("roles.view")
async def simulate_role_permission_change(
    request: SimulateRolePermissionRequest,
    current_user: UserResponse = Depends(get_current_user),
):
    """
    Simulate granting/revoking permissions on a role WITHOUT applying.

    Shows which users would be affected and how their permissions would change.

    Requires: roles.view
    """
    if request.action not in ("grant", "revoke"):
        raise HTTPException(status_code=400, detail="action must be 'grant' or 'revoke'")

    from app.modules.permissions.services.permission_simulator import PermissionSimulator
    from app.database.connection import db_manager

    async with db_manager.get_connection() as conn:
        simulator = PermissionSimulator(conn)
        return await simulator.simulate_role_permission_change(
            role_id=request.role_id,
            permission_names=request.permission_names,
            action=request.action,
        )


@router.post("/simulate/user-role-change")
@require_permission("roles.view")
async def simulate_user_role_change(
    request: SimulateUserRoleChangeRequest,
    current_user: UserResponse = Depends(get_current_user),
):
    """
    Simulate changing a user's role WITHOUT applying.

    Shows permission diff (added/removed) that would result from the role change.

    Requires: roles.view
    """
    from app.modules.permissions.services.permission_simulator import PermissionSimulator
    from app.database.connection import db_manager

    async with db_manager.get_connection() as conn:
        simulator = PermissionSimulator(conn)
        return await simulator.simulate_user_role_change(
            user_id=request.user_id,
            new_role_id=request.new_role_id,
        )
