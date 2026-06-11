"""
Template-Based Extractor for TaxasGE Documents
Extracts structured data from OCR text using template configurations

Author: Claude Code
Date: 2025-12-06
Version: 1.0.0
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import re
from loguru import logger

from app.modules.documents.extractors.base import BaseExtractor, ExtractionResult
from app.modules.documents.extractors.template_loader import DocumentTemplate


class TemplateBasedExtractor(BaseExtractor):
    """
    Template-based document extractor

    Uses DocumentTemplate configuration to extract structured data
    from OCR text based on field definitions and patterns.
    """

    def __init__(self, template: DocumentTemplate):
        """
        Initialize extractor with a document template

        Args:
            template: DocumentTemplate configuration for extraction
        """
        self.template = template
        super().__init__()

    def _initialize_patterns(self) -> Dict[str, List[str]]:
        """
        Initialize extraction patterns from template fields

        Returns:
            Dict mapping field names to list of regex patterns
        """
        patterns = {}

        if self.template and self.template.fields:
            for field in self.template.fields:
                field_name = field.name
                # Create patterns based on field type and label
                patterns[field_name] = self._create_patterns_for_field(field)

        return patterns

    def _create_patterns_for_field(self, field) -> List[str]:
        """
        Create regex patterns for a field configuration

        Args:
            field: FieldConfig object

        Returns:
            List of regex patterns
        """
        patterns = []

        # Basic pattern based on field label
        if hasattr(field, 'label') and field.label:
            label = re.escape(field.label)
            patterns.append(f"{label}[:\\s]*([\\w\\s\\d.,/-]+)")

        # Type-specific patterns
        if hasattr(field, 'type'):
            if field.type == 'date':
                patterns.extend([
                    r'(\d{2}[/.-]\d{2}[/.-]\d{4})',
                    r'(\d{4}[/.-]\d{2}[/.-]\d{2})'
                ])
            elif field.type == 'number' or field.type == 'currency':
                patterns.extend([
                    r'(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)',
                    r'([€$]?\s*\d+(?:[.,]\d+)?)'
                ])
            elif field.type == 'nif' or field.type == 'tax_id':
                patterns.extend([
                    r'NIF[:\s]*([A-Z0-9]+)',
                    r'([A-Z]\d{8})',
                    r'(\d{8}[A-Z])'
                ])

        return patterns

    async def extract(
        self,
        ocr_text: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ExtractionResult:
        """
        Extract structured data from OCR text using template

        Args:
            ocr_text: OCR extracted text
            metadata: Optional metadata (confidence, provider, etc.)

        Returns:
            ExtractionResult with extracted data and confidence scores
        """
        start_time = datetime.now()

        extracted_data = {}
        field_confidences = {}
        errors = []
        warnings = []

        # Preprocess text
        processed_text = self._preprocess_text(ocr_text)

        # Extract each field defined in template
        if self.template and self.template.fields:
            required_fields = []

            for field in self.template.fields:
                field_name = field.name
                is_required = getattr(field, 'required', False)

                if is_required:
                    required_fields.append(field_name)

                # Get patterns for this field
                patterns = self.patterns.get(field_name, [])

                if patterns:
                    value, confidence = await self._extract_field(
                        processed_text,
                        field_name,
                        patterns,
                        required=is_required
                    )

                    if value:
                        extracted_data[field_name] = value
                        field_confidences[field_name] = confidence
                    elif is_required:
                        warnings.append(f"Required field '{field_name}' not found")

            # Calculate overall confidence
            overall_confidence = self._calculate_overall_confidence(
                field_confidences,
                required_fields
            )
        else:
            overall_confidence = 0.0
            warnings.append("No template fields defined")

        # Calculate processing time
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)

        return ExtractionResult(
            success=len(extracted_data) > 0,
            data=extracted_data,
            confidence=overall_confidence,
            field_confidences=field_confidences,
            processing_time_ms=processing_time,
            errors=errors,
            warnings=warnings,
            metadata={
                "template_id": self.template.id if self.template else None,
                "template_name": self.template.name if self.template else None,
                "fields_extracted": len(extracted_data),
                "fields_total": len(self.template.fields) if self.template and self.template.fields else 0,
                **(metadata or {})
            }
        )


class DeclarationDatabaseMapper:
    """
    Maps extracted declaration data to database format

    Transforms raw extracted fields to the format expected
    by the tax_declarations table schema.
    """

    def __init__(self, template: DocumentTemplate):
        """
        Initialize mapper with document template

        Args:
            template: DocumentTemplate configuration for field mapping
        """
        self.template = template
        self.field_mappings = self._build_field_mappings()

    def _build_field_mappings(self) -> Dict[str, str]:
        """
        Build mappings from extracted field names to database columns

        Returns:
            Dict mapping extraction field names to DB column names
        """
        mappings = {}

        if self.template and self.template.fields:
            for field in self.template.fields:
                # Use db_column if specified, otherwise use field name in snake_case
                db_column = getattr(field, 'db_column', None)
                if db_column:
                    mappings[field.name] = db_column
                else:
                    # Convert to snake_case
                    mappings[field.name] = self._to_snake_case(field.name)

        return mappings

    def _to_snake_case(self, name: str) -> str:
        """Convert CamelCase to snake_case"""
        import re
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

    def map_to_database(
        self,
        extracted_data: Dict[str, Any],
        user_id: str,
        declaration_type: str
    ) -> Dict[str, Any]:
        """
        Map extracted data to database format

        Args:
            extracted_data: Raw extracted field values
            user_id: User ID for the declaration
            declaration_type: Type of tax declaration

        Returns:
            Dict with data formatted for database insertion
        """
        db_data = {
            "user_id": user_id,
            "declaration_type": declaration_type,
            "status": "draft",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }

        # Map extracted fields
        for field_name, value in extracted_data.items():
            db_column = self.field_mappings.get(field_name, field_name)
            db_data[db_column] = self._transform_value(field_name, value)

        return db_data

    def _transform_value(self, field_name: str, value: Any) -> Any:
        """
        Transform extracted value to appropriate database type

        Args:
            field_name: Name of the field
            value: Extracted value

        Returns:
            Transformed value
        """
        if value is None:
            return None

        # Find field config
        field_config = None
        if self.template and self.template.fields:
            for field in self.template.fields:
                if field.name == field_name:
                    field_config = field
                    break

        if not field_config:
            return value

        field_type = getattr(field_config, 'type', 'text')

        # Transform based on type
        if field_type in ('number', 'currency', 'decimal'):
            return self._parse_number(value)
        elif field_type == 'date':
            return self._parse_date(value)
        elif field_type == 'boolean':
            return self._parse_boolean(value)
        else:
            return str(value) if value else None

    def _parse_number(self, value: Any) -> Optional[float]:
        """Parse string to number"""
        try:
            if isinstance(value, (int, float)):
                return float(value)
            # Remove currency symbols and normalize
            cleaned = str(value).replace('€', '').replace('$', '').strip()
            cleaned = cleaned.replace(' ', '')
            # Handle European format (1.234,56) vs American (1,234.56)
            if ',' in cleaned and '.' in cleaned:
                if cleaned.rindex(',') > cleaned.rindex('.'):
                    cleaned = cleaned.replace('.', '').replace(',', '.')
                else:
                    cleaned = cleaned.replace(',', '')
            elif ',' in cleaned:
                cleaned = cleaned.replace(',', '.')
            return float(cleaned)
        except (ValueError, TypeError):
            return None

    def _parse_date(self, value: Any) -> Optional[str]:
        """Parse string to ISO date format"""
        if isinstance(value, datetime):
            return value.date().isoformat()

        date_formats = [
            '%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d',
            '%d.%m.%Y', '%Y/%m/%d'
        ]

        for fmt in date_formats:
            try:
                dt = datetime.strptime(str(value), fmt)
                return dt.date().isoformat()
            except ValueError:
                continue

        return str(value) if value else None

    def _parse_boolean(self, value: Any) -> bool:
        """Parse string to boolean"""
        if isinstance(value, bool):
            return value
        str_value = str(value).lower().strip()
        return str_value in ('true', '1', 'yes', 'si', 'sí', 'oui', 'x')
