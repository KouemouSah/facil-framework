"""
Legacy Tax Declaration Repository - Backwards Compatibility

Re-exports from app.modules.declarations.repositories.declaration_repository
"""

from app.modules.declarations.repositories.declaration_repository import DeclarationRepository

# Create singleton instance for backwards compatibility
# Note: The module uses DeclarationRepository, aliased here as tax_declaration_repository
tax_declaration_repository = DeclarationRepository()

__all__ = ["DeclarationRepository", "tax_declaration_repository"]
