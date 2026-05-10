"""
ENUM Management API Routes

Endpoints for managing PostgreSQL ENUM types:
- List modifiable ENUMs
- Get ENUM values with translation status
- Add new ENUM values
- Update ENUM translations
- Archive/Restore ENUM values

Module: Translations
Architecture: 3-tier (Routes -> Services -> Repositories)
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from loguru import logger
import asyncpg

from app.database.connection import get_database
from app.modules.auth.middleware.auth_middleware import get_current_user, get_current_admin_user
from app.modules.translations.services.enum_service import EnumService
from app.modules.translations.repositories.enum_repository import MODIFIABLE_ENUMS

router = APIRouter(prefix="/enums", tags=["enums"])
service = EnumService()


# =============================================================================
# Request/Response Models
# =============================================================================

class AddEnumValueRequest(BaseModel):
    """Request model for adding a new ENUM value"""
    value: str = Field(..., min_length=1, max_length=50, description="ENUM value (snake_case)")
    es: str = Field(..., min_length=1, description="Spanish translation")
    fr: str = Field(..., min_length=1, description="French translation")
    en: str = Field(..., min_length=1, description="English translation")


class UpdateEnumTranslationRequest(BaseModel):
    """Request model for updating ENUM value translation"""
    es: Optional[str] = Field(None, description="Spanish translation")
    fr: Optional[str] = Field(None, description="French translation")
    en: Optional[str] = Field(None, description="English translation")


# =============================================================================
# Routes
# =============================================================================

@router.get("/")
async def list_modifiable_enums(
    language: str = Query("es", description="Language for labels (es, fr, en)"),
    conn: asyncpg.Connection = Depends(get_database),
    _: None = Depends(get_current_admin_user),
):
    """
    List all modifiable ENUM types with metadata

    Returns list of ENUMs that can be modified from the UI.
    """
    try:
        enums = await service.get_modifiable_enums(conn, language)
        return {
            "enums": enums,
            "count": len(enums),
        }
    except Exception as e:
        logger.error(f"Error listing modifiable enums: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/{enum_name}")
async def get_enum_values(
    enum_name: str,
    language: str = Query("es", description="Language for display (es, fr, en)"),
    conn: asyncpg.Connection = Depends(get_database),
    _: None = Depends(get_current_admin_user),
):
    """
    Get all values for a specific ENUM with translation status

    Returns all values (active and archived) with their translations.
    """
    if enum_name not in MODIFIABLE_ENUMS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"ENUM '{enum_name}' is not modifiable. Allowed ENUMs: {MODIFIABLE_ENUMS}",
        )

    try:
        result = await service.get_enum_values_with_translations(conn, enum_name, language)
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting enum values for {enum_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/{enum_name}/values")
async def add_enum_value(
    enum_name: str,
    request: AddEnumValueRequest,
    conn: asyncpg.Connection = Depends(get_database),
    current_user = Depends(get_current_user),
    _: None = Depends(get_current_admin_user),
):
    """
    Add a new value to an ENUM type

    Creates the value in PostgreSQL ENUM and creates translation entry.
    """
    if enum_name not in MODIFIABLE_ENUMS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"ENUM '{enum_name}' is not modifiable. Allowed ENUMs: {MODIFIABLE_ENUMS}",
        )

    try:
        result = await service.add_enum_value(
            conn,
            enum_name,
            request.value,
            request.es,
            request.fr,
            request.en,
            user_id=current_user.id if current_user else None,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error adding enum value to {enum_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.put("/{enum_name}/values/{value}/translation")
async def update_enum_translation(
    enum_name: str,
    value: str,
    request: UpdateEnumTranslationRequest,
    conn: asyncpg.Connection = Depends(get_database),
    current_user = Depends(get_current_user),
    _: None = Depends(get_current_admin_user),
):
    """
    Update translation for an ENUM value

    Creates or updates the translation entry for an ENUM value.
    """
    if enum_name not in MODIFIABLE_ENUMS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"ENUM '{enum_name}' is not modifiable. Allowed ENUMs: {MODIFIABLE_ENUMS}",
        )

    try:
        result = await service.update_enum_translation(
            conn,
            enum_name,
            value,
            es=request.es,
            fr=request.fr,
            en=request.en,
            user_id=current_user.id if current_user else None,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating enum translation for {enum_name}.{value}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/{enum_name}/values/{value}/archive")
async def archive_enum_value(
    enum_name: str,
    value: str,
    conn: asyncpg.Connection = Depends(get_database),
    _: None = Depends(get_current_admin_user),
):
    """
    Archive an ENUM value

    Renames the value with _archived_ prefix.
    Cannot archive values that are currently in use.
    """
    if enum_name not in MODIFIABLE_ENUMS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"ENUM '{enum_name}' is not modifiable. Allowed ENUMs: {MODIFIABLE_ENUMS}",
        )

    try:
        result = await service.archive_enum_value(conn, enum_name, value)
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error archiving enum value {enum_name}.{value}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/{enum_name}/values/{value}/restore")
async def restore_enum_value(
    enum_name: str,
    value: str,
    conn: asyncpg.Connection = Depends(get_database),
    _: None = Depends(get_current_admin_user),
):
    """
    Restore an archived ENUM value

    Removes the _archived_ prefix from the value.
    """
    if enum_name not in MODIFIABLE_ENUMS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"ENUM '{enum_name}' is not modifiable. Allowed ENUMs: {MODIFIABLE_ENUMS}",
        )

    try:
        result = await service.restore_enum_value(conn, enum_name, value)
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error restoring enum value {enum_name}.{value}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/untranslated/list")
async def get_untranslated_enum_values(
    enum_name: Optional[str] = Query(None, description="Filter by specific ENUM"),
    conn: asyncpg.Connection = Depends(get_database),
    _: None = Depends(get_current_admin_user),
):
    """
    Get list of ENUM values without translations

    Useful for finding values that need to be translated.
    """
    try:
        if enum_name and enum_name not in MODIFIABLE_ENUMS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"ENUM '{enum_name}' is not modifiable. Allowed ENUMs: {MODIFIABLE_ENUMS}",
            )

        untranslated = await service.get_untranslated_enum_values(conn, enum_name)
        return {
            "untranslated": untranslated,
            "count": len(untranslated),
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting untranslated enum values: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
