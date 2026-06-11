-- ============================================================================
-- Migration 048: Complete Agent Architecture Migration (Optimized)
-- ============================================================================
-- This migration:
-- 1. Simplifies agent_type to 2 values: ministry_agent, entity_agent
-- 2. Adds is_supervisor boolean column for supervisor capability
-- 3. Adds constraint: agent must have ministry_id OR entity_id
-- 4. Replaces user_role_enum (removes old agent values, adds 'agent')
-- 5. Populates agent_profiles from ministry_agents
-- 6. Migrates FK references from ministry_agents to agent_profiles
-- 7. Creates validation triggers
--
-- Design Decisions:
-- - agent_type: WHERE the agent works (ministry vs independent entity)
-- - is_supervisor: CAN the agent supervise others (capability)
-- - agent_role: WHAT function they perform (validator, approver, etc.)
--
-- PREREQUISITE: Migration 047 must be run first
-- ============================================================================

-- ============================================================================
-- PART 1: SIMPLIFY AGENT_TYPE AND ADD IS_SUPERVISOR
-- ============================================================================
--
-- Before: agent_type IN ('dgi_agent', 'ministry_agent', 'supervisor', 'treasury_agent')
-- After:  agent_type IN ('ministry_agent', 'entity_agent')
--         + is_supervisor BOOLEAN
--
-- Mapping:
--   dgi_agent     → ministry_agent (ministry.code = 'DGI')
--   treasury_agent → ministry_agent (ministry.code = 'TESORO')
--   supervisor    → ministry_agent/entity_agent + is_supervisor = TRUE
-- ============================================================================

-- Add is_supervisor column
ALTER TABLE agent_profiles
ADD COLUMN IF NOT EXISTS is_supervisor BOOLEAN DEFAULT FALSE;

COMMENT ON COLUMN agent_profiles.is_supervisor IS 'TRUE if agent can supervise other agents. Supervisors must still belong to a ministry or entity.';

-- Create index for supervisor filtering
CREATE INDEX IF NOT EXISTS idx_agent_profiles_is_supervisor
ON agent_profiles(is_supervisor) WHERE is_supervisor = TRUE;

-- Update existing supervisor type to is_supervisor = TRUE before changing constraint
UPDATE agent_profiles
SET is_supervisor = TRUE
WHERE agent_type = 'supervisor';

-- Update dgi_agent and treasury_agent to ministry_agent
UPDATE agent_profiles
SET agent_type = 'ministry_agent'
WHERE agent_type IN ('dgi_agent', 'treasury_agent', 'supervisor');

-- Now update the CHECK constraint to allow only 2 values
ALTER TABLE agent_profiles DROP CONSTRAINT IF EXISTS agent_profiles_agent_type_check;
ALTER TABLE agent_profiles ADD CONSTRAINT agent_profiles_agent_type_check
    CHECK (agent_type IN ('ministry_agent', 'entity_agent'));

-- Add comments
COMMENT ON COLUMN agent_profiles.agent_type IS 'ministry_agent = works for a ministry (DGI, Treasury, etc.), entity_agent = works for an independent entity (CNEDOGE, ONRC, etc.)';

-- ============================================================================
-- PART 2: ADD CONSTRAINT - AGENT MUST HAVE ASSIGNMENT
-- ============================================================================

-- An agent MUST be assigned to either a ministry OR an entity
ALTER TABLE agent_profiles DROP CONSTRAINT IF EXISTS chk_agent_has_assignment;
ALTER TABLE agent_profiles ADD CONSTRAINT chk_agent_has_assignment
    CHECK (ministry_id IS NOT NULL OR entity_id IS NOT NULL);

-- ============================================================================
-- PART 3: VALIDATION TRIGGER FOR AGENT ASSIGNMENT COHERENCE
-- ============================================================================

-- Ensures:
-- 1. If entity_id points to entity with ministry_id, agent.ministry_id must match
-- 2. entity_agent must have entity_id pointing to independent entity (no ministry)
-- 3. ministry_agent must have ministry_id (directly or via entity)

CREATE OR REPLACE FUNCTION validate_agent_assignment()
RETURNS TRIGGER AS $validate_agent$
DECLARE
    v_entity_ministry_id INTEGER;
    v_entity_has_ministry BOOLEAN;
