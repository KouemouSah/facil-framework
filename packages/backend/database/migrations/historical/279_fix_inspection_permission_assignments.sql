-- ============================================================================
-- Migration 279: Fix missing inspection permission assignments
-- ============================================================================
-- Migration 277 created 5 new permissions but their role_permission rows
-- were not inserted (partial migration execution + audit trigger FK issue).
-- This migration re-runs the INSERTs with the audit trigger temporarily disabled.
--
-- Missing: inspection.view_reports, inspection.export,
--   inspection.manage_missions, inspection.view_analytics,
--   inspection.manage_filter_presets
--
-- NOTE: trg_audit_role_permissions references audit_logs.user_id FK which
-- fails for migration-level INSERTs (no session user). Disabled during insert.
--
-- EXECUTED: 2026-03-24 — 45 supervisor rows, 5 admin rows, 9 agent rows
-- ============================================================================

BEGIN;

-- Disable audit trigger (FK to users.id fails without session user)
ALTER TABLE role_permissions DISABLE TRIGGER trg_audit_role_permissions;

-- 1. Agent filter preset permission
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.code IN (
    'agent_ayuntamiento', 'agent_camara',
    'agent_min_comercio', 'agent_min_hacienda',
    'agent_min_informacion', 'agent_min_turismo',
    'agent_min_agricultura', 'agent_min_electricidad',
    'agent_oms_polyvalent'
)
AND p.name = 'inspection.manage_filter_presets'
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- 2. Supervisor: all 14 inspection permissions
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.code IN (
    'supervisor_ayuntamiento', 'supervisor_camara',
    'supervisor_min_comercio', 'supervisor_min_hacienda',
    'supervisor_min_informacion', 'supervisor_min_turismo',
    'supervisor_min_agricultura', 'supervisor_min_electricidad',
    'supervisor_tesoro'
)
AND p.name IN (
    'inspection.create', 'inspection.view_own',
    'inspection.view_entity', 'inspection.seal_propose',
    'inspection.seal_approve', 'inspection.collect_payment',
    'inspection.mise_en_demeure', 'inspection.reconcile_validate',
    'inspection.view_performance', 'inspection.view_reports',
    'inspection.export', 'inspection.manage_missions',
    'inspection.view_analytics', 'inspection.manage_filter_presets'
)
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- 3. Admin: all inspection permissions
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.code = 'admin'
AND p.name LIKE 'inspection.%'
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- Re-enable audit trigger
ALTER TABLE role_permissions ENABLE TRIGGER trg_audit_role_permissions;

COMMIT;
