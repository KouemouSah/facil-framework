-- ============================================================================
-- Migration 041: Drop fiscal_service_code from service_payments
-- ============================================================================
-- Purpose: Remove unused column. All payments now go through service_requests,
-- so fiscal_service_code is redundant. The workflow info is available via
-- JOIN to service_requests.workflow_code.
--
-- Current state (from schema):
--   fiscal_service_code: varchar(10) NOT NULL, FK to fiscal_services.service_code
--   service_request_id: uuid NULLABLE, FK to service_requests.id
--   CHECK constraint: chk_payment_target_xor (XOR logic)
--
-- Dependencies to handle:
--   1. mv_treasury_daily_kpis (materialized view) - uses sp.fiscal_service_code
--   2. agent_payments_dashboard (materialized view) - uses fiscal_service_code
--   3. v_kpi_summary, v_top_payment_methods, v_top_ministries, v_top_workflows
--      (regular views depending on mv_treasury_daily_kpis)
--   4. chk_payment_target_xor (CHECK constraint)
--   5. FK constraint: service_payments_fiscal_service_code_fkey
-- ============================================================================

BEGIN;

-- ============================================================================
-- STEP 1: Drop all dependent views (CASCADE would do this, but explicit is safer)
-- ============================================================================

-- Drop regular views that depend on mv_treasury_daily_kpis
DROP VIEW IF EXISTS v_kpi_summary CASCADE;
DROP VIEW IF EXISTS v_top_payment_methods CASCADE;
DROP VIEW IF EXISTS v_top_ministries CASCADE;
DROP VIEW IF EXISTS v_top_workflows CASCADE;

-- Drop materialized views that use fiscal_service_code
DROP MATERIALIZED VIEW IF EXISTS mv_treasury_daily_kpis CASCADE;
DROP MATERIALIZED VIEW IF EXISTS agent_payments_dashboard CASCADE;

-- ============================================================================
-- STEP 2: Drop constraints
-- ============================================================================

-- Drop XOR check constraint
ALTER TABLE service_payments
DROP CONSTRAINT IF EXISTS chk_payment_target_xor;

-- Drop FK constraint to fiscal_services
ALTER TABLE service_payments
DROP CONSTRAINT IF EXISTS service_payments_fiscal_service_code_fkey;

-- ============================================================================
-- STEP 3: Drop index if exists
-- ============================================================================

DROP INDEX IF EXISTS idx_service_payments_service_code;
DROP INDEX IF EXISTS idx_service_payments_fiscal_service_code;

-- ============================================================================
-- STEP 4: Drop the column
-- ============================================================================

ALTER TABLE service_payments
DROP COLUMN IF EXISTS fiscal_service_code;

-- ============================================================================
-- STEP 5: Add constraint for service_request_id (required for new payments)
-- ============================================================================

-- For new records, service_request_id should be set
-- Legacy records (before 2026-01-11) may have NULL for backwards compatibility
ALTER TABLE service_payments
ADD CONSTRAINT chk_service_request_required
CHECK (
    service_request_id IS NOT NULL
    OR created_at < '2026-01-11'::date
);

-- ============================================================================
-- STEP 6: Recreate mv_treasury_daily_kpis WITHOUT fiscal_service_code
-- ============================================================================

CREATE MATERIALIZED VIEW mv_treasury_daily_kpis AS
SELECT
    -- Temporal dimensions
    DATE(sp.created_at) as report_date,

    -- Payment dimensions
    sp.payment_method::text as payment_method,
    sp.ministry_id,
    m.name_es as ministry_name,

    -- Service dimensions (now only via service_requests)
    sr.workflow_code as service_code,
    COALESCE(fs.name_es, sr.workflow_code) as service_name,

    -- Service request dimensions
    sr.workflow_code as workflow_code,
    sr.solicitud_type as solicitud_type,

    -- Volume metrics
    COUNT(*) as payment_count,
    COUNT(*) FILTER (WHERE sp.workflow_status = 'completed') as completed_count,
    COUNT(*) FILTER (WHERE sp.workflow_status IN ('rejected_by_agent', 'cancelled_by_agent')) as rejected_count,
    COUNT(*) FILTER (WHERE sp.workflow_status = 'cancelled_by_user') as cancelled_by_user_count,

    -- Financial metrics
    SUM(sp.total_amount) FILTER (WHERE sp.workflow_status = 'completed') as total_amount,
    AVG(sp.total_amount) FILTER (WHERE sp.workflow_status = 'completed') as avg_amount,
    MIN(sp.total_amount) FILTER (WHERE sp.workflow_status = 'completed') as min_amount,
    MAX(sp.total_amount) FILTER (WHERE sp.workflow_status = 'completed') as max_amount,

    -- Time metrics (in minutes)
    AVG(
        EXTRACT(EPOCH FROM (
            COALESCE(sp.validated_at, sp.paid_at, NOW()) - sp.created_at
        )) / 60
    ) FILTER (
        WHERE sp.workflow_status IN ('completed', 'approved_by_agent')
          AND sp.validated_at IS NOT NULL
    ) as avg_processing_minutes,

    -- SLA metrics
    COUNT(*) FILTER (WHERE sp.sla_escalated = true) as sla_breached_count,
    COUNT(*) FILTER (WHERE sp.sla_warning_sent = true) as sla_warning_count

