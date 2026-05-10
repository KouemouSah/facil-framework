"""
Push Template Repository - Data access layer for push notification templates

Handles:
- CRUD operations on push_templates table
- PostgreSQL queries with asyncpg
- Template code uniqueness validation
- Pagination and filtering

Module: Communications
"""

import json
import asyncpg
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from loguru import logger

from ..models.push_template import (
    PushTemplateCreate,
    PushTemplateUpdate,
    PushTemplateResponse,
    PlatformEnum
)


class PushTemplateRepository:
    """Data access layer for push_templates table"""

    async def create(
        self,
        db: asyncpg.Connection,
        template_data: PushTemplateCreate,
        created_by: int
    ) -> PushTemplateResponse:
        """
        Create a new push template

        Args:
            db: Database connection
            template_data: Template data
            created_by: User ID creating the template

        Returns:
            Created template

        Raises:
            asyncpg.UniqueViolationError: If template_code already exists
        """
        query = """
            INSERT INTO push_templates (
                template_code,
                name_es, name_fr, name_en,
                title_es, title_fr, title_en,
                body_es, body_fr, body_en,
                image_url, icon_url, click_action,
                data_payload, variables,
                platform, ttl_seconds, is_active,
                created_by
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19)
            RETURNING *
        """

        try:
            row = await db.fetchrow(
                query,
                template_data.template_code,
                template_data.name_es,
                template_data.name_fr,
                template_data.name_en,
                template_data.title_es,
                template_data.title_fr,
                template_data.title_en,
                template_data.body_es,
                template_data.body_fr,
                template_data.body_en,
                template_data.image_url,
                template_data.icon_url,
                template_data.click_action,
                template_data.data_payload,
                template_data.variables,
                template_data.platform.value,
                template_data.ttl_seconds,
                template_data.is_active,
                created_by
            )

            logger.info(f"Created push template: {template_data.template_code}")
            return self._row_to_model(row)

        except asyncpg.UniqueViolationError:
            logger.error(f"Template code already exists: {template_data.template_code}")
            raise ValueError(f"Template code '{template_data.template_code}' already exists")

    async def find_by_id(
        self,
        db: asyncpg.Connection,
        template_id: int
    ) -> Optional[PushTemplateResponse]:
        """
        Find push template by ID

        Args:
            db: Database connection
            template_id: Template ID

        Returns:
            Template or None if not found
        """
        query = "SELECT * FROM push_templates WHERE id = $1"
        row = await db.fetchrow(query, template_id)

        if not row:
            return None

        return self._row_to_model(row)

    async def find_by_code(
        self,
        db: asyncpg.Connection,
        template_code: str
    ) -> Optional[PushTemplateResponse]:
        """
        Find push template by code

        Args:
            db: Database connection
            template_code: Template code

        Returns:
            Template or None if not found
        """
        query = "SELECT * FROM push_templates WHERE template_code = $1"
        row = await db.fetchrow(query, template_code)

        if not row:
            return None

        return self._row_to_model(row)

    async def find_all(
        self,
        db: asyncpg.Connection,
        page: int = 1,
        page_size: int = 20,
        is_active: Optional[bool] = None,
        platform: Optional[PlatformEnum] = None,
        search: Optional[str] = None
    ) -> tuple[List[PushTemplateResponse], int]:
        """
        List all push templates with pagination and filters

        Args:
            db: Database connection
            page: Page number (1-indexed)
            page_size: Items per page
            is_active: Filter by active status
            platform: Filter by platform
            search: Search in template_code and names

        Returns:
            Tuple of (templates list, total count)
        """
        # Build WHERE clause
        conditions = []
        params = []
        param_count = 1

        if is_active is not None:
            conditions.append(f"is_active = ${param_count}")
            params.append(is_active)
            param_count += 1

        if platform:
            conditions.append(f"platform = ${param_count}")
            params.append(platform.value)
            param_count += 1

        if search:
            conditions.append(
                f"(template_code ILIKE ${param_count} OR name_es ILIKE ${param_count} OR "
                f"name_fr ILIKE ${param_count} OR name_en ILIKE ${param_count})"
            )
            params.append(f"%{search}%")
            param_count += 1

        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

        # Count total
        count_query = f"SELECT COUNT(*) FROM push_templates {where_clause}"
        total = await db.fetchval(count_query, *params)

        # Fetch templates
        offset = (page - 1) * page_size
        query = f"""
            SELECT * FROM push_templates
            {where_clause}
            ORDER BY created_at DESC
            LIMIT ${param_count} OFFSET ${param_count + 1}
        """
        params.extend([page_size, offset])

        rows = await db.fetch(query, *params)
        templates = [self._row_to_model(row) for row in rows]

        logger.debug(f"Found {len(templates)} push templates (total: {total})")
        return templates, total

    async def update(
        self,
        db: asyncpg.Connection,
        template_id: int,
        template_data: PushTemplateUpdate
    ) -> Optional[PushTemplateResponse]:
        """
        Update push template

        Args:
            db: Database connection
            template_id: Template ID
            template_data: Update data

        Returns:
            Updated template or None if not found
        """
        # Build UPDATE clause dynamically
        updates = []
        params = []
        param_count = 1

        update_dict = template_data.model_dump(exclude_unset=True)

        for field, value in update_dict.items():
            if value is not None or field in update_dict:
                updates.append(f"{field} = ${param_count}")
                # Convert enum to value
                if isinstance(value, PlatformEnum):
                    value = value.value
                params.append(value)
                param_count += 1

        if not updates:
            # No updates, just return current template
            return await self.find_by_id(db, template_id)

        # Add updated_at
        updates.append(f"updated_at = ${param_count}")
        params.append(datetime.now(timezone.utc))
        param_count += 1

        # Add template_id
        params.append(template_id)

        query = f"""
            UPDATE push_templates
            SET {', '.join(updates)}
            WHERE id = ${param_count}
            RETURNING *
        """

        row = await db.fetchrow(query, *params)

        if not row:
            logger.warning(f"Push template not found for update: {template_id}")
            return None

        logger.info(f"Updated push template: {template_id}")
        return self._row_to_model(row)

    async def delete(
        self,
        db: asyncpg.Connection,
        template_id: int
    ) -> bool:
        """
        Delete push template

        Args:
            db: Database connection
            template_id: Template ID

        Returns:
            True if deleted, False if not found
        """
        query = "DELETE FROM push_templates WHERE id = $1"
        result = await db.execute(query, template_id)

        deleted = result.endswith("1")

        if deleted:
            logger.info(f"Deleted push template: {template_id}")
        else:
            logger.warning(f"Push template not found for deletion: {template_id}")

        return deleted

    async def get_stats(
        self,
        db: asyncpg.Connection
    ) -> Dict[str, Any]:
        """
        Get push template statistics

        Args:
            db: Database connection

        Returns:
            Statistics dictionary
        """
        query = """
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE is_active = true) as active,
                COUNT(*) FILTER (WHERE is_active = false) as inactive,
                COUNT(*) FILTER (WHERE platform = 'all') as all_platform,
                COUNT(*) FILTER (WHERE platform = 'ios') as ios_platform,
                COUNT(*) FILTER (WHERE platform = 'android') as android_platform,
                COUNT(*) FILTER (WHERE platform = 'web') as web_platform
            FROM push_templates
        """

        row = await db.fetchrow(query)

        return {
            "total": row["total"],
            "active": row["active"],
            "inactive": row["inactive"],
            "by_platform": {
                "all": row["all_platform"],
                "ios": row["ios_platform"],
                "android": row["android_platform"],
                "web": row["web_platform"]
            }
        }

    def _parse_json_field(self, value: Any, default: Any) -> Any:
        """
        Parse a JSON field that might be stored as a string in the database.

        Args:
            value: The field value (could be None, string, list, or dict)
            default: Default value if parsing fails or value is None

        Returns:
            Parsed value or default
        """
        if value is None:
            return default
        if isinstance(value, (list, dict)):
            return value
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return default
        return default

    def _row_to_model(self, row: asyncpg.Record) -> PushTemplateResponse:
        """
        Convert database row to Pydantic model.
        Handles nullable fields with sensible defaults.

        Args:
            row: Database row

        Returns:
            PushTemplateResponse model
        """
        # Handle nullable platform - default to 'all'
        platform_value = row["platform"] or "all"

        return PushTemplateResponse(
            id=row["id"],
            template_code=row["template_code"],
            name_es=row["name_es"],
            name_fr=row["name_fr"],
            name_en=row["name_en"],
            title_es=row["title_es"],
            title_fr=row["title_fr"],
            title_en=row["title_en"],
            body_es=row["body_es"],
            body_fr=row["body_fr"],
            body_en=row["body_en"],
            image_url=row["image_url"],
            icon_url=row["icon_url"],
            click_action=row["click_action"],
            data_payload=self._parse_json_field(row["data_payload"], {}),
            variables=self._parse_json_field(row["variables"], []),
            platform=PlatformEnum(platform_value),
            ttl_seconds=row["ttl_seconds"] if row["ttl_seconds"] is not None else 86400,
            is_active=row["is_active"] if row["is_active"] is not None else True,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            created_by=row["created_by"]
        )
