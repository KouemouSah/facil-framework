"""
User API Routes

Exports:
- user_routes: User profile and management endpoints
"""

from app.modules.users.api.user_routes import router as user_routes

__all__ = [
    "user_routes",
]
