"""
Entity Translation Repository - Data access layer for entity_translations table

Handles CRUD operations for ministry, sector, category translations.

Schema reference: docs-internal/database/DATABASE_SCHEMA_REFERENCE.md
Primary Key: (entity_type, entity_code, language_code, field_name)
"""

from typing import Optional, List, Dict, Any
from loguru import logger
import asyncpg


class EntityTranslationRepository:
    """Repository for entity translation CRUD operations"""

    async def create(
        self,
        conn: asyncpg.Connection,
        entity_type: str,
        entity_code: str,
        language_code: str,
        field_name: str,
        translation_text: str,
        translation_source: str = "manual",
        translation_quality: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Create a single entity translation

        Args:
            conn: Database connection
            entity_type: Entity type (ministry, sector, category)
            entity_code: Unique entity identifier
            language_code: Language code (es, fr, en)
            field_name: Field being translated (name, description)
            translation_text: The actual translation
            translation_source: Source (manual, import, ai_generated)
            translation_quality: Quality score 0-100

        Returns:
            Created translation dict
        """
        query = """
            INSERT INTO entity_translations (
                entity_type, entity_code, language_code, field_name,
                translation_text, translation_source, translation_quality,
                created_at, updated_at
            )
            VALUES ($1::translatable_entity_type, $2, $3, $4, $5, $6, $7, NOW(), NOW())
            RETURNING *
        """

        result = await conn.fetchrow(
            query,
            entity_type,
            entity_code,
            language_code,
            field_name,
            translation_text,
            translation_source,
            translation_quality,
        )

        logger.info(f"Created entity translation: {entity_type}.{entity_code}.{language_code}.{field_name}")
        return dict(result)

    async def upsert(
        self,
        conn: asyncpg.Connection,
        entity_type: str,
        entity_code: str,
        language_code: str,
        field_name: str,
        translation_text: str,
        translation_source: str = "manual",
        translation_quality: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Create or update entity translation (upsert)

        Returns:
            Translation dict
        """
        query = """
            INSERT INTO entity_translations (
                entity_type, entity_code, language_code, field_name,
                translation_text, translation_source, translation_quality,
                created_at, updated_at
            )
            VALUES ($1::translatable_entity_type, $2, $3, $4, $5, $6, $7, NOW(), NOW())
            ON CONFLICT (entity_type, entity_code, language_code, field_name)
            DO UPDATE SET
                translation_text = EXCLUDED.translation_text,
                translation_source = EXCLUDED.translation_source,
                translation_quality = EXCLUDED.translation_quality,
                updated_at = NOW()
            RETURNING *
        """

        result = await conn.fetchrow(
            query,
            entity_type,
            entity_code,
            language_code,
            field_name,
            translation_text,
            translation_source,
            translation_quality,
        )

        return dict(result)

    async def get_by_key(
        self,
        conn: asyncpg.Connection,
        entity_type: str,
        entity_code: str,
        language_code: str,
        field_name: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get translation by composite key

        Returns:
            Translation dict or None
        """
        query = """
            SELECT * FROM entity_translations
            WHERE entity_type = $1::translatable_entity_type
              AND entity_code = $2
              AND language_code = $3
              AND field_name = $4
        """
        result = await conn.fetchrow(query, entity_type, entity_code, language_code, field_name)
        return dict(result) if result else None

    async def get_entity_translations(
        self,
        conn: asyncpg.Connection,
        entity_type: str,
        entity_code: str,
    ) -> List[Dict[str, Any]]:
        """
        Get all translations for a single entity (all languages, all fields)

        Returns:
            List of translations
        """
        query = """
            SELECT * FROM entity_translations
            WHERE entity_type = $1::translatable_entity_type
              AND entity_code = $2
            ORDER BY field_name, language_code
        """
        results = await conn.fetch(query, entity_type, entity_code)
        return [dict(r) for r in results]

    async def get_grouped_translations(
        self,
        conn: asyncpg.Connection,
        entity_type: str,
        entity_code: str,
    ) -> Dict[str, Dict[str, str]]:
        """
        Get translations grouped by field_name with all languages

        Returns:
            Dict like {field_name: {es: "...", fr: "...", en: "..."}}
        """
        translations = await self.get_entity_translations(conn, entity_type, entity_code)

        grouped = {}
        for t in translations:
            field = t["field_name"]
            lang = t["language_code"]
            if field not in grouped:
                grouped[field] = {"es": "", "fr": "", "en": ""}
            grouped[field][lang] = t["translation_text"]

        return grouped

    async def search(
        self,
        conn: asyncpg.Connection,
        entity_type: Optional[str] = None,
        entity_code: Optional[str] = None,
        language_code: Optional[str] = None,
        field_name: Optional[str] = None,
        search_term: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[List[Dict[str, Any]], int]:
        """
        Search entity translations with filters

        Returns:
            Tuple of (translations list, total count)
        """
        where_conditions = []
        params = []
        param_counter = 1

        if entity_type:
            where_conditions.append(f"entity_type = ${param_counter}::translatable_entity_type")
            params.append(entity_type)
            param_counter += 1

        if entity_code:
            where_conditions.append(f"entity_code ILIKE ${param_counter}")
            params.append(f"%{entity_code}%")
            param_counter += 1

        if language_code:
            where_conditions.append(f"language_code = ${param_counter}")
            params.append(language_code)
            param_counter += 1

        if field_name:
            where_conditions.append(f"field_name = ${param_counter}")
            params.append(field_name)
            param_counter += 1

        if search_term:
            where_conditions.append(f"translation_text ILIKE ${param_counter}")
            params.append(f"%{search_term}%")
            param_counter += 1

        where_clause = " AND ".join(where_conditions) if where_conditions else "TRUE"

        # Count query
        count_query = f"SELECT COUNT(*) FROM entity_translations WHERE {where_clause}"
        total = await conn.fetchval(count_query, *params)

        # Data query
        params.extend([limit, offset])
        data_query = f"""
            SELECT * FROM entity_translations
            WHERE {where_clause}
            ORDER BY entity_type, entity_code, field_name, language_code
            LIMIT ${param_counter} OFFSET ${param_counter + 1}
        """

        results = await conn.fetch(data_query, *params)
        translations = [dict(r) for r in results]

        return translations, total

    async def list_by_entity_type(
        self,
        conn: asyncpg.Connection,
        entity_type: str,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[List[Dict[str, Any]], int]:
        """
        List all translations for an entity type

        Returns:
            Tuple of (translations list, total count)
        """
        count_query = """
            SELECT COUNT(*) FROM entity_translations
            WHERE entity_type = $1::translatable_entity_type
        """
        total = await conn.fetchval(count_query, entity_type)

        data_query = """
            SELECT * FROM entity_translations
            WHERE entity_type = $1::translatable_entity_type
            ORDER BY entity_code, field_name, language_code
            LIMIT $2 OFFSET $3
        """
        results = await conn.fetch(data_query, entity_type, limit, offset)
        translations = [dict(r) for r in results]

        return translations, total

    async def list_distinct_entities(
        self,
        conn: asyncpg.Connection,
        entity_type: str,
    ) -> List[str]:
        """
        List distinct entity_codes for an entity type

        Returns:
            List of entity codes
        """
        query = """
            SELECT DISTINCT entity_code FROM entity_translations
            WHERE entity_type = $1::translatable_entity_type
            ORDER BY entity_code
        """
        results = await conn.fetch(query, entity_type)
        return [r["entity_code"] for r in results]

    async def update(
        self,
        conn: asyncpg.Connection,
        entity_type: str,
        entity_code: str,
        language_code: str,
        field_name: str,
        translation_text: Optional[str] = None,
        translation_source: Optional[str] = None,
        translation_quality: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Update entity translation

        Returns:
            Updated translation or None
        """
        set_parts = []
        params = [entity_type, entity_code, language_code, field_name]
        param_counter = 5

        if translation_text is not None:
            set_parts.append(f"translation_text = ${param_counter}")
            params.append(translation_text)
            param_counter += 1

        if translation_source is not None:
            set_parts.append(f"translation_source = ${param_counter}")
            params.append(translation_source)
            param_counter += 1

        if translation_quality is not None:
            set_parts.append(f"translation_quality = ${param_counter}")
            params.append(translation_quality)
            param_counter += 1

        if not set_parts:
            return await self.get_by_key(conn, entity_type, entity_code, language_code, field_name)

        set_parts.append("updated_at = NOW()")
        set_clause = ", ".join(set_parts)

        query = f"""
            UPDATE entity_translations
            SET {set_clause}
            WHERE entity_type = $1::translatable_entity_type
              AND entity_code = $2
              AND language_code = $3
              AND field_name = $4
            RETURNING *
        """

        result = await conn.fetchrow(query, *params)
        return dict(result) if result else None

    async def delete(
        self,
        conn: asyncpg.Connection,
        entity_type: str,
        entity_code: str,
        language_code: str,
        field_name: str,
    ) -> bool:
        """
        Delete a single entity translation

        Returns:
            True if deleted, False if not found
        """
        query = """
            DELETE FROM entity_translations
            WHERE entity_type = $1::translatable_entity_type
              AND entity_code = $2
              AND language_code = $3
              AND field_name = $4
        """
        result = await conn.execute(query, entity_type, entity_code, language_code, field_name)
        return result.split()[-1] != "0"

    async def delete_entity(
        self,
        conn: asyncpg.Connection,
        entity_type: str,
        entity_code: str,
    ) -> int:
        """
        Delete all translations for an entity

        Returns:
            Number of deleted translations
        """
        query = """
            DELETE FROM entity_translations
            WHERE entity_type = $1::translatable_entity_type
              AND entity_code = $2
        """
        result = await conn.execute(query, entity_type, entity_code)
        return int(result.split()[-1])

    async def batch_upsert(
        self,
        conn: asyncpg.Connection,
        translations: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Bulk upsert translations

        Each item should have: entity_type, entity_code, field_name, es, fr, en

        Returns:
            List of upserted translations
        """
        created = []

        for t in translations:
            entity_type = t["entity_type"]
            entity_code = t["entity_code"]
            field_name = t["field_name"]
            source = t.get("translation_source", "import")

            # Upsert each target language (fr, en only - es is source language)
            # Spanish content is stored in source tables (ministries, sectors, etc.)
            for lang in ["fr", "en"]:
                if lang in t and t[lang]:
                    result = await self.upsert(
                        conn,
                        entity_type,
                        entity_code,
                        lang,
                        field_name,
                        t[lang],
                        source,
                    )
                    created.append(result)

        logger.info(f"Batch upserted {len(created)} entity translations")
        return created

    async def get_stats(
        self,
        conn: asyncpg.Connection,
    ) -> Dict[str, Any]:
        """
        Get entity translation statistics

        Returns:
            Statistics dict
        """
        # Total count
        total = await conn.fetchval("SELECT COUNT(*) FROM entity_translations")

        # By entity type
        by_type_query = """
            SELECT entity_type::text, COUNT(*) as count
            FROM entity_translations
            GROUP BY entity_type
            ORDER BY entity_type
        """
        by_type_results = await conn.fetch(by_type_query)
        by_entity_type = {r["entity_type"]: r["count"] for r in by_type_results}

        # By language
        by_lang_query = """
            SELECT language_code, COUNT(*) as count
            FROM entity_translations
            GROUP BY language_code
            ORDER BY language_code
        """
        by_lang_results = await conn.fetch(by_lang_query)
        by_language = {r["language_code"]: r["count"] for r in by_lang_results}

        # By field
        by_field_query = """
            SELECT field_name, COUNT(*) as count
            FROM entity_translations
            GROUP BY field_name
            ORDER BY count DESC
        """
        by_field_results = await conn.fetch(by_field_query)
        by_field = {r["field_name"]: r["count"] for r in by_field_results}

        # Distinct entities per type
        distinct_query = """
            SELECT entity_type::text, COUNT(DISTINCT entity_code) as count
            FROM entity_translations
            GROUP BY entity_type
        """
        distinct_results = await conn.fetch(distinct_query)
        distinct_entities = {r["entity_type"]: r["count"] for r in distinct_results}

        return {
            "total_translations": total,
            "by_entity_type": by_entity_type,
            "by_language": by_language,
            "by_field": by_field,
            "distinct_entities": distinct_entities,
        }

    async def export_by_entity_type(
        self,
        conn: asyncpg.Connection,
        entity_type: str,
    ) -> List[Dict[str, Any]]:
        """
        Export all translations for an entity type, grouped by entity

        Returns:
            List of {entity_code, translations: {field: {es, fr, en}}}
        """
        # Get all distinct entity codes
        entity_codes = await self.list_distinct_entities(conn, entity_type)

        result = []
        for code in entity_codes:
            grouped = await self.get_grouped_translations(conn, entity_type, code)
            result.append({
                "entity_type": entity_type,
                "entity_code": code,
                "translations": grouped,
            })

        return result
