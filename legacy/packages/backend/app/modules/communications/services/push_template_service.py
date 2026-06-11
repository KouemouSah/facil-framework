"""
Push Template Service - Business logic for push notification templates

Handles:
- Push template CRUD operations
- Template variable validation
- Preview generation with sample data
- Template rendering with variables

Module: Communications
"""

import asyncpg
import re
from typing import Optional, List, Dict, Any
from loguru import logger

from ..models.push_template import (
    PushTemplateCreate,
    PushTemplateUpdate,
    PushTemplateResponse,
    PushTemplateListResponse,
    PushNotificationPreview,
    PlatformEnum
)
from ..repositories.push_template_repository import PushTemplateRepository


class PushTemplateService:
    """Business logic for push template operations"""

    def __init__(self):
        self.repository = PushTemplateRepository()

    async def create_template(
        self,
        db: asyncpg.Connection,
        template_data: PushTemplateCreate,
        created_by: int
    ) -> PushTemplateResponse:
        """
        Create new push template with validation

        Args:
            db: Database connection
            template_data: Template data
            created_by: User ID

        Returns:
            Created template

        Raises:
            ValueError: If validation fails
        """
        # Validate template variables
        self._validate_template_variables(template_data)

        # Create template
        template = await self.repository.create(db, template_data, created_by)

        logger.info(
            f"Push template created",
            template_id=template.id,
            template_code=template.template_code,
            created_by=created_by
        )

        return template

    async def get_template(
        self,
        db: asyncpg.Connection,
        template_id: int
    ) -> PushTemplateResponse:
        """
        Get push template by ID

        Args:
            db: Database connection
            template_id: Template ID

        Returns:
            Template

        Raises:
            ValueError: If template not found
        """
        template = await self.repository.find_by_id(db, template_id)

        if not template:
            raise ValueError(f"Push template not found: {template_id}")

        return template

    async def get_template_by_code(
        self,
        db: asyncpg.Connection,
        template_code: str
    ) -> PushTemplateResponse:
        """
        Get push template by code

        Args:
            db: Database connection
            template_code: Template code

        Returns:
            Template

        Raises:
            ValueError: If template not found
        """
        template = await self.repository.find_by_code(db, template_code)

        if not template:
            raise ValueError(f"Push template not found: {template_code}")

        return template

    async def list_templates(
        self,
        db: asyncpg.Connection,
        page: int = 1,
        page_size: int = 20,
        is_active: Optional[bool] = None,
        platform: Optional[PlatformEnum] = None,
        search: Optional[str] = None
    ) -> PushTemplateListResponse:
        """
        List push templates with pagination and filters

        Args:
            db: Database connection
            page: Page number
            page_size: Items per page
            is_active: Filter by active status
            platform: Filter by platform
            search: Search query

        Returns:
            List response with pagination
        """
        templates, total = await self.repository.find_all(
            db,
            page=page,
            page_size=page_size,
            is_active=is_active,
            platform=platform,
            search=search
        )

        return PushTemplateListResponse(
            templates=templates,
            total=total,
            page=page,
            page_size=page_size
        )

    async def update_template(
        self,
        db: asyncpg.Connection,
        template_id: int,
        template_data: PushTemplateUpdate
    ) -> PushTemplateResponse:
        """
        Update push template

        Args:
            db: Database connection
            template_id: Template ID
            template_data: Update data

        Returns:
            Updated template

        Raises:
            ValueError: If template not found or validation fails
        """
        # Check if template exists
        existing = await self.repository.find_by_id(db, template_id)
        if not existing:
            raise ValueError(f"Push template not found: {template_id}")

        # Validate variables if updating content
        if any([
            template_data.title_es,
            template_data.title_fr,
            template_data.title_en,
            template_data.body_es,
            template_data.body_fr,
            template_data.body_en
        ]):
            # Create temporary model for validation
            temp_data = PushTemplateCreate(
                template_code=existing.template_code,
                name_es=template_data.name_es or existing.name_es,
                name_fr=template_data.name_fr or existing.name_fr,
                name_en=template_data.name_en or existing.name_en,
                title_es=template_data.title_es or existing.title_es,
                title_fr=template_data.title_fr or existing.title_fr,
                title_en=template_data.title_en or existing.title_en,
                body_es=template_data.body_es or existing.body_es,
                body_fr=template_data.body_fr or existing.body_fr,
                body_en=template_data.body_en or existing.body_en,
                variables=template_data.variables or existing.variables
            )
            self._validate_template_variables(temp_data)

        # Update template
        template = await self.repository.update(db, template_id, template_data)

        logger.info(
            f"Push template updated",
            template_id=template_id,
            template_code=template.template_code
        )

        return template

    async def delete_template(
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
            True if deleted

        Raises:
            ValueError: If template not found
        """
        # Check if template exists
        existing = await self.repository.find_by_id(db, template_id)
        if not existing:
            raise ValueError(f"Push template not found: {template_id}")

        # Delete template
        deleted = await self.repository.delete(db, template_id)

        logger.info(
            f"Push template deleted",
            template_id=template_id,
            template_code=existing.template_code
        )

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
        return await self.repository.get_stats(db)

    def preview_template(
        self,
        template: PushTemplateResponse,
        language: str = "es",
        variables: Optional[Dict[str, str]] = None
    ) -> PushNotificationPreview:
        """
        Generate preview of push notification with sample data

        Args:
            template: Template to preview
            language: Language code (es/fr/en)
            variables: Variable values for preview

        Returns:
            Preview with rendered content
        """
        # Get localized title and body
        title = self._get_localized_field(template, "title", language)
        body = self._get_localized_field(template, "body", language)

        # Replace variables
        variables_used = variables or {}
        if not variables_used:
            # Generate sample data for variables
            for var in template.variables:
                variables_used[var] = f"<{var}>"

        rendered_title = self._render_template_string(title, variables_used)
        rendered_body = self._render_template_string(body, variables_used)

        return PushNotificationPreview(
            title=rendered_title,
            body=rendered_body,
            image_url=template.image_url,
            icon_url=template.icon_url,
            platform=template.platform,
            variables_used=variables_used
        )

    def render_notification(
        self,
        template: PushTemplateResponse,
        language: str = "es",
        variables: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Render push notification for sending via FCM

        Args:
            template: Template to render
            language: Language code
            variables: Variable values

        Returns:
            FCM notification payload
        """
        # Get localized content
        title = self._get_localized_field(template, "title", language)
        body = self._get_localized_field(template, "body", language)

        # Replace variables
        variables_dict = variables or {}
        rendered_title = self._render_template_string(title, variables_dict)
        rendered_body = self._render_template_string(body, variables_dict)

        # Build FCM payload
        notification = {
            "title": rendered_title,
            "body": rendered_body
        }

        if template.image_url:
            notification["image"] = template.image_url

        if template.icon_url:
            notification["icon"] = template.icon_url

        # Build data payload
        data = dict(template.data_payload)
        if template.click_action:
            data["click_action"] = template.click_action

        # Platform-specific options
        android_config = {
            "ttl": f"{template.ttl_seconds}s",
            "priority": "high"
        }

        apns_config = {
            "payload": {
                "aps": {
                    "sound": "default",
                    "badge": 1
                }
            }
        }

        if template.click_action:
            apns_config["payload"]["aps"]["category"] = template.click_action

        return {
            "notification": notification,
            "data": data,
            "android": android_config,
            "apns": apns_config
        }

    def _validate_template_variables(self, template_data: PushTemplateCreate):
        """
        Validate that all variables used in templates are declared

        Args:
            template_data: Template data

        Raises:
            ValueError: If undeclared variables are used
        """
        declared_vars = set(template_data.variables or [])

        # Extract variables from all text fields
        used_vars = set()

        for field in [
            template_data.title_es, template_data.title_fr, template_data.title_en,
            template_data.body_es, template_data.body_fr, template_data.body_en
        ]:
            if field:
                vars_in_field = re.findall(r'\{(\w+)\}', field)
                used_vars.update(vars_in_field)

        # Check for undeclared variables
        undeclared = used_vars - declared_vars
        if undeclared:
            raise ValueError(
                f"Undeclared variables found in template: {', '.join(undeclared)}. "
                f"Please add them to the 'variables' field."
            )

        # Check for unused declared variables (warning only)
        unused = declared_vars - used_vars
        if unused:
            logger.warning(
                f"Template '{template_data.template_code}' has declared but unused variables: {', '.join(unused)}"
            )

    def _get_localized_field(
        self,
        template: PushTemplateResponse,
        field_name: str,
        language: str
    ) -> str:
        """Get localized field value with fallback"""
        # Try requested language
        value = getattr(template, f"{field_name}_{language}", None)
        if value:
            return value

        # Fallback to Spanish
        value = getattr(template, f"{field_name}_es", None)
        if value:
            return value

        # Fallback to English
        value = getattr(template, f"{field_name}_en", None)
        if value:
            return value

        # Fallback to French
        value = getattr(template, f"{field_name}_fr", None)
        if value:
            return value

        return ""

    def _render_template_string(
        self,
        template: str,
        variables: Dict[str, str]
    ) -> str:
        """
        Render template string with variables

        Args:
            template: Template string with {variable} placeholders
            variables: Variable values

        Returns:
            Rendered string
        """
        result = template
        for key, value in variables.items():
            result = result.replace(f"{{{key}}}", str(value))

        return result


# ============================================================================
# FACTORY FUNCTION
# ============================================================================

def get_push_template_service() -> PushTemplateService:
    """
    Get PushTemplateService instance

    Returns:
        PushTemplateService instance
    """
    return PushTemplateService()
