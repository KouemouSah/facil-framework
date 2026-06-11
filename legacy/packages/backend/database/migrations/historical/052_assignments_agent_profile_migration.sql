-- Migration 052: Migrate assignments to use agent_profiles
-- Part of Phase 3: Agent Unification
--
-- Changes:
-- 1. Add agent_profile_id column to assignments (new FK to agent_profiles)
-- 2. Add assigned_by_profile_id column (supervisor who assigned)
-- 3. Add reassigned_to_profile_id column (new agent after reassignment)
-- 4. Migrate existing data from users.id to agent_profiles.id
-- 5. Mark old columns as deprecated (keep for backward compatibility)
--
-- Note: Old columns (agent_id, assigned_by, reassigned_to) are NOT dropped
-- to maintain backward compatibility during transition period.

BEGIN;

-- ============================================================================
-- STEP 1: Add new columns with FK to agent_profiles
-- ============================================================================

-- Add agent_profile_id (the agent assigned to this task)
ALTER TABLE assignments
ADD COLUMN IF NOT EXISTS agent_profile_id UUID;

COMMENT ON COLUMN assignments.agent_profile_id IS
    'NEW: Reference to agent_profiles. The agent assigned to process this task.';

-- Add assigned_by_profile_id (supervisor who made the assignment)
ALTER TABLE assignments
ADD COLUMN IF NOT EXISTS assigned_by_profile_id UUID;

COMMENT ON COLUMN assignments.assigned_by_profile_id IS
    'NEW: Reference to agent_profiles for the supervisor who assigned this task.';

-- Add reassigned_to_profile_id (new agent after reassignment)
ALTER TABLE assignments
ADD COLUMN IF NOT EXISTS reassigned_to_profile_id UUID;

COMMENT ON COLUMN assignments.reassigned_to_profile_id IS
    'NEW: Reference to agent_profiles for the agent after reassignment.';

-- ============================================================================
-- STEP 2: Add Foreign Key constraints
-- ============================================================================

-- FK for agent_profile_id
ALTER TABLE assignments
ADD CONSTRAINT fk_assignments_agent_profile
FOREIGN KEY (agent_profile_id) REFERENCES agent_profiles(id)
ON DELETE RESTRICT ON UPDATE NO ACTION;

-- FK for assigned_by_profile_id
ALTER TABLE assignments
ADD CONSTRAINT fk_assignments_assigned_by_profile
FOREIGN KEY (assigned_by_profile_id) REFERENCES agent_profiles(id)
ON DELETE SET NULL ON UPDATE NO ACTION;

-- FK for reassigned_to_profile_id
ALTER TABLE assignments
ADD CONSTRAINT fk_assignments_reassigned_to_profile
FOREIGN KEY (reassigned_to_profile_id) REFERENCES agent_profiles(id)
ON DELETE SET NULL ON UPDATE NO ACTION;

-- ============================================================================
-- STEP 3: Migrate existing data
-- ============================================================================

-- Migrate agent_id → agent_profile_id
-- Find the agent_profile for each user_id in agent_id
UPDATE assignments a
SET agent_profile_id = ap.id
FROM agent_profiles ap
WHERE a.agent_id = ap.user_id
  AND a.agent_profile_id IS NULL
  AND ap.is_active = true;

-- Log unmigrated records (agents without profiles)
DO $$
DECLARE
    unmigrated_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO unmigrated_count
    FROM assignments
    WHERE agent_profile_id IS NULL;

    IF unmigrated_count > 0 THEN
        RAISE NOTICE 'WARNING: % assignments could not be migrated (agent has no profile)', unmigrated_count;
    END IF;
END $$;

-- Migrate assigned_by → assigned_by_profile_id (only if assigner is an agent)
UPDATE assignments a
SET assigned_by_profile_id = ap.id
FROM agent_profiles ap
WHERE a.assigned_by = ap.user_id
  AND a.assigned_by_profile_id IS NULL
  AND ap.is_active = true;

