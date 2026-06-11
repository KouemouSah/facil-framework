"""
ENUM Service - Business logic for PostgreSQL ENUM management

Handles:
- Listing ENUM values with translation status
- Adding new ENUM values + creating translations
- Archiving ENUM values
- Validating operations

Module: Translations
Architecture: 3-tier (Routes -> Services -> Repositories)
"""

from typing import Dict, List, Optional, Any
from uuid import UUID
from loguru import logger
import asyncpg

from app.modules.translations.repositories.enum_repository import (
    EnumRepository,
    MODIFIABLE_ENUMS,
    ARCHIVED_PREFIX,
)
from app.modules.translations.repositories.translation_repository import TranslationRepository


class EnumService:
    """Service for ENUM management business logic"""

    def __init__(self):
        self.enum_repo = EnumRepository()
        self.translation_repo = TranslationRepository()
        logger.info("EnumService initialized")

    async def get_modifiable_enums(
        self,
        conn: asyncpg.Connection,
        language: str = "es",
    ) -> List[Dict[str, Any]]:
        """
        Get list of all modifiable ENUM types with metadata

        Args:
            conn: Database connection
            language: Language for labels

        Returns:
            List of ENUM metadata
        """
        # Get enum labels from translations
        labels = {
            "user_role_enum": {
                "es": "Roles de Usuario",
                "fr": "Rôles Utilisateur",
                "en": "User Roles",
            },
            "declaration_status_enum": {
                "es": "Estados de Declaración",
                "fr": "Statuts de Déclaration",
                "en": "Declaration Status",
            },
            "payment_status_enum": {
                "es": "Estados de Pago",
                "fr": "Statuts de Paiement",
                "en": "Payment Status",
            },
            "document_status_enum": {
                "es": "Estados de Documento",
                "fr": "Statuts de Document",
                "en": "Document Status",
            },
            "service_type_enum": {
                "es": "Tipos de Servicio",
                "fr": "Types de Service",
                "en": "Service Types",
            },
            "calculation_method_enum": {
                "es": "Métodos de Cálculo",
                "fr": "Méthodes de Calcul",
                "en": "Calculation Methods",
            },
        }

        result = []
        for enum_name in MODIFIABLE_ENUMS:
            values = await self.enum_repo.get_enum_values(conn, enum_name)
            active_values = [v for v in values if not v.startswith(ARCHIVED_PREFIX)]
            archived_values = [v for v in values if v.startswith(ARCHIVED_PREFIX)]

            result.append({
                "enum_name": enum_name,
                "label": labels.get(enum_name, {}).get(language, enum_name),
                "total_values": len(values),
                "active_count": len(active_values),
                "archived_count": len(archived_values),
            })

        return result

    async def get_enum_values_with_translations(
        self,
        conn: asyncpg.Connection,
        enum_name: str,
        language: str = "es",
    ) -> Dict[str, Any]:
        """
        Get all values for an ENUM with their translation status

        Args:
            conn: Database connection
            enum_name: Name of the ENUM type
            language: Language code for display

        Returns:
            Dict with enum info and values list
        """
        if enum_name not in MODIFIABLE_ENUMS:
            raise ValueError(f"ENUM '{enum_name}' is not modifiable")

        # Get all ENUM values from PostgreSQL
        values_with_status = await self.enum_repo.get_enum_values_with_status(conn, enum_name)

        # Get translation category for this enum
        category = enum_name.replace("_enum", "")

        # Get translations for all values
        result_values = []
        for value_info in values_with_status:
            value = value_info["value"]
            display_value = value_info["display_value"]

            # Get translation from translations table
            translation = await self.translation_repo.get_by_key(
                conn, category, display_value, None
            )

            has_translation = translation is not None

            result_values.append({
                "value": value,
                "display_value": display_value,
                "is_archived": value_info["is_archived"],
                "usage_count": value_info["usage_count"],
                "can_archive": value_info["can_archive"],
                "has_translation": has_translation,
                "translation_id": translation["id"] if translation else None,
                "es": translation["es"] if translation else None,
                "fr": translation["fr"] if translation else None,
                "en": translation["en"] if translation else None,
            })

        return {
            "enum_name": enum_name,
            "category": category,
            "values": result_values,
            "total": len(result_values),
            "with_translation": sum(1 for v in result_values if v["has_translation"]),
            "without_translation": sum(1 for v in result_values if not v["has_translation"]),
        }

    async def add_enum_value(
        self,
        conn: asyncpg.Connection,
        enum_name: str,
        value: str,
        es: str,
        fr: str,
        en: str,
        user_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """
        Add a new value to an ENUM type and create its translation

        Args:
            conn: Database connection
            enum_name: Name of the ENUM type
            value: New value to add (snake_case)
            es: Spanish translation
            fr: French translation
            en: English translation
            user_id: User performing the action

        Returns:
            Dict with created value and translation info
        """
        # Validate enum is modifiable
        if enum_name not in MODIFIABLE_ENUMS:
            raise ValueError(f"ENUM '{enum_name}' is not modifiable")

        # Add the value to PostgreSQL ENUM type
        await self.enum_repo.add_enum_value(conn, enum_name, value)

        # Create translation entry
        category = enum_name.replace("_enum", "")
        translation = await self.translation_repo.create(
            conn,
            category=category,
            key_code=value,
            es=es,
            fr=fr,
            en=en,
            context=None,
            description=f"ENUM value for {enum_name}",
            translation_source="manual",
            user_id=user_id,
        )

        logger.info(f"Added ENUM value '{value}' to {enum_name} with translation")

        return {
            "enum_name": enum_name,
            "value": value,
            "translation": translation,
            "message": f"Value '{value}' added successfully to {enum_name}",
        }

    async def update_enum_translation(
        self,
        conn: asyncpg.Connection,
        enum_name: str,
        value: str,
        es: Optional[str] = None,
        fr: Optional[str] = None,
        en: Optional[str] = None,
        user_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """
        Update translation for an ENUM value

        Args:
            conn: Database connection
            enum_name: Name of the ENUM type
            value: ENUM value to update translation for
            es: Spanish translation (optional)
            fr: French translation (optional)
            en: English translation (optional)
            user_id: User performing the action

        Returns:
            Updated translation
        """
        if enum_name not in MODIFIABLE_ENUMS:
            raise ValueError(f"ENUM '{enum_name}' is not modifiable")

        # Get display value (remove _archived_ prefix if present)
        display_value = value
        if value.startswith(ARCHIVED_PREFIX):
            display_value = value[len(ARCHIVED_PREFIX):]

        # Get or create translation
        category = enum_name.replace("_enum", "")
        existing = await self.translation_repo.get_by_key(conn, category, display_value, None)

        if existing:
            # Update existing translation
            updated = await self.translation_repo.update(
                conn,
                existing["id"],
                es=es,
                fr=fr,
                en=en,
                translation_source="manual",
                user_id=user_id,
            )
            return updated
        else:
            # Create new translation
            created = await self.translation_repo.create(
                conn,
                category=category,
                key_code=display_value,
                es=es or display_value,
                fr=fr or display_value,
                en=en or display_value,
                context=None,
                description=f"ENUM value for {enum_name}",
                translation_source="manual",
                user_id=user_id,
            )
            return created

    async def archive_enum_value(
        self,
        conn: asyncpg.Connection,
        enum_name: str,
        value: str,
    ) -> Dict[str, Any]:
        """
        Archive an ENUM value (rename to _archived_ prefix)

        Args:
            conn: Database connection
            enum_name: Name of the ENUM type
            value: Value to archive

        Returns:
            Result with archived value info
        """
        if enum_name not in MODIFIABLE_ENUMS:
            raise ValueError(f"ENUM '{enum_name}' is not modifiable")

        # Archive the value in PostgreSQL ENUM
        await self.enum_repo.archive_enum_value(conn, enum_name, value)

        logger.info(f"Archived ENUM value '{value}' in {enum_name}")

        return {
            "enum_name": enum_name,
            "original_value": value,
            "archived_value": f"{ARCHIVED_PREFIX}{value}",
            "message": f"Value '{value}' has been archived",
        }

    async def restore_enum_value(
        self,
        conn: asyncpg.Connection,
        enum_name: str,
        archived_value: str,
    ) -> Dict[str, Any]:
        """
        Restore an archived ENUM value

        Args:
            conn: Database connection
            enum_name: Name of the ENUM type
            archived_value: Archived value to restore

        Returns:
            Result with restored value info
        """
        if enum_name not in MODIFIABLE_ENUMS:
            raise ValueError(f"ENUM '{enum_name}' is not modifiable")

        # Restore the value
        await self.enum_repo.restore_enum_value(conn, enum_name, archived_value)

        original_value = archived_value[len(ARCHIVED_PREFIX):]
        logger.info(f"Restored ENUM value '{original_value}' in {enum_name}")

        return {
            "enum_name": enum_name,
            "archived_value": archived_value,
            "restored_value": original_value,
            "message": f"Value '{original_value}' has been restored",
        }

    async def get_untranslated_enum_values(
        self,
        conn: asyncpg.Connection,
        enum_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get ENUM values that don't have translations yet

        Args:
            conn: Database connection
            enum_name: Optional filter by specific ENUM

        Returns:
            List of untranslated values
        """
        enums_to_check = [enum_name] if enum_name else MODIFIABLE_ENUMS
        untranslated = []

        for enum in enums_to_check:
            if enum not in MODIFIABLE_ENUMS:
                continue

            values = await self.enum_repo.get_active_enum_values(conn, enum)
            category = enum.replace("_enum", "")

            for value in values:
                translation = await self.translation_repo.get_by_key(conn, category, value, None)
                if not translation:
                    untranslated.append({
                        "enum_name": enum,
                        "category": category,
                        "value": value,
                    })

        return untranslated
