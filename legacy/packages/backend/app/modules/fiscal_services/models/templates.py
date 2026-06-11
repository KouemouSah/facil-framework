"""
Template Models - Document and Procedure Templates

Tables implemented:
- document_templates: Reusable document templates
- procedure_templates: Reusable procedure workflows
- procedure_template_steps: Individual steps in procedures
- service_document_assignments: Link services to required documents
- service_procedure_assignments: Link services to procedures
- service_keywords: Multilingual keywords for search
- entity_translations: Translations for all entities
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


# ═══════════════════════════════════════════════════════════════════════════
# ENUMS
# ═══════════════════════════════════════════════════════════════════════════


class TranslatableEntityType(str, Enum):
    """
    Types of entities that can be translated

    IMPORTANT: Translations are ONLY used for the site's UI language
    (not for user data or search). They allow displaying the same
    entity in French, English, etc. based on user's language preference.
    """
    MINISTRY = "ministry"
    SECTOR = "sector"
    CATEGORY = "category"
    FISCAL_SERVICE = "fiscal_service"
    DOCUMENT_TEMPLATE = "document_template"
    PROCEDURE_TEMPLATE = "procedure_template"
    PROCEDURE_STEP = "procedure_step"


# ═══════════════════════════════════════════════════════════════════════════
# DOCUMENT_TEMPLATES Models
# ═══════════════════════════════════════════════════════════════════════════


class DocumentTemplateBase(BaseModel):
    """Base document template model"""
    template_code: str = Field(..., max_length=100, description="Unique template code")
    document_name_es: str = Field(..., max_length=255, description="Document name (Spanish)")
    description_es: Optional[str] = Field(None, description="Document description (Spanish)")
    category: Optional[str] = Field(None, max_length=50, description="Document category")
    validity_duration_months: Optional[int] = Field(None, ge=0, description="How long document is valid")
    validity_notes: Optional[str] = Field(None, description="Notes about validity period")
    is_active: bool = Field(True, description="Whether template is active")


class DocumentTemplateCreate(DocumentTemplateBase):
    """Create document template request"""
    created_by: Optional[int] = Field(None, description="User ID who created this template")


class DocumentTemplateUpdate(BaseModel):
    """Update document template request - all fields optional"""
    document_name_es: Optional[str] = Field(None, max_length=255)
    description_es: Optional[str] = None
    category: Optional[str] = Field(None, max_length=50)
    validity_duration_months: Optional[int] = Field(None, ge=0)
    validity_notes: Optional[str] = None
    is_active: Optional[bool] = None


class DocumentTemplateResponse(DocumentTemplateBase):
    """Document template response"""
    id: int
    usage_count: int = Field(0, description="Number of times this template has been used")
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by: Optional[int] = None

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════════════════
# PROCEDURE_TEMPLATES Models
# ═══════════════════════════════════════════════════════════════════════════


class ProcedureTemplateBase(BaseModel):
    """Base procedure template model"""
    template_code: str = Field(..., max_length=100, description="Unique template code")
    name_es: str = Field(..., max_length=255, description="Procedure name (Spanish)")
    description_es: Optional[str] = Field(None, description="Procedure description (Spanish)")
    category: Optional[str] = Field(None, max_length=50, description="Procedure category")
    is_active: bool = Field(True, description="Whether template is active")


class ProcedureTemplateCreate(ProcedureTemplateBase):
    """Create procedure template request"""
    created_by: Optional[int] = Field(None, description="User ID who created this template")


class ProcedureTemplateUpdate(BaseModel):
    """Update procedure template request - all fields optional"""
    name_es: Optional[str] = Field(None, max_length=255)
    description_es: Optional[str] = None
    category: Optional[str] = Field(None, max_length=50)
    is_active: Optional[bool] = None


class ProcedureTemplateResponse(ProcedureTemplateBase):
    """Procedure template response"""
    id: int
    usage_count: int = Field(0, description="Number of times this template has been used")
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by: Optional[int] = None

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════════════════
# PROCEDURE_TEMPLATE_STEPS Models
# ═══════════════════════════════════════════════════════════════════════════


class ProcedureStepBase(BaseModel):
    """Base procedure step model"""
    template_id: int = Field(..., description="FK to procedure_templates")
    step_number: int = Field(..., ge=1, description="Sequential step number")
    description_es: str = Field(..., description="Step description (Spanish)")
    instructions_es: Optional[str] = Field(None, description="Detailed instructions (Spanish)")
    estimated_duration_minutes: Optional[int] = Field(None, ge=0, description="Estimated time to complete step")
    location_address: Optional[str] = Field(None, description="Physical location if required")
    office_hours: Optional[str] = Field(None, max_length=100, description="Office hours for this step")
    requires_appointment: bool = Field(False, description="Whether appointment is required")
    is_optional: bool = Field(False, description="Whether step is optional")


class ProcedureStepCreate(ProcedureStepBase):
    """Create procedure step request"""
    pass


class ProcedureStepUpdate(BaseModel):
    """Update procedure step request - all fields optional"""
    step_number: Optional[int] = Field(None, ge=1)
    description_es: Optional[str] = None
    instructions_es: Optional[str] = None
    estimated_duration_minutes: Optional[int] = Field(None, ge=0)
    location_address: Optional[str] = None
    office_hours: Optional[str] = Field(None, max_length=100)
    requires_appointment: Optional[bool] = None
    is_optional: Optional[bool] = None


class ProcedureStepResponse(ProcedureStepBase):
    """Procedure step response"""
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ProcedureTemplateWithSteps(ProcedureTemplateResponse):
    """Procedure template with all its steps"""
    steps: List[ProcedureStepResponse] = []


# ═══════════════════════════════════════════════════════════════════════════
# SERVICE_DOCUMENT_ASSIGNMENTS Models
# ═══════════════════════════════════════════════════════════════════════════


class ServiceDocumentAssignmentBase(BaseModel):
    """Base service document assignment model"""
    fiscal_service_id: int = Field(..., description="FK to fiscal_services")
    document_template_id: int = Field(..., description="FK to document_templates")
    is_required_expedition: bool = Field(True, description="Required for first issuance")
    is_required_renewal: bool = Field(False, description="Required for renewal")
    display_order: int = Field(1, ge=1, description="Display order in UI")
    custom_notes: Optional[str] = Field(None, description="Custom notes for this assignment")


class ServiceDocumentAssignmentCreate(ServiceDocumentAssignmentBase):
    """Create service document assignment request"""
    assigned_by: Optional[int] = Field(None, description="User ID who made assignment")


class ServiceDocumentAssignmentUpdate(BaseModel):
    """Update service document assignment request - all fields optional"""
    is_required_expedition: Optional[bool] = None
    is_required_renewal: Optional[bool] = None
    display_order: Optional[int] = Field(None, ge=1)
    custom_notes: Optional[str] = None


class ServiceDocumentAssignmentResponse(ServiceDocumentAssignmentBase):
    """Service document assignment response"""
    id: int
    assigned_at: datetime
    assigned_by: Optional[int] = None

    # Optionally populated by joins
    document_name: Optional[str] = None
    service_name: Optional[str] = None

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════════════════
# SERVICE_PROCEDURE_ASSIGNMENTS Models
# ═══════════════════════════════════════════════════════════════════════════


class ServiceProcedureAssignmentBase(BaseModel):
    """Base service procedure assignment model"""
    fiscal_service_id: int = Field(..., description="FK to fiscal_services")
    template_id: int = Field(..., description="FK to procedure_templates")
    applies_to: Optional[str] = Field(None, max_length=20, description="expedition, renewal, or both")
    display_order: int = Field(1, ge=1, description="Display order in UI")
    custom_notes: Optional[str] = Field(None, description="Custom notes for this assignment")
    override_steps: Optional[Dict[str, Any]] = Field(None, description="JSONB to override specific steps")


class ServiceProcedureAssignmentCreate(ServiceProcedureAssignmentBase):
    """Create service procedure assignment request"""
    assigned_by: Optional[int] = Field(None, description="User ID who made assignment")


class ServiceProcedureAssignmentUpdate(BaseModel):
    """Update service procedure assignment request - all fields optional"""
    applies_to: Optional[str] = Field(None, max_length=20)
    display_order: Optional[int] = Field(None, ge=1)
    custom_notes: Optional[str] = None
    override_steps: Optional[Dict[str, Any]] = None


class ServiceProcedureAssignmentResponse(ServiceProcedureAssignmentBase):
    """Service procedure assignment response"""
    id: int
    assigned_at: datetime
    assigned_by: Optional[int] = None

    # Optionally populated by joins
    procedure_name: Optional[str] = None
    service_name: Optional[str] = None

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════════════════
# SERVICE_KEYWORDS Models
# ═══════════════════════════════════════════════════════════════════════════


class ServiceKeywordBase(BaseModel):
    """
    Base service keyword model

    IMPORTANT: Keywords are EXCLUSIVELY for search functionality.
    They help users find services using different terms in different languages.
    Examples:
    - Service "Permiso de Residencia" might have keywords:
      - "residencia", "permiso" (es)
      - "residence", "permit" (en)
      - "résidence", "permis" (fr)
    This improves search results when users type in their preferred language.
    """
    fiscal_service_id: int = Field(..., description="FK to fiscal_services")
    keyword: str = Field(..., max_length=100, description="Search keyword (lowercase)")
    language_code: str = Field(..., max_length=2, description="ISO 639-1 language code (es, fr, en)")
    weight: int = Field(1, ge=1, le=10, description="Search weight/importance (1-10, higher = more relevant)")
    is_auto_generated: bool = Field(False, description="Whether keyword was auto-generated from entity names")


class ServiceKeywordCreate(ServiceKeywordBase):
    """Create service keyword request"""
    pass


class ServiceKeywordUpdate(BaseModel):
    """Update service keyword request - all fields optional"""
    weight: Optional[int] = Field(None, ge=1, le=10)
    is_auto_generated: Optional[bool] = None


class ServiceKeywordResponse(ServiceKeywordBase):
    """Service keyword response"""
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class ServiceKeywordBulkCreate(BaseModel):
    """Bulk create keywords for a service"""
    fiscal_service_id: int
    keywords: List[Dict[str, Any]] = Field(
        ...,
        description="List of {keyword, language_code, weight?, is_auto_generated?}"
    )


# ═══════════════════════════════════════════════════════════════════════════
# ENTITY_TRANSLATIONS Models
# ═══════════════════════════════════════════════════════════════════════════


class EntityTranslationBase(BaseModel):
    """
    Base entity translation model

    USAGE: Translations for the WEBSITE UI ONLY (not for search or user data)

    Purpose: Display entity information in the user's preferred language
    Example:
    - Base data (Spanish):
      - name_es: "Permiso de Residencia"
      - description_es: "Documento para residir en el país"

    - Translations (for UI):
      - entity_translations:
        - (en, name): "Residence Permit"
        - (en, description): "Document to reside in the country"
        - (fr, name): "Permis de Résidence"
        - (fr, description): "Document pour résider dans le pays"

    When user selects English UI → Display "Residence Permit"
    When user selects French UI → Display "Permis de Résidence"

    NOTE: This is separate from keywords (which are for search only)
    """
    entity_type: TranslatableEntityType = Field(..., description="Type of entity being translated")
    entity_code: str = Field(..., max_length=100, description="Unique code of the entity")
    language_code: str = Field(..., max_length=5, description="Target language (fr, en, pt, etc - NOT source language es)")
    field_name: str = Field(..., max_length=30, description="Field being translated (name, description, notes, etc)")
    translation_text: str = Field(..., description="Translated text in target language")
    translation_source: str = Field("manual", max_length=20, description="Translation method: manual, google_translate, deepl, chatgpt")
    translation_quality: Optional[float] = Field(None, ge=0, le=1, description="Quality score 0-1 (1=perfect, 0.5=machine, 0=poor)")


class EntityTranslationCreate(EntityTranslationBase):
    """Create entity translation request"""
    pass


class EntityTranslationUpdate(BaseModel):
    """Update entity translation request - all fields optional"""
    translation_text: Optional[str] = None
    translation_source: Optional[str] = Field(None, max_length=20)
    translation_quality: Optional[float] = Field(None, ge=0, le=1)


class EntityTranslationResponse(EntityTranslationBase):
    """Entity translation response"""
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class EntityTranslationBulk(BaseModel):
    """Bulk create/update translations for an entity"""
    entity_type: TranslatableEntityType
    entity_code: str
    translations: List[Dict[str, Any]] = Field(
        ...,
        description="List of {language_code, field_name, translation_text, ...}"
    )


# ═══════════════════════════════════════════════════════════════════════════
# List Response Models
# ═══════════════════════════════════════════════════════════════════════════


class DocumentTemplateListResponse(BaseModel):
    """Paginated list of document templates"""
    templates: List[DocumentTemplateResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class ProcedureTemplateListResponse(BaseModel):
    """Paginated list of procedure templates"""
    templates: List[ProcedureTemplateResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
