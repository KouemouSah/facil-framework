"""
Template Loader for Document Extraction
Loads and caches JSON templates from Firebase Storage with local fallback

Author: Claude Code
Date: 2025-11-15
Version: 4.0 - Firebase Storage integration with local fallback (CHECKPOINT 1)
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from loguru import logger

from app.modules.documents.templates import DECLARATIONS_DIR, FISCAL_SERVICES_DIR
from app.modules.documents.services.storage_service import firebase_storage_service


@dataclass
class FieldConfig:
    """Configuration for a single field in the template"""
    id: str
    db_column: Optional[str]
    db_type: Optional[str]
    label: List[str]
    type: str
    campo: Optional[str] = None
    ocr_pattern: Optional[str] = None
    required: bool = False
    calculated: bool = False
    formula: Optional[str] = None
    display_formula: Optional[str] = None
    default_value: Any = None
    validation: Optional[Dict[str, Any]] = None
    comment: Optional[str] = None


@dataclass
class SectionConfig:
    """Configuration for a section in the template"""
    section_id: str
    section_label: str
    section_description: Optional[str]
    db_table: str
    fields: List[FieldConfig]
    comment: Optional[str] = None


@dataclass
class ValidationRule:
    """Validation rule from template"""
    type: str  # calculation, format, range, required_group, array_validation, unique_field
    data: Dict[str, Any]


@dataclass
class OCRStrategy:
    """OCR extraction strategy from template"""
    primary: str  # table_detection, line_by_line_matching, coordinate_based
    fallback: Optional[str] = None
    use_coordinates: bool = False
    preprocessing: Optional[Dict[str, bool]] = None
    table_extraction: Optional[Dict[str, Any]] = None


@dataclass
class BusinessRule:
    """Business rule from template"""
    rule: str
    description: str
    enforcement: str


@dataclass
class DocumentTemplate:
    """Parsed document template"""
    name: str
    code_impuesto: Optional[str]
    category: str
    subtype: Optional[str]
    description: str
    version: str
    official_pdf: Optional[str]
    db_table: str
    db_subtype_field: Optional[str]
    db_subtype_value: Optional[str]
    sections: List[SectionConfig]
    validations: List[ValidationRule]
    ocr_strategy: Optional[OCRStrategy] = None
    business_rules: List[BusinessRule] = None
    comment: Optional[str] = None


class TemplateLoader:
    """
    Loads and caches document templates

    Usage:
        loader = TemplateLoader()
        template = loader.load("iva_destajo")

        # Access sections and fields
        for section in template.sections:
            print(f"Section: {section.section_label}")
            for field in section.fields:
                print(f"  Field {field.id}: {field.label}")
    """

    def __init__(self, use_firebase: bool = True):
        self._cache: Dict[str, DocumentTemplate] = {}
        self._declarations_path = DECLARATIONS_DIR
        self._fiscal_services_path = FISCAL_SERVICES_DIR
        self._use_firebase = use_firebase

        logger.info(f"TemplateLoader initialized (v4.0 - Firebase Storage + local fallback)")
        logger.info(f"Firebase Storage: {'enabled' if use_firebase else 'disabled'}")
        logger.info(f"Local declarations path: {self._declarations_path}")
        logger.info(f"Local fiscal services path: {self._fiscal_services_path}")

    def load(self, template_name: str, template_type: str = "declaration") -> Optional[DocumentTemplate]:
        """
        Load a template by name and type (Firebase Storage first, local fallback)

        Args:
            template_name: Name of template (e.g., "iva_destajo", "retencion_3pct_petrolero")
            template_type: Type of template ("declaration" or "fiscal_service")

        Returns:
            DocumentTemplate or None if not found

        Loading strategy:
            1. Check cache
            2. Try Firebase Storage: tax-forms/{template_name}/{template_name}.json
            3. Fallback to local: templates/{type}/{template_name}.json
        """
        cache_key = f"{template_type}:{template_name}"

        # Check cache
        if cache_key in self._cache:
            logger.debug(f"Template {cache_key} loaded from cache")
            return self._cache[cache_key]

        data = None
        source = None

        # Try Firebase Storage first (if enabled)
        if self._use_firebase:
            firebase_path = f"tax-forms/{template_name}/{template_name}.json"
            try:
                import asyncio

                # Run async download in sync context
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If loop is already running, we can't use run_until_complete
                    # Skip Firebase and go straight to local fallback
                    logger.debug(f"Event loop already running, skipping Firebase for {cache_key}")
                else:
                    download_result = loop.run_until_complete(
                        firebase_storage_service.download_file(firebase_path, user_id=None)
                    )

                    # Parse JSON from bytes
                    data = json.loads(download_result.content.decode('utf-8'))
                    source = "Firebase Storage"
                    logger.info(f"Template {cache_key} loaded from Firebase Storage: {firebase_path}")

            except Exception as e:
                logger.debug(f"Firebase Storage load failed for {cache_key}: {e}, falling back to local")

        # Fallback to local filesystem
        if data is None:
            # Determine local file path
            if template_type == "declaration":
                file_path = self._declarations_path / f"{template_name}.json"
            elif template_type == "fiscal_service":
                file_path = self._fiscal_services_path / f"{template_name}.json"
            else:
                logger.error(f"Unknown template type: {template_type}")
                return None

            # Load from local file
            try:
                if not file_path.exists():
                    logger.error(f"Template file not found (local): {file_path}")
                    return None

                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                source = "Local filesystem"
                logger.info(f"Template {cache_key} loaded from local filesystem: {file_path}")

            except Exception as e:
                logger.error(f"Error loading template {cache_key} from local: {e}")
                import traceback
                traceback.print_exc()
                return None

        # Parse template
        try:
            template = self._parse_template(data)

            # Cache it
            self._cache[cache_key] = template

            total_fields = sum(len(section.fields) for section in template.sections)
            logger.info(f"Template {cache_key} ready ({len(template.sections)} sections, {total_fields} fields) [source: {source}]")
            return template

        except Exception as e:
            logger.error(f"Error parsing template {cache_key}: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _parse_template(self, data: Dict[str, Any]) -> DocumentTemplate:
        """Parse JSON data into DocumentTemplate"""

        # Parse form_metadata (supports both structures: declarations vs fiscal_services)
        if "form_metadata" in data:
            # Declaration template structure (iva_destajo, etc.)
            metadata = data["form_metadata"]
        else:
            # Fiscal service template structure (nota_ingreso, etc.)
            # Metadata at root level
            metadata = {
                "name": data.get("name"),
                "code_impuesto": data.get("code_impuesto"),
                "category": data.get("category", "fiscal_service"),
                "subtype": data.get("subtype"),
                "description": data.get("description", ""),
                "version": data.get("version", "1.0"),
                "official_pdf": data.get("official_pdf"),
                "db_table": data.get("sections", [{}])[0].get("db_table", "fiscal_service_data") if data.get("sections") else "fiscal_service_data",
                "db_subtype_field": data.get("db_subtype_field"),
                "db_subtype_value": data.get("db_subtype_value")
            }

        # Parse sections
        sections = []
        for section_data in data.get("sections", []):
            fields = []
            for field_data in section_data.get("fields", []):
                field = FieldConfig(
                    id=field_data["id"],
                    db_column=field_data.get("db_column"),
                    db_type=field_data.get("db_type"),
                    label=field_data.get("label", []),
                    type=field_data["type"],
                    campo=field_data.get("campo"),
                    ocr_pattern=field_data.get("ocr_pattern"),
                    required=field_data.get("required", False),
                    calculated=field_data.get("calculated", False),
                    formula=field_data.get("formula"),
                    display_formula=field_data.get("display_formula"),
                    default_value=field_data.get("default_value"),
                    validation=field_data.get("validation"),
                    comment=field_data.get("comment")
                )
                fields.append(field)

            section = SectionConfig(
                section_id=section_data["section_id"],
                section_label=section_data["section_label"],
                section_description=section_data.get("section_description"),
                db_table=section_data["db_table"],
                fields=fields,
                comment=section_data.get("comment")
            )
            sections.append(section)

        # Parse validations
        validations = []
        for val_data in data.get("validations", []):
            validation = ValidationRule(
                type=val_data["type"],
                data=val_data
            )
            validations.append(validation)

        # Parse OCR strategy
        ocr_strategy = None
        if "ocr_extraction_strategy" in data:
            ocr_data = data["ocr_extraction_strategy"]
            ocr_strategy = OCRStrategy(
                primary=ocr_data.get("primary", "line_by_line_matching"),
                fallback=ocr_data.get("fallback"),
                use_coordinates=ocr_data.get("use_coordinates", False),
                preprocessing=ocr_data.get("preprocessing"),
                table_extraction=ocr_data.get("table_extraction")
            )

        # Parse business rules
        business_rules = []
        for rule_data in data.get("business_rules", []):
            rule = BusinessRule(
                rule=rule_data["rule"],
                description=rule_data["description"],
                enforcement=rule_data["enforcement"]
            )
            business_rules.append(rule)

        return DocumentTemplate(
            name=metadata["name"],
            code_impuesto=metadata.get("code_impuesto"),
            category=metadata["category"],
            subtype=metadata.get("subtype"),
            description=metadata["description"],
            version=metadata["version"],
            official_pdf=metadata.get("official_pdf"),
            db_table=metadata["db_table"],
            db_subtype_field=metadata.get("db_subtype_field"),
            db_subtype_value=metadata.get("db_subtype_value"),
            sections=sections,
            validations=validations,
            ocr_strategy=ocr_strategy,
            business_rules=business_rules,
            comment=metadata.get("comment")
        )

    def list_available_templates(self, template_type: str = "declaration") -> List[str]:
        """
        List all available templates

        Args:
            template_type: Type of templates to list

        Returns:
            List of template names (without .json extension)
        """
        if template_type == "declaration":
            path = self._declarations_path
        elif template_type == "fiscal_service":
            path = self._fiscal_services_path
        else:
            return []

        if not path.exists():
            return []

        templates = [f.stem for f in path.glob("*.json") if not f.stem.startswith("form_")]
        return sorted(templates)

    def get_required_fields(self, template: DocumentTemplate) -> List[str]:
        """Get list of required field IDs across all sections"""
        required = []
        for section in template.sections:
            required.extend([f.id for f in section.fields if f.required])
        return required

    def get_fields_by_type(self, template: DocumentTemplate, field_type: str) -> List[FieldConfig]:
        """Get all fields of a specific type across all sections"""
        fields = []
        for section in template.sections:
            fields.extend([f for f in section.fields if f.type == field_type])
        return fields

    def get_section_by_id(self, template: DocumentTemplate, section_id: str) -> Optional[SectionConfig]:
        """Get a specific section by ID"""
        for section in template.sections:
            if section.section_id == section_id:
                return section
        return None

    def get_field_by_id(self, template: DocumentTemplate, field_id: str) -> Optional[FieldConfig]:
        """Get a specific field by ID (searches all sections)"""
        for section in template.sections:
            for field in section.fields:
                if field.id == field_id:
                    return field
        return None

    def get_calculated_fields(self, template: DocumentTemplate) -> List[FieldConfig]:
        """Get all calculated fields"""
        calculated = []
        for section in template.sections:
            calculated.extend([f for f in section.fields if f.calculated])
        return calculated

    def get_ocr_patterns(self, template: DocumentTemplate) -> Dict[str, str]:
        """Get all OCR patterns mapped by field ID"""
        patterns = {}
        for section in template.sections:
            for field in section.fields:
                if field.ocr_pattern:
                    patterns[field.id] = field.ocr_pattern
        return patterns

    def clear_cache(self):
        """Clear the template cache"""
        self._cache.clear()
        logger.info("Template cache cleared")


# Singleton instance
template_loader = TemplateLoader()
