"""
Legacy User Repository - Backwards Compatibility

This module re-exports UserRepository from its new modular location.
New code should import from app.modules.users.repositories.user_repository

Uses lazy imports to avoid import-time errors that can cause auth module to fail loading.
"""

__all__ = ["UserRepository", "user_repository", "get_user_repository"]

# Lazy-loaded singleton for backwards compatibility
_user_repository_instance = None
_user_repository_class = None


def _get_user_repository_class():
    """Get UserRepository class (lazy-loaded)"""
    global _user_repository_class
    if _user_repository_class is None:
        from app.modules.users.repositories.user_repository import UserRepository as _UserRepository
        _user_repository_class = _UserRepository
    return _user_repository_class


def get_user_repository():
    """Get UserRepository singleton (lazy-loaded)"""
    global _user_repository_instance
    if _user_repository_instance is None:
        UserRepositoryClass = _get_user_repository_class()
        _user_repository_instance = UserRepositoryClass()
    return _user_repository_instance


# For backwards compatibility - property-like access
# Note: Direct access to `user_repository` is deprecated
# Use `get_user_repository()` instead
class _LazyUserRepository:
    """Lazy proxy for backwards compatibility with user_repository singleton"""

    def __getattr__(self, name):
        return getattr(get_user_repository(), name)


user_repository = _LazyUserRepository()


def __getattr__(name: str):
    """Lazy import for UserRepository class"""
    if name == "UserRepository":
        return _get_user_repository_class()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
