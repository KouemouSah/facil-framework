-- Migration 219: Add fiscal_service.view_bundles and manage_bundles permissions
-- Required by 34+ endpoints across bundle_routes, license_routes, config_rules_routes
-- Without these, all non-admin users get 403 on OMS endpoints

BEGIN;

-- 1. Insert the 2 missing permissions
INSERT INTO permissions (name, resource, action, description, is_critical, module_name)
VALUES
    ('fiscal_service.view_bundles', 'fiscal_service', 'view_bundles',
     'Ver paquetes de servicios, licencias y obligaciones', false, 'fiscal_service'),
    ('fiscal_service.manage_bundles', 'fiscal_service', 'manage_bundles',
     'Gestionar paquetes, licencias, obligaciones y reglas de configuración', true, 'fiscal_service')
ON CONFLICT (name) DO NOTHING;

-- 2. Assign view_bundles + manage_bundles to agent_tesoro ONLY
--    admin already has wildcard access via middleware auto-approval
--    Other OMS entities (AYUNTAMIENTO, CAMARA_COMERCIO, MIN_*) don't have
--    agent roles yet — permissions will be assigned when those roles are created.
--    IMPORTANT: Do NOT assign to unrelated agents (CNEDOGE, DGT, Extranjeria, etc.)
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.code = 'agent_tesoro'
  AND p.name IN ('fiscal_service.view_bundles', 'fiscal_service.manage_bundles')
ON CONFLICT DO NOTHING;

COMMIT;
