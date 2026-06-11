-- Migration 196: Fix admin privilege inversion
-- CRITICAL: admin role (73 perms) had FEWER permissions than admin_agents (76)
-- This migration ensures admin role has ALL permissions that any scoped admin has,
-- plus removes admin.run_migrations from admin_security (too dangerous).

BEGIN;

-- 0. Re-create admin.view_security permission (may have been lost)
INSERT INTO permissions (name, description, module_name, resource, action, is_critical)
VALUES ('admin.view_security', 'View security anomalies and overprivileged users', 'admin', 'security', 'view', true)
ON CONFLICT (name) DO NOTHING;

-- 0b. Ensure super_admin has all permissions (including any new ones)
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r CROSS JOIN permissions p
WHERE r.code = 'super_admin'
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- 0c. Ensure admin.view_security is assigned to admin and admin_security
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r CROSS JOIN permissions p
WHERE r.code IN ('admin', 'admin_security') AND p.name = 'admin.view_security'
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- 1. Give admin role ALL permissions from ALL scoped admin roles
-- This ensures admin >= any scoped admin (no privilege inversion)
INSERT INTO role_permissions (role_id, permission_id)
SELECT admin_role.id, rp.permission_id
FROM roles admin_role
CROSS JOIN (
  SELECT DISTINCT rp2.permission_id
  FROM role_permissions rp2
  JOIN roles r ON r.id = rp2.role_id
  WHERE r.code IN ('admin_agents', 'admin_services', 'admin_config', 'admin_security', 'admin_support')
) rp
WHERE admin_role.code = 'admin'
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- 2. Remove admin.run_migrations from admin_security (should be super_admin only)
DELETE FROM role_permissions
WHERE role_id = (SELECT id FROM roles WHERE code = 'admin_security')
  AND permission_id = (SELECT id FROM permissions WHERE name = 'admin.run_migrations');

-- 3. Add read-only service_request access to admin_agents and admin_services
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.code = 'admin_agents'
  AND p.name IN (
    'service_request.view', 'service_request.view_all',
    'service_request.view_queue', 'service_request.view_queue_stats',
    'service_request.view_audit_log'
  )
ON CONFLICT (role_id, permission_id) DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.code = 'admin_services'
  AND p.name IN (
    'service_request.view', 'service_request.view_all',
    'service_request.view_queue_stats'
  )
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- 4. Add service_request read access to admin_support (see what users complain about)
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.code = 'admin_support'
  AND p.name IN (
    'service_request.view', 'service_request.view_all',
    'service_request.view_documents'
  )
ON CONFLICT (role_id, permission_id) DO NOTHING;

COMMIT;
