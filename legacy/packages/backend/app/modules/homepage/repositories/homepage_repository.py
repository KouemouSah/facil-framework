"""
Homepage Repository - Data Access Layer
Optimized SQL queries for homepage statistics and category directory
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import asyncpg
from loguru import logger


class HomepageRepository:
    """
    Repository for homepage data with optimized queries

    Uses single optimized queries instead of multiple round-trips
    """

    def __init__(self, db: asyncpg.Connection):
        self.db = db

    async def get_stats(self) -> Dict[str, Any]:
        """
        Get homepage statistics with a SINGLE optimized query

        Instead of 4 separate queries, use CTEs and window functions
        Performance: ~15ms vs ~80ms with 4 queries

        Returns:
            Dict with total_services, total_ministries, total_categories, total_sectors
        """
        query = """
            WITH active_services AS (
                SELECT
                    COUNT(*) as total_services,
                    COUNT(DISTINCT category_id) FILTER (WHERE category_id IS NOT NULL) as categories_with_services
                FROM fiscal_services
                WHERE status = 'active'::service_status_enum
            ),
            active_categories AS (
                SELECT COUNT(*) as total_categories
                FROM categories
                WHERE is_active = true
            ),
            active_ministries AS (
                SELECT COUNT(*) as total_ministries
                FROM ministries
                WHERE is_active = true
            ),
            active_sectors AS (
                SELECT COUNT(*) as total_sectors
                FROM sectors
                WHERE is_active = true
            )
            SELECT
                COALESCE(s.total_services, 0)::INTEGER as total_services,
                COALESCE(m.total_ministries, 0)::INTEGER as total_ministries,
                COALESCE(c.total_categories, 0)::INTEGER as total_categories,
                COALESCE(sec.total_sectors, 0)::INTEGER as total_sectors
            FROM active_services s
            CROSS JOIN active_categories c
            CROSS JOIN active_ministries m
            CROSS JOIN active_sectors sec;
        """

        try:
            result = await self.db.fetchrow(query)

            if not result:
                logger.warning("Stats query returned no results")
                return {
                    "total_services": 0,
                    "total_ministries": 0,
                    "total_categories": 0,
                    "total_sectors": 0
                }

            return dict(result)

        except asyncpg.PostgresError as e:
            logger.error(f"Database error in get_stats: {e}")
            raise

    async def get_category_directory(self, language: str = "es") -> List[Dict[str, Any]]:
        """
        Get category directory with service counts and multilingual support

        Uses entity_translations table for proper i18n support
        Optimized with single query using JOINs and aggregations

        Args:
            language: Language code (es, fr, en)

        Returns:
            List of categories with service counts, sorted by count DESC
        """
        query = """
            SELECT
                c.id,
                c.category_code,

                -- Name with translation fallback (translation -> es -> code)
                COALESCE(
                    et_name.translation_text,
                    c.name_es,
                    c.category_code
                ) as name,

                -- Description with translation fallback
                COALESCE(
                    et_desc.translation_text,
                    c.description_es
                ) as description,

                c.icon,
                c.color,
                c.ministry_id,
                c.sector_id,

                -- Ministry name with translation
                COALESCE(
                    et_ministry.translation_text,
                    m.name_es
                ) as ministry_name,

                -- Sector name with translation
                COALESCE(
                    et_sector.translation_text,
                    s.name_es
                ) as sector_name,

                -- Count active services
                COUNT(fs.id) FILTER (WHERE fs.status = 'active'::service_status_enum)::INTEGER as service_count

            FROM categories c

            -- Join ministries and sectors
            LEFT JOIN ministries m ON c.ministry_id = m.id
            LEFT JOIN sectors s ON c.sector_id = s.id

            -- Join fiscal services for counting
            LEFT JOIN fiscal_services fs ON fs.category_id = c.id

            -- Join entity_translations for category name
            LEFT JOIN entity_translations et_name ON
                et_name.entity_type = 'category'
                AND et_name.entity_code = c.category_code
                AND et_name.field_name = 'name'
                AND et_name.language_code = $1

            -- Join entity_translations for category description
            LEFT JOIN entity_translations et_desc ON
                et_desc.entity_type = 'category'
                AND et_desc.entity_code = c.category_code
                AND et_desc.field_name = 'description'
                AND et_desc.language_code = $1

            -- Join entity_translations for ministry name
            LEFT JOIN entity_translations et_ministry ON
                et_ministry.entity_type = 'ministry'
                AND et_ministry.entity_code = m.ministry_code
                AND et_ministry.field_name = 'name'
                AND et_ministry.language_code = $1

            -- Join entity_translations for sector name
            LEFT JOIN entity_translations et_sector ON
                et_sector.entity_type = 'sector'
                AND et_sector.entity_code = s.sector_code
                AND et_sector.field_name = 'name'
                AND et_sector.language_code = $1

            WHERE c.is_active = true

            GROUP BY
                c.id, c.category_code, c.name_es, c.description_es,
                c.icon, c.color, c.ministry_id, c.sector_id,
                m.name_es, s.name_es,
                et_name.translation_text, et_desc.translation_text,
                et_ministry.translation_text, et_sector.translation_text

            -- Order by service count DESC, then alphabetically
            ORDER BY service_count DESC, name ASC;
        """

        try:
            rows = await self.db.fetch(query, language)
            return [dict(row) for row in rows]

        except asyncpg.PostgresError as e:
            logger.error(f"Database error in get_category_directory: {e}")
            raise

    async def get_services_by_type(
        self,
        service_type: str,
        language: str = "es",
        letter: Optional[str] = None,
        limit: int = 300
    ) -> Dict[str, Any]:
        """
        Get services filtered by type and optionally by first letter

        Args:
            service_type: Service type enum value (e.g., 'document_processing')
            language: Language code (es, fr, en)
            letter: Optional first letter filter (A-Z)
            limit: Maximum number of services to return

        Returns:
            Dict with services list, total count, and has_more flag
        """
        # Build the query dynamically based on letter filter
        # Note: language param kept for API compatibility but not used in query
        # (fiscal_services has no translations in entity_translations table)
        letter_condition = ""
        params = [service_type]  # $1 = service_type

        if letter:
            letter_condition = "AND UPPER(SUBSTRING(fs.name_es, 1, 1)) = $2"
            params.append(letter.upper())  # $2 = letter
            limit_param = "$3"
        else:
            limit_param = "$2"

        params.append(limit + 1)  # Get one extra to check if there are more

        # Note: fiscal_services doesn't have translations in entity_translations
        # (translatable_entity_type enum only has: ministry, sector, category)
        # So we use name_es directly as the primary name
        query = f"""
            SELECT
                fs.id,
                fs.service_code,
                fs.name_es,
                fs.tasa_expedicion,

                -- Use name_es as the display name (no translations available for fiscal_services)
                fs.name_es as name,

                -- Count total for this type/letter combination
                COUNT(*) OVER() as total_count

            FROM fiscal_services fs

            WHERE fs.service_type = $1::service_type_enum
                AND fs.status = 'active'::service_status_enum
                {letter_condition}

            ORDER BY fs.name_es ASC
            LIMIT {limit_param};
        """

        try:
            rows = await self.db.fetch(query, *params)

            # Determine if there are more results
            has_more = len(rows) > limit
            services = rows[:limit]  # Take only the requested limit

            # Get total count (same for all rows due to window function)
            total = rows[0]['total_count'] if rows else 0

            # Build result
            result = {
                "services": [
                    {
                        "id": row['id'],
                        "service_code": row['service_code'],
                        "name_es": row['name_es'],
                        "name_fr": row['name'] if language == 'fr' else None,
                        "name_en": row['name'] if language == 'en' else None,
                        "tasa_expedicion": row['tasa_expedicion']
                    }
                    for row in services
                ],
                "total": total if not has_more else total - 1,  # Subtract the extra one we fetched
                "has_more": has_more
            }

            return result

        except asyncpg.PostgresError as e:
            logger.error(f"Database error in get_services_by_type: {e}")
            raise

    async def get_ministry_directory(self, language: str = "es") -> List[Dict[str, Any]]:
        """
        Get ministry directory with service, sector, and category counts

        Args:
            language: Language code (es, fr, en)

        Returns:
            List of ministries with counts, sorted by service_count DESC
        """
        # Single GROUP BY replaces 3 correlated subqueries per ministry (was: 15 ministries × 3 = 45 subqueries)
        query = """
            WITH ministry_stats AS (
                SELECT
                    s.ministry_id,
                    COUNT(DISTINCT s.id) FILTER (WHERE s.is_active = true) AS sector_count,
                    COUNT(DISTINCT c.id) FILTER (WHERE c.is_active = true) AS category_count,
                    COUNT(DISTINCT fs.id) FILTER (WHERE fs.status = 'active'::service_status_enum) AS service_count
                FROM sectors s
                LEFT JOIN categories c ON c.sector_id = s.id
                LEFT JOIN fiscal_services fs ON fs.category_id = c.id
                GROUP BY s.ministry_id
            )
            SELECT
                m.id, m.ministry_code,
                COALESCE(et_name.translation_text, m.name_es) as name,
                COALESCE(et_desc.translation_text, m.description_es) as description,
                m.icon, m.color, m.is_active,
                COALESCE(ms.sector_count, 0)::INTEGER as sector_count,
                COALESCE(ms.category_count, 0)::INTEGER as category_count,
                COALESCE(ms.service_count, 0)::INTEGER as service_count
            FROM ministries m
            LEFT JOIN ministry_stats ms ON ms.ministry_id = m.id
            LEFT JOIN entity_translations et_name ON
                et_name.entity_type = 'ministry' AND et_name.entity_code = m.ministry_code
                AND et_name.field_name = 'name' AND et_name.language_code = $1
            LEFT JOIN entity_translations et_desc ON
                et_desc.entity_type = 'ministry' AND et_desc.entity_code = m.ministry_code
                AND et_desc.field_name = 'description' AND et_desc.language_code = $1
            WHERE m.is_active = true
            ORDER BY service_count DESC, name ASC
        """

        try:
            rows = await self.db.fetch(query, language)
            return [dict(row) for row in rows]

        except asyncpg.PostgresError as e:
            logger.error(f"Database error in get_ministry_directory: {e}")
            raise

    async def get_ministry_details(
        self,
        ministry_id: int,
        language: str = "es",
        page: int = 1,
        limit: int = 12
    ) -> Optional[Dict[str, Any]]:
        """
        Get complete ministry details with paginated services

        Args:
            ministry_id: Ministry ID
            language: Language code (es, fr, en)
            page: Page number (1-based)
            limit: Services per page

        Returns:
            Ministry details with services or None if not found
        """
        # Single CTE for counts instead of 3 correlated subqueries
        ministry_query = """
            WITH ministry_stats AS (
                SELECT
                    s.ministry_id,
                    COUNT(DISTINCT s.id) FILTER (WHERE s.is_active = true) AS sector_count,
                    COUNT(DISTINCT c.id) FILTER (WHERE c.is_active = true) AS category_count,
                    COUNT(DISTINCT fs.id) FILTER (WHERE fs.status = 'active'::service_status_enum) AS service_count
                FROM sectors s
                LEFT JOIN categories c ON c.sector_id = s.id
                LEFT JOIN fiscal_services fs ON fs.category_id = c.id
                WHERE s.ministry_id = $1
                GROUP BY s.ministry_id
            )
            SELECT
                m.id, m.ministry_code,
                COALESCE(et_name.translation_text, m.name_es) as name,
                COALESCE(et_desc.translation_text, m.description_es) as description,
                m.icon, m.color, m.is_active,
                COALESCE(ms.sector_count, 0)::INTEGER as sector_count,
                COALESCE(ms.category_count, 0)::INTEGER as category_count,
                COALESCE(ms.service_count, 0)::INTEGER as service_count
            FROM ministries m
            LEFT JOIN ministry_stats ms ON ms.ministry_id = m.id
            LEFT JOIN entity_translations et_name ON
                et_name.entity_type = 'ministry' AND et_name.entity_code = m.ministry_code
                AND et_name.field_name = 'name' AND et_name.language_code = $2
            LEFT JOIN entity_translations et_desc ON
                et_desc.entity_type = 'ministry' AND et_desc.entity_code = m.ministry_code
                AND et_desc.field_name = 'description' AND et_desc.language_code = $2
            WHERE m.id = $1
        """

        try:
            ministry_row = await self.db.fetchrow(ministry_query, ministry_id, language)

            if not ministry_row:
                return None

            ministry = dict(ministry_row)

            # Calculate pagination
            offset = (page - 1) * limit
            total_services = ministry['service_count']
            total_pages = max(1, (total_services + limit - 1) // limit)

            # Get services with pagination
            services_query = """
                SELECT
                    fs.id,
                    fs.service_code,

                    -- Service name with translation fallback
                    COALESCE(
                        et_name.translation_text,
                        fs.name_es
                    ) as name,

                    -- Service description with translation fallback
                    COALESCE(
                        et_desc.translation_text,
                        fs.description_es
                    ) as description,

                    COALESCE(fs.tasa_expedicion, 0) as expedition_price,
                    COALESCE(fs.tasa_renovacion, 0) as renewal_price,
                    fs.service_type,

                    -- Category name
                    COALESCE(
                        et_cat.translation_text,
                        c.name_es
                    ) as category_name,

                    -- Sector name
                    COALESCE(
                        et_sec.translation_text,
                        sec.name_es
                    ) as sector_name

                FROM fiscal_services fs
                JOIN categories c ON fs.category_id = c.id
                JOIN sectors sec ON c.sector_id = sec.id

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

                -- Category translation
                LEFT JOIN entity_translations et_cat ON
                    et_cat.entity_type = 'category'
                    AND et_cat.entity_code = c.category_code
                    AND et_cat.field_name = 'name'
                    AND et_cat.language_code = $2

                -- Sector translation
                LEFT JOIN entity_translations et_sec ON
                    et_sec.entity_type = 'sector'
                    AND et_sec.entity_code = sec.sector_code
                    AND et_sec.field_name = 'name'
                    AND et_sec.language_code = $2

                WHERE sec.ministry_id = $1
                    AND fs.status = 'active'::service_status_enum

                ORDER BY fs.name_es ASC
                LIMIT $3 OFFSET $4;
            """

            service_rows = await self.db.fetch(
                services_query, ministry_id, language, limit, offset
            )

            ministry['services'] = [dict(row) for row in service_rows]
            ministry['total_pages'] = total_pages
            ministry['current_page'] = page

            return ministry

        except asyncpg.PostgresError as e:
            logger.error(f"Database error in get_ministry_details: {e}")
            raise

    async def search_services(
        self,
        q: Optional[str] = None,
        category_id: Optional[int] = None,
        category_code: Optional[str] = None,
        ministry_id: Optional[int] = None,
        service_type: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        calculation_methods: Optional[List[str]] = None,
        sort_by: str = "relevance",
        sort_order: str = "asc",
        page: int = 1,
        limit: int = 20,
        language: str = "es"
    ) -> Dict[str, Any]:
        """
        Search fiscal services with filters and pagination

        Args:
            q: Search query (searches in name, description)
            category_id: Filter by category ID
            category_code: Filter by category code
            ministry_id: Filter by ministry ID
            service_type: Filter by service type
            min_price: Minimum expedition price
            max_price: Maximum expedition price
            calculation_methods: Filter by calculation methods (e.g., ['percentage_based', 'formula_based'])
            sort_by: Sort field (relevance, name, price)
            sort_order: Sort order (asc, desc)
            page: Page number (1-based)
            limit: Results per page
            language: Language code for translations

        Returns:
            Dict with results, total_results, total_pages, facets
        """
        # Build WHERE conditions (uses mv_services_translated + tsvector JOIN for text search)
        conditions = ["true"]  # mv already filtered to status='active'
        params = []
        param_idx = 1
        use_fts = False  # Full-text search JOIN flag

        # Search query — tsvector GIN index (2-10ms) + ILIKE fallback for translations/categories
        if q and q.strip():
            use_fts = True
            search_term = f"%{q.strip()}%"
            conditions.append(f"""(
                fs.search_vector @@ plainto_tsquery('spanish', ${param_idx})
                OR mv.category_name_es ILIKE ${param_idx + 1}
                OR mv.name_fr ILIKE ${param_idx + 1}
                OR mv.name_en ILIKE ${param_idx + 1}
                OR EXISTS (
                    SELECT 1 FROM service_keywords sk
                    WHERE sk.fiscal_service_id = mv.id
                    AND sk.keyword ILIKE ${param_idx + 1}
                )
            )""")
            params.append(q.strip())      # $1 for plainto_tsquery (raw text, not %wrapped%)
            params.append(search_term)     # $2 for ILIKE fallback
            param_idx += 2

        # Category filter
        if category_id:
            conditions.append(f"mv.category_id = ${param_idx}")
            params.append(category_id)
            param_idx += 1
        elif category_code:
            conditions.append(f"mv.category_code = ${param_idx}")
            params.append(category_code)
            param_idx += 1

        # Ministry filter
        if ministry_id:
            conditions.append(f"mv.ministry_id = ${param_idx}")
            params.append(ministry_id)
            param_idx += 1

        # Service type filter
        if service_type:
            conditions.append(f"mv.service_type = ${param_idx}::service_type_enum")
            params.append(service_type)
            param_idx += 1

        # Price filters
        if min_price is not None:
            conditions.append(f"COALESCE(mv.tasa_expedicion, 0) >= ${param_idx}")
            params.append(min_price)
            param_idx += 1

        if max_price is not None:
            conditions.append(f"COALESCE(mv.tasa_expedicion, 0) <= ${param_idx}")
            params.append(max_price)
            param_idx += 1

        # Calculation method filter
        if calculation_methods and len(calculation_methods) > 0:
            placeholders = ", ".join([f"${param_idx + i}::calculation_method_enum" for i in range(len(calculation_methods))])
            conditions.append(f"mv.calculation_method IN ({placeholders})")
            for method in calculation_methods:
                params.append(method)
                param_idx += 1

        where_clause = " AND ".join(conditions)

        # Build ORDER BY — use ts_rank for relevance when FTS is active
        if sort_by == "relevance" and use_fts:
            order_field = "search_rank DESC, mv.view_count DESC, mv.calculation_count"
            order_dir = "DESC"
        else:
            order_mapping = {
                "name": "name_es",
                "price": "COALESCE(tasa_expedicion, 0)",
                "relevance": "mv.view_count DESC, mv.calculation_count",
            }
            order_field = order_mapping.get(sort_by, "mv.id")
            order_dir = "DESC" if sort_order == "desc" else "ASC"

        # Single query on materialized view — 0 JOINs, all translations pre-computed
        offset = (page - 1) * limit

        # Language column mapping for materialized view
        lang_suffix = {"fr": "fr", "en": "en"}.get(language, "")
        name_col = f"COALESCE(mv.name_{lang_suffix}, mv.name_es)" if lang_suffix else "mv.name_es"
        desc_col = f"COALESCE(mv.description_{lang_suffix}, mv.description_es)" if lang_suffix else "mv.description_es"
        cat_col = f"COALESCE(mv.category_name_{lang_suffix}, mv.category_name_es)" if lang_suffix else "mv.category_name_es"
        min_col = f"COALESCE(mv.ministry_name_{lang_suffix}, mv.ministry_name_es)" if lang_suffix else "mv.ministry_name_es"
        sec_col = f"COALESCE(mv.sector_name_{lang_suffix}, mv.sector_name_es)" if lang_suffix else "mv.sector_name_es"

        # Build FTS JOIN + rank column when text search is active
        fts_join = "JOIN fiscal_services fs ON fs.id = mv.id" if use_fts else ""
        rank_col = f", ts_rank(fs.search_vector, plainto_tsquery('spanish', $1)) AS search_rank" if use_fts else ""

        search_query = f"""
            SELECT
                mv.id,
                COUNT(*) OVER() AS total_count,
                {name_col} as name,
                {desc_col} as description,
                {cat_col} as category_name,
                {min_col} as ministry_name,
                {sec_col} as sector_name,
                mv.service_type::TEXT as service_type,
                COALESCE(mv.tasa_expedicion, 0)::FLOAT as expedition_price,
                COALESCE(mv.tasa_renovacion, 0)::FLOAT as renewal_price,
                COALESCE(mv.processing_time_days, 30) as processing_time_days,
                mv.status::TEXT as status,
                COALESCE(mv.calculation_method::TEXT, 'fixed_expedition') as calculation_method
                {rank_col}
            FROM mv_services_translated mv
            {fts_join}
            WHERE {where_clause}
            ORDER BY {order_field} {order_dir}
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """

        params.append(limit)
        params.append(offset)

        try:
            rows = await self.db.fetch(search_query, *params)
            results = [dict(row) for row in rows]
            total_results = rows[0]['total_count'] if rows else 0
            # Remove internal columns from each result
            for r in results:
                r.pop('total_count', None)
                r.pop('search_rank', None)
            total_pages = max(1, (total_results + limit - 1) // limit)

            return {
                "results": results,
                "total_results": total_results,
                "total_pages": total_pages,
                "page": page,
                "limit": limit
            }

        except asyncpg.PostgresError as e:
            logger.error(f"Database error in search_services: {e}")
            raise

    async def get_search_facets(
        self,
        language: str = "es",
        ministry_id: Optional[int] = None,
        category_code: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get facets for search filters with CASCADE FILTERING

        Cascade logic:
        - Ministries: Always return ALL active ministries (root level)
        - Categories: If ministry_id provided, filter to only that ministry's categories
        - Service Types: If category_code provided, filter to only that category's service types

        Args:
            language: Language code for translations
            ministry_id: Filter categories to this ministry only
            category_code: Filter service_types to this category only

        Returns:
            Filtered facets for cascade dropdowns
        """
        # MINISTRIES: Always return ALL (root level, no filter)
        ministries_query = """
            SELECT
                m.id,
                m.ministry_code as code,
                COALESCE(et.translation_text, m.name_es) as name,
                COUNT(fs.id) as count
            FROM ministries m
            JOIN sectors s ON s.ministry_id = m.id
            JOIN categories c ON c.sector_id = s.id
            JOIN fiscal_services fs ON fs.category_id = c.id AND fs.status = 'active'::service_status_enum
            LEFT JOIN entity_translations et ON
                et.entity_type = 'ministry'
                AND et.entity_code = m.ministry_code
                AND et.field_name = 'name'
                AND et.language_code = $1
            WHERE m.is_active = true
            GROUP BY m.id, m.ministry_code, m.name_es, et.translation_text
            ORDER BY count DESC
        """

        # CATEGORIES: Filter by ministry_id if provided
        if ministry_id:
            categories_query = """
                SELECT
                    c.id,
                    c.category_code as code,
                    COALESCE(et.translation_text, c.name_es) as name,
                    COUNT(fs.id) FILTER (WHERE fs.status = 'active'::service_status_enum) as count
                FROM categories c
                JOIN sectors s ON c.sector_id = s.id
                LEFT JOIN fiscal_services fs ON fs.category_id = c.id
                LEFT JOIN entity_translations et ON
                    et.entity_type = 'category'
                    AND et.entity_code = c.category_code
                    AND et.field_name = 'name'
                    AND et.language_code = $1
                WHERE c.is_active = true
                    AND s.ministry_id = $2
                GROUP BY c.id, c.category_code, c.name_es, et.translation_text
                HAVING COUNT(fs.id) FILTER (WHERE fs.status = 'active'::service_status_enum) > 0
                ORDER BY count DESC
            """
        else:
            categories_query = """
                SELECT
                    c.id,
                    c.category_code as code,
                    COALESCE(et.translation_text, c.name_es) as name,
                    COUNT(fs.id) FILTER (WHERE fs.status = 'active'::service_status_enum) as count
                FROM categories c
                LEFT JOIN fiscal_services fs ON fs.category_id = c.id
                LEFT JOIN entity_translations et ON
                    et.entity_type = 'category'
                    AND et.entity_code = c.category_code
                    AND et.field_name = 'name'
                    AND et.language_code = $1
                WHERE c.is_active = true
                GROUP BY c.id, c.category_code, c.name_es, et.translation_text
                HAVING COUNT(fs.id) FILTER (WHERE fs.status = 'active'::service_status_enum) > 0
                ORDER BY count DESC
                LIMIT 20
            """

        # SERVICE TYPES: Filter by category_code if provided
        if category_code:
            service_types_query = """
                SELECT
                    fs.service_type::TEXT as type,
                    COUNT(*) as count
                FROM fiscal_services fs
                JOIN categories c ON fs.category_id = c.id
                WHERE fs.status = 'active'::service_status_enum
                    AND c.category_code = $1
                GROUP BY fs.service_type
                ORDER BY count DESC
            """
        else:
            service_types_query = """
                SELECT
                    service_type::TEXT as type,
                    COUNT(*) as count
                FROM fiscal_services
                WHERE status = 'active'::service_status_enum
                GROUP BY service_type
                ORDER BY count DESC
            """

        try:
            # Sequential fetch: asyncpg connections cannot run concurrent queries
            cat_params = (categories_query, language, ministry_id) if ministry_id else (categories_query, language)
            svc_params = (service_types_query, category_code) if category_code else (service_types_query,)

            ministries_rows = await self.db.fetch(ministries_query, language)
            categories_rows = await self.db.fetch(*cat_params)
            service_types_rows = await self.db.fetch(*svc_params)

            return {
                "categories": [dict(row) for row in categories_rows],
                "ministries": [dict(row) for row in ministries_rows],
                "service_types": [dict(row) for row in service_types_rows],
                "price_ranges": []
            }

        except asyncpg.PostgresError as e:
            logger.error(f"Database error in get_search_facets: {e}")
            raise

    async def autocomplete(
        self,
        q: str,
        language: str = "es",
        limit: int = 7,
    ) -> List[Dict[str, Any]]:
        """
        Fast autocomplete suggestions using tsvector prefix matching + pg_trgm similarity.

        Returns up to `limit` results with: id, name, category_name, service_type, expedition_price.
        Designed for <100ms response on type-ahead (debounced 200-300ms frontend).
        """
        if not q or len(q.strip()) < 2:
            return []

        q_clean = q.strip()

        # Language column mapping
        lang_suffix = {"fr": "fr", "en": "en"}.get(language, "")
        name_col = f"COALESCE(mv.name_{lang_suffix}, mv.name_es)" if lang_suffix else "mv.name_es"
        cat_col = f"COALESCE(mv.category_name_{lang_suffix}, mv.category_name_es)" if lang_suffix else "mv.category_name_es"

        # Use plainto_tsquery (safe for user input) — no prefix matching needed,
        # pg_trgm similarity handles partial matches as fallback
        query = f"""
            SELECT
                mv.id,
                {name_col} AS name,
                {cat_col} AS category_name,
                mv.service_type::TEXT AS service_type,
                COALESCE(mv.tasa_expedicion, 0)::FLOAT AS expedition_price,
                ts_rank(fs.search_vector, plainto_tsquery('spanish', $1)) AS rank,
                similarity(mv.name_es, $1) AS sim
            FROM mv_services_translated mv
            JOIN fiscal_services fs ON fs.id = mv.id
            WHERE fs.search_vector @@ plainto_tsquery('spanish', $1)
               OR similarity(mv.name_es, $1) > 0.15
            ORDER BY rank DESC, sim DESC
            LIMIT $2
        """

        try:
            rows = await self.db.fetch(query, q_clean, limit)
            return [
                {
                    "id": row["id"],
                    "name": row["name"],
                    "category_name": row["category_name"],
                    "service_type": row["service_type"],
                    "expedition_price": row["expedition_price"],
                }
                for row in rows
            ]
        except asyncpg.PostgresError as e:
            logger.error(f"Autocomplete error: {e}")
            return []

    async def search_bundles(
        self,
        q: str,
        language: str = "es",
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Search service bundles by name/commerce_type.
        Surfaced alongside service results when a query matches a bundle.
        """
        if not q or len(q.strip()) < 2:
            return []

        search_term = f"%{q.strip()}%"

        # For es: no translation JOINs needed. For fr/en: JOIN entity_translations.
        needs_translation = language in ("fr", "en")

        if needs_translation:
            query = f"""
                SELECT sb.id,
                    COALESCE(et_name.translation_text, sb.name_es) AS name,
                    COALESCE(et_desc.translation_text, sb.description_es) AS description,
                    sb.bundle_code, sb.commerce_type,
                    (SELECT COUNT(*) FROM service_bundle_items sbi
                     WHERE sbi.bundle_id = sb.id AND sbi.is_active = true) AS item_count
                FROM service_bundles sb
                LEFT JOIN entity_translations et_name ON
                    et_name.entity_type = 'bundle' AND et_name.entity_code = sb.bundle_code
                    AND et_name.field_name = 'name' AND et_name.language_code = $2
                LEFT JOIN entity_translations et_desc ON
                    et_desc.entity_type = 'bundle' AND et_desc.entity_code = sb.bundle_code
                    AND et_desc.field_name = 'description' AND et_desc.language_code = $2
                WHERE sb.is_active = true
                  AND (sb.name_es ILIKE $1 OR sb.commerce_type ILIKE $1
                       OR sb.description_es ILIKE $1)
                ORDER BY sb.name_es LIMIT $3
            """
            query_params = (search_term, language, limit)
        else:
            query = """
                SELECT sb.id, sb.name_es AS name, sb.description_es AS description,
                    sb.bundle_code, sb.commerce_type,
                    (SELECT COUNT(*) FROM service_bundle_items sbi
                     WHERE sbi.bundle_id = sb.id AND sbi.is_active = true) AS item_count
                FROM service_bundles sb
                WHERE sb.is_active = true
                  AND (sb.name_es ILIKE $1 OR sb.commerce_type ILIKE $1
                       OR sb.description_es ILIKE $1)
                ORDER BY sb.name_es LIMIT $2
            """
            query_params = (search_term, limit)

        try:
            rows = await self.db.fetch(query, *query_params)
            return [dict(row) for row in rows]
        except asyncpg.PostgresError as e:
            logger.error(f"Bundle search error: {e}")
            return []

    # ========================================================================
    # SEMANTIC SEARCH (pgvector cosine similarity)
    # ========================================================================

    async def semantic_search(
        self,
        query_embedding: list,
        language: str = "es",
        limit: int = 10,
        similarity_threshold: float = 0.1,
    ) -> List[Dict[str, Any]]:
        """
        Semantic search using pgvector cosine similarity on fiscal_services.embedding.
        Uses mv_services_translated for multilingual results.

        Args:
            query_embedding: 768-dim vector from EmbeddingService
            language: Language code (es/fr/en)
            limit: Max results
            similarity_threshold: Minimum similarity score (0-1)

        Returns:
            List of services with similarity scores, translated names/descriptions
        """
        embedding_str = '[' + ','.join(str(x) for x in query_embedding) + ']'

        # Language-specific column mapping on mv_services_translated
        lang_suffix = "" if language == "es" else f"_{language}"
        name_col = f"mv.name{lang_suffix}" if language != "es" else "mv.name_es"
        desc_col = f"mv.description{lang_suffix}" if language != "es" else "mv.description_es"
        cat_col = f"mv.category_name{lang_suffix}" if language != "es" else "mv.category_name_es"
        min_col = f"mv.ministry_name{lang_suffix}" if language != "es" else "mv.ministry_name_es"

        # For FR/EN, COALESCE to ES fallback
        if language != "es":
            name_col = f"COALESCE({name_col}, mv.name_es)"
            desc_col = f"COALESCE({desc_col}, mv.description_es)"
            cat_col = f"COALESCE({cat_col}, mv.category_name_es)"
            min_col = f"COALESCE({min_col}, mv.ministry_name_es)"

        query = f"""
            SELECT
                mv.id,
                {name_col} AS name,
                {desc_col} AS description,
                {cat_col} AS category_name,
                {min_col} AS ministry_name,
                mv.service_type,
                COALESCE(mv.tasa_expedicion, 0) AS expedition_price,
                COALESCE(mv.tasa_renovacion, 0) AS renewal_price,
                (1 - (fs.embedding <=> $1::vector))::FLOAT AS similarity
            FROM mv_services_translated mv
            JOIN fiscal_services fs ON fs.id = mv.id
            WHERE fs.embedding IS NOT NULL
              AND fs.status = 'active'
              AND (1 - (fs.embedding <=> $1::vector)) >= $2
            ORDER BY fs.embedding <=> $1::vector
            LIMIT $3
        """

        try:
            rows = await self.db.fetch(query, embedding_str, similarity_threshold, limit)
            return [dict(row) for row in rows]
        except asyncpg.PostgresError as e:
            logger.error(f"Semantic search error: {e}")
            return []
