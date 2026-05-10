"""
Auth Module for TaxasGE Backend
JWT-based authentication with 2FA support and RBAC

Exports authentication dependencies for route protection.
Uses lazy imports via __getattr__ to avoid circular dependency issues.
"""

__all__ = [
    "get_current_user",
    "get_current_active_user",
    "get_current_admin_user",
]

# Cache for lazy-loaded attributes
_cache = {}


def __getattr__(name: str):
    """
    Lazy import mechanism for auth dependencies.
    This avoids import-time errors while maintaining backward compatibility.

    Usage remains the same:
        from app.modules.auth import get_current_user
        @router.get("/protected")
        async def protected_route(user = Depends(get_current_user)):
            ...
    """
    if name in _cache:
        return _cache[name]

    if name in __all__:
        from app.modules.auth.middleware import auth_middleware
        attr = getattr(auth_middleware, name)
        _cache[name] = attr
        return attr

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
