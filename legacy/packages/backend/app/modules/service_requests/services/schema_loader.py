"""
Schema Loader for document extraction.
Loads JSON schemas from the schemas/ directory.

Handles mapping between:
- Database extraction_schema_key (e.g., 'DIP_GQ_V1')
- JSON file names (e.g., 'dip_gq.json')
- Schema IDs inside files (e.g., 'DIP_GQ_V2')
"""
import json
import re
from pathlib import Path
from typing import Dict, Optional, List
import logging

logger = logging.getLogger(__name__)

SCHEMAS_DIR = Path(__file__).parent.parent / "schemas"


class SchemaLoader:
    """
    Load and manage extraction schemas from JSON files.

    Provides multiple access methods:
    - By file name (e.g., 'dip_gq')
    - By database key (e.g., 'DIP_GQ_V1')
    - By schema_id (e.g., 'DIP_GQ_V2')
    - By document_code (e.g., 'dip', 'pasaporte_entrada')
    """

    def __init__(self):
        self._schemas: Dict[str, Dict] = {}
        # Mapping from database extraction_schema_key to file-based key
        self._db_key_to_file_key: Dict[str, str] = {}
        # Mapping from schema_id to file-based key
        self._schema_id_to_file_key: Dict[str, str] = {}
        # Mapping from document_type to file-based key
        self._doc_type_to_file_key: Dict[str, str] = {}
        self._load_all()

    def _normalize_db_key(self, db_key: str) -> str:
        """
        Normalize database extraction_schema_key to file-based key.

        Examples:
            'DIP_GQ_V1' -> 'dip_gq'
            'PASAPORTE_GQ_V1' -> 'pasaporte_gq'
            'CONTRATO_COMPRAVENTA_GQ_V1' -> 'contrato_compraventa_gq'
        """
        if not db_key:
            return ""
        # Remove version suffix (_V1, _V2, etc.)
        normalized = re.sub(r'_V\d+$', '', db_key)
        # Convert to lowercase
        return normalized.lower()

    def _load_all(self):
        """Load all JSON schemas from directory and build mappings"""
        if not SCHEMAS_DIR.exists():
            logger.warning(f"Schemas directory not found: {SCHEMAS_DIR}")
            return

        for filepath in SCHEMAS_DIR.glob("*.json"):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    schema = json.load(f)
                    # Use filename without extension as primary key
                    file_key = filepath.stem
                    self._schemas[file_key] = schema

                    # Build mappings
                    schema_id = schema.get("schema_id", "")
                    doc_type = schema.get("document_type", "")

                    if schema_id:
                        # Map schema_id to file key
                        self._schema_id_to_file_key[schema_id] = file_key
                        self._schema_id_to_file_key[schema_id.lower()] = file_key
                        # Also map normalized (without version) to file key
                        normalized = self._normalize_db_key(schema_id)
                        self._db_key_to_file_key[normalized] = file_key

                    if doc_type:
                        # Map document_type to file key
                        self._doc_type_to_file_key[doc_type.lower()] = file_key

                    logger.debug(f"Loaded schema: {file_key} (schema_id={schema_id}, doc_type={doc_type})")

            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in {filepath}: {e}")
            except Exception as e:
                logger.error(f"Error loading {filepath}: {e}")

        logger.info(f"Loaded {len(self._schemas)} schemas with {len(self._db_key_to_file_key)} key mappings")

    def get_schema(self, schema_key: str) -> Optional[Dict]:
        """
        Get schema by key (e.g., 'dip_gq', 'pasaporte_gq').

        Args:
            schema_key: The schema key (filename without .json)

        Returns:
            The schema dictionary or None if not found
        """
        return self._schemas.get(schema_key)

    def get_schema_by_db_key(self, extraction_schema_key: str) -> Optional[Dict]:
        """
        Get schema by database extraction_schema_key.

        This is the PREFERRED method when you have the database key.

        Args:
            extraction_schema_key: The key from workflow_document_requirements
                                   (e.g., 'DIP_GQ_V1', 'PASAPORTE_GQ_V1')

        Returns:
            The schema dictionary or None if not found
        """
        if not extraction_schema_key:
            return None

        # First try exact match on schema_id
        if extraction_schema_key in self._schema_id_to_file_key:
            file_key = self._schema_id_to_file_key[extraction_schema_key]
            return self._schemas.get(file_key)

        # Try normalized key (remove version, lowercase)
        normalized = self._normalize_db_key(extraction_schema_key)
        if normalized in self._db_key_to_file_key:
            file_key = self._db_key_to_file_key[normalized]
            return self._schemas.get(file_key)

        # Try direct file lookup
        if normalized in self._schemas:
            return self._schemas[normalized]

        logger.warning(f"No schema found for extraction_schema_key: {extraction_schema_key}")
        return None

    def get_schema_for_document(self, document_code: str, extraction_schema_key: Optional[str] = None) -> Optional[Dict]:
        """
        Get schema matching a document code or extraction_schema_key.

        Priority order:
        1. extraction_schema_key (if provided) - direct database mapping
        2. document_code exact match
        3. document_code partial match

        Args:
            document_code: The document code to match (e.g., 'dip', 'pasaporte_entrada')
            extraction_schema_key: Optional database key (e.g., 'DIP_GQ_V1')

        Returns:
            Matching schema or None
        """
        # Priority 1: Use extraction_schema_key if provided
        if extraction_schema_key:
            schema = self.get_schema_by_db_key(extraction_schema_key)
            if schema:
                return schema
            logger.warning(
                f"extraction_schema_key '{extraction_schema_key}' not found, "
                f"falling back to document_code '{document_code}'"
            )

        # Normalize document code
        code_lower = document_code.lower().replace(" ", "_").replace("-", "_")

        # Priority 2: Try exact match on file key
        if code_lower in self._schemas:
            return self._schemas[code_lower]

        # Priority 3: Try document_type mapping
        if code_lower in self._doc_type_to_file_key:
            file_key = self._doc_type_to_file_key[code_lower]
            return self._schemas.get(file_key)

        # Priority 4: Try partial match on file key
        for key, schema in self._schemas.items():
            if code_lower in key.lower() or key.lower() in code_lower:
                return schema

        # Priority 5: Try matching against schema document_type
        for key, schema in self._schemas.items():
            doc_type = schema.get("document_type", "").lower()
            if doc_type and (code_lower in doc_type or doc_type in code_lower):
                return schema

        logger.warning(f"No schema found for document_code: {document_code}")
        return None

    def resolve_schema_key(self, document_code: str, extraction_schema_key: Optional[str] = None) -> Optional[str]:
        """
        Resolve the file-based schema key for a document.

        Useful for logging and debugging.

        Args:
            document_code: The document code
            extraction_schema_key: Optional database key

        Returns:
            The resolved file key or None
        """
        if extraction_schema_key:
            # Try normalized DB key
            normalized = self._normalize_db_key(extraction_schema_key)
            if normalized in self._db_key_to_file_key:
                return self._db_key_to_file_key[normalized]
            if normalized in self._schemas:
                return normalized

        code_lower = document_code.lower().replace(" ", "_").replace("-", "_")
        if code_lower in self._schemas:
            return code_lower

        # Try partial match
        for key in self._schemas.keys():
            if code_lower in key.lower() or key.lower() in code_lower:
                return key

        return None

    def get_all_schemas(self) -> Dict[str, Dict]:
        """Get all loaded schemas"""
        return self._schemas.copy()

    def get_schema_keys(self) -> List[str]:
        """Get list of all schema keys"""
        return list(self._schemas.keys())

    def get_extraction_fields(self, schema_key: str, extraction_schema_key: Optional[str] = None) -> Dict[str, Dict]:
        """
        Get all extraction fields from a schema, flattened.

        Args:
            schema_key: The schema key (file-based)
            extraction_schema_key: Optional database extraction_schema_key

        Returns:
            Dict of field_name -> field_config with bloc info
        """
        # Try to get schema with priority to extraction_schema_key
        schema = None
        if extraction_schema_key:
            schema = self.get_schema_by_db_key(extraction_schema_key)
        if not schema:
            schema = self.get_schema(schema_key)
        if not schema:
            return {}

        fields = {}
        # Schema uses "extraction" key, not "blocs"
        extraction = schema.get("extraction", {})
        for bloc_name, bloc in extraction.items():
            if isinstance(bloc, dict) and "fields" in bloc:
                for field_name, field_config in bloc.get("fields", {}).items():
                    fields[field_name] = {
                        **field_config,
                        "bloc": bloc_name
                    }
        return fields

    def get_required_fields(self, schema_key: str) -> List[str]:
        """Get list of required field names for a schema"""
        fields = self.get_extraction_fields(schema_key)
        return [
            name for name, config in fields.items()
            if config.get("required", False)
        ]

    def build_gemini_prompt(self, schema_key: str, extraction_schema_key: Optional[str] = None) -> str:
        """
        Build extraction prompt from schema for Gemini.

        Args:
            schema_key: The schema key (file-based)
            extraction_schema_key: Optional database extraction_schema_key

        Returns:
            Formatted prompt string with extraction instructions
        """
        # Try to get schema with priority to extraction_schema_key
        schema = None
        if extraction_schema_key:
            schema = self.get_schema_by_db_key(extraction_schema_key)
        if not schema:
            schema = self.get_schema(schema_key)
        if not schema:
            return ""

        lines = [
            f"## Document: {schema.get('title', schema.get('description', schema_key))}",
            f"Description: {schema.get('description', '')}",
            "",
            "Extraire les informations suivantes en JSON:",
            ""
        ]

        # Use gemini_hints if available
        gemini_hints = schema.get("gemini_hints", {})
        if gemini_hints.get("document_description"):
            lines.append(f"Note: {gemini_hints['document_description']}")
            lines.append("")

        if gemini_hints.get("visual_zones"):
            lines.append("Zones visuelles:")
            zones = gemini_hints["visual_zones"]
            if isinstance(zones, dict):
                for face, zone_list in zones.items():
                    lines.append(f"  {face}:")
                    for zone in zone_list:
                        lines.append(f"    - {zone}")
            elif isinstance(zones, list):
                for zone in zones:
                    lines.append(f"  - {zone}")
            lines.append("")

        # Use "extraction" key for fields
        extraction = schema.get("extraction", {})
        for bloc_name, bloc in extraction.items():
            if not isinstance(bloc, dict) or "fields" not in bloc:
                continue

            bloc_title = bloc_name.replace("_", " ").title()
            lines.append(f"### {bloc_title}")
            lines.append(f"{bloc.get('description', '')}")
            lines.append("")

            for field_name, config in bloc.get("fields", {}).items():
                required = "OBLIGATOIRE" if config.get("required") else "optionnel"
                # Use field_label or description for hint
                hint = config.get("field_label", config.get("description", ""))
                field_type = config.get("type", "string")
                pattern = config.get("pattern", "")

                line = f"- **{field_name}** ({field_type}, {required})"
                if hint:
                    line += f": {hint}"
                if pattern:
                    line += f" [pattern: {pattern}]"
                lines.append(line)

            lines.append("")

        return "\n".join(lines)

    def get_tesseract_patterns(self, schema_key: str, extraction_schema_key: Optional[str] = None) -> Dict[str, List[str]]:
        """
        Get regex patterns for Tesseract fallback extraction.

        Args:
            schema_key: The schema key (file-based)
            extraction_schema_key: Optional database extraction_schema_key

        Returns:
            Dict of field_name -> list of regex patterns
        """
        # Try to get schema with priority to extraction_schema_key
        schema = None
        if extraction_schema_key:
            schema = self.get_schema_by_db_key(extraction_schema_key)
        if not schema:
            schema = self.get_schema(schema_key)
        if not schema:
            return {}
        return schema.get("tesseract_patterns", {})

    def get_validation_rules(self, schema_key: str, extraction_schema_key: Optional[str] = None) -> Dict[str, Dict]:
        """
        Get validation rules from schema.

        Args:
            schema_key: The schema key (file-based)
            extraction_schema_key: Optional database extraction_schema_key

        Returns:
            Dict of field_name -> validation config
        """
        fields = self.get_extraction_fields(schema_key, extraction_schema_key)
        rules = {}

        for field_name, config in fields.items():
            rule = {}
            if config.get("required"):
                rule["required"] = True
            if config.get("pattern"):
                rule["pattern"] = config["pattern"]
            if config.get("type") == "date":
                rule["type"] = "date"
                rule["format"] = config.get("format", config.get("date_format", "YYYY-MM-DD"))
            if config.get("type") == "enum" or "enum" in config:
                rule["type"] = "enum"
                rule["values"] = config.get("enum", config.get("values", []))
            if config.get("validation"):
                rule["validation"] = config["validation"]
            if rule:
                rules[field_name] = rule

        return rules

    def get_schema_validations(self, schema_key: str, extraction_schema_key: Optional[str] = None) -> List[Dict]:
        """
        Get top-level validation rules from schema (cross-field validations).

        Args:
            schema_key: The schema key (file-based)
            extraction_schema_key: Optional database extraction_schema_key

        Returns:
            List of validation rule dictionaries
        """
        schema = None
        if extraction_schema_key:
            schema = self.get_schema_by_db_key(extraction_schema_key)
        if not schema:
            schema = self.get_schema(schema_key)
        if not schema:
            return []
        return schema.get("validations", [])

    def get_gemini_hints(self, schema_key: str, extraction_schema_key: Optional[str] = None) -> Dict:
        """
        Get Gemini-specific hints from schema.

        Args:
            schema_key: The schema key (file-based)
            extraction_schema_key: Optional database extraction_schema_key

        Returns:
            Dict with gemini_hints content
        """
        schema = None
        if extraction_schema_key:
            schema = self.get_schema_by_db_key(extraction_schema_key)
        if not schema:
            schema = self.get_schema(schema_key)
        if not schema:
            return {}
        return schema.get("gemini_hints", {})


# Singleton instance
schema_loader = SchemaLoader()
