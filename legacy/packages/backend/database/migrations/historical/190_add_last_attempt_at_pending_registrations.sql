-- Migration 190: Add last_attempt_at to pending_registrations
-- Purpose: Track timestamp of last verification attempt for security auditing
-- Required by: Phase 10 fix — atomic increment_attempts() uses last_attempt_at = NOW()
-- Date: 2026-03-09

ALTER TABLE pending_registrations
ADD COLUMN IF NOT EXISTS last_attempt_at TIMESTAMP WITH TIME ZONE;

COMMENT ON COLUMN pending_registrations.last_attempt_at IS 'Timestamp of last verification attempt (security audit)';
