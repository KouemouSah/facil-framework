"""
Notification Template Repository

Data access layer for notification templates
"""

import json
import asyncpg
from typing import Optional, List, Dict, Any
from datetime import datetime
from loguru import logger

from app.modules.communications.models.notification_template import (
    NotificationTemplateCreate,
    NotificationTemplateUpdate,
    NotificationTemplateResponse,
    NotificationType,
    NotificationPriority,
)


def _row_to_response(row: dict) -> NotificationTemplateResponse:
    """
    Convert database row to NotificationTemplateResponse.
    Handles nullable fields and enum conversions.
    """
    data = dict(row)

    # Handle nullable notification_type - default to 'info' if None
    if data.get('notification_type') is None:
        data['notification_type'] = 'info'

    # Handle nullable priority - default to 'normal' if None
    if data.get('priority') is None:
        data['priority'] = 'normal'

    # Handle nullable variables - default to empty list if None
    # Also parse JSON string if stored as string in database
    variables = data.get('variables')
    if variables is None:
        data['variables'] = []
    elif isinstance(variables, str):
        try:
            data['variables'] = json.loads(variables)
        except json.JSONDecodeError:
            data['variables'] = []

    # Handle nullable is_active - default to True if None
    if data.get('is_active') is None:
        data['is_active'] = True

    return NotificationTemplateResponse(**data)


