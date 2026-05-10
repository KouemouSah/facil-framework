"""
🧠 TaxasGE Data Extraction Service
Intelligent structured data extraction from OCR text
Specialized for tax documents and identification papers

Author: KOUEMOU SAH Jean Emac
Date: 27 septembre 2025
Version: 1.0.0
"""

import re
import json
from typing import Dict, List, Optional, Any, Tuple, Union
from datetime import datetime, date
from dataclasses import dataclass
from enum import Enum

from loguru import logger
from pydantic import BaseModel, Field


# ============================================================================
# MODELS & TYPES
# ============================================================================

class ExtractionResult(BaseModel):
    """Data extraction result"""
    success: bool = Field(..., description="Extraction success status")
    data: Dict[str, Any] = Field(default_factory=dict, description="Extracted structured data")
    confidence: float = Field(default=0.0, description="Overall extraction confidence (0-1)")
    field_confidences: Dict[str, float] = Field(default_factory=dict, description="Per-field confidence scores")
    processing_time_ms: int = Field(default=0, description="Processing time in milliseconds")
    errors: List[str] = Field(default_factory=list, description="Extraction errors")
    warnings: List[str] = Field(default_factory=list, description="Extraction warnings")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class DocumentType(str, Enum):
    """
    Supported document types for extraction

    Note: For tax declaration forms (IVA, IRPF, etc.), use TemplateBasedExtractor
    from app.core.documents.extractors instead of this service.
    This service is optimized for general documents only.
    """
    PASSPORT = "passport"
    NIF_CARD = "nif_card"
    RESIDENCE_PERMIT = "residence_permit"
    BIRTH_CERTIFICATE = "birth_certificate"
    BANK_STATEMENT = "bank_statement"
    INVOICE = "invoice"
    RECEIPT = "receipt"
    CONTRACT = "contract"
    GENERAL = "general"


@dataclass
class ExtractionPattern:
    """Pattern for field extraction"""
    field_name: str
    patterns: List[str]
    required: bool = False
    data_type: str = "string"  # string, date, number, currency
    validation_func: Optional[callable] = None
    confidence_boost: float = 0.0


# ============================================================================
# EXTRACTION SERVICE
# ============================================================================

