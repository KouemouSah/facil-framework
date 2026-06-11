"""Email Template Service - Business logic for email template management"""

from typing import Optional, List
from loguru import logger
import asyncpg
from pathlib import Path
from fastapi import HTTPException, status

from ..repositories.email_template_repository import EmailTemplateRepository
from ..models.email_template import (
    EmailTemplateCreate,
    EmailTemplateUpdate,
    EmailTemplateResponse,
)


class EmailTemplateService:
    """Service for email template operations with direct DB storage"""

    def __init__(self):
        self.repository = EmailTemplateRepository()
        # Legacy: kept for backwards compatibility
        self.templates_dir = Path(__file__).parent.parent.parent.parent / "templates" / "emails"

    def _get_template_file_path(self, template_code: str) -> Path:
        """Get the full path for a legacy template HTML file"""
        return self.templates_dir / f"{template_code}.html"

    async def create_template(
        self, db: asyncpg.Connection, template_data: EmailTemplateCreate, user_id: int
    ) -> EmailTemplateResponse:
        """Create a new email template - stores HTML in database"""
        existing = await self.repository.get_by_code(db, template_data.template_code)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Template with code '{template_data.template_code}' already exists",
            )

        # Store html_content directly in DB
        db_data = template_data.model_dump()
        db_data["html_file_path"] = None  # Deprecated

        try:
            result = await self.repository.create(db, db_data, user_id)
            return EmailTemplateResponse(**result)
        except Exception as e:
            logger.error(f"Failed to create template: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create template",
            )

    async def get_template(
        self, db: asyncpg.Connection, template_id: int
    ) -> Optional[EmailTemplateResponse]:
        """Get email template by ID"""
        result = await self.repository.get_by_id(db, template_id)
        if not result:
            return None
        return EmailTemplateResponse(**result)

    async def get_template_by_code(
        self, db: asyncpg.Connection, template_code: str
    ) -> Optional[EmailTemplateResponse]:
        """Get email template by code"""
        result = await self.repository.get_by_code(db, template_code)
        if not result:
            return None
        return EmailTemplateResponse(**result)

    async def get_template_html(
        self, db: asyncpg.Connection, template_id: int
    ) -> Optional[str]:
        """Get HTML content. Priority: html_content (DB) > html_file_path (legacy)"""
        template = await self.repository.get_by_id(db, template_id)
        if not template:
            return None

        # Priority 1: Use html_content from database
        if template.get("html_content"):
            return template["html_content"]

        # Priority 2: Legacy - read from file
        html_file_path = self._get_template_file_path(template["template_code"])
        if html_file_path.exists():
            try:
                with open(html_file_path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception as e:
                logger.error(f"Failed to read template file: {e}")
        return None

    async def list_templates(
        self,
        db: asyncpg.Connection,
        category: Optional[str] = None,
        is_active: Optional[bool] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[List[EmailTemplateResponse], int]:
        """List email templates with pagination"""
        offset = (page - 1) * page_size
        templates, total = await self.repository.list(
            db, category=category, is_active=is_active, limit=page_size, offset=offset
        )
        return [EmailTemplateResponse(**t) for t in templates], total

    async def search_templates(
        self,
        db: asyncpg.Connection,
        search_term: str,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[List[EmailTemplateResponse], int]:
        """Search email templates"""
        offset = (page - 1) * page_size
        templates, total = await self.repository.search(
            db, search_term=search_term, limit=page_size, offset=offset
        )
        return [EmailTemplateResponse(**t) for t in templates], total

    async def update_template(
        self,
        db: asyncpg.Connection,
        template_id: int,
        template_data: EmailTemplateUpdate,
        user_id: int,
    ) -> Optional[EmailTemplateResponse]:
        """Update email template - stores html_content directly in DB"""
        existing = await self.repository.get_by_id(db, template_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Template with ID {template_id} not found",
            )

        db_data = template_data.model_dump(exclude_unset=True)
        result = await self.repository.update(db, template_id, db_data, user_id)
        if not result:
            return None
        return EmailTemplateResponse(**result)

    async def delete_template(self, db: asyncpg.Connection, template_id: int) -> bool:
        """Delete email template from database"""
        template = await self.repository.get_by_id(db, template_id)
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Template with ID {template_id} not found",
            )
        return await self.repository.delete(db, template_id)

    async def get_templates_by_category(
        self, db: asyncpg.Connection, category: str
    ) -> List[EmailTemplateResponse]:
        """Get all active templates in a category"""
        templates = await self.repository.get_by_category(db, category)
        return [EmailTemplateResponse(**t) for t in templates]
