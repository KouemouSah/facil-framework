"""
Entity Translation Service - Business logic for entity_translations

Handles:
- CRUD operations for ministry, sector, category translations
- Bulk operations
- Export/Import functionality
"""

from typing import Optional, List, Dict, Any
from loguru import logger
import asyncpg

from ..models.entity_translation import (
    EntityTranslationCreate,
    EntityTranslationUpdate,
    EntityTranslationBulkCreate,
    EntityTranslationSearchParams,
)
from ..repositories.entity_translation_repository import EntityTranslationRepository


class EntityTranslationService:
    """Service for entity translation operations"""

    def __init__(self):
        self.repository = EntityTranslationRepository()

    async def create_translation(
        self,
        conn: asyncpg.Connection,
        translation: EntityTranslationCreate,
    ) -> Dict[str, Any]:
        """
        Create a single entity translation

        Args:
            conn: Database connection
            translation: Translation data

        Returns:
            Created translation
        """
        return await self.repository.create(
            conn,
            translation.entity_type.value,
            translation.entity_code,
            translation.language_code.value,
            translation.field_name,
            translation.translation_text,
            translation.translation_source or "manual",
            translation.translation_quality,
        )

    async def upsert_translation(
        self,
        conn: asyncpg.Connection,
        translation: EntityTranslationCreate,
    ) -> Dict[str, Any]:
        """
        Create or update entity translation

        Returns:
            Translation
        """
        return await self.repository.upsert(
            conn,
            translation.entity_type.value,
            translation.entity_code,
            translation.language_code.value,
            translation.field_name,
            translation.translation_text,
            translation.translation_source or "manual",
            translation.translation_quality,
        )

    async def get_translation_by_key(
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
            Translation or None
        """
        return await self.repository.get_by_key(
            conn, entity_type, entity_code, language_code, field_name
        )

    async def get_entity_all_translations(
        self,
        conn: asyncpg.Connection,
        entity_type: str,
        entity_code: str,
    ) -> Dict[str, Any]:
        """
        Get all translations for an entity, grouped by field

        Returns:
            {entity_type, entity_code, translations: {field: {es, fr, en}}}
        """
        grouped = await self.repository.get_grouped_translations(conn, entity_type, entity_code)
        return {
            "entity_type": entity_type,
            "entity_code": entity_code,
            "translations": grouped,
        }

    async def search_translations(
        self,
        conn: asyncpg.Connection,
        params: EntityTranslationSearchParams,
    ) -> tuple[List[Dict[str, Any]], int]:
        """
        Search translations with filters

        Returns:
            Tuple of (translations, total count)
        """
        return await self.repository.search(
            conn,
            params.entity_type.value if params.entity_type else None,
            params.entity_code,
            params.language_code.value if params.language_code else None,
            params.field_name,
            params.search_term,
            params.limit,
            params.offset,
        )

    async def update_translation(
        self,
        conn: asyncpg.Connection,
        entity_type: str,
        entity_code: str,
        language_code: str,
        field_name: str,
        update_data: EntityTranslationUpdate,
    ) -> Optional[Dict[str, Any]]:
        """
        Update entity translation

        Returns:
            Updated translation or None
        """
        return await self.repository.update(
            conn,
            entity_type,
            entity_code,
            language_code,
            field_name,
            update_data.translation_text,
            update_data.translation_source,
            update_data.translation_quality,
        )

    async def delete_translation(
        self,
        conn: asyncpg.Connection,
        entity_type: str,
        entity_code: str,
        language_code: str,
        field_name: str,
    ) -> bool:
        """
        Delete a single translation

        Returns:
            True if deleted
        """
        return await self.repository.delete(
            conn, entity_type, entity_code, language_code, field_name
        )

    async def delete_entity_translations(
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
        return await self.repository.delete_entity(conn, entity_type, entity_code)

    async def bulk_upsert(
        self,
        conn: asyncpg.Connection,
        batch: EntityTranslationBulkCreate,
    ) -> List[Dict[str, Any]]:
        """
        Bulk upsert translations

        Args:
            batch: Batch with translations list (each has es, fr, en)

        Returns:
            List of upserted translations
        """
        translations_data = []
        for item in batch.translations:
            translations_data.append({
                "entity_type": item.entity_type.value,
                "entity_code": item.entity_code,
                "field_name": item.field_name,
                "es": item.es,
                "fr": item.fr,
                "en": item.en,
                "translation_source": item.translation_source or "import",
            })

        return await self.repository.batch_upsert(conn, translations_data)

    async def get_stats(
        self,
        conn: asyncpg.Connection,
    ) -> Dict[str, Any]:
        """
        Get entity translation statistics

        Returns:
            Statistics dict
        """
        return await self.repository.get_stats(conn)

    async def get_entity_types(self) -> List[str]:
        """
        Get list of supported entity types

        Returns:
            ["ministry", "sector", "category"]
        """
        return ["ministry", "sector", "category"]

    async def list_entities_by_type(
        self,
        conn: asyncpg.Connection,
        entity_type: str,
    ) -> List[str]:
        """
        List distinct entity codes for an entity type

        Returns:
            List of entity codes
        """
        return await self.repository.list_distinct_entities(conn, entity_type)

    async def export_by_type(
        self,
        conn: asyncpg.Connection,
        entity_type: str,
    ) -> List[Dict[str, Any]]:
        """
        Export all translations for an entity type

        Returns:
            List of {entity_code, translations: {field: {es, fr, en}}}
        """
        return await self.repository.export_by_entity_type(conn, entity_type)

    async def get_source_content(
        self,
        conn: asyncpg.Connection,
        entity_type: str,
        entity_code: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get Spanish source content from the source table

        Maps entity_type to source table and fetches Spanish fields:
        - ministry -> ministries (ministry_code, name_es, description_es)
        - sector -> sectors (sector_code, name_es, description_es)
        - category -> categories (category_code, name_es, description_es)
        - service -> fiscal_services (service_code, name_es, description_es)
        - procedure_template -> procedure_templates (template_code, name_es, description_es)
        - procedure_step -> procedure_template_steps (id, description_es, instructions_es)
        - document_template -> document_templates (template_code, document_name_es, description_es)

        Returns:
            {entity_type, entity_code, source_language, fields: {field_name: value}}
        """
        # Define table mappings
        table_mapping = {
            "ministry": {
                "table": "ministries",
                "code_column": "ministry_code",
                "fields": ["name_es", "description_es"],
            },
            "sector": {
                "table": "sectors",
                "code_column": "sector_code",
                "fields": ["name_es", "description_es"],
            },
            "category": {
                "table": "categories",
                "code_column": "category_code",
                "fields": ["name_es", "description_es"],
            },
            "service": {
                "table": "fiscal_services",
                "code_column": "service_code",
                "fields": ["name_es", "description_es"],
            },
            "procedure_template": {
                "table": "procedure_templates",
                "code_column": "template_code",
                "fields": ["name_es", "description_es"],
            },
            "procedure_step": {
                "table": "procedure_template_steps",
                "code_column": "id",
                "fields": ["description_es", "instructions_es"],
            },
            "document_template": {
                "table": "document_templates",
                "code_column": "template_code",
                "fields": ["document_name_es", "description_es"],
            },
        }

        if entity_type not in table_mapping:
            logger.warning(f"Unknown entity type: {entity_type}")
            return None

        mapping = table_mapping[entity_type]
        table = mapping["table"]
        code_column = mapping["code_column"]
        fields = mapping["fields"]

        # Build query
        fields_select = ", ".join(fields)

        # For procedure_step, entity_code is the id (integer)
        if entity_type == "procedure_step":
            query = f"SELECT {fields_select} FROM {table} WHERE {code_column} = $1::integer"
        else:
            query = f"SELECT {fields_select} FROM {table} WHERE {code_column} = $1"

        try:
            row = await conn.fetchrow(query, entity_code)
            if not row:
                return None

            # Build response with normalized field names
            result_fields = {}
            for field in fields:
                value = row.get(field)
                # Normalize field name (remove _es suffix, handle document_name_es -> name)
                normalized_name = field.replace("_es", "")
                if normalized_name == "document_name":
                    normalized_name = "name"
                result_fields[normalized_name] = value or ""

            return {
                "entity_type": entity_type,
                "entity_code": entity_code,
                "source_language": "es",
                "fields": result_fields,
            }

        except Exception as e:
            logger.error(f"Error fetching source content for {entity_type}/{entity_code}: {e}")
            return None

    async def list_source_entities(
        self,
        conn: asyncpg.Connection,
        entity_type: str,
        search_term: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        untranslated_only: bool = False,
    ) -> tuple[List[Dict[str, Any]], int]:
        """
        List entities from source table with Spanish content

        Args:
            entity_type: Type of entity to list
            search_term: Optional search filter
            limit: Max results per page
            offset: Pagination offset
            untranslated_only: If True, only return entities without translations

        Returns:
            Tuple of (entities list, total count)
        """
        table_mapping = {
            "ministry": {
                "table": "ministries",
                "code_column": "ministry_code",
                "name_column": "name_es",
                "description_column": "description_es",
            },
            "sector": {
                "table": "sectors",
                "code_column": "sector_code",
                "name_column": "name_es",
                "description_column": "description_es",
            },
            "category": {
                "table": "categories",
                "code_column": "category_code",
                "name_column": "name_es",
                "description_column": "description_es",
            },
            "service": {
                "table": "fiscal_services",
                "code_column": "service_code",
                "name_column": "name_es",
                "description_column": "description_es",
            },
            "procedure_template": {
                "table": "procedure_templates",
                "code_column": "template_code",
                "name_column": "name_es",
                "description_column": "description_es",
            },
            "procedure_step": {
                "table": "procedure_template_steps",
                "code_column": "id",
                "name_column": "description_es",
                "description_column": "instructions_es",
            },
            "document_template": {
                "table": "document_templates",
                "code_column": "template_code",
                "name_column": "document_name_es",
                "description_column": "description_es",
            },
        }

        if entity_type not in table_mapping:
            return [], 0

        mapping = table_mapping[entity_type]
        table = mapping["table"]
        code_column = mapping["code_column"]
        name_column = mapping["name_column"]
        description_column = mapping["description_column"]

        # Cast id to text for procedure_step
        # code_select without alias for SELECT clause
        code_select = f"CAST(s.{code_column} AS TEXT)" if entity_type == "procedure_step" else f"s.{code_column}"

        # Build WHERE conditions
        where_conditions = []
        params = []
        param_idx = 1

        if search_term:
            where_conditions.append(f"(s.{name_column} ILIKE ${param_idx} OR {code_select} ILIKE ${param_idx})")
            params.append(f"%{search_term}%")
            param_idx += 1

        # Build JOIN and filter for untranslated entities
        join_clause = ""
        if untranslated_only:
            # LEFT JOIN with entity_translations to find entities without any translations
            # Note: entity_translations uses composite PK (entity_type, entity_code, language_code, field_name)
            # so we check for et.entity_type IS NULL (no id column exists)
            join_clause = f"""
                LEFT JOIN entity_translations et ON
                    et.entity_type = '{entity_type}' AND
                    et.entity_code = {code_select}
            """
            where_conditions.append("et.entity_type IS NULL")

        where_clause = ""
        if where_conditions:
            where_clause = "WHERE " + " AND ".join(where_conditions)

        # Count query
        count_query = f"SELECT COUNT(DISTINCT s.{code_column}) FROM {table} s {join_clause} {where_clause}"
        total = await conn.fetchval(count_query, *params)

        # Data query
        data_query = f"""
            SELECT DISTINCT {code_select} as entity_code, s.{name_column} as name_es, s.{description_column} as description_es
            FROM {table} s
            {join_clause}
            {where_clause}
            ORDER BY s.{name_column}
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        params.extend([limit, offset])

        rows = await conn.fetch(data_query, *params)

        entities = [
            {
                "entity_code": row["entity_code"],
                "name_es": row["name_es"] or "",
                "description_es": row["description_es"] or "",
            }
            for row in rows
        ]

        return entities, total

    async def import_translations(
        self,
        conn: asyncpg.Connection,
        data: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Import translations from export format

        Args:
            data: List of {entity_type, entity_code, translations: {field: {es, fr, en}}}

        Returns:
            Import result with counts
        """
        created_count = 0
        updated_count = 0
        errors = []

        for item in data:
            entity_type = item.get("entity_type")
            entity_code = item.get("entity_code")
            translations = item.get("translations", {})

            if not entity_type or not entity_code:
                errors.append(f"Missing entity_type or entity_code: {item}")
                continue

            for field_name, langs in translations.items():
                for lang_code, text in langs.items():
                    if lang_code not in ["es", "fr", "en"]:
                        continue
                    if not text:
                        continue

                    try:
                        # Check if exists
                        existing = await self.repository.get_by_key(
                            conn, entity_type, entity_code, lang_code, field_name
                        )

                        await self.repository.upsert(
                            conn,
                            entity_type,
                            entity_code,
                            lang_code,
                            field_name,
                            text,
                            "import",
                        )

                        if existing:
                            updated_count += 1
                        else:
                            created_count += 1

                    except Exception as e:
                        errors.append(f"Error importing {entity_type}.{entity_code}.{lang_code}.{field_name}: {e}")
                        logger.error(f"Import error: {e}")

        return {
            "created": created_count,
            "updated": updated_count,
            "errors": errors,
            "total_processed": created_count + updated_count,
        }
