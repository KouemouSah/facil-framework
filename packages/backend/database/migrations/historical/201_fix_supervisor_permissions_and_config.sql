-- Migration 201: Fix supervisor permissions gap + missing default_agent_config
--
-- CRITICAL FINDINGS:
--   1. Entity supervisors (9 roles) have 21 direct perms but LACK 14 supervisor-specific
--      permissions that supervisor_tesoro has (team mgmt, assignments, rules, reports)
--   2. ALL 10 supervisors (incl. tesoro) lack dashboard.team_* and service_request.view_all
--   3. 6 roles missing default_agent_config (agent_itv, agent_minfp, 4 supervisors)
--
-- HIERARCHY NOTE: parent_role_id + recursive CTE handles inheritance correctly.
--   Supervisors already inherit their parent agent's permissions via effective_permissions_mv.
--   This migration adds SUPERVISOR-SPECIFIC permissions that agents DON'T have.
--
-- Author: Claude Opus 4.6
-- Date: 2026-03-10

BEGIN;

-- Set audit context (required by trg_audit_role_permissions trigger)
-- Falls back to system admin if app.current_user_id is not set
DO $$
BEGIN
  PERFORM set_config('app.current_user_id',
    COALESCE(
      current_setting('app.current_user_id', true),
      (SELECT id::text FROM users u JOIN roles r ON r.id = u.role_id
       WHERE r.code = 'admin' AND u.status = 'active' LIMIT 1)
    ), true);
  PERFORM set_config('app.client_ip', '127.0.0.1', true);
END $$;

-- ============================================================================
-- PART 1: Add 14 supervisor-specific permissions to 9 entity supervisors
-- These are permissions that supervisor_tesoro already has, granting team
-- management capabilities that ANY supervisor needs regardless of entity.
-- ============================================================================

-- Permissions to grant (verified existing in permissions table):
--   agent.manage_workload, agent.set_availability, agent.view_workload
--   assignment.create, assignment.list, assignment.view, assignment.update_priority
--   rules.view, rules.create, rules.edit, rules.activate
--   reports.generate, reports.export_excel, reports.view_performance

INSERT INTO role_permissions (role_id, permission_id, granted)
SELECT r.id, p.id, true
FROM roles r
CROSS JOIN permissions p
WHERE r.code IN (
    'supervisor_cnedoge_pasaporte',
    'supervisor_cnedoge_residencia',
    'supervisor_dgt',
    'supervisor_extranjeria',
    'supervisor_itv',
    'supervisor_minfp',
    'supervisor_ofive',
    'supervisor_onrc',
    'supervisor_policia'
)
AND p.name IN (
    -- Team workload management
    'agent.manage_workload',
    'agent.set_availability',
    'agent.view_workload',
    -- Assignment management (create, list, view, prioritize)
    'assignment.create',
    'assignment.list',
    'assignment.view',
    'assignment.update_priority',
    -- Auto-assignment rules
    'rules.view',
    'rules.create',
    'rules.edit',
    'rules.activate',
    -- Reports
    'reports.generate',
    'reports.export_excel',
    'reports.view_performance'
)
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- ============================================================================
-- PART 2: Add 4 dashboard/global view permissions to ALL 10 supervisors
-- supervisor_tesoro was also missing these.
-- ============================================================================

INSERT INTO role_permissions (role_id, permission_id, granted)
SELECT r.id, p.id, true
FROM roles r
CROSS JOIN permissions p
WHERE r.code IN (
    'supervisor_cnedoge_pasaporte',
    'supervisor_cnedoge_residencia',
    'supervisor_dgt',
    'supervisor_extranjeria',
    'supervisor_itv',
    'supervisor_minfp',
    'supervisor_ofive',
    'supervisor_onrc',
    'supervisor_policia',
    'supervisor_tesoro'
)
AND p.name IN (
    'dashboard.team_performance',
    'dashboard.team_workload',
    'dashboard.view_realtime',
    'service_request.view_all'
)
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- ============================================================================
-- PART 3: Add default_agent_config to 6 roles missing it
-- Pattern: agents get base config, supervisors get elevated config
-- ============================================================================

-- Agent roles (base config: can escalate only)
UPDATE roles SET default_agent_config = '{
    "can_escalate": true,
    "can_reassign": false,
    "is_supervisor": false,
    "can_assign_tasks": false,
    "can_approve_unlimited": false
}'::jsonb
WHERE code IN ('agent_itv', 'agent_minfp')
  AND default_agent_config IS NULL;

-- Supervisor roles (elevated config: full team management)
UPDATE roles SET default_agent_config = '{
    "can_escalate": true,
    "can_reassign": true,
    "is_supervisor": true,
    "can_assign_tasks": true,
    "can_approve_unlimited": false
}'::jsonb
WHERE code IN (
    'supervisor_extranjeria',
    'supervisor_itv',
    'supervisor_minfp',
    'supervisor_policia'
)
AND default_agent_config IS NULL;

-- ============================================================================
-- PART 4: Refresh materialized view to reflect changes
-- ============================================================================

SELECT refresh_effective_permissions();

-- ============================================================================
-- VERIFICATION QUERIES (run manually to confirm)
-- ============================================================================

-- Verify: all supervisors now have >= 35 direct permissions
-- SELECT r.code, COUNT(rp.permission_id) as direct_perms
-- FROM roles r
-- JOIN role_permissions rp ON rp.role_id = r.id
-- WHERE r.code LIKE 'supervisor_%'
-- GROUP BY r.code ORDER BY r.code;

-- Verify: all roles have default_agent_config
-- SELECT code, default_agent_config IS NOT NULL as has_config
-- FROM roles WHERE entity_type IN ('agent', 'entity_agent') ORDER BY code;

COMMIT;
