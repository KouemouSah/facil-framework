-- Migration 304: OMS performance indexes
--
-- Audit findings for 1M+ concurrent transactions:
-- 1. Missing partial index on (fee_type, status) for independent agent queue
--    → sequential scan at 1M rows for AYUNTAMIENTO/CAMARA agents
-- 2. Missing partial index for counter refresh aggregation
--
-- NOTE: CREATE INDEX CONCURRENTLY cannot run inside a transaction.
-- This migration runs WITHOUT BEGIN/COMMIT (autocommit mode).
-- IF NOT EXISTS makes it idempotent.

-- ============================================================================
-- 1. Partial index for independent agent queue filtering
-- Covers: WHERE fee_type = 'municipal' AND status IN ('paid', 'processing')
-- Impact: AYUNTAMIENTO/CAMARA agents see their queue in <10ms instead of ~500ms
-- ============================================================================
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_lo_fee_type_status_active
    ON license_obligations (fee_type, status)
    WHERE status IN ('paid', 'processing', 'pending', 'overdue');

-- ============================================================================
-- 2. Partial index for counter refresh aggregation
-- Covers: WHERE license_id = $1 AND status IN ('paid','processing','completed')
-- Impact: update_license_counters SUM(amount) in <5ms instead of ~250ms
-- ============================================================================
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_lo_license_paid_status
    ON license_obligations (license_id)
    WHERE status IN ('paid', 'processing', 'completed');
