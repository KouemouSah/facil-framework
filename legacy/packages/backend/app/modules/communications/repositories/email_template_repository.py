"""Email Template Repository - Data access for email templates"""

from typing import Optional, List, Dict, Any
from loguru import logger
import asyncpg
import json


class EmailTemplateRepository:
    """Repository for email templates CRUD operations"""

    def _normalize_variables(self, variables: list) -> list:
        """
        Normalize variables to TemplateVariable format.
        Handles legacy data where variables were stored as simple strings.

        Legacy format: ['user_name', 'appointment_date']
        Expected format: [{'name': 'user_name', 'description': 'user_name', 'required': True}, ...]
        """
        if not variables:
            return []

        normalized = []
        for var in variables:
            if isinstance(var, str):
                # Legacy format - convert string to TemplateVariable dict
                normalized.append({
                    "name": var,
                    "description": var.replace("_", " ").title(),
                    "example": None,
                    "required": True
                })
            elif isinstance(var, dict):
                # Already in correct format, ensure all fields exist
                normalized.append({
                    "name": var.get("name", "unknown"),
                    "description": var.get("description", var.get("name", "unknown")),
                    "example": var.get("example"),
                    "required": var.get("required", True)
                })
            else:
                # Unknown format, skip
                continue
        return normalized

    async def create(
        self, conn: asyncpg.Connection, data: Dict[str, Any], user_id: int
    ) -> Dict[str, Any]:
        """Create a new email template"""
        query = """
            INSERT INTO email_templates (
                template_code, name_es, name_fr, name_en,
                subject_es, subject_fr, subject_en,
                description_es, description_fr, description_en,
                html_content, html_file_path, variables, category, is_active,
                created_by, updated_by
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $16)
            RETURNING *
        """

        # Convert variables list to JSONB
        variables_json = json.dumps(data.get("variables", []))

        result = await conn.fetchrow(
            query,
            data.get("template_code"),
            data.get("name_es"),
            data.get("name_fr"),
            data.get("name_en"),
            data.get("subject_es"),
            data.get("subject_fr"),
            data.get("subject_en"),
            data.get("description_es"),
            data.get("description_fr"),
            data.get("description_en"),
            data.get("html_content"),
            data.get("html_file_path"),
            variables_json,
            data.get("category"),
            data.get("is_active", True),
            user_id,
        )

        template_dict = dict(result)

        # Parse JSONB variables back to list and normalize
        if isinstance(template_dict.get("variables"), str):
            template_dict["variables"] = json.loads(template_dict["variables"])
        if not isinstance(template_dict.get("variables"), list):
            template_dict["variables"] = []
        template_dict["variables"] = self._normalize_variables(template_dict["variables"])

        return template_dict

    async def get_by_id(
        self, conn: asyncpg.Connection, template_id: int
    ) -> Optional[Dict[str, Any]]:
        """Get email template by ID with user names"""
        query = """
            SELECT
                et.*,
                u_created.full_name as created_by_name,
                u_updated.full_name as updated_by_name
            FROM email_templates et
            LEFT JOIN users u_created ON et.created_by = u_created.id
            LEFT JOIN users u_updated ON et.updated_by = u_updated.id
            WHERE et.id = $1
        """
        result = await conn.fetchrow(query, template_id)

        if not result:
            return None

        template_dict = dict(result)

        # Parse JSONB variables and normalize
        if isinstance(template_dict.get("variables"), str):
            template_dict["variables"] = json.loads(template_dict["variables"])
        if not isinstance(template_dict.get("variables"), list):
            template_dict["variables"] = []
        template_dict["variables"] = self._normalize_variables(template_dict["variables"])

        return template_dict

    async def get_by_code(
        self, conn: asyncpg.Connection, template_code: str
    ) -> Optional[Dict[str, Any]]:
        """Get email template by code"""
        query = """
            SELECT
                et.*,
                u_created.full_name as created_by_name,
                u_updated.full_name as updated_by_name
            FROM email_templates et
            LEFT JOIN users u_created ON et.created_by = u_created.id
            LEFT JOIN users u_updated ON et.updated_by = u_updated.id
            WHERE et.template_code = $1
        """
        result = await conn.fetchrow(query, template_code)

        if not result:
            return None

        template_dict = dict(result)

        # Parse JSONB variables and normalize
        if isinstance(template_dict.get("variables"), str):
            template_dict["variables"] = json.loads(template_dict["variables"])
        if not isinstance(template_dict.get("variables"), list):
            template_dict["variables"] = []
        template_dict["variables"] = self._normalize_variables(template_dict["variables"])

        return template_dict

    async def list(
        self,
        conn: asyncpg.Connection,
        category: Optional[str] = None,
        is_active: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[List[Dict[str, Any]], int]:
        """List email templates with filters and pagination"""
        conditions = []
        params = []
        param_idx = 1

        if category:
            conditions.append(f"et.category = ${param_idx}")
            params.append(category)
            param_idx += 1

        if is_active is not None:
            conditions.append(f"et.is_active = ${param_idx}")
            params.append(is_active)
            param_idx += 1

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        # Count
        count_query = f"SELECT COUNT(*) FROM email_templates et {where_clause}"
        total = await conn.fetchval(count_query, *params)

        # Data
        data_query = f"""
            SELECT
                et.*,
                u_created.full_name as created_by_name,
                u_updated.full_name as updated_by_name
            FROM email_templates et
            LEFT JOIN users u_created ON et.created_by = u_created.id
            LEFT JOIN users u_updated ON et.updated_by = u_updated.id
            {where_clause}
            ORDER BY et.category, et.template_code
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        params.extend([limit, offset])
        results = await conn.fetch(data_query, *params)

        templates = []
        for r in results:
            template = dict(r)
            # Parse JSONB variables and normalize
            if isinstance(template.get("variables"), str):
                template["variables"] = json.loads(template["variables"])
            if not isinstance(template.get("variables"), list):
                template["variables"] = []
            template["variables"] = self._normalize_variables(template["variables"])
            templates.append(template)

        return templates, total

    async def update(
        self,
        conn: asyncpg.Connection,
        template_id: int,
        data: Dict[str, Any],
        user_id: int,
    ) -> Optional[Dict[str, Any]]:
        """Update email template"""
        updates = []
        params = [template_id]
        param_idx = 2

        # Handle variables separately (JSONB)
        variables_to_update = None
        for field, value in data.items():
            if value is not None:
                if field == "variables":
                    variables_to_update = json.dumps(value)
                    updates.append(f"variables = ${param_idx}")
                    params.append(variables_to_update)
                    param_idx += 1
                else:
                    updates.append(f"{field} = ${param_idx}")
                    params.append(value)
                    param_idx += 1

        if not updates:
            return await self.get_by_id(conn, template_id)

        # Always update updated_by and updated_at
        updates.append(f"updated_by = ${param_idx}")
        params.append(user_id)
        param_idx += 1
        updates.append("updated_at = NOW()")

        query = f"UPDATE email_templates SET {', '.join(updates)} WHERE id = $1 RETURNING *"
        result = await conn.fetchrow(query, *params)

        if not result:
            return None

        return await self.get_by_id(conn, template_id)

    async def delete(self, conn: asyncpg.Connection, template_id: int) -> bool:
        """Delete email template"""
        result = await conn.execute(
            "DELETE FROM email_templates WHERE id = $1", template_id
        )
        return result == "DELETE 1"

    async def search(
        self,
        conn: asyncpg.Connection,
        search_term: str,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[List[Dict[str, Any]], int]:
        """Search email templates by name or code"""
        search_pattern = f"%{search_term}%"

        # Count
        count_query = """
            SELECT COUNT(*)
            FROM email_templates
            WHERE template_code ILIKE $1
               OR name_es ILIKE $1
               OR name_fr ILIKE $1
               OR name_en ILIKE $1
        """
        total = await conn.fetchval(count_query, search_pattern)

        # Data
        data_query = """
            SELECT
                et.*,
                u_created.full_name as created_by_name,
                u_updated.full_name as updated_by_name
            FROM email_templates et
            LEFT JOIN users u_created ON et.created_by = u_created.id
            LEFT JOIN users u_updated ON et.updated_by = u_updated.id
            WHERE et.template_code ILIKE $1
               OR et.name_es ILIKE $1
               OR et.name_fr ILIKE $1
               OR et.name_en ILIKE $1
            ORDER BY et.template_code
            LIMIT $2 OFFSET $3
        """
        results = await conn.fetch(data_query, search_pattern, limit, offset)

        templates = []
        for r in results:
            template = dict(r)
            # Parse JSONB variables and normalize
            if isinstance(template.get("variables"), str):
                template["variables"] = json.loads(template["variables"])
            if not isinstance(template.get("variables"), list):
                template["variables"] = []
            template["variables"] = self._normalize_variables(template["variables"])
            templates.append(template)

        return templates, total

    async def get_by_category(
        self, conn: asyncpg.Connection, category: str
    ) -> List[Dict[str, Any]]:
        """Get all active templates in a category"""
        query = """
            SELECT
                et.*,
                u_created.full_name as created_by_name,
                u_updated.full_name as updated_by_name
            FROM email_templates et
            LEFT JOIN users u_created ON et.created_by = u_created.id
            LEFT JOIN users u_updated ON et.updated_by = u_updated.id
            WHERE et.category = $1 AND et.is_active = true
            ORDER BY et.template_code
        """
        results = await conn.fetch(query, category)

        templates = []
        for r in results:
            template = dict(r)
            # Parse JSONB variables and normalize
            if isinstance(template.get("variables"), str):
                template["variables"] = json.loads(template["variables"])
            if not isinstance(template.get("variables"), list):
                template["variables"] = []
            template["variables"] = self._normalize_variables(template["variables"])
            templates.append(template)

        return templates
