"""
Admin API routes for TaxasGE Backend
Exports routers for admin endpoints
"""

from app.modules.admin.api.admin_routes import router as admin_router
from app.modules.admin.api.user_management_routes import router as user_management_router
from app.modules.admin.api.monitoring_routes import router as monitoring_router

__all__ = [
    "admin_router",
    "user_management_router",
    "monitoring_router",
]
