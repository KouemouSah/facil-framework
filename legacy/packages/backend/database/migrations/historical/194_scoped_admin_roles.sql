-- Migration 194: Scoped Admin Roles
-- Phase 6.1 of GESTION_ACCES_PROFESSIONAL_REDESIGN
-- Creates modular admin roles: super_admin, admin_agents, admin_services, admin_config, admin_security, admin_support
-- Each role gets a specific subset of the 290+ permissions

BEGIN;

-- 1. Create admin.view_security permission (needed for anomaly detection endpoint)
INSERT INTO permissions (name, description, module_name, resource, action, is_critical)
VALUES ('admin.view_security', 'View security anomalies and overprivileged users', 'admin', 'security', 'view', true)
ON CONFLICT (name) DO NOTHING;

-- 2. Create scoped admin roles
INSERT INTO roles (code, name, description, is_system, entity_type)
VALUES
  ('super_admin', 'Super Administrador', 'Full access to all admin features including security and system management', true, NULL),
  ('admin_agents', 'Admin Agentes', 'Agent management, assignments, workload and performance', false, NULL),
  ('admin_services', 'Admin Servicios', 'Fiscal services catalog, workflows, tariffs, document and procedure templates', false, NULL),
  ('admin_config', 'Admin Configuración', 'Communications, menu config, translations, system settings', false, NULL),
  ('admin_security', 'Admin Seguridad', 'Roles, permissions, audit logs, security anomalies', false, NULL),
  ('admin_support', 'Admin Soporte', 'Support tickets, categories, and diagnostics', false, NULL)
ON CONFLICT (code) DO UPDATE SET
  name = EXCLUDED.name,
  description = EXCLUDED.description;

-- 3. super_admin = ALL permissions (same as admin role)
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.code = 'super_admin'
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- 4. admin_agents: agent.*, assignment.*, user management, dashboard, reports
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.code = 'admin_agents'
  AND (
    p.module_name IN ('agent', 'assignment', 'dashboard', 'reports')
    OR p.name IN (
      'admin.manage_user', 'admin.view_user', 'admin.manage_entity', 'admin.view_entity',
      'admin.manage_appointment', 'admin.view_appointment',
      'user.view', 'user.view_all', 'user.search', 'user.view_stats', 'user.view_any_activities',
      'user.create', 'user.update', 'user.update_any', 'user.change_role',
      'user.suspend', 'user.reactivate',
      'city.view', 'entity.view'
    )
  )
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- 5. admin_services: fiscal_service.*, document templates, procedure templates, workflows, tariffs
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.code = 'admin_services'
  AND (
    p.module_name IN ('fiscal_service', 'document')
    OR p.name IN (
      'admin.manage_workflow', 'admin.view_workflow',
      'admin.manage_tariff', 'admin.view_tariff',
      'admin.manage_entity', 'admin.view_entity',
      'admin.manage_appointment', 'admin.view_appointment',
      'city.view', 'entity.view', 'entity.create', 'entity.update',
      'funcionario_verificacion.read_all', 'funcionario_verificacion.process',
      'funcionario_verificacion.view_stats', 'funcionario_verificacion.export'
    )
  )
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- 6. admin_config: communication.*, menu.*, translation.*, webhook.*, system settings
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.code = 'admin_config'
  AND (
    p.module_name IN ('communication', 'menu', 'translation', 'webhook')
    OR p.name IN (
      'admin.manage_system', 'admin.view_system',
      'admin.view_diagnostics',
      'city.view', 'city.create', 'city.update', 'city.delete',
      'entity.view'
    )
  )
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- 7. admin_security: permissions.*, roles.*, audit.*, system permissions, user_permissions.*
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.code = 'admin_security'
  AND (
    p.module_name IN ('permissions', 'audit', 'system', 'rules')
    OR p.name IN (
      'admin.view_security',
      'admin.view_user', 'admin.view_system',
      'user.view', 'user.view_all', 'user.search',
      'admin.run_migrations'
    )
  )
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- 8. admin_support: support.*, diagnostics
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.code = 'admin_support'
  AND (
    p.module_name = 'support'
    OR p.name IN (
      'admin.view_diagnostics',
      'admin.view_user',
      'user.view', 'user.search'
    )
  )
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- 9. Also grant admin.view_security to existing admin role
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.code = 'admin' AND p.name = 'admin.view_security'
ON CONFLICT (role_id, permission_id) DO NOTHING;

COMMIT;
