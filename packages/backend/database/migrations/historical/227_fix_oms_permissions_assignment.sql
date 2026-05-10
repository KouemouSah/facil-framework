-- Migration 227: Fix missing OMS permissions + assign to all OMS roles
--
-- DIAGNOSTIC (2026-03-17):
--   Migration 223 created 17 OMS roles + 15 agent profiles + test users
--   BUT the 3 OMS permissions were NEVER inserted into `permissions` table.
--   Result: 6 agent_min_* have 0 permissions, agent_oms_polyvalent has 0.
--   All OMS endpoints return 403 for non-admin users.
--
-- FIX (idempotent):
--   1. INSERT 3 OMS permissions (ON CONFLICT DO NOTHING)
--   2. Assign view_bundles + process_obligations to ALL 15 OMS roles
--   3. manage_bundles stays admin-only (middleware auto-approve)
--   4. Verify: SELECT count shows expected assignments

BEGIN;

-- Audit trigger requires current_user_id
SET LOCAL app.current_user_id = '7c6073e3-66b0-45ba-be8d-80fcf98b7ad2';

-- ============================================================
-- 1. Create the 3 OMS permissions (if not exist)
-- ============================================================

INSERT INTO permissions (name, resource, action, description, is_critical, module_name)
VALUES
    ('fiscal_service.view_bundles', 'fiscal_service', 'view_bundles',
     'Ver paquetes de servicios, licencias y obligaciones', false, 'fiscal_service'),
    ('fiscal_service.manage_bundles', 'fiscal_service', 'manage_bundles',
     'Gestionar paquetes, licencias, obligaciones y reglas de configuracion', true, 'fiscal_service'),
    ('fiscal_service.process_obligations', 'fiscal_service', 'process_obligations',
     'Validar pagos, actualizar estado de obligaciones (agentes OMS)', false, 'fiscal_service')
ON CONFLICT (name) DO NOTHING;

-- ============================================================
-- 2. Assign view_bundles + process_obligations to ALL OMS roles
--    (agents process obligations, supervisors view + escalate)
-- ============================================================

-- All 15 OMS roles get: view_bundles + process_obligations
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.code IN (
    -- Ministry agents (Mode A per-line)
    'agent_min_comercio', 'agent_min_hacienda', 'agent_min_informacion',
    'agent_min_turismo', 'agent_min_agricultura', 'agent_min_electricidad',
    -- Ministry supervisors (Mode A per-line)
    'supervisor_min_comercio', 'supervisor_min_hacienda', 'supervisor_min_informacion',
    'supervisor_min_turismo', 'supervisor_min_agricultura', 'supervisor_min_electricidad',
    -- Polyvalent (Mode B consolidated)
    'agent_oms_polyvalent',
    -- TESORO (existing roles, need OMS permissions added)
    'agent_tesoro', 'supervisor_tesoro'
)
AND p.name IN ('fiscal_service.view_bundles', 'fiscal_service.process_obligations')
ON CONFLICT DO NOTHING;

-- ============================================================
-- 3. manage_bundles → admin only (already has via middleware)
--    Explicitly assign to admin + admin_services + super_admin
--    for permission audit completeness
-- ============================================================

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.code IN ('admin', 'admin_services', 'super_admin')
  AND p.name = 'fiscal_service.manage_bundles'
ON CONFLICT DO NOTHING;

COMMIT;
