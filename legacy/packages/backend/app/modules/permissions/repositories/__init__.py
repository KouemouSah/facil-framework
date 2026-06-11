"""
Permissions Repositories - Exports all repository classes
"""

from .permission_repository import PermissionRepository
from .role_repository import RoleRepository
from .user_permission_repository import UserPermissionRepository

__all__ = [
    "PermissionRepository",
    "RoleRepository",
    "UserPermissionRepository",
]
