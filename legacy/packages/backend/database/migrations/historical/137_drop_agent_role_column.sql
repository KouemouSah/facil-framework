-- Migration 137: Drop dead agent_role column + audit/optimize all agent views
--
-- CONTEXT:
-- agent_role (validator/approver/auditor/reviewer) is 100% dead code:
--   - 4/4 agents = "validator"
--   - 0 WHERE/HAVING clauses filter on it
--   - 0 business logic conditions on it
--   - RBAC roles (users.role_id → roles → role_permissions) replaced it entirely
--
-- AUDIT FINDINGS (beyond agent_role removal):
--   - v_agent_workload_summary: missing entity_code/entity_name, entity_location_id
--   - v_agent_performance_summary: missing entity_id/entity_code for entity filtering
--   - v_available_agents: missing entity_location_id for site-based routing
--   - v_agents_workload_dashboard: missing entity_location_id
--   - v_agent_performance_rankings: missing entity_name (had entity_code but not name)
--   - vw_agents: missing entity_location_id + location details
--
-- STEPS:
-- 1. Recreate 7 views (6 with agent_role removed + 1 aggregate view refreshed)
-- 2. DROP the column from agent_profiles
-- 3. Verify
--
-- ROLLBACK: If needed, re-add column with:
--   ALTER TABLE agent_profiles ADD COLUMN agent_role VARCHAR(50) NOT NULL DEFAULT 'validator';
--   Then recreate views with ap.agent_role added back.

BEGIN;

-- ============================================================================
-- STEP 0: Drop all views (required because removing a column changes positions)
-- CREATE VIEW cannot reorder/remove columns
-- ============================================================================

DROP VIEW IF EXISTS v_agent_workload_summary CASCADE;
DROP VIEW IF EXISTS v_agent_performance_summary CASCADE;
DROP VIEW IF EXISTS v_available_agents CASCADE;
DROP VIEW IF EXISTS v_available_agents_by_ministry CASCADE;
DROP VIEW IF EXISTS v_agents_workload_dashboard CASCADE;
DROP VIEW IF EXISTS v_agent_performance_rankings CASCADE;
DROP VIEW IF EXISTS vw_agents CASCADE;

-- ============================================================================
-- STEP 1: Recreate views WITHOUT agent_role + add missing columns
-- ============================================================================

-- 1a. v_agent_workload_summary
-- CHANGES: removed agent_role, added entity_code/entity_name/entity_location_id
CREATE VIEW v_agent_workload_summary AS
SELECT aw.id AS workload_id,
    aw.agent_profile_id,
    ap.user_id,
    ap.agent_type,
    ap.is_supervisor,
    ap.ministry_id,
    ap.entity_id,
    ap.entity_location_id,
    u.full_name AS agent_name,
    u.email AS agent_email,
    e.code AS entity_code,
    e.name AS entity_name,
    m.name_es AS ministry_name,
    aw.current_assignments,
    aw.pending_declarations,
    aw.in_progress_declarations,
    aw.max_concurrent_assignments,
    aw.capacity_percentage,
    aw.workload_status,
    aw.availability,
    aw.availability_reason,
    aw.unavailable_until,
    aw.avg_processing_time_hours,
    aw.avg_daily_completions,
    aw.completion_rate_7d,
    aw.quality_score_avg,
    aw.success_rate,
    aw.deadline_compliance_rate,
    aw.last_assignment_at,
    aw.last_completion_at,
    aw.last_updated_at,
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
LEFT JOIN entities e ON ap.entity_id = e.id
LEFT JOIN ministries m ON ap.ministry_id = m.id
WHERE ap.is_active = true;

