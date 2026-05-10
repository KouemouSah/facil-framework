"""Fiscal Service Repository - Data access for 850 services"""

from typing import Optional, List, Dict, Any
from loguru import logger
import asyncpg

from app.modules.fiscal_services.models import (
    FiscalServiceCreate,
    FiscalServiceUpdate,
    FiscalServiceSearchRequest,
)


class FiscalServiceRepository:
    """Repository for fiscal services catalog"""

    # ========== MINISTRIES ==========
    async def list_ministries(
        self, conn: asyncpg.Connection, language: str = "es"
    ) -> List[Dict[str, Any]]:
        """List all ministries with i18n support"""
        query = """
            SELECT
                m.id, m.ministry_code,
                COALESCE(et_name.translation_text, m.name_es) as name_es,
                COALESCE(et_desc.translation_text, m.description_es) as description_es,
                m.display_order, m.icon, m.color,
                m.website_url, m.contact_email, m.contact_phone,
                m.is_active, m.description_source, m.created_at, m.updated_at
            FROM ministries m
            LEFT JOIN entity_translations et_name ON
                et_name.entity_type = 'ministry'
                AND et_name.entity_code = m.ministry_code
                AND et_name.field_name = 'name'
                AND et_name.language_code = $1
            LEFT JOIN entity_translations et_desc ON
                et_desc.entity_type = 'ministry'
                AND et_desc.entity_code = m.ministry_code
                AND et_desc.field_name = 'description'
                AND et_desc.language_code = $1
            ORDER BY m.display_order, m.ministry_code
        """
        results = await conn.fetch(query, language)
        return [dict(r) for r in results]

    async def get_ministry_by_id(self, conn: asyncpg.Connection, ministry_id: int) -> Optional[Dict[str, Any]]:
        """Get ministry by ID"""
        query = "SELECT * FROM ministries WHERE id = $1"
        result = await conn.fetchrow(query, ministry_id)
        return dict(result) if result else None

    async def get_ministry_by_code(self, conn: asyncpg.Connection, ministry_code: str) -> Optional[Dict[str, Any]]:
        """Get ministry by code"""
        query = "SELECT * FROM ministries WHERE ministry_code = $1"
        result = await conn.fetchrow(query, ministry_code)
        return dict(result) if result else None

    async def create_ministry(self, conn: asyncpg.Connection, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new ministry"""
        query = """
            INSERT INTO ministries (
                ministry_code, name_es, description_es, display_order,
                icon, color, website_url, contact_email, contact_phone, is_active
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            RETURNING *
        """
        result = await conn.fetchrow(
            query,
            data.get("ministry_code"),
            data.get("name_es"),
            data.get("description_es"),
            data.get("display_order", 0),
            data.get("icon"),
            data.get("color"),
            data.get("website_url"),
            data.get("contact_email"),
            data.get("contact_phone"),
            data.get("is_active", True),
        )
        return dict(result)

    async def update_ministry(
        self, conn: asyncpg.Connection, ministry_id: int, data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Update ministry"""
        updates = []
        params = [ministry_id]
        param_idx = 2

        for field, value in data.items():
            if value is not None:
                updates.append(f"{field} = ${param_idx}")
                params.append(value)
                param_idx += 1

        if not updates:
            return await self.get_ministry_by_id(conn, ministry_id)

        updates.append("updated_at = NOW()")
        query = f"UPDATE ministries SET {', '.join(updates)} WHERE id = $1 RETURNING *"
        result = await conn.fetchrow(query, *params)
        return dict(result) if result else None

    async def delete_ministry(self, conn: asyncpg.Connection, ministry_id: int) -> bool:
        """Delete ministry (fails if has sectors)"""
        # Check for dependent sectors
        check_query = "SELECT COUNT(*) FROM sectors WHERE ministry_id = $1"
        count = await conn.fetchval(check_query, ministry_id)

        if count > 0:
            raise ValueError(f"Cannot delete ministry: {count} sectors depend on it")

        result = await conn.execute("DELETE FROM ministries WHERE id = $1", ministry_id)
        return result == "DELETE 1"

    # ========== SECTORS ==========
    async def list_sectors(
        self, conn: asyncpg.Connection, ministry_id: Optional[int] = None, language: str = "es"
    ) -> List[Dict[str, Any]]:
        """List sectors with i18n support, optionally filtered by ministry"""
        base_query = """
            SELECT
                s.id, s.sector_code, s.ministry_id,
                COALESCE(et_name.translation_text, s.name_es) as name_es,
                COALESCE(et_desc.translation_text, s.description_es) as description_es,
                s.display_order, s.icon, s.color,
                s.is_active, s.created_at, s.updated_at
            FROM sectors s
            LEFT JOIN entity_translations et_name ON
                et_name.entity_type = 'sector'
                AND et_name.entity_code = s.sector_code
                AND et_name.field_name = 'name'
                AND et_name.language_code = $1
            LEFT JOIN entity_translations et_desc ON
                et_desc.entity_type = 'sector'
                AND et_desc.entity_code = s.sector_code
                AND et_desc.field_name = 'description'
                AND et_desc.language_code = $1
        """
        if ministry_id:
            query = base_query + " WHERE s.ministry_id = $2 ORDER BY s.display_order, s.sector_code"
            results = await conn.fetch(query, language, ministry_id)
        else:
            query = base_query + " ORDER BY s.display_order, s.sector_code"
            results = await conn.fetch(query, language)
        return [dict(r) for r in results]

    async def get_sector_by_id(self, conn: asyncpg.Connection, sector_id: int) -> Optional[Dict[str, Any]]:
        """Get sector by ID"""
        query = "SELECT * FROM sectors WHERE id = $1"
        result = await conn.fetchrow(query, sector_id)
        return dict(result) if result else None

    async def get_sector_by_code(self, conn: asyncpg.Connection, sector_code: str) -> Optional[Dict[str, Any]]:
        """Get sector by code"""
        query = "SELECT * FROM sectors WHERE sector_code = $1"
        result = await conn.fetchrow(query, sector_code)
        return dict(result) if result else None

    async def create_sector(self, conn: asyncpg.Connection, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new sector"""
        # Verify ministry exists
        ministry = await self.get_ministry_by_id(conn, data.get("ministry_id"))
        if not ministry:
            raise ValueError(f"Ministry with ID {data.get('ministry_id')} not found")

        query = """
            INSERT INTO sectors (
                sector_code, ministry_id, name_es, description_es,
                display_order, icon, color, is_active
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING *
        """
        result = await conn.fetchrow(
            query,
            data.get("sector_code"),
            data.get("ministry_id"),
            data.get("name_es"),
            data.get("description_es"),
            data.get("display_order", 0),
            data.get("icon"),
            data.get("color"),
            data.get("is_active", True),
        )
        return dict(result)

    async def update_sector(
        self, conn: asyncpg.Connection, sector_id: int, data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Update sector"""
        # If ministry_id is being updated, verify it exists
        if "ministry_id" in data and data["ministry_id"] is not None:
            ministry = await self.get_ministry_by_id(conn, data["ministry_id"])
            if not ministry:
                raise ValueError(f"Ministry with ID {data['ministry_id']} not found")

        updates = []
        params = [sector_id]
        param_idx = 2

        for field, value in data.items():
            if value is not None:
                updates.append(f"{field} = ${param_idx}")
                params.append(value)
                param_idx += 1

        if not updates:
            return await self.get_sector_by_id(conn, sector_id)

        updates.append("updated_at = NOW()")
        query = f"UPDATE sectors SET {', '.join(updates)} WHERE id = $1 RETURNING *"
        result = await conn.fetchrow(query, *params)
        return dict(result) if result else None

    async def delete_sector(self, conn: asyncpg.Connection, sector_id: int) -> bool:
        """Delete sector (fails if has categories)"""
        # Check for dependent categories
        check_query = "SELECT COUNT(*) FROM categories WHERE sector_id = $1"
        count = await conn.fetchval(check_query, sector_id)

        if count > 0:
            raise ValueError(f"Cannot delete sector: {count} categories depend on it")

        result = await conn.execute("DELETE FROM sectors WHERE id = $1", sector_id)
        return result == "DELETE 1"

    # ========== CATEGORIES ==========
    async def list_categories(
        self, conn: asyncpg.Connection, sector_id: Optional[int] = None, language: str = "es"
    ) -> List[Dict[str, Any]]:
        """List categories with i18n support, optionally filtered by sector"""
        base_query = """
            SELECT
                c.id, c.category_code, c.sector_id, c.ministry_id, c.service_type,
                COALESCE(et_name.translation_text, c.name_es) as name_es,
                COALESCE(et_desc.translation_text, c.description_es) as description_es,
                c.display_order, c.icon, c.color,
                c.is_active, c.created_at, c.updated_at
            FROM categories c
            LEFT JOIN entity_translations et_name ON
                et_name.entity_type = 'category'
                AND et_name.entity_code = c.category_code
                AND et_name.field_name = 'name'
                AND et_name.language_code = $1
            LEFT JOIN entity_translations et_desc ON
                et_desc.entity_type = 'category'
                AND et_desc.entity_code = c.category_code
                AND et_desc.field_name = 'description'
                AND et_desc.language_code = $1
        """
        if sector_id:
            query = base_query + " WHERE c.sector_id = $2 ORDER BY c.display_order, c.category_code"
            results = await conn.fetch(query, language, sector_id)
        else:
            query = base_query + " ORDER BY c.display_order, c.category_code"
            results = await conn.fetch(query, language)
        return [dict(r) for r in results]

    async def get_category_by_id(self, conn: asyncpg.Connection, category_id: int) -> Optional[Dict[str, Any]]:
        """Get category by ID"""
        query = "SELECT * FROM categories WHERE id = $1"
        result = await conn.fetchrow(query, category_id)
        return dict(result) if result else None

    async def get_category_by_code(self, conn: asyncpg.Connection, category_code: str) -> Optional[Dict[str, Any]]:
        """Get category by code"""
        query = "SELECT * FROM categories WHERE category_code = $1"
        result = await conn.fetchrow(query, category_code)
        return dict(result) if result else None

    async def create_category(self, conn: asyncpg.Connection, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new category"""
        # Verify sector exists if provided
        if data.get("sector_id"):
            sector = await self.get_sector_by_id(conn, data.get("sector_id"))
            if not sector:
                raise ValueError(f"Sector with ID {data.get('sector_id')} not found")

        # Verify ministry exists if provided
        if data.get("ministry_id"):
            ministry = await self.get_ministry_by_id(conn, data.get("ministry_id"))
            if not ministry:
                raise ValueError(f"Ministry with ID {data.get('ministry_id')} not found")

        query = """
            INSERT INTO categories (
                category_code, sector_id, ministry_id, service_type,
                name_es, description_es, display_order, icon, color, is_active
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            RETURNING *
        """
        result = await conn.fetchrow(
            query,
            data.get("category_code"),
            data.get("sector_id"),
            data.get("ministry_id"),
            data.get("service_type"),
            data.get("name_es"),
            data.get("description_es"),
            data.get("display_order", 0),
            data.get("icon"),
            data.get("color"),
            data.get("is_active", True),
        )
        return dict(result)

    async def update_category(
        self, conn: asyncpg.Connection, category_id: int, data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Update category"""
        # Verify sector exists if being updated
        if "sector_id" in data and data["sector_id"] is not None:
            sector = await self.get_sector_by_id(conn, data["sector_id"])
            if not sector:
                raise ValueError(f"Sector with ID {data['sector_id']} not found")

        # Verify ministry exists if being updated
        if "ministry_id" in data and data["ministry_id"] is not None:
            ministry = await self.get_ministry_by_id(conn, data["ministry_id"])
            if not ministry:
                raise ValueError(f"Ministry with ID {data['ministry_id']} not found")

        updates = []
        params = [category_id]
        param_idx = 2

        for field, value in data.items():
            if value is not None:
                updates.append(f"{field} = ${param_idx}")
                params.append(value)
                param_idx += 1

        if not updates:
            return await self.get_category_by_id(conn, category_id)

        updates.append("updated_at = NOW()")
        query = f"UPDATE categories SET {', '.join(updates)} WHERE id = $1 RETURNING *"
        result = await conn.fetchrow(query, *params)
        return dict(result) if result else None

    async def delete_category(self, conn: asyncpg.Connection, category_id: int) -> bool:
        """Delete category (fails if has fiscal services)"""
        # Check for dependent fiscal services
        check_query = "SELECT COUNT(*) FROM fiscal_services WHERE category_id = $1"
        count = await conn.fetchval(check_query, category_id)

        if count > 0:
            raise ValueError(f"Cannot delete category: {count} fiscal services depend on it")

        result = await conn.execute("DELETE FROM categories WHERE id = $1", category_id)
        return result == "DELETE 1"

    # ========== FISCAL SERVICES ==========
    async def create(
        self, conn: asyncpg.Connection, service: FiscalServiceCreate
    ) -> Dict[str, Any]:
        """Create fiscal service - matches database schema exactly"""
        import json
        from datetime import date

        query = """
            INSERT INTO fiscal_services (
                service_code, category_id, name_es, description_es,
                service_type, calculation_method,
                tasa_expedicion, tasa_renovacion,
                base_percentage, percentage_of, unit_rate, unit_type,
                expedition_formula, expedition_unit_measure,
                renewal_formula, renewal_unit_measure,
                calculation_config, rate_tiers,
                tier_group_name, is_tier_component,
                validity_period_months, renewal_frequency_months, grace_period_days,
                late_penalty_percentage, late_penalty_fixed,
                penalty_calculation_rules, eligibility_criteria, exemption_conditions,
                parent_service_id, legal_reference, regulatory_articles,
                tariff_effective_from, tariff_effective_to,
                processing_time_days, priority, complexity_level, status,
                description_visible,
                created_at, updated_at
            )
            VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                $11, $12, $13, $14, $15, $16, $17, $18, $19, $20,
                $21, $22, $23, $24, $25, $26, $27, $28, $29, $30,
                $31, $32, $33, $34, $35, $36, $37, $38,
                NOW(), NOW()
            )
            RETURNING *
        """
        result = await conn.fetchrow(
            query,
            service.service_code,
            service.category_id,
            service.name_es,
            service.description_es,
            service.service_type.value if service.service_type else None,
            service.calculation_method.value if service.calculation_method else None,
            service.tasa_expedicion,
            service.tasa_renovacion,
            service.base_percentage,
            service.percentage_of,
            service.unit_rate,
            service.unit_type,
            service.expedition_formula,
            service.expedition_unit_measure,
            service.renewal_formula,
            service.renewal_unit_measure,
            json.dumps(service.calculation_config) if service.calculation_config else '{}',
            json.dumps(service.rate_tiers) if service.rate_tiers else '[]',
            service.tier_group_name,
            service.is_tier_component,
            service.validity_period_months,
            service.renewal_frequency_months,
            service.grace_period_days,
            service.late_penalty_percentage,
            service.late_penalty_fixed,
            json.dumps(service.penalty_calculation_rules) if service.penalty_calculation_rules else '{}',
            json.dumps(service.eligibility_criteria) if service.eligibility_criteria else '{}',
            json.dumps(service.exemption_conditions) if service.exemption_conditions else '[]',
            service.parent_service_id,
            service.legal_reference,
            service.regulatory_articles,
            service.tariff_effective_from or date.today(),
            service.tariff_effective_to,
            service.processing_time_days,
            service.priority,
            service.complexity_level,
            service.status.value if service.status else 'active',
            service.description_visible if service.description_visible is not None else True,
        )

        service_dict = dict(result)

        return service_dict

    # Full column list for detail views (all columns except embedding and search_vector)
    _DETAIL_COLUMNS = """
        fs.id, fs.service_code, fs.category_id,
        fs.name_es, fs.description_es, fs.description_visible, fs.description_source,
        fs.service_type, fs.calculation_method, fs.status,
        fs.tasa_expedicion, fs.tasa_renovacion,
        fs.base_percentage, fs.percentage_of,
        fs.unit_rate, fs.unit_type,
        fs.expedition_formula, fs.expedition_unit_measure,
        fs.renewal_formula, fs.renewal_unit_measure,
        fs.calculation_config, fs.rate_tiers,
        fs.tier_group_name, fs.is_tier_component,
        fs.validity_period_months, fs.renewal_frequency_months,
        fs.grace_period_days,
        fs.late_penalty_percentage, fs.late_penalty_fixed,
        fs.penalty_calculation_rules, fs.eligibility_criteria, fs.exemption_conditions,
        fs.parent_service_id,
        fs.legal_reference, fs.regulatory_articles,
        fs.tariff_effective_from, fs.tariff_effective_to,
        fs.processing_time_days, fs.priority, fs.complexity_level,
        fs.view_count, fs.calculation_count, fs.payment_count, fs.favorite_count,
        fs.created_at, fs.updated_at
    """

    async def get_by_id(
        self, conn: asyncpg.Connection, service_id: int
    ) -> Optional[Dict[str, Any]]:
        """Get fiscal service by ID with hierarchical data"""
        query = f"""
            SELECT
                {self._DETAIL_COLUMNS},
                c.name_es as category_name,
                s.name_es as sector_name,
                m.name_es as ministry_name
            FROM fiscal_services fs
            JOIN categories c ON fs.category_id = c.id
            LEFT JOIN sectors s ON c.sector_id = s.id
            LEFT JOIN ministries m ON s.ministry_id = m.id
            WHERE fs.id = $1
        """
        result = await conn.fetchrow(query, service_id)
        if not result:
            return None

        service_dict = dict(result)

        # Ensure JSONB/array fields have proper defaults (Pydantic expects dict/list)
        # Handle None, empty strings, and invalid types
        json_dict_fields = ["calculation_config", "penalty_calculation_rules", "eligibility_criteria"]
        json_list_fields = ["rate_tiers", "exemption_conditions", "regulatory_articles"]

        for field in json_dict_fields:
            val = service_dict.get(field)
            if not isinstance(val, dict):
                service_dict[field] = {}

        for field in json_list_fields:
            val = service_dict.get(field)
            if not isinstance(val, (list, tuple)):
                service_dict[field] = []
            elif isinstance(val, tuple):
                # Convert PostgreSQL ARRAY (tuple) to list
                service_dict[field] = list(val)

        # Get keywords
        keywords = await conn.fetch(
            "SELECT keyword FROM service_keywords WHERE fiscal_service_id = $1",
            service_id,
        )
        service_dict["keywords"] = [k["keyword"] for k in keywords]

        # NOTE: fiscal_service_data → MODULE DECLARATIONS (user data, not catalog)

        # Get required documents
        docs = await conn.fetch(
            """SELECT d.document_name_es
               FROM service_document_assignments sda
               JOIN document_templates d ON sda.document_template_id = d.id
               WHERE sda.fiscal_service_id = $1""",
            service_id,
        )
        service_dict["required_documents"] = [d["document_name_es"] for d in docs]

        return service_dict

    async def get_by_code(
        self, conn: asyncpg.Connection, code: str
    ) -> Optional[Dict[str, Any]]:
        """Get fiscal service by service_code"""
        query = f"""
            SELECT {self._DETAIL_COLUMNS},
                   c.name_es as category_name
            FROM fiscal_services fs
            JOIN categories c ON fs.category_id = c.id
            WHERE fs.service_code = $1
        """
        result = await conn.fetchrow(query, code)
        return dict(result) if result else None

    async def list(
        self,
        conn: asyncpg.Connection,
        category_id: Optional[int] = None,
        status: Optional[str] = None,
        ministry_id: Optional[int] = None,
        sector_id: Optional[int] = None,
        search: Optional[str] = None,
        sort_by: str = "service_code",
        sort_order: str = "asc",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[List[Dict[str, Any]], int]:
        """List fiscal services with server-side filters, search, sort, pagination"""
        conditions = []
        params: List[Any] = []
        param_idx = 1

        # Text search — tsvector + ILIKE fallback
        if search:
            conditions.append(
                f"(fs.search_vector @@ plainto_tsquery('spanish', ${param_idx})"
                f" OR fs.name_es ILIKE ${param_idx + 1}"
                f" OR fs.service_code ILIKE ${param_idx + 1})"
            )
            params.append(search)
            escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            params.append(f"%{escaped}%")
            param_idx += 2

        if category_id:
            conditions.append(f"fs.category_id = ${param_idx}")
            params.append(category_id)
            param_idx += 1

        if status is not None:
            conditions.append(f"fs.status = ${param_idx}")
            params.append(status)
            param_idx += 1

        if ministry_id:
            conditions.append(f"m.id = ${param_idx}")
            params.append(ministry_id)
            param_idx += 1

        if sector_id:
            conditions.append(f"s.id = ${param_idx}")
            params.append(sector_id)
            param_idx += 1

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        # Count (need JOINs for ministry/sector filters)
        count_query = f"""
            SELECT COUNT(fs.id)
            FROM fiscal_services fs
            LEFT JOIN categories c ON fs.category_id = c.id
            LEFT JOIN sectors s ON c.sector_id = s.id
            LEFT JOIN ministries m ON s.ministry_id = m.id
            {where_clause}
        """
        total = await conn.fetchval(count_query, *params)

        # Sort — whitelist to prevent injection
        sort_map = {
            "service_code": "fs.service_code",
            "name": "fs.name_es",
            "price": "COALESCE(fs.tasa_expedicion, 0)",
            "status": "fs.status",
            "popular": "fs.calculation_count DESC, fs.view_count DESC",
            "updated": "fs.updated_at",
        }
        order_col = sort_map.get(sort_by, "fs.service_code")
        safe_order = "DESC" if sort_order.upper() == "DESC" else "ASC"
        # 'popular' already includes direction
        order_clause = order_col if sort_by == "popular" else f"{order_col} {safe_order}"

        # Data — explicit columns
        data_query = f"""
            SELECT
                {self._LIST_COLUMNS},
                c.name_es as category_name,
                s.name_es as sector_name,
                m.name_es as ministry_name
            FROM fiscal_services fs
            LEFT JOIN categories c ON fs.category_id = c.id
            LEFT JOIN sectors s ON c.sector_id = s.id
            LEFT JOIN ministries m ON s.ministry_id = m.id
            {where_clause}
            ORDER BY {order_clause}
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        params.extend([limit, offset])
        results = await conn.fetch(data_query, *params)

        services = []
        for r in results:
            service = dict(r)
            service["keywords"] = list(service.get("keywords") or [])
            service["required_documents"] = []
            services.append(service)

        return services, total

    # Explicit column list for list/search queries (no embedding, no search_vector, no JSONB blobs)
    _LIST_COLUMNS = """
        fs.id, fs.service_code, fs.category_id,
        fs.name_es, fs.description_es, fs.description_visible, fs.description_source,
        fs.service_type, fs.calculation_method, fs.status,
        fs.tasa_expedicion, fs.tasa_renovacion,
        fs.processing_time_days, fs.priority, fs.complexity_level,
        fs.validity_period_months, fs.parent_service_id,
        fs.view_count, fs.calculation_count, fs.payment_count, fs.favorite_count,
        fs.created_at, fs.updated_at
    """

    async def search(
        self, conn: asyncpg.Connection, search: FiscalServiceSearchRequest, limit: int = 50, offset: int = 0
    ) -> tuple[List[Dict[str, Any]], int]:
        """Advanced search for fiscal services using tsvector + materialized view"""
        conditions = []
        params = []
        param_idx = 1

        # Text search — use tsvector GIN index (O(log N) instead of seq scan ILIKE)
        if search.search_term:
            conditions.append(
                f"(fs.search_vector @@ plainto_tsquery('spanish', ${param_idx})"
                f" OR EXISTS (SELECT 1 FROM service_keywords sk WHERE sk.fiscal_service_id = fs.id AND sk.keyword ILIKE ${param_idx + 1}))"
            )
            params.append(search.search_term)
            params.append(f"%{search.search_term}%")
            param_idx += 2

        if search.ministry_id:
            conditions.append(f"m.id = ${param_idx}")
            params.append(search.ministry_id)
            param_idx += 1

        if search.sector_id:
            conditions.append(f"s.id = ${param_idx}")
            params.append(search.sector_id)
            param_idx += 1

        if search.category_id:
            conditions.append(f"fs.category_id = ${param_idx}")
            params.append(search.category_id)
            param_idx += 1

        if search.calculation_method:
            conditions.append(f"fs.calculation_method = ${param_idx}")
            params.append(search.calculation_method.value)
            param_idx += 1

        if search.status is not None:
            conditions.append(f"fs.status = ${param_idx}")
            params.append(search.status)
            param_idx += 1

        if search.min_amount is not None:
            conditions.append(f"fs.tasa_expedicion >= ${param_idx}")
            params.append(search.min_amount)
            param_idx += 1

        if search.max_amount is not None:
            conditions.append(f"fs.tasa_expedicion <= ${param_idx}")
            params.append(search.max_amount)
            param_idx += 1

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        # Count
        count_query = f"""
            SELECT COUNT(fs.id)
            FROM fiscal_services fs
            JOIN categories c ON fs.category_id = c.id
            LEFT JOIN sectors s ON c.sector_id = s.id
            LEFT JOIN ministries m ON s.ministry_id = m.id
            {where_clause}
        """
        total = await conn.fetchval(count_query, *params)

        # Data — explicit columns, no embedding/search_vector/JSONB blobs
        data_query = f"""
            SELECT
                {self._LIST_COLUMNS},
                c.name_es as category_name,
                s.name_es as sector_name,
                m.name_es as ministry_name
            FROM fiscal_services fs
            JOIN categories c ON fs.category_id = c.id
            LEFT JOIN sectors s ON c.sector_id = s.id
            LEFT JOIN ministries m ON s.ministry_id = m.id
            {where_clause}
            ORDER BY fs.calculation_count DESC, fs.service_code
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        params.extend([limit, offset])
        results = await conn.fetch(data_query, *params)

        service_ids = [r["id"] for r in results]
        keywords_map = await self._batch_keywords(conn, service_ids)

        services = []
        for r in results:
            service = dict(r)
            service["keywords"] = keywords_map.get(service["id"], [])
            service["required_documents"] = []
            services.append(service)

        return services, total

    async def _batch_keywords(
        self, conn: asyncpg.Connection, service_ids: List[int]
    ) -> Dict[int, List[str]]:
        """Batch fetch keywords for multiple services (no N+1)"""
        keywords_map: Dict[int, List[str]] = {sid: [] for sid in service_ids}
        if service_ids:
            kw_rows = await conn.fetch(
                "SELECT fiscal_service_id, keyword FROM service_keywords WHERE fiscal_service_id = ANY($1)",
                service_ids,
            )
            for kw in kw_rows:
                keywords_map[kw["fiscal_service_id"]].append(kw["keyword"])
        return keywords_map

    async def get_popular(
        self, conn: asyncpg.Connection, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get most used services — uses materialized view when available"""
        query = f"""
            SELECT
                {self._LIST_COLUMNS},
                c.name_es as category_name,
                s.name_es as sector_name,
                m.name_es as ministry_name
            FROM fiscal_services fs
            JOIN categories c ON fs.category_id = c.id
            LEFT JOIN sectors s ON c.sector_id = s.id
            LEFT JOIN ministries m ON s.ministry_id = m.id
            WHERE fs.status = 'active'
            ORDER BY fs.calculation_count DESC, fs.view_count DESC NULLS LAST
            LIMIT $1
        """
        results = await conn.fetch(query, limit)

        service_ids = [r["id"] for r in results]
        keywords_map = await self._batch_keywords(conn, service_ids)

        services = []
        for r in results:
            service = dict(r)
            service["keywords"] = keywords_map.get(service["id"], [])
            service["required_documents"] = []
            services.append(service)

        return services

    async def get_recent(
        self, conn: asyncpg.Connection, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get recently created/updated services"""
        query = f"""
            SELECT
                {self._LIST_COLUMNS},
                c.name_es as category_name,
                s.name_es as sector_name,
                m.name_es as ministry_name
            FROM fiscal_services fs
            JOIN categories c ON fs.category_id = c.id
            LEFT JOIN sectors s ON c.sector_id = s.id
            LEFT JOIN ministries m ON s.ministry_id = m.id
            WHERE fs.status = 'active'
            ORDER BY fs.updated_at DESC NULLS LAST
            LIMIT $1
        """
        results = await conn.fetch(query, limit)

        service_ids = [r["id"] for r in results]
        keywords_map = await self._batch_keywords(conn, service_ids)

        services = []
        for r in results:
            service = dict(r)
            service["keywords"] = keywords_map.get(service["id"], [])
            service["required_documents"] = []
            services.append(service)

        return services

    async def update(
        self, conn: asyncpg.Connection, service_id: int, update_data: FiscalServiceUpdate,
        updated_by: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Update fiscal service - matches database schema"""
        import json

        updates = []
        params = [service_id]
        param_idx = 2

        # Fields that need special handling (enums and JSON)
        enum_fields = {"service_type", "calculation_method", "status"}
        json_fields = {"calculation_config", "rate_tiers", "penalty_calculation_rules",
                       "eligibility_criteria", "exemption_conditions"}
        # Boolean fields: include even when value is False (not None)
        bool_fields = {"description_visible", "is_tier_component"}

        for field, value in update_data.model_dump(exclude_unset=True).items():
            if value is not None or field in bool_fields:
                if value is None and field in bool_fields:
                    continue  # skip if truly None (not set)
                if field in enum_fields:
                    updates.append(f"{field} = ${param_idx}")
                    params.append(value.value if hasattr(value, 'value') else value)
                elif field in json_fields:
                    updates.append(f"{field} = ${param_idx}")
                    params.append(json.dumps(value) if not isinstance(value, str) else value)
                else:
                    updates.append(f"{field} = ${param_idx}")
                    params.append(value)
                param_idx += 1

        if not updates:
            return await self.get_by_id(conn, service_id)

        updates.append("updated_at = NOW()")
        if updated_by:
            updates.append(f"updated_by = ${param_idx}")
            params.append(updated_by)
            param_idx += 1

        query = f"UPDATE fiscal_services SET {', '.join(updates)} WHERE id = $1 RETURNING *"
        result = await conn.fetchrow(query, *params)

        if not result:
            return None

        return await self.get_by_id(conn, service_id)

    async def delete(self, conn: asyncpg.Connection, service_id: int) -> bool:
        """Delete fiscal service"""
        # Delete keywords
        await conn.execute(
            "DELETE FROM service_keywords WHERE fiscal_service_id = $1", service_id
        )
        # NOTE: fiscal_service_data → MODULE DECLARATIONS (not deleted here)
        # Delete document assignments
        await conn.execute(
            "DELETE FROM service_document_assignments WHERE fiscal_service_id = $1",
            service_id,
        )
        # Delete procedure assignments
        await conn.execute(
            "DELETE FROM service_procedure_assignments WHERE fiscal_service_id = $1",
            service_id,
        )
        # Delete service
        result = await conn.execute(
            "DELETE FROM fiscal_services WHERE id = $1", service_id
        )
        return result == "DELETE 1"

    async def increment_usage(
        self, conn: asyncpg.Connection, service_id: int
    ) -> None:
        """Increment usage counter"""
        await conn.execute(
            """UPDATE fiscal_services
               SET calculation_count = calculation_count + 1, updated_at = NOW()
               WHERE id = $1""",
            service_id,
        )

    async def get_statistics(self, conn: asyncpg.Connection) -> Dict[str, Any]:
        """
        Get comprehensive fiscal services statistics

        Migrated from legacy /api/v1/taxes/stats/overview
        Aligned with DATABASE_SCHEMA_REFERENCE.md
        """
        # Total counts by status
        status_counts = await conn.fetch("""
            SELECT status, COUNT(*) as count
            FROM fiscal_services
            GROUP BY status
        """)

        total_services = sum(row["count"] for row in status_counts)
        active_services = next((row["count"] for row in status_counts if row["status"] == "active"), 0)
        inactive_services = total_services - active_services

        # Services by type
        type_counts = await conn.fetch("""
            SELECT service_type, COUNT(*) as count
            FROM fiscal_services
            GROUP BY service_type
            ORDER BY count DESC
        """)

        # Services by category
        category_counts = await conn.fetch("""
            SELECT c.name_es, COUNT(fs.id) as count
            FROM fiscal_services fs
            JOIN categories c ON fs.category_id = c.id
            GROUP BY c.id, c.name_es
            ORDER BY count DESC
        """)

        # Services by ministry
        ministry_counts = await conn.fetch("""
            SELECT m.name_es, COUNT(fs.id) as count
            FROM fiscal_services fs
            JOIN categories c ON fs.category_id = c.id
            JOIN sectors s ON c.sector_id = s.id
            JOIN ministries m ON s.ministry_id = m.id
            GROUP BY m.id, m.name_es
            ORDER BY count DESC
        """)

        # Average processing time
        avg_processing = await conn.fetchval("""
            SELECT COALESCE(AVG(processing_time_days), 1.0)
            FROM fiscal_services
            WHERE processing_time_days IS NOT NULL
        """)

        # Most used services (top 10)
        most_used = await conn.fetch("""
            SELECT id, service_code, name_es, calculation_count, view_count
            FROM fiscal_services
            WHERE status = 'active'
            ORDER BY calculation_count DESC, view_count DESC
            LIMIT 10
        """)

        # Total stats
        totals = await conn.fetchrow("""
            SELECT
                COALESCE(SUM(calculation_count), 0) as total_calculations,
                COALESCE(SUM(view_count), 0) as total_views
            FROM fiscal_services
        """)

        return {
            "total_services": total_services,
            "active_services": active_services,
            "inactive_services": inactive_services,
            "services_by_type": {row["service_type"]: row["count"] for row in type_counts},
            "services_by_category": {row["name_es"]: row["count"] for row in category_counts},
            "services_by_ministry": {row["name_es"]: row["count"] for row in ministry_counts},
            "services_by_status": {row["status"]: row["count"] for row in status_counts},
            "average_processing_time": float(avg_processing),
            "most_used_services": [dict(row) for row in most_used],
            "total_calculations": totals["total_calculations"],
            "total_views": totals["total_views"],
        }

    async def bulk_create(
        self, conn: asyncpg.Connection, services: List[Any], created_by: str
    ) -> Dict[str, Any]:
        """
        Bulk create fiscal services (batch approach — no N+1)

        Fetches all existing codes in one query, then inserts only new ones.

        Args:
            conn: Database connection
            services: List of FiscalServiceCreate models
            created_by: User ID creating the services

        Returns:
            Dict with successful and failed counts
        """
        if not services:
            return {"successful": 0, "failed": 0, "errors": []}

        # 1. Fetch ALL existing codes in one query
        all_codes = [s.service_code for s in services]
        existing_rows = await conn.fetch(
            "SELECT service_code FROM fiscal_services WHERE service_code = ANY($1)",
            all_codes,
        )
        existing_codes = {row["service_code"] for row in existing_rows}

        # 2. Separate existing (skip) from new (insert)
        errors = []
        to_create = []
        for service in services:
            if service.service_code in existing_codes:
                errors.append({
                    "code": service.service_code,
                    "error": "Service code already exists"
                })
            else:
                to_create.append(service)

        # 3. Insert new items individually (create() has complex field mapping)
        successful = 0
        for service in to_create:
            try:
                await self.create(conn, service)
                successful += 1
            except Exception as e:
                errors.append({
                    "code": service.service_code if hasattr(service, 'service_code') else "unknown",
                    "error": str(e)
                })

        return {
            "successful": successful,
            "failed": len(errors),
            "errors": errors
        }

    async def bulk_update_status(
        self,
        conn: asyncpg.Connection,
        service_ids: List[str],
        new_status: Any,
        updated_by: str
    ) -> Dict[str, int]:
        """
        Bulk update service status (single query — no N+1)

        Args:
            conn: Database connection
            service_ids: List of service IDs to update
            new_status: New ServiceStatusEnum value
            updated_by: User ID performing the update

        Returns:
            Dict with updated and failed counts
        """
        if not service_ids:
            return {"updated": 0, "failed": 0}

        # Convert to int list for ANY($1::int[])
        int_ids = [int(sid) for sid in service_ids]

        result = await conn.execute(
            """
            UPDATE fiscal_services
            SET status = $1, updated_at = NOW(), updated_by = $2
            WHERE id = ANY($3::int[])
            """,
            new_status.value,
            updated_by,
            int_ids,
        )

        # result is like "UPDATE N"
        updated_count = int(result.split(" ")[1]) if result else 0
        failed_count = len(int_ids) - updated_count

        return {
            "updated": updated_count,
            "failed": failed_count
        }

    # ========== DOCUMENT ASSIGNMENTS ==========
    async def list_document_assignments(
        self, conn: asyncpg.Connection, service_id: int, language: str = "es"
    ) -> List[Dict[str, Any]]:
        """List document assignments for a service with i18n support"""
        query = """
            SELECT
                sda.id,
                sda.fiscal_service_id,
                sda.document_template_id,
                sda.is_required_expedition,
                sda.is_required_renewal,
                sda.display_order,
                sda.custom_notes,
                sda.assigned_at,
                sda.assigned_by,
                COALESCE(et.translation_text, dt.document_name_es) as document_name,
                fs.name_es as service_name
            FROM service_document_assignments sda
            JOIN document_templates dt ON sda.document_template_id = dt.id
            JOIN fiscal_services fs ON sda.fiscal_service_id = fs.id
            LEFT JOIN entity_translations et ON
                et.entity_type = 'document_template'
                AND et.entity_code = dt.template_code
                AND et.field_name = 'name'
                AND et.language_code = $1
            WHERE sda.fiscal_service_id = $2
            ORDER BY sda.display_order, sda.id
        """
        results = await conn.fetch(query, language, service_id)
        return [dict(r) for r in results]

    async def create_document_assignment(
        self, conn: asyncpg.Connection, data: Dict[str, Any], user_id: int
    ) -> Dict[str, Any]:
        """Create a document assignment"""
        # Verify document template exists
        doc_check = await conn.fetchrow(
            "SELECT id FROM document_templates WHERE id = $1",
            data.get("document_template_id")
        )
        if not doc_check:
            raise ValueError(f"Document template with ID {data.get('document_template_id')} not found")

        query = """
            INSERT INTO service_document_assignments (
                fiscal_service_id, document_template_id,
                is_required_expedition, is_required_renewal,
                display_order, custom_notes, assigned_by
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING *
        """
        result = await conn.fetchrow(
            query,
            data.get("fiscal_service_id"),
            data.get("document_template_id"),
            data.get("is_required_expedition", True),
            data.get("is_required_renewal", False),
            data.get("display_order", 1),
            data.get("custom_notes"),
            user_id,
        )
        return dict(result)

    async def delete_document_assignment(
        self, conn: asyncpg.Connection, service_id: int, assignment_id: int
    ) -> bool:
        """Delete a document assignment"""
        result = await conn.execute(
            "DELETE FROM service_document_assignments WHERE id = $1 AND fiscal_service_id = $2",
            assignment_id, service_id
        )
        return result == "DELETE 1"

    # ========== PROCEDURE ASSIGNMENTS ==========
    async def list_procedure_assignments(
        self, conn: asyncpg.Connection, service_id: int, language: str = "es"
    ) -> List[Dict[str, Any]]:
        """List procedure assignments for a service with i18n support"""
        query = """
            SELECT
                spa.id,
                spa.fiscal_service_id,
                spa.template_id,
                spa.applies_to,
                spa.display_order,
                spa.custom_notes,
                spa.override_steps,
                spa.assigned_at,
                spa.assigned_by,
                COALESCE(et.translation_text, pt.name_es) as procedure_name,
                fs.name_es as service_name
            FROM service_procedure_assignments spa
            JOIN procedure_templates pt ON spa.template_id = pt.id
            JOIN fiscal_services fs ON spa.fiscal_service_id = fs.id
            LEFT JOIN entity_translations et ON
                et.entity_type = 'procedure_template'
                AND et.entity_code = pt.template_code
                AND et.field_name = 'name'
                AND et.language_code = $1
            WHERE spa.fiscal_service_id = $2
            ORDER BY spa.display_order, spa.id
        """
        results = await conn.fetch(query, language, service_id)
        return [dict(r) for r in results]

    async def create_procedure_assignment(
        self, conn: asyncpg.Connection, data: Dict[str, Any], user_id: int
    ) -> Dict[str, Any]:
        """Create a procedure assignment"""
        import json

        # Verify procedure template exists
        proc_check = await conn.fetchrow(
            "SELECT id FROM procedure_templates WHERE id = $1",
            data.get("template_id")
        )
        if not proc_check:
            raise ValueError(f"Procedure template with ID {data.get('template_id')} not found")

        override_steps = data.get("override_steps")
        if override_steps and not isinstance(override_steps, str):
            override_steps = json.dumps(override_steps)

        query = """
            INSERT INTO service_procedure_assignments (
                fiscal_service_id, template_id,
                applies_to, display_order, custom_notes,
                override_steps, assigned_by
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING *
        """
        result = await conn.fetchrow(
            query,
            data.get("fiscal_service_id"),
            data.get("template_id"),
            data.get("applies_to"),
            data.get("display_order", 1),
            data.get("custom_notes"),
            override_steps,
            user_id,
        )
        return dict(result)

    async def delete_procedure_assignment(
        self, conn: asyncpg.Connection, service_id: int, assignment_id: int
    ) -> bool:
        """Delete a procedure assignment"""
        result = await conn.execute(
            "DELETE FROM service_procedure_assignments WHERE id = $1 AND fiscal_service_id = $2",
            assignment_id, service_id
        )
        return result == "DELETE 1"
