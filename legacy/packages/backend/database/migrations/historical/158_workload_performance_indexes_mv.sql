-- ================================================================
-- Migration 158: Performance indexes + materialized view for workload dashboard
--
-- Audit: 7 queries in /treasury/stats/workload-dashboard degrade from
-- <2ms (10 rows) to 30-60s (1M+ rows) due to:
-- 1) No index on (agent_profile_id, action, created_at) for pva
-- 2) No index on (created_at, action) for date-range scans
-- 3) No index on service_payments.created_at
-- 4) Correlated subqueries in Q2 (fixed in Python code)
-- 5) No pre-aggregated daily stats for Q1/Q5/Q7
--
-- Expected improvement: all 7 queries drop to <500ms at 1M+ rows.
-- ================================================================

-- ================================================================
-- PRIORITY 1: Covers Q1, Q2, Q3, Q5, Q7 (5 of 7 queries)
-- Partial index: only approve/reject actions (95% of workload queries)
-- ================================================================
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pva_profile_action_created
ON payment_validation_audit (agent_profile_id, created_at DESC)
WHERE action IN ('approve', 'reject');

-- ================================================================
-- PRIORITY 2: Covers Q1, Q3, Q4, Q7 (date-range scans without agent filter)
-- ================================================================
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pva_created_action
ON payment_validation_audit (created_at, action)
WHERE action IN ('approve', 'reject');

-- ================================================================
-- PRIORITY 3: Covers Q4 volume_trend incoming subquery
-- service_payments has NO general created_at index
-- ================================================================
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sp_created_at
ON service_payments (created_at);

-- ================================================================
-- PRIORITY 4: Covers Q6 KPI queue subquery (3 pending statuses)
-- Existing idx_service_payments_pending_validation only covers
-- pending_agent_review, not submitted/auto_processing
-- ================================================================
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sp_queue_pending_status
ON service_payments (workflow_status, created_at)
WHERE workflow_status IN ('pending_agent_review', 'submitted', 'auto_processing');

-- ================================================================
-- MATERIALIZED VIEW: Pre-aggregated daily agent workload stats
-- Eliminates expensive GROUP BY + PERCENTILE_CONT on raw 1M+ rows.
-- Refreshed by CRON scheduler (every 15 min, already wired for
-- mv_treasury_daily_kpis and mv_reconciliation_stats).
-- ================================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_agent_daily_workload AS
SELECT
    pva.created_at::date AS report_date,
    pva.agent_profile_id,
    u.full_name AS agent_name,
    COUNT(*) FILTER (WHERE pva.action = 'approve') AS approved,
    COUNT(*) FILTER (WHERE pva.action = 'reject') AS rejected,
    COUNT(*) AS total_actions,
    AVG(pva.action_duration_seconds)
        FILTER (WHERE pva.action_duration_seconds IS NOT NULL) AS avg_duration_seconds,
    MIN(pva.action_duration_seconds)
        FILTER (WHERE pva.action_duration_seconds IS NOT NULL) AS min_duration_seconds,
    MAX(pva.action_duration_seconds)
        FILTER (WHERE pva.action_duration_seconds IS NOT NULL) AS max_duration_seconds,
    PERCENTILE_CONT(0.5) WITHIN GROUP (
        ORDER BY pva.action_duration_seconds
    ) FILTER (WHERE pva.action_duration_seconds IS NOT NULL) AS p50_duration_seconds
FROM payment_validation_audit pva
JOIN agent_profiles ap ON ap.id = pva.agent_profile_id
JOIN users u ON u.id = ap.user_id
WHERE pva.action IN ('approve', 'reject')
GROUP BY pva.created_at::date, pva.agent_profile_id, u.full_name
WITH NO DATA;

-- Unique index required for REFRESH CONCURRENTLY
CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_agent_daily_pk
ON mv_agent_daily_workload (report_date, agent_profile_id);

-- Covering indexes for common access patterns
CREATE INDEX IF NOT EXISTS idx_mv_agent_daily_date
ON mv_agent_daily_workload (report_date DESC);

CREATE INDEX IF NOT EXISTS idx_mv_agent_daily_agent
ON mv_agent_daily_workload (agent_profile_id, report_date DESC);

-- Initial population
REFRESH MATERIALIZED VIEW mv_agent_daily_workload;

-- ================================================================
COMMENT ON MATERIALIZED VIEW mv_agent_daily_workload IS
'Pre-aggregated daily agent workload stats for /treasury/stats/workload-dashboard.
Refreshed by CRON scheduler every 15 minutes (scheduler.py).
Covers Q1 (daily_velocity), Q5 (processing_times), Q7 (rankings).';
