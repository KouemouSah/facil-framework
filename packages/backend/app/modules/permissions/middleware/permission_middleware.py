"""
Permission Middleware - Decorator and Dependency for route permission checking
"""
from functools import wraps
from typing import Callable, Optional, Dict, Any
from fastapi import HTTPException, status, Depends

from app.modules.auth.middleware.auth_middleware import get_current_user
from app.modules.users.models.user import UserResponse
from app.modules.permissions.services.permission_service import PermissionService, get_permission_service


def permission_required(permission_name: str):
    """
    FastAPI dependency factory for permission checking.

    This is the correct way to use permission checks with Depends().

    Usage:
        ```python
        @router.get("/users")
        async def list_users(
            current_user: UserResponse = Depends(get_current_user),
            _: None = Depends(permission_required("user.view_all"))
        ):
            # Route handler code
            ...
        ```

    Args:
        permission_name: Permission name required (e.g., "user.view_all")

    Returns:
        Dependency function that checks permission

    Raises:
        HTTPException: 401 if not authenticated, 403 if permission denied
    """
    async def check_permission_dependency(
        current_user: UserResponse = Depends(get_current_user),
        permission_service: PermissionService = Depends(get_permission_service)
    ) -> None:
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )

        user_id = str(current_user.id) if current_user.id else None
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid user: no ID found"
            )

        # Pass pre-fetched user to avoid redundant DB query in has_permission()
        has_perm = await permission_service.has_permission(user_id, permission_name, user=current_user)

        if not has_perm:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Permission denied: '{permission_name}' required. "
                    f"Contact your administrator to request this permission."
                )
            )

        return None

    return check_permission_dependency


def permission_required_any(*permission_names: str):
    """
    FastAPI dependency factory that requires ANY of the specified permissions.

    User needs at least ONE of the permissions to access the route.

    Usage:
        ```python
        @router.get("/dashboard")
        async def view_dashboard(
            current_user: UserResponse = Depends(get_current_user),
            _: None = Depends(permission_required_any(
                "treasury.validate_payment",
                "treasury_stat.view"
            ))
        ):
            # Route handler code
            ...
        ```

    Args:
        *permission_names: Permission names (at least one required)

    Returns:
        Dependency function that checks permissions

    Raises:
        HTTPException: 401 if not authenticated, 403 if none of the permissions
    """
    async def check_any_permission_dependency(
        current_user: UserResponse = Depends(get_current_user),
        permission_service: PermissionService = Depends(get_permission_service)
    ) -> None:
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )

        user_id = str(current_user.id) if current_user.id else None
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid user: no ID found"
            )

        # Check if user has ANY of the required permissions (pass user to avoid redundant fetch)
        for permission_name in permission_names:
            has_perm = await permission_service.has_permission(user_id, permission_name, user=current_user)
            if has_perm:
                return None  # User has at least one permission

        # User has none of the permissions
        permissions_str = "' or '".join(permission_names)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Permission denied: '{permissions_str}' required. "
                f"Contact your administrator to request this permission."
            )
        )

    return check_any_permission_dependency


