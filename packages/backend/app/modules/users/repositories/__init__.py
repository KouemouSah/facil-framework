"""
User Repositories for TaxasGE Backend
Database access layer for user operations

Uses lazy imports to avoid import-time errors.
"""

__all__ = [
    "UserRepository",
]

# Lazy import mechanism
_cache = {}


def __getattr__(name: str):
    """Lazy import mechanism for user repositories"""
    if name in _cache:
        return _cache[name]

    if name == "UserRepository":
        from app.modules.users.repositories.user_repository import UserRepository
        _cache[name] = UserRepository
        return UserRepository

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