-- 1b. v_agent_performance_summary
-- CHANGES: removed agent_role, added entity_id/entity_code/entity_name
CREATE VIEW v_agent_performance_summary AS
SELECT aps.agent_profile_id,
    ap.user_id,
    ap.agent_type,
    ap.is_supervisor,
    ap.ministry_id,
    ap.entity_id,
    u.full_name AS agent_name,
    e.code AS entity_code,
    e.name AS entity_name,
    m.name_es AS ministry_name,
    aps.current_month_processed,
    aps.current_month_approved,
    aps.current_month_rejected,
    aps.current_month_escalated,
    aps.avg_processing_minutes,
    aps.sla_respected_count,
    aps.sla_missed_count,
    aps.sla_respect_percentage,
    CASE
        WHEN aps.current_month_processed > 0 THEN round((aps.current_month_approved::numeric / aps.current_month_processed::numeric) * 100, 2)
        ELSE 0
    END AS approval_rate,
    CASE
        WHEN aps.current_month_processed > 0 THEN round((aps.current_month_rejected::numeric / aps.current_month_processed::numeric) * 100, 2)
        ELSE 0
    END AS rejection_rate,
    CASE
        WHEN aps.current_month_processed > 0 THEN round((aps.current_month_escalated::numeric / aps.current_month_processed::numeric) * 100, 2)
        ELSE 0
    END AS escalation_rate,
    aps.stats_period_start,
    aps.stats_period_end,
    aps.last_action_at,
    aps.updated_at
FROM agent_performance_stats aps
JOIN agent_profiles ap ON aps.agent_profile_id = ap.id
JOIN users u ON ap.user_id = u.id
LEFT JOIN entities e ON ap.entity_id = e.id
LEFT JOIN ministries m ON ap.ministry_id = m.id
WHERE ap.is_active = true;

-- 1c. v_available_agents
-- CHANGES: removed agent_role, added entity_location_id
CREATE VIEW v_available_agents AS
SELECT ap.id AS agent_profile_id,
    ap.user_id,
    u.email,
    u.full_name,
    u.first_name,
    u.last_name,
    u.role AS user_role,
    ap.agent_type,
    ap.is_supervisor,
    ap.entity_id,
    ap.entity_location_id,
    e.code AS entity_code,
    e.name AS entity_name,
    ap.ministry_id,
    m.ministry_code,
    m.name_es AS ministry_name,
    ap.can_approve_unlimited,
    ap.max_approval_amount,
    ap.can_escalate,
    ap.can_assign_tasks,
    ap.specializations,
    ap.is_active,
    aw.current_assignments,
    aw.max_concurrent_assignments,
    aw.capacity_percentage,
    aw.workload_status,
    aw.availability,
    aw.quality_score_avg,
    aw.last_assignment_at,
    CASE
        WHEN m.ministry_code = 'DGI' THEN 'dgi'
        WHEN m.ministry_code = 'TESORO' THEN 'treasury'
        WHEN ap.agent_type = 'entity_agent' THEN 'entity'
        ELSE 'ministry'
    END AS agent_category
FROM agent_profiles ap
JOIN users u ON ap.user_id = u.id
LEFT JOIN entities e ON ap.entity_id = e.id
LEFT JOIN ministries m ON ap.ministry_id = m.id
LEFT JOIN agent_workloads aw ON ap.id = aw.agent_profile_id
WHERE ap.is_active = true
  AND (aw.availability = 'available' OR aw.availability IS NULL)
  AND (aw.workload_status <> 'overloaded' OR aw.workload_status IS NULL);

-- 1d. v_agents_workload_dashboard
-- CHANGES: removed agent_role, added entity_location_id
-- NOTE: intentionally NO is_active filter — dashboard admin needs to see all agents
CREATE VIEW v_agents_workload_dashboard AS
SELECT ap.id AS agent_profile_id,
    ap.user_id,
    u.email,
    u.full_name,
    ap.agent_type,
    ap.is_supervisor,
    ap.ministry_id,
    m.ministry_code,
    m.name_es AS ministry_name,
    ap.entity_id,
    ap.entity_location_id,
    e.code AS entity_code,
    e.name AS entity_name,
    ap.is_active,
    COALESCE(aw.current_assignments, 0) AS current_assignments,
    COALESCE(aw.pending_declarations, 0) AS pending_declarations,
    COALESCE(aw.in_progress_declarations, 0) AS in_progress_declarations,
    COALESCE(aw.max_concurrent_assignments, 20) AS max_concurrent_assignments,
    COALESCE(aw.capacity_percentage, 0) AS capacity_percentage,
    COALESCE(aw.workload_status::text, 'available') AS workload_status,
    COALESCE(aw.availability::text, 'available') AS availability,
    aw.quality_score_avg,
    aw.success_rate,
    aw.avg_daily_completions,
    aw.last_assignment_at,
    aw.last_completion_at,
    CASE
        WHEN COALESCE(aw.capacity_percentage, 0) >= 100 THEN 'FULL'
        WHEN COALESCE(aw.capacity_percentage, 0) >= 80 THEN 'HIGH'
        WHEN COALESCE(aw.capacity_percentage, 0) >= 50 THEN 'MEDIUM'
        ELSE 'LOW'
    END AS load_level,
    COALESCE(aps.current_month_processed, 0) AS current_month_processed,
    COALESCE(aps.current_month_approved, 0) AS current_month_approved,
    COALESCE(aps.current_month_rejected, 0) AS current_month_rejected,
    aps.sla_respect_percentage,
    CASE
        WHEN m.ministry_code = 'DGI' THEN 'dgi'
        WHEN m.ministry_code = 'TESORO' THEN 'treasury'
        WHEN ap.agent_type = 'entity_agent' THEN 'entity'
        ELSE 'ministry'
    END AS agent_category
