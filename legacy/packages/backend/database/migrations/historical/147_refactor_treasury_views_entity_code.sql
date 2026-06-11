-- ============================================================================
-- MIGRATION 147: Refactor treasury views to use entity_code instead of ministry_id
-- Date: 2026-03-01
-- Context: Migration 146 added entity_code to service_payments. Now we need to
--          update the materialized view mv_treasury_daily_kpis and its 4 dependent
--          views to use entity_code as the primary organizational dimension.
--          ministry_id is kept as a secondary dimension derived from entities.
-- ============================================================================

BEGIN;

-- ============================================================================
-- Step 1: Drop dependent views (they reference the matview)
-- ============================================================================
DROP VIEW IF EXISTS v_kpi_summary CASCADE;
DROP VIEW IF EXISTS v_top_payment_methods CASCADE;
DROP VIEW IF EXISTS v_top_ministries CASCADE;
DROP VIEW IF EXISTS v_top_workflows CASCADE;

-- ============================================================================
-- Step 2: Drop the old materialized view and its indexes
-- ============================================================================
DROP MATERIALIZED VIEW IF EXISTS mv_treasury_daily_kpis CASCADE;

-- ============================================================================
-- Step 3: Recreate materialized view with entity_code as primary dimension
-- ============================================================================
CREATE MATERIALIZED VIEW mv_treasury_daily_kpis AS
SELECT
    DATE(sp.created_at) AS report_date,
    sp.payment_method::text AS payment_method,
    -- NEW: entity_code as primary organizational dimension
    sp.entity_code,
    e.name AS entity_name,
    -- KEPT: ministry_id as secondary dimension (derived from entities)
    e.ministry_id,
    m.name_es AS ministry_name,
    -- Service dimensions
    sr.workflow_code AS service_code,
    COALESCE(fs.name_es, sr.workflow_code) AS service_name,
    sr.workflow_code,
    sr.solicitud_type,
    -- Counts
    COUNT(*) AS payment_count,
    COUNT(*) FILTER (WHERE sp.workflow_status = 'completed') AS completed_count,
    COUNT(*) FILTER (WHERE sp.workflow_status IN ('rejected_by_agent', 'cancelled_by_agent')) AS rejected_count,
    COUNT(*) FILTER (WHERE sp.workflow_status = 'cancelled_by_user') AS cancelled_by_user_count,
    -- Amounts (completed only)
    SUM(sp.total_amount) FILTER (WHERE sp.workflow_status = 'completed') AS total_amount,
    AVG(sp.total_amount) FILTER (WHERE sp.workflow_status = 'completed') AS avg_amount,
    MIN(sp.total_amount) FILTER (WHERE sp.workflow_status = 'completed') AS min_amount,
    MAX(sp.total_amount) FILTER (WHERE sp.workflow_status = 'completed') AS max_amount,
    -- Processing time
    AVG(
        EXTRACT(EPOCH FROM (COALESCE(sp.validated_at, sp.paid_at, NOW()) - sp.created_at)) / 60
    ) FILTER (WHERE sp.workflow_status IN ('completed', 'approved_by_agent') AND sp.validated_at IS NOT NULL)
    AS avg_processing_minutes,
    -- SLA metrics
    COUNT(*) FILTER (WHERE sp.sla_escalated = true) AS sla_breached_count,
    COUNT(*) FILTER (WHERE sp.sla_warning_sent = true) AS sla_warning_count
FROM service_payments sp
LEFT JOIN entities e ON e.code = sp.entity_code
LEFT JOIN ministries m ON m.id = e.ministry_id
LEFT JOIN service_requests sr ON sr.id = sp.service_request_id
LEFT JOIN fiscal_services fs ON fs.id = sr.fiscal_service_id
WHERE sp.created_at >= CURRENT_DATE - INTERVAL '365 days'
GROUP BY
    DATE(sp.created_at),
    sp.payment_method,
    sp.entity_code,
    e.name,
    e.ministry_id,
    m.name_es,
    sr.workflow_code,
    sr.solicitud_type,
    fs.name_es;

-- ============================================================================
-- Step 4: Recreate indexes on the materialized view
-- ============================================================================

-- Unique index (required for REFRESH CONCURRENTLY)
CREATE UNIQUE INDEX idx_mv_kpis_unique ON mv_treasury_daily_kpis (
    report_date,
    payment_method,
    COALESCE(entity_code, ''),
    COALESCE(service_code, ''),
    COALESCE(workflow_code, ''),
    COALESCE(solicitud_type, '')
);