class NotificationTemplateRepository:
    """Repository for notification template CRUD operations"""

    async def create(
        self,
        db: asyncpg.Connection,
        template_data: NotificationTemplateCreate,
        created_by: int
    ) -> NotificationTemplateResponse:
        """
        Create a new notification template

        Args:
            db: Database connection
            template_data: Template data
            created_by: User ID creating the template

        Returns:
            Created notification template

        Raises:
            asyncpg.UniqueViolationError: If template_code already exists
        """
        query = """
            INSERT INTO notification_templates (
                template_code,
                name_es, name_fr, name_en,
                title_es, title_fr, title_en,
                body_es, body_fr, body_en,
                icon, action_url, variables,
                notification_type, priority, is_active,
                created_by, created_at, updated_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, NOW(), NOW())
            RETURNING
                id, template_code,
                name_es, name_fr, name_en,
                title_es, title_fr, title_en,
                body_es, body_fr, body_en,
                icon, action_url, variables,
                notification_type, priority, is_active,
                created_at, updated_at, created_by
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
                template_data.icon,
                template_data.action_url,
                template_data.variables,
                template_data.notification_type.value,
                template_data.priority.value,
                template_data.is_active,
                created_by
            )

            logger.info(f"Created notification template: {template_data.template_code}")
            return _row_to_response(row)

        except asyncpg.UniqueViolationError:
            logger.error(f"Duplicate template_code: {template_data.template_code}")
            raise

    async def find_by_id(
        self,
        db: asyncpg.Connection,
        template_id: int
    ) -> Optional[NotificationTemplateResponse]:
        """
        Find notification template by ID

        Args:
            db: Database connection
            template_id: Template ID

        Returns:
            Notification template or None if not found
        """
        query = """
            SELECT
                id, template_code,
                name_es, name_fr, name_en,
                title_es, title_fr, title_en,
                body_es, body_fr, body_en,
                icon, action_url, variables,
                notification_type, priority, is_active,
                created_at, updated_at, created_by
            FROM notification_templates
            WHERE id = $1
        """

        row = await db.fetchrow(query, template_id)
        return _row_to_response(row) if row else None

    async def find_by_code(
        self,
        db: asyncpg.Connection,
        template_code: str
    ) -> Optional[NotificationTemplateResponse]:
        """
        Find notification template by template code

        Args:
            db: Database connection
            template_code: Template code

        Returns:
            Notification template or None if not found
        """
        query = """
            SELECT
                id, template_code,
                name_es, name_fr, name_en,
                title_es, title_fr, title_en,
                body_es, body_fr, body_en,
                icon, action_url, variables,
                notification_type, priority, is_active,
                created_at, updated_at, created_by
            FROM notification_templates
            WHERE template_code = $1
        """

        row = await db.fetchrow(query, template_code.lower())
        return _row_to_response(row) if row else None

    async def find_all(
        self,
        db: asyncpg.Connection,
        limit: int = 100,
        offset: int = 0,
        is_active: Optional[bool] = None,
        notification_type: Optional[str] = None,
        search: Optional[str] = None
    ) -> tuple[List[NotificationTemplateResponse], int]:
        """
        List all notification templates with pagination and filters

        Args:
            db: Database connection
            limit: Maximum number of results
            offset: Offset for pagination
            is_active: Filter by active status
            notification_type: Filter by notification type
            search: Search in template code and names

        Returns:
            Tuple of (list of templates, total count)
        """
        # Build WHERE clause
        conditions = []
        params = []
        param_count = 0

        if is_active is not None:
            param_count += 1
            conditions.append(f"is_active = ${param_count}")
            params.append(is_active)

        if notification_type:
            param_count += 1
            conditions.append(f"notification_type = ${param_count}")
            params.append(notification_type)

        if search:
            param_count += 1
            conditions.append(
                f"(template_code ILIKE ${param_count} OR name_es ILIKE ${param_count} OR name_fr ILIKE ${param_count} OR name_en ILIKE ${param_count})"
            )
            params.append(f"%{search}%")

        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

        # Count query
        count_query = f"""
            SELECT COUNT(*)
            FROM notification_templates
            {where_clause}
        """
        total = await db.fetchval(count_query, *params)

        # Data query with pagination
        param_count += 1
        limit_param = param_count
        param_count += 1
        offset_param = param_count

        data_query = f"""
            SELECT
                id, template_code,
                name_es, name_fr, name_en,
                title_es, title_fr, title_en,
                body_es, body_fr, body_en,
                icon, action_url, variables,
                notification_type, priority, is_active,
                created_at, updated_at, created_by
            FROM notification_templates
            {where_clause}
            ORDER BY priority DESC, created_at DESC
            LIMIT ${limit_param} OFFSET ${offset_param}
        """

        rows = await db.fetch(data_query, *params, limit, offset)
        templates = [_row_to_response(row) for row in rows]

        return templates, total

    async def update(
        self,
        db: asyncpg.Connection,
        template_id: int,
        template_data: NotificationTemplateUpdate
    ) -> Optional[NotificationTemplateResponse]:
        """
        Update notification template

        Args:
            db: Database connection
            template_id: Template ID
            template_data: Updated template data

        Returns:
            Updated notification template or None if not found
        """
        # Build dynamic UPDATE query
        update_fields = []
        params = []
        param_count = 0

        # Map field names to values
        update_dict = template_data.model_dump(exclude_unset=True)

        for field_name, value in update_dict.items():
            param_count += 1
            update_fields.append(f"{field_name} = ${param_count}")
            params.append(value)

        if not update_fields:
            # No fields to update
            return await self.find_by_id(db, template_id)

        # Add updated_at
        param_count += 1
        update_fields.append(f"updated_at = ${param_count}")
        params.append(datetime.now())

        # Add template_id for WHERE clause
        param_count += 1
        params.append(template_id)

        query = f"""
            UPDATE notification_templates
            SET {', '.join(update_fields)}
            WHERE id = ${param_count}
            RETURNING
                id, template_code,
                name_es, name_fr, name_en,
                title_es, title_fr, title_en,
                body_es, body_fr, body_en,
                icon, action_url, variables,
                notification_type, priority, is_active,
                created_at, updated_at, created_by
        """

        try:
            row = await db.fetchrow(query, *params)
            if row:
                logger.info(f"Updated notification template ID: {template_id}")
                return _row_to_response(row)
            return None

        except Exception as e:
            logger.error(f"Error updating notification template {template_id}: {e}")
            raise

    async def delete(
        self,
        db: asyncpg.Connection,
        template_id: int
    ) -> bool:
        """
        Delete notification template

        Args:
            db: Database connection
            template_id: Template ID

        Returns:
            True if deleted, False if not found
        """
        query = "DELETE FROM notification_templates WHERE id = $1"

        try:
            result = await db.execute(query, template_id)
            deleted = result.split()[-1] == "1"

            if deleted:
                logger.info(f"Deleted notification template ID: {template_id}")

            return deleted

        except Exception as e:
            logger.error(f"Error deleting notification template {template_id}: {e}")
            raise

    async def get_active_templates(
        self,
        db: asyncpg.Connection
    ) -> List[NotificationTemplateResponse]:
        """
        Get all active notification templates

        Args:
            db: Database connection

        Returns:
            List of active notification templates
        """
        query = """
            SELECT
                id, template_code,
                name_es, name_fr, name_en,
                title_es, title_fr, title_en,
                body_es, body_fr, body_en,
                icon, action_url, variables,
                notification_type, priority, is_active,
                created_at, updated_at, created_by
            FROM notification_templates
            WHERE is_active = true
            ORDER BY priority DESC, created_at DESC
        """

        rows = await db.fetch(query)
        return [_row_to_response(row) for row in rows]
