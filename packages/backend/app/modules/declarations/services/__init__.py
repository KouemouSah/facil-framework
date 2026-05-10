"""
Declaration Services
Business logic layer for tax declarations
"""

from app.modules.declarations.services.declaration_service import (
    DeclarationService,
    get_declaration_service,
)

__all__ = [
    "DeclarationService",
    "get_declaration_service",
]
