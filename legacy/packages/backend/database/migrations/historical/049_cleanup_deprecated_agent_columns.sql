-- ============================================================================
-- Migration 049: Cleanup Deprecated Agent Columns and Tables
-- ============================================================================
-- WARNING: Only run this migration AFTER all application code has been updated
-- to use the new agent_profiles-based columns!
--
-- This migration:
-- 1. Drops deprecated INTEGER FK columns from service_payments
-- 2. Drops deprecated INTEGER FK columns from other tables
-- 3. Drops deprecated agent columns from users table
-- 4. Drops the ministry_agents table
-- 5. Updates agent_performance_stats PK to use agent_profile_id
--
-- PREREQUISITE: Migrations 047 and 048 must be run first
-- PREREQUISITE: All application code must use new *_agent_profile_id columns
-- ============================================================================

-- ============================================================================
-- SAFETY CHECK: Verify all data has been migrated
-- ============================================================================

DO $$
DECLARE
    v_unmigrated_sp INTEGER;
    v_unmigrated_aps INTEGER;
    v_unmigrated_plh INTEGER;
    v_unmigrated_pva INTEGER;
BEGIN
    -- Check service_payments
    SELECT COUNT(*) INTO v_unmigrated_sp
    FROM service_payments
    WHERE (assigned_agent_id IS NOT NULL AND assigned_agent_profile_id IS NULL)
       OR (locked_by_agent_id IS NOT NULL AND locked_by_agent_profile_id IS NULL)
       OR (validated_by_agent_id IS NOT NULL AND validated_by_agent_profile_id IS NULL)
       OR (escalated_to_agent_id IS NOT NULL AND escalated_to_agent_profile_id IS NULL);

    -- Check agent_performance_stats
    SELECT COUNT(*) INTO v_unmigrated_aps
    FROM agent_performance_stats
    WHERE agent_id IS NOT NULL AND agent_profile_id IS NULL;

    -- Check payment_lock_history
    SELECT COUNT(*) INTO v_unmigrated_plh
    FROM payment_lock_history
    WHERE agent_id IS NOT NULL AND agent_profile_id IS NULL;

    -- Check payment_validation_audit
    SELECT COUNT(*) INTO v_unmigrated_pva
    FROM payment_validation_audit
    WHERE agent_id IS NOT NULL AND agent_profile_id IS NULL;

    IF v_unmigrated_sp > 0 OR v_unmigrated_aps > 0 OR v_unmigrated_plh > 0 OR v_unmigrated_pva > 0 THEN
        RAISE EXCEPTION 'MIGRATION ABORTED: Unmigrated data found! SP: %, APS: %, PLH: %, PVA: %',
            v_unmigrated_sp, v_unmigrated_aps, v_unmigrated_plh, v_unmigrated_pva;
    END IF;

    RAISE NOTICE 'Safety check passed: All data has been migrated to new columns';
END $$;

-- ============================================================================
-- PART 1: DROP FK CONSTRAINTS ON OLD INTEGER COLUMNS
-- ============================================================================

-- service_payments
ALTER TABLE service_payments DROP CONSTRAINT IF EXISTS service_payments_assigned_agent_id_fkey;
ALTER TABLE service_payments DROP CONSTRAINT IF EXISTS service_payments_locked_by_agent_id_fkey;
ALTER TABLE service_payments DROP CONSTRAINT IF EXISTS service_payments_validated_by_agent_id_fkey;
ALTER TABLE service_payments DROP CONSTRAINT IF EXISTS service_payments_escalated_to_agent_id_fkey;

-- agent_performance_stats
ALTER TABLE agent_performance_stats DROP CONSTRAINT IF EXISTS agent_performance_stats_agent_id_fkey;

-- payment_lock_history
ALTER TABLE payment_lock_history DROP CONSTRAINT IF EXISTS payment_lock_history_agent_id_fkey;

-- payment_validation_audit
ALTER TABLE payment_validation_audit DROP CONSTRAINT IF EXISTS payment_validation_audit_agent_id_fkey;

-- ============================================================================
-- PART 2: DROP OLD INTEGER FK COLUMNS FROM SERVICE_PAYMENTS
-- ============================================================================

ALTER TABLE service_payments DROP COLUMN IF EXISTS assigned_agent_id;
ALTER TABLE service_payments DROP COLUMN IF EXISTS locked_by_agent_id;
ALTER TABLE service_payments DROP COLUMN IF EXISTS validated_by_agent_id;
ALTER TABLE service_payments DROP COLUMN IF EXISTS escalated_to_agent_id;

-- Rename new columns to cleaner names
ALTER TABLE service_payments RENAME COLUMN assigned_agent_profile_id TO assigned_agent_id;
ALTER TABLE service_payments RENAME COLUMN locked_by_agent_profile_id TO locked_by_agent_id;
ALTER TABLE service_payments RENAME COLUMN validated_by_agent_profile_id TO validated_by_agent_id;
ALTER TABLE service_payments RENAME COLUMN escalated_to_agent_profile_id TO escalated_to_agent_id;

-- Update comments
COMMENT ON COLUMN service_payments.assigned_agent_id IS 'Agent profile assigned to process this payment';
COMMENT ON COLUMN service_payments.locked_by_agent_id IS 'Agent profile currently locking this payment';
COMMENT ON COLUMN service_payments.validated_by_agent_id IS 'Agent profile who validated this payment';
COMMENT ON COLUMN service_payments.escalated_to_agent_id IS 'Agent profile to whom this payment was escalated';

-- ============================================================================
-- PART 3: RESTRUCTURE AGENT_PERFORMANCE_STATS (PK CHANGE)
-- ============================================================================

-- Drop the old PK constraint
ALTER TABLE agent_performance_stats DROP CONSTRAINT IF EXISTS agent_performance_stats_pkey;

