-- ============================================================================
-- Migration 051: Drop Deprecated Tables and Recreate Views
-- ============================================================================
-- Date: 2025-01-13
-- Description: Remove deprecated tables and recreate views with correct schema
--
-- PREREQUISITE: Migration 049 must be applied first!
--               After 049, all *_agent_id columns are UUIDs referencing agent_profiles
--
-- Tables dropped:
-- 1. ministry_agents - Replaced by agent_profiles (should be empty)
-- 2. user_ministry_assignments - Never implemented in backend (orphan table)
--
-- Tables KEPT:
-- - ministry_validation_config - Reserved for future auto-approval/SLA features
-- - user_permissions - Active part of RBAC system
-- ============================================================================

-- ============================================================================
-- PART 1: DROP ALL VIEWS THAT MIGHT DEPEND ON DEPRECATED STRUCTURES
-- ============================================================================
-- Drop ALL agent-related views to avoid dependency issues
-- These will be recreated with correct schema in Part 4

DROP VIEW IF EXISTS v_agent_work_queue_priority CASCADE;
DROP VIEW IF EXISTS v_agents_workload_dashboard CASCADE;
DROP VIEW IF EXISTS v_available_agents CASCADE;
DROP VIEW IF EXISTS v_available_agents_by_ministry CASCADE;
DROP VIEW IF EXISTS v_agent_entity_summary CASCADE;
DROP VIEW IF EXISTS v_agent_performance_rankings CASCADE;
DROP VIEW IF EXISTS v_active_assignments CASCADE;
DROP VIEW IF EXISTS v_agent_assignment_history CASCADE;
DROP VIEW IF EXISTS v_pending_escalations CASCADE;
DROP VIEW IF EXISTS v_pending_payment_validations CASCADE;
DROP VIEW IF EXISTS vw_agents CASCADE;
DROP VIEW IF EXISTS vw_ministry_agents_migration CASCADE;

-- Also drop permission views that might have issues
DROP VIEW IF EXISTS v_permission_grants_audit CASCADE;
DROP VIEW IF EXISTS v_permission_usage_analytics CASCADE;
DROP VIEW IF EXISTS v_role_capabilities_summary CASCADE;

-- ============================================================================
-- PART 2: DROP DEPRECATED TABLES
-- ============================================================================

-- Safety check: Verify ministry_agents has no data before dropping
DO $$
DECLARE
    agent_count INTEGER;
BEGIN
    -- Check if table exists first
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'ministry_agents') THEN
        SELECT COUNT(*) INTO agent_count FROM ministry_agents;
        IF agent_count > 0 THEN
            RAISE EXCEPTION 'ministry_agents still has % rows. Migrate data before dropping.', agent_count;
        END IF;
    END IF;
END $$;

-- Drop FK constraints on ministry_agents (if they still exist)
ALTER TABLE ministry_agents DROP CONSTRAINT IF EXISTS ministry_agents_backup_for_agent_id_fkey;

-- Drop ministry_agents table
DROP TABLE IF EXISTS ministry_agents CASCADE;

-- Drop user_ministry_assignments table (never implemented)
DROP TABLE IF EXISTS user_ministry_assignments CASCADE;

-- Drop orphaned indexes (if any remain)
DROP INDEX IF EXISTS idx_ministry_agents_user;
DROP INDEX IF EXISTS idx_ministry_agents_ministry;
DROP INDEX IF EXISTS ministry_agents_user_id_ministry_id_key;
DROP INDEX IF EXISTS idx_ministry_assignments_user;
DROP INDEX IF EXISTS idx_ministry_assignments_ministry;
DROP INDEX IF EXISTS idx_ministry_assignments_pending;

-- ============================================================================
-- PART 3: VERIFY CURRENT SCHEMA STATE
-- ============================================================================
-- After migration 049, these columns should exist and be UUID type

DO $$
DECLARE
    v_agent_workloads_ok BOOLEAN := FALSE;
    v_service_payments_ok BOOLEAN := FALSE;
