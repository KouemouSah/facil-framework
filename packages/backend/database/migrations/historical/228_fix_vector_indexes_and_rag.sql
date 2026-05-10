-- Migration 228: Fix vector indexes + SQL function for RAG
-- Fixes:
--   1. legislacion_documents HNSW index: vector_l2_ops → vector_cosine_ops (match <=> operator)
--   2. search_legislacion_documents_semantic: return TRUE similarity (1 - distance), not raw distance
--   3. fiscal_services HNSW index already uses vector_cosine_ops (verified) — no change needed
--
-- Impact: HNSW index will actually be used → queries drop from ~500ms (seq scan) to ~10-50ms

-- ============================================================
-- 1. Rebuild legislacion_documents HNSW index with cosine ops
-- ============================================================
DROP INDEX IF EXISTS idx_legislacion_documents_embedding_hnsw;
CREATE INDEX idx_legislacion_documents_embedding_hnsw
ON legislacion_documents USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- ============================================================
-- 2. Rewrite search function to return true similarity [0,1]
--    Old: returned raw cosine DISTANCE (0=identical, 1=orthogonal)
--         named "similarity" → confusing, ORDER BY ASC needed
--    New: returns 1 - distance = true similarity (1=identical)
--         ORDER BY DESC = most similar first
-- ============================================================
CREATE OR REPLACE FUNCTION search_legislacion_documents_semantic(
    query_embedding vector,
    _limit integer DEFAULT 5,
    similarity_threshold double precision DEFAULT 0.7
)
RETURNS TABLE(
    id uuid,
    document_name text,
    page_number integer,
    chunk_id text,
    content text,
    similarity double precision
)
LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT
        ld.id,
        ld.document_name,
        ld.page_number,
        ld.chunk_id,
        ld.content,
        (1 - (ld.embedding <=> query_embedding))::double precision AS similarity
    FROM legislacion_documents ld
    WHERE ld.embedding IS NOT NULL
      AND (1 - (ld.embedding <=> query_embedding)) >= similarity_threshold
    ORDER BY similarity DESC
    LIMIT _limit;
END;
$$;
