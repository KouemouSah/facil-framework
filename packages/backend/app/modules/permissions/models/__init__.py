"""
Permissions Models - Exports all Pydantic models
"""

# Permission models
from .permission import (
    PermissionBase,
    PermissionCreate,
    PermissionUpdate,
    PermissionResponse,
    PermissionListResponse,
    PermissionsByModuleResponse,
)

# Role models
from .role import (
    RoleBase,
    RoleCreate,
    RoleUpdate,
    RoleResponse,
    RoleWithPermissionsResponse,
    RoleListResponse,
    AssignPermissionsToRoleRequest,
    RemovePermissionsFromRoleRequest,
)

# RolePermission models
from .role_permission import (
    RolePermissionBase,
    RolePermissionCreate,
    RolePermissionResponse,
    RolePermissionWithDetails,
)

# UserPermission models
from .user_permission import (
    UserPermissionBase,
    UserPermissionCreate,
    UserPermissionUpdate,
    UserPermissionResponse,
    UserPermissionWithDetails,
    UserPermissionListResponse,
    GrantPermissionToUserRequest,
    RevokePermissionFromUserRequest,
    UserPermissionsSummary,
)

# PermissionGrant (audit) models
from .permission_grant import (
    PermissionAuditLogBase,
    PermissionAuditLogResponse,
    PermissionAuditLogWithDetails,
    PermissionAuditLogListResponse,
    PermissionAuditLogFilters,
    PermissionGrantSummary,
)

__all__ = [
    # Permission
    "PermissionBase",
    "PermissionCreate",
    "PermissionUpdate",
    "PermissionResponse",
    "PermissionListResponse",
    "PermissionsByModuleResponse",
    # Role
    "RoleBase",
    "RoleCreate",
    "RoleUpdate",
    "RoleResponse",
    "RoleWithPermissionsResponse",
    "RoleListResponse",
    "AssignPermissionsToRoleRequest",
    "RemovePermissionsFromRoleRequest",
    # RolePermission
    "RolePermissionBase",
    "RolePermissionCreate",
    "RolePermissionResponse",
    "RolePermissionWithDetails",
    # UserPermission
    "UserPermissionBase",
    "UserPermissionCreate",
    "UserPermissionUpdate",
    "UserPermissionResponse",
    "UserPermissionWithDetails",
    "UserPermissionListResponse",
    "GrantPermissionToUserRequest",
    "RevokePermissionFromUserRequest",
    "UserPermissionsSummary",
    # PermissionGrant (audit)
    "PermissionAuditLogBase",
    "PermissionAuditLogResponse",
    "PermissionAuditLogWithDetails",
    "PermissionAuditLogListResponse",
    "PermissionAuditLogFilters",
    "PermissionGrantSummary",
]