class ExtractionService:
    """
    Intelligent data extraction service for TaxasGE

    Features:
    - Document type-specific extraction patterns
    - Smart field recognition with fuzzy matching
    - Date and number parsing with validation
    - Confidence scoring for extracted data
    - Multi-language support (Spanish, French, English)
    - Context-aware field extraction
    """

    def __init__(self):
        self._patterns = self._initialize_extraction_patterns()
        self._validators = self._initialize_validators()

    def _initialize_extraction_patterns(self) -> Dict[str, List[ExtractionPattern]]:
        """Initialize extraction patterns for different document types"""
        patterns = {
            DocumentType.PASSPORT: [
                ExtractionPattern(
                    "passport_number",
                    [
                        r"(?:passport|pasaporte|passeport)\s*(?:no|n°|number|número|numéro)?\s*:?\s*([A-Z0-9]{6,12})",
                        r"[A-Z]{2}\d{7}",  # Standard passport format
                        r"P\d{8}",  # P followed by 8 digits
                        r"(?:^|\s)([A-Z]{2}\d{6,8})(?:\s|$)"
                    ],
                    required=True,
                    confidence_boost=0.8
                ),
                ExtractionPattern(
                    "full_name",
                    [
                        r"(?:name|nombre|nom)\s*:?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)",
                        r"(?:surname|apellido|nom de famille)\s*:?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
                        r"^([A-Z][A-Z\s]+)$"  # All caps name line
                    ],
                    required=True,
                    data_type="string",
                    confidence_boost=0.7
                ),
                ExtractionPattern(
                    "date_of_birth",
                    [
                        r"(?:date of birth|fecha de nacimiento|date de naissance)\s*:?\s*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})",
                        r"(?:born|nacido|né)\s*:?\s*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})",
                        r"DOB\s*:?\s*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})"
                    ],
                    required=True,
                    data_type="date",
                    confidence_boost=0.9
                ),
                ExtractionPattern(
                    "nationality",
                    [
                        r"(?:nationality|nacionalidad|nationalité)\s*:?\s*([A-Z][a-z]+)",
                        r"(?:citizen of|ciudadano de|citoyen de)\s*([A-Z][a-z]+)",
                        r"(?:^|\s)(SPANISH|FRENCH|AMERICAN|BRITISH|GERMAN|ITALIAN|PORTUGUESE|EQUATORIAL GUINEAN)(?:\s|$)"
                    ],
                    required=False,
                    confidence_boost=0.6
                ),
                ExtractionPattern(
                    "expiry_date",
                    [
                        r"(?:expiry|expires|vence|expire)\s*(?:date)?\s*:?\s*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})",
                        r"(?:valid until|válido hasta|valable jusqu'au)\s*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})"
                    ],
                    data_type="date",
                    confidence_boost=0.8
                ),
                ExtractionPattern(
                    "place_of_birth",
                    [
                        r"(?:place of birth|lugar de nacimiento|lieu de naissance)\s*:?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
                        r"(?:born in|nacido en|né à)\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)"
                    ],
                    confidence_boost=0.5
                )
            ],

            DocumentType.NIF_CARD: [
                ExtractionPattern(
                    "nif_number",
                    [
                        r"(?:NIF|nif)\s*(?:no|n°|number|número)?\s*:?\s*(\d{8,12}[A-Z]?)",
                        r"(?:^|\s)(\d{8}[A-Z])(?:\s|$)",  # 8 digits + letter
                        r"(?:tax id|identificación fiscal)\s*:?\s*(\d{8,12}[A-Z]?)"
                    ],
                    required=True,
                    confidence_boost=0.9
                ),
                ExtractionPattern(
                    "full_name",
                    [
                        r"(?:name|nombre|nom)\s*:?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)",
                        r"^([A-Z][A-Z\s]+)$"
                    ],
                    required=True,
                    confidence_boost=0.7
                ),
                ExtractionPattern(
                    "date_of_birth",
                    [
                        r"(?:date of birth|fecha de nacimiento|date de naissance)\s*:?\s*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})",
                        r"DOB\s*:?\s*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})"
                    ],
                    required=True,
                    data_type="date",
                    confidence_boost=0.8
                ),
                ExtractionPattern(
                    "address",
                    [
                        r"(?:address|dirección|adresse)\s*:?\s*([A-Z0-9][a-z0-9\s,.-]+)",
                        r"(?:street|calle|rue)\s*:?\s*([A-Z0-9][a-z0-9\s,.-]+)"
                    ],
                    confidence_boost=0.5
                )
            ],

            DocumentType.INVOICE: [
                ExtractionPattern(
                    "invoice_number",
                    [
                        r"(?:invoice|factura|facture)\s*(?:no|n°|number|número)?\s*:?\s*([A-Z0-9\-]+)",
                        r"(?:^|\s)(INV-\d+|FAC-\d+|\d{4,10})(?:\s|$)"
                    ],
                    required=True,
                    confidence_boost=0.8
                ),
                ExtractionPattern(
                    "total_amount",
                    [
                        r"(?:total|total amount|importe total|montant total)\s*:?\s*([€$£]?\s*\d+[.,]\d{2})",
                        r"(?:^|\s)([€$£]\s*\d+[.,]\d{2})(?:\s|$)",
                        r"(?:FCFA|XAF)\s*(\d+[.,]\d{2}|\d+)"
                    ],
                    required=True,
                    data_type="currency",
                    confidence_boost=0.9
                ),
                ExtractionPattern(
                    "invoice_date",
                    [
                        r"(?:date|fecha|date)\s*:?\s*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})",
                        r"(?:issued|emitido|émis)\s*(?:on)?\s*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})"
                    ],
                    required=True,
                    data_type="date",
                    confidence_boost=0.7
                ),
                ExtractionPattern(
                    "vendor_name",
                    [
                        r"(?:from|de|vendor|proveedor|vendeur)\s*:?\s*([A-Z][a-z\s&.,]+)",
                        r"^([A-Z][A-Z\s&.,]+)$"  # All caps vendor name
                    ],
                    confidence_boost=0.6
                ),
                ExtractionPattern(
                    "tax_amount",
                    [
                        r"(?:tax|IVA|TVA|impuesto|taxe)\s*:?\s*([€$£]?\s*\d+[.,]\d{2})",
                        r"(?:VAT|IVA|TVA)\s*\(\d+%\)\s*([€$£]?\s*\d+[.,]\d{2})"
                    ],
                    data_type="currency",
                    confidence_boost=0.8
                )
            ]
        }

        return patterns

    def _initialize_validators(self) -> Dict[str, callable]:
        """Initialize field validators"""
        return {
            "passport_number": self._validate_passport_number,
            "nif_number": self._validate_nif_number,
            "date_of_birth": self._validate_date,
            "expiry_date": self._validate_date,
            "invoice_date": self._validate_date,
            "total_amount": self._validate_currency,
            "tax_amount": self._validate_currency
        }

    async def extract_structured_data(
        self,
        text: str,
        document_type: str,
        document_subtype: Optional[str] = None
    ) -> ExtractionResult:
        """
        Extract structured data from OCR text

        Args:
            text: OCR extracted text
            document_type: Type of document
            document_subtype: Document subtype for specialized extraction

        Returns:
            ExtractionResult with extracted structured data
        """
        start_time = datetime.now()

        try:
            logger.info(f"Starting data extraction for document type: {document_type}")

            # Get extraction patterns for document type
            doc_type = DocumentType(document_type) if document_type in DocumentType.__members__.values() else DocumentType.GENERAL
            patterns = self._patterns.get(doc_type, [])

            if not patterns:
                logger.warning(f"No extraction patterns found for document type: {document_type}")
                return ExtractionResult(
                    success=False,
                    errors=[f"Unsupported document type: {document_type}"]
                )

            # Preprocess text
            processed_text = self._preprocess_text(text)

            # Extract fields
            extracted_data = {}
            field_confidences = {}
            errors = []
            warnings = []

            for pattern in patterns:
                try:
                    value, confidence = await self._extract_field(processed_text, pattern)
                    if value:
                        extracted_data[pattern.field_name] = value
                        field_confidences[pattern.field_name] = confidence

                        logger.debug(f"Extracted {pattern.field_name}: {value} (confidence: {confidence:.3f})")
                    elif pattern.required:
                        errors.append(f"Required field '{pattern.field_name}' not found")

                except Exception as e:
                    logger.error(f"Error extracting {pattern.field_name}: {e}")
                    if pattern.required:
                        errors.append(f"Failed to extract required field '{pattern.field_name}': {str(e)}")

            # Validate extracted data
            validation_results = await self._validate_extracted_data(extracted_data, document_type)
            errors.extend(validation_results.get("errors", []))
            warnings.extend(validation_results.get("warnings", []))

            # Update confidences based on validation
            for field, is_valid in validation_results.get("field_validations", {}).items():
                if field in field_confidences and not is_valid:
                    field_confidences[field] *= 0.5  # Reduce confidence for invalid fields

            # Calculate overall confidence
            overall_confidence = self._calculate_overall_confidence(field_confidences, patterns)

            # Calculate processing time
            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            result = ExtractionResult(
                success=len(extracted_data) > 0 and len(errors) == 0,
                data=extracted_data,
                confidence=overall_confidence,
                field_confidences=field_confidences,
                processing_time_ms=int(processing_time),
                errors=errors,
                warnings=warnings,
                metadata={
                    "document_type": document_type,
                    "document_subtype": document_subtype,
                    "text_length": len(text),
                    "patterns_matched": len(extracted_data)
                }
            )

            logger.info(f"Data extraction completed in {processing_time:.2f}ms with confidence {overall_confidence:.3f}")
            return result

        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            logger.error(f"Data extraction failed: {e}")
            return ExtractionResult(
                success=False,
                processing_time_ms=int(processing_time),
                errors=[str(e)]
            )

    def _preprocess_text(self, text: str) -> str:
        """Preprocess OCR text for better extraction"""
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)

        # Fix common OCR errors
        text = text.replace('|', 'I')
        text = text.replace('0', 'O')  # In names, 0 is often O

        # Normalize line breaks
        text = text.replace('\n', ' ')

        return text.strip()

    async def _extract_field(self, text: str, pattern: ExtractionPattern) -> Tuple[Optional[str], float]:
        """Extract a specific field using pattern matching"""
        best_match = None
        best_confidence = 0.0

        for regex_pattern in pattern.patterns:
            try:
                matches = re.finditer(regex_pattern, text, re.IGNORECASE | re.MULTILINE)

                for match in matches:
                    value = match.group(1) if match.groups() else match.group(0)
                    value = value.strip()

                    if not value:
                        continue

                    # Calculate confidence based on pattern specificity and context
                    confidence = self._calculate_field_confidence(value, pattern, text, match)

                    if confidence > best_confidence:
                        best_match = value
                        best_confidence = confidence

            except re.error as e:
                logger.warning(f"Invalid regex pattern for {pattern.field_name}: {regex_pattern} - {e}")
                continue

        # Post-process the extracted value
        if best_match:
            best_match = self._post_process_field_value(best_match, pattern)

        return best_match, best_confidence

    def _calculate_field_confidence(self, value: str, pattern: ExtractionPattern, text: str, match: re.Match) -> float:
        """Calculate confidence score for extracted field"""
        confidence = 0.5  # Base confidence

        # Apply pattern-specific confidence boost
        confidence += pattern.confidence_boost

        # Check context around the match
        start_pos = max(0, match.start() - 20)
        end_pos = min(len(text), match.end() + 20)
        context = text[start_pos:end_pos].lower()

        # Boost confidence if field name appears near the value
        field_keywords = pattern.field_name.replace('_', ' ').split()
        for keyword in field_keywords:
            if keyword in context:
                confidence += 0.1

        # Data type specific validation
        if pattern.data_type == "date":
            if self._is_valid_date_format(value):
                confidence += 0.2

        elif pattern.data_type == "currency":
            if self._is_valid_currency_format(value):
                confidence += 0.2

        elif pattern.data_type == "number":
            if value.replace('.', '').replace(',', '').isdigit():
                confidence += 0.1

        # Normalize to 0-1 range
        return min(1.0, max(0.0, confidence))

    def _post_process_field_value(self, value: str, pattern: ExtractionPattern) -> str:
        """Post-process extracted field value based on data type"""
        if pattern.data_type == "date":
            return self._normalize_date(value)

        elif pattern.data_type == "currency":
            return self._normalize_currency(value)

        elif pattern.data_type == "string":
            return self._normalize_string(value)

        return value

    def _normalize_date(self, date_str: str) -> str:
        """Normalize date string to ISO format"""
        try:
            # Try different date formats
            date_formats = [
                "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y",
                "%m/%d/%Y", "%m-%d-%Y", "%m.%d.%Y",
                "%d/%m/%y", "%d-%m-%y", "%d.%m.%y",
                "%Y-%m-%d", "%Y/%m/%d"
            ]

            for fmt in date_formats:
                try:
                    parsed_date = datetime.strptime(date_str, fmt)
                    return parsed_date.strftime("%Y-%m-%d")
                except ValueError:
                    continue

            # If no format matches, return original
            return date_str

        except Exception:
            return date_str

    def _normalize_currency(self, currency_str: str) -> str:
        """Normalize currency string"""
        # Remove currency symbols and normalize decimal separator
        cleaned = re.sub(r'[€$£]', '', currency_str)
        cleaned = re.sub(r'\s+', '', cleaned)
        cleaned = cleaned.replace(',', '.')

        return cleaned

    def _normalize_string(self, text: str) -> str:
        """Normalize string field"""
        # Title case for names
        return ' '.join(word.capitalize() for word in text.split())

    async def _validate_extracted_data(self, data: Dict[str, Any], document_type: str) -> Dict[str, Any]:
        """Validate extracted data"""
        errors = []
        warnings = []
        field_validations = {}

        for field_name, value in data.items():
            validator = self._validators.get(field_name)
            if validator:
                try:
                    is_valid, message = validator(value)
                    field_validations[field_name] = is_valid
                    if not is_valid:
                        warnings.append(f"Invalid {field_name}: {message}")
                except Exception as e:
                    warnings.append(f"Validation error for {field_name}: {str(e)}")

        # Document-specific validations
        if document_type == DocumentType.PASSPORT:
            if "date_of_birth" in data and "expiry_date" in data:
                try:
                    birth_date = datetime.strptime(data["date_of_birth"], "%Y-%m-%d")
                    expiry_date = datetime.strptime(data["expiry_date"], "%Y-%m-%d")
                    if expiry_date <= birth_date:
                        errors.append("Expiry date cannot be before birth date")
                except ValueError:
                    pass  # Date format issues already caught in field validation

        return {
            "errors": errors,
            "warnings": warnings,
            "field_validations": field_validations
        }

    def _calculate_overall_confidence(self, field_confidences: Dict[str, float], patterns: List[ExtractionPattern]) -> float:
        """Calculate overall extraction confidence"""
        if not field_confidences:
            return 0.0

        # Weight required fields more heavily
        weighted_sum = 0.0
        total_weight = 0.0

        for pattern in patterns:
            if pattern.field_name in field_confidences:
                weight = 2.0 if pattern.required else 1.0
                weighted_sum += field_confidences[pattern.field_name] * weight
                total_weight += weight

        if total_weight == 0:
            return 0.0

        return weighted_sum / total_weight

    # Validator functions
    def _validate_passport_number(self, value: str) -> Tuple[bool, str]:
        """Validate passport number format"""
        if not value:
            return False, "Empty value"

        # Check length
        if len(value) < 6 or len(value) > 12:
            return False, "Invalid length"

        # Check format (letters and numbers only)
        if not re.match(r'^[A-Z0-9]+$', value.upper()):
            return False, "Invalid characters"

        return True, "Valid"

    def _validate_nif_number(self, value: str) -> Tuple[bool, str]:
        """Validate NIF number format"""
        if not value:
            return False, "Empty value"

        # Spanish NIF format: 8 digits + letter
        if re.match(r'^\d{8}[A-Z]$', value.upper()):
            return True, "Valid"

        # Numeric NIF
        if re.match(r'^\d{8,12}$', value):
            return True, "Valid"

        return False, "Invalid NIF format"

    def _validate_date(self, value: str) -> Tuple[bool, str]:
        """Validate date format and value"""
        if not value:
            return False, "Empty value"

        try:
            # Try to parse as ISO date
            parsed_date = datetime.strptime(value, "%Y-%m-%d")

            # Check reasonable date range
            if parsed_date.year < 1900 or parsed_date.year > datetime.now().year + 50:
                return False, "Date out of reasonable range"

            return True, "Valid"

        except ValueError:
            return False, "Invalid date format"

    def _validate_currency(self, value: str) -> Tuple[bool, str]:
        """Validate currency format"""
        if not value:
            return False, "Empty value"

        try:
            # Remove any non-digit/decimal characters and parse
            cleaned = re.sub(r'[^\d.]', '', value)
            amount = float(cleaned)

            if amount < 0:
                return False, "Negative amount"

            return True, "Valid"

        except ValueError:
            return False, "Invalid currency format"

    def _is_valid_date_format(self, date_str: str) -> bool:
        """Check if string matches a valid date format"""
        date_patterns = [
            r'\d{1,2}/\d{1,2}/\d{2,4}',
            r'\d{1,2}-\d{1,2}-\d{2,4}',
            r'\d{1,2}\.\d{1,2}\.\d{2,4}',
            r'\d{4}-\d{2}-\d{2}'
        ]

        return any(re.match(pattern, date_str) for pattern in date_patterns)

    def _is_valid_currency_format(self, currency_str: str) -> bool:
        """Check if string matches a valid currency format"""
        currency_patterns = [
            r'[€$£]?\s*\d+[.,]\d{2}',
            r'\d+[.,]\d{2}\s*[€$£]?',
            r'FCFA\s*\d+',
            r'\d+\s*FCFA'
        ]

        return any(re.search(pattern, currency_str) for pattern in currency_patterns)


