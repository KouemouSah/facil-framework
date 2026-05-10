"""
Translation Service - Business logic for system translations

Handles:
- Creating and managing system translations (ENUMs, UI, Forms, Messages)
- Translation lookups with fallback support
- Batch operations
- Search and filtering

Module: Translations
Architecture: 3-tier (Routes → Services → Repositories)

Note: entity_translations (for fiscal services) is in fiscal_services module
"""

from typing import Dict, Optional, List
from uuid import UUID
from loguru import logger
import asyncpg

from app.modules.translations.repositories.translation_repository import TranslationRepository
from app.modules.translations.models.language import Language
from app.modules.translations.models.translation import (
    TranslationCreate,
    TranslationUpdate,
    TranslationBatchCreate,
    TranslationSearchParams,
)
from app.core.cache import get_translations_cache, CacheKeys, invalidate_translations_cache


class TranslationService:
    """Service for system translation business logic"""

    def __init__(self):
        """Initialize translation service"""
        self.repo = TranslationRepository()
        logger.info("TranslationService initialized")

    async def create_translation(
        self,
        conn: asyncpg.Connection,
        translation: TranslationCreate,
        user_id: Optional[UUID] = None,
    ) -> Dict:
        """
        Create a system translation

        Args:
            conn: Database connection
            translation: Translation data
            user_id: User creating the translation

        Returns:
            Created translation
        """
        result = await self.repo.create(
            conn,
            translation.category,
            translation.key_code,
            translation.es,
            translation.fr,
            translation.en,
            translation.context,
            translation.description,
            translation.translation_source or "manual",
            user_id,
        )
        await invalidate_translations_cache()
        return result

    async def upsert_translation(
        self,
        conn: asyncpg.Connection,
        translation: TranslationCreate,
        user_id: Optional[UUID] = None,
    ) -> Dict:
        """
        Create or update translation (upsert)

        Args:
            conn: Database connection
            translation: Translation data
            user_id: User upserting the translation

        Returns:
            Translation
        """
        result = await self.repo.upsert(
            conn,
            translation.category,
            translation.key_code,
            translation.es,
            translation.fr,
            translation.en,
            translation.context,
            translation.description,
            translation.translation_source or "manual",
            user_id,
        )
        await invalidate_translations_cache()
        return result

    async def batch_create(
        self,
        conn: asyncpg.Connection,
        batch: TranslationBatchCreate,
        user_id: Optional[UUID] = None,
    ) -> List[Dict]:
        """
        Create multiple translations in batch

        Args:
            conn: Database connection
            batch: Batch of translations
            user_id: User creating the translations

        Returns:
            List of created translations
        """
        translations_data = [
            {
                "category": t.category,
                "key_code": t.key_code,
                "es": t.es,
                "fr": t.fr,
                "en": t.en,
                "context": t.context,
                "description": t.description,
                "translation_source": t.translation_source or "import",
            }
            for t in batch.translations
        ]

        results = await self.repo.batch_create(conn, translations_data, user_id)

        logger.info(f"Batch created {len(results)} translations")
        return results

    async def get_translation_by_id(
        self,
        conn: asyncpg.Connection,
        translation_id: int,
    ) -> Optional[Dict]:
        """
        Get translation by ID

        Args:
            conn: Database connection
            translation_id: Translation ID

        Returns:
            Translation or None
        """
        return await self.repo.get_by_id(conn, translation_id)

    async def get_translation_by_key(
        self,
        conn: asyncpg.Connection,
        category: str,
        key_code: str,
        context: Optional[str] = None,
    ) -> Optional[Dict]:
        """
        Get translation by category, key_code, and context

        Args:
            conn: Database connection
            category: Category
            key_code: Key code
            context: Optional context

        Returns:
            Translation or None
        """
        return await self.repo.get_by_key(conn, category, key_code, context)

    async def get_translation_content(
        self,
        conn: asyncpg.Connection,
        category: str,
        key_code: str,
        language: Language = None,
        context: Optional[str] = None,
        fallback: bool = True,
    ) -> Optional[str]:
        """
        Get translation content for specific language with fallback

        Args:
            conn: Database connection
            category: Category
            key_code: Key code
            language: Desired language (default: Spanish)
            context: Optional context
            fallback: If True, fallback to Spanish if not found

        Returns:
            Translated content or None
        """
        if language is None:
            language = Language.SPANISH

        # Try requested language
        content = await self.repo.get_translation(
            conn,
            category,
            key_code,
            language.value,
            context,
        )

        # Fallback to Spanish if not found
        if content is None and fallback and language != Language.SPANISH:
            content = await self.repo.get_translation(
                conn,
                category,
                key_code,
                Language.SPANISH.value,
                context,
            )

        return content

    async def list_by_category(
        self,
        conn: asyncpg.Connection,
        category: str,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[List[Dict], int]:
        """
        List translations by category

        Args:
            conn: Database connection
            category: Category filter
            limit: Max results
            offset: Pagination offset

        Returns:
            Tuple of (translations list, total count)
        """
        return await self.repo.list_by_category(conn, category, limit, offset)

    async def search_translations(
        self,
        conn: asyncpg.Connection,
        search_params: TranslationSearchParams,
    ) -> tuple[List[Dict], int]:
        """
        Search translations with filters

        Args:
            conn: Database connection
            search_params: Search parameters

        Returns:
            Tuple of (translations list, total count)
        """
        return await self.repo.search(
            conn,
            search_params.category,
            search_params.categories_in,
            search_params.key_code,
            search_params.context,
            search_params.search_term,
            search_params.limit,
            search_params.offset,
        )

    async def update_translation(
        self,
        conn: asyncpg.Connection,
        translation_id: int,
        update_data: TranslationUpdate,
        user_id: Optional[UUID] = None,
    ) -> Optional[Dict]:
        """
        Update translation

        Args:
            conn: Database connection
            translation_id: Translation ID
            update_data: Update data
            user_id: User updating the translation

        Returns:
            Updated translation or None
        """
        result = await self.repo.update(
            conn,
            translation_id,
            update_data.es,
            update_data.fr,
            update_data.en,
            update_data.description,
            update_data.translation_source,
            user_id,
        )
        if result:
            await invalidate_translations_cache()
        return result

    async def delete_translation(
        self,
        conn: asyncpg.Connection,
        translation_id: int,
    ) -> bool:
        """
        Delete a translation

        Args:
            conn: Database connection
            translation_id: Translation ID

        Returns:
            True if deleted
        """
        deleted = await self.repo.delete(conn, translation_id)
        if deleted:
            await invalidate_translations_cache()
        return deleted

    async def get_all_categories(
        self,
        conn: asyncpg.Connection,
    ) -> List[str]:
        """
        Get list of all unique categories

        Args:
            conn: Database connection

        Returns:
            List of category strings
        """
        query = """
            SELECT DISTINCT category
            FROM translations
            ORDER BY category
        """
        results = await conn.fetch(query)
        return [row["category"] for row in results]

    async def get_translation_stats(
        self,
        conn: asyncpg.Connection,
    ) -> Dict:
        """
        Get translation statistics

        Args:
            conn: Database connection

        Returns:
            Dict with statistics
        """
        query = """
            SELECT
                COUNT(*) as total_translations,
                COUNT(DISTINCT category) as total_categories,
                COUNT(DISTINCT key_code) as unique_keys,
                COUNT(*) FILTER (WHERE translation_source = 'manual') as manual_count,
                COUNT(*) FILTER (WHERE translation_source = 'import') as import_count,
                COUNT(*) FILTER (WHERE translation_source = 'ai_generated') as ai_count
            FROM translations
        """
        result = await conn.fetchrow(query)

        return {
            "total_translations": result["total_translations"],
            "total_categories": result["total_categories"],
            "unique_keys": result["unique_keys"],
            "by_source": {
                "manual": result["manual_count"],
                "import": result["import_count"],
                "ai_generated": result["ai_count"],
            },
        }

    async def export_category_json(
        self,
        conn: asyncpg.Connection,
        category: str,
    ) -> Dict[str, Dict[str, str]]:
        """
        Export category translations in JSON format for frontend

        Uses translations cache (1h TTL) since translation data rarely changes.

        Args:
            conn: Database connection
            category: Category to export

        Returns:
            Dict structure: {key_code: {es: "...", fr: "...", en: "..."}}
        """
        # Check cache first (keyed by category, all languages)
        cache = get_translations_cache()
        cache_key = CacheKeys.translations("all", category)

        cached = await cache.get(cache_key)
        if cached is not None:
            logger.debug(f"Translation cache HIT for category {category}")
            return cached

        # Cache miss - query DB
        logger.debug(f"Translation cache MISS for category {category}")
        query = """
            SELECT key_code, es, fr, en
            FROM translations
            WHERE category = $1
            ORDER BY key_code
        """
        results = await conn.fetch(query, category)

        data = {
            row["key_code"]: {
                "es": row["es"],
                "fr": row["fr"],
                "en": row["en"],
            }
            for row in results
        }

        # Store in cache (1h TTL from get_translations_cache default)
        await cache.set(cache_key, data)

        return data