BEGIN
    -- Check agent_workloads.agent_id exists and is UUID
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'agent_workloads'
          AND column_name = 'agent_id'
          AND udt_name = 'uuid'
    ) INTO v_agent_workloads_ok;

    -- Check service_payments has UUID agent columns
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'service_payments'
          AND column_name = 'assigned_agent_id'
          AND udt_name = 'uuid'
    ) INTO v_service_payments_ok;

    IF NOT v_agent_workloads_ok THEN
        RAISE WARNING 'agent_workloads.agent_id is not UUID - check migration 049';
    END IF;

    IF NOT v_service_payments_ok THEN
        RAISE WARNING 'service_payments.assigned_agent_id is not UUID - check migration 049';
    END IF;

    IF v_agent_workloads_ok AND v_service_payments_ok THEN
        RAISE NOTICE 'Part 3: Schema verification passed - all columns are UUID type';
    END IF;
END $$;

-- ============================================================================
-- PART 4: RECREATE ALL AGENT-RELATED VIEWS
-- ============================================================================
-- All views now use agent_profiles and UUID agent_id columns

-- v_available_agents: List of available agents for task assignment
CREATE OR REPLACE VIEW v_available_agents AS
SELECT
    ap.id AS agent_profile_id,
    ap.user_id,
    u.email,
    u.full_name,
    u.first_name,
    u.last_name,
    u.role AS user_role,
    ap.agent_type,
    ap.agent_role,
    ap.is_supervisor,
    ap.entity_id,
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
  AND (aw.workload_status != 'overloaded' OR aw.workload_status IS NULL);

COMMENT ON VIEW v_available_agents IS 'Available agents for task assignment with workload info';

-- v_available_agents_by_ministry: Aggregated agent availability per ministry
CREATE OR REPLACE VIEW v_available_agents_by_ministry AS
SELECT
    m.id AS ministry_id,
    m.ministry_code,
    m.name_es AS ministry_name,
    COUNT(DISTINCT ap.id) AS total_agents,
    COUNT(DISTINCT ap.id) FILTER (WHERE ap.is_active = true) AS active_agents,
    COUNT(DISTINCT ap.id) FILTER (
        WHERE ap.is_active = true
        AND (aw.availability = 'available' OR aw.availability IS NULL)
    ) AS available_agents,
    COUNT(DISTINCT ap.id) FILTER (WHERE ap.is_supervisor = true) AS supervisor_count,
    ROUND(COALESCE(AVG(aw.capacity_percentage), 0), 2) AS avg_capacity,
    COALESCE(SUM(aw.max_concurrent_assignments - aw.current_assignments) FILTER (
        WHERE ap.is_active = true AND aw.availability = 'available'
    ), 0) AS available_capacity
FROM ministries m
LEFT JOIN agent_profiles ap ON m.id = ap.ministry_id
LEFT JOIN agent_workloads aw ON ap.id = aw.agent_profile_id
GROUP BY m.id, m.ministry_code, m.name_es;

COMMENT ON VIEW v_available_agents_by_ministry IS 'Agent availability aggregated by ministry';

-- v_agent_entity_summary: Agent summary per entity
CREATE OR REPLACE VIEW v_agent_entity_summary AS
SELECT
    e.id AS entity_id,
    e.code AS entity_code,
    e.name AS entity_name,
    e.entity_type,
    m.id AS ministry_id,
    m.ministry_code,
    m.name_es AS ministry_name,
    COUNT(DISTINCT ap.id) AS total_agents,
    COUNT(DISTINCT ap.id) FILTER (WHERE ap.is_active = true) AS active_agents,
    COUNT(DISTINCT ap.id) FILTER (
        WHERE ap.is_active = true
        AND (aw.availability = 'available' OR aw.availability IS NULL)
    ) AS available_agents,
    COUNT(DISTINCT ap.id) FILTER (WHERE ap.is_supervisor = true) AS supervisor_count,
    ROUND(COALESCE(AVG(aw.capacity_percentage), 0), 2) AS avg_capacity,
    COALESCE(SUM(aw.max_concurrent_assignments - aw.current_assignments) FILTER (
        WHERE ap.is_active = true AND aw.availability = 'available'
    ), 0) AS available_capacity
FROM entities e
LEFT JOIN ministries m ON e.ministry_id = m.id
LEFT JOIN agent_profiles ap ON e.id = ap.entity_id
LEFT JOIN agent_workloads aw ON ap.id = aw.agent_profile_id
GROUP BY e.id, e.code, e.name, e.entity_type, m.id, m.ministry_code, m.name_es;

COMMENT ON VIEW v_agent_entity_summary IS 'Agent availability aggregated by entity';

