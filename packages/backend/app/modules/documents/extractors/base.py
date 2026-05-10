"""
Base Extractor for TaxasGE Documents
Abstract interface for all document extractors

Author: Claude Code
Date: 2025-11-13
Version: 2.0 - Reorganized with core/documents/
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
import re
from loguru import logger
from pydantic import BaseModel, Field


class ExtractionResult(BaseModel):
    """Result of document extraction"""
    success: bool = Field(..., description="Extraction success status")
    data: Dict[str, Any] = Field(default_factory=dict, description="Extracted structured data")
    confidence: float = Field(default=0.0, description="Overall extraction confidence (0-1)")
    field_confidences: Dict[str, float] = Field(default_factory=dict, description="Per-field confidence scores")
    processing_time_ms: int = Field(default=0, description="Processing time in milliseconds")
    errors: List[str] = Field(default_factory=list, description="Extraction errors")
    warnings: List[str] = Field(default_factory=list, description="Extraction warnings")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class BaseExtractor(ABC):
    """
    Abstract base class for document extractors

    All specialized extractors must inherit from this class
    and implement the extract() method.
    """

    def __init__(self):
        """Initialize extractor with patterns and validators"""
        self.patterns = self._initialize_patterns()
        self.validators = self._initialize_validators()

    @abstractmethod
    def _initialize_patterns(self) -> Dict[str, List[str]]:
        """
        Initialize extraction patterns for this document type

        Returns:
            Dict mapping field names to list of regex patterns
        """
        pass

    def _initialize_validators(self) -> Dict[str, callable]:
        """
        Initialize field validators (optional override)

        Returns:
            Dict mapping field names to validation functions
        """
        return {}

    @abstractmethod
    async def extract(self, ocr_text: str, metadata: Optional[Dict[str, Any]] = None) -> ExtractionResult:
        """
        Extract structured data from OCR text

        Args:
            ocr_text: OCR extracted text
            metadata: Optional metadata (confidence, provider, etc.)

        Returns:
            ExtractionResult with extracted data and confidence scores
        """
        pass

    def _preprocess_text(self, text: str) -> str:
        """
        Preprocess OCR text for better extraction

        Args:
            text: Raw OCR text

        Returns:
            Preprocessed text
        """
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)

        # Normalize line breaks
        text = text.replace('\n', ' ')

        return text.strip()

    async def _extract_field(
        self,
        text: str,
        field_name: str,
        patterns: List[str],
        required: bool = False
    ) -> Tuple[Optional[str], float]:
        """
        Extract a specific field using pattern matching

        Args:
            text: OCR text to search
            field_name: Name of field to extract
            patterns: List of regex patterns to try
            required: Whether this field is required

        Returns:
            Tuple of (extracted_value, confidence_score)
        """
        best_match = None
        best_confidence = 0.0

        for pattern in patterns:
            try:
                matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)

                for match in matches:
                    value = match.group(1) if match.groups() else match.group(0)
                    value = value.strip()

                    if not value:
                        continue

                    # Calculate confidence (0.5 base + 0.3 for capture group + 0.2 for context)
                    confidence = 0.5
                    if match.groups():
                        confidence += 0.3
                    if len(value) > 3:
                        confidence += 0.2

                    if confidence > best_confidence:
                        best_match = value
                        best_confidence = confidence

            except re.error as e:
                logger.warning(f"Invalid regex pattern for {field_name}: {pattern} - {e}")
                continue

        return best_match, best_confidence

    def _calculate_overall_confidence(
        self,
        field_confidences: Dict[str, float],
        required_fields: List[str]
    ) -> float:
        """
        Calculate overall extraction confidence

        Args:
            field_confidences: Per-field confidence scores
            required_fields: List of required field names

        Returns:
            Overall confidence (0-1)
        """
        if not field_confidences:
            return 0.0

        # Check required fields presence
        required_found = sum(1 for f in required_fields if f in field_confidences)
        required_ratio = required_found / len(required_fields) if required_fields else 1.0

        # Average confidence of extracted fields
        avg_confidence = sum(field_confidences.values()) / len(field_confidences)

        # Overall = 50% required fields + 50% average confidence
        return (required_ratio * 0.5) + (avg_confidence * 0.5)

    def _validate_date(self, date_str: str) -> bool:
        """Validate date string"""
        try:
            # Try common date formats
            for fmt in ['%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d', '%d.%m.%Y']:
                try:
                    datetime.strptime(date_str, fmt)
                    return True
                except ValueError:
                    continue
            return False
        except:
            return False

    def _validate_number(self, number_str: str) -> bool:
        """Validate numeric string"""
        try:
            # Remove currency symbols and whitespace
            cleaned = re.sub(r'[€$£\s]', '', number_str)
            # Replace comma with dot
            cleaned = cleaned.replace(',', '.')
            float(cleaned)
            return True
        except:
            return False

    def _normalize_currency(self, amount_str: str) -> Optional[float]:
        """
        Normalize currency string to float

        Args:
            amount_str: Currency string (e.g., "1.234,56 €", "$1,234.56")

        Returns:
            Float value or None
        """
        try:
            # Remove currency symbols and whitespace
            cleaned = re.sub(r'[€$£\s]', '', amount_str)

            # Detect format (European vs American)
            if ',' in cleaned and '.' in cleaned:
                # Both present - determine which is decimal separator
                if cleaned.rindex(',') > cleaned.rindex('.'):
                    # European format: 1.234,56
                    cleaned = cleaned.replace('.', '').replace(',', '.')
                else:
                    # American format: 1,234.56
                    cleaned = cleaned.replace(',', '')
            elif ',' in cleaned:
                # Only comma - could be decimal or thousands
                if len(cleaned.split(',')[1]) == 2:
                    # Likely decimal: 1234,56
                    cleaned = cleaned.replace(',', '.')
                else:
                    # Likely thousands: 1,234
                    cleaned = cleaned.replace(',', '')

            return float(cleaned)
        except:
            return None

    def _normalize_percentage(self, percent_str: str) -> Optional[float]:
        """
        Normalize percentage string to float

        Args:
            percent_str: Percentage string (e.g., "21%", "21 %", "21,5%")

        Returns:
            Float value (0-100) or None
        """
        try:
            # Remove % symbol and whitespace
            cleaned = percent_str.replace('%', '').replace(' ', '')
            # Replace comma with dot
            cleaned = cleaned.replace(',', '.')
            return float(cleaned)
        except:
            return None
