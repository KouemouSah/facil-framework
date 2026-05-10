"""
Entity Translation API Routes - Admin CRUD for entity_translations

Endpoints for managing translations of ministries, sectors, categories.

Prefix: /api/v1/translations/entities
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
import asyncpg

from ..models.entity_translation import (
    EntityTranslationCreate,
    EntityTranslationUpdate,
    EntityTranslationResponse,
    EntityTranslationBulkCreate,
    EntityTranslationSearchParams,
    EntityTranslationListResponse,
    EntityTranslationGrouped,
    EntityTranslationStats,
    TranslatableEntityType,
    LanguageCode,
)
from ..services.entity_translation_service import EntityTranslationService
from app.database.connection import get_database as get_db
from app.modules.auth.middleware.auth_middleware import get_current_user


router = APIRouter(prefix="/translations/entities", tags=["Entity Translations"])


# ============================================================================
# UTILITY ENDPOINTS
# ============================================================================

@router.get("/types")
async def list_entity_types():
    """
    Get list of supported entity types

    Returns:
        List of entity types (ministry, sector, category)
    """
    return {
        "entity_types": [
            {"value": "ministry", "label": "Ministerios", "label_fr": "Ministères", "label_en": "Ministries"},
            {"value": "sector", "label": "Sectores", "label_fr": "Secteurs", "label_en": "Sectors"},
            {"value": "category", "label": "Categorías", "label_fr": "Catégories", "label_en": "Categories"},
            {"value": "service", "label": "Servicios Fiscales", "label_fr": "Services Fiscaux", "label_en": "Fiscal Services"},
            {"value": "procedure_template", "label": "Procedimientos", "label_fr": "Procédures", "label_en": "Procedures"},
            {"value": "procedure_step", "label": "Pasos de Procedimiento", "label_fr": "Étapes de Procédure", "label_en": "Procedure Steps"},
            {"value": "document_template", "label": "Plantillas de Documento", "label_fr": "Modèles de Document", "label_en": "Document Templates"},
        ]
    }


@router.get("/stats", response_model=EntityTranslationStats)
async def get_entity_translation_stats(
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Get entity translation statistics

    Returns:
        Statistics about translations by type, language, field
    """
    service = EntityTranslationService()

    try:
        stats = await service.get_stats(conn)
        return stats

    except Exception as e:
        logger.error(f"Error fetching entity translation stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list/{entity_type}")
