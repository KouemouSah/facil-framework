"""
Pydantic response models for Dynamic Form Config API.

These models are used for the GET /requests/{request_id}/form-config/{step_id} endpoint
that returns form configuration with pre-filled values.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union


class FormFieldOptionResponse(BaseModel):
    """Option with value and display label for select/radio fields."""
    value: str
    label_es: str


class FormFieldResponse(BaseModel):
    """
    A field in a form section with its current value.

    Note: extraction_path is NOT included - the backend resolves values
    via workflow.get_form_mapping() and sends them in current_value.
    """
    key: str = Field(..., description="Unique field identifier (e.g., 'numero_dip', 'apellidos')")
    label_es: str = Field(..., description="Spanish label for display")
    type: str = Field(default="text", description="Field type: text, date, select, radio, checkbox, textarea")
    required: bool = Field(default=False, description="Whether field is mandatory")
    options: Optional[List[Union[str, FormFieldOptionResponse]]] = Field(default=None, description="Options for select/radio fields (string or {value, label_es})")
    readonly: bool = Field(default=False, description="Whether field is read-only")
    placeholder_es: Optional[str] = Field(default=None, description="Placeholder text in Spanish")
    validation: Optional[Dict[str, Any]] = Field(default=None, description="Validation rules")
    help_text_es: Optional[str] = Field(default=None, description="Helper text displayed below the field")
    show_when: Optional[Dict[str, str]] = Field(default=None, description="Conditional visibility: {field: key, value: val}")
    current_value: Optional[Any] = Field(default=None, description="Pre-filled value from extraction")

    class Config:
        json_schema_extra = {
            "example": {
                "key": "apellidos",
                "label_es": "Apellidos",
                "type": "text",
                "required": True,
                "readonly": False,
                "current_value": "GARCIA LOPEZ"
            }
        }


class FormSectionResponse(BaseModel):
    """
    A section in a form containing multiple fields.

    Note: condition is NOT included in response - sections are already
    filtered by the backend based on context evaluation.
    """
    id: str = Field(..., description="Unique section identifier (e.g., 'personal', 'filiacion')")
    title_es: str = Field(..., description="Spanish title for display")
    fields: List[FormFieldResponse] = Field(default_factory=list, description="Fields in this section")
    source_document: Optional[str] = Field(default=None, description="Document source (e.g., 'dip')")
    description_es: Optional[str] = Field(default=None, description="Optional description")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "datos_personales",
                "title_es": "Datos Personales",
                "source_document": "dip",
                "fields": [
                    {"key": "apellidos", "label_es": "Apellidos", "type": "text", "required": True},
                    {"key": "nombre", "label_es": "Nombre", "type": "text", "required": True}
                ]
            }
        }


class FormConfigResponse(BaseModel):
    """
    Complete form configuration for a workflow step.

    Only contains sections that passed condition evaluation based on
    the current request context (solicitud_type, motivo, is_minor, etc.).
    """
    step_id: str = Field(..., description="ID of the workflow step (e.g., 'form_review_1')")
    title_es: str = Field(..., description="Spanish title for the step")
    description_es: Optional[str] = Field(default=None, description="Optional description")
    sections: List[FormSectionResponse] = Field(default_factory=list, description="Sections to display")

    class Config:
        json_schema_extra = {
            "example": {
                "step_id": "form_review_2",
                "title_es": "Revisión de Datos Extraídos",
                "sections": [
                    {
                        "id": "datos_personales",
                        "title_es": "Datos Personales",
                        "fields": [
                            {"key": "apellidos", "label_es": "Apellidos", "required": True}
                        ]
                    }
                ]
            }
        }

    @classmethod
    def from_dataclass(cls, form_config: "FormConfig") -> "FormConfigResponse":
        """
        Convert from workflow FormConfig dataclass to Pydantic response.

        Args:
            form_config: FormConfig dataclass from workflow.get_form_config()

        Returns:
            FormConfigResponse ready for API serialization
        """
        sections = []
        for section in form_config.sections:
            fields = [
                FormFieldResponse(
                    key=f.key,
                    label_es=f.label_es,
                    type=f.type,
                    required=f.required,
                    options=f.options,
                    readonly=f.readonly,
                    placeholder_es=f.placeholder_es,
                    validation=f.validation,
                    help_text_es=f.help_text_es,
                    show_when=f.show_when,
                    current_value=None  # Will be filled by API endpoint
                )
                for f in section.fields
            ]
            sections.append(FormSectionResponse(
                id=section.id,
                title_es=section.title_es,
                fields=fields,
                source_document=section.source_document,
                description_es=section.description_es
            ))

        return cls(
            step_id=form_config.step_id,
            title_es=form_config.title_es,
            description_es=form_config.description_es,
            sections=sections
        )


# Type hint for lazy import
if False:  # TYPE_CHECKING
    from ..workflows.form_config import FormConfig