-- v_agents_workload_dashboard: Comprehensive dashboard view
CREATE OR REPLACE VIEW v_agents_workload_dashboard AS
SELECT
    ap.id AS agent_profile_id,
    ap.user_id,
    u.email,
    u.full_name,
    ap.agent_type,
    ap.agent_role,
    ap.is_supervisor,
    ap.ministry_id,
    m.ministry_code,
    m.name_es AS ministry_name,
    ap.entity_id,
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

COMMENT ON VIEW v_agents_workload_dashboard IS 'Comprehensive agent workload dashboard';

-- v_agent_performance_rankings: Agent performance with rankings
CREATE OR REPLACE VIEW v_agent_performance_rankings AS
SELECT
    ap.id AS agent_profile_id,
    ap.user_id,
    u.full_name,
    u.email,
    ap.ministry_id,
    m.ministry_code,
    m.name_es AS ministry_name,
    ap.entity_id,
    e.code AS entity_code,
    ap.agent_type,
    ap.agent_role,
    ap.is_supervisor,
    COALESCE(aps.current_month_processed, 0) AS current_month_processed,
    COALESCE(aps.current_month_approved, 0) AS current_month_approved,
    COALESCE(aps.current_month_rejected, 0) AS current_month_rejected,
    COALESCE(aps.current_month_escalated, 0) AS current_month_escalated,
    COALESCE(aps.sla_respect_percentage, 0) AS sla_respect_percentage,
    aps.avg_processing_minutes,
    COALESCE(aw.quality_score_avg, 0) AS quality_score_avg,
    COALESCE(aw.success_rate, 0) AS success_rate,
    ROUND(
        COALESCE(aps.sla_respect_percentage, 0) * 0.30 +
        COALESCE(aw.quality_score_avg, 0) * 0.30 +
        COALESCE(aw.success_rate, 0) * 0.20 +
        LEAST(COALESCE(aps.current_month_processed, 0) / 10.0, 20) * 0.20
    , 2) AS performance_score,
    CASE
        WHEN COALESCE(aps.sla_respect_percentage, 0) >= 90
             AND COALESCE(aw.quality_score_avg, 0) >= 85 THEN 'EXCELLENT'
        WHEN COALESCE(aps.sla_respect_percentage, 0) >= 75
             AND COALESCE(aw.quality_score_avg, 0) >= 70 THEN 'GOOD'
        WHEN COALESCE(aps.sla_respect_percentage, 0) >= 60 THEN 'AVERAGE'
        ELSE 'NEEDS_IMPROVEMENT'
    END AS performance_tier,
    RANK() OVER (
        ORDER BY COALESCE(aps.sla_respect_percentage, 0) DESC,
                 COALESCE(aps.current_month_processed, 0) DESC
    ) AS overall_rank,
    RANK() OVER (
        PARTITION BY ap.ministry_id
        ORDER BY COALESCE(aps.sla_respect_percentage, 0) DESC,
                 COALESCE(aps.current_month_processed, 0) DESC
    ) AS ministry_rank
FROM agent_profiles ap
JOIN users u ON ap.user_id = u.id
LEFT JOIN ministries m ON ap.ministry_id = m.id
LEFT JOIN entities e ON ap.entity_id = e.id
LEFT JOIN agent_performance_stats aps ON ap.id = aps.agent_profile_id
LEFT JOIN agent_workloads aw ON ap.id = aw.agent_profile_id
WHERE ap.is_active = true;

COMMENT ON VIEW v_agent_performance_rankings IS 'Agent performance rankings with composite scores';

-- v_agent_work_queue_priority: Work queue with priority scoring
-- Note: agent_work_queue.assigned_to → users.id, so we join through users to get agent_profile
CREATE OR REPLACE VIEW v_agent_work_queue_priority AS
SELECT
    awq.id AS queue_id,
    awq.ministry_id,
    m.name_es AS ministry_name,
    awq.item_id AS declaration_id,
    awq.declaration_type,
    awq.amount AS calculated_tax,
    awq.priority_score AS priority,
    awq.sla_deadline,
    awq.sla_status,
    awq.status AS queue_status,
    awq.assigned_to AS assigned_user_id,
    ap.id AS agent_profile_id,
    u.full_name AS agent_name,
    awq.locked_until,
    awq.escalated,
    awq.escalation_reason,
    awq.created_at,
    EXTRACT(EPOCH FROM (NOW() - awq.created_at)) / 3600 AS hours_in_queue,
    CASE
        WHEN awq.sla_deadline IS NOT NULL AND NOW() > awq.sla_deadline THEN true
        ELSE false
    END AS is_overdue,
    CASE
        WHEN awq.sla_deadline IS NOT NULL THEN
            EXTRACT(EPOCH FROM (awq.sla_deadline - NOW())) / 3600
        ELSE NULL
    END AS hours_until_deadline
