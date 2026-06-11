-- ============================================================================
-- MIGRATION 150: Drop dead index on agent_workloads.agent_id
-- Date: 2026-03-01
-- Context: agent_workloads.agent_id is 100% NULL (5/5 rows). The column
--          is deprecated in favor of agent_profile_id (UUID NOT NULL).
--          Drop the non-unique index on the dead column to save write overhead.
--          Keep the UNIQUE constraint (agent_workloads_agent_id_key) to avoid
--          breaking any ON CONFLICT (agent_id) in legacy methods.
-- ============================================================================

BEGIN;

-- Drop the non-unique index on the dead column
DROP INDEX IF EXISTS idx_agent_workloads_agent_id;

-- Verify
DO $$
DECLARE
    v_exists BOOLEAN;
BEGIN
    SELECT EXISTS(
        SELECT 1 FROM pg_indexes
        WHERE tablename = 'agent_workloads'
          AND indexname = 'idx_agent_workloads_agent_id'
    ) INTO v_exists;

    IF v_exists THEN
        RAISE EXCEPTION 'Migration 150: idx_agent_workloads_agent_id still exists';
    END IF;

    RAISE NOTICE 'Migration 150: Dead index idx_agent_workloads_agent_id dropped successfully';
END $$;

COMMIT;
