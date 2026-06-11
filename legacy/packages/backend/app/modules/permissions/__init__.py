"""
Permissions Module - Complete RBAC system for TaxasGE

This module provides:
- Permission management (CRUD)
- Role management with permission assignment
- User-specific permission overrides
- Temporal permissions with automatic expiration
- Permission middleware decorators for route protection
- Audit trail for all permission changes

Usage:
    # In route handlers
    from app.modules.permissions.middleware import require_permission

    @router.post("/manual")
    @require_permission("assignment.create")
    async def create_assignment(...):
        pass

    # In main.py to register routes
    from app.modules.permissions import permission_router, role_router, user_permission_router

    app.include_router(permission_router, prefix="/api/v1")
    app.include_router(role_router, prefix="/api/v1")
    app.include_router(user_permission_router, prefix="/api/v1")
"""

# =============================================================================
# AUTO-DISCOVERY: Import module_permissions to trigger auto-registration
# This MUST be imported BEFORE services to ensure permissions are registered
# before initialize_permissions() is called
# =============================================================================
from . import module_permissions  # noqa: F401 - triggers discover_and_register_permissions()

# API Routers
from .api import (
    permission_router,
    role_router,
    user_permission_router,
)

# Middleware decorators
from .middleware import (
    require_permission,
    require_any_permission,
    require_all_permissions,
    check_permission,
)

# Services
from .services import (
    PermissionService,
    get_permission_service,
    RoleService,
    get_role_service,
    PermissionRegistry,
    is_permission_registered,
    initialize_permissions,
)

# Models
from .models.permission import (
    PermissionCreate,
    PermissionUpdate,
    PermissionResponse,
)
from .models.role import (
    RoleCreate,
    RoleUpdate,
    RoleResponse,
)
from .models.user_permission import (
    UserPermissionCreate,
    GrantPermissionToUserRequest,
)

__all__ = [
    # Routers
    "permission_router",
    "role_router",
    "user_permission_router",
    # Middleware
    "require_permission",
    "require_any_permission",
    "require_all_permissions",
    "check_permission",
    # Services
    "PermissionService",
    "get_permission_service",
    "RoleService",
    "get_role_service",
    "PermissionRegistry",
    "is_permission_registered",
    "initialize_permissions",
    # Models
    "PermissionCreate",
    "PermissionUpdate",
    "PermissionResponse",
    "RoleCreate",
    "RoleUpdate",
    "RoleResponse",
    "UserPermissionCreate",
    "GrantPermissionToUserRequest",
]
