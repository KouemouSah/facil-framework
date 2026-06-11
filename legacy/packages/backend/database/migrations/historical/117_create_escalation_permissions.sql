-- Migration 117: Create missing escalation permissions
--
-- These permissions are required for supervisor escalation endpoints.
-- Without them, _check_is_supervisor() auto-grants them dynamically,
-- but they should exist in the permissions table for consistency.
--
-- Note: rules.* permissions already exist (rules.view/create/edit/delete/activate/view_effectiveness/view_history)
-- Note: escalation permissions are auto-granted to supervisors via _check_is_supervisor()
--       (prefix 'escalations' in generic_prefixes), so no role_permissions INSERT needed.
--
-- Date: 2026-02-22

BEGIN;

INSERT INTO permissions (id, name, resource, action, description, module_name, is_critical)
VALUES
  (gen_random_uuid(), 'escalations.view', 'escalations', 'read', 'View escalated service requests', 'escalations', false),
  (gen_random_uuid(), 'escalations.assign', 'escalations', 'write', 'Assign escalated requests to agents', 'escalations', false),
  (gen_random_uuid(), 'escalations.resolve', 'escalations', 'write', 'Resolve, approve, or reject escalations', 'escalations', true)
ON CONFLICT (name) DO NOTHING;

COMMIT;