-- Migrate reassigned_to → reassigned_to_profile_id
UPDATE assignments a
SET reassigned_to_profile_id = ap.id
FROM agent_profiles ap
WHERE a.reassigned_to = ap.user_id
  AND a.reassigned_to_profile_id IS NULL
  AND ap.is_active = true;

-- ============================================================================
-- STEP 4: Add indexes for new columns
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_assignments_agent_profile_id
ON assignments(agent_profile_id);

CREATE INDEX IF NOT EXISTS idx_assignments_assigned_by_profile_id
ON assignments(assigned_by_profile_id);

CREATE INDEX IF NOT EXISTS idx_assignments_reassigned_to_profile_id
ON assignments(reassigned_to_profile_id);

-- ============================================================================
-- STEP 5: Mark old columns as deprecated (via comments)
-- ============================================================================

COMMENT ON COLUMN assignments.agent_id IS
    'DEPRECATED: Use agent_profile_id instead. Kept for backward compatibility.';

COMMENT ON COLUMN assignments.assigned_by IS
    'DEPRECATED: Use assigned_by_profile_id for agent supervisors. Still valid for admin users.';

COMMENT ON COLUMN assignments.reassigned_to IS
    'DEPRECATED: Use reassigned_to_profile_id instead. Kept for backward compatibility.';

-- ============================================================================
-- STEP 6: Create view for easy querying with both old and new columns
-- ============================================================================

CREATE OR REPLACE VIEW v_assignments_with_profiles AS
SELECT
    a.*,
    -- Agent profile details
    ap.agent_type,
    ap.is_supervisor as agent_is_supervisor,
    ap.ministry_id as agent_ministry_id,
    ap.entity_id as agent_entity_id,
    u.full_name as agent_full_name,
    u.email as agent_email,
    -- Assigned by profile details
    abp.agent_type as assigned_by_agent_type,
    abp.is_supervisor as assigned_by_is_supervisor,
    abu.full_name as assigned_by_full_name,
    -- Ministry/Entity names
    m.name_es as agent_ministry_name,
    e.name as agent_entity_name
FROM assignments a
LEFT JOIN agent_profiles ap ON a.agent_profile_id = ap.id
LEFT JOIN users u ON ap.user_id = u.id
LEFT JOIN agent_profiles abp ON a.assigned_by_profile_id = abp.id
LEFT JOIN users abu ON abp.user_id = abu.id
LEFT JOIN ministries m ON ap.ministry_id = m.id
LEFT JOIN entities e ON ap.entity_id = e.id;

COMMENT ON VIEW v_assignments_with_profiles IS
    'Assignments with agent profile details for easy querying';

COMMIT;

-- ============================================================================
-- ROLLBACK SCRIPT (for reference)
-- ============================================================================
-- BEGIN;
-- DROP VIEW IF EXISTS v_assignments_with_profiles;
-- DROP INDEX IF EXISTS idx_assignments_reassigned_to_profile_id;
-- DROP INDEX IF EXISTS idx_assignments_assigned_by_profile_id;
-- DROP INDEX IF EXISTS idx_assignments_agent_profile_id;
-- ALTER TABLE assignments DROP CONSTRAINT IF EXISTS fk_assignments_reassigned_to_profile;
-- ALTER TABLE assignments DROP CONSTRAINT IF EXISTS fk_assignments_assigned_by_profile;
-- ALTER TABLE assignments DROP CONSTRAINT IF EXISTS fk_assignments_agent_profile;
-- ALTER TABLE assignments DROP COLUMN IF EXISTS reassigned_to_profile_id;
-- ALTER TABLE assignments DROP COLUMN IF EXISTS assigned_by_profile_id;
-- ALTER TABLE assignments DROP COLUMN IF EXISTS agent_profile_id;
-- COMMIT;
