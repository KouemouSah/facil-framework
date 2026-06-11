-- ============================================================================
-- Migration 047: RBAC Phase 1 - Entities Hierarchy & Agent Profiles
-- ============================================================================
-- This migration:
-- 1. Extends entities table with ministry_id, parent_entity_id, entity_type
-- 2. Creates agent_profiles table (separates agent config from users)
-- 3. Adds agent_profile_id to agent_workloads
--
-- Key Design Decisions:
-- - entity_type: 'entity' (independent or ministry-linked) or 'department' (must have parent)
-- - Entities CAN be independent (ministry_id NULL) or linked to a ministry
-- - Departments MUST have a parent (either entity OR ministry)
-- - agent_profiles replaces ministry_agents for cleaner separation
-- ============================================================================

-- ============================================================================
-- PART 1: ENTITY TYPE ENUM
-- ============================================================================

-- Create enum for entity types
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'entity_type_enum') THEN
        CREATE TYPE entity_type_enum AS ENUM ('entity', 'department');
    END IF;
END $$;

-- ============================================================================
-- PART 2: EXTEND ENTITIES TABLE
-- ============================================================================

-- Add ministry_id column (nullable - entities can be independent)
ALTER TABLE entities
ADD COLUMN IF NOT EXISTS ministry_id INTEGER REFERENCES ministries(id) ON DELETE SET NULL;

-- Add parent_entity_id for department hierarchy
ALTER TABLE entities
ADD COLUMN IF NOT EXISTS parent_entity_id UUID REFERENCES entities(id) ON DELETE CASCADE;

-- Add entity_type column with default 'entity' for existing records
ALTER TABLE entities
ADD COLUMN IF NOT EXISTS entity_type entity_type_enum NOT NULL DEFAULT 'entity';

-- Create indexes for the new columns
CREATE INDEX IF NOT EXISTS idx_entities_ministry_id ON entities(ministry_id);
CREATE INDEX IF NOT EXISTS idx_entities_parent_entity_id ON entities(parent_entity_id);
CREATE INDEX IF NOT EXISTS idx_entities_entity_type ON entities(entity_type);

-- Add comment explaining the relationship logic
COMMENT ON COLUMN entities.ministry_id IS 'Optional ministry link. Entities can be independent (NULL) or linked to a ministry.';
COMMENT ON COLUMN entities.parent_entity_id IS 'For departments: the parent entity. NULL for top-level entities.';
COMMENT ON COLUMN entities.entity_type IS 'entity = top-level (can be independent or ministry-linked), department = must have parent';

-- ============================================================================
-- PART 3: VALIDATION CONSTRAINT FOR DEPARTMENTS
-- ============================================================================

-- Departments MUST have either a parent_entity_id OR a ministry_id
-- This constraint only applies to type='department'
-- Note: Using a function for complex validation

CREATE OR REPLACE FUNCTION check_department_parent()
RETURNS TRIGGER AS $$
BEGIN
    -- Only validate departments
    IF NEW.entity_type = 'department' THEN
        -- Departments must have at least one parent (entity OR ministry)
        IF NEW.parent_entity_id IS NULL AND NEW.ministry_id IS NULL THEN
            RAISE EXCEPTION 'Departments must have a parent_entity_id OR ministry_id';
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger if not exists
DROP TRIGGER IF EXISTS trg_check_department_parent ON entities;
CREATE TRIGGER trg_check_department_parent
    BEFORE INSERT OR UPDATE ON entities
    FOR EACH ROW
    EXECUTE FUNCTION check_department_parent();

-- ============================================================================
-- PART 4: AGENT PROFILES TABLE
-- ============================================================================

