-- ============================================================================
-- Migration 107: Add GIN index on entities.workflow_codes
-- ============================================================================
-- The @> JSONB containment operator used in resolve_workflow_sites()
-- benefits from a GIN index. Without it, PostgreSQL performs a sequential
-- scan on the entities table for every site resolution call.
--
-- Also adds a CHECK constraint to prevent slot_duration_minutes = 0
-- in appointment_slot_configs (prevents division by zero in
-- get_available_slots_v3).
--
-- Date: 2026-02-17
-- ============================================================================

-- GIN index for JSONB containment queries on entities.workflow_codes
CREATE INDEX IF NOT EXISTS idx_entities_workflow_codes_gin
    ON entities USING GIN (workflow_codes);

-- Guard against division by zero in get_available_slots_v3
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chk_slot_duration_positive'
    ) THEN
        ALTER TABLE appointment_slot_configs
            ADD CONSTRAINT chk_slot_duration_positive
            CHECK (slot_duration_minutes > 0);
    END IF;
END $$;
