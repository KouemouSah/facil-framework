-- Migration 290: Fix batch_requests permissions — create if missing + assign to roles
--
-- BUG FIX: Migration 100 created the permissions but they don't exist in DB.
-- Migration 101 assigned them but silently failed (no permissions to assign).
-- Result: citizens get "Permission denied: 'batch_requests.read' required" on
-- the "Demandes en Lot" page.
--
-- This migration is idempotent (ON CONFLICT DO NOTHING).

BEGIN;

-- Set session user for audit trigger
SET LOCAL app.current_user_id = '7c6073e3-66b0-45ba-be8d-80fcf98b7ad2';

-- 1. Create permissions if missing (schema: name, resource, action, description, is_critical, module_name)
INSERT INTO permissions (name, resource, action, description, is_critical, module_name)
VALUES
    ('batch_requests.create', 'batch_requests', 'create', 'Crear solicitudes en lote', false, 'batch_requests'),
    ('batch_requests.read', 'batch_requests', 'read', 'Ver solicitudes en lote propias', false, 'batch_requests'),
    ('batch_requests.manage', 'batch_requests', 'manage', 'Gestionar solicitudes en lote', false, 'batch_requests'),
    ('batch_requests.admin', 'batch_requests', 'all', 'Administrar todos los lotes (admin)', true, 'batch_requests')
ON CONFLICT (name) DO NOTHING;

-- 2. Assign to citizen, business, accountant: create + read
INSERT INTO role_permissions (role_id, permission_id, granted, created_by)
SELECT r.id, p.id, true, '7c6073e3-66b0-45ba-be8d-80fcf98b7ad2'::uuid
FROM roles r
CROSS JOIN permissions p
WHERE r.code IN ('citizen', 'business', 'accountant')
  AND p.name IN ('batch_requests.create', 'batch_requests.read')
ON CONFLICT DO NOTHING;

-- 3. Assign to admin: all permissions
INSERT INTO role_permissions (role_id, permission_id, granted, created_by)
SELECT r.id, p.id, true, '7c6073e3-66b0-45ba-be8d-80fcf98b7ad2'::uuid
FROM roles r
CROSS JOIN permissions p
WHERE r.code = 'admin'
  AND p.name IN ('batch_requests.create', 'batch_requests.read', 'batch_requests.manage', 'batch_requests.admin')
ON CONFLICT DO NOTHING;

-- 4. Grant declaration batch permissions to citizen (parity with business)
INSERT INTO role_permissions (role_id, permission_id, granted, created_by)
SELECT r.id, p.id, true, '7c6073e3-66b0-45ba-be8d-80fcf98b7ad2'::uuid
FROM roles r
CROSS JOIN permissions p
WHERE r.code = 'citizen'
  AND p.name IN ('declaration.batch_create', 'declaration.batch_submit', 'declaration.import_excel')
ON CONFLICT DO NOTHING;

COMMIT;
