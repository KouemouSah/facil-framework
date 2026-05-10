-- ============================================================================
-- Migration 095: Fix service_payments agent columns (INT → UUID rename)
-- ============================================================================
-- Problem:
--   Migration 049 was not executed. The table has BOTH:
--   - Old INT columns: assigned_agent_id, validated_by_agent_id, escalated_to_agent_id
--   - New UUID columns: assigned_agent_profile_id, validated_by_agent_profile_id, escalated_to_agent_profile_id
--   Code expects the short names to be UUID (post-rename), but they're still INT.
--
-- Database state verified 2026-02-10:
--   - All 3 INT columns have 0 non-null values (safe to drop)
--   - All 3 UUID columns have FK to agent_profiles.id
--   - No FK constraints on the INT columns
--
-- Fix (targeted, no other changes):
--   1. Drop the 3 empty INT columns
--   2. Rename the 3 UUID columns to short names
-- ============================================================================

BEGIN;

-- 1. Drop old empty INT columns
ALTER TABLE service_payments DROP COLUMN IF EXISTS assigned_agent_id;
ALTER TABLE service_payments DROP COLUMN IF EXISTS validated_by_agent_id;
ALTER TABLE service_payments DROP COLUMN IF EXISTS escalated_to_agent_id;

-- 2. Rename UUID columns to short names
ALTER TABLE service_payments RENAME COLUMN assigned_agent_profile_id TO assigned_agent_id;
ALTER TABLE service_payments RENAME COLUMN validated_by_agent_profile_id TO validated_by_agent_id;
ALTER TABLE service_payments RENAME COLUMN escalated_to_agent_profile_id TO escalated_to_agent_id;

-- 3. Update comments
COMMENT ON COLUMN service_payments.assigned_agent_id IS 'Agent profile assigned to process this payment (UUID → agent_profiles.id)';
COMMENT ON COLUMN service_payments.validated_by_agent_id IS 'Agent profile who validated this payment (UUID → agent_profiles.id)';
COMMENT ON COLUMN service_payments.escalated_to_agent_id IS 'Agent profile to whom this payment was escalated (UUID → agent_profiles.id)';

COMMIT;
