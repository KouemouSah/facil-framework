-- Migration 220: Split process_obligations from manage_bundles
--
-- Principle of least privilege:
--   view_bundles = read access to bundles, licenses, obligations (OMS agents + admin)
--   manage_bundles = admin only (bundle CRUD, config rules, license admin, crons)
--   process_obligations = OMS agents (validate payments, update obligation status)
--
-- agent_tesoro gets: view_bundles + process_obligations (NOT manage_bundles)
-- Future OMS agents (ayuntamiento, camara, min_*) will get the same pattern.

BEGIN;

-- 1. Ensure all 3 OMS permissions exist
INSERT INTO permissions (name, resource, action, description, is_critical, module_name)
VALUES
    ('fiscal_service.view_bundles', 'fiscal_service', 'view_bundles',
     'Ver paquetes de servicios, licencias y obligaciones', false, 'fiscal_service'),
    ('fiscal_service.manage_bundles', 'fiscal_service', 'manage_bundles',
     'Gestionar paquetes, licencias, obligaciones y reglas de configuracion', true, 'fiscal_service'),
    ('fiscal_service.process_obligations', 'fiscal_service', 'process_obligations',
     'Validar pagos, actualizar estado de obligaciones (agentes OMS)', false, 'fiscal_service')
ON CONFLICT (name) DO NOTHING;

-- 2. Assign view_bundles + process_obligations to agent_tesoro
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r CROSS JOIN permissions p
WHERE r.code = 'agent_tesoro'
  AND p.name IN ('fiscal_service.view_bundles', 'fiscal_service.process_obligations')
ON CONFLICT DO NOTHING;

-- 3. Ensure manage_bundles is NOT assigned to agent_tesoro
DELETE FROM role_permissions
WHERE role_id = (SELECT id FROM roles WHERE code = 'agent_tesoro')
  AND permission_id = (SELECT id FROM permissions WHERE name = 'fiscal_service.manage_bundles');

COMMIT;
