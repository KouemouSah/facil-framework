-- Migration 067: Remove locked_by_agent workflow status
--
-- Purpose: Simplify payment validation workflow by removing the lock mechanism
-- With auto-assignment architecture, agents only see their assigned payments,
-- so there's no concurrent access conflict that would require locking.
--
-- Changes:
--   1. Convert all 'locked_by_agent' payments to 'pending_agent_review'
--   2. Clear lock-related columns for these payments
--   3. Add comment explaining deprecation
--
-- Rollback: Not needed - locked_by_agent was an intermediate state

BEGIN;

-- ============================================================================
-- 1. Log current state before migration
-- ============================================================================
DO $$
DECLARE
    locked_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO locked_count
    FROM service_payments
    WHERE workflow_status = 'locked_by_agent';

    RAISE NOTICE 'Migration 067: Found % payments with locked_by_agent status', locked_count;
END $$;

-- ============================================================================
-- 2. Convert locked_by_agent → pending_agent_review
-- ============================================================================
UPDATE service_payments
SET
    workflow_status = 'pending_agent_review',
    locked_by_agent_profile_id = NULL,
    locked_at = NULL,
    lock_expires_at = NULL,
    updated_at = NOW()
WHERE workflow_status = 'locked_by_agent';

-- ============================================================================
-- 3. Add comments to document deprecation
-- ============================================================================
COMMENT ON COLUMN service_payments.locked_by_agent_profile_id IS
    'DEPRECATED (Migration 067): Lock mechanism removed. Auto-assignment eliminates concurrent access. Column kept for historical data.';

COMMENT ON COLUMN service_payments.locked_at IS
    'DEPRECATED (Migration 067): Lock mechanism removed. Column kept for historical data.';

COMMENT ON COLUMN service_payments.lock_expires_at IS
    'DEPRECATED (Migration 067): Lock mechanism removed. Column kept for historical data.';

-- ============================================================================
-- 4. Log completion
-- ============================================================================
DO $$
DECLARE
    pending_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO pending_count
    FROM service_payments
    WHERE workflow_status = 'pending_agent_review';

    RAISE NOTICE 'Migration 067: Complete. % payments now in pending_agent_review status', pending_count;
END $$;

COMMIT;