FROM agent_profiles ap
JOIN users u ON ap.user_id = u.id
LEFT JOIN ministries m ON ap.ministry_id = m.id
LEFT JOIN entities e ON ap.entity_id = e.id
LEFT JOIN agent_workloads aw ON ap.id = aw.agent_profile_id
LEFT JOIN agent_performance_stats aps ON ap.id = aps.agent_profile_id;

-- 1e. v_agent_performance_rankings
-- CHANGES: removed agent_role, added entity_name
CREATE VIEW v_agent_performance_rankings AS
SELECT ap.id AS agent_profile_id,
    ap.user_id,
    u.full_name,
    u.email,
    ap.ministry_id,
    m.ministry_code,
    m.name_es AS ministry_name,
    ap.entity_id,
    e.code AS entity_code,
    e.name AS entity_name,
    ap.agent_type,
    ap.is_supervisor,
    COALESCE(aps.current_month_processed, 0) AS current_month_processed,
    COALESCE(aps.current_month_approved, 0) AS current_month_approved,
    COALESCE(aps.current_month_rejected, 0) AS current_month_rejected,
    COALESCE(aps.current_month_escalated, 0) AS current_month_escalated,
    COALESCE(aps.sla_respect_percentage, 0) AS sla_respect_percentage,
    aps.avg_processing_minutes,
    COALESCE(aw.quality_score_avg, 0) AS quality_score_avg,
    COALESCE(aw.success_rate, 0) AS success_rate,
    round(
        COALESCE(aps.sla_respect_percentage, 0) * 0.30
        + COALESCE(aw.quality_score_avg, 0) * 0.30
        + COALESCE(aw.success_rate, 0) * 0.20
        + LEAST(COALESCE(aps.current_month_processed, 0)::numeric / 10.0, 20) * 0.20
    , 2) AS performance_score,
    CASE
        WHEN COALESCE(aps.sla_respect_percentage, 0) >= 90 AND COALESCE(aw.quality_score_avg, 0) >= 85 THEN 'EXCELLENT'
        WHEN COALESCE(aps.sla_respect_percentage, 0) >= 75 AND COALESCE(aw.quality_score_avg, 0) >= 70 THEN 'GOOD'
        WHEN COALESCE(aps.sla_respect_percentage, 0) >= 60 THEN 'AVERAGE'
        ELSE 'NEEDS_IMPROVEMENT'
    END AS performance_tier,
    rank() OVER (ORDER BY COALESCE(aps.sla_respect_percentage, 0) DESC, COALESCE(aps.current_month_processed, 0) DESC) AS overall_rank,
    rank() OVER (PARTITION BY ap.ministry_id ORDER BY COALESCE(aps.sla_respect_percentage, 0) DESC, COALESCE(aps.current_month_processed, 0) DESC) AS ministry_rank
FROM agent_profiles ap
JOIN users u ON ap.user_id = u.id
LEFT JOIN ministries m ON ap.ministry_id = m.id
LEFT JOIN entities e ON ap.entity_id = e.id
LEFT JOIN agent_performance_stats aps ON ap.id = aps.agent_profile_id
LEFT JOIN agent_workloads aw ON ap.id = aw.agent_profile_id
WHERE ap.is_active = true;

