-- ============================================================================
-- Migration 068: Drop Lock Columns from service_payments
-- ============================================================================
-- Date: 2025-01-23
-- Purpose: Complete removal of lock mechanism columns
--
-- Context:
--   Migration 067 deprecated the locked_by_agent workflow status.
--   With auto-assignment architecture, agents only see their assigned payments,
--   so the lock mechanism is completely obsolete.
--
-- Changes:
--   1. Drop views that depend on lock columns
--   2. Recreate v_pending_payment_validations view WITHOUT lock columns
--   3. Recreate v_service_request_payments view WITHOUT lock columns
--   4. Drop the lock index
--   5. Drop the lock-related columns from service_payments
--
-- Columns dropped:
--   - locked_by_agent_profile_id (UUID)
--   - locked_at (TIMESTAMPTZ)
--   - lock_expires_at (TIMESTAMPTZ)
--
-- Prerequisites: Migration 067 must be applied (all lock columns should be NULL)
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. SAFETY CHECK: Verify all lock columns are NULL
-- ============================================================================
DO $$
DECLARE
    locked_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO locked_count
    FROM service_payments
    WHERE locked_by_agent_profile_id IS NOT NULL
       OR locked_at IS NOT NULL
       OR lock_expires_at IS NOT NULL;

    IF locked_count > 0 THEN
        RAISE EXCEPTION 'Migration 068: Found % payments with non-NULL lock columns. Run migration 067 first.', locked_count;
    END IF;

    RAISE NOTICE 'Migration 068: Safety check passed - all lock columns are NULL';
END $$;

-- ============================================================================
-- 2. DROP ALL VIEWS that depend on lock columns
-- ============================================================================
DROP VIEW IF EXISTS v_pending_payment_validations CASCADE;
DROP VIEW IF EXISTS v_service_request_payments CASCADE;

-- ============================================================================
-- 3. RECREATE VIEW: v_pending_payment_validations (without lock columns)
-- ============================================================================

-- Recreate without lock-related columns and joins
-- Note: Using assigned_agent_profile_id (UUID) which references agent_profiles
CREATE OR REPLACE VIEW v_pending_payment_validations AS
SELECT
    sp.id AS payment_id,
    sp.payment_reference,
    sp.service_request_id,
    sr.reference AS request_reference,
    sr.workflow_code,
    sp.user_id,
    u.full_name AS user_name,
    u.email AS user_email,
    sp.payment_method,
    sp.total_amount,
    sp.currency,
    sp.workflow_status,
    sp.assigned_agent_profile_id,
    assigned_ap.user_id AS assigned_to_user_id,
    assigned_user.full_name AS assigned_to_name,
    sp.created_at,
    EXTRACT(EPOCH FROM (NOW() - sp.created_at)) / 3600 AS hours_waiting
FROM service_payments sp
LEFT JOIN service_requests sr ON sp.service_request_id = sr.id
LEFT JOIN users u ON sp.user_id = u.id
LEFT JOIN agent_profiles assigned_ap ON sp.assigned_agent_profile_id = assigned_ap.id
LEFT JOIN users assigned_user ON assigned_ap.user_id = assigned_user.id
WHERE sp.workflow_status = 'pending_agent_review'
  AND sp.requires_agent_validation = true
ORDER BY sp.created_at ASC;

COMMENT ON VIEW v_pending_payment_validations IS
    'View for Treasury agent dashboard showing payments awaiting validation. Lock columns removed in migration 068.';

-- ============================================================================
-- 4. RECREATE VIEW: v_service_request_payments (without lock columns)
-- ============================================================================
CREATE OR REPLACE VIEW v_service_request_payments AS
SELECT
    sp.id,
    sp.payment_reference,
    sp.service_request_id,
    sr.reference AS request_reference,
    sr.workflow_code,
    sr.solicitud_type,
    sp.user_id,
    u.email AS user_email,
    u.full_name AS user_name,
    sp.payment_method,
    sp.base_amount,
    sp.total_amount,
    sp.currency,
    sp.status,
    sp.workflow_status,
    sp.requires_agent_validation,
    sp.assigned_agent_profile_id,
    sp.validated_by_agent_profile_id,
    sp.validated_at,
    sp.validation_comment,
    sp.receipt_number,
    sp.receipt_url,
    sp.paid_at,
    sp.created_at,
    sp.updated_at
FROM service_payments sp
LEFT JOIN service_requests sr ON sp.service_request_id = sr.id
LEFT JOIN users u ON sp.user_id = u.id
WHERE sp.service_request_id IS NOT NULL;

COMMENT ON VIEW v_service_request_payments IS
    'View for service request payments. Lock columns removed in migration 068.';

-- ============================================================================
-- 5. DROP INDEX on lock column
-- ============================================================================
DROP INDEX IF EXISTS idx_service_payments_locked_profile;

-- ============================================================================
-- 6. DROP COLUMNS from service_payments
-- ============================================================================
ALTER TABLE service_payments
    DROP COLUMN IF EXISTS locked_by_agent_profile_id,
    DROP COLUMN IF EXISTS locked_at,
    DROP COLUMN IF EXISTS lock_expires_at;

-- ============================================================================
-- 7. Also drop legacy lock column if it exists
-- ============================================================================
-- locked_by_agent_id was the old INTEGER column (pre-migration 048)
ALTER TABLE service_payments
    DROP COLUMN IF EXISTS locked_by_agent_id;

-- ============================================================================
-- 8. VERIFICATION: Log completion
-- ============================================================================
DO $$
DECLARE
    col_exists BOOLEAN;
BEGIN
    -- Verify columns are dropped
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'service_payments'
          AND column_name IN ('locked_by_agent_profile_id', 'locked_at', 'lock_expires_at')
    ) INTO col_exists;

    IF col_exists THEN
        RAISE EXCEPTION 'Migration 068: Failed to drop lock columns!';
    END IF;

    RAISE NOTICE 'Migration 068: Complete - Lock columns dropped from service_payments';
    RAISE NOTICE 'Migration 068: View v_pending_payment_validations recreated without lock references';
END $$;

COMMIT;
