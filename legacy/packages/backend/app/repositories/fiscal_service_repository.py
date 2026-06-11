"""
Legacy Fiscal Service Repository - Backwards Compatibility

Re-exports from app.modules.fiscal_services.repositories.fiscal_service_repository
"""

from app.modules.fiscal_services.repositories.fiscal_service_repository import FiscalServiceRepository

# Create singleton instance for backwards compatibility
fiscal_service_repository = FiscalServiceRepository()

__all__ = ["FiscalServiceRepository", "fiscal_service_repository"]
