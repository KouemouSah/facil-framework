"""
Zone-Label Hybrid Extractor
Optimized extraction strategy combining label detection and pattern matching

Author: Claude Code
Date: 2025-11-13
Version: 2.0 - Robust extraction without mandatory homography
"""

import re
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime
from loguru import logger

from app.modules.documents.extractors.template_loader import FieldConfig, DocumentTemplate
from app.modules.documents.extractors.base import ExtractionResult


class ZoneLabelExtractor:
    """
    Hybrid extraction strategy:
    1. Primary: Label detection + value extraction (robust to scan quality)
    2. Fallback: Pattern matching in full text
    3. Last resort: Coordinate-based (if implemented later)

    NO homography required - works with any OCR text
    """

    def __init__(self):
        self.strategies = {
            "label_detection": self._extract_by_label,
            "pattern_matching": self._extract_by_pattern
        }

    async def extract_from_template(
        self,
        ocr_text: str,
        template: DocumentTemplate,
        ocr_confidence: Optional[float] = None
    ) -> ExtractionResult:
        """
        Extract all fields from OCR text using template

        Args:
            ocr_text: Raw OCR text (from Tesseract/Google Vision)
            template: Loaded document template
            ocr_confidence: Optional OCR confidence score

        Returns:
            ExtractionResult with extracted data
        """
        start_time = datetime.now()

        try:
            logger.info(f"Starting extraction for template: {template.name}")

            # Preprocess text
            processed_text = self._preprocess_text(ocr_text)

            extracted_data = {}
            field_confidences = {}
            errors = []
            warnings = []

            # Extract each field
            for field in template.fields:
                try:
                    # Try label detection first (primary strategy)
                    value, confidence = await self._extract_by_label(
                        processed_text,
                        field
                    )

                    # Fallback to pattern matching if label detection failed
                    if value is None and field.pattern:
                        logger.debug(f"Label detection failed for {field.id}, trying pattern matching")
                        value, confidence = await self._extract_by_pattern(
                            processed_text,
                            field
                        )

                    if value:
                        # Post-process value based on type
                        processed_value = self._post_process_value(field, value)
                        extracted_data[field.id] = processed_value
                        field_confidences[field.id] = confidence

                        logger.debug(f"✓ {field.id}: {processed_value} (confidence: {confidence:.2f})")
                    elif field.required:
                        errors.append(f"Required field '{field.id}' not found")
                        logger.warning(f"✗ Required field {field.id} not found")

                except Exception as e:
                    logger.error(f"Error extracting {field.id}: {e}")
                    if field.required:
                        errors.append(f"Failed to extract required field '{field.id}': {str(e)}")

            # Run validations
            validation_errors = self._validate_data(extracted_data, template)
            errors.extend(validation_errors)

            # Calculate overall confidence
            required_fields = [f.id for f in template.fields if f.required]
            overall_confidence = self._calculate_overall_confidence(
                field_confidences,
                required_fields
            )

            # Processing time
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
                    "template_name": template.name,
                    "template_category": template.category,
                    "extractor": "ZoneLabelExtractor",
                    "text_length": len(ocr_text),
                    "fields_extracted": len(extracted_data),
                    "required_fields_found": sum(1 for f in required_fields if f in extracted_data),
                    "total_required": len(required_fields)
                }
            )

            logger.info(
                f"Extraction completed: {len(extracted_data)}/{len(template.fields)} fields "
                f"in {processing_time:.0f}ms (confidence: {overall_confidence:.2f})"
            )

            return result

        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            logger.error(f"Extraction failed: {e}")
            return ExtractionResult(
                success=False,
                processing_time_ms=int(processing_time),
                errors=[f"Extraction error: {str(e)}"]
            )

    async def _extract_by_label(
        self,
        text: str,
        field: FieldConfig
    ) -> Tuple[Optional[str], float]:
        """
        Strategy 1: Extract value by finding label and getting adjacent text

        Most robust strategy - works even with rotated/distorted scans
        """
        # Try each label variant
        for label_text in field.label:
            # Build flexible regex for label
            # Example: "N.I.F." -> "N\.?\s*I\.?\s*F\.?"
            label_pattern = self._build_flexible_label_pattern(label_text)

            # Search for label
            label_match = re.search(label_pattern, text, re.IGNORECASE)

            if label_match:
                # Found label - now extract value based on position_hint
                if field.position_hint == "after_label":
                    # Extract text after label (most common case)
                    remaining_text = text[label_match.end():]
                    value = self._extract_value_after_label(remaining_text, field)

                    if value:
                        confidence = 0.7  # Base confidence for label detection

                        # Boost confidence if pattern matches
                        if field.pattern and re.search(field.pattern, value):
                            confidence += 0.2

                        logger.debug(f"Label detected for {field.id}: '{label_text}' -> '{value}'")
                        return value, confidence

        return None, 0.0

    async def _extract_by_pattern(
        self,
        text: str,
        field: FieldConfig
    ) -> Tuple[Optional[str], float]:
        """
        Strategy 2: Extract value using regex pattern (fallback)

        Less precise but works when labels are missing or OCR is poor
        """
        if not field.pattern:
            return None, 0.0

        # Search for pattern in entire text
        matches = re.finditer(field.pattern, text, re.IGNORECASE)

        best_match = None
        best_confidence = 0.0

        for match in matches:
            value = match.group(1) if match.groups() else match.group(0)
            value = value.strip()

            if not value:
                continue

            # Calculate confidence (lower than label detection)
            confidence = 0.5  # Base confidence for pattern matching

            # Boost if capture group used
            if match.groups():
                confidence += 0.1

            if confidence > best_confidence:
                best_match = value
                best_confidence = confidence

        if best_match:
            logger.debug(f"Pattern match for {field.id}: '{best_match}'")

        return best_match, best_confidence

    def _build_flexible_label_pattern(self, label: str) -> str:
        """
        Build flexible regex pattern for label matching

        Examples:
            "N.I.F." -> "N\.?\s*I\.?\s*F\.?"
            "Base Imponible" -> "Base\s+Imponible"
            "01 Base" -> "0?1\.?\s*Base"
        """
        # Escape special regex chars except dots
        label = re.escape(label)

        # Make dots optional and add optional whitespace
        label = label.replace(r'\.', r'\.?\s*')

        # Make whitespace flexible
        label = re.sub(r'\s+', r'\\s+', label)

        return label

    def _extract_value_after_label(self, text: str, field: FieldConfig) -> Optional[str]:
        """
        Extract value that appears immediately after a label

        Heuristics:
        - Skip whitespace and common separators (:, -)
        - Extract until newline, comma, or next label
        - Apply field type-specific extraction
        """
        # Skip leading whitespace and separators
        text = re.sub(r'^[\s:;\-_]+', '', text)

        # Extract based on field type
        if field.type == "currency":
            # Extract currency pattern: 1.234,56 or 1,234.56 or #102.000 F
            match = re.search(r'#?([0-9.,]+)\s*[A-Z€$£]?', text)
            if match:
                return match.group(1)

        elif field.type == "percentage":
            # Extract percentage: 21% or 21 % or 21,5%
            match = re.search(r'([0-9.,]+)\s*%?', text)
            if match:
                return match.group(1)

        elif field.type == "date":
            # Extract date: DD/MM/YYYY or DD-MM-YYYY
            match = re.search(r'(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})', text)
            if match:
                return match.group(1)

        elif field.type == "year":
            # Extract 4-digit year
            match = re.search(r'(20\d{2})', text)
            if match:
                return match.group(1)

        # Default: extract until newline or 50 chars
        match = re.search(r'^([^\n]{1,50})', text)
        if match:
            value = match.group(1).strip()
            # Remove trailing punctuation
            value = re.sub(r'[,;:\-_]+$', '', value)
            return value if value else None

        return None

    def _post_process_value(self, field: FieldConfig, value: str) -> Any:
        """Post-process extracted value based on field type"""

        if field.type == "currency":
            # Normalize currency
            normalized = self._normalize_currency(value)
            return normalized if normalized is not None else value

        elif field.type == "percentage":
            # Normalize percentage
            normalized = self._normalize_percentage(value)
            return normalized if normalized is not None else value

        elif field.type == "year":
            try:
                return int(value)
            except:
                return value

        # Default: return cleaned string
        return value.strip()

    def _normalize_currency(self, amount_str: str) -> Optional[float]:
        """Normalize currency string to float"""
        try:
            # Remove currency symbols, #, and whitespace
            cleaned = re.sub(r'[#€$£\sFCFA]', '', amount_str)

            # Detect format (European vs American)
            if ',' in cleaned and '.' in cleaned:
                if cleaned.rindex(',') > cleaned.rindex('.'):
                    # European: 1.234,56
                    cleaned = cleaned.replace('.', '').replace(',', '.')
                else:
                    # American: 1,234.56
                    cleaned = cleaned.replace(',', '')
            elif ',' in cleaned:
                # Only comma - check if decimal or thousands
                parts = cleaned.split(',')
                if len(parts[-1]) == 2:
                    # Decimal: 1234,56
                    cleaned = cleaned.replace(',', '.')
                else:
                    # Thousands: 1,234
                    cleaned = cleaned.replace(',', '')

            return float(cleaned)
        except:
            return None

    def _normalize_percentage(self, percent_str: str) -> Optional[float]:
        """Normalize percentage string to float"""
        try:
            cleaned = percent_str.replace('%', '').replace(' ', '').replace(',', '.')
            return float(cleaned)
        except:
            return None

    def _preprocess_text(self, text: str) -> str:
        """Preprocess OCR text"""
        # Remove excessive whitespace but keep line structure
        text = re.sub(r' +', ' ', text)
        return text.strip()

    def _validate_data(
        self,
        data: Dict[str, Any],
        template: DocumentTemplate
    ) -> List[str]:
        """Run template validations on extracted data"""
        errors = []

        for validation in template.validations:
            if validation.type == "format":
                # Format validation
                field_id = validation.data.get("field")
                pattern = validation.data.get("pattern")
                error_msg = validation.data.get("error_message")

                if field_id in data:
                    value = str(data[field_id])
                    if not re.match(pattern, value):
                        errors.append(error_msg or f"Invalid format for {field_id}")

            elif validation.type == "range":
                # Range validation
                field_id = validation.data.get("field")
                min_val = validation.data.get("min")
                max_val = validation.data.get("max")
                error_msg = validation.data.get("error_message")

                if field_id in data:
                    try:
                        value = float(data[field_id])
                        if min_val is not None and value < min_val:
                            errors.append(error_msg or f"{field_id} below minimum")
                        if max_val is not None and value > max_val:
                            errors.append(error_msg or f"{field_id} above maximum")
                    except:
                        pass

            elif validation.type == "calculation":
                # Calculation validation (e.g., cuota = base * tipo / 100)
                # TODO: Implement formula parser
                pass

        return errors

    def _calculate_overall_confidence(
        self,
        field_confidences: Dict[str, float],
        required_fields: List[str]
    ) -> float:
        """Calculate overall extraction confidence"""
        if not field_confidences:
            return 0.0

        # Check required fields
        required_found = sum(1 for f in required_fields if f in field_confidences)
        required_ratio = required_found / len(required_fields) if required_fields else 1.0

        # Average confidence
        avg_confidence = sum(field_confidences.values()) / len(field_confidences)

        # Overall = 50% required fields + 50% average confidence
        return (required_ratio * 0.5) + (avg_confidence * 0.5)


# Singleton instance
zone_label_extractor = ZoneLabelExtractor()