FROM agent_work_queue awq
LEFT JOIN ministries m ON awq.ministry_id = m.id
LEFT JOIN users u ON awq.assigned_to = u.id
LEFT JOIN agent_profiles ap ON ap.user_id = u.id AND ap.is_active = true
WHERE awq.status IN ('pending', 'in_progress', 'assigned')
ORDER BY awq.priority_score DESC, awq.created_at ASC;

COMMENT ON VIEW v_agent_work_queue_priority IS 'Work queue prioritized by score and SLA';

-- v_active_assignments: Currently active assignments
CREATE OR REPLACE VIEW v_active_assignments AS
SELECT
    a.id AS assignment_id,
    a.declaration_id,
    a.declaration_type,
    a.agent_id AS agent_user_id,
    ap.id AS agent_profile_id,
    u.full_name AS agent_name,
    u.email AS agent_email,
    ap.ministry_id,
    m.ministry_code,
    ap.entity_id,
    e.code AS entity_code,
    a.status AS assignment_status,
    a.priority_level,
    a.assigned_at,
    a.deadline,
    ROUND(EXTRACT(EPOCH FROM (NOW() - a.assigned_at)) / 3600, 2) AS hours_since_assigned,
    CASE
        WHEN a.deadline IS NOT NULL AND NOW() > a.deadline THEN true
        ELSE false
    END AS is_overdue,
    CASE
        WHEN a.deadline IS NOT NULL THEN
            ROUND(EXTRACT(EPOCH FROM (a.deadline - NOW())) / 3600, 2)
        ELSE NULL
    END AS hours_until_deadline
FROM assignments a
JOIN users u ON a.agent_id = u.id
LEFT JOIN agent_profiles ap ON ap.user_id = u.id AND ap.is_active = true
LEFT JOIN ministries m ON ap.ministry_id = m.id
LEFT JOIN entities e ON ap.entity_id = e.id
WHERE a.status IN ('assigned', 'in_progress', 'pending_review');

COMMENT ON VIEW v_active_assignments IS 'Currently active task assignments';

-- v_agent_assignment_history: Complete assignment history
CREATE OR REPLACE VIEW v_agent_assignment_history AS
SELECT
    a.id AS assignment_id,
    a.declaration_id,
    a.declaration_type,
    a.agent_id AS agent_user_id,
    ap.id AS agent_profile_id,
    u.full_name AS agent_name,
    ap.ministry_id,
    m.ministry_code,
    ap.entity_id,
    e.code AS entity_code,
    a.status AS assignment_status,
    a.priority_level,
    a.assignment_method,
    a.assigned_at,
    a.completed_at,
    a.deadline,
    a.notes,
    CASE
        WHEN a.completed_at IS NOT NULL THEN
            ROUND(EXTRACT(EPOCH FROM (a.completed_at - a.assigned_at)) / 3600, 2)
        ELSE NULL
    END AS total_hours
FROM assignments a
JOIN users u ON a.agent_id = u.id
LEFT JOIN agent_profiles ap ON ap.user_id = u.id AND ap.is_active = true
LEFT JOIN ministries m ON ap.ministry_id = m.id
LEFT JOIN entities e ON ap.entity_id = e.id;

COMMENT ON VIEW v_agent_assignment_history IS 'Complete assignment history with agent details';

-- v_pending_escalations: Pending escalations needing supervisor attention
CREATE OR REPLACE VIEW v_pending_escalations AS
SELECT
    sp.id AS payment_id,
    sp.payment_reference,
    sp.service_request_id,
    sr.reference AS service_request_reference,
    sp.total_amount,
    sp.workflow_status,
    sp.escalation_level,
    sp.escalation_reason,
    sp.escalated_at,
    sp.escalated_to_agent_profile_id AS escalated_to_agent_profile_id,
    supervisor.full_name AS escalated_to_name,
    supervisor.email AS escalated_to_email,
    sp.assigned_agent_profile_id AS original_agent_profile_id,
    original_agent.full_name AS original_agent_name,
    ap_escalated.ministry_id,
    m.ministry_code,
    m.name_es AS ministry_name,
    ROUND(EXTRACT(EPOCH FROM (NOW() - sp.escalated_at)) / 3600, 2) AS hours_since_escalation,
    CASE
        WHEN sp.escalation_level::text = 'critical' THEN 1
        WHEN sp.escalation_level::text = 'high' THEN 2
        WHEN sp.escalation_level::text = 'medium' THEN 3
        ELSE 4
    END AS priority_order
