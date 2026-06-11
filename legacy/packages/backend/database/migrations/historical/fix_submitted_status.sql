-- ============================================================================
-- FIX: Reset incorrectly SUBMITTED service requests to DRAFT
-- ============================================================================
-- This migration corrects requests that were set to SUBMITTED prematurely
-- by the old _check_completion() logic that auto-submitted when all documents
-- were uploaded, without verifying that all wizard steps were completed.
--
-- Criteria for resetting to DRAFT:
-- 1. Status is SUBMITTED
-- 2. submitted_at is NULL (didn't go through proper submission flow)
-- 3. OR form_data is incomplete (missing required wizard fields)
-- ============================================================================

-- First, let's see what we're about to fix
DO $$
DECLARE
    affected_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO affected_count
    FROM service_requests
    WHERE status = 'SUBMITTED'
    AND (
        submitted_at IS NULL
        OR (
            -- Check if essential wizard fields are missing
            form_data->>'is_minor' IS NULL
            OR form_data->>'solicitud_type' IS NULL
        )
    );

    RAISE NOTICE 'Found % service requests to reset from SUBMITTED to DRAFT', affected_count;
END $$;

-- Reset status to DRAFT for requests that were incorrectly set to SUBMITTED
UPDATE service_requests
SET
    status = 'DRAFT',
    updated_at = NOW()
WHERE status = 'SUBMITTED'
AND (
    -- Condition 1: No submitted_at timestamp (didn't complete submission step)
    submitted_at IS NULL
    OR (
        -- Condition 2: Essential wizard fields are missing
        form_data->>'is_minor' IS NULL
        OR form_data->>'solicitud_type' IS NULL
    )
);

-- Log the fix in history table
INSERT INTO service_request_history (
    service_request_id,
    action,
    previous_status,
    new_status,
    performed_by,
    comment,
    performed_at
)
SELECT
    id,
    'status_correction',
    'SUBMITTED'::service_request_status_enum,
    'DRAFT'::service_request_status_enum,
    NULL,  -- System action
    'Auto-correction: Status reset to DRAFT because wizard steps were not completed',
    NOW()
FROM service_requests
WHERE status = 'DRAFT'
AND updated_at >= NOW() - INTERVAL '1 minute';  -- Recently updated by the above UPDATE

-- Verification
DO $$
DECLARE
    remaining_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO remaining_count
    FROM service_requests
    WHERE status = 'SUBMITTED'
    AND submitted_at IS NULL;

    RAISE NOTICE 'Remaining SUBMITTED requests without submitted_at: %', remaining_count;
END $$;
