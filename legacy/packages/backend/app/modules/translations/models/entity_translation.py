"""
Entity Translation Models - Pydantic models for entity_translations table

For database schema, see: docs-internal/database/DATABASE_SCHEMA_REFERENCE.md
Table: entity_translations (ministry, sector, category, service, procedure_template translations)

Primary Key: (entity_type, entity_code, language_code, field_name)
ENUM: translatable_entity_type = ministry, sector, category, service, procedure_template
"""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum


class TranslatableEntityType(str, Enum):
    """Entity types that support translations in entity_translations table"""
    MINISTRY = "ministry"
    SECTOR = "sector"
    CATEGORY = "category"
    SERVICE = "service"
    PROCEDURE_TEMPLATE = "procedure_template"
    PROCEDURE_STEP = "procedure_step"
    DOCUMENT_TEMPLATE = "document_template"


class LanguageCode(str, Enum):
    """Supported language codes"""
    ES = "es"
    FR = "fr"
    EN = "en"


class EntityTranslationCreate(BaseModel):
    """Model for creating an entity translation"""
    entity_type: TranslatableEntityType = Field(..., description="Entity type (ministry, sector, category)")
    entity_code: str = Field(..., max_length=100, description="Unique entity identifier code")
    language_code: LanguageCode = Field(..., description="Language code (es, fr, en)")
    field_name: str = Field(..., max_length=30, description="Field being translated (name, description)")
    translation_text: str = Field(..., min_length=1, description="The actual translation")
    translation_source: Optional[str] = Field("manual", max_length=20, description="Source: manual, import, ai_generated")
    translation_quality: Optional[float] = Field(None, ge=0, le=100, description="Quality score 0-100")

    class Config:
        json_schema_extra = {
            "example": {
                "entity_type": "ministry",
                "entity_code": "MINHACIENDA",
                "language_code": "fr",
                "field_name": "name",
                "translation_text": "Ministère des Finances",
                "translation_source": "manual",
                "translation_quality": 100
            }
        }


class EntityTranslationUpdate(BaseModel):
    """Model for updating an entity translation"""
    translation_text: Optional[str] = Field(None, min_length=1, description="The actual translation")
    translation_source: Optional[str] = Field(None, max_length=20, description="Source")
    translation_quality: Optional[float] = Field(None, ge=0, le=100, description="Quality score")

    class Config:
        json_schema_extra = {
            "example": {
                "translation_text": "Ministère des Finances et du Budget",
                "translation_quality": 95
            }
        }


class EntityTranslationResponse(BaseModel):
    """Model for entity translation response"""
    entity_type: str
    entity_code: str
    language_code: str
    field_name: str
    translation_text: str
    translation_source: Optional[str]
    translation_quality: Optional[float]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class EntityTranslationBulkItem(BaseModel):
    """Single item for bulk operations - all 3 languages for one entity field"""
    entity_type: TranslatableEntityType
    entity_code: str = Field(..., max_length=100)
    field_name: str = Field(..., max_length=30)
    es: str = Field(..., min_length=1, description="Spanish translation")
    fr: str = Field(..., min_length=1, description="French translation")
    en: str = Field(..., min_length=1, description="English translation")
    translation_source: Optional[str] = Field("manual", max_length=20)

    class Config:
        json_schema_extra = {
            "example": {
                "entity_type": "ministry",
                "entity_code": "MINHACIENDA",
                "field_name": "name",
                "es": "Ministerio de Hacienda",
                "fr": "Ministère des Finances",
                "en": "Ministry of Finance"
            }
        }


class EntityTranslationBulkCreate(BaseModel):
    """Model for creating multiple entity translations at once"""
    translations: List[EntityTranslationBulkItem] = Field(..., description="List of translations")

    class Config:
        json_schema_extra = {
            "example": {
                "translations": [
                    {
                        "entity_type": "ministry",
                        "entity_code": "MINHACIENDA",
                        "field_name": "name",
                        "es": "Ministerio de Hacienda",
                        "fr": "Ministère des Finances",
                        "en": "Ministry of Finance"
                    }
                ]
            }
        }


class EntityTranslationSearchParams(BaseModel):
    """Model for entity translation search parameters"""
    entity_type: Optional[TranslatableEntityType] = Field(None, description="Filter by entity type")
    entity_code: Optional[str] = Field(None, description="Filter by entity code (partial match)")
    language_code: Optional[LanguageCode] = Field(None, description="Filter by language")
    field_name: Optional[str] = Field(None, description="Filter by field name")
    search_term: Optional[str] = Field(None, description="Full-text search in translation_text")
    limit: int = Field(100, ge=1, le=500, description="Max results")
    offset: int = Field(0, ge=0, description="Pagination offset")


class EntityTranslationListResponse(BaseModel):
    """Model for paginated entity translation list response"""
    translations: List[EntityTranslationResponse]
    total: int
    limit: int
    offset: int


class EntityTranslationGrouped(BaseModel):
    """Grouped translations for one entity (all languages, all fields)"""
    entity_type: str
    entity_code: str
    translations: dict  # {field_name: {es: "", fr: "", en: ""}}

    class Config:
        json_schema_extra = {
            "example": {
                "entity_type": "ministry",
                "entity_code": "MINHACIENDA",
                "translations": {
                    "name": {
                        "es": "Ministerio de Hacienda",
                        "fr": "Ministère des Finances",
                        "en": "Ministry of Finance"
                    },
                    "description": {
                        "es": "Gestiona las finanzas públicas",
                        "fr": "Gère les finances publiques",
                        "en": "Manages public finances"
                    }
                }
            }
        }


class EntityTranslationStats(BaseModel):
    """Statistics about entity translations"""
    total_translations: int
    by_entity_type: dict  # {ministry: count, sector: count, category: count}
    by_language: dict  # {es: count, fr: count, en: count}
    by_field: dict  # {name: count, description: count}
    distinct_entities: dict = {}  # {ministry: count, sector: count, category: count}
