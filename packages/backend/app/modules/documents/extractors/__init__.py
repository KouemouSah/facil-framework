"""
Document Extractors Module
Template-based extraction system for all document types

Author: Claude Code
Date: 2025-11-13
Version: 2.0 - Unified template-based architecture
"""

from app.modules.documents.extractors.base import BaseExtractor, ExtractionResult
from app.modules.documents.extractors.template_loader import (
    template_loader,
    TemplateLoader,
    DocumentTemplate,
    FieldConfig
)
from app.modules.documents.extractors.zone_label_extractor import (
    zone_label_extractor,
    ZoneLabelExtractor
)
from app.modules.documents.extractors.template_based_extractor import (
    TemplateBasedExtractor,
    DeclarationDatabaseMapper
)

__all__ = [
    "BaseExtractor",
    "ExtractionResult",
    "template_loader",
    "TemplateLoader",
    "DocumentTemplate",
    "FieldConfig",
    "zone_label_extractor",
    "ZoneLabelExtractor",
    "TemplateBasedExtractor",
    "DeclarationDatabaseMapper"
]
