"""
Search Repository for Fiscal Services
Optimized SQL queries for the /search-db endpoint with facets
"""

from typing import Dict, Any, List, Optional, Tuple
import asyncpg
from loguru import logger
import time


class SearchRepository:
    """Repository for fiscal services search with facets"""

    async def search_services(
        self,
        conn: asyncpg.Connection,
        q: Optional[str] = None,
        category_id: Optional[int] = None,
        category_code: Optional[str] = None,
        ministry_id: Optional[int] = None,
        service_type: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        min_expedition_price: Optional[float] = None,
        max_expedition_price: Optional[float] = None,
        min_renewal_price: Optional[float] = None,
        max_renewal_price: Optional[float] = None,
        sort_by: str = "relevance",
        sort_order: str = "asc",
        page: int = 1,
        limit: int = 20,
        language: str = "es",
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Search fiscal services with filters and pagination

        Returns:
            Tuple of (results, total_count)
        """
        # Build WHERE conditions
        conditions = ["fs.status = 'active'"]
        params: List[Any] = []
        param_idx = 1

        # Text search — use tsvector GIN index when possible, ILIKE as fallback
        if q:
            # Use search_vector (GIN indexed) for Spanish full-text search
            # Falls back to ILIKE for category names and keywords (not in tsvector)
            conditions.append(f"""(
                fs.search_vector @@ plainto_tsquery('spanish', ${param_idx})
                OR c.name_es ILIKE ${param_idx + 1}
                OR EXISTS (
                    SELECT 1 FROM service_keywords sk
                    WHERE sk.fiscal_service_id = fs.id AND sk.keyword ILIKE ${param_idx + 1}
                )
            )""")
            params.append(q)
            params.append(f"%{q}%")
            param_idx += 2

        # Category filter
        if category_id:
            conditions.append(f"fs.category_id = ${param_idx}")
            params.append(category_id)
            param_idx += 1
        elif category_code:
            conditions.append(f"c.category_code = ${param_idx}")
            params.append(category_code)
            param_idx += 1

        # Ministry filter
        if ministry_id:
            conditions.append(f"m.id = ${param_idx}")
            params.append(ministry_id)
            param_idx += 1

        # Service type filter
        if service_type:
            conditions.append(f"fs.service_type = ${param_idx}")
            params.append(service_type)
            param_idx += 1

        # Price filters
        if min_price is not None:
            conditions.append(f"(fs.tasa_expedicion >= ${param_idx} OR fs.tasa_renovacion >= ${param_idx})")
            params.append(min_price)
            param_idx += 1

        if max_price is not None:
            conditions.append(f"(fs.tasa_expedicion <= ${param_idx} OR fs.tasa_renovacion <= ${param_idx})")
            params.append(max_price)
            param_idx += 1

        if min_expedition_price is not None:
            conditions.append(f"fs.tasa_expedicion >= ${param_idx}")
            params.append(min_expedition_price)
            param_idx += 1

        if max_expedition_price is not None:
            conditions.append(f"fs.tasa_expedicion <= ${param_idx}")
            params.append(max_expedition_price)
            param_idx += 1

        if min_renewal_price is not None:
            conditions.append(f"fs.tasa_renovacion >= ${param_idx}")
            params.append(min_renewal_price)
            param_idx += 1

        if max_renewal_price is not None:
            conditions.append(f"fs.tasa_renovacion <= ${param_idx}")
            params.append(max_renewal_price)
            param_idx += 1

        where_clause = " AND ".join(conditions)

        # Build ORDER BY (column names match CTE base aliases)
        order_map = {
            "relevance": "view_count DESC, calculation_count DESC",
            "name": "name_es",
            "price": "COALESCE(tasa_expedicion, 0)",
            "popular": "calculation_count DESC, view_count DESC",
        }
        order_by = order_map.get(sort_by, order_map["relevance"])
        if sort_by in ["name", "price"]:
            safe_order = "DESC" if sort_order.upper() == "DESC" else "ASC"
            order_by += f" {safe_order}"

        # Single CTE: filter+count in base, translate only paginated rows
        offset = (page - 1) * limit

        data_query = f"""
            WITH base AS (
                SELECT DISTINCT fs.id, fs.service_code, fs.name_es, fs.description_es,
                       COALESCE(fs.description_visible, true) AS description_visible,
                       fs.service_type, fs.tasa_expedicion, fs.tasa_renovacion,
                       fs.processing_time_days, fs.status, fs.view_count, fs.calculation_count,
                       c.category_code, c.name_es AS cat_name,
                       s.sector_code, s.name_es AS sec_name,
                       m.ministry_code, m.name_es AS min_name,
                       COUNT(*) OVER() AS total_count
                FROM fiscal_services fs
                JOIN categories c ON fs.category_id = c.id
                LEFT JOIN sectors s ON c.sector_id = s.id
                LEFT JOIN ministries m ON s.ministry_id = m.id
                WHERE {where_clause}
            ),
            page AS (
                SELECT * FROM base
                ORDER BY {order_by}
                LIMIT ${param_idx + 1} OFFSET ${param_idx + 2}
            )
            SELECT
                p.id, p.total_count,
                COALESCE(et_name.translation_text, p.name_es) as name,
                CASE WHEN p.description_visible
                     THEN COALESCE(et_desc.translation_text, p.description_es)
                     ELSE NULL
                END as description,
                COALESCE(et_cat.translation_text, p.cat_name) as category_name,
                COALESCE(et_min.translation_text, p.min_name) as ministry_name,
                COALESCE(et_sec.translation_text, p.sec_name) as sector_name,
                p.service_type,
                COALESCE(p.tasa_expedicion, 0) as expedition_price,
                COALESCE(p.tasa_renovacion, 0) as renewal_price,
                COALESCE(p.processing_time_days, 1) as processing_time_days,
                p.status
            FROM page p
            LEFT JOIN entity_translations et_name ON
                et_name.entity_type = 'service' AND et_name.entity_code = p.service_code
                AND et_name.field_name = 'name' AND et_name.language_code = ${param_idx}
            LEFT JOIN entity_translations et_desc ON
                et_desc.entity_type = 'service' AND et_desc.entity_code = p.service_code
                AND et_desc.field_name = 'description' AND et_desc.language_code = ${param_idx}
            LEFT JOIN entity_translations et_cat ON
                et_cat.entity_type = 'category' AND et_cat.entity_code = p.category_code
                AND et_cat.field_name = 'name' AND et_cat.language_code = ${param_idx}
            LEFT JOIN entity_translations et_min ON
                et_min.entity_type = 'ministry' AND et_min.entity_code = p.ministry_code
                AND et_min.field_name = 'name' AND et_min.language_code = ${param_idx}
            LEFT JOIN entity_translations et_sec ON
                et_sec.entity_type = 'sector' AND et_sec.entity_code = p.sector_code
                AND et_sec.field_name = 'name' AND et_sec.language_code = ${param_idx}
            ORDER BY {order_by}
        """
        params.extend([language, limit, offset])

        try:
            rows = await conn.fetch(data_query, *params)
            total = rows[0]['total_count'] if rows else 0
            results = [dict(row) for row in rows]
            for r in results:
                r.pop('total_count', None)
            return results, total
        except asyncpg.PostgresError as e:
            logger.error(f"Search query error: {e}")
            raise

    async def get_facets(
        self,
        conn: asyncpg.Connection,
        language: str = "es",
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get facets for filtering (categories, ministries, service types, price ranges)
        """
        facets = {
            "categories": [],
            "ministries": [],
            "service_types": [],
            "price_ranges": [],
        }

        try:
            # Categories facet
            cat_query = """
                SELECT
                    c.id,
                    c.category_code as code,
                    COALESCE(et.translation_text, c.name_es) as name,
                    COUNT(fs.id) FILTER (WHERE fs.status = 'active') as count
                FROM categories c
                LEFT JOIN fiscal_services fs ON fs.category_id = c.id
                LEFT JOIN entity_translations et ON
                    et.entity_type = 'category'
                    AND et.entity_code = c.category_code
                    AND et.field_name = 'name'
                    AND et.language_code = $1
                WHERE c.is_active = true
                GROUP BY c.id, c.category_code, c.name_es, et.translation_text
                HAVING COUNT(fs.id) FILTER (WHERE fs.status = 'active') > 0
                ORDER BY count DESC
                LIMIT 20
            """
            cat_rows = await conn.fetch(cat_query, language)
            facets["categories"] = [dict(row) for row in cat_rows]

            # Ministries facet
            min_query = """
                SELECT
                    m.id,
                    COALESCE(et.translation_text, m.name_es) as name,
                    COUNT(DISTINCT fs.id) FILTER (WHERE fs.status = 'active') as count
                FROM ministries m
                JOIN sectors s ON s.ministry_id = m.id
                JOIN categories c ON c.sector_id = s.id
                LEFT JOIN fiscal_services fs ON fs.category_id = c.id
                LEFT JOIN entity_translations et ON
                    et.entity_type = 'ministry'
                    AND et.entity_code = m.ministry_code
                    AND et.field_name = 'name'
                    AND et.language_code = $1
                WHERE m.is_active = true
                GROUP BY m.id, m.name_es, et.translation_text
                HAVING COUNT(DISTINCT fs.id) FILTER (WHERE fs.status = 'active') > 0
                ORDER BY count DESC
            """
            min_rows = await conn.fetch(min_query, language)
            facets["ministries"] = [dict(row) for row in min_rows]

            # Service types facet
            type_query = """
                SELECT
                    service_type as type,
                    COUNT(*) as count
                FROM fiscal_services
                WHERE status = 'active' AND service_type IS NOT NULL
                GROUP BY service_type
                ORDER BY count DESC
            """
            type_rows = await conn.fetch(type_query)
            facets["service_types"] = [dict(row) for row in type_rows]

            # Price ranges facet
            price_query = """
                SELECT
                    CASE
                        WHEN COALESCE(tasa_expedicion, 0) = 0 AND COALESCE(tasa_renovacion, 0) = 0 THEN 'free'
                        WHEN COALESCE(tasa_expedicion, 0) < 50000 THEN 'low'
                        WHEN COALESCE(tasa_expedicion, 0) < 200000 THEN 'medium'
                        WHEN COALESCE(tasa_expedicion, 0) < 500000 THEN 'high'
                        ELSE 'very_high'
                    END as range,
                    COUNT(*) as count
                FROM fiscal_services
                WHERE status = 'active'
                GROUP BY range
                ORDER BY
                    CASE range
                        WHEN 'free' THEN 1
                        WHEN 'low' THEN 2
                        WHEN 'medium' THEN 3
                        WHEN 'high' THEN 4
                        WHEN 'very_high' THEN 5
                    END
            """
            price_rows = await conn.fetch(price_query)
            facets["price_ranges"] = [dict(row) for row in price_rows]

        except asyncpg.PostgresError as e:
            logger.error(f"Facets query error: {e}")

        return facets

    async def get_suggestions(
        self,
        conn: asyncpg.Connection,
        q: Optional[str] = None,
        language: str = "es",
        limit: int = 5,
    ) -> List[str]:
        """Get search suggestions based on popular services and keywords"""
        suggestions = []

        try:
            if q:
                # Get matching keywords
                kw_query = """
                    SELECT DISTINCT keyword
                    FROM service_keywords
                    WHERE keyword ILIKE $1
                    LIMIT $2
                """
                kw_rows = await conn.fetch(kw_query, f"%{q}%", limit)
                suggestions.extend([row["keyword"] for row in kw_rows])
            else:
                # Get popular service names
                pop_query = """
                    SELECT DISTINCT COALESCE(et.translation_text, fs.name_es) as name
                    FROM fiscal_services fs
                    LEFT JOIN entity_translations et ON
                        et.entity_type = 'service'
                        AND et.entity_code = fs.service_code
                        AND et.field_name = 'name'
                        AND et.language_code = $1
                    WHERE fs.status = 'active'
                    ORDER BY fs.calculation_count DESC
                    LIMIT $2
                """
                pop_rows = await conn.fetch(pop_query, language, limit)
                suggestions.extend([row["name"] for row in pop_rows if row["name"]])

        except asyncpg.PostgresError as e:
            logger.error(f"Suggestions query error: {e}")

        return suggestions[:limit]
