"""
SMS Template Service - Business logic for SMS template management

Handles template rendering, variable substitution, character counting,
and SMS segmentation calculations.
"""

import re
import asyncpg
from typing import Optional, List, Dict, Any
from loguru import logger

from ..models.sms_template import (
    SmsTemplateCreate,
    SmsTemplateUpdate,
    SmsTemplateResponse,
    SmsTemplateListResponse,
    SmsCharacterCount,
    SmsTemplateRenderRequest,
    SmsTemplateRenderResponse
)
from ..repositories.sms_template_repository import SmsTemplateRepository


class SmsTemplateService:
    """Service for SMS template business logic"""

    def __init__(self):
        self.repository = SmsTemplateRepository()

    async def create_template(
        self,
        db: asyncpg.Connection,
        template_data: SmsTemplateCreate,
        created_by: Optional[int] = None
    ) -> SmsTemplateResponse:
        """
        Create a new SMS template with validation

        Args:
            db: Database connection
            template_data: Template data
            created_by: User ID who created the template

        Returns:
            Created template

        Raises:
            ValueError: If validation fails
        """
        # Validate template variables match content placeholders
        self._validate_template_variables(template_data)

        # Validate content length against max_segments
        self._validate_content_length(template_data)

        return await self.repository.create(db, template_data, created_by)

    async def get_template_by_id(
        self,
        db: asyncpg.Connection,
        template_id: int
    ) -> Optional[SmsTemplateResponse]:
        """Get SMS template by ID"""
        return await self.repository.find_by_id(db, template_id)

    async def get_template_by_code(
        self,
        db: asyncpg.Connection,
        template_code: str
    ) -> Optional[SmsTemplateResponse]:
        """Get SMS template by code"""
        return await self.repository.find_by_code(db, template_code)

    async def list_templates(
        self,
        db: asyncpg.Connection,
        category: Optional[str] = None,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> SmsTemplateListResponse:
        """
        List SMS templates with pagination

        Args:
            db: Database connection
            category: Filter by category
            is_active: Filter by active status
            search: Search term
            page: Page number (1-indexed)
            page_size: Items per page

        Returns:
            Paginated list of templates
        """
        offset = (page - 1) * page_size
        templates, total = await self.repository.find_all(
            db,
            category=category,
            is_active=is_active,
            search=search,
            limit=page_size,
            offset=offset
        )

        total_pages = (total + page_size - 1) // page_size

        return SmsTemplateListResponse(
            templates=templates,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )

    async def update_template(
        self,
        db: asyncpg.Connection,
        template_id: int,
        template_data: SmsTemplateUpdate,
        updated_by: Optional[int] = None
    ) -> Optional[SmsTemplateResponse]:
        """
        Update SMS template with validation

        Args:
            db: Database connection
            template_id: Template ID
            template_data: Updated data
            updated_by: User ID who updated

        Returns:
            Updated template if found

        Raises:
            ValueError: If validation fails
        """
        # Get existing template
        existing = await self.repository.find_by_id(db, template_id)
        if not existing:
            return None

        # Validate variables if provided
        if template_data.variables is not None:
            # Merge with existing content to validate
            content_es = template_data.content_es or existing.content_es
            content_fr = template_data.content_fr or existing.content_fr
            content_en = template_data.content_en or existing.content_en

            self._validate_variables_match_content(
                template_data.variables,
                content_es,
                content_fr,
                content_en
            )

        return await self.repository.update(db, template_id, template_data, updated_by)

    async def delete_template(
        self,
        db: asyncpg.Connection,
        template_id: int
    ) -> bool:
        """Delete SMS template"""
        return await self.repository.delete(db, template_id)

    async def get_categories(
        self,
        db: asyncpg.Connection
    ) -> List[Dict[str, Any]]:
        """Get template categories with counts"""
        return await self.repository.get_categories(db)

    def calculate_character_count(self, content: str) -> SmsCharacterCount:
        """
        Calculate SMS character count and segmentation

        Args:
            content: SMS content

        Returns:
            Character count information
        """
        uses_unicode = self._uses_unicode(content)
        chars_per_segment = 70 if uses_unicode else 160
        chars_per_segment_concat = 67 if uses_unicode else 153

        length = len(content)

        if length == 0:
            segment_count = 0
            chars_remaining = chars_per_segment
        elif length <= chars_per_segment:
            segment_count = 1
            chars_remaining = chars_per_segment - length
        else:
            segment_count = (length + chars_per_segment_concat - 1) // chars_per_segment_concat
            chars_used_in_last = length % chars_per_segment_concat
            if chars_used_in_last == 0:
                chars_used_in_last = chars_per_segment_concat
            chars_remaining = chars_per_segment_concat - chars_used_in_last

        return SmsCharacterCount(
            content=content,
            character_count=length,
            segment_count=segment_count,
            characters_per_segment=chars_per_segment,
            characters_remaining=chars_remaining,
            uses_unicode=uses_unicode
        )

    async def render_template(
        self,
        db: asyncpg.Connection,
        request: SmsTemplateRenderRequest
    ) -> SmsTemplateRenderResponse:
        """
        Render SMS template with variable substitution

        Args:
            db: Database connection
            request: Render request with template code, language, and variables

        Returns:
            Rendered template with character count

        Raises:
            ValueError: If template not found or variables missing
        """
        # Get template
        template = await self.repository.find_by_code(db, request.template_code)
        if not template:
            raise ValueError(f"Template not found: {request.template_code}")

        if not template.is_active:
            raise ValueError(f"Template is not active: {request.template_code}")

        # Get content for requested language
        content = self._get_content_by_language(template, request.language)
        if not content:
            raise ValueError(
                f"No content available for language '{request.language}' "
                f"in template '{request.template_code}'"
            )

        # Render template with variables
        rendered_content = self._render_content(content, request.variables)

        # Calculate character count
        char_count = self.calculate_character_count(rendered_content)

        return SmsTemplateRenderResponse(
            template_code=request.template_code,
            language=request.language,
            rendered_content=rendered_content,
            character_count=char_count.character_count,
            segment_count=char_count.segment_count,
            variables_used=request.variables
        )

    # =========================================================================
    # PRIVATE HELPER METHODS
    # =========================================================================

    def _validate_template_variables(self, template_data: SmsTemplateCreate) -> None:
        """
        Validate that template variables match content placeholders

        Args:
            template_data: Template data to validate

        Raises:
            ValueError: If validation fails
        """
        self._validate_variables_match_content(
            template_data.variables,
            template_data.content_es,
            template_data.content_fr,
            template_data.content_en
        )

    def _validate_variables_match_content(
        self,
        variables: List[str],
        content_es: str,
        content_fr: Optional[str],
        content_en: Optional[str]
    ) -> None:
        """Validate variables match content placeholders"""
        # Extract placeholders from content
        placeholders_es = self._extract_placeholders(content_es)
        placeholders_fr = self._extract_placeholders(content_fr) if content_fr else set()
        placeholders_en = self._extract_placeholders(content_en) if content_en else set()

        all_placeholders = placeholders_es | placeholders_fr | placeholders_en
        variable_set = set(variables)

        # Check if all placeholders are defined in variables
        undefined = all_placeholders - variable_set
        if undefined:
            raise ValueError(
                f"Placeholders used in content but not defined in variables: {sorted(undefined)}"
            )

        # Check if all variables are used in at least one content
        unused = variable_set - all_placeholders
        if unused:
            logger.warning(
                f"Variables defined but not used in any content: {sorted(unused)}"
            )

    def _validate_content_length(self, template_data: SmsTemplateCreate) -> None:
        """
        Validate content length against max_segments

        Args:
            template_data: Template data to validate

        Raises:
            ValueError: If content exceeds max_segments
        """
        max_segments = template_data.max_segments

        # Check Spanish content (required)
        es_segments = self._calculate_segments(template_data.content_es)
        if es_segments > max_segments:
            raise ValueError(
                f"Spanish content exceeds max_segments ({es_segments} > {max_segments})"
            )

        # Check French content (optional)
        if template_data.content_fr:
            fr_segments = self._calculate_segments(template_data.content_fr)
            if fr_segments > max_segments:
                raise ValueError(
                    f"French content exceeds max_segments ({fr_segments} > {max_segments})"
                )

        # Check English content (optional)
        if template_data.content_en:
            en_segments = self._calculate_segments(template_data.content_en)
            if en_segments > max_segments:
                raise ValueError(
                    f"English content exceeds max_segments ({en_segments} > {max_segments})"
                )

    def _extract_placeholders(self, content: str) -> set:
        """
        Extract placeholder variable names from content

        Args:
            content: SMS content with {{variable}} placeholders

        Returns:
            Set of variable names
        """
        if not content:
            return set()

        # Find all {{variable}} patterns
        pattern = r'\{\{(\w+)\}\}'
        matches = re.findall(pattern, content)
        return set(matches)

    def _get_content_by_language(
        self,
        template: SmsTemplateResponse,
        language: str
    ) -> Optional[str]:
        """Get template content for specified language"""
        if language == "es":
            return template.content_es
        elif language == "fr":
            return template.content_fr
        elif language == "en":
            return template.content_en
        else:
            return template.content_es  # Fallback to Spanish

    def _render_content(
        self,
        content: str,
        variables: Dict[str, Any]
    ) -> str:
        """
        Render content by replacing {{variable}} placeholders

        Args:
            content: Template content
            variables: Variable values

        Returns:
            Rendered content

        Raises:
            ValueError: If required variables are missing
        """
        placeholders = self._extract_placeholders(content)

        # Check if all required variables are provided
        missing = placeholders - set(variables.keys())
        if missing:
            raise ValueError(f"Missing required variables: {sorted(missing)}")

        # Replace placeholders
        rendered = content
        for var_name, var_value in variables.items():
            placeholder = f"{{{{{var_name}}}}}"
            rendered = rendered.replace(placeholder, str(var_value))

        return rendered

    def _calculate_segments(self, content: str) -> int:
        """Calculate SMS segments for content"""
        return self.repository._calculate_segments(content)

    def _uses_unicode(self, content: str) -> bool:
        """Check if content uses Unicode characters"""
        return self.repository._uses_unicode(content)
