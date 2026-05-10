-- Migration 055: Add metadata column to pending_registrations
-- Purpose: Store additional data for agent/admin invitations
-- Date: 2025-01-17
--
-- This allows pending_registrations to handle:
-- 1. Regular user registrations (metadata = {})
-- 2. Agent invitations (metadata = {registration_type: 'agent', agent_data: {...}, created_by: UUID})
-- 3. Admin invitations (metadata = {registration_type: 'admin', admin_data: {...}, created_by: UUID})

-- ============================================================================
-- ADD METADATA COLUMN
-- ============================================================================

ALTER TABLE pending_registrations
ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb;

-- Add comment for documentation
COMMENT ON COLUMN pending_registrations.metadata IS
'JSONB metadata for different registration types:
- registration_type: "user" | "agent" | "admin"
- For agents: agent_data (profile config), user_data (name, phone), created_by (admin UUID)
- For admins: admin_data, created_by (admin UUID)';

-- ============================================================================
-- ADD INDEX FOR QUERYING BY TYPE
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_pending_registrations_type
ON pending_registrations ((metadata->>'registration_type'));

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'pending_registrations'
        AND column_name = 'metadata'
    ) THEN
        RAISE NOTICE 'Migration 055: metadata column added successfully';
    ELSE
        RAISE EXCEPTION 'Migration 055: Failed to add metadata column';
    END IF;
END $$;
