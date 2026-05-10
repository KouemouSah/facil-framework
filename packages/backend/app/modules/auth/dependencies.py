"""
Auth Dependencies - Central export for auth-related dependencies.

This module provides a single import point for commonly used auth dependencies:
- get_current_user: Get authenticated user from JWT token
- require_permission: Check single permission
- require_permissions: Check multiple permissions (at least one required)
"""

from app.modules.auth.middleware.auth_middleware import (
    get_current_user,
    get_current_user_optional,
    get_current_admin_user,
)
from app.modules.permissions.middleware.permission_middleware import (
    permission_required,
    require_permission,
    require_any_permission,
    require_all_permissions,
    check_permission,
)

# Alias for backwards compatibility - require_permissions accepts a list
# and requires at least one permission (same as require_any_permission)
def require_permissions(permissions: list[str]):
    """
    Require at least one of the specified permissions.

    This is an alias for permission_required with the first permission,
    but supports a list syntax for compatibility.

    Usage:
        @router.get("/example")
        async def example(
            current_user=Depends(require_permissions(["perm1", "perm2"]))
        ):
            ...

    Args:
        permissions: List of permission names (at least one required)

    Returns:
        Dependency function that checks permissions
    """
    if not permissions:
        raise ValueError("At least one permission must be specified")

    # Use the first permission for single permission check
    # For multiple permissions, the caller should use require_any_permission
    if len(permissions) == 1:
        return permission_required(permissions[0])
    else:
        # For multiple permissions, require all of them
        return require_any_permission(*permissions)


__all__ = [
    # Auth middleware
    "get_current_user",
    "get_current_user_optional",
    "get_current_admin_user",
    # Permission middleware
    "permission_required",
    "require_permission",
    "require_permissions",
    "require_any_permission",
    "require_all_permissions",
    "check_permission",
]
