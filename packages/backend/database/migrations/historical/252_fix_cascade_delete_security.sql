-- Migration 252: Fix dangerous CASCADE DELETE on financial tables
-- P0 SECURITY: service_payments must NOT be deleted when service_request is deleted
-- This preserves financial audit trail and prevents data loss.
--
-- Changes:
-- 1. service_payments.service_request_id: CASCADE → SET NULL
-- 2. notification_log.user_id: CASCADE → SET NULL
-- 3. uploaded_files.user_id: CASCADE → SET NULL
--
-- Date: 2026-03-22

BEGIN;

-- ============================================================================
-- 1. service_payments.service_request_id: CASCADE → SET NULL
--    CRITICAL: Deleting a service_request must NOT delete its payment records
-- ============================================================================
ALTER TABLE service_payments
    DROP CONSTRAINT IF EXISTS service_payments_service_request_id_fkey;

ALTER TABLE service_payments
    ADD CONSTRAINT service_payments_service_request_id_fkey
    FOREIGN KEY (service_request_id)
    REFERENCES service_requests(id)
    ON DELETE SET NULL;

-- ============================================================================
-- 2. notification_log.user_id: CASCADE → SET NULL
--    Preserve notification history even if user is deactivated/deleted
-- ============================================================================
ALTER TABLE notification_log
    DROP CONSTRAINT IF EXISTS notification_log_user_id_fkey;

ALTER TABLE notification_log
    ADD CONSTRAINT notification_log_user_id_fkey
    FOREIGN KEY (user_id)
    REFERENCES users(id)
    ON DELETE SET NULL;

-- ============================================================================
-- 3. uploaded_files.user_id: CASCADE → SET NULL
--    Preserve file metadata for audit even if user is deleted
-- ============================================================================
ALTER TABLE uploaded_files
    DROP CONSTRAINT IF EXISTS uploaded_files_user_id_fkey;

ALTER TABLE uploaded_files
    ADD CONSTRAINT uploaded_files_user_id_fkey
    FOREIGN KEY (user_id)
    REFERENCES users(id)
    ON DELETE SET NULL;

COMMIT;