-- Date index (hot path: period filtering)
CREATE INDEX idx_mv_kpis_date ON mv_treasury_daily_kpis (report_date DESC);

-- Payment method index
CREATE INDEX idx_mv_kpis_method ON mv_treasury_daily_kpis (payment_method);

-- Entity index (replaces ministry index)
CREATE INDEX idx_mv_kpis_entity ON mv_treasury_daily_kpis (entity_code);

-- Workflow index
CREATE INDEX idx_mv_kpis_workflow ON mv_treasury_daily_kpis (workflow_code)
    WHERE workflow_code IS NOT NULL;

-- ============================================================================
-- Step 5: Recreate dependent views
-- ============================================================================

-- v_kpi_summary: unchanged logic, reads from matview
CREATE OR REPLACE VIEW v_kpi_summary AS
SELECT 'today' AS period,
    SUM(total_amount) AS total_collected,
    SUM(completed_count) AS total_transactions,
    AVG(avg_amount) AS avg_transaction,
    SUM(sla_breached_count) AS sla_breaches
FROM mv_treasury_daily_kpis
WHERE report_date = CURRENT_DATE
UNION ALL
SELECT 'week',
    SUM(total_amount), SUM(completed_count), AVG(avg_amount), SUM(sla_breached_count)
FROM mv_treasury_daily_kpis
WHERE report_date >= date_trunc('week', CURRENT_DATE)
UNION ALL
SELECT 'month',
    SUM(total_amount), SUM(completed_count), AVG(avg_amount), SUM(sla_breached_count)
FROM mv_treasury_daily_kpis
WHERE report_date >= date_trunc('month', CURRENT_DATE)
UNION ALL
SELECT 'year',
    SUM(total_amount), SUM(completed_count), AVG(avg_amount), SUM(sla_breached_count)
FROM mv_treasury_daily_kpis
WHERE report_date >= date_trunc('year', CURRENT_DATE);

-- v_top_entities: replaces v_top_ministries, groups by entity_code
CREATE OR REPLACE VIEW v_top_entities AS
SELECT
    entity_code,
    entity_name,
    SUM(completed_count) AS transaction_count,
    SUM(total_amount) AS total_amount
FROM mv_treasury_daily_kpis
WHERE report_date >= date_trunc('month', CURRENT_DATE)
  AND entity_code IS NOT NULL
GROUP BY entity_code, entity_name
ORDER BY total_amount DESC
LIMIT 10;

-- v_top_payment_methods: unchanged logic
CREATE OR REPLACE VIEW v_top_payment_methods AS
SELECT
    payment_method,
    SUM(completed_count) AS transaction_count,
    SUM(total_amount) AS total_amount,
    ROUND(
        SUM(total_amount) / NULLIF(SUM(SUM(total_amount)) OVER(), 0) * 100, 2
    ) AS percentage
FROM mv_treasury_daily_kpis
WHERE report_date >= date_trunc('month', CURRENT_DATE)
GROUP BY payment_method
ORDER BY total_amount DESC;

-- v_top_workflows: unchanged logic
CREATE OR REPLACE VIEW v_top_workflows AS
SELECT
    workflow_code,
    solicitud_type,
    SUM(completed_count) AS transaction_count,
    SUM(total_amount) AS total_amount,
    ROUND(
        SUM(total_amount) / NULLIF(SUM(SUM(total_amount)) OVER(), 0) * 100, 2
    ) AS percentage
FROM mv_treasury_daily_kpis
WHERE report_date >= date_trunc('month', CURRENT_DATE)
  AND workflow_code IS NOT NULL
GROUP BY workflow_code, solicitud_type
ORDER BY total_amount DESC
LIMIT 10;

-- ============================================================================
-- Step 6: Verify
-- ============================================================================
DO $$
DECLARE
    v_count INTEGER;
    v_entity_groups TEXT;
BEGIN
    SELECT COUNT(*) INTO v_count FROM mv_treasury_daily_kpis;

    SELECT string_agg(entity_code || ':' || cnt::text, ', ')
    INTO v_entity_groups
    FROM (
        SELECT entity_code, SUM(completed_count) AS cnt
        FROM mv_treasury_daily_kpis
        WHERE entity_code IS NOT NULL
        GROUP BY entity_code
        ORDER BY cnt DESC
    ) sub;

    RAISE NOTICE 'Migration 147: mv_treasury_daily_kpis has % rows', v_count;
    RAISE NOTICE 'Migration 147: entity groups = %', v_entity_groups;
    RAISE NOTICE 'Migration 147: v_top_ministries replaced by v_top_entities';
END $$;

COMMIT;
