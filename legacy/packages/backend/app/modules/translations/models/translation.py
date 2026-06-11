"""
Translation Models - Pydantic models for system translations

For database schema, see: docs-internal/database/DATABASE_SCHEMA_REFERENCE.md
Table: translations (system-wide translations for ENUMs, UI, Forms, Messages)

Note: entity_translations (for fiscal services) is handled in fiscal_services module
"""

from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, UUID4


class TranslationCreate(BaseModel):
    """Model for creating a system translation"""
    category: str = Field(..., max_length=50, description="Category: enum, ui.menu, ui.button, form.label, system.message, fiscal.period")
    key_code: str = Field(..., max_length=255, description="Unique code (ex: user_role.citizen, dashboard, save)")
    context: Optional[str] = Field(None, max_length=100, description="Optional context (ex: user_role_enum, navigation)")
    es: str = Field(..., min_length=1, description="Spanish translation (default)")
    fr: str = Field(..., min_length=1, description="French translation")
    en: str = Field(..., min_length=1, description="English translation")
    description: Optional[str] = Field(None, description="Description/notes")
    translation_source: Optional[str] = Field("manual", max_length=50, description="Source: manual, import, ai_generated")

    class Config:
        json_schema_extra = {
            "example": {
                "category": "enum",
                "key_code": "payment_status.pending",
                "context": "payment_workflow",
                "es": "Pendiente",
                "fr": "En Attente",
                "en": "Pending",
                "description": "Payment status enum value",
                "translation_source": "manual"
            }
        }


class TranslationUpdate(BaseModel):
    """Model for updating a system translation"""
    es: Optional[str] = Field(None, min_length=1, description="Spanish translation")
    fr: Optional[str] = Field(None, min_length=1, description="French translation")
    en: Optional[str] = Field(None, min_length=1, description="English translation")
    description: Optional[str] = Field(None, description="Description/notes")
    translation_source: Optional[str] = Field(None, max_length=50, description="Source")

    class Config:
        json_schema_extra = {
            "example": {
                "es": "Pendiente (actualizado)",
                "fr": "En Attente (mis à jour)",
                "en": "Pending (updated)"
            }
        }


class TranslationResponse(BaseModel):
    """Model for translation response"""
    id: int
    category: str
    key_code: str
    context: Optional[str]
    es: str
    fr: str
    en: str
    description: Optional[str]
    translation_source: str
    created_at: datetime
    updated_at: datetime
    created_by: Optional[UUID4]
    updated_by: Optional[UUID4]
    version: int

    class Config:
        from_attributes = True


class TranslationBatchCreate(BaseModel):
    """Model for creating multiple translations at once"""
    translations: list[TranslationCreate] = Field(..., description="List of translations to create")

    class Config:
        json_schema_extra = {
            "example": {
                "translations": [
                    {
                        "category": "enum",
                        "key_code": "payment_status.pending",
                        "es": "Pendiente",
                        "fr": "En Attente",
                        "en": "Pending"
                    },
                    {
                        "category": "enum",
                        "key_code": "payment_status.completed",
                        "es": "Completado",
                        "fr": "Terminé",
                        "en": "Completed"
                    }
                ]
            }
        }


class TranslationSearchParams(BaseModel):
    """Model for translation search parameters"""
    category: Optional[str] = Field(None, description="Filter by category")
    categories_in: Optional[list[str]] = Field(None, description="Filter by multiple categories (for group filtering)")
    key_code: Optional[str] = Field(None, description="Search in key_code")
    context: Optional[str] = Field(None, description="Filter by context")
    search_term: Optional[str] = Field(None, description="Full-text search in translations (any language)")
    limit: int = Field(100, ge=1, le=500, description="Max results")
    offset: int = Field(0, ge=0, description="Pagination offset")

    class Config:
        json_schema_extra = {
            "example": {
                "category": "enum",
                "search_term": "pending",
                "limit": 50,
                "offset": 0
            }
        }


class TranslationListResponse(BaseModel):
    """Model for paginated translation list response"""
    translations: list[TranslationResponse]
    total: int
    limit: int
    offset: int

    class Config:
        json_schema_extra = {
            "example": {
                "translations": [],
                "total": 150,
                "limit": 100,
                "offset": 0
            }
        }