-- 1f. vw_agents (comprehensive agent view)
-- CHANGES: removed agent_role, added entity_location_id + location details
CREATE VIEW vw_agents AS
SELECT u.id AS user_id,
    u.email,
    u.full_name,
    u.first_name,
    u.last_name,
    u.phone_number,
    u.role AS user_role,
    ap.id AS agent_profile_id,
    ap.agent_type,
    ap.is_supervisor,
    ap.entity_id,
    e.code AS entity_code,
    e.name AS entity_name,
    e.ministry_id AS entity_ministry_id,
    ap.entity_location_id,
    el.location_name,
    el.city AS location_city,
    el.region AS location_region,
    ap.ministry_id,
    m.ministry_code,
    m.name_es AS ministry_name,
    CASE
        WHEN m.ministry_code = 'DGI' THEN 'dgi'
        WHEN m.ministry_code = 'TESORO' THEN 'treasury'
        WHEN ap.agent_type = 'entity_agent' THEN 'entity'
        ELSE 'ministry'
    END AS agent_category,
    ap.can_approve_unlimited,
    ap.max_approval_amount,
    ap.can_escalate,
    ap.can_assign_tasks,
    ap.can_reassign,
    ap.specializations,
    ap.working_hours_start,
    ap.working_hours_end,
    ap.working_days,
    ap.is_active AS agent_is_active,
    ap.is_backup_agent,
    aw.id AS workload_id,
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
LEFT JOIN entity_locations el ON ap.entity_location_id = el.id
LEFT JOIN ministries m ON ap.ministry_id = m.id
LEFT JOIN agent_workloads aw ON ap.id = aw.agent_profile_id;

-- 1g. v_available_agents_by_ministry (aggregate view - no agent_role to remove)
-- REFRESH: no changes needed, but recreate to ensure consistency
CREATE VIEW v_available_agents_by_ministry AS
SELECT m.id AS ministry_id,
    m.ministry_code,
    m.name_es AS ministry_name,
    count(DISTINCT ap.id) AS total_agents,
    count(DISTINCT ap.id) FILTER (WHERE ap.is_active = true) AS active_agents,
    count(DISTINCT ap.id) FILTER (WHERE ap.is_active = true AND (aw.availability = 'available' OR aw.availability IS NULL)) AS available_agents,
    count(DISTINCT ap.id) FILTER (WHERE ap.is_supervisor = true) AS supervisor_count,
    round(COALESCE(avg(aw.capacity_percentage), 0), 2) AS avg_capacity,
    COALESCE(sum(aw.max_concurrent_assignments - aw.current_assignments) FILTER (WHERE ap.is_active = true AND aw.availability = 'available'), 0) AS available_capacity
FROM ministries m
LEFT JOIN agent_profiles ap ON m.id = ap.ministry_id
LEFT JOIN agent_workloads aw ON ap.id = aw.agent_profile_id
GROUP BY m.id, m.ministry_code, m.name_es;

-- ============================================================================
-- STEP 2: Drop the column
-- ============================================================================

ALTER TABLE agent_profiles DROP COLUMN agent_role;

-- ============================================================================
-- STEP 3: Verify
-- ============================================================================

DO $$
DECLARE
    col_exists BOOLEAN;
    view_count INTEGER;
BEGIN
    -- Verify column dropped
    SELECT EXISTS(
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'agent_profiles' AND column_name = 'agent_role'
    ) INTO col_exists;

    IF col_exists THEN
        RAISE EXCEPTION 'agent_role column still exists after DROP!';
    END IF;

    -- Verify all 7 views exist
    SELECT count(*) INTO view_count
    FROM information_schema.views
    WHERE table_schema = 'public'
      AND table_name IN (
        'v_agent_workload_summary',
        'v_agent_performance_summary',
        'v_available_agents',
        'v_available_agents_by_ministry',
        'v_agents_workload_dashboard',
        'v_agent_performance_rankings',
        'vw_agents'
      );

    IF view_count <> 7 THEN
        RAISE EXCEPTION 'Expected 7 views, found %', view_count;
    END IF;

    -- Verify no view references agent_role anymore
    IF EXISTS (
        SELECT 1 FROM pg_views
        WHERE schemaname = 'public'
          AND viewname LIKE '%agent%'
          AND definition ILIKE '%agent_role%'
    ) THEN
        RAISE EXCEPTION 'Some view still references agent_role!';
    END IF;

    RAISE NOTICE 'Migration 137 OK: agent_role dropped, 7 views recreated with audit fixes.';
END $$;

COMMIT;