-- Create agent_profiles table to separate agent configuration from users
CREATE TABLE IF NOT EXISTS agent_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Core Identity
    user_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,

    -- Agent Type (replaces user_role_enum check for agent types)
    agent_type VARCHAR(30) NOT NULL CHECK (agent_type IN ('dgi_agent', 'ministry_agent', 'supervisor', 'treasury_agent')),

    -- Entity Assignment (which entity/department the agent belongs to)
    entity_id UUID REFERENCES entities(id) ON DELETE SET NULL,

    -- Legacy ministry_id for backward compatibility during transition
    ministry_id INTEGER REFERENCES ministries(id) ON DELETE SET NULL,

    -- Agent Role within their scope
    agent_role VARCHAR(50) NOT NULL DEFAULT 'validator',

    -- Approval Limits
    can_approve_unlimited BOOLEAN DEFAULT FALSE,
    max_approval_amount NUMERIC,

    -- Capabilities
    can_escalate BOOLEAN DEFAULT TRUE,
    can_assign_tasks BOOLEAN DEFAULT FALSE,
    can_reassign BOOLEAN DEFAULT FALSE,

    -- Specializations (JSONB array of declaration_types or workflow_codes)
    specializations JSONB DEFAULT '[]'::jsonb,

    -- Working Schedule
    working_hours_start TIME DEFAULT '08:00:00',
    working_hours_end TIME DEFAULT '17:00:00',
    working_days INTEGER[] DEFAULT ARRAY[1, 2, 3, 4, 5],

    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    is_backup_agent BOOLEAN DEFAULT FALSE,
    backup_for_profile_id UUID REFERENCES agent_profiles(id) ON DELETE SET NULL,

    -- Audit
    assigned_at TIMESTAMPTZ DEFAULT NOW(),
    assigned_by UUID REFERENCES users(id) ON DELETE SET NULL,
    deactivated_at TIMESTAMPTZ,
    deactivated_by UUID REFERENCES users(id) ON DELETE SET NULL,
    deactivation_reason TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for agent_profiles
CREATE INDEX IF NOT EXISTS idx_agent_profiles_user_id ON agent_profiles(user_id);
CREATE INDEX IF NOT EXISTS idx_agent_profiles_entity_id ON agent_profiles(entity_id);
CREATE INDEX IF NOT EXISTS idx_agent_profiles_ministry_id ON agent_profiles(ministry_id);
CREATE INDEX IF NOT EXISTS idx_agent_profiles_agent_type ON agent_profiles(agent_type);
CREATE INDEX IF NOT EXISTS idx_agent_profiles_is_active ON agent_profiles(is_active) WHERE is_active = TRUE;

-- Comments
COMMENT ON TABLE agent_profiles IS 'Agent configuration profiles - separates agent data from users table';
COMMENT ON COLUMN agent_profiles.entity_id IS 'The entity/department this agent belongs to';
COMMENT ON COLUMN agent_profiles.ministry_id IS 'Legacy: direct ministry assignment (prefer entity_id going forward)';
COMMENT ON COLUMN agent_profiles.specializations IS 'JSONB array of declaration_type_enum values or workflow_codes';

-- ============================================================================
-- PART 5: EXTEND AGENT_WORKLOADS WITH AGENT_PROFILE_ID
-- ============================================================================

-- Add agent_profile_id column (allows transition period where both agent_id and agent_profile_id work)
ALTER TABLE agent_workloads
ADD COLUMN IF NOT EXISTS agent_profile_id UUID REFERENCES agent_profiles(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_agent_workloads_profile_id ON agent_workloads(agent_profile_id);

COMMENT ON COLUMN agent_workloads.agent_profile_id IS 'New: reference to agent_profiles. Transition period: both agent_id (users) and agent_profile_id can be used.';

-- ============================================================================
-- PART 6: MIGRATION HELPER VIEW
-- ============================================================================

-- View to help migrate data from ministry_agents to agent_profiles
CREATE OR REPLACE VIEW vw_ministry_agents_migration AS
SELECT
    ma.id as ministry_agent_id,
    ma.user_id,
    u.role as user_role,
    ma.ministry_id,
    m.ministry_code,
    m.name_es as ministry_name,
    ma.agent_role,
    ma.can_approve_unlimited,
    ma.max_approval_amount,
    ma.can_escalate,
    ma.can_assign_tasks,
    ma.is_active,
    ma.is_backup_agent,
    ma.working_hours_start,
    ma.working_hours_end,
    ma.working_days,
    ma.assigned_at,
    ma.assigned_by,
    -- Check if already migrated to agent_profiles
    CASE WHEN ap.id IS NOT NULL THEN TRUE ELSE FALSE END as already_migrated,
    ap.id as agent_profile_id
FROM ministry_agents ma
JOIN users u ON ma.user_id = u.id
JOIN ministries m ON ma.ministry_id = m.id
LEFT JOIN agent_profiles ap ON ma.user_id = ap.user_id;

COMMENT ON VIEW vw_ministry_agents_migration IS 'Helper view to track migration from ministry_agents to agent_profiles';

-- ============================================================================
-- PART 7: UPDATED_AT TRIGGER FOR AGENT_PROFILES
-- ============================================================================

-- Reuse existing update_updated_at function if exists, or create it
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_agent_profiles_updated_at ON agent_profiles;
CREATE TRIGGER trg_agent_profiles_updated_at
    BEFORE UPDATE ON agent_profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- END OF MIGRATION 047
-- ============================================================================
