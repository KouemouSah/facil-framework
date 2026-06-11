"""
Auth middleware for TaxasGE Backend
Request authentication and authorization

Uses lazy imports to avoid circular dependency issues during module loading.
"""

__all__ = [
    "get_current_user",
    "get_current_active_user",
    "get_current_admin_user",
]

# Lazy import mechanism to avoid import-time errors
_cache = {}


def __getattr__(name: str):
    """
    Lazy import mechanism for auth middleware dependencies.
    Avoids import-time errors that can cause the entire auth module to fail.
    """
    if name in _cache:
        return _cache[name]

    if name in __all__:
        from app.modules.auth.middleware import auth_middleware
        attr = getattr(auth_middleware, name)
        _cache[name] = attr
        return attr

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
