-- ============================================================================
-- Migration 202: Fiscal Services Schema Optimization
-- Date: 2026-03-10
-- Actions: C (drop redundant index), D (widen service_code),
--          E (materialized view), F (pricing table)
-- ============================================================================

BEGIN;

-- ============================================================================
-- ACTION C: Drop redundant index idx_fiscal_services_code
-- The UNIQUE constraint fiscal_services_service_code_key already creates
-- an implicit btree index on service_code. This saves ~30KB.
-- ============================================================================

DROP INDEX IF EXISTS idx_fiscal_services_code;

-- Drop unused index on workflow_code (0 rows have workflow_code)
DROP INDEX IF EXISTS idx_fiscal_services_workflow_code;


-- ============================================================================
-- ACTION D: Widen service_code constraint from T-NNN to T-NNNN[NN]
-- Current: ^T-[0-9]{3}$ → max 999 services (852 used = 85% capacity)
-- New: ^T-[0-9]{3,6}$ → max 999,999 services (backward compatible)
-- ============================================================================

ALTER TABLE fiscal_services DROP CONSTRAINT IF EXISTS valid_service_code;
ALTER TABLE fiscal_services ADD CONSTRAINT valid_service_code
    CHECK (service_code ~ '^T-[0-9]{3,6}$');


-- ============================================================================
-- ACTION E: Materialized view for fast listing
-- Replaces the 4-table JOIN (fiscal_services → categories → sectors → ministries)
-- with a flat, pre-joined view. Only lightweight columns (no embedding,
-- no search_vector, no JSONB blobs).
-- ============================================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_fiscal_services_catalog AS
SELECT
    fs.id,
    fs.service_code,
    fs.name_es,
    fs.description_es,
    fs.service_type,
    fs.calculation_method,
    fs.status,
    fs.tasa_expedicion,
    fs.tasa_renovacion,
    fs.processing_time_days,
    fs.priority,
    fs.complexity_level,
    fs.validity_period_months,
    fs.parent_service_id,
    fs.view_count,
    fs.calculation_count,
    fs.payment_count,
    fs.favorite_count,
    fs.created_at,
    fs.updated_at,
    -- Category
    c.id AS category_id,
    c.category_code,
    c.name_es AS category_name,
    -- Sector
    s.id AS sector_id,
    s.sector_code,
    s.name_es AS sector_name,
    -- Ministry
    m.id AS ministry_id,
    m.ministry_code,
    m.name_es AS ministry_name
FROM fiscal_services fs
JOIN categories c ON fs.category_id = c.id
LEFT JOIN sectors s ON c.sector_id = s.id
LEFT JOIN ministries m ON s.ministry_id = m.id;

-- Indexes on the materialized view for fast filtered queries
CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_catalog_id
    ON mv_fiscal_services_catalog (id);
CREATE INDEX IF NOT EXISTS idx_mv_catalog_status_calc
    ON mv_fiscal_services_catalog (status, calculation_count DESC);
CREATE INDEX IF NOT EXISTS idx_mv_catalog_category
    ON mv_fiscal_services_catalog (category_id) WHERE status = 'active';
CREATE INDEX IF NOT EXISTS idx_mv_catalog_ministry
    ON mv_fiscal_services_catalog (ministry_id) WHERE status = 'active';
CREATE INDEX IF NOT EXISTS idx_mv_catalog_service_code
    ON mv_fiscal_services_catalog (service_code);


-- ============================================================================
-- ACTION F: Separate pricing table (normalize tarification)
-- Moves the 13 rarely-used pricing columns out of fiscal_services into a
-- dedicated table. Keeps tasa_expedicion/tasa_renovacion on fiscal_services
-- as denormalized "current price" for fast reads.
-- ============================================================================

