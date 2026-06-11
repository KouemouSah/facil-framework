"""
Legacy Repository Exports - Backwards Compatibility Layer

This module re-exports repositories from their new modular locations
to maintain backwards compatibility with existing imports.

New code should import directly from app.modules.<module>.repositories

Uses lazy imports to avoid import-time errors that can cause module loading failures.
"""

__all__ = [
    "UserRepository",
    "user_repository",
    "get_user_repository",
    "PendingRegistrationRepository",
    "RefreshTokenRepository",
    "FiscalServiceRepository",
    "fiscal_service_repository",
    "get_fiscal_service_repository",
    "DeclarationRepository",
    "tax_declaration_repository",
    "get_declaration_repository",
]

# Lazy import mechanism
_cache = {}

# Lazy-loaded singleton instances
_user_repository_instance = None
_fiscal_service_repository_instance = None
_declaration_repository_instance = None


def get_user_repository():
    """Get UserRepository singleton (lazy-loaded)"""
    global _user_repository_instance
    if _user_repository_instance is None:
        from app.modules.users.repositories.user_repository import UserRepository
        _user_repository_instance = UserRepository()
    return _user_repository_instance


def get_fiscal_service_repository():
    """Get FiscalServiceRepository singleton (lazy-loaded)"""
    global _fiscal_service_repository_instance
    if _fiscal_service_repository_instance is None:
        from app.modules.fiscal_services.repositories.fiscal_service_repository import FiscalServiceRepository
        _fiscal_service_repository_instance = FiscalServiceRepository()
    return _fiscal_service_repository_instance


def get_declaration_repository():
    """Get DeclarationRepository singleton (lazy-loaded)"""
    global _declaration_repository_instance
    if _declaration_repository_instance is None:
        from app.modules.declarations.repositories.declaration_repository import DeclarationRepository
        _declaration_repository_instance = DeclarationRepository()
    return _declaration_repository_instance


# Lazy proxy classes for backwards compatibility with direct attribute access
class _LazyProxy:
    """Lazy proxy that delegates to a getter function"""
    def __init__(self, getter):
        self._getter = getter

    def __getattr__(self, name):
        return getattr(self._getter(), name)


# Lazy singletons for backwards compatibility
user_repository = _LazyProxy(get_user_repository)
fiscal_service_repository = _LazyProxy(get_fiscal_service_repository)
tax_declaration_repository = _LazyProxy(get_declaration_repository)


# Map of class names to their source modules
_import_map = {
    "UserRepository": "app.modules.users.repositories.user_repository",
    "PendingRegistrationRepository": "app.modules.auth.repositories.pending_registration_repository",
    "RefreshTokenRepository": "app.modules.auth.repositories.refresh_token_repository",
    "FiscalServiceRepository": "app.modules.fiscal_services.repositories.fiscal_service_repository",
    "DeclarationRepository": "app.modules.declarations.repositories.declaration_repository",
}


def __getattr__(name: str):
    """Lazy import mechanism for repository classes"""
    if name in _cache:
        return _cache[name]

    if name in _import_map:
        import importlib
        module = importlib.import_module(_import_map[name])
        attr = getattr(module, name)
        _cache[name] = attr
        return attr

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
