-- Migration 234: Full-Text Search + Performance Indexes for 1M+ Companies
-- Part of OMS Companies Phase 1 — Database & Performance Foundation
--
-- Adds:
--   1. search_vector GENERATED column (tsvector, weighted: legal_name A, nif A, objeto_social C)
--   2. GIN index on search_vector (replaces ILIKE for O(log N) text search)
--   3. GIN trigram indexes on legal_name + nif (for partial match / autocomplete)
--   4. Composite indexes for admin + supervisor filter patterns
--   5. Cursor pagination index (created_at DESC, id DESC)
--
-- VERIFIED: pg_trgm extension exists (v1.6), spanish ts_config exists
-- VERIFIED: No existing GIN/tsvector indexes on companies

BEGIN;

-- ════════════════════════════════════════════════════════════════════
-- 1. Full-Text Search Vector (GENERATED STORED column)
-- ════════════════════════════════════════════════════════════════════

-- Weighted tsvector: legal_name/nif = highest priority, objeto_social = lowest
-- Uses 'spanish' config for proper stemming (GE = Spanish-speaking)
ALTER TABLE companies ADD COLUMN IF NOT EXISTS search_vector tsvector
    GENERATED ALWAYS AS (
        setweight(to_tsvector('spanish', COALESCE(legal_name, '')), 'A') ||
        setweight(to_tsvector('spanish', COALESCE(nif, '')), 'A') ||
        setweight(to_tsvector('spanish', COALESCE(registration_number, '')), 'A') ||
        setweight(to_tsvector('spanish', COALESCE(trade_name, '')), 'B') ||
        setweight(to_tsvector('spanish', COALESCE(objeto_social, '')), 'C')
    ) STORED;

-- GIN index for ts_query full-text search
CREATE INDEX IF NOT EXISTS idx_companies_search_vector
    ON companies USING GIN(search_vector);

-- ════════════════════════════════════════════════════════════════════
-- 2. Trigram indexes for partial match / autocomplete (ILIKE '%query%')
-- ════════════════════════════════════════════════════════════════════

-- legal_name: most common search field for autocomplete
CREATE INDEX IF NOT EXISTS idx_companies_legal_name_trgm
    ON companies USING GIN(legal_name gin_trgm_ops);

-- nif: exact or partial NIF lookup
CREATE INDEX IF NOT EXISTS idx_companies_nif_trgm
    ON companies USING GIN(nif gin_trgm_ops)
    WHERE nif IS NOT NULL;

-- ════════════════════════════════════════════════════════════════════
-- 3. Composite indexes for frequent filter patterns
-- ════════════════════════════════════════════════════════════════════

-- Admin list: filters by is_active + regimen_fiscal + zone_id
CREATE INDEX IF NOT EXISTS idx_companies_active_regimen_zone
    ON companies(is_active, regimen_fiscal, zone_id);

-- Supervisor: filter by city_id (entity-scoped)
CREATE INDEX IF NOT EXISTS idx_companies_city_id
    ON companies(city_id)
    WHERE city_id IS NOT NULL;

-- Public directory: verified active companies only
CREATE INDEX IF NOT EXISTS idx_companies_public_directory
    ON companies(is_active, is_verified)
    WHERE is_active = true AND is_verified = true;

-- ════════════════════════════════════════════════════════════════════
-- 4. Cursor-based pagination index
-- ════════════════════════════════════════════════════════════════════

-- Keyset pagination: WHERE (created_at, id) < ($cursor_ts, $cursor_id)
-- ORDER BY created_at DESC, id DESC LIMIT $page_size
CREATE INDEX IF NOT EXISTS idx_companies_cursor_pagination
    ON companies(created_at DESC, id DESC);

-- ════════════════════════════════════════════════════════════════════
-- 5. Helper function: plainto_tsquery with prefix matching
-- ════════════════════════════════════════════════════════════════════

-- Converts user input to a ts_query that supports prefix matching
-- "empresa const" → 'empresa' & 'const':*
CREATE OR REPLACE FUNCTION company_search_query(search_text TEXT)
RETURNS tsquery
LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE
AS $$
    SELECT CASE
        WHEN TRIM(search_text) = '' THEN ''::tsquery
        ELSE (
            SELECT string_agg(lexeme || ':*', ' & ')::tsquery
            FROM unnest(string_to_array(TRIM(search_text), ' ')) AS lexeme
            WHERE lexeme != ''
        )
    END
$$;

COMMENT ON FUNCTION company_search_query(TEXT) IS
    'Convert user search input to tsquery with prefix matching. '
    'Example: "empresa const" → empresa:* & const:*';

COMMIT;
