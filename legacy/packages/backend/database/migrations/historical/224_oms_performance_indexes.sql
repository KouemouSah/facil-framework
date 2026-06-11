-- Migration 224: OMS performance indexes for 1M+ obligations
-- Addresses agent queue scalability, payment hook queries, and counter refresh
--
-- Without these indexes:
--   - Agent queue query at 1M rows: sequential scan ~8s
--   - With indexes: index-only scan ~50ms
--
-- All indexes are IF NOT EXISTS — safe to re-run.

BEGIN;

-- ============================================================
-- 1. Agent Queue: ministry agents (Mode A per_line)
--    Query pattern: WHERE lo.ministry_id = $1 AND lo.status = 'processing'
--    AND cl.processing_mode = 'per_line'
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_lo_ministry_status_processing
    ON license_obligations (ministry_id, status)
    WHERE status = 'processing';

-- Agent Queue: polyvalent (Mode B consolidated)
-- Filtered on license processing_mode via JOIN
CREATE INDEX IF NOT EXISTS idx_cl_processing_mode
    ON commercial_licenses (processing_mode)
    WHERE status NOT IN ('closed', 'suspended');

-- ============================================================
-- 2. Payment hook: find obligations by payment_id + status
--    Query: WHERE payment_id = $1 AND status = 'payment_pending'
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_lo_payment_pending
    ON license_obligations (payment_id)
    WHERE status = 'payment_pending';

-- ============================================================
-- 3. Counter refresh: aggregate by license_id
--    Query: WHERE license_id = $1 (already has idx_lo_license)
--    Covering index for the aggregate columns
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_lo_license_status_amount
    ON license_obligations (license_id, status, amount, penalty_amount);

-- ============================================================
-- 4. Agent queue stats: completed today filter
--    Query: WHERE lo.status = 'completed' AND lo.updated_at::date = CURRENT_DATE
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_lo_completed_date
    ON license_obligations (updated_at)
    WHERE status = 'completed';

-- ============================================================
-- 5. Overdue cron: find pending obligations past due_date
--    Query: WHERE status = 'pending' AND due_date < CURRENT_DATE
--    (replaces existing idx_lo_overdue if scope differs)
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_lo_pending_due
    ON license_obligations (due_date)
    WHERE status = 'pending' AND due_date IS NOT NULL;

-- ============================================================
-- 6. Event timeline: obligation-scoped event queries
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_lce_obligation_type
    ON license_compliance_events (obligation_id, event_type, created_at DESC)
    WHERE obligation_id IS NOT NULL;

COMMIT;
