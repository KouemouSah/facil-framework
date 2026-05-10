"""
Documents API Routes

Exports:
- document_routes: Document management endpoints
"""

from app.modules.documents.api.document_routes import router as document_routes

__all__ = [
    "document_routes",
]