FROM service_payments sp
LEFT JOIN ministries m ON m.id = sp.ministry_id
LEFT JOIN service_requests sr ON sr.id = sp.service_request_id
LEFT JOIN fiscal_services fs ON fs.id = sr.fiscal_service_id
WHERE sp.created_at >= CURRENT_DATE - INTERVAL '365 days'
GROUP BY
    DATE(sp.created_at),
    sp.payment_method,
    sp.ministry_id,
    m.name_es,
    sr.workflow_code,
    sr.solicitud_type,
    fs.name_es;

-- ============================================================================
-- STEP 7: Recreate indexes on materialized view
-- ============================================================================

CREATE UNIQUE INDEX idx_mv_kpis_unique
    ON mv_treasury_daily_kpis(
        report_date,
        payment_method,
        COALESCE(ministry_id, 0),
        COALESCE(service_code, ''),
        COALESCE(workflow_code, ''),
        COALESCE(solicitud_type, '')
    );

CREATE INDEX idx_mv_kpis_date ON mv_treasury_daily_kpis(report_date DESC);
CREATE INDEX idx_mv_kpis_method ON mv_treasury_daily_kpis(payment_method);
CREATE INDEX idx_mv_kpis_ministry ON mv_treasury_daily_kpis(ministry_id);
CREATE INDEX idx_mv_kpis_workflow ON mv_treasury_daily_kpis(workflow_code) WHERE workflow_code IS NOT NULL;

COMMENT ON MATERIALIZED VIEW mv_treasury_daily_kpis IS
'Daily KPIs for Treasury dashboard.
Uses service_requests.workflow_code for service identification.
Refresh: REFRESH MATERIALIZED VIEW CONCURRENTLY mv_treasury_daily_kpis;';

-- ============================================================================
-- STEP 8: Recreate dependent views
-- ============================================================================

CREATE OR REPLACE VIEW v_kpi_summary AS
SELECT
    'today' as period,
    SUM(total_amount) as total_collected,
    SUM(completed_count) as total_transactions,
    AVG(avg_amount) as avg_transaction,
    SUM(sla_breached_count) as sla_breaches
FROM mv_treasury_daily_kpis
WHERE report_date = CURRENT_DATE

UNION ALL

SELECT
    'week' as period,
    SUM(total_amount),
    SUM(completed_count),
    AVG(avg_amount),
    SUM(sla_breached_count)
FROM mv_treasury_daily_kpis
WHERE report_date >= DATE_TRUNC('week', CURRENT_DATE)

UNION ALL

SELECT
    'month' as period,
    SUM(total_amount),
    SUM(completed_count),
    AVG(avg_amount),
    SUM(sla_breached_count)
FROM mv_treasury_daily_kpis
WHERE report_date >= DATE_TRUNC('month', CURRENT_DATE)

UNION ALL

SELECT
    'year' as period,
    SUM(total_amount),
    SUM(completed_count),
    AVG(avg_amount),
    SUM(sla_breached_count)
FROM mv_treasury_daily_kpis
WHERE report_date >= DATE_TRUNC('year', CURRENT_DATE);

CREATE OR REPLACE VIEW v_top_payment_methods AS
SELECT
    payment_method,
    SUM(completed_count) as transaction_count,
    SUM(total_amount) as total_amount,
    ROUND(
        SUM(total_amount)::numeric /
        NULLIF(SUM(SUM(total_amount)) OVER (), 0)::numeric * 100, 2
    ) as percentage
FROM mv_treasury_daily_kpis
WHERE report_date >= DATE_TRUNC('month', CURRENT_DATE)
GROUP BY payment_method
ORDER BY total_amount DESC;

CREATE OR REPLACE VIEW v_top_ministries AS
SELECT
    ministry_id,
    ministry_name,
    SUM(completed_count) as transaction_count,
    SUM(total_amount) as total_amount
FROM mv_treasury_daily_kpis
WHERE report_date >= DATE_TRUNC('month', CURRENT_DATE)
  AND ministry_id IS NOT NULL
GROUP BY ministry_id, ministry_name
ORDER BY total_amount DESC
LIMIT 10;

CREATE OR REPLACE VIEW v_top_workflows AS
SELECT
    workflow_code,
    solicitud_type,
    SUM(completed_count) as transaction_count,
    SUM(total_amount) as total_amount,
    ROUND(
        SUM(total_amount)::numeric /
        NULLIF(SUM(SUM(total_amount)) OVER (), 0)::numeric * 100, 2
    ) as percentage
FROM mv_treasury_daily_kpis
WHERE report_date >= DATE_TRUNC('month', CURRENT_DATE)
  AND workflow_code IS NOT NULL
GROUP BY workflow_code, solicitud_type
ORDER BY total_amount DESC
LIMIT 10;

-- ============================================================================
-- STEP 9: Refresh materialized view
-- ============================================================================

REFRESH MATERIALIZED VIEW mv_treasury_daily_kpis;

-- ============================================================================
-- STEP 10: Verification
-- ============================================================================

-- Verify column was dropped
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'service_payments'
        AND column_name = 'fiscal_service_code'
    ) THEN
        RAISE EXCEPTION 'fiscal_service_code column still exists!';
    END IF;
    RAISE NOTICE 'Migration 041 completed successfully: fiscal_service_code dropped from service_payments';
END $$;

COMMIT;