FROM service_payments sp
LEFT JOIN service_requests sr ON sp.service_request_id = sr.id
LEFT JOIN agent_profiles ap_escalated ON ap_escalated.id = sp.escalated_to_agent_profile_id
LEFT JOIN users supervisor ON ap_escalated.user_id = supervisor.id
LEFT JOIN agent_profiles ap_original ON ap_original.id = sp.assigned_agent_profile_id
LEFT JOIN users original_agent ON ap_original.user_id = original_agent.id
LEFT JOIN ministries m ON ap_escalated.ministry_id = m.id
WHERE sp.workflow_status IN ('escalated_supervisor', 'supervisor_reviewing')
  AND sp.escalated_at IS NOT NULL
ORDER BY priority_order, sp.escalated_at ASC;

COMMENT ON VIEW v_pending_escalations IS 'Pending escalations requiring supervisor attention';

-- v_pending_payment_validations: Treasury dashboard for pending validations
CREATE OR REPLACE VIEW v_pending_payment_validations AS
SELECT
    sp.id AS payment_id,
    sp.payment_reference,
    sp.service_request_id,
    sr.reference AS request_reference,
    sr.workflow_code,
    sp.user_id,
    u.full_name AS user_name,
    u.email AS user_email,
    sp.payment_method,
    sp.total_amount,
    sp.currency,
    sp.workflow_status,
    sp.locked_by_agent_profile_id,
    ap.user_id AS locked_by_user_id,
    locked_user.full_name AS locked_by_name,
    sp.lock_expires_at,
    sp.created_at,
    EXTRACT(EPOCH FROM (NOW() - sp.created_at)) / 3600 AS hours_waiting
FROM service_payments sp
LEFT JOIN service_requests sr ON sp.service_request_id = sr.id
LEFT JOIN users u ON sp.user_id = u.id
LEFT JOIN agent_profiles ap ON sp.locked_by_agent_profile_id = ap.id
LEFT JOIN users locked_user ON ap.user_id = locked_user.id
WHERE sp.workflow_status = 'pending_agent_review'
  AND sp.requires_agent_validation = true
ORDER BY sp.created_at ASC;

COMMENT ON VIEW v_pending_payment_validations IS 'View for Treasury agent dashboard showing payments awaiting validation';

-- vw_agents: Unified view of all agents
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
-- PART 5: RECREATE PERMISSION VIEWS
-- ============================================================================

-- v_permission_grants_audit: Audit trail for permission changes
CREATE OR REPLACE VIEW v_permission_grants_audit AS
SELECT
    pal.id,
    pal.user_id AS target_user_id,
    u.email AS target_email,
    u.role AS target_role,
    pal.permission_id,
    p.name AS permission_name,
    p.resource AS permission_resource,
    p.action AS permission_action,
    p.module_name,
    pal.action AS audit_action,
    pal.table_name,
    pal.changed_by,
    admin.email AS changed_by_email,
    admin.full_name AS changed_by_name,
    pal.old_value,
    pal.new_value,
    pal.changed_at
FROM permission_audit_log pal
LEFT JOIN users u ON pal.user_id = u.id
LEFT JOIN permissions p ON pal.permission_id = p.id
LEFT JOIN users admin ON pal.changed_by = admin.id
ORDER BY pal.changed_at DESC;

COMMENT ON VIEW v_permission_grants_audit IS 'Audit trail for all permission changes';

-- v_permission_usage_analytics: Analytics on permission distribution
CREATE OR REPLACE VIEW v_permission_usage_analytics AS
SELECT
    p.id AS permission_id,
    p.name AS permission_name,
    p.resource,
    p.action,
    p.module_name,
    p.is_critical,
    COUNT(DISTINCT up.user_id) FILTER (WHERE up.granted = true) AS direct_grant_count,
    COUNT(DISTINCT rp.role_id) FILTER (WHERE rp.granted = true) AS role_grant_count,
    p.created_at AS permission_created_at