BEGIN
    v_entity_has_ministry := FALSE;

    IF NEW.entity_id IS NOT NULL THEN
        SELECT e.ministry_id INTO v_entity_ministry_id
        FROM entities e
        WHERE e.id = NEW.entity_id;

        v_entity_has_ministry := v_entity_ministry_id IS NOT NULL;

        IF v_entity_has_ministry THEN
            IF NEW.ministry_id IS NULL THEN
                NEW.ministry_id := v_entity_ministry_id;
            ELSIF NEW.ministry_id != v_entity_ministry_id THEN
                RAISE EXCEPTION 'Agent ministry_id must match entity ministry_id';
            END IF;
        END IF;
    END IF;

    IF NEW.agent_type = 'entity_agent' THEN
        IF NEW.entity_id IS NULL THEN
            RAISE EXCEPTION 'entity_agent must have entity_id set';
        END IF;
        IF v_entity_has_ministry THEN
            RAISE EXCEPTION 'entity_agent cannot be assigned to entity with ministry';
        END IF;
    ELSIF NEW.agent_type = 'ministry_agent' THEN
        IF NEW.ministry_id IS NULL AND (NEW.entity_id IS NULL OR NOT v_entity_has_ministry) THEN
            RAISE EXCEPTION 'ministry_agent must be linked to a ministry';
        END IF;
    END IF;

    RETURN NEW;
END;
$validate_agent$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_validate_agent_assignment ON agent_profiles;
CREATE TRIGGER trg_validate_agent_assignment
    BEFORE INSERT OR UPDATE ON agent_profiles
    FOR EACH ROW
    EXECUTE FUNCTION validate_agent_assignment();

-- ============================================================================
-- PART 4: CREATE NEW USER_ROLE_ENUM (PostgreSQL requires this approach)
-- ============================================================================
-- PostgreSQL does NOT support removing values from enum.
-- The only way is: create new type → alter column → drop old → rename new

DO $create_enum$
BEGIN
    DROP TYPE IF EXISTS user_role_enum_new CASCADE;

    CREATE TYPE user_role_enum_new AS ENUM (
        'citizen',
        'business',
        'accountant',
        'admin',
        'agent',
        'funcionario'
    );
END $create_enum$;

-- ============================================================================
-- PART 5: POPULATE AGENT_PROFILES FROM MINISTRY_AGENTS
-- ============================================================================

INSERT INTO agent_profiles (
    user_id,
    agent_type,
    is_supervisor,
    ministry_id,
    agent_role,
    can_approve_unlimited,
    max_approval_amount,
    can_escalate,
    can_assign_tasks,
    specializations,
    working_hours_start,
    working_hours_end,
    working_days,
    is_active,
    is_backup_agent,
    assigned_at,
    assigned_by
)
SELECT
    ma.user_id,
    'ministry_agent'::VARCHAR(30),  -- All ministry_agents are ministry_agent type
    u.role::text = 'supervisor',     -- is_supervisor from old role
    ma.ministry_id,
    ma.agent_role,
    ma.can_approve_unlimited,
    ma.max_approval_amount,
    ma.can_escalate,
    ma.can_assign_tasks,
    COALESCE(u.specializations, '[]'::jsonb),
    ma.working_hours_start,
    ma.working_hours_end,
    ma.working_days,
    ma.is_active,
    ma.is_backup_agent,
    ma.assigned_at,
    ma.assigned_by
FROM ministry_agents ma
JOIN users u ON ma.user_id = u.id
WHERE NOT EXISTS (
    SELECT 1 FROM agent_profiles ap WHERE ap.user_id = ma.user_id
);

-- Also create profiles for agents not in ministry_agents table
INSERT INTO agent_profiles (
    user_id,
    agent_type,
    is_supervisor,
    agent_role,
    can_escalate,
    can_assign_tasks,
    specializations,
    is_active
)
SELECT
    u.id,
    'ministry_agent'::VARCHAR(30),
    u.role::text = 'supervisor',
    'validator',
    TRUE,
    u.role::text = 'supervisor',
    COALESCE(u.specializations, '[]'::jsonb),
    TRUE