# ============================================================================
# SERVICE INSTANCE
# ============================================================================

# Global service instance
extraction_service = ExtractionService()


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

async def extract_document_data(
    text: str,
    document_type: str,
    document_subtype: Optional[str] = None
) -> ExtractionResult:
    """Helper function for document data extraction"""
    return await extraction_service.extract_structured_data(
        text=text,
        document_type=document_type,
        document_subtype=document_subtype
    )


def get_supported_document_types() -> List[Dict[str, Any]]:
    """Get list of supported document types for extraction"""
    return [
        {
            "type": doc_type.value,
            "name": doc_type.value.replace('_', ' ').title(),
            "description": _get_document_description(doc_type),
            "required_fields": _get_required_fields(doc_type),
            "optional_fields": _get_optional_fields(doc_type)
        }
        for doc_type in DocumentType
    ]


def _get_document_description(doc_type: DocumentType) -> str:
    """Get description for document type"""
    descriptions = {
        DocumentType.PASSPORT: "International travel document with personal identification",
        DocumentType.NIF_CARD: "Tax identification number card",
        DocumentType.RESIDENCE_PERMIT: "Official residence authorization document",
        DocumentType.BIRTH_CERTIFICATE: "Official birth registration document",
        DocumentType.BANK_STATEMENT: "Financial account statement",
        DocumentType.INVOICE: "Commercial transaction invoice",
        DocumentType.RECEIPT: "Payment receipt or proof of purchase",
        DocumentType.CONTRACT: "Legal agreement document",
        DocumentType.GENERAL: "General document with basic text extraction"
    }
    return descriptions.get(doc_type, "Document for data extraction")


def _get_required_fields(doc_type: DocumentType) -> List[str]:
    """Get required fields for document type"""
    required_fields = {
        DocumentType.PASSPORT: ["passport_number", "full_name", "date_of_birth"],
        DocumentType.NIF_CARD: ["nif_number", "full_name", "date_of_birth"],
        DocumentType.INVOICE: ["invoice_number", "total_amount", "invoice_date"],
        DocumentType.RECEIPT: ["total_amount"]
    }
    return required_fields.get(doc_type, [])


def _get_optional_fields(doc_type: DocumentType) -> List[str]:
    """Get optional fields for document type"""
    optional_fields = {
        DocumentType.PASSPORT: ["nationality", "expiry_date", "place_of_birth"],
        DocumentType.NIF_CARD: ["address"],
        DocumentType.INVOICE: ["vendor_name", "tax_amount"],
        DocumentType.RECEIPT: ["vendor_name", "purchase_date"]
    }
    return optional_fields.get(doc_type, [])