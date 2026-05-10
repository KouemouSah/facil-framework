"""
Permissions API - Exports all permission-related routers
"""

from .permission_routes import router as permission_router
from .role_routes import router as role_router
from .user_permission_routes import router as user_permission_router

__all__ = [
    "permission_router",
    "role_router",
    "user_permission_router",
]