FROM users u
WHERE u.role::text IN ('dgi_agent', 'ministry_agent', 'supervisor', 'treasury_agent')
AND NOT EXISTS (
    SELECT 1 FROM agent_profiles ap WHERE ap.user_id = u.id
);

-- ============================================================================
-- PART 6: CREATE MAPPING TABLE FOR FK MIGRATION
-- ============================================================================

DROP TABLE IF EXISTS _migration_agent_map;
CREATE TABLE _migration_agent_map AS
SELECT
    ma.id as ministry_agent_id,
    ap.id as agent_profile_id
FROM ministry_agents ma
JOIN agent_profiles ap ON ma.user_id = ap.user_id;

CREATE INDEX idx_migration_map_ma_id ON _migration_agent_map(ministry_agent_id);

-- ============================================================================
-- PART 7: ADD UUID FK COLUMNS TO AFFECTED TABLES
-- ============================================================================

-- service_payments
ALTER TABLE service_payments
ADD COLUMN IF NOT EXISTS assigned_agent_profile_id UUID REFERENCES agent_profiles(id) ON DELETE SET NULL;
ALTER TABLE service_payments
ADD COLUMN IF NOT EXISTS locked_by_agent_profile_id UUID REFERENCES agent_profiles(id) ON DELETE SET NULL;
ALTER TABLE service_payments
ADD COLUMN IF NOT EXISTS validated_by_agent_profile_id UUID REFERENCES agent_profiles(id) ON DELETE SET NULL;
ALTER TABLE service_payments
ADD COLUMN IF NOT EXISTS escalated_to_agent_profile_id UUID REFERENCES agent_profiles(id) ON DELETE SET NULL;

-- agent_performance_stats
ALTER TABLE agent_performance_stats
ADD COLUMN IF NOT EXISTS agent_profile_id UUID REFERENCES agent_profiles(id) ON DELETE CASCADE;

-- payment_lock_history
ALTER TABLE payment_lock_history
ADD COLUMN IF NOT EXISTS agent_profile_id UUID REFERENCES agent_profiles(id) ON DELETE SET NULL;

-- payment_validation_audit
ALTER TABLE payment_validation_audit
ADD COLUMN IF NOT EXISTS agent_profile_id UUID REFERENCES agent_profiles(id) ON DELETE SET NULL;

-- ============================================================================
-- PART 8: MIGRATE FK DATA
-- ============================================================================

-- service_payments
UPDATE service_payments sp
SET assigned_agent_profile_id = m.agent_profile_id
FROM _migration_agent_map m
WHERE sp.assigned_agent_id = m.ministry_agent_id AND sp.assigned_agent_profile_id IS NULL;

UPDATE service_payments sp
SET locked_by_agent_profile_id = m.agent_profile_id
FROM _migration_agent_map m
WHERE sp.locked_by_agent_id = m.ministry_agent_id AND sp.locked_by_agent_profile_id IS NULL;

UPDATE service_payments sp
SET validated_by_agent_profile_id = m.agent_profile_id
FROM _migration_agent_map m
WHERE sp.validated_by_agent_id = m.ministry_agent_id AND sp.validated_by_agent_profile_id IS NULL;

UPDATE service_payments sp
SET escalated_to_agent_profile_id = m.agent_profile_id
FROM _migration_agent_map m
WHERE sp.escalated_to_agent_id = m.ministry_agent_id AND sp.escalated_to_agent_profile_id IS NULL;

-- agent_performance_stats
UPDATE agent_performance_stats aps
SET agent_profile_id = m.agent_profile_id
FROM _migration_agent_map m
WHERE aps.agent_id = m.ministry_agent_id AND aps.agent_profile_id IS NULL;

-- payment_lock_history
UPDATE payment_lock_history plh
SET agent_profile_id = m.agent_profile_id
FROM _migration_agent_map m
WHERE plh.agent_id = m.ministry_agent_id AND plh.agent_profile_id IS NULL;

-- payment_validation_audit
UPDATE payment_validation_audit pva
SET agent_profile_id = m.agent_profile_id
FROM _migration_agent_map m
WHERE pva.agent_id = m.ministry_agent_id AND pva.agent_profile_id IS NULL;

-- agent_workloads
UPDATE agent_workloads aw
SET agent_profile_id = ap.id
FROM agent_profiles ap
WHERE aw.agent_id = ap.user_id AND aw.agent_profile_id IS NULL;

