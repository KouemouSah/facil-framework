-- Migration 054: Consolidate agent_profile_id in agent_workloads and agent_performance_stats
-- Purpose: Complete migration from agent_id to agent_profile_id as primary identifier
-- Date: 2025-01-13
--
-- Changes:
-- 1. agent_workloads: Make agent_profile_id NOT NULL, add unique constraint
-- 2. agent_performance_stats: Add unique constraint on agent_profile_id
-- 3. Update views to use agent_profile_id
--
-- IMPORTANT: Run this AFTER ensuring all records have agent_profile_id populated

-- ============================================================================
-- STEP 1: Verify all agent_workloads have agent_profile_id
-- ============================================================================

DO $$
DECLARE
    missing_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO missing_count
    FROM agent_workloads
    WHERE agent_profile_id IS NULL;

    IF missing_count > 0 THEN
        RAISE NOTICE 'Found % records without agent_profile_id. Attempting to populate...', missing_count;

        -- Try to populate from agent_profiles using user_id = agent_id
        UPDATE agent_workloads aw
        SET agent_profile_id = ap.id
        FROM agent_profiles ap
        WHERE aw.agent_id = ap.user_id
        AND aw.agent_profile_id IS NULL;

        -- Check again
        SELECT COUNT(*) INTO missing_count
        FROM agent_workloads
        WHERE agent_profile_id IS NULL;

        IF missing_count > 0 THEN
            RAISE NOTICE 'Still % records without agent_profile_id. Deleting orphan records...', missing_count;
            DELETE FROM agent_workloads WHERE agent_profile_id IS NULL;
        END IF;
    END IF;
END $$;

-- ============================================================================
-- STEP 2: Update agent_workloads table structure
-- ============================================================================

-- Make agent_profile_id NOT NULL
ALTER TABLE agent_workloads
ALTER COLUMN agent_profile_id SET NOT NULL;

-- Add unique constraint on agent_profile_id (if not exists)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'agent_workloads_agent_profile_id_key'
    ) THEN
        ALTER TABLE agent_workloads
        ADD CONSTRAINT agent_workloads_agent_profile_id_key UNIQUE (agent_profile_id);
    END IF;
END $$;

-- Make agent_id nullable (legacy, will be removed in future migration)
ALTER TABLE agent_workloads
ALTER COLUMN agent_id DROP NOT NULL;

-- Add comment to document deprecation
COMMENT ON COLUMN agent_workloads.agent_id IS 'DEPRECATED: Use agent_profile_id. Kept for backward compatibility.';

-- ============================================================================
-- STEP 3: Verify all agent_performance_stats have agent_profile_id
-- ============================================================================

DO $$
DECLARE
    missing_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO missing_count
    FROM agent_performance_stats
    WHERE agent_profile_id IS NULL;

    IF missing_count > 0 THEN
        RAISE NOTICE 'Found % performance records without agent_profile_id. Attempting to populate...', missing_count;

        -- Try to populate from agent_profiles
        UPDATE agent_performance_stats aps
        SET agent_profile_id = ap.id
        FROM agent_profiles ap
        WHERE aps.ministry_id = ap.ministry_id
        AND aps.agent_profile_id IS NULL;

        -- Check again and delete orphans
        SELECT COUNT(*) INTO missing_count
        FROM agent_performance_stats
        WHERE agent_profile_id IS NULL;

        IF missing_count > 0 THEN
            RAISE NOTICE 'Deleting % orphan performance records...', missing_count;
            DELETE FROM agent_performance_stats WHERE agent_profile_id IS NULL;
        END IF;
    END IF;
END $$;

-- ============================================================================
-- STEP 4: Update agent_performance_stats table structure
-- ============================================================================

-- Make agent_profile_id NOT NULL
ALTER TABLE agent_performance_stats
ALTER COLUMN agent_profile_id SET NOT NULL;

-- Add unique constraint on agent_profile_id (if not exists)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'agent_performance_stats_agent_profile_id_key'
    ) THEN
        ALTER TABLE agent_performance_stats
        ADD CONSTRAINT agent_performance_stats_agent_profile_id_key UNIQUE (agent_profile_id);
    END IF;
END $$;

-- Add comment to document deprecation
COMMENT ON COLUMN agent_performance_stats.agent_id IS 'DEPRECATED: Use agent_profile_id. Legacy integer ID kept as PK for backward compatibility.';

-- ============================================================================
-- STEP 5: Create/Update views to use agent_profile_id
-- ============================================================================

