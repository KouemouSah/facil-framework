"""
Notification Template Service

Business logic for notification template management
"""

import asyncpg
import re
from typing import Optional, List, Dict, Any
from fastapi import HTTPException, status
from loguru import logger

from app.modules.communications.models.notification_template import (
    NotificationTemplateCreate,
    NotificationTemplateUpdate,
    NotificationTemplateResponse,
    NotificationPreviewRequest,
    NotificationPreviewResponse,
)
from app.modules.communications.repositories.notification_template_repository import (
    NotificationTemplateRepository,
)


class NotificationTemplateService:
    """Service for notification template business logic"""

    def __init__(self):
        self.repository = NotificationTemplateRepository()

    async def create_template(
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
            HTTPException: If template_code already exists
        """
        # Check if template_code already exists
        existing = await self.repository.find_by_code(db, template_data.template_code)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Template with code '{template_data.template_code}' already exists"
            )

        # Validate variables are used in body
        self._validate_template_variables(template_data)

        try:
            template = await self.repository.create(db, template_data, created_by)
            logger.info(f"Created notification template: {template.template_code} by user {created_by}")
            return template

        except asyncpg.UniqueViolationError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Template with code '{template_data.template_code}' already exists"
            )
        except Exception as e:
            logger.error(f"Error creating notification template: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create notification template"
            )

    async def get_template_by_id(
        self,
        db: asyncpg.Connection,
        template_id: int
    ) -> NotificationTemplateResponse:
        """
        Get notification template by ID

        Args:
            db: Database connection
            template_id: Template ID

        Returns:
            Notification template

        Raises:
            HTTPException: If template not found
        """
        template = await self.repository.find_by_id(db, template_id)
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Notification template with ID {template_id} not found"
            )
        return template

    async def get_template_by_code(
        self,
        db: asyncpg.Connection,
        template_code: str
    ) -> NotificationTemplateResponse:
        """
        Get notification template by code

        Args:
            db: Database connection
            template_code: Template code

        Returns:
            Notification template

        Raises:
            HTTPException: If template not found
        """
        template = await self.repository.find_by_code(db, template_code)
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Notification template with code '{template_code}' not found"
            )
        return template

    async def list_templates(
        self,
        db: asyncpg.Connection,
        page: int = 1,
        page_size: int = 20,
        is_active: Optional[bool] = None,
        notification_type: Optional[str] = None,
        search: Optional[str] = None
    ) -> tuple[List[NotificationTemplateResponse], int, int]:
        """
        List notification templates with pagination and filters

        Args:
            db: Database connection
            page: Page number (1-indexed)
            page_size: Items per page
            is_active: Filter by active status
            notification_type: Filter by notification type
            search: Search in template code and names

        Returns:
            Tuple of (list of templates, total count, total pages)
        """
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 20
        if page_size > 100:
            page_size = 100

        offset = (page - 1) * page_size

        templates, total = await self.repository.find_all(
            db,
            limit=page_size,
            offset=offset,
            is_active=is_active,
            notification_type=notification_type,
            search=search
        )

        total_pages = (total + page_size - 1) // page_size

        return templates, total, total_pages

    async def update_template(
        self,
        db: asyncpg.Connection,
        template_id: int,
        template_data: NotificationTemplateUpdate
    ) -> NotificationTemplateResponse:
        """
        Update notification template

        Args:
            db: Database connection
            template_id: Template ID
            template_data: Updated template data

        Returns:
            Updated notification template

        Raises:
            HTTPException: If template not found
        """
        # Check if template exists
        existing = await self.repository.find_by_id(db, template_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Notification template with ID {template_id} not found"
            )

        # Validate variables if body is being updated
        if any([template_data.body_es, template_data.body_fr, template_data.body_en]):
            self._validate_update_variables(existing, template_data)

        try:
            updated_template = await self.repository.update(db, template_id, template_data)
            if not updated_template:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Notification template with ID {template_id} not found"
                )

            logger.info(f"Updated notification template ID: {template_id}")
            return updated_template

        except Exception as e:
            logger.error(f"Error updating notification template {template_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update notification template"
            )

    async def delete_template(
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
            True if deleted

        Raises:
            HTTPException: If template not found
        """
        try:
            deleted = await self.repository.delete(db, template_id)
            if not deleted:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Notification template with ID {template_id} not found"
                )

            logger.info(f"Deleted notification template ID: {template_id}")
            return True

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error deleting notification template {template_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete notification template"
            )

    async def preview_notification(
        self,
        db: asyncpg.Connection,
        preview_request: NotificationPreviewRequest
    ) -> NotificationPreviewResponse:
        """
        Preview notification with variable substitution

        Args:
            db: Database connection
            preview_request: Preview request with template ID, language, and variables

        Returns:
            Notification preview

        Raises:
            HTTPException: If template not found
        """
        # Get template
        template = await self.get_template_by_id(db, preview_request.template_id)

        # Select language fields
        language = preview_request.language
        if language == "fr":
            title = template.title_fr or template.title_es
            body = template.body_fr or template.body_es
        elif language == "en":
            title = template.title_en or template.title_es
            body = template.body_en or template.body_es
        else:
            title = template.title_es
            body = template.body_es

        # Substitute variables
        title = self._substitute_variables(title, preview_request.variables)
        body = self._substitute_variables(body, preview_request.variables)
        action_url = None
        if template.action_url:
            action_url = self._substitute_variables(template.action_url, preview_request.variables)

        return NotificationPreviewResponse(
            title=title,
            body=body,
            icon=template.icon,
            action_url=action_url,
            notification_type=template.notification_type,
            priority=template.priority
        )

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
        return await self.repository.get_active_templates(db)

    # Helper methods

    def _validate_template_variables(self, template_data: NotificationTemplateCreate) -> None:
        """
        Validate that all declared variables are used in at least one body

        Args:
            template_data: Template data to validate

        Raises:
            HTTPException: If variables are invalid
        """
        if not template_data.variables:
            return

        # Extract variables from all bodies
        bodies = [template_data.body_es]
        if template_data.body_fr:
            bodies.append(template_data.body_fr)
        if template_data.body_en:
            bodies.append(template_data.body_en)

        combined_bodies = " ".join(bodies)
        used_variables = self._extract_variables(combined_bodies)

        # Check if action_url uses variables
        if template_data.action_url:
            used_variables.update(self._extract_variables(template_data.action_url))

        # Warn if declared variables are not used
        unused_variables = set(template_data.variables) - used_variables
        if unused_variables:
            logger.warning(f"Unused variables in template: {unused_variables}")

    def _validate_update_variables(
        self,
        existing_template: NotificationTemplateResponse,
        update_data: NotificationTemplateUpdate
    ) -> None:
        """
        Validate variables when updating template

        Args:
            existing_template: Existing template
            update_data: Update data

        Raises:
            HTTPException: If variables are invalid
        """
        # Merge existing and new data
        body_es = update_data.body_es or existing_template.body_es
        body_fr = update_data.body_fr or existing_template.body_fr
        body_en = update_data.body_en or existing_template.body_en

        bodies = [body_es]
        if body_fr:
            bodies.append(body_fr)
        if body_en:
            bodies.append(body_en)

        combined_bodies = " ".join(bodies)
        used_variables = self._extract_variables(combined_bodies)

        # Check action_url
        action_url = update_data.action_url or existing_template.action_url
        if action_url:
            used_variables.update(self._extract_variables(action_url))

        # Get variables list
        variables = update_data.variables if update_data.variables is not None else existing_template.variables

        # Warn if declared variables are not used
        unused_variables = set(variables) - used_variables
        if unused_variables:
            logger.warning(f"Unused variables in template update: {unused_variables}")

    def _extract_variables(self, text: str) -> set[str]:
        """
        Extract variables from text using {{variable_name}} pattern

        Args:
            text: Text containing variables

        Returns:
            Set of variable names
        """
        pattern = r'\{\{(\w+)\}\}'
        matches = re.findall(pattern, text)
        return set(matches)

    def _substitute_variables(self, text: str, variables: Dict[str, Any]) -> str:
        """
        Substitute variables in text with values

        Args:
            text: Text containing variables
            variables: Variable values

        Returns:
            Text with substituted variables
        """
        for var_name, var_value in variables.items():
            pattern = f"{{{{{var_name}}}}}"
            text = text.replace(pattern, str(var_value))
        return text
