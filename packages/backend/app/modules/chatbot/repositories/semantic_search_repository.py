"""
Semantic Search Repository - Vector similarity search using pgvector

Provides efficient semantic search over fiscal_services using
vector embeddings and cosine similarity.

Author: Claude Code
Date: 2025-01-22
"""

from typing import List, Dict, Any, Optional
import asyncpg
from loguru import logger

from app.config import settings


class SemanticSearchRepository:
    """
    Repository for semantic search using pgvector

    Uses cosine distance (<=> operator) for similarity search.
    Leverages HNSW index for fast approximate nearest neighbor search.

    Query performance:
    - With HNSW index: ~10-50ms for top-K search
    - Without index: ~500ms+ (sequential scan)

    Usage:
        repo = SemanticSearchRepository(db_connection)
        results = await repo.search_services(query_embedding, limit=5)
    """

    def __init__(self, db: asyncpg.Connection):
        """
        Initialize repository with database connection

        Args:
            db: asyncpg connection or connection pool
        """
        self.db = db

    async def search_services(
        self,
        query_embedding: List[float],
        limit: int = None,
        similarity_threshold: float = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search fiscal services using vector similarity

        Args:
            query_embedding: 768-dimensional query vector
            limit: Max results (default: from settings)
            similarity_threshold: Min similarity score 0-1 (default: from settings)
            filters: Optional filters:
                - category_id: Filter by category
                - service_type: Filter by service type
                - sector_id: Filter by sector
                - ministry_id: Filter by ministry

        Returns:
            List of fiscal services with similarity scores, enriched with:
            - Basic service info (code, name, description)
            - Category hierarchy (category, sector, ministry)
            - Keywords (filtered by language)
            - Required documents
            - Procedures
            - Similarity score (0-1, higher = more relevant)

        Example:
            results = await repo.search_services(
                query_embedding=[0.1, 0.2, ...],
                limit=5,
                similarity_threshold=0.7,
                filters={"category_id": 3}
            )
        """
        # Use defaults from settings
        if limit is None:
            limit = settings.SEMANTIC_SEARCH_TOP_K

        if similarity_threshold is None:
            similarity_threshold = settings.SEMANTIC_SEARCH_SIMILARITY_THRESHOLD

        # Build dynamic WHERE clause
        where_conditions = ["fs.status = 'active'", "fs.embedding IS NOT NULL"]
        # Convert embedding list to pgvector string format: '[x,y,z,...]'
        embedding_str = '[' + ','.join(str(x) for x in query_embedding) + ']'
        params = [embedding_str, similarity_threshold, limit]
        param_idx = 4

        # Add filters
        if filters:
            if filters.get('category_id'):
                where_conditions.append(f"fs.category_id = ${param_idx}")
                params.append(filters['category_id'])
                param_idx += 1

            if filters.get('service_type'):
                where_conditions.append(f"fs.service_type = ${param_idx}")
                params.append(filters['service_type'])
                param_idx += 1

            if filters.get('sector_id'):
                where_conditions.append(f"c.sector_id = ${param_idx}")
                params.append(filters['sector_id'])
                param_idx += 1

            if filters.get('ministry_id'):
                where_conditions.append(f"c.ministry_id = ${param_idx}")
                params.append(filters['ministry_id'])
                param_idx += 1

        where_clause = " AND ".join(where_conditions)

        # Query with full context enrichment
        query = f"""
            SELECT
                fs.id,
                fs.service_code,
                fs.name_es,
                fs.description_es,
                fs.service_type,
                fs.calculation_method,
                fs.tasa_expedicion,
                fs.tasa_renovacion,
                fs.processing_time_days,
                fs.validity_period_months,
                fs.legal_reference,

                -- Category hierarchy
                c.id as category_id,
                c.name_es as category_name,
                s.id as sector_id,
                s.name_es as sector_name,
                m.id as ministry_id,
                m.name_es as ministry_name,

                -- Cosine similarity (1 - cosine distance) — matches vector_cosine_ops HNSW index
                (1 - (fs.embedding <=> $1::vector))::FLOAT as similarity,

                -- Keywords aggregation (Spanish only)
                COALESCE(
                    jsonb_agg(
                        DISTINCT jsonb_build_object(
                            'keyword', sk.keyword,
                            'weight', sk.weight
                        ) ORDER BY jsonb_build_object(
                            'keyword', sk.keyword,
                            'weight', sk.weight
                        )
                    ) FILTER (WHERE sk.id IS NOT NULL AND sk.language_code = 'es'),
                    '[]'::jsonb
                ) as keywords,

                -- Required documents
                COALESCE(
                    jsonb_agg(
                        DISTINCT jsonb_build_object(
                            'template_code', dt.template_code,
                            'document_name', dt.document_name_es,
                            'is_required_expedition', sda.is_required_expedition,
                            'is_required_renewal', sda.is_required_renewal
                        ) ORDER BY jsonb_build_object(
                            'template_code', dt.template_code,
                            'document_name', dt.document_name_es,
                            'is_required_expedition', sda.is_required_expedition,
                            'is_required_renewal', sda.is_required_renewal
                        )
                    ) FILTER (WHERE dt.id IS NOT NULL),
                    '[]'::jsonb
                ) as required_documents,

                -- Procedures with actual step descriptions
                COALESCE(
                    jsonb_agg(
                        DISTINCT jsonb_build_object(
                            'procedure_name', pt.name_es,
                            'applies_to', spa.applies_to,
                            'steps', COALESCE(pts_data.steps, '[]'::jsonb)
                        ) ORDER BY jsonb_build_object(
                            'procedure_name', pt.name_es,
                            'applies_to', spa.applies_to,
                            'steps', COALESCE(pts_data.steps, '[]'::jsonb)
                        )
                    ) FILTER (WHERE pt.id IS NOT NULL),
                    '[]'::jsonb
                ) as procedures,

                -- Bundle context (for RAG enrichment)
                sb.name_es as bundle_name,
                cz.name_es as zone_name

            FROM fiscal_services fs

            -- Join category hierarchy
            LEFT JOIN categories c ON fs.category_id = c.id
            LEFT JOIN sectors s ON c.sector_id = s.id
            LEFT JOIN ministries m ON c.ministry_id = m.id

            -- Join bundle context (first bundle item + zone for RAG)
            LEFT JOIN LATERAL (
                SELECT sbi.bundle_id, sbi.zone_id
                FROM service_bundle_items sbi
                WHERE sbi.fiscal_service_id = fs.id
                LIMIT 1
            ) first_bundle ON true
            LEFT JOIN service_bundles sb ON sb.id = first_bundle.bundle_id
            LEFT JOIN commerce_zones cz ON cz.id = first_bundle.zone_id

            -- Join keywords
            LEFT JOIN service_keywords sk ON fs.id = sk.fiscal_service_id

            -- Join documents
            LEFT JOIN service_document_assignments sda ON fs.id = sda.fiscal_service_id
            LEFT JOIN document_templates dt ON sda.document_template_id = dt.id

            -- Join procedures
            LEFT JOIN service_procedure_assignments spa ON fs.id = spa.fiscal_service_id
            LEFT JOIN procedure_templates pt ON spa.template_id = pt.id
            -- Get procedure steps with descriptions
            LEFT JOIN LATERAL (
                SELECT jsonb_agg(
                    jsonb_build_object(
                        'step_number', pts.step_number,
                        'description', pts.description_es
                    ) ORDER BY pts.step_number
                ) as steps
                FROM procedure_template_steps pts
                WHERE pts.template_id = pt.id
            ) pts_data ON true

            WHERE {where_clause}
                AND (1 - (fs.embedding <=> $1::vector)) >= $2

            GROUP BY
                fs.id, fs.service_code, fs.name_es, fs.description_es,
                fs.service_type, fs.calculation_method, fs.tasa_expedicion,
                fs.tasa_renovacion, fs.processing_time_days,
                fs.validity_period_months, fs.legal_reference,
                c.id, c.name_es, s.id, s.name_es, m.id, m.name_es,
                sb.name_es, cz.name_es

            -- Order by cosine distance (HNSW index accelerates this)
            ORDER BY fs.embedding <=> $1::vector
            LIMIT $3
        """

        try:
            results = await self.db.fetch(query, *params)

            # SQL already filters by threshold — no need for redundant Python filter
            services = [dict(row) for row in results]

            logger.info(
                f"Semantic search: {len(services)} results "
                f"(threshold: {similarity_threshold}, limit: {limit})"
            )

            return services

        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return []

    async def search_services_hybrid(
        self,
        query_embedding: List[float],
        query_text: str,
        limit: int = None,
        similarity_threshold: float = None,
        semantic_weight: float = 0.7,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Hybrid search combining semantic (vector) and full-text (tsvector).
        Returns the SAME enriched fields as search_services() for full compatibility.

        Args:
            query_embedding: 768-dimensional query vector
            query_text: Original query text for full-text search
            limit: Max results
            similarity_threshold: Min combined score (0-1)
            semantic_weight: Weight for semantic score (0-1, default 0.7)
            filters: Optional filters (category_id, service_type, sector_id, ministry_id)

        Returns:
            Services ranked by combined score with full context enrichment
        """
        if limit is None:
            limit = settings.SEMANTIC_SEARCH_TOP_K
        if similarity_threshold is None:
            similarity_threshold = settings.SEMANTIC_SEARCH_SIMILARITY_THRESHOLD

        fulltext_weight = 1.0 - semantic_weight

        where_conditions = ["fs.status = 'active'", "fs.embedding IS NOT NULL"]
        embedding_str = '[' + ','.join(str(x) for x in query_embedding) + ']'
        params = [embedding_str, query_text, semantic_weight, fulltext_weight, similarity_threshold, limit]
        param_idx = 7

        if filters:
            if filters.get('category_id'):
                where_conditions.append(f"fs.category_id = ${param_idx}")
                params.append(filters['category_id'])
                param_idx += 1
            if filters.get('service_type'):
                where_conditions.append(f"fs.service_type = ${param_idx}")
                params.append(filters['service_type'])
                param_idx += 1
            if filters.get('sector_id'):
                where_conditions.append(f"c.sector_id = ${param_idx}")
                params.append(filters['sector_id'])
                param_idx += 1
            if filters.get('ministry_id'):
                where_conditions.append(f"c.ministry_id = ${param_idx}")
                params.append(filters['ministry_id'])
                param_idx += 1

        where_clause = " AND ".join(where_conditions)

        query = f"""
            SELECT
                fs.id,
                fs.service_code,
                fs.name_es,
                fs.description_es,
                fs.service_type,
                fs.calculation_method,
                fs.tasa_expedicion,
                fs.tasa_renovacion,
                fs.processing_time_days,
                fs.validity_period_months,
                fs.legal_reference,

                -- Category hierarchy
                c.id as category_id,
                c.name_es as category_name,
                s.id as sector_id,
                s.name_es as sector_name,
                m.id as ministry_id,
                m.name_es as ministry_name,

                -- Combined score as "similarity" for downstream compatibility
                (
                    $3 * (1 - (fs.embedding <=> $1::vector)) +
                    $4 * ts_rank(fs.search_vector, plainto_tsquery('simple', $2))
                )::FLOAT as similarity,

                -- Keywords
                COALESCE(
                    jsonb_agg(
                        DISTINCT jsonb_build_object('keyword', sk.keyword, 'weight', sk.weight)
                        ORDER BY jsonb_build_object('keyword', sk.keyword, 'weight', sk.weight)
                    ) FILTER (WHERE sk.id IS NOT NULL AND sk.language_code = 'es'),
                    '[]'::jsonb
                ) as keywords,

                -- Required documents
                COALESCE(
                    jsonb_agg(
                        DISTINCT jsonb_build_object(
                            'template_code', dt.template_code,
                            'document_name', dt.document_name_es,
                            'is_required_expedition', sda.is_required_expedition,
                            'is_required_renewal', sda.is_required_renewal
                        ) ORDER BY jsonb_build_object(
                            'template_code', dt.template_code,
                            'document_name', dt.document_name_es,
                            'is_required_expedition', sda.is_required_expedition,
                            'is_required_renewal', sda.is_required_renewal
                        )
                    ) FILTER (WHERE dt.id IS NOT NULL),
                    '[]'::jsonb
                ) as required_documents,

                -- Procedures with steps
                COALESCE(
                    jsonb_agg(
                        DISTINCT jsonb_build_object(
                            'procedure_name', pt.name_es,
                            'applies_to', spa.applies_to,
                            'steps', COALESCE(pts_data.steps, '[]'::jsonb)
                        ) ORDER BY jsonb_build_object(
                            'procedure_name', pt.name_es,
                            'applies_to', spa.applies_to,
                            'steps', COALESCE(pts_data.steps, '[]'::jsonb)
                        )
                    ) FILTER (WHERE pt.id IS NOT NULL),
                    '[]'::jsonb
                ) as procedures,

                -- Bundle context
                sb.name_es as bundle_name,
                cz.name_es as zone_name

            FROM fiscal_services fs
            LEFT JOIN categories c ON fs.category_id = c.id
            LEFT JOIN sectors s ON c.sector_id = s.id
            LEFT JOIN ministries m ON c.ministry_id = m.id
            LEFT JOIN LATERAL (
                SELECT sbi.bundle_id, sbi.zone_id
                FROM service_bundle_items sbi
                WHERE sbi.fiscal_service_id = fs.id
                LIMIT 1
            ) first_bundle ON true
            LEFT JOIN service_bundles sb ON sb.id = first_bundle.bundle_id
            LEFT JOIN commerce_zones cz ON cz.id = first_bundle.zone_id
            LEFT JOIN service_keywords sk ON fs.id = sk.fiscal_service_id
            LEFT JOIN service_document_assignments sda ON fs.id = sda.fiscal_service_id
            LEFT JOIN document_templates dt ON sda.document_template_id = dt.id
            LEFT JOIN service_procedure_assignments spa ON fs.id = spa.fiscal_service_id
            LEFT JOIN procedure_templates pt ON spa.template_id = pt.id
            LEFT JOIN LATERAL (
                SELECT jsonb_agg(
                    jsonb_build_object('step_number', pts.step_number, 'description', pts.description_es)
                    ORDER BY pts.step_number
                ) as steps
                FROM procedure_template_steps pts
                WHERE pts.template_id = pt.id
            ) pts_data ON true

            WHERE {where_clause}
                AND (
                    $3 * (1 - (fs.embedding <=> $1::vector)) +
                    $4 * ts_rank(fs.search_vector, plainto_tsquery('simple', $2))
                ) >= $5

            GROUP BY
                fs.id, fs.service_code, fs.name_es, fs.description_es,
                fs.service_type, fs.calculation_method, fs.tasa_expedicion,
                fs.tasa_renovacion, fs.processing_time_days,
                fs.validity_period_months, fs.legal_reference,
                c.id, c.name_es, s.id, s.name_es, m.id, m.name_es,
                sb.name_es, cz.name_es

            ORDER BY similarity DESC
            LIMIT $6
        """

        try:
            results = await self.db.fetch(query, *params)
            services = [dict(row) for row in results]

            logger.info(
                f"Hybrid search: {len(services)} results "
                f"(semantic_w={semantic_weight}, threshold={similarity_threshold})"
            )
            return services

        except Exception as e:
            logger.error(f"Hybrid search failed: {e}")
            return []

    async def get_similar_services(
        self,
        service_id: int,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Find services similar to a given service

        Uses the service's embedding to find nearest neighbors

        Args:
            service_id: ID of reference service
            limit: Max similar services to return

        Returns:
            List of similar services (excluding the reference service)

        Use cases:
        - "You might also be interested in..."
        - Related services suggestions
        - Service grouping/clustering
        """
        query = """
            WITH reference_service AS (
                SELECT embedding
                FROM fiscal_services
                WHERE id = $1
                  AND embedding IS NOT NULL
            )
            SELECT
                fs.id,
                fs.service_code,
                fs.name_es,
                fs.description_es,
                c.name_es as category_name,
                sb.name_es as bundle_name,
                cz.name_es as zone_name,
                (1 - (fs.embedding <=> ref.embedding))::FLOAT as similarity
            FROM fiscal_services fs
            CROSS JOIN reference_service ref
            LEFT JOIN categories c ON fs.category_id = c.id
            LEFT JOIN LATERAL (
                SELECT sbi.bundle_id, sbi.zone_id
                FROM service_bundle_items sbi
                WHERE sbi.fiscal_service_id = fs.id
                LIMIT 1
            ) first_bundle ON true
            LEFT JOIN service_bundles sb ON sb.id = first_bundle.bundle_id
            LEFT JOIN commerce_zones cz ON cz.id = first_bundle.zone_id
            WHERE fs.id != $1
              AND fs.status = 'active'
              AND fs.embedding IS NOT NULL
            ORDER BY fs.embedding <=> ref.embedding
            LIMIT $2
        """

        try:
            results = await self.db.fetch(query, service_id, limit)

            services = []
            for row in results:
                service = dict(row)
                services.append(service)

            logger.info(
                f"Found {len(services)} services similar to service_id={service_id}"
            )

            return services

        except Exception as e:
            logger.error(f"Similar services search failed: {e}")
            return []

    async def get_embedding_stats(self) -> Dict[str, Any]:
        """
        Get statistics about embedding coverage

        Returns:
            Dict with embedding statistics:
            - total_services: Total active services
            - with_embeddings: Services with embeddings
            - without_embeddings: Services missing embeddings
            - needs_update: Services flagged for update
            - coverage_percentage: % of services with embeddings
            - last_generated: Most recent embedding timestamp
        """
        query = """
            SELECT * FROM v_embedding_status
        """

        try:
            result = await self.db.fetchrow(query)

            if result:
                stats = dict(result)
                logger.info(f"Embedding coverage: {stats.get('coverage_percentage', 0)}%")
                return stats
            else:
                return {
                    "total_services": 0,
                    "with_embeddings": 0,
                    "without_embeddings": 0,
                    "coverage_percentage": 0.0
                }

        except Exception as e:
            logger.error(f"Failed to get embedding stats: {e}")
            return {}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

async def create_semantic_search_repository(
    db: asyncpg.Connection
) -> SemanticSearchRepository:
    """
    Factory function to create semantic search repository

    Args:
        db: Database connection

    Returns:
        Initialized SemanticSearchRepository instance
    """
    return SemanticSearchRepository(db)
