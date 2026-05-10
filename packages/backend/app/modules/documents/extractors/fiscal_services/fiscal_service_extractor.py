"""
Fiscal Service Extractor
Handles fiscal service documents (Nota de Ingreso, etc.)

Author: Claude Code
Date: 2025-11-13
Version: 2.0 - Template-based extraction for fiscal services
"""

from typing import Optional, Dict, Any
from loguru import logger

from app.modules.documents.extractors.base import BaseExtractor, ExtractionResult
from app.modules.documents.extractors.template_loader import template_loader
from app.modules.documents.extractors.zone_label_extractor import zone_label_extractor


class FiscalServiceExtractor(BaseExtractor):
    """
    Extractor for fiscal service documents

    Supported forms:
    - Nota de Ingreso (residence, etc.)
    - Other fiscal services (to be added)

    Usage:
        extractor = FiscalServiceExtractor("nota_ingreso")
        result = await extractor.extract(ocr_text)
    """

    def __init__(self, service_type: str = "nota_ingreso"):
        """
        Initialize extractor for specific service type

        Args:
            service_type: Template name (e.g., "nota_ingreso")
        """
        super().__init__()
        self.service_type = service_type
        self.template = template_loader.load(service_type, "fiscal_service")

        if not self.template:
            raise ValueError(f"Template not found for service type: {service_type}")

        logger.info(f"FiscalServiceExtractor initialized for {service_type}")

    def _initialize_patterns(self) -> Dict[str, Any]:
        """Not used - patterns come from templates"""
        return {}

    async def extract(
        self,
        ocr_text: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ExtractionResult:
        """
        Extract structured data from OCR text using template

        Args:
            ocr_text: OCR extracted text
            metadata: Optional metadata (OCR confidence, provider)

        Returns:
            ExtractionResult with extracted fields
        """
        try:
            logger.info(f"Extracting {self.service_type} service data")

            # Use zone-label extractor with our template
            result = await zone_label_extractor.extract_from_template(
                ocr_text,
                self.template,
                ocr_confidence=metadata.get("ocr_confidence") if metadata else None
            )

            # Add service type to metadata
            result.metadata["service_type"] = self.service_type
            result.metadata["template_version"] = self.template.version

            return result

        except Exception as e:
            logger.error(f"Extraction failed for {self.service_type}: {e}")
            return ExtractionResult(
                success=False,
                errors=[f"Extraction error: {str(e)}"],
                metadata={"service_type": self.service_type}
            )


# Factory function for creating extractors
def create_fiscal_service_extractor(service_type: str) -> FiscalServiceExtractor:
    """
    Factory function to create fiscal service extractor

    Args:
        service_type: Template name

    Returns:
        FiscalServiceExtractor instance
    """
    return FiscalServiceExtractor(service_type)


# Pre-instantiated common extractors
nota_ingreso_extractor = FiscalServiceExtractor("nota_ingreso")
