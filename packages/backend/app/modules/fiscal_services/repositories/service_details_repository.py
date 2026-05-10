"""
Service Details Repository - Complete service information with documents and procedures
Optimized SQL queries with i18n support
"""

from typing import Dict, Any, List, Optional
import asyncpg
from loguru import logger


class ServiceDetailsRepository:
    """Repository for fetching complete service details with translations"""

    async def get_service_details(
        self,
        conn: asyncpg.Connection,
        service_id: int,
        language: str = "es",
    ) -> Optional[Dict[str, Any]]:
        """
        Get complete service details with all related information

        Args:
            conn: Database connection
            service_id: Service ID
            language: Language code for translations (es, fr, en)

        Returns:
            Complete service details dict or None if not found
        """
        # Main service query with translations
        service_query = """
            SELECT
                fs.id,
                fs.service_code,
                COALESCE(et_name.translation_text, fs.name_es) as name,
                CASE WHEN COALESCE(fs.description_visible, true)
                     THEN COALESCE(et_desc.translation_text, fs.description_es)
                     ELSE NULL
                END as description,
                fs.service_type,
                fs.status,
                COALESCE(fs.calculation_method, 'fixed_expedition') as calculation_method,
                COALESCE(fs.tasa_expedicion, 0) as expedition_price,
                COALESCE(fs.tasa_renovacion, 0) as renewal_price,
                fs.base_percentage as percentage_rate,
                fs.unit_rate as unit_price,
                fs.validity_period_months,
                fs.renewal_frequency_months,
                fs.processing_time_days,
                fs.legal_reference,
                NULL::text as notes,
                fs.parent_service_id,
                fs.calculation_config,
                COALESCE(fs.view_count, 0) as view_count,
                COALESCE(fs.calculation_count, 0) as calculation_count,
                fs.updated_at as last_updated,
                -- Category
                c.id as category_id,
                c.category_code,
                COALESCE(et_cat.translation_text, c.name_es) as category_name,
                COALESCE(et_cat_desc.translation_text, c.description_es) as category_description,
                c.icon as category_icon,
                c.color as category_color,
                -- Sector
                s.id as sector_id,
                s.sector_code as sector_code,
                COALESCE(et_sec.translation_text, s.name_es) as sector_name,
                COALESCE(et_sec_desc.translation_text, s.description_es) as sector_description,
                -- Ministry
                m.id as ministry_id,
                m.ministry_code as ministry_code,
                COALESCE(et_min.translation_text, m.name_es) as ministry_name,
                COALESCE(et_min_desc.translation_text, m.description_es) as ministry_description
            FROM fiscal_services fs
            LEFT JOIN categories c ON fs.category_id = c.id
            LEFT JOIN sectors s ON c.sector_id = s.id
            LEFT JOIN ministries m ON s.ministry_id = m.id
            -- Service translations
            LEFT JOIN entity_translations et_name ON
                et_name.entity_type = 'service'
                AND et_name.entity_code = fs.service_code
                AND et_name.field_name = 'name'
                AND et_name.language_code = $2
            LEFT JOIN entity_translations et_desc ON
                et_desc.entity_type = 'service'
                AND et_desc.entity_code = fs.service_code
                AND et_desc.field_name = 'description'
                AND et_desc.language_code = $2
            -- Category translations
            LEFT JOIN entity_translations et_cat ON
                et_cat.entity_type = 'category'
                AND et_cat.entity_code = c.category_code
                AND et_cat.field_name = 'name'
                AND et_cat.language_code = $2
            LEFT JOIN entity_translations et_cat_desc ON
                et_cat_desc.entity_type = 'category'
                AND et_cat_desc.entity_code = c.category_code
                AND et_cat_desc.field_name = 'description'
                AND et_cat_desc.language_code = $2
            -- Sector translations
            LEFT JOIN entity_translations et_sec ON
                et_sec.entity_type = 'sector'
                AND et_sec.entity_code = s.sector_code
                AND et_sec.field_name = 'name'
                AND et_sec.language_code = $2
            LEFT JOIN entity_translations et_sec_desc ON
                et_sec_desc.entity_type = 'sector'
                AND et_sec_desc.entity_code = s.sector_code
                AND et_sec_desc.field_name = 'description'
                AND et_sec_desc.language_code = $2
            -- Ministry translations
            LEFT JOIN entity_translations et_min ON
                et_min.entity_type = 'ministry'
                AND et_min.entity_code = m.ministry_code
                AND et_min.field_name = 'name'
                AND et_min.language_code = $2
            LEFT JOIN entity_translations et_min_desc ON
                et_min_desc.entity_type = 'ministry'
                AND et_min_desc.entity_code = m.ministry_code
                AND et_min_desc.field_name = 'description'
                AND et_min_desc.language_code = $2
            WHERE fs.id = $1
        """

        try:
            row = await conn.fetchrow(service_query, service_id, language)
            if not row:
                return None

            service = dict(row)
            return service

        except asyncpg.PostgresError as e:
            logger.error(f"Error fetching service details: {e}")
            raise

    async def increment_view_count(self, conn: asyncpg.Connection, service_id: int):
        """Increment view count (non-critical)"""
        try:
            await conn.execute(
                "UPDATE fiscal_services SET view_count = COALESCE(view_count, 0) + 1 WHERE id = $1",
                service_id
            )
        except Exception:
            pass

    async def get_service_documents(
        self,
        conn: asyncpg.Connection,
        service_id: int,
        language: str = "es",
    ) -> List[Dict[str, Any]]:
        """Get all documents required for a service"""
        query = """
            SELECT
                dt.id,
                dt.template_code,
                COALESCE(et_name.translation_text, dt.document_name_es) as name,
                COALESCE(et_desc.translation_text, dt.description_es) as description,
                dt.category,
                dt.validity_duration_months,
                dt.validity_notes,
                sda.is_required_expedition,
                sda.is_required_renewal,
                sda.display_order,
                sda.custom_notes
            FROM service_document_assignments sda
            JOIN document_templates dt ON sda.document_template_id = dt.id
            LEFT JOIN entity_translations et_name ON
                et_name.entity_type = 'document_template'
                AND et_name.entity_code = dt.template_code
                AND et_name.field_name = 'name'
                AND et_name.language_code = $2
            LEFT JOIN entity_translations et_desc ON
                et_desc.entity_type = 'document_template'
                AND et_desc.entity_code = dt.template_code
                AND et_desc.field_name = 'description'
                AND et_desc.language_code = $2
            WHERE sda.fiscal_service_id = $1 AND dt.is_active = true
            ORDER BY sda.display_order, dt.document_name_es
        """

        try:
            rows = await conn.fetch(query, service_id, language)
            return [dict(row) for row in rows]
        except asyncpg.PostgresError as e:
            logger.error(f"Error fetching service documents: {e}")
            return []

    async def get_service_procedures(
        self,
        conn: asyncpg.Connection,
        service_id: int,
        language: str = "es",
    ) -> List[Dict[str, Any]]:
        """Get all procedures for a service with their steps"""
        logger.info(f"[PROCEDURES] Fetching procedures for service_id={service_id}, language={language}")

        # Get procedures
        procedures_query = """
            SELECT
                pt.id,
                pt.template_code,
                COALESCE(et_name.translation_text, pt.name_es) as name,
                COALESCE(et_desc.translation_text, pt.description_es) as description,
                pt.category,
                spa.applies_to,
                spa.display_order,
                spa.custom_notes
            FROM service_procedure_assignments spa
            JOIN procedure_templates pt ON spa.template_id = pt.id
            LEFT JOIN entity_translations et_name ON
                et_name.entity_type = 'procedure_template'
                AND et_name.entity_code = pt.template_code
                AND et_name.field_name = 'name'
                AND et_name.language_code = $2
            LEFT JOIN entity_translations et_desc ON
                et_desc.entity_type = 'procedure_template'
                AND et_desc.entity_code = pt.template_code
                AND et_desc.field_name = 'description'
                AND et_desc.language_code = $2
            WHERE spa.fiscal_service_id = $1 AND pt.is_active = true
            ORDER BY spa.display_order, pt.name_es
        """

        try:
            procedure_rows = await conn.fetch(procedures_query, service_id, language)
            if not procedure_rows:
                return []

            procedures = [dict(row) for row in procedure_rows]
            procedure_ids = [p["id"] for p in procedures]

            # Batch fetch ALL steps for ALL procedures in 1 query (eliminates N+1)
            all_steps_query = """
                SELECT
                    pts.template_id,
                    pts.id,
                    pts.step_number,
                    COALESCE(et_desc.translation_text, pts.description_es) as description,
                    COALESCE(et_inst.translation_text, pts.instructions_es) as instructions,
                    pts.estimated_duration_minutes,
                    pts.location_address,
                    pts.office_hours,
                    pts.requires_appointment,
                    pts.is_optional
                FROM procedure_template_steps pts
                LEFT JOIN procedure_templates pt_ref ON pts.template_id = pt_ref.id
                LEFT JOIN entity_translations et_desc ON
                    et_desc.entity_type = 'procedure_step'
                    AND et_desc.entity_code = pt_ref.template_code || ':step_' || pts.step_number::TEXT
                    AND et_desc.field_name = 'description'
                    AND et_desc.language_code = $2
                LEFT JOIN entity_translations et_inst ON
                    et_inst.entity_type = 'procedure_step'
                    AND et_inst.entity_code = pt_ref.template_code || ':step_' || pts.step_number::TEXT
                    AND et_inst.field_name = 'instructions'
                    AND et_inst.language_code = $2
                WHERE pts.template_id = ANY($1)
                ORDER BY pts.template_id, pts.step_number
            """
            step_rows = await conn.fetch(all_steps_query, procedure_ids, language)

            # Group steps by template_id
            steps_by_template: dict = {}
            for step in step_rows:
                tid = step["template_id"]
                if tid not in steps_by_template:
                    steps_by_template[tid] = []
                steps_by_template[tid].append(dict(step))

            # Assign steps to procedures + calculate total time
            for procedure in procedures:
                proc_steps = steps_by_template.get(procedure["id"], [])
                # Remove template_id from each step (internal field)
                for s in proc_steps:
                    s.pop("template_id", None)
                procedure["steps"] = proc_steps
                procedure["total_estimated_minutes"] = sum(
                    s.get("estimated_duration_minutes") or 0 for s in proc_steps
                )

            return procedures

        except asyncpg.PostgresError as e:
            logger.error(f"Error fetching service procedures: {e}")
            return []

    async def get_related_services(
        self,
        conn: asyncpg.Connection,
        service_id: int,
        category_id: int,
        language: str = "es",
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Get related services in the same category"""
        query = """
            SELECT
                fs.id,
                fs.service_code,
                COALESCE(et_name.translation_text, fs.name_es) as name,
                COALESCE(fs.tasa_expedicion, 0) as expedition_price,
                fs.processing_time_days
            FROM fiscal_services fs
            LEFT JOIN entity_translations et_name ON
                et_name.entity_type = 'service'
                AND et_name.entity_code = fs.service_code
                AND et_name.field_name = 'name'
                AND et_name.language_code = $3
            WHERE fs.category_id = $2
              AND fs.id != $1
              AND fs.status = 'active'
            ORDER BY fs.view_count DESC, fs.calculation_count DESC
            LIMIT $4
        """

        try:
            rows = await conn.fetch(query, service_id, category_id, language, limit)
            return [dict(row) for row in rows]
        except asyncpg.PostgresError as e:
            logger.error(f"Error fetching related services: {e}")
            return []

    async def get_parent_service(
        self,
        conn: asyncpg.Connection,
        parent_id: int,
        language: str = "es",
    ) -> Optional[Dict[str, Any]]:
        """Get parent service info"""
        query = """
            SELECT
                fs.id,
                fs.service_code,
                COALESCE(et_name.translation_text, fs.name_es) as name,
                COALESCE(fs.tasa_expedicion, 0) as expedition_price,
                fs.processing_time_days
            FROM fiscal_services fs
            LEFT JOIN entity_translations et_name ON
                et_name.entity_type = 'service'
                AND et_name.entity_code = fs.service_code
                AND et_name.field_name = 'name'
                AND et_name.language_code = $2
            WHERE fs.id = $1
        """

        try:
            row = await conn.fetchrow(query, parent_id, language)
            return dict(row) if row else None
        except asyncpg.PostgresError as e:
            logger.error(f"Error fetching parent service: {e}")
            return None

    async def get_child_services(
        self,
        conn: asyncpg.Connection,
        service_id: int,
        language: str = "es",
    ) -> List[Dict[str, Any]]:
        """Get child/sub-services"""
        query = """
            SELECT
                fs.id,
                fs.service_code,
                COALESCE(et_name.translation_text, fs.name_es) as name,
                COALESCE(fs.tasa_expedicion, 0) as expedition_price,
                fs.processing_time_days
            FROM fiscal_services fs
            LEFT JOIN entity_translations et_name ON
                et_name.entity_type = 'service'
                AND et_name.entity_code = fs.service_code
                AND et_name.field_name = 'name'
                AND et_name.language_code = $2
            WHERE fs.parent_service_id = $1 AND fs.status = 'active'
            ORDER BY fs.name_es
        """

        try:
            rows = await conn.fetch(query, service_id, language)
            return [dict(row) for row in rows]
        except asyncpg.PostgresError as e:
            logger.error(f"Error fetching child services: {e}")
            return []

    async def get_service_keywords(
        self,
        conn: asyncpg.Connection,
        service_id: int,
    ) -> List[Dict[str, Any]]:
        """Get service keywords for SEO"""
        query = """
            SELECT keyword, language_code, weight
            FROM service_keywords
            WHERE fiscal_service_id = $1
            ORDER BY weight DESC, keyword
        """

        try:
            rows = await conn.fetch(query, service_id)
            return [dict(row) for row in rows]
        except asyncpg.PostgresError as e:
            logger.error(f"Error fetching service keywords: {e}")
            return []
