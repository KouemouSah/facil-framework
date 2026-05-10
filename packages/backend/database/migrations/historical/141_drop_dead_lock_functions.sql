-- Migration 141: Drop dead SQL functions that reference removed columns
--
-- These 3 functions reference columns that were dropped by migrations 049/068:
--   - locked_by_agent_id (dropped)
--   - locked_by_agent_profile_id (dropped)
--   - locked_at (dropped)
--   - lock_expires_at (dropped)
-- They also reference the dropped table ministry_agents.
-- None are called from application code or triggers.

DROP FUNCTION IF EXISTS lock_payment_for_agent(UUID, INTEGER, INTEGER);
DROP FUNCTION IF EXISTS lock_payment_for_agent(UUID, UUID, INTEGER);
DROP FUNCTION IF EXISTS unlock_payment_by_agent(UUID, INTEGER, payment_workflow_status, TEXT, JSONB);
DROP FUNCTION IF EXISTS unlock_payment_by_agent(UUID, UUID, payment_workflow_status, TEXT, JSONB);
DROP FUNCTION IF EXISTS cleanup_expired_locks();
