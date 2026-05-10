"""
Translation API Routes - CRUD operations for system translations

Endpoints:
- GET /translations/categories - List all categories
- GET /translations/stats - Get translation statistics
- GET /translations/export/{category} - Export category as JSON
- GET /translations - Search/list translations
- GET /translations/{translation_id} - Get translation by ID
- POST /translations - Create translation
- POST /translations/batch - Create multiple translations
- PUT /translations/{translation_id} - Update translation
- DELETE /translations/{translation_id} - Delete translation

Module: Translations (System translations for ENUMs, UI, Forms, Messages)

Note: entity_translations (for fiscal services) is in fiscal_services module
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Header
from loguru import logger
import asyncpg

from app.modules.translations.models.translation import (
    TranslationCreate,
    TranslationUpdate,
    TranslationResponse,
    TranslationBatchCreate,
    TranslationSearchParams,
    TranslationListResponse,
)
from app.modules.translations.models.category_metadata import enrich_categories, get_all_groups, get_categories_for_group
from app.modules.translations.services.translation_service import TranslationService
from app.modules.translations.services.language_service import LanguageService
from app.modules.translations.middleware.language_middleware import detect_language
from app.database.connection import get_database as get_db
from app.modules.auth.middleware.auth_middleware import get_current_user


router = APIRouter(prefix="/translations/system", tags=["System Translations"])


# ============================================================================
# UTILITY ENDPOINTS
# ============================================================================

@router.get("/categories")
async def list_categories(
    language: Optional[str] = Query(
        "es",
        description="Language code for labels (es, fr, en)",
        regex="^(es|fr|en)$"
    ),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Get list of all translation categories with localized labels

    Args:
        language: Language code for labels (default: es)

    Returns:
        List of categories with code, label, description, and DB associations
    """
    service = TranslationService()

    try:
        # Get raw category codes from database
        category_codes = await service.get_all_categories(conn)

        # Enrich with metadata (localized labels, DB associations)
        enriched_categories = enrich_categories(category_codes, language or "es")

        return {
            "categories": enriched_categories,
            "count": len(enriched_categories),
            "language": language or "es",
        }

    except Exception as e:
        logger.error(f"Error fetching categories: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/groups")
async def list_groups(
    language: Optional[str] = Query(
        "es",
        description="Language code for labels (es, fr, en)",
        regex="^(es|fr|en)$"
    ),
):
    """
    Get list of translation groups (ENUM types + functional groups)

    Groups are based on:
    - PostgreSQL ENUM types (declaration_status_enum, payment_method_enum, etc.)
    - Functional groups (ui, forms, messages, notifications, chatbot)

    Args:
        language: Language code for labels (default: es)

    Returns:
        List of groups with code, label, type, and DB associations
    """
    try:
        groups = get_all_groups(language or "es")

        return {
            "groups": groups,
            "count": len(groups),
            "language": language or "es",
        }

    except Exception as e:
        logger.error(f"Error fetching groups: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_translation_stats(
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Get translation statistics

    Returns:
        Statistics about translations (counts, sources, etc.)
    """
    service = TranslationService()

    try:
        stats = await service.get_translation_stats(conn)
        return stats

    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export/{category}")
async def export_category_json(
    category: str,
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Export all translations for a category as JSON

    Useful for frontend i18n files

    Args:
        category: Category to export (enum, ui.menu, etc.)

    Returns:
        JSON structure: {key_code: {es: "...", fr: "...", en: "..."}}
    """
    service = TranslationService()

    try:
        data = await service.export_category_json(conn, category)
        return data

    except Exception as e:
        logger.error(f"Error exporting category {category}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# CRUD ENDPOINTS
# ============================================================================

@router.post("/", response_model=TranslationResponse)
async def create_translation(
    translation: TranslationCreate,
    conn: asyncpg.Connection = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Create a single translation

    Args:
        translation: Translation data (category, key_code, es, fr, en)

    Returns:
        Created translation
    """
    service = TranslationService()

    try:
        user_id = current_user.get("sub")
        result = await service.create_translation(conn, translation, user_id)
        return result

    except Exception as e:
        logger.error(f"Error creating translation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch")
async def create_translation_batch(
    batch: TranslationBatchCreate,
    conn: asyncpg.Connection = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Create multiple translations at once

    Args:
        batch: Batch of translations

    Returns:
        List of created translations with count
    """
    service = TranslationService()

    try:
        user_id = current_user.get("sub")
        results = await service.batch_create(conn, batch, user_id)
        return {"created": len(results), "translations": results}

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating translation batch: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=TranslationListResponse)
async def search_translations(
    category: Optional[str] = Query(None, description="Filter by category"),
    group: Optional[str] = Query(None, description="Filter by group (ENUM type or functional group)"),
    key_code: Optional[str] = Query(None, description="Search in key_code"),
    context: Optional[str] = Query(None, description="Filter by context"),
    search_term: Optional[str] = Query(None, description="Full-text search"),
    limit: int = Query(100, ge=1, le=500, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Search and list translations

    Args:
        category: Optional category filter
        group: Optional group filter (filters by all categories belonging to this group)
        key_code: Optional key_code search (partial match)
        context: Optional context filter
        search_term: Optional full-text search in translations
        limit: Max results
        offset: Pagination offset

    Returns:
        Paginated list of translations
    """
    service = TranslationService()

    try:
        # If group is specified, get all categories for that group
        categories_in = None
        if group and not category:
            categories_in = get_categories_for_group(group)
            logger.debug(f"Group '{group}' resolved to categories: {categories_in}")

        search_params = TranslationSearchParams(
            category=category,
            categories_in=categories_in,
            key_code=key_code,
            context=context,
            search_term=search_term,
            limit=limit,
            offset=offset,
        )

        translations, total = await service.search_translations(conn, search_params)
        return {
            "translations": translations,
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    except Exception as e:
        logger.error(f"Error searching translations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{translation_id}", response_model=TranslationResponse)
async def get_translation(
    translation_id: int,
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Get translation by ID

    Args:
        translation_id: Translation ID

    Returns:
        Translation details
    """
    service = TranslationService()

    try:
        translation = await service.get_translation_by_id(conn, translation_id)

        if translation is None:
            raise HTTPException(status_code=404, detail="Translation not found")

        return translation

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching translation {translation_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{translation_id}", response_model=TranslationResponse)
async def update_translation(
    translation_id: int,
    update_data: TranslationUpdate,
    conn: asyncpg.Connection = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Update translation

    Args:
        translation_id: Translation ID
        update_data: Update data (es, fr, en, description, source)

    Returns:
        Updated translation
    """
    service = TranslationService()

    try:
        user_id = current_user.get("sub")
        result = await service.update_translation(
            conn, translation_id, update_data, user_id
        )

        if result is None:
            raise HTTPException(status_code=404, detail="Translation not found")

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating translation {translation_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{translation_id}")
async def delete_translation(
    translation_id: int,
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Delete a translation

    Args:
        translation_id: Translation ID

    Returns:
        Success message
    """
    service = TranslationService()

    try:
        deleted = await service.delete_translation(conn, translation_id)

        if not deleted:
            raise HTTPException(status_code=404, detail="Translation not found")

        return {"message": "Translation deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting translation {translation_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# LANGUAGE DETECTION (reuse from previous implementation)
# ============================================================================

@router.get("/languages")
async def list_supported_languages():
    """
    Get list of supported languages

    Returns:
        List of language information
    """
    language_service = LanguageService()
    return {
        "languages": language_service.get_language_info(),
        "default": language_service.get_default_language().value,
    }
