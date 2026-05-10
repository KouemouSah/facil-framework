"""
Legislacion Repository - Vector similarity search for legislative documents using pgvector

Provides efficient semantic search over legislacion_documents using
vector embeddings and cosine similarity.

Author: Claude Code
Date: 2025-01-22 (adapted for legislacion_documents: 2026-02-11)
"""

from typing import List, Dict, Any, Optional
import asyncpg
from loguru import logger

from app.config import settings


class LegislacionRepository:
    """
    Repository for semantic search in legislacion_documents using pgvector
    """

    def __init__(self, db: asyncpg.Connection):
        """
        Initialize repository with database connection
        """
        self.db = db

    async def search_documents(
        self,
        query_embedding: List[float],
        limit: Optional[int] = None,
        similarity_threshold: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Search legislative document chunks using vector similarity

        Args:
            query_embedding: 768-dimensional query vector
            limit: Max results (default: from settings.RAG_MAX_CONTEXT_DOCUMENTS)
            similarity_threshold: Min similarity score 0-1 (default: from settings.SEMANTIC_SEARCH_SIMILARITY_THRESHOLD)

        Returns:
            List of document chunks with similarity scores.
        """
        if limit is None:
            # Reusing SEMANTIC_SEARCH_TOP_K for now. A dedicated RAG_MAX_CONTEXT_DOCUMENTS setting might be better.
            limit = settings.SEMANTIC_SEARCH_TOP_K
        if similarity_threshold is None:
            similarity_threshold = settings.SEMANTIC_SEARCH_SIMILARITY_THRESHOLD

        embedding_str = '[' + ','.join(str(x) for x in query_embedding) + ']'

        # Use the helper function created in the migration
        query = f"""
            SELECT
                id,
                document_name,
                page_number,
                chunk_id,
                content,
                similarity
            FROM search_legislacion_documents_semantic(
                $1::vector,
                $2,
                $3
            ) ORDER BY similarity DESC;
        """

        try:
            results = await self.db.fetch(query, embedding_str, limit, similarity_threshold)
            documents = [dict(row) for row in results]
            logger.info(
                f"Legislacion search: {len(documents)} results after threshold filter "
                f"(threshold: {similarity_threshold}, limit: {limit})"
            )
            return documents
        except Exception as e:
            logger.error(f"Legislacion semantic search failed: {e}")
            return []

    async def get_embedding_stats(self) -> Dict[str, Any]:
        """
        Get statistics about embedding coverage for legislative documents.
        """
        query = """
            SELECT * FROM v_legislacion_embedding_status
        """
        try:
            result = await self.db.fetchrow(query)
            if result:
                stats = dict(result)
                logger.info(f"Legislacion embedding coverage: {stats.get('embedding_coverage_percent', 0)}%")
                return stats
            else:
                return {
                    "total_chunks": 0,
                    "embedded_chunks": 0,
                    "chunks_needing_update": 0,
                    "embedding_coverage_percent": 0.0
                }
        except Exception as e:
            logger.error(f"Failed to get legislacion embedding stats: {e}")
            return {}

# Factory function (similar to existing)
async def create_legislacion_repository(
    db: asyncpg.Connection
) -> LegislacionRepository:
    """
    Factory function to create legislacion documents repository
    """
    return LegislacionRepository(db)
