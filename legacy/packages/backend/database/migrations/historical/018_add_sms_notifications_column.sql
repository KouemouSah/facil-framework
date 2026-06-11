-- Migration: Add sms_notifications column to users table
-- Date: 2025-12-21
-- Description: Add SMS notification preference for users

-- =============================================================================
-- ADD SMS NOTIFICATIONS COLUMN
-- =============================================================================

ALTER TABLE users
ADD COLUMN IF NOT EXISTS sms_notifications BOOLEAN DEFAULT false;

-- Add comment for documentation
COMMENT ON COLUMN users.sms_notifications IS 'User preference for receiving SMS notifications';

-- =============================================================================
-- UPDATE EXISTING USERS - Default to false (opt-in)
-- =============================================================================

UPDATE users
SET sms_notifications = false
WHERE sms_notifications IS NULL;
