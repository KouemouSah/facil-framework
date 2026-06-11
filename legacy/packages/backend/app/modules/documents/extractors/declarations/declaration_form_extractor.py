"""
Unified Declaration Form Extractor
Handles ALL 13 declaration forms using templates

Author: Claude Code
Date: 2025-11-13
Version: 2.0 - Template-based unified extraction
"""

from typing import Optional, Dict, Any
from loguru import logger

from app.modules.documents.extractors.base import BaseExtractor, ExtractionResult
from app.modules.documents.extractors.template_loader import template_loader
from app.modules.documents.extractors.zone_label_extractor import zone_label_extractor


class DeclarationFormExtractor(BaseExtractor):
    """
    Unified extractor for ALL fiscal declaration forms

    Supported forms (13 total):
    - I.V.A.-DESTAJO
    - 3_RESIDENTES_PETROLERO
    - 5_RESIDENTES_PETROLERO
    - 10_NO-RESIDENTES_PETROLERO
    - 10_NO-RESIDENTES_SEC.COMUN_
    - CUOTA-MIN.FISCAL_PETROLERA
    - CUOTA-MIN.FISCAL_SEC.COMUN_
    - IMP.PROD_.PETROLEROS_IVS
    - IMP.PROD_.PETROLIFEROS_FMI
    - IMP.SUELDOS-Y-SALARIOS_PETROLERO
    - IMP.SUELDOS-Y-SALARIOS_SEC.COMUN_
    - IMPRESO-COMUN
    - IMPRESO-DE-LIQUIDACION

    Usage:
        extractor = DeclarationFormExtractor("iva_destajo")
        result = await extractor.extract(ocr_text)
    """

    def __init__(self, form_type: str):
        """
        Initialize extractor for specific form type

        Args:
            form_type: Template name (e.g., "iva_destajo")
        """
        super().__init__()
        self.form_type = form_type
        self.template = template_loader.load(form_type, "declaration")

        if not self.template:
            raise ValueError(f"Template not found for form type: {form_type}")

        logger.info(f"DeclarationFormExtractor initialized for {form_type}")

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
            logger.info(f"Extracting {self.form_type} form data")

            # Use zone-label extractor with our template
            result = await zone_label_extractor.extract_from_template(
                ocr_text,
                self.template,
                ocr_confidence=metadata.get("ocr_confidence") if metadata else None
            )

            # Add form type to metadata
            result.metadata["form_type"] = self.form_type
            result.metadata["template_version"] = self.template.version

            return result

        except Exception as e:
            logger.error(f"Extraction failed for {self.form_type}: {e}")
            return ExtractionResult(
                success=False,
                errors=[f"Extraction error: {str(e)}"],
                metadata={"form_type": self.form_type}
            )


# Factory function for creating extractors
def create_declaration_extractor(form_type: str) -> DeclarationFormExtractor:
    """
    Factory function to create declaration extractor

    Args:
        form_type: Template name

    Returns:
        DeclarationFormExtractor instance
    """
    return DeclarationFormExtractor(form_type)


# Pre-instantiated common extractors
iva_destajo_extractor = DeclarationFormExtractor("iva_destajo")