CREATE TABLE IF NOT EXISTS fiscal_service_pricing (
    id SERIAL PRIMARY KEY,
    fiscal_service_id INT NOT NULL REFERENCES fiscal_services(id) ON DELETE CASCADE,

    -- Calculation parameters
    base_percentage NUMERIC(5,4),
    percentage_of VARCHAR(100),
    unit_rate NUMERIC(15,4),
    unit_type VARCHAR(50),

    -- Formulas
    expedition_formula TEXT,
    expedition_unit_measure VARCHAR(50),
    renewal_formula TEXT,
    renewal_unit_measure VARCHAR(50),

    -- Advanced config
    calculation_config JSONB DEFAULT '{}'::jsonb,
    rate_tiers JSONB DEFAULT '[]'::jsonb,

    -- Grouping
    tier_group_name VARCHAR(100),
    is_tier_component BOOLEAN DEFAULT false,

    -- Penalties
    grace_period_days INT DEFAULT 0,
    late_penalty_percentage NUMERIC(5,2),
    late_penalty_fixed NUMERIC(15,2),
    penalty_calculation_rules JSONB DEFAULT '{}'::jsonb,

    -- Eligibility
    eligibility_criteria JSONB DEFAULT '{}'::jsonb,
    exemption_conditions JSONB DEFAULT '[]'::jsonb,

    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_fsp_service_id
    ON fiscal_service_pricing (fiscal_service_id);

-- Populate from existing data (only rows that have ANY non-default value)
INSERT INTO fiscal_service_pricing (
    fiscal_service_id,
    base_percentage, percentage_of, unit_rate, unit_type,
    expedition_formula, expedition_unit_measure,
    renewal_formula, renewal_unit_measure,
    calculation_config, rate_tiers,
    tier_group_name, is_tier_component,
    grace_period_days, late_penalty_percentage, late_penalty_fixed,
    penalty_calculation_rules, eligibility_criteria, exemption_conditions,
    created_at, updated_at
)
SELECT
    fs.id,
    fs.base_percentage, fs.percentage_of, fs.unit_rate, fs.unit_type,
    fs.expedition_formula, fs.expedition_unit_measure,
    fs.renewal_formula, fs.renewal_unit_measure,
    fs.calculation_config, fs.rate_tiers,
    fs.tier_group_name, fs.is_tier_component,
    fs.grace_period_days, fs.late_penalty_percentage, fs.late_penalty_fixed,
    fs.penalty_calculation_rules, fs.eligibility_criteria, fs.exemption_conditions,
    fs.created_at, fs.updated_at
FROM fiscal_services fs
WHERE fs.base_percentage IS NOT NULL
   OR fs.unit_rate IS NOT NULL
   OR fs.expedition_formula IS NOT NULL
   OR fs.renewal_formula IS NOT NULL
   OR fs.tier_group_name IS NOT NULL
   OR fs.late_penalty_percentage IS NOT NULL
   OR fs.late_penalty_fixed IS NOT NULL
   OR (fs.calculation_config IS NOT NULL AND fs.calculation_config != '{}'::jsonb)
   OR (fs.rate_tiers IS NOT NULL AND fs.rate_tiers != '[]'::jsonb)
   OR (fs.penalty_calculation_rules IS NOT NULL AND fs.penalty_calculation_rules != '{}'::jsonb)
   OR (fs.eligibility_criteria IS NOT NULL AND fs.eligibility_criteria != '{}'::jsonb)
   OR (fs.exemption_conditions IS NOT NULL AND fs.exemption_conditions != '[]'::jsonb)
ON CONFLICT (fiscal_service_id) DO NOTHING;

-- NOTE: We keep the original columns on fiscal_services for backward compatibility.
-- They will be deprecated and removed in a future migration after all code paths
-- are updated to read from fiscal_service_pricing.
-- DO NOT drop the columns yet.

COMMENT ON TABLE fiscal_service_pricing IS
    'Normalized pricing/penalty/eligibility config for fiscal services. '
    'Columns on fiscal_services are kept as deprecated cache until full migration.';

COMMENT ON MATERIALIZED VIEW mv_fiscal_services_catalog IS
    'Pre-joined flat view of fiscal services with category/sector/ministry. '
    'Refresh after any CRUD on fiscal_services, categories, sectors, or ministries. '
    'Does NOT include embedding, search_vector, or JSONB blobs.';


-- ============================================================================
-- Helper function to refresh the materialized view
-- Call after any CRUD operation on fiscal_services
-- ============================================================================

CREATE OR REPLACE FUNCTION refresh_fiscal_services_catalog()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_fiscal_services_catalog;
END;
$$ LANGUAGE plpgsql;

COMMIT;
