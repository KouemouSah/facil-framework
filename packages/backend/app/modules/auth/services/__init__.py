"""
Auth services for TaxasGE Backend
Business logic for authentication operations

Uses lazy imports to avoid import-time errors that can cause the entire auth module to fail.
"""

__all__ = [
    "AuthService",
    "get_auth_service",
    "JWTService",
    "get_jwt_service",
    "SessionService",
    "get_session_service",
    "PasswordService",
    "get_password_service",
    "TwoFactorService",
    "get_two_factor_service",
]

# Lazy import mechanism to avoid import-time errors
_cache = {}

# Map of attribute names to their source modules
_import_map = {
    "AuthService": ("app.modules.auth.services.auth_service", "AuthService"),
    "get_auth_service": ("app.modules.auth.services.auth_service", "get_auth_service"),
    "JWTService": ("app.modules.auth.services.jwt_service", "JWTService"),
    "get_jwt_service": ("app.modules.auth.services.jwt_service", "get_jwt_service"),
    "SessionService": ("app.modules.auth.services.session_service", "SessionService"),
    "get_session_service": ("app.modules.auth.services.session_service", "get_session_service"),
    "PasswordService": ("app.modules.auth.services.password_service", "PasswordService"),
    "get_password_service": ("app.modules.auth.services.password_service", "get_password_service"),
    "TwoFactorService": ("app.modules.auth.services.two_factor_service", "TwoFactorService"),
    "get_two_factor_service": ("app.modules.auth.services.two_factor_service", "get_two_factor_service"),
}


def __getattr__(name: str):
    """
    Lazy import mechanism for auth services.
    Avoids import-time errors that can cause the entire auth module to fail.
    """
    if name in _cache:
        return _cache[name]

    if name in _import_map:
        module_path, attr_name = _import_map[name]
        import importlib
        module = importlib.import_module(module_path)
        attr = getattr(module, attr_name)
        _cache[name] = attr
        return attr

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
