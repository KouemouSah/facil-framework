-- Migration 276: Permission Audit Log Cleanup + Drop 1 Duplicate Index
-- Date: 2026-03-21
-- Author: Claude (Performance Optimizer)
--
-- PROBLEM: permission_audit_log has 300K rows (91 MB) — largest table in DB.
-- ROOT CAUSE: assign_permission() uses ON CONFLICT DO UPDATE which triggers
--   audit_role_permissions() trigger even when granted value is unchanged.
--   Every backend restart syncs ~1600 role-permissions → 1600 UPDATE audit entries.
--   Over ~4 months → 297K spurious UPDATE entries.
--
-- FIX (code side): Added WHERE...IS DISTINCT FROM to skip no-op updates (role_repository.py)
--
-- THIS MIGRATION:
-- 1. Archive old permission_audit_log entries (>90 days) to separate table
-- 2. Create cleanup function for periodic maintenance
-- 3. Drop 1 confirmed duplicate index (sessions)
--

BEGIN;

-- ============================================================================
-- 1. Archive permission_audit_log entries older than 90 days
-- ============================================================================

-- Create archive table (same structure, no triggers)
CREATE TABLE IF NOT EXISTS permission_audit_log_archive (
    LIKE permission_audit_log INCLUDING ALL
);

-- Move old entries to archive
INSERT INTO permission_audit_log_archive
SELECT * FROM permission_audit_log
WHERE changed_at < NOW() - INTERVAL '90 days';

DELETE FROM permission_audit_log
WHERE changed_at < NOW() - INTERVAL '90 days';

-- ============================================================================
-- 2. Create cleanup function for cron-based maintenance
-- ============================================================================

CREATE OR REPLACE FUNCTION cleanup_permission_audit_log(
    retention_days INTEGER DEFAULT 90
)
RETURNS TABLE(archived_count BIGINT, remaining_count BIGINT) AS $$
DECLARE
    v_archived BIGINT;
    v_remaining BIGINT;
BEGIN
    -- Archive old entries
    WITH moved AS (
        DELETE FROM permission_audit_log
        WHERE changed_at < NOW() - MAKE_INTERVAL(days => retention_days)
        RETURNING *
    )
    INSERT INTO permission_audit_log_archive
    SELECT * FROM moved;

    GET DIAGNOSTICS v_archived = ROW_COUNT;

    SELECT COUNT(*) INTO v_remaining FROM permission_audit_log;

    RETURN QUERY SELECT v_archived, v_remaining;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION cleanup_permission_audit_log IS
    'Archive permission audit entries older than N days. Called by cron job.';

-- ============================================================================
-- 3. Drop confirmed duplicate index
-- ============================================================================
-- idx_sessions_refresh_token (non-partial) is a strict duplicate of
-- idx_sessions_refresh_token_active (partial WHERE status='active')
-- Both have 0 scans. The partial index is strictly better at scale
-- (smaller, covers the only query pattern: WHERE refresh_token=$1 AND status='active')
-- The non-partial covers no additional query pattern.

DROP INDEX IF EXISTS idx_sessions_refresh_token;

-- ============================================================================
-- 4. ANALYZE updated tables for query planner
-- ============================================================================

ANALYZE permission_audit_log;
ANALYZE sessions;

COMMIT;