FROM permissions p
LEFT JOIN user_permissions up ON p.id = up.permission_id
LEFT JOIN role_permissions rp ON p.id = rp.permission_id
GROUP BY p.id, p.name, p.resource, p.action, p.module_name, p.is_critical, p.created_at
ORDER BY direct_grant_count DESC, role_grant_count DESC;

COMMENT ON VIEW v_permission_usage_analytics IS 'Analytics on how permissions are distributed';

-- v_role_capabilities_summary: Summary of role capabilities
CREATE OR REPLACE VIEW v_role_capabilities_summary AS
SELECT
    r.id AS role_id,
    r.name AS role_name,
    r.code AS role_code,
    r.description AS role_description,
    r.entity_type,
    r.is_system,
    COUNT(DISTINCT rp.permission_id) FILTER (WHERE rp.granted = true) AS permission_count,
    COUNT(DISTINCT u.id) AS user_count,
    ARRAY_AGG(DISTINCT p.module_name ORDER BY p.module_name) FILTER (WHERE p.module_name IS NOT NULL AND rp.granted = true) AS modules_accessed,
    r.created_at
FROM roles r
LEFT JOIN role_permissions rp ON r.id = rp.role_id
LEFT JOIN permissions p ON rp.permission_id = p.id
LEFT JOIN users u ON u.role_id = r.id AND u.status = 'active'
GROUP BY r.id, r.name, r.code, r.description, r.entity_type, r.is_system, r.created_at
ORDER BY permission_count DESC;

COMMENT ON VIEW v_role_capabilities_summary IS 'Summary of capabilities per role';

-- ============================================================================
-- PART 6: VERIFICATION
-- ============================================================================

DO $$
DECLARE
    v_views_count INTEGER;
    v_ministry_agents_exists BOOLEAN;
    v_user_ministry_assignments_exists BOOLEAN;
BEGIN
    -- Count recreated views
    SELECT COUNT(*) INTO v_views_count
    FROM information_schema.views
    WHERE table_schema = 'public'
      AND table_name IN (
          'v_available_agents',
          'v_available_agents_by_ministry',
          'v_agent_entity_summary',
          'v_agents_workload_dashboard',
          'v_agent_performance_rankings',
          'v_agent_work_queue_priority',
          'v_active_assignments',
          'v_agent_assignment_history',
          'v_pending_escalations',
          'v_pending_payment_validations',
          'vw_agents',
          'v_permission_grants_audit',
          'v_permission_usage_analytics',
          'v_role_capabilities_summary'
      );

    -- Check deprecated tables are gone
    SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'ministry_agents')
    INTO v_ministry_agents_exists;

    SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'user_ministry_assignments')
    INTO v_user_ministry_assignments_exists;

    RAISE NOTICE '========================================';
    RAISE NOTICE 'Migration 051 Complete';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Views recreated: %/14', v_views_count;
    RAISE NOTICE 'ministry_agents dropped: %', NOT v_ministry_agents_exists;
    RAISE NOTICE 'user_ministry_assignments dropped: %', NOT v_user_ministry_assignments_exists;
    RAISE NOTICE '';
    RAISE NOTICE 'Agent views (11):';
    RAISE NOTICE '  - v_available_agents';
    RAISE NOTICE '  - v_available_agents_by_ministry';
    RAISE NOTICE '  - v_agent_entity_summary';
    RAISE NOTICE '  - v_agents_workload_dashboard';
    RAISE NOTICE '  - v_agent_performance_rankings';
    RAISE NOTICE '  - v_agent_work_queue_priority';
    RAISE NOTICE '  - v_active_assignments';
    RAISE NOTICE '  - v_agent_assignment_history';
    RAISE NOTICE '  - v_pending_escalations';
    RAISE NOTICE '  - v_pending_payment_validations';
    RAISE NOTICE '  - vw_agents';
    RAISE NOTICE '';
    RAISE NOTICE 'Permission views (3):';
    RAISE NOTICE '  - v_permission_grants_audit';
    RAISE NOTICE '  - v_permission_usage_analytics';
    RAISE NOTICE '  - v_role_capabilities_summary';
    RAISE NOTICE '========================================';
END $$;

-- ============================================================================
-- END OF MIGRATION 051
-- ============================================================================