-- Drop the old agent_id column
ALTER TABLE agent_performance_stats DROP COLUMN IF EXISTS agent_id;

-- Rename and set new PK
ALTER TABLE agent_performance_stats RENAME COLUMN agent_profile_id TO agent_id;
ALTER TABLE agent_performance_stats ADD PRIMARY KEY (agent_id);

-- Recreate index
DROP INDEX IF EXISTS idx_agent_perf_stats_profile;
CREATE INDEX IF NOT EXISTS idx_agent_perf_stats_agent ON agent_performance_stats(agent_id);

COMMENT ON COLUMN agent_performance_stats.agent_id IS 'FK to agent_profiles.id (UUID)';

-- ============================================================================
-- PART 4: CLEANUP PAYMENT_LOCK_HISTORY
-- ============================================================================

ALTER TABLE payment_lock_history DROP COLUMN IF EXISTS agent_id;
ALTER TABLE payment_lock_history RENAME COLUMN agent_profile_id TO agent_id;

-- Update index
DROP INDEX IF EXISTS idx_payment_lock_history_profile;
CREATE INDEX IF NOT EXISTS idx_payment_lock_history_agent ON payment_lock_history(agent_id);

COMMENT ON COLUMN payment_lock_history.agent_id IS 'FK to agent_profiles.id (UUID)';

-- ============================================================================
-- PART 5: CLEANUP PAYMENT_VALIDATION_AUDIT
-- ============================================================================

-- Keep agent_user_id for backward compatibility (references users.id directly)
ALTER TABLE payment_validation_audit DROP COLUMN IF EXISTS agent_id;
ALTER TABLE payment_validation_audit RENAME COLUMN agent_profile_id TO agent_id;

-- Update index
DROP INDEX IF EXISTS idx_payment_validation_audit_profile;
CREATE INDEX IF NOT EXISTS idx_payment_validation_audit_agent ON payment_validation_audit(agent_id);

COMMENT ON COLUMN payment_validation_audit.agent_id IS 'FK to agent_profiles.id (UUID)';
COMMENT ON COLUMN payment_validation_audit.agent_user_id IS 'Direct FK to users.id for quick user lookup';

-- ============================================================================
-- PART 6: CLEANUP AGENT_WORKLOADS
-- ============================================================================

-- Drop old agent_id (users FK) and use agent_profile_id only
ALTER TABLE agent_workloads DROP CONSTRAINT IF EXISTS agent_workloads_agent_id_fkey;
ALTER TABLE agent_workloads DROP CONSTRAINT IF EXISTS agent_workloads_agent_id_key;
DROP INDEX IF EXISTS idx_agent_workloads_agent_id;

ALTER TABLE agent_workloads DROP COLUMN IF EXISTS agent_id;
ALTER TABLE agent_workloads RENAME COLUMN agent_profile_id TO agent_id;

-- Add unique constraint on new agent_id
ALTER TABLE agent_workloads ADD CONSTRAINT agent_workloads_agent_id_key UNIQUE (agent_id);
CREATE INDEX idx_agent_workloads_agent ON agent_workloads(agent_id);

COMMENT ON COLUMN agent_workloads.agent_id IS 'FK to agent_profiles.id (UUID)';

-- ============================================================================
-- PART 7: DROP DEPRECATED COLUMNS FROM USERS TABLE
-- ============================================================================

ALTER TABLE users DROP CONSTRAINT IF EXISTS users_supervisor_id_fkey;
DROP INDEX IF EXISTS idx_users_supervisor_id;

ALTER TABLE users DROP COLUMN IF EXISTS supervisor_id;
ALTER TABLE users DROP COLUMN IF EXISTS department_id;
ALTER TABLE users DROP COLUMN IF EXISTS specializations;
ALTER TABLE users DROP COLUMN IF EXISTS max_concurrent_assignments;

-- ============================================================================
-- PART 8: DROP MINISTRY_AGENTS TABLE
-- ============================================================================

-- First drop dependent views
DROP VIEW IF EXISTS vw_ministry_agents_migration;

-- Drop the table
DROP TABLE IF EXISTS ministry_agents CASCADE;

-- ============================================================================
-- PART 9: UPDATE VIEWS
-- ============================================================================

-- Recreate vw_agents view (already correct from migration 048)
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
    ap.agent_role,
    ap.entity_id,
    e.code as entity_code,
    e.name as entity_name,
    ap.ministry_id,
    m.ministry_code,
    m.name_es as ministry_name,
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
LEFT JOIN agent_workloads aw ON ap.id = aw.agent_id;

COMMENT ON VIEW vw_agents IS 'Unified view of all agents with profiles, entities, ministries, and workloads';

-- ============================================================================
-- PART 10: FINAL CLEANUP STATISTICS
-- ============================================================================

DO $$
DECLARE
    v_agent_profiles INTEGER;
    v_agent_users INTEGER;
    v_agent_workloads INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_agent_profiles FROM agent_profiles;
    SELECT COUNT(*) INTO v_agent_users FROM users WHERE role = 'agent';
    SELECT COUNT(*) INTO v_agent_workloads FROM agent_workloads;

    RAISE NOTICE '=== Migration 049 Cleanup Complete ===';
    RAISE NOTICE 'Agent profiles: %', v_agent_profiles;
    RAISE NOTICE 'Users with agent role: %', v_agent_users;
    RAISE NOTICE 'Agent workloads: %', v_agent_workloads;
    RAISE NOTICE 'ministry_agents table: DROPPED';
    RAISE NOTICE 'Deprecated columns: REMOVED';
    RAISE NOTICE '======================================';
END $$;

-- ============================================================================
-- END OF MIGRATION 049
-- ============================================================================