-- ============================================================================
-- PART 9: CREATE INDEXES ON NEW COLUMNS
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_service_payments_assigned_profile ON service_payments(assigned_agent_profile_id);
CREATE INDEX IF NOT EXISTS idx_service_payments_locked_profile ON service_payments(locked_by_agent_profile_id);
CREATE INDEX IF NOT EXISTS idx_service_payments_validated_profile ON service_payments(validated_by_agent_profile_id);
CREATE INDEX IF NOT EXISTS idx_service_payments_escalated_profile ON service_payments(escalated_to_agent_profile_id);
CREATE INDEX IF NOT EXISTS idx_agent_perf_stats_profile ON agent_performance_stats(agent_profile_id);
CREATE INDEX IF NOT EXISTS idx_payment_lock_history_profile ON payment_lock_history(agent_profile_id);
CREATE INDEX IF NOT EXISTS idx_payment_validation_audit_profile ON payment_validation_audit(agent_profile_id);

-- ============================================================================
-- PART 10: DROP VIEWS THAT DEPEND ON USERS.ROLE
-- ============================================================================

-- Drop ALL views that might depend on users.role or deprecated agent columns
-- These will be recreated with new schema after migration
DROP VIEW IF EXISTS v_available_agents CASCADE;
DROP VIEW IF EXISTS v_available_agents_by_ministry CASCADE;
DROP VIEW IF EXISTS v_user_effective_permissions CASCADE;
DROP VIEW IF EXISTS v_overprivileged_users_detection CASCADE;
DROP VIEW IF EXISTS v_permission_grants_audit CASCADE;
DROP VIEW IF EXISTS v_permission_gaps_analysis CASCADE;
DROP VIEW IF EXISTS v_permission_usage_analytics CASCADE;
DROP VIEW IF EXISTS v_role_capabilities_summary CASCADE;
DROP VIEW IF EXISTS v_agents_workload_dashboard CASCADE;
DROP VIEW IF EXISTS v_agent_performance_rankings CASCADE;
DROP VIEW IF EXISTS v_agent_assignment_history CASCADE;
DROP VIEW IF EXISTS v_active_assignments CASCADE;
DROP VIEW IF EXISTS vw_ministry_agents_migration CASCADE;

-- ============================================================================
-- PART 11: CONVERT USERS.ROLE TO NEW ENUM TYPE
-- ============================================================================

ALTER TABLE users ALTER COLUMN role DROP DEFAULT;

ALTER TABLE users
ALTER COLUMN role TYPE user_role_enum_new
USING (
    CASE
        WHEN role::text IN ('dgi_agent', 'ministry_agent', 'supervisor', 'treasury_agent') THEN 'agent'::user_role_enum_new
        ELSE role::text::user_role_enum_new
    END
);

ALTER TABLE users ALTER COLUMN role SET DEFAULT 'citizen'::user_role_enum_new;

-- ============================================================================
-- PART 12: REPLACE OLD ENUM WITH NEW
-- ============================================================================

DROP TYPE IF EXISTS user_role_enum;
ALTER TYPE user_role_enum_new RENAME TO user_role_enum;

-- ============================================================================
-- PART 13: MARK DEPRECATED COLUMNS
-- ============================================================================

COMMENT ON COLUMN service_payments.assigned_agent_id IS 'DEPRECATED: Use assigned_agent_profile_id';
COMMENT ON COLUMN service_payments.locked_by_agent_id IS 'DEPRECATED: Use locked_by_agent_profile_id';
COMMENT ON COLUMN service_payments.validated_by_agent_id IS 'DEPRECATED: Use validated_by_agent_profile_id';
COMMENT ON COLUMN service_payments.escalated_to_agent_id IS 'DEPRECATED: Use escalated_to_agent_profile_id';
COMMENT ON COLUMN agent_performance_stats.agent_id IS 'DEPRECATED: Use agent_profile_id';
COMMENT ON COLUMN payment_lock_history.agent_id IS 'DEPRECATED: Use agent_profile_id';
COMMENT ON COLUMN payment_validation_audit.agent_id IS 'DEPRECATED: Use agent_profile_id';
COMMENT ON TABLE ministry_agents IS 'DEPRECATED: Use agent_profiles table';
COMMENT ON COLUMN users.supervisor_id IS 'DEPRECATED: Use agent_profiles.is_supervisor and backup_for_profile_id';
COMMENT ON COLUMN users.department_id IS 'DEPRECATED: Use agent_profiles.entity_id';
COMMENT ON COLUMN users.specializations IS 'DEPRECATED: Use agent_profiles.specializations';
COMMENT ON COLUMN users.max_concurrent_assignments IS 'DEPRECATED: Use agent_workloads.max_concurrent_assignments';

