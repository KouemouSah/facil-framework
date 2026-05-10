"""Admin Module - System Administration and User Management

This module handles all administrative functions including:
- User management (create, update, delete users with roles: accountant, admin, supervisor, dgi_agent, ministry_agent)
- System configuration and rules management
- Audit logs and activity tracking
- System diagnostics and maintenance
- Database migrations

Note: Citizens and business users register through the public registration endpoint.
"""

from app.modules.admin.api.admin_routes import router as admin_router
from app.modules.admin.api.user_management_routes import router as user_management_router

__all__ = ["admin_router", "user_management_router"]
