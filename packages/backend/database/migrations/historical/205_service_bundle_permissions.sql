-- Migration 205: Permissions for Service Bundles
-- Assigns bundle management permissions to admin roles

BEGIN;

-- ============================================================
-- 1. Create permissions
-- ============================================================
INSERT INTO permissions (name, resource, action, description, module_name)
VALUES
    ('fiscal_service.manage_bundles', 'fiscal_service', 'manage_bundles', 'Crear, editar y eliminar bundles de servicios comerciales', 'fiscal_service'),
    ('fiscal_service.view_bundles', 'fiscal_service', 'view_bundles', 'Ver bundles de servicios comerciales y matrices de precios', 'fiscal_service')
ON CONFLICT (name) DO NOTHING;

-- ============================================================
-- 2. Assign to admin roles
-- ============================================================
-- Roles verified via: SELECT code FROM roles WHERE code LIKE '%admin%' OR code LIKE '%super%'
-- admin, admin_services, super_admin get manage_bundles
-- All admin + supervisor roles get view_bundles

-- manage_bundles → admin, admin_services, super_admin
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r, permissions p
WHERE r.code IN ('admin', 'admin_services', 'super_admin')
  AND p.name = 'fiscal_service.manage_bundles'
ON CONFLICT DO NOTHING;

-- view_bundles → all admin + supervisor roles
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r, permissions p
WHERE (r.code LIKE 'admin%' OR r.code LIKE 'super%' OR r.code LIKE 'supervisor%')
  AND p.name = 'fiscal_service.view_bundles'
ON CONFLICT DO NOTHING;

-- ============================================================
-- 3. Verification
-- ============================================================
-- SELECT r.code, p.name
-- FROM role_permissions rp
-- JOIN roles r ON r.id = rp.role_id
-- JOIN permissions p ON p.id = rp.permission_id
-- WHERE p.name LIKE 'fiscal_service.%bundle%'
-- ORDER BY r.code, p.name;

COMMIT;
