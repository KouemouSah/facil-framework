-- Migration 226: Add company.view_entity_scoped permission for supervisors
-- This permission allows supervisors to see companies scoped to their entity's cities.
-- Agents do NOT get this permission — they see companies only via OMS queue.
-- Also removes company.view_all from agents (they don't need global company access).

BEGIN;

-- 1. Add the new permission
INSERT INTO permissions (name, resource, action, description, is_critical)
VALUES ('company.view_entity_scoped', 'company', 'view_entity_scoped',
        'Ver empresas de mi entidad (supervisor)', false)
ON CONFLICT (name) DO NOTHING;

-- 2. Assign to all supervisor roles
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE p.name = 'company.view_entity_scoped'
  AND r.code IN (
    'supervisor_tesoro',
    'supervisor_onrc',
    'supervisor_min_comercio',
    'supervisor_ayuntamiento',
    'supervisor_camara',
    'supervisor_min_hacienda',
    'supervisor_cnedoge_pasaporte',
    'supervisor_cnedoge_residencia',
    'supervisor_dgt',
    'supervisor_extranjeria',
    'supervisor_itv',
    'supervisor_min_agricultura',
    'supervisor_min_electricidad',
    'supervisor_min_informacion',
    'supervisor_min_turismo',
    'supervisor_minfp',
    'supervisor_ofive',
    'supervisor_policia'
  )
ON CONFLICT DO NOTHING;

-- 3. Also assign to admin/super_admin
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE p.name = 'company.view_entity_scoped'
  AND r.code IN ('admin', 'super_admin')
ON CONFLICT DO NOTHING;

-- 4. Remove company.view_all from non-supervisor agents (they see companies via OMS queue only)
DELETE FROM role_permissions
WHERE permission_id = (SELECT id FROM permissions WHERE name = 'company.view_all')
  AND role_id IN (
    SELECT id FROM roles WHERE code IN ('agent_oms_polyvalent', 'agent_onrc', 'agent_min_comercio')
  );

-- 5. Ensure supervisor roles that need entity-scoped also have company.view_stats
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE p.name = 'company.view_stats'
  AND r.code IN (
    'supervisor_ayuntamiento',
    'supervisor_camara',
    'supervisor_min_hacienda'
  )
ON CONFLICT DO NOTHING;

COMMIT;
