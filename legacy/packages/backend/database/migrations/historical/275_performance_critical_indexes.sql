-- Migration 275: Critical Performance Index Fixes
-- Date: 2026-03-21
-- Author: Claude (Performance Optimizer)
--
-- 4 fixes identified by pg_stat_statements + pg_stat_user_indexes audit:
--
-- FIX 1a: legislacion_documents HNSW index uses vector_l2_ops but queries use <=> (cosine)
--          Migration 228 was never applied in production → 50x slower RAG queries
--
-- FIX 1b: fiscal_services HNSW index SAME BUG — vector_l2_ops instead of vector_cosine_ops
--          848/873 services have embeddings, actively used by chatbot RAG + homepage search
--          Had 0 scans because PostgreSQL couldn't use L2 index for <=> cosine queries
--
-- FIX 2: appointment_holds missing composite index on (slot_config_id, appointment_date)
--         hold_appointment_slot() and get_available_slots_v3() do COUNT(*) per slot/date
--         Currently: only idx_holds_expires (expires_at WHERE held) and idx_holds_status exist
--
-- FIX 3: service_requests missing index on (entity_code, status, created_at)
--         Agent dashboard filters by entity_code → currently falls back to seq scan
--         idx_sr_workflow_status_created covers (workflow_code, status, created_at) but NOT entity_code
--

BEGIN;

-- ============================================================================
-- FIX 1a: Recreate legislacion_documents HNSW with correct cosine operator
-- ============================================================================
-- BEFORE: USING hnsw (embedding vector_l2_ops)  ← Euclidean distance
-- AFTER:  USING hnsw (embedding vector_cosine_ops) ← Cosine similarity (matches <=> operator)
-- Impact: RAG semantic search 428ms mean → ~10-50ms expected

DROP INDEX IF EXISTS idx_legislacion_documents_embedding_hnsw;

CREATE INDEX idx_legislacion_documents_embedding_hnsw
ON legislacion_documents USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- ============================================================================
-- FIX 1b: Recreate fiscal_services HNSW with correct cosine operator
-- ============================================================================
-- SAME BUG as legislacion_documents: vector_l2_ops → vector_cosine_ops
-- Used by: chatbot RAG (semantic_search_repository), homepage search,
--          enrichment agent, similar services, few-shot retriever
-- 848/873 services have embeddings (97.1% coverage)

DROP INDEX IF EXISTS idx_fiscal_services_embedding_hnsw;

CREATE INDEX idx_fiscal_services_embedding_hnsw
ON fiscal_services USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- ============================================================================
-- FIX 2: Appointment holds composite index for capacity checks
-- ============================================================================
-- Used by: hold_appointment_slot(), get_available_slots_v3()
-- Query pattern: SELECT COUNT(*) FROM appointment_holds
--   WHERE slot_config_id = $1 AND appointment_date = $2 AND status IN ('held','confirmed')
-- Current coverage: NONE for this pattern

CREATE INDEX IF NOT EXISTS idx_ah_slot_date_status
ON appointment_holds (slot_config_id, appointment_date)
WHERE status IN ('held'::appointment_hold_status, 'confirmed'::appointment_hold_status);


-- ============================================================================
-- FIX 3: Service requests entity_code composite for agent dashboards
-- ============================================================================
-- Used by: agent dashboard list, entity-scoped queries
-- Query pattern: WHERE entity_code = $1 AND status = $2 ORDER BY created_at DESC
-- Current coverage: idx_sr_entity_code (entity_code only, no status/sort)
--                   idx_sr_workflow_status_created (workflow_code, not entity_code)

CREATE INDEX IF NOT EXISTS idx_sr_entity_status_created
ON service_requests (entity_code, status, created_at DESC)
WHERE entity_code IS NOT NULL;


COMMIT;
