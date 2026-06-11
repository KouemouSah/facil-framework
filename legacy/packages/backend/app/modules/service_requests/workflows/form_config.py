"""
Form Configuration Dataclasses for Dynamic Wizard.

These dataclasses define the structure for form configurations
that can be read from workflow step configs and returned via API.

Usage:
    workflow.get_form_config("form_review_1", context) -> FormConfig
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Union


@dataclass
class FormField:
    """
    A field in a form section.

    Attributes:
        key: Unique field identifier (e.g., "numero_dip", "apellidos")
        label_es: Spanish label for display
        type: Field type (text, date, select, radio, checkbox, textarea)
        required: Whether field is mandatory
        options: Options for select/radio fields (str or {"value": str, "label_es": str})
        readonly: Whether field is read-only
        placeholder_es: Placeholder text in Spanish
        validation: Validation rules (e.g., {"min_length": 2, "pattern": "^[A-Z]+"})
        help_text_es: Helper text displayed below the field
        show_when: Conditional visibility ({"field": "key", "value": "val"})

    Note:
        extraction_path is NOT included here - use workflow.get_form_mapping()
        which is the source of truth for mapping form fields to extracted data.
    """
    key: str
    label_es: str
    type: str = "text"
    required: bool = False
    options: Optional[List[Union[str, Dict[str, str]]]] = None
    readonly: bool = False
    placeholder_es: Optional[str] = None
    validation: Optional[Dict[str, Any]] = None
    help_text_es: Optional[str] = None
    show_when: Optional[Dict[str, str]] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FormField":
        """Create FormField from dict (e.g., from workflow config)."""
        return cls(
            key=data["key"],
            label_es=data.get("label_es", data.get("label", data["key"])),
            type=data.get("type", "text"),
            required=data.get("required", False),
            options=data.get("options"),
            readonly=data.get("readonly", False),
            placeholder_es=data.get("placeholder_es"),
            validation=data.get("validation"),
            help_text_es=data.get("help_text_es"),
            show_when=data.get("show_when"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for API response."""
        result = {
            "key": self.key,
            "label_es": self.label_es,
            "type": self.type,
            "required": self.required,
            "readonly": self.readonly,
        }
        if self.options:
            result["options"] = self.options
        if self.placeholder_es:
            result["placeholder_es"] = self.placeholder_es
        if self.validation:
            result["validation"] = self.validation
        if self.help_text_es:
            result["help_text_es"] = self.help_text_es
        if self.show_when:
            result["show_when"] = self.show_when
        return result


@dataclass
class FormSection:
    """
    A section in a form containing multiple fields.

    Attributes:
        id: Unique section identifier (e.g., "personal", "filiacion")
        title_es: Spanish title for display
        fields: List of fields in this section
        condition: Optional condition for when to show this section
                   Format: {"key": "value"} or {"key_in": [...]} or {"OR": [...]}
        source_document: Document from which data is extracted (e.g., "dip")
        description_es: Optional description in Spanish
    """
    id: str
    title_es: str
    fields: List[FormField]
    condition: Optional[Dict[str, Any]] = None
    source_document: Optional[str] = None
    description_es: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FormSection":
        """Create FormSection from dict (e.g., from workflow config)."""
        fields = [FormField.from_dict(f) for f in data.get("fields", [])]
        return cls(
            id=data["id"],
            title_es=data.get("title_es", data.get("title", data["id"])),
            fields=fields,
            condition=data.get("condition"),
            source_document=data.get("source_document"),
            description_es=data.get("description_es")
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for API response."""
        result = {
            "id": self.id,
            "title_es": self.title_es,
            "fields": [f.to_dict() for f in self.fields],
        }
        if self.source_document:
            result["source_document"] = self.source_document
        if self.description_es:
            result["description_es"] = self.description_es
        # Note: condition is NOT included in API response (already evaluated)
        return result


@dataclass
class FormConfig:
    """
    Complete form configuration for a workflow step.

    Returned by workflow.get_form_config(step_id, context).
    Only contains sections that passed condition evaluation.

    Attributes:
        step_id: ID of the workflow step (e.g., "form_review_1")
        title_es: Spanish title for the step
        sections: List of sections to display (already filtered by conditions)
        description_es: Optional description in Spanish
    """
    step_id: str
    title_es: str
    sections: List[FormSection]
    description_es: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for API response."""
        result = {
            "step_id": self.step_id,
            "title_es": self.title_es,
            "sections": [s.to_dict() for s in self.sections],
        }
        if self.description_es:
            result["description_es"] = self.description_es
        return result

    def get_all_field_keys(self) -> List[str]:
        """Get all field keys across all sections."""
        keys = []
        for section in self.sections:
            for field in section.fields:
                keys.append(field.key)
        return keys


__all__ = ["FormField", "FormSection", "FormConfig"]
