"""
Role API Routes - REST endpoints for role management

BUG 6 Fix deployed: 2026-01-15 - Validators moved from Base to Create models
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from uuid import UUID
import csv
import io

from app.modules.auth.middleware.auth_middleware import get_current_user
from app.core.database import get_db_connection
from app.modules.users.models.user import UserResponse
from app.modules.permissions.models.role import (
    RoleCreate,
    RoleUpdate,
    RoleResponse,
    RoleWithPermissionsResponse,
    AssignPermissionsToRoleRequest,
    RemovePermissionsFromRoleRequest,
    RoleMenuConfigUpdate,
)
from app.modules.permissions.services.role_service import (
    RoleService,
    get_role_service,
)
from app.modules.permissions.services.permission_service import (
    PermissionService,
    get_permission_service,
)
from app.modules.permissions.middleware.permission_middleware import require_permission
from app.core.cache import invalidate_role_menu_cache, invalidate_role_permissions_cache


router = APIRouter(prefix="/roles", tags=["Roles"])


@router.get("", response_model=dict)
@require_permission("roles.view")
async def get_all_roles(
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    is_system: Optional[bool] = Query(None, description="Filter system/custom roles"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Results per page"),
    current_user: UserResponse = Depends(get_current_user),
    role_service: RoleService = Depends(get_role_service),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """
    Get all roles with pagination and filtering

    Requires: roles.view

    Args:
        entity_type: Filter by entity type (e.g., "taxpayer", "professional")
        is_system: True for system roles, False for custom roles, None for all
        page: Page number
        page_size: Results per page

    Returns:
        Paginated list of roles
    """
    result = await role_service.get_all_roles(
        entity_type=entity_type,
        is_system=is_system,
        page=page,
        page_size=page_size
    )

    return result


@router.get("/system", response_model=List[RoleResponse])
@require_permission("roles.view")
async def get_system_roles(
    current_user: UserResponse = Depends(get_current_user),
    role_service: RoleService = Depends(get_role_service),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """
    Get all system (built-in) roles

    Requires: roles.view

    Returns:
        List of system roles (cannot be modified or deleted)
    """
    system_roles = await role_service.get_system_roles()
    return system_roles


@router.get("/custom", response_model=List[RoleResponse])
@require_permission("roles.view")
async def get_custom_roles(
    current_user: UserResponse = Depends(get_current_user),
    role_service: RoleService = Depends(get_role_service),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """
    Get all custom (user-created) roles

    Requires: roles.view

    Returns:
        List of custom roles (can be modified and deleted)
    """
    custom_roles = await role_service.get_custom_roles()
    return custom_roles


@router.get("/agent-roles", response_model=List[RoleResponse])
@require_permission("roles.view")
async def get_agent_rbac_roles(
    current_user: UserResponse = Depends(get_current_user),
    role_service: RoleService = Depends(get_role_service),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """
    Get all predefined RBAC roles for agents

    Requires: roles.view

    Returns:
        List of agent RBAC roles (dgi_validator, dgi_approver, ministry_validator, etc.)

    These roles should be assigned to agents during creation to define their permissions.
    """
    agent_roles = await role_service.get_agent_rbac_roles()
    return agent_roles


@router.get("/permission-matrix", response_model=dict)
@require_permission("roles.view")
async def get_permission_matrix(
    module_name: Optional[str] = Query(None, description="Filter by permission module"),
    current_user: UserResponse = Depends(get_current_user),
    role_service: RoleService = Depends(get_role_service),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """
    Get permission matrix: all roles × permissions with assignment data.

    Requires: roles.view

    Returns a single payload with roles, permissions, and an assignments map
    keyed by "role_id:permission_id" → granted boolean.
    Filters permissions by module_name if provided.
    """
    matrix = await role_service.role_repo.get_permission_matrix(module_name)
    # Serialize UUIDs
    for role in matrix["roles"]:
        role["id"] = str(role["id"])
    for perm in matrix["permissions"]:
        perm["id"] = str(perm["id"])
    return matrix


@router.get("/{role_id}", response_model=RoleResponse)
@require_permission("roles.view")
async def get_role_by_id(
    role_id: UUID,
    current_user: UserResponse = Depends(get_current_user),
    role_service: RoleService = Depends(get_role_service),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """
    Get role by ID

    Requires: roles.view

    Args:
        role_id: Role UUID

    Returns:
        Role details

    Raises:
        404: Role not found
    """
    role = await role_service.get_role_by_id(str(role_id))

    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role with id '{role_id}' not found"
        )

    return role


@router.get("/{role_id}/with-permissions", response_model=RoleWithPermissionsResponse)
@require_permission("roles.view")
async def get_role_with_permissions(
    role_id: UUID,
    current_user: UserResponse = Depends(get_current_user),
    role_service: RoleService = Depends(get_role_service),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """
    Get role with all associated permissions

    Requires: roles.view

    Args:
        role_id: Role UUID

    Returns:
        Role with complete list of permissions

    Raises:
        404: Role not found
    """
    role_with_perms = await role_service.get_role_with_permissions(str(role_id))

    if not role_with_perms:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role with id '{role_id}' not found"
        )

    return role_with_perms


@router.get("/code/{code}", response_model=RoleResponse)
@require_permission("roles.view")
async def get_role_by_code(
    code: str,
    current_user: UserResponse = Depends(get_current_user),
    role_service: RoleService = Depends(get_role_service),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """
    Get role by code

    Requires: roles.view

    Args:
        code: Role code (e.g., "admin", "tax_manager")

    Returns:
        Role details

    Raises:
        404: Role not found
    """
    role = await role_service.get_role_by_code(code)

    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role with code '{code}' not found"
        )

    return role


@router.post("", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
@require_permission("roles.create")
async def create_role(
    role: RoleCreate,
    current_user: UserResponse = Depends(get_current_user),
    role_service: RoleService = Depends(get_role_service),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """
    Create a new custom role

    Requires: roles.create (critical permission)

    Args:
        role: Role data

    Returns:
        Created role

    Raises:
        409: Role with same code already exists
    """
    created = await role_service.create_role(role, current_user.id)
    return created


@router.put("/{role_id}", response_model=RoleResponse)
@require_permission("roles.update")
async def update_role(
    role_id: UUID,
    role: RoleUpdate,
    current_user: UserResponse = Depends(get_current_user),
    role_service: RoleService = Depends(get_role_service),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """
    Update a role

    Requires: roles.update (critical permission)

    Args:
        role_id: Role UUID
        role: Updated role data

    Returns:
        Updated role

    Raises:
        404: Role not found
        403: Cannot update system roles
    """
    updated = await role_service.update_role(str(role_id), role)
    return updated


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
@require_permission("roles.delete")
async def delete_role(
    role_id: UUID,
    current_user: UserResponse = Depends(get_current_user),
    role_service: RoleService = Depends(get_role_service),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """
    Delete a role

    Requires: roles.delete (critical permission)

    Args:
        role_id: Role UUID

    Raises:
        404: Role not found
        403: Cannot delete system roles
        409: Role is in use (has assigned users)
    """
    await role_service.delete_role(str(role_id))
    return None


@router.post("/{role_id}/permissions", response_model=dict)
@require_permission("roles.assign_permissions")
async def assign_permissions_to_role(
    role_id: UUID,
    request: AssignPermissionsToRoleRequest,
    current_user: UserResponse = Depends(get_current_user),
    role_service: RoleService = Depends(get_role_service),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """
    Assign multiple permissions to a role

    Requires: roles.assign_permissions (critical permission)

    Args:
        role_id: Role UUID
        request: List of permission IDs and grant/deny flag

    Returns:
        Assignment result summary

    Raises:
        404: Role or permissions not found
    """
    result = await role_service.assign_permissions_to_role(
        role_id=str(role_id),
        permission_ids=[str(pid) for pid in request.permission_ids],
        granted=request.granted,
        assigned_by=current_user.id
    )

    # Invalidate cached permissions for all users with this role
    role = await role_service.get_role_by_id(str(role_id))
    if role and role.get("code"):
        await invalidate_role_permissions_cache(role["code"])

    return result


@router.delete("/{role_id}/permissions", response_model=dict)
@require_permission("roles.assign_permissions")
async def remove_permissions_from_role(
    role_id: UUID,
    request: RemovePermissionsFromRoleRequest,
    current_user: UserResponse = Depends(get_current_user),
    role_service: RoleService = Depends(get_role_service),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """
    Remove permissions from a role

    Requires: roles.assign_permissions (critical permission)

    Args:
        role_id: Role UUID
        request: List of permission IDs to remove

    Returns:
        Removal result summary

    Raises:
        404: Role not found
    """
    result = await role_service.remove_permissions_from_role(
        role_id=str(role_id),
        permission_ids=[str(pid) for pid in request.permission_ids]
    )

    # Invalidate cached permissions for all users with this role
    role = await role_service.get_role_by_id(str(role_id))
    if role and role.get("code"):
        await invalidate_role_permissions_cache(role["code"])

    return result


# POST alias for remove permissions (DELETE with body not well supported by all HTTP clients)
@router.post("/{role_id}/permissions/remove", response_model=dict)
@require_permission("roles.assign_permissions")
async def remove_permissions_from_role_post(
    role_id: UUID,
    request: RemovePermissionsFromRoleRequest,
    current_user: UserResponse = Depends(get_current_user),
    role_service: RoleService = Depends(get_role_service),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """
    Remove permissions from a role (POST alias)

    This is a POST alias for DELETE /{role_id}/permissions because
    DELETE with request body is not well supported by all HTTP clients.

    Requires: roles.assign_permissions (critical permission)
    """
    result = await role_service.remove_permissions_from_role(
        role_id=str(role_id),
        permission_ids=[str(pid) for pid in request.permission_ids]
    )

    # Invalidate cached permissions for all users with this role
    role = await role_service.get_role_by_id(str(role_id))
    if role and role.get("code"):
        await invalidate_role_permissions_cache(role["code"])

    return result


@router.get("/{role_id}/permissions", response_model=List[str])
@require_permission("roles.view")
async def get_role_permissions(
    role_id: UUID,
    current_user: UserResponse = Depends(get_current_user),
    role_service: RoleService = Depends(get_role_service),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """
    Get list of permission IDs for a role

    Requires: roles.view

    Args:
        role_id: Role UUID

    Returns:
        List of permission UUIDs

    Raises:
        404: Role not found
    """
    permission_ids = await role_service.get_role_permissions(str(role_id))
    return permission_ids


@router.post("/{role_id}/clone", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
@require_permission("roles.create")
async def clone_role(
    role_id: UUID,
    new_name: Optional[str] = Query(None, description="Name for cloned role (default: 'Original Name (Copy)')"),
    new_code: Optional[str] = Query(None, description="Code for cloned role (default: 'original_code_copy')"),
    current_user: UserResponse = Depends(get_current_user),
    role_service: RoleService = Depends(get_role_service),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """
    Clone a role with all its permissions

    Requires: roles.create

    Creates a new custom role that is an exact copy of the source role,
    including all permission assignments. Menu/dashboard config are NOT copied.

    Args:
        role_id: Source role UUID to clone
        new_name: Optional custom name (default adds ' (Copy)')
        new_code: Optional custom code (default adds '_copy')

    Returns:
        Created role

    Raises:
        404: Source role not found
        409: Role with same code already exists
    """
    source_role = await role_service.get_role_with_permissions(str(role_id))
    if not source_role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role with id '{role_id}' not found"
        )

    # Generate clone names
    clone_name = new_name or f"{source_role.get('name', 'Role')} (Copy)"
    clone_code = new_code or f"{source_role.get('code', 'role')}_copy"

    # Create the new role
    clone_data = RoleCreate(
        name=clone_name,
        code=clone_code,
        entity_type=source_role.get('entity_type'),
        description=f"Cloned from {source_role.get('name', 'unknown')}",
    )
    created = await role_service.create_role(clone_data, current_user.id)

    # Copy all permissions from source role
    if source_role.get('permissions'):
        permission_ids = [str(p['id']) for p in source_role['permissions']]
        if permission_ids:
            await role_service.assign_permissions_to_role(
                role_id=str(created['id']),
                permission_ids=permission_ids,
                granted=True,
                assigned_by=current_user.id
            )
            # Invalidate cache — new role with permissions needs to be visible
            await invalidate_role_permissions_cache(clone_code)

    return created


# =============================================================================
# EXPORT & BULK OPERATIONS
# =============================================================================


@router.get("/export/csv")
@require_permission("roles.view")
async def export_roles_csv(
    current_user: UserResponse = Depends(get_current_user),
    role_service: RoleService = Depends(get_role_service),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """
    Export all roles as CSV file.

    Requires: roles.view
    """
    roles_data = await role_service.get_all_roles(page=1, page_size=1000)
    roles = roles_data.get("roles", [])

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["name", "code", "entity_type", "is_system", "description", "created_at"])

    for role in roles:
        writer.writerow([
            role.get("name", ""),
            role.get("code", ""),
            role.get("entity_type", ""),
            role.get("is_system", False),
            role.get("description", ""),
            str(role.get("created_at", "")),
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=roles_export.csv"},
    )


@router.post("/bulk-delete", status_code=status.HTTP_200_OK)
@require_permission("roles.delete")
async def bulk_delete_roles(
    role_ids: List[UUID],
    current_user: UserResponse = Depends(get_current_user),
    role_service: RoleService = Depends(get_role_service),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """
    Bulk delete custom roles (system roles are protected).

    Requires: roles.delete

    Returns:
        Dict with deleted count and any failures
    """
    deleted = []
    failed = []

    for role_id in role_ids:
        try:
            role = await role_service.get_role(str(role_id))
            if not role:
                failed.append({"id": str(role_id), "reason": "not_found"})
                continue
            if role.get("is_system"):
                failed.append({"id": str(role_id), "reason": "system_role_protected"})
                continue
            await role_service.delete_role(str(role_id))
            deleted.append(str(role_id))
        except Exception as e:
            failed.append({"id": str(role_id), "reason": str(e)})

    if deleted:
        from app.core.cache import invalidate_all_permissions_cache
        await invalidate_all_permissions_cache()

    return {
        "deleted_count": len(deleted),
        "deleted": deleted,
        "failed_count": len(failed),
        "failed": failed,
    }


# =============================================================================
# ROLE MENU CONFIG ENDPOINTS
# =============================================================================

@router.get("/{role_id}/menu-config", response_model=dict)
@require_permission("roles.view")
async def get_role_menu_config(
    role_id: UUID,
    current_user: UserResponse = Depends(get_current_user),
    role_service: RoleService = Depends(get_role_service),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """
    Get role menu and dashboard configuration

    Requires: roles.view

    Args:
        role_id: Role UUID

    Returns:
        Dict with menu_config and dashboard_config

    Raises:
        404: Role not found
    """
    role = await role_service.get_role_by_id(str(role_id))

    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role with id '{role_id}' not found"
        )

    return {
        "menu_config": role.get("menu_config"),
        "dashboard_config": role.get("dashboard_config"),
        "ui_config": role.get("ui_config"),
    }


@router.put("/{role_id}/menu-config", response_model=dict)
@require_permission("roles.update")
async def update_role_menu_config(
    role_id: UUID,
    data: RoleMenuConfigUpdate,
    current_user: UserResponse = Depends(get_current_user),
    role_service: RoleService = Depends(get_role_service),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """
    Update role menu and dashboard configuration

    Requires: roles.update

    Args:
        role_id: Role UUID
        data: RoleMenuConfigUpdate with menu_config, dashboard_config, ui_config

    Returns:
        Updated menu_config, dashboard_config, ui_config

    Raises:
        404: Role not found
        403: Cannot update system roles
        422: Validation error on dashboard_config or ui_config
    """
    # Build RoleUpdate with only config fields
    # Pydantic sub-models → dict for JSONB storage
    update_data = RoleUpdate(
        menu_config=data.menu_config,
        dashboard_config=data.dashboard_config.model_dump(mode='json')
        if data.dashboard_config is not None else None,
        ui_config=data.ui_config.model_dump(mode='json')
        if data.ui_config is not None else None,
    )

    updated = await role_service.update_role(str(role_id), update_data)

    # Invalidate cached menus for all agents with this role
    try:
        await invalidate_role_menu_cache(str(role_id))
    except Exception:
        pass  # Non-critical — cache will expire naturally (5 min TTL)

    return {
        "menu_config": updated.get("menu_config"),
        "dashboard_config": updated.get("dashboard_config"),
        "ui_config": updated.get("ui_config"),
    }
