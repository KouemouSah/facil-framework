"""
Translation Repository - Data access layer for system translations

Handles:
- translations table (system-wide translations for ENUMs, UI, Forms, Messages)

Schema reference: docs-internal/database/DATABASE_SCHEMA_REFERENCE.md

Note: entity_translations (for fiscal services) is in fiscal_services module
"""

from typing import Optional, List, Dict, Any
from uuid import UUID
from loguru import logger
import asyncpg


class TranslationRepository:
    """Repository for system translation CRUD operations"""

    async def create(
        self,
        conn: asyncpg.Connection,
        category: str,
        key_code: str,
        es: str,
        fr: str,
        en: str,
        context: Optional[str] = None,
        description: Optional[str] = None,
        translation_source: str = "manual",
        user_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """
        Create a system translation

        Args:
            conn: Database connection
            category: Category (enum, ui.menu, etc.)
            key_code: Unique key code
            es: Spanish translation
            fr: French translation
            en: English translation
            context: Optional context
            description: Optional description
            translation_source: Source (manual, import, ai_generated)
            user_id: User creating the translation

        Returns:
            Created translation dict
        """
        query = """
            INSERT INTO translations (
                category, key_code, context, es, fr, en,
                description, translation_source,
                created_by, updated_by, created_at, updated_at, version
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, NOW(), NOW(), 1)
            RETURNING *
        """

        user_id_str = str(user_id) if user_id else None

        result = await conn.fetchrow(
            query,
            category,
            key_code,
            context,
            es,
            fr,
            en,
            description,
            translation_source,
            user_id_str,
            user_id_str,
        )

        logger.info(f"Created translation: {category}.{key_code}")
        return dict(result)

    async def upsert(
        self,
        conn: asyncpg.Connection,
        category: str,
        key_code: str,
        es: str,
        fr: str,
        en: str,
        context: Optional[str] = None,
        description: Optional[str] = None,
        translation_source: str = "manual",
        user_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """
        Create or update translation (upsert)

        Args:
            conn: Database connection
            category: Category
            key_code: Unique key code
            es: Spanish translation
            fr: French translation
            en: English translation
            context: Optional context
            description: Optional description
            translation_source: Source
            user_id: User upserting the translation

        Returns:
            Translation dict
        """
        query = """
            INSERT INTO translations (
                category, key_code, context, es, fr, en,
                description, translation_source,
                created_by, updated_by, created_at, updated_at, version
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, NOW(), NOW(), 1)
            ON CONFLICT (category, key_code, context)
            DO UPDATE SET
                es = EXCLUDED.es,
                fr = EXCLUDED.fr,
                en = EXCLUDED.en,
                description = EXCLUDED.description,
                translation_source = EXCLUDED.translation_source,
                updated_by = EXCLUDED.updated_by,
                updated_at = NOW(),
                version = translations.version + 1
            RETURNING *
        """

        user_id_str = str(user_id) if user_id else None

        result = await conn.fetchrow(
            query,
            category,
            key_code,
            context,
            es,
            fr,
            en,
            description,
            translation_source,
            user_id_str,
            user_id_str,
        )

        return dict(result)

    async def get_by_id(
        self,
        conn: asyncpg.Connection,
        translation_id: int,
    ) -> Optional[Dict[str, Any]]:
        """
        Get translation by ID

        Args:
            conn: Database connection
            translation_id: Translation ID

        Returns:
            Translation dict or None
        """
        query = "SELECT * FROM translations WHERE id = $1"
        result = await conn.fetchrow(query, translation_id)
        return dict(result) if result else None

    async def get_by_key(
        self,
        conn: asyncpg.Connection,
        category: str,
        key_code: str,
        context: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Get translation by category, key_code, and context

        Args:
            conn: Database connection
            category: Category
            key_code: Key code
            context: Optional context

        Returns:
            Translation dict or None
        """
        if context is not None:
            query = """
                SELECT * FROM translations
                WHERE category = $1 AND key_code = $2 AND context = $3
            """
            result = await conn.fetchrow(query, category, key_code, context)
        else:
            query = """
                SELECT * FROM translations
                WHERE category = $1 AND key_code = $2 AND context IS NULL
            """
            result = await conn.fetchrow(query, category, key_code)

        return dict(result) if result else None

    async def get_translation(
        self,
        conn: asyncpg.Connection,
        category: str,
        key_code: str,
        language: str = "es",
        context: Optional[str] = None,
    ) -> Optional[str]:
        """
        Get specific translation content for a language

        Args:
            conn: Database connection
            category: Category
            key_code: Key code
            language: Language code (es/fr/en)
            context: Optional context

        Returns:
            Translated content or None
        """
        # Validate language
        if language not in ["es", "fr", "en"]:
            logger.warning(f"Invalid language '{language}', defaulting to 'es'")
            language = "es"

        if context is not None:
            query = f"""
                SELECT {language} FROM translations
                WHERE category = $1 AND key_code = $2 AND context = $3
            """
            result = await conn.fetchval(query, category, key_code, context)
        else:
            query = f"""
                SELECT {language} FROM translations
                WHERE category = $1 AND key_code = $2 AND context IS NULL
            """
            result = await conn.fetchval(query, category, key_code)

        return result

    async def list_by_category(
        self,
        conn: asyncpg.Connection,
        category: str,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[List[Dict[str, Any]], int]:
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
        # Count query
        count_query = """
            SELECT COUNT(*) FROM translations WHERE category = $1
        """
        total = await conn.fetchval(count_query, category)

        # Data query
        data_query = """
            SELECT * FROM translations
            WHERE category = $1
            ORDER BY key_code, context
            LIMIT $2 OFFSET $3
        """
        results = await conn.fetch(data_query, category, limit, offset)
        translations = [dict(r) for r in results]

        return translations, total

    async def search(
        self,
        conn: asyncpg.Connection,
        category: Optional[str] = None,
        categories_in: Optional[List[str]] = None,
        key_code: Optional[str] = None,
        context: Optional[str] = None,
        search_term: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[List[Dict[str, Any]], int]:
        """
        Search translations with filters

        Args:
            conn: Database connection
            category: Optional category filter (single category)
            categories_in: Optional list of categories to filter (for group filtering)
            key_code: Optional key_code search (ILIKE)
            context: Optional context filter
            search_term: Optional full-text search in translations
            limit: Max results
            offset: Pagination offset

        Returns:
            Tuple of (translations list, total count)
        """
        # Build WHERE clause
        where_conditions = []
        params = []
        param_counter = 1

        if category:
            where_conditions.append(f"category = ${param_counter}")
            params.append(category)
            param_counter += 1
        elif categories_in and len(categories_in) > 0:
            where_conditions.append(f"category = ANY(${param_counter})")
            params.append(categories_in)
            param_counter += 1

        if key_code:
            where_conditions.append(f"key_code ILIKE ${param_counter}")
            params.append(f"%{key_code}%")
            param_counter += 1

        if context:
            where_conditions.append(f"context = ${param_counter}")
            params.append(context)
            param_counter += 1

        if search_term:
            where_conditions.append(
                f"(es ILIKE ${param_counter} OR fr ILIKE ${param_counter} OR en ILIKE ${param_counter})"
            )
            params.append(f"%{search_term}%")
            param_counter += 1

        where_clause = " AND ".join(where_conditions) if where_conditions else "TRUE"

        # Count query
        count_query = f"SELECT COUNT(*) FROM translations WHERE {where_clause}"
        total = await conn.fetchval(count_query, *params)

        # Data query
        params.extend([limit, offset])
        data_query = f"""
            SELECT * FROM translations
            WHERE {where_clause}
            ORDER BY category, key_code, context
            LIMIT ${param_counter} OFFSET ${param_counter + 1}
        """

        results = await conn.fetch(data_query, *params)
        translations = [dict(r) for r in results]

        return translations, total

    async def update(
        self,
        conn: asyncpg.Connection,
        translation_id: int,
        es: Optional[str] = None,
        fr: Optional[str] = None,
        en: Optional[str] = None,
        description: Optional[str] = None,
        translation_source: Optional[str] = None,
        user_id: Optional[UUID] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Update translation

        Args:
            conn: Database connection
            translation_id: Translation ID
            es: Optional Spanish translation
            fr: Optional French translation
            en: Optional English translation
            description: Optional description
            translation_source: Optional source
            user_id: User updating the translation

        Returns:
            Updated translation or None
        """
        # Build SET clause dynamically
        set_parts = []
        params = [translation_id]
        param_counter = 2

        if es is not None:
            set_parts.append(f"es = ${param_counter}")
            params.append(es)
            param_counter += 1

        if fr is not None:
            set_parts.append(f"fr = ${param_counter}")
            params.append(fr)
            param_counter += 1

        if en is not None:
            set_parts.append(f"en = ${param_counter}")
            params.append(en)
            param_counter += 1

        if description is not None:
            set_parts.append(f"description = ${param_counter}")
            params.append(description)
            param_counter += 1

        if translation_source is not None:
            set_parts.append(f"translation_source = ${param_counter}")
            params.append(translation_source)
            param_counter += 1

        if user_id is not None:
            set_parts.append(f"updated_by = ${param_counter}")
            params.append(str(user_id))
            param_counter += 1

        if not set_parts:
            # No updates
            return await self.get_by_id(conn, translation_id)

        # Always update these fields
        set_parts.append("updated_at = NOW()")
        set_parts.append("version = version + 1")

        set_clause = ", ".join(set_parts)

        query = f"""
            UPDATE translations
            SET {set_clause}
            WHERE id = $1
            RETURNING *
        """

        result = await conn.fetchrow(query, *params)
        return dict(result) if result else None

    async def delete(
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
            True if deleted, False if not found
        """
        query = "DELETE FROM translations WHERE id = $1"
        result = await conn.execute(query, translation_id)

        # Result is like "DELETE 1" or "DELETE 0"
        return result.split()[-1] != "0"

    async def batch_create(
        self,
        conn: asyncpg.Connection,
        translations: List[Dict[str, Any]],
        user_id: Optional[UUID] = None,
    ) -> List[Dict[str, Any]]:
        """
        Create multiple translations in batch

        Args:
            conn: Database connection
            translations: List of translation dicts
            user_id: User creating the translations

        Returns:
            List of created translations
        """
        created = []
        user_id_str = str(user_id) if user_id else None

        for t in translations:
            result = await self.upsert(
                conn,
                t["category"],
                t["key_code"],
                t["es"],
                t["fr"],
                t["en"],
                t.get("context"),
                t.get("description"),
                t.get("translation_source", "import"),
                user_id,
            )
            created.append(result)

        logger.info(f"Batch created {len(created)} translations")
        return created