async def list_entities_for_type(
    entity_type: TranslatableEntityType,
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    List distinct entity codes for an entity type

    Args:
        entity_type: Entity type (ministry, sector, category)

    Returns:
        List of entity codes
    """
    service = EntityTranslationService()

    try:
        entities = await service.list_entities_by_type(conn, entity_type.value)
        return {"entity_type": entity_type.value, "entities": entities, "count": len(entities)}

    except Exception as e:
        logger.error(f"Error listing entities for {entity_type}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export/{entity_type}")
async def export_entity_translations(
    entity_type: TranslatableEntityType,
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Export all translations for an entity type

    Args:
        entity_type: Entity type to export

    Returns:
        List of {entity_code, translations: {field: {es, fr, en}}}
    """
    service = EntityTranslationService()

    try:
        data = await service.export_by_type(conn, entity_type.value)
        return {
            "entity_type": entity_type.value,
            "count": len(data),
            "data": data,
        }

    except Exception as e:
        logger.error(f"Error exporting {entity_type} translations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/source/{entity_type}")
async def list_source_entities(
    entity_type: TranslatableEntityType,
    search: Optional[str] = Query(None, description="Search term for name or code"),
    limit: int = Query(50, ge=1, le=200, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    untranslated_only: bool = Query(False, description="Only show entities without translations"),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    List entities from source table with Spanish content

    This endpoint allows browsing entities by type to select which one to translate.

    Args:
        entity_type: Entity type (ministry, sector, category, service, etc.)
        search: Optional search term
        limit: Max results
        offset: Pagination offset
        untranslated_only: If True, only return entities without any translations

    Returns:
        List of {entity_code, name_es, description_es}
    """
    service = EntityTranslationService()

    try:
        entities, total = await service.list_source_entities(
            conn, entity_type.value, search, limit, offset, untranslated_only
        )
        return {
            "entity_type": entity_type.value,
            "entities": entities,
            "total": total,
            "limit": limit,
            "offset": offset,
            "untranslated_only": untranslated_only,
        }

    except Exception as e:
        logger.error(f"Error listing source entities for {entity_type}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/source/{entity_type}/{entity_code}")
async def get_source_content(
    entity_type: TranslatableEntityType,
    entity_code: str,
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Get Spanish source content from the source table

    This endpoint fetches the Spanish content that will be translated.
    Used by the Translation Workbench to show the source text.

    Args:
        entity_type: Entity type
        entity_code: Entity code (or id for procedure_step)

    Returns:
        {entity_type, entity_code, source_language: "es", fields: {name: "...", description: "..."}}
    """
    service = EntityTranslationService()

    try:
        result = await service.get_source_content(conn, entity_type.value, entity_code)

        if result is None:
            raise HTTPException(status_code=404, detail=f"Entity not found: {entity_type.value}/{entity_code}")

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching source content for {entity_type}/{entity_code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# CRUD ENDPOINTS
# ============================================================================

@router.post("/", response_model=EntityTranslationResponse)
async def create_entity_translation(
    translation: EntityTranslationCreate,
    conn: asyncpg.Connection = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Create a single entity translation

    Args:
        translation: Translation data

    Returns:
        Created translation
    """
    service = EntityTranslationService()

    try:
        result = await service.create_translation(conn, translation)
        return result

    except Exception as e:
        logger.error(f"Error creating entity translation: {e}")
        if "duplicate key" in str(e).lower():
            raise HTTPException(status_code=409, detail="Translation already exists. Use PUT to update.")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upsert", response_model=EntityTranslationResponse)
async def upsert_entity_translation(
    translation: EntityTranslationCreate,
    conn: asyncpg.Connection = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Create or update entity translation (upsert)

    Args:
        translation: Translation data

    Returns:
        Translation (created or updated)
    """
    service = EntityTranslationService()

    try:
        result = await service.upsert_translation(conn, translation)
        return result

    except Exception as e:
        logger.error(f"Error upserting entity translation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bulk", response_model=Dict[str, Any])
async def bulk_upsert_entity_translations(
    batch: EntityTranslationBulkCreate,
    conn: asyncpg.Connection = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Bulk create/update entity translations

    Each item contains all 3 languages for one entity field.

    Args:
        batch: Batch of translations

    Returns:
        Count and list of created/updated translations
    """
    service = EntityTranslationService()

    try:
        results = await service.bulk_upsert(conn, batch)
        return {
            "created": len(results),
            "translations": results,
        }

    except Exception as e:
        logger.error(f"Error bulk upserting entity translations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/import")
async def import_entity_translations(
    data: List[Dict[str, Any]],
    conn: asyncpg.Connection = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Import translations from export format

    Args:
        data: List of {entity_type, entity_code, translations: {field: {es, fr, en}}}

    Returns:
        Import result with counts
    """
    service = EntityTranslationService()

    try:
        result = await service.import_translations(conn, data)
        return result

    except Exception as e:
        logger.error(f"Error importing entity translations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=EntityTranslationListResponse)
async def search_entity_translations(
    entity_type: Optional[TranslatableEntityType] = Query(None, description="Filter by entity type"),
    entity_code: Optional[str] = Query(None, description="Filter by entity code (partial match)"),
    language_code: Optional[LanguageCode] = Query(None, description="Filter by language"),
    field_name: Optional[str] = Query(None, description="Filter by field name"),
    search_term: Optional[str] = Query(None, description="Search in translation text"),
    limit: int = Query(100, ge=1, le=500, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Search entity translations with filters

    Args:
        entity_type: Optional entity type filter
        entity_code: Optional entity code search (partial)
        language_code: Optional language filter
        field_name: Optional field name filter
        search_term: Optional text search
        limit: Max results
        offset: Pagination offset

    Returns:
        Paginated list of translations
    """
    service = EntityTranslationService()

    try:
        params = EntityTranslationSearchParams(
            entity_type=entity_type,
            entity_code=entity_code,
            language_code=language_code,
            field_name=field_name,
            search_term=search_term,
            limit=limit,
            offset=offset,
        )

        translations, total = await service.search_translations(conn, params)
        return {
            "translations": translations,
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    except Exception as e:
        logger.error(f"Error searching entity translations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{entity_type}/{entity_code}", response_model=EntityTranslationGrouped)
async def get_entity_all_translations(
    entity_type: TranslatableEntityType,
    entity_code: str,
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Get all translations for a specific entity

    Args:
        entity_type: Entity type
        entity_code: Entity code

    Returns:
        Grouped translations {entity_type, entity_code, translations: {field: {es, fr, en}}}
    """
    service = EntityTranslationService()

    try:
        result = await service.get_entity_all_translations(conn, entity_type.value, entity_code)
        return result

    except Exception as e:
        logger.error(f"Error fetching entity translations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{entity_type}/{entity_code}/{language_code}/{field_name}", response_model=EntityTranslationResponse)
async def get_single_entity_translation(
    entity_type: TranslatableEntityType,
    entity_code: str,
    language_code: LanguageCode,
    field_name: str,
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Get a single entity translation by composite key

    Args:
        entity_type: Entity type
        entity_code: Entity code
        language_code: Language code
        field_name: Field name

    Returns:
        Translation details
    """
    service = EntityTranslationService()

    try:
        result = await service.get_translation_by_key(
            conn, entity_type.value, entity_code, language_code.value, field_name
        )

        if result is None:
            raise HTTPException(status_code=404, detail="Translation not found")

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching entity translation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{entity_type}/{entity_code}/{language_code}/{field_name}", response_model=EntityTranslationResponse)
async def update_entity_translation(
    entity_type: TranslatableEntityType,
    entity_code: str,
    language_code: LanguageCode,
    field_name: str,
    update_data: EntityTranslationUpdate,
    conn: asyncpg.Connection = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Update an entity translation

    Args:
        entity_type: Entity type
        entity_code: Entity code
        language_code: Language code
        field_name: Field name
        update_data: Update data

    Returns:
        Updated translation
    """
    service = EntityTranslationService()

    try:
        result = await service.update_translation(
            conn,
            entity_type.value,
            entity_code,
            language_code.value,
            field_name,
            update_data,
        )

        if result is None:
            raise HTTPException(status_code=404, detail="Translation not found")

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating entity translation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{entity_type}/{entity_code}/{language_code}/{field_name}")
async def delete_entity_translation(
    entity_type: TranslatableEntityType,
    entity_code: str,
    language_code: LanguageCode,
    field_name: str,
    conn: asyncpg.Connection = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Delete a single entity translation

    Args:
        entity_type: Entity type
        entity_code: Entity code
        language_code: Language code
        field_name: Field name

    Returns:
        Success message
    """
    service = EntityTranslationService()

    try:
        deleted = await service.delete_translation(
            conn, entity_type.value, entity_code, language_code.value, field_name
        )

        if not deleted:
            raise HTTPException(status_code=404, detail="Translation not found")

        return {"message": "Translation deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting entity translation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{entity_type}/{entity_code}")
async def delete_all_entity_translations(
    entity_type: TranslatableEntityType,
    entity_code: str,
    conn: asyncpg.Connection = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Delete all translations for an entity

    Args:
        entity_type: Entity type
        entity_code: Entity code

    Returns:
        Count of deleted translations
    """
    service = EntityTranslationService()

    try:
        count = await service.delete_entity_translations(conn, entity_type.value, entity_code)
        return {"message": f"Deleted {count} translations", "count": count}

    except Exception as e:
        logger.error(f"Error deleting entity translations: {e}")
        raise HTTPException(status_code=500, detail=str(e))
