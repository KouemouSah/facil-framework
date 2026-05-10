"""
SMS Template Repository - Data access layer for SMS templates

Handles all database operations for SMS templates table.
"""

import asyncpg
import json
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from loguru import logger

from ..models.sms_template import (
    SmsTemplateCreate,
    SmsTemplateUpdate,
    SmsTemplateResponse
)


class SmsTemplateRepository:
    """Repository for SMS templates data access"""

    async def create(
        self,
        db: asyncpg.Connection,
        template_data: SmsTemplateCreate,
        created_by: Optional[int] = None
    ) -> SmsTemplateResponse:
        """
        Create a new SMS template

        Args:
            db: Database connection
            template_data: Template data to create
            created_by: User ID who created the template

        Returns:
            Created template

        Raises:
            asyncpg.UniqueViolationError: If template_code already exists
        """
        query = """
            INSERT INTO sms_templates (
                template_code,
                name_es, name_fr, name_en,
                content_es, content_fr, content_en,
                variables,
                category,
                max_segments,
                is_active,
                created_by,
                created_at,
                updated_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $13)
            RETURNING *
        """

        try:
            row = await db.fetchrow(
                query,
                template_data.template_code,
                template_data.name_es,
                template_data.name_fr,
                template_data.name_en,
                template_data.content_es,
                template_data.content_fr,
                template_data.content_en,
                template_data.variables,
                template_data.category.value,
                template_data.max_segments,
                template_data.is_active,
                created_by,
                datetime.now(timezone.utc)
            )

            logger.info(f"Created SMS template: {template_data.template_code}")
            return self._row_to_response(row)

        except asyncpg.UniqueViolationError:
            logger.warning(f"Template code already exists: {template_data.template_code}")
            raise

    async def find_by_id(
        self,
        db: asyncpg.Connection,
        template_id: int
    ) -> Optional[SmsTemplateResponse]:
        """
        Find SMS template by ID

        Args:
            db: Database connection
            template_id: Template ID

        Returns:
            Template if found, None otherwise
        """
        query = """
            SELECT * FROM sms_templates
            WHERE id = $1
        """

        row = await db.fetchrow(query, template_id)
        return self._row_to_response(row) if row else None

    async def find_by_code(
        self,
        db: asyncpg.Connection,
        template_code: str
    ) -> Optional[SmsTemplateResponse]:
        """
        Find SMS template by template code

        Args:
            db: Database connection
            template_code: Unique template code

        Returns:
            Template if found, None otherwise
        """
        query = """
            SELECT * FROM sms_templates
            WHERE template_code = $1
        """

        row = await db.fetchrow(query, template_code)
        return self._row_to_response(row) if row else None

    async def find_all(
        self,
        db: asyncpg.Connection,
        category: Optional[str] = None,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> tuple[List[SmsTemplateResponse], int]:
        """
        List SMS templates with filters and pagination

        Args:
            db: Database connection
            category: Filter by category
            is_active: Filter by active status
            search: Search in template code, names, and content
            limit: Maximum number of templates to return
            offset: Number of templates to skip

        Returns:
            Tuple of (templates list, total count)
        """
        # Build WHERE clause
        where_clauses = []
        params = []
        param_counter = 1

        if category:
            where_clauses.append(f"category = ${param_counter}")
            params.append(category)
            param_counter += 1

        if is_active is not None:
            where_clauses.append(f"is_active = ${param_counter}")
            params.append(is_active)
            param_counter += 1

        if search:
            where_clauses.append(
                f"(template_code ILIKE ${param_counter} OR "
                f"name_es ILIKE ${param_counter} OR "
                f"name_fr ILIKE ${param_counter} OR "
                f"name_en ILIKE ${param_counter} OR "
                f"content_es ILIKE ${param_counter} OR "
                f"content_fr ILIKE ${param_counter} OR "
                f"content_en ILIKE ${param_counter})"
            )
            params.append(f"%{search}%")
            param_counter += 1

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        # Count total
        count_query = f"SELECT COUNT(*) FROM sms_templates {where_sql}"
        total = await db.fetchval(count_query, *params)

        # Fetch templates
        query = f"""
            SELECT * FROM sms_templates
            {where_sql}
            ORDER BY created_at DESC
            LIMIT ${param_counter} OFFSET ${param_counter + 1}
        """
        params.extend([limit, offset])

        rows = await db.fetch(query, *params)
        templates = [self._row_to_response(row) for row in rows]

        logger.info(f"Found {len(templates)} SMS templates (total: {total})")
        return templates, total

    async def update(
        self,
        db: asyncpg.Connection,
        template_id: int,
        template_data: SmsTemplateUpdate,
        updated_by: Optional[int] = None
    ) -> Optional[SmsTemplateResponse]:
        """
        Update an SMS template

        Args:
            db: Database connection
            template_id: Template ID to update
            template_data: Updated template data
            updated_by: User ID who updated the template

        Returns:
            Updated template if found, None otherwise
        """
        # Build SET clause dynamically based on provided fields
        set_clauses = ["updated_at = $1", "updated_by = $2"]
        params = [datetime.now(timezone.utc), updated_by]
        param_counter = 3

        update_fields = template_data.model_dump(exclude_unset=True)

        for field, value in update_fields.items():
            if field == "category" and value is not None:
                value = value.value  # Convert enum to string
            set_clauses.append(f"{field} = ${param_counter}")
            params.append(value)
            param_counter += 1

        if len(set_clauses) == 2:  # Only updated_at and updated_by
            logger.warning(f"No fields to update for template {template_id}")
            return await self.find_by_id(db, template_id)

        params.append(template_id)

        query = f"""
            UPDATE sms_templates
            SET {', '.join(set_clauses)}
            WHERE id = ${param_counter}
            RETURNING *
        """

        try:
            row = await db.fetchrow(query, *params)
            if row:
                logger.info(f"Updated SMS template: {template_id}")
                return self._row_to_response(row)
            return None

        except Exception as e:
            logger.error(f"Error updating SMS template {template_id}: {e}")
            raise

    async def delete(
        self,
        db: asyncpg.Connection,
        template_id: int
    ) -> bool:
        """
        Delete an SMS template

        Args:
            db: Database connection
            template_id: Template ID to delete

        Returns:
            True if deleted, False if not found
        """
        query = "DELETE FROM sms_templates WHERE id = $1"

        result = await db.execute(query, template_id)
        deleted = result.endswith("1")  # "DELETE 1" means 1 row deleted

        if deleted:
            logger.info(f"Deleted SMS template: {template_id}")
        else:
            logger.warning(f"SMS template not found: {template_id}")

        return deleted

    async def get_categories(self, db: asyncpg.Connection) -> List[Dict[str, Any]]:
        """
        Get list of categories with template counts

        Args:
            db: Database connection

        Returns:
            List of categories with counts
        """
        query = """
            SELECT
                category,
                COUNT(*) as total_templates,
                SUM(CASE WHEN is_active THEN 1 ELSE 0 END) as active_templates
            FROM sms_templates
            GROUP BY category
            ORDER BY category
        """

        rows = await db.fetch(query)
        return [dict(row) for row in rows]

    def _row_to_response(self, row: asyncpg.Record) -> SmsTemplateResponse:
        """
        Convert database row to SmsTemplateResponse model

        Args:
            row: Database row

        Returns:
            SmsTemplateResponse model
        """
        # Parse variables from JSONB - handle both string and list formats
        variables_raw = row["variables"]
        if variables_raw is None:
            variables = []
        elif isinstance(variables_raw, str):
            # JSONB returned as string, parse it
            try:
                variables = json.loads(variables_raw)
            except json.JSONDecodeError:
                variables = []
        elif isinstance(variables_raw, list):
            variables = variables_raw
        else:
            variables = []

        template = SmsTemplateResponse(
            id=row["id"],
            template_code=row["template_code"],
            name_es=row["name_es"],
            name_fr=row["name_fr"],
            name_en=row["name_en"],
            content_es=row["content_es"],
            content_fr=row["content_fr"],
            content_en=row["content_en"],
            variables=variables,
            category=row["category"],
            max_segments=row["max_segments"],
            is_active=row["is_active"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            created_by=row["created_by"],
            updated_by=row["updated_by"]
        )

        # Calculate character counts and segments
        template.content_es_length = len(row["content_es"])
        template.content_es_segments = self._calculate_segments(row["content_es"])

        if row["content_fr"]:
            template.content_fr_length = len(row["content_fr"])
            template.content_fr_segments = self._calculate_segments(row["content_fr"])

        if row["content_en"]:
            template.content_en_length = len(row["content_en"])
            template.content_en_segments = self._calculate_segments(row["content_en"])

        return template

    def _calculate_segments(self, content: str) -> int:
        """
        Calculate number of SMS segments for content

        Args:
            content: SMS content

        Returns:
            Number of segments (1 segment = 160 chars for GSM-7, 70 for Unicode)
        """
        if not content:
            return 0

        # Check if content uses Unicode characters
        uses_unicode = self._uses_unicode(content)

        # SMS segment sizes
        chars_per_segment = 70 if uses_unicode else 160
        chars_per_segment_concat = 67 if uses_unicode else 153

        length = len(content)

        if length == 0:
            return 0
        elif length <= chars_per_segment:
            return 1
        else:
            # For concatenated messages, first segment uses chars_per_segment_concat
            return (length + chars_per_segment_concat - 1) // chars_per_segment_concat

    def _uses_unicode(self, content: str) -> bool:
        """
        Check if content contains Unicode characters outside GSM-7 charset

        Args:
            content: SMS content

        Returns:
            True if Unicode, False if GSM-7
        """
        # GSM-7 basic character set
        gsm7_basic = set(
            "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?"
            "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà"
        )

        # GSM-7 extended characters (count as 2 chars)
        gsm7_extended = set("^{}\\[~]|€")

        for char in content:
            if char not in gsm7_basic and char not in gsm7_extended:
                return True

        return False
