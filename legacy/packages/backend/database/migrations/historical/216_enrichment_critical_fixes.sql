-- Migration 216: Critical fixes for enrichment module
-- Fixes 3 critical bugs discovered in post-deployment audit:
--   1. description_source DEFAULT 'manual' prevents auto_enqueue from ever triggering
--   2. mv_services_translated has no UNIQUE INDEX → CONCURRENTLY always fails
--   3. Services without descriptions marked as 'manual' instead of NULL

-- ==========================================================================
-- FIX #1: Change column default from 'manual' to NULL
-- 'manual' means "a human wrote this" — new services without descriptions
-- should have NULL (meaning "no source yet, safe to auto-generate")
-- ==========================================================================
ALTER TABLE fiscal_services ALTER COLUMN description_source SET DEFAULT NULL;

COMMENT ON COLUMN fiscal_services.description_source IS
    'NULL = no description yet (auto-generate OK), manual = human-authored (never overwrite), ai_generated = LLM-generated (can regenerate)';

-- ==========================================================================
-- FIX #2: Services WITHOUT descriptions should have description_source = NULL
-- Migration 215 set ALL 869 services to 'manual' including the 856 without
-- any description. Only the 13 with actual descriptions should be 'manual'.
-- ==========================================================================
UPDATE fiscal_services
SET description_source = NULL
WHERE (description_es IS NULL OR description_es = '')
  AND description_source = 'manual';

-- ==========================================================================
-- FIX #3: Create UNIQUE INDEX on mv_services_translated
-- Required for REFRESH MATERIALIZED VIEW CONCURRENTLY (non-blocking reads)
-- Without this, CONCURRENTLY fails every cron run, falling back to blocking
-- refresh which locks the MV and blocks all reads during refresh.
-- ==========================================================================
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_mv_services_translated_id
    ON mv_services_translated (id);
