"""
SMS Template Models - Pydantic models for SMS templates CRUD

Used for managing reusable SMS templates with multi-language support
and character counting for SMS segmentation.
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, field_validator


class SmsTemplateCategory(str, Enum):
    """SMS template categories"""
    AUTH = "auth"
    NOTIFICATIONS = "notifications"
    PAYMENTS = "payments"
    DECLARATIONS = "declarations"
    REMINDERS = "reminders"
    ALERTS = "alerts"


class SmsTemplateCreate(BaseModel):
    """Model for creating an SMS template"""
    template_code: str = Field(
        ...,
        min_length=3,
        max_length=100,
        pattern=r"^[A-Z0-9_]+$",
        description="Unique template code (uppercase, underscores allowed)"
    )
    name_es: str = Field(..., min_length=1, max_length=255, description="Template name (Spanish)")
    name_fr: Optional[str] = Field(None, max_length=255, description="Template name (French)")
    name_en: Optional[str] = Field(None, max_length=255, description="Template name (English)")

    content_es: str = Field(..., min_length=1, description="SMS content (Spanish)")
    content_fr: Optional[str] = Field(None, description="SMS content (French)")
    content_en: Optional[str] = Field(None, description="SMS content (English)")

    variables: List[Any] = Field(
        default_factory=list,
        description="Template variables: strings or objects {name, example, description}"
    )
    category: SmsTemplateCategory = Field(..., description="Template category")
    max_segments: int = Field(
        1,
        ge=1,
        le=10,
        description="Maximum allowed SMS segments (1 segment = 160 chars)"
    )
    is_active: bool = Field(True, description="Whether template is active")

    @field_validator('content_es', 'content_fr', 'content_en')
    @classmethod
    def validate_content_length(cls, v: Optional[str]) -> Optional[str]:
        """Validate SMS content doesn't exceed reasonable length"""
        if v is not None and len(v) > 1600:  # 10 segments max
            raise ValueError("SMS content cannot exceed 1600 characters (10 segments)")
        return v

    @field_validator('variables')
    @classmethod
    def validate_variables(cls, v: List[Any]) -> List[Any]:
        """Validate variable entries (str or dict with 'name' key)"""
        for var in v:
            if isinstance(var, str):
                if not var.isidentifier():
                    raise ValueError(f"Invalid variable name: {var}. Must be a valid identifier.")
            elif isinstance(var, dict):
                if 'name' not in var:
                    raise ValueError(f"Variable dict must have a 'name' key: {var}")
            else:
                raise ValueError(f"Variable must be a string or dict, got {type(var)}")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "template_code": "AUTH_VERIFICATION_CODE",
                "name_es": "Código de verificación",
                "name_fr": "Code de vérification",
                "name_en": "Verification code",
                "content_es": "Tu código de verificación Facil es: {{code}}. Válido por 15 minutos.",
                "content_fr": "Votre code de vérification Facil est: {{code}}. Valide pendant 15 minutes.",
                "content_en": "Your Facil verification code is: {{code}}. Valid for 15 minutes.",
                "variables": ["code"],
                "category": "auth",
                "max_segments": 1,
                "is_active": True
            }
        }


class SmsTemplateUpdate(BaseModel):
    """Model for updating an SMS template - all fields optional"""
    name_es: Optional[str] = Field(None, min_length=1, max_length=255)
    name_fr: Optional[str] = Field(None, max_length=255)
    name_en: Optional[str] = Field(None, max_length=255)

    content_es: Optional[str] = Field(None, min_length=1)
    content_fr: Optional[str] = Field(None)
    content_en: Optional[str] = Field(None)

    variables: Optional[List[Any]] = Field(None)
    category: Optional[SmsTemplateCategory] = Field(None)
    max_segments: Optional[int] = Field(None, ge=1, le=10)
    is_active: Optional[bool] = Field(None)

    @field_validator('content_es', 'content_fr', 'content_en')
    @classmethod
    def validate_content_length(cls, v: Optional[str]) -> Optional[str]:
        """Validate SMS content doesn't exceed reasonable length"""
        if v is not None and len(v) > 1600:
            raise ValueError("SMS content cannot exceed 1600 characters (10 segments)")
        return v

    @field_validator('variables')
    @classmethod
    def validate_variables(cls, v: Optional[List[Any]]) -> Optional[List[Any]]:
        """Validate variable entries"""
        if v is not None:
            for var in v:
                if isinstance(var, str) and not var.isidentifier():
                    raise ValueError(f"Invalid variable name: {var}")
                elif isinstance(var, dict) and 'name' not in var:
                    raise ValueError(f"Variable dict must have a 'name' key: {var}")
        return v


class SmsTemplateResponse(BaseModel):
    """Model for SMS template response"""
    id: int
    template_code: str
    name_es: str
    name_fr: Optional[str]
    name_en: Optional[str]

    content_es: str
    content_fr: Optional[str]
    content_en: Optional[str]

    variables: List[Any]  # Can be List[str] or List[Dict] (mixed format in DB)
    category: str
    max_segments: int
    is_active: bool

    created_at: datetime
    updated_at: Optional[datetime]
    created_by: Optional[UUID] = None
    updated_by: Optional[UUID] = None

    # Computed fields for SMS segmentation
    content_es_length: Optional[int] = None
    content_fr_length: Optional[int] = None
    content_en_length: Optional[int] = None
    content_es_segments: Optional[int] = None
    content_fr_segments: Optional[int] = None
    content_en_segments: Optional[int] = None

    class Config:
        from_attributes = True


class SmsTemplateListResponse(BaseModel):
    """Model for paginated SMS template list"""
    templates: List[SmsTemplateResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class SmsCharacterCount(BaseModel):
    """Model for SMS character count calculation"""
    content: str
    character_count: int
    segment_count: int
    characters_per_segment: int = 160
    characters_remaining: int
    uses_unicode: bool

    class Config:
        json_schema_extra = {
            "example": {
                "content": "Hello, this is a test message",
                "character_count": 30,
                "segment_count": 1,
                "characters_per_segment": 160,
                "characters_remaining": 130,
                "uses_unicode": False
            }
        }


class SmsTemplateRenderRequest(BaseModel):
    """Request to render a template with variables"""
    template_code: str = Field(..., description="Template code to render")
    language: str = Field("es", pattern="^(es|fr|en)$", description="Language code")
    variables: Dict[str, Any] = Field(
        default_factory=dict,
        description="Variables to replace in template"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "template_code": "AUTH_VERIFICATION_CODE",
                "language": "es",
                "variables": {
                    "code": "123456"
                }
            }
        }


class SmsTemplateRenderResponse(BaseModel):
    """Response from rendering a template"""
    template_code: str
    language: str
    rendered_content: str
    character_count: int
    segment_count: int
    variables_used: Dict[str, Any]