def require_permission(permission_name: str, raise_on_deny: bool = True):
    """
    Decorator/Dependency for permission checking.

    Can be used both as a decorator and with Depends().

    Usage as decorator:
        ```python
        @router.get("/users")
        @require_permission("user.view_all")
        async def list_users(
            current_user: UserResponse = Depends(get_current_user),
            permission_service: PermissionService = Depends(get_permission_service)
        ):
            # Route handler code
            ...
        ```

    Usage with Depends():
        ```python
        @router.get("/users")
        async def list_users(
            current_user: UserResponse = Depends(get_current_user),
            _: None = Depends(require_permission("user.view_all"))
        ):
            # Route handler code
            ...
        ```

    Args:
        permission_name: Permission name required (e.g., "user.view_all")
        raise_on_deny: If True, raises 403 exception on permission denied

    Returns:
        Decorator function or dependency function

    Raises:
        HTTPException: 401 if not authenticated, 403 if permission denied
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user: Optional[UserResponse] = kwargs.get('current_user')

            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )

            permission_service: Optional[PermissionService] = kwargs.get('permission_service')

            if not permission_service:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Permission service not available"
                )

            # Pass pre-fetched user to avoid redundant DB query
            has_perm = await permission_service.has_permission(str(current_user.id), permission_name, user=current_user)

            if not has_perm:
                if raise_on_deny:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=(
                            f"Permission denied: '{permission_name}' required. "
                            f"Contact your administrator to request this permission."
                        )
                    )
                else:
                    kwargs['_permission_denied'] = True

            return await func(*args, **kwargs)

        return wrapper
    return decorator


def require_any_permission(*permission_names: str, raise_on_deny: bool = True):
    """
    Decorator to require ANY of the specified permissions

    User needs at least ONE of the permissions to access the route.

    Usage:
        ```python
        @router.get("/dashboard")
        @require_any_permission("dashboard.view", "reports.view_all")
        async def view_dashboard(
            current_user: UserResponse = Depends(get_current_user),
            permission_service: PermissionService = Depends(get_permission_service)
        ):
            # Route handler code
            ...
        ```

    Args:
        *permission_names: Permission names (at least one required)
        raise_on_deny: If True, raises 403 exception on permission denied

    Returns:
        Decorator function

    Raises:
        HTTPException: 403 Forbidden if user doesn't have any of the permissions
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user: Optional[UserResponse] = kwargs.get('current_user')

            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )

            permission_service: Optional[PermissionService] = kwargs.get('permission_service')

            if not permission_service:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Permission service not available"
                )

            # Check if user has ANY of the permissions (pass user to avoid redundant fetch)
            has_any = False
            for perm_name in permission_names:
                if await permission_service.has_permission(str(current_user.id), perm_name, user=current_user):
                    has_any = True
                    break

            if not has_any:
                if raise_on_deny:
                    perms_list = "', '".join(permission_names)
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=(
                            f"Permission denied: At least one of these permissions required: '{perms_list}'. "
                            f"Contact your administrator."
                        )
                    )
                else:
                    kwargs['_permission_denied'] = True

            return await func(*args, **kwargs)

        return wrapper
    return decorator


def require_all_permissions(*permission_names: str, raise_on_deny: bool = True):
    """
    Decorator to require ALL of the specified permissions

    User needs ALL permissions to access the route.

    Usage:
        ```python
        @router.delete("/sensitive-data/{id}")
        @require_all_permissions("data.delete", "data.admin", "audit.create")
        async def delete_sensitive_data(
            id: str,
            current_user: UserResponse = Depends(get_current_user),
            permission_service: PermissionService = Depends(get_permission_service)
        ):
            # Route handler code
            ...
        ```

    Args:
        *permission_names: Permission names (all required)
        raise_on_deny: If True, raises 403 exception on permission denied

    Returns:
        Decorator function

    Raises:
        HTTPException: 403 Forbidden if user doesn't have all permissions
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user: Optional[UserResponse] = kwargs.get('current_user')

            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )

            permission_service: Optional[PermissionService] = kwargs.get('permission_service')

            if not permission_service:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Permission service not available"
                )

            # Check if user has ALL permissions (pass user to avoid redundant fetch)
            missing_permissions = []
            for perm_name in permission_names:
                if not await permission_service.has_permission(str(current_user.id), perm_name, user=current_user):
                    missing_permissions.append(perm_name)

            if missing_permissions:
                if raise_on_deny:
                    perms_list = "', '".join(missing_permissions)
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=(
                            f"Permission denied: Missing required permissions: '{perms_list}'. "
                            f"Contact your administrator."
                        )
                    )
                else:
                    kwargs['_permission_denied'] = True
                    kwargs['_missing_permissions'] = missing_permissions

            return await func(*args, **kwargs)

        return wrapper
    return decorator


# Helper function for checking permissions in route handlers
async def check_permission(
    user_id: str,
    permission_name: str,
    permission_service: PermissionService,
    raise_on_deny: bool = True
) -> bool:
    """
    Helper function to check permission inside a route handler

    Useful for dynamic permission checking (e.g., conditional logic).

    Usage:
        ```python
        @router.put("/{id}/reassign")
        async def reassign_assignment(
            id: str,
            current_user: UserResponse = Depends(get_current_user),
            permission_service: PermissionService = Depends(get_permission_service)
        ):
            # Get assignment
            assignment = await get_assignment(id)

            # Dynamic permission check based on status
            if assignment.status == "in_progress":
                # Requires critical permission
                await check_permission(
                    current_user.id,
                    "assignment.reassign_in_progress",
                    permission_service
                )
            else:
                # Regular permission
                await check_permission(
                    current_user.id,
                    "assignment.reassign",
                    permission_service
                )

            # Proceed with reassignment
            ...
        ```

    Args:
        user_id: User UUID
        permission_name: Permission name
        permission_service: PermissionService instance
        raise_on_deny: If True, raises 403 on deny

    Returns:
        True if has permission

    Raises:
        HTTPException: 403 Forbidden if no permission and raise_on_deny=True
    """
    return await permission_service.check_permission(
        user_id,
        permission_name,
        raise_exception=raise_on_deny
    )