-- Drop existing view if exists
DROP VIEW IF EXISTS v_agent_workload_summary CASCADE;

-- Create comprehensive workload view using agent_profile_id
CREATE OR REPLACE VIEW v_agent_workload_summary AS
SELECT
    aw.id AS workload_id,
    aw.agent_profile_id,
    ap.user_id,
    ap.agent_type,
    ap.agent_role,
    ap.is_supervisor,
    ap.ministry_id,
    ap.entity_id,
    u.full_name AS agent_name,
    u.email AS agent_email,
    m.name_es AS ministry_name,
    -- Workload metrics
    aw.current_assignments,
    aw.pending_declarations,
    aw.in_progress_declarations,
    aw.max_concurrent_assignments,
    aw.capacity_percentage,
    aw.workload_status,
    aw.availability,
    aw.availability_reason,
    aw.unavailable_until,
    -- Performance metrics
    aw.avg_processing_time_hours,
    aw.avg_daily_completions,
    aw.completion_rate_7d,
    aw.quality_score_avg,
    aw.success_rate,
    aw.deadline_compliance_rate,
    -- Timestamps
    aw.last_assignment_at,
    aw.last_completion_at,
    aw.last_updated_at,
    -- Calculated fields
    CASE
        WHEN aw.capacity_percentage >= 100 THEN 'OVERLOADED'
        WHEN aw.capacity_percentage >= 80 THEN 'HIGH'
        WHEN aw.capacity_percentage >= 50 THEN 'MEDIUM'
        ELSE 'LOW'
    END AS load_level,
    (aw.max_concurrent_assignments - aw.current_assignments) AS available_capacity
FROM agent_workloads aw
JOIN agent_profiles ap ON aw.agent_profile_id = ap.id
JOIN users u ON ap.user_id = u.id
LEFT JOIN ministries m ON ap.ministry_id = m.id
WHERE ap.is_active = true;

-- Create performance summary view
DROP VIEW IF EXISTS v_agent_performance_summary CASCADE;

CREATE OR REPLACE VIEW v_agent_performance_summary AS
SELECT
    aps.agent_profile_id,
    ap.user_id,
    ap.agent_type,
    ap.agent_role,
    ap.is_supervisor,
    ap.ministry_id,
    u.full_name AS agent_name,
    m.name_es AS ministry_name,
    -- Performance metrics
    aps.current_month_processed,
    aps.current_month_approved,
    aps.current_month_rejected,
    aps.current_month_escalated,
    aps.avg_processing_minutes,
    aps.sla_respected_count,
    aps.sla_missed_count,
    aps.sla_respect_percentage,
    -- Calculated rates
    CASE
        WHEN aps.current_month_processed > 0
        THEN ROUND((aps.current_month_approved::numeric / aps.current_month_processed) * 100, 2)
        ELSE 0
    END AS approval_rate,
    CASE
        WHEN aps.current_month_processed > 0
        THEN ROUND((aps.current_month_rejected::numeric / aps.current_month_processed) * 100, 2)
        ELSE 0
    END AS rejection_rate,
    CASE
        WHEN aps.current_month_processed > 0
        THEN ROUND((aps.current_month_escalated::numeric / aps.current_month_processed) * 100, 2)
        ELSE 0
    END AS escalation_rate,
    -- Period info
    aps.stats_period_start,
    aps.stats_period_end,
    aps.last_action_at,
    aps.updated_at
FROM agent_performance_stats aps
JOIN agent_profiles ap ON aps.agent_profile_id = ap.id
JOIN users u ON ap.user_id = u.id
LEFT JOIN ministries m ON ap.ministry_id = m.id
WHERE ap.is_active = true;

-- ============================================================================
-- STEP 6: Add index for performance on new primary identifier
-- ============================================================================

-- Index on agent_workloads.agent_profile_id (if not exists from unique constraint)
CREATE INDEX IF NOT EXISTS idx_agent_workloads_profile_id
ON agent_workloads(agent_profile_id);

-- Index for common queries
CREATE INDEX IF NOT EXISTS idx_agent_workloads_ministry_availability
ON agent_workloads(agent_profile_id, workload_status, availability);

-- ============================================================================
-- Migration complete
-- ============================================================================

-- Summary comment
COMMENT ON TABLE agent_workloads IS 'Agent workload tracking. Migration 054: agent_profile_id is now the primary identifier. agent_id is deprecated.';
COMMENT ON TABLE agent_performance_stats IS 'Agent performance statistics. Migration 054: agent_profile_id is now the primary identifier. agent_id (int PK) is deprecated.';
