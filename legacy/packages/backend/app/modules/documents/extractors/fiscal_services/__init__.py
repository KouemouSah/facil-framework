"""
Fiscal Services Extractors
Template-based extraction for fiscal service documents

Author: Claude Code
Date: 2025-11-13
"""

from app.modules.documents.extractors.fiscal_services.fiscal_service_extractor import (
    FiscalServiceExtractor,
    create_fiscal_service_extractor,
    nota_ingreso_extractor
)

__all__ = [
    "FiscalServiceExtractor",
    "create_fiscal_service_extractor",
    "nota_ingreso_extractor"
]
