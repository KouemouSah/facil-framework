"""
Declarations API routes

Export declaration router for main app registration.
"""

from app.modules.declarations.api.declaration_routes import router as declaration_router

__all__ = ["declaration_router"]