-- ============================================================================
-- PART 14: CREATE UNIFIED AGENT VIEW
-- ============================================================================

CREATE OR REPLACE VIEW vw_agents AS
SELECT
    u.id as user_id,
    u.email,
    u.full_name,
    u.first_name,
    u.last_name,
    u.phone_number,
    u.role as user_role,
    ap.id as agent_profile_id,
    ap.agent_type,
    ap.is_supervisor,
    ap.agent_role,
    ap.entity_id,
    e.code as entity_code,
    e.name as entity_name,
    e.ministry_id as entity_ministry_id,
    ap.ministry_id,
    m.ministry_code,
    m.name_es as ministry_name,
    -- Computed: specific agent category for filtering
    CASE
        WHEN m.ministry_code = 'DGI' THEN 'dgi'
        WHEN m.ministry_code = 'TESORO' THEN 'treasury'
        WHEN ap.agent_type = 'entity_agent' THEN 'entity'
        ELSE 'ministry'
    END as agent_category,
    ap.can_approve_unlimited,
    ap.max_approval_amount,
    ap.can_escalate,
    ap.can_assign_tasks,
    ap.can_reassign,
    ap.specializations,
    ap.working_hours_start,
    ap.working_hours_end,
    ap.working_days,
    ap.is_active as agent_is_active,
    ap.is_backup_agent,
    aw.id as workload_id,
    aw.current_assignments,
    aw.max_concurrent_assignments,
    aw.capacity_percentage,
    aw.workload_status,
    aw.availability,
    aw.last_assignment_at,
    aw.last_completion_at
FROM users u
JOIN agent_profiles ap ON u.id = ap.user_id
LEFT JOIN entities e ON ap.entity_id = e.id
LEFT JOIN ministries m ON ap.ministry_id = m.id
LEFT JOIN agent_workloads aw ON ap.id = aw.agent_profile_id;

COMMENT ON VIEW vw_agents IS 'Unified view of all agents with profiles, entities, ministries, workloads. Use agent_category for DGI/Treasury/Entity filtering.';

-- ============================================================================
-- PART 15: MIGRATION STATISTICS
-- ============================================================================

DO $stats$
DECLARE
    v_total_ministry_agents INTEGER;
    v_total_agent_profiles INTEGER;
    v_total_supervisors INTEGER;
    v_total_agent_users INTEGER;
    v_enum_values TEXT;
BEGIN
    SELECT COUNT(*) INTO v_total_ministry_agents FROM ministry_agents;
    SELECT COUNT(*) INTO v_total_agent_profiles FROM agent_profiles;
    SELECT COUNT(*) INTO v_total_supervisors FROM agent_profiles WHERE is_supervisor = TRUE;
    SELECT COUNT(*) INTO v_total_agent_users FROM users WHERE role = 'agent';

    SELECT string_agg(enumlabel, ', ' ORDER BY enumsortorder)
    INTO v_enum_values
    FROM pg_enum
    WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'user_role_enum');

    RAISE NOTICE 'Migration 048 Complete';
    RAISE NOTICE 'Ministry agents migrated: %', v_total_ministry_agents;
    RAISE NOTICE 'Agent profiles created: %', v_total_agent_profiles;
    RAISE NOTICE 'Supervisors: %', v_total_supervisors;
    RAISE NOTICE 'Users with agent role: %', v_total_agent_users;
    RAISE NOTICE 'user_role_enum values: %', v_enum_values;
END $stats$;

-- ============================================================================
-- PART 16: CLEANUP MIGRATION TABLE
-- ============================================================================

DROP TABLE IF EXISTS _migration_agent_map;

-- ============================================================================
-- END OF MIGRATION 048
-- ============================================================================
