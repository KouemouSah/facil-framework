-- Migration: Create identifiers module permissions
-- Date: 2026-01-29
-- Description: Create missing permissions for verified_identifiers module
--              and assign them to admin role

BEGIN;

-- Create identifiers.import permission
INSERT INTO permissions (name, resource, action, description, is_critical, module_name)
VALUES (
    'identifiers.import',
    'identifiers',
    'import',
    'Import verified identifiers from external sources (CSV/JSON batch import)',
    true,
    'identifiers'
)
ON CONFLICT (name) DO NOTHING;

-- Create identifiers.stats permission
INSERT INTO permissions (name, resource, action, description, is_critical, module_name)
VALUES (
    'identifiers.stats',
    'identifiers',
    'stats',
    'View verified identifiers statistics and queue metrics',
    false,
    'identifiers'
)
ON CONFLICT (name) DO NOTHING;

-- Create identifiers.config permission
INSERT INTO permissions (name, resource, action, description, is_critical, module_name)
VALUES (
    'identifiers.config',
    'identifiers',
    'config',
    'View and manage document verification configurations',
    false,
    'identifiers'
)
ON CONFLICT (name) DO NOTHING;

-- Assign all identifiers permissions to admin role
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r, permissions p
WHERE r.code = 'admin'
  AND p.name IN ('identifiers.import', 'identifiers.stats', 'identifiers.config')
  AND NOT EXISTS (
    SELECT 1 FROM role_permissions rp
    WHERE rp.role_id = r.id AND rp.permission_id = p.id
  );

-- Also assign to supervisor role (for monitoring purposes)
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r, permissions p
WHERE r.code = 'supervisor'
  AND p.name IN ('identifiers.stats', 'identifiers.config')
  AND NOT EXISTS (
    SELECT 1 FROM role_permissions rp
    WHERE rp.role_id = r.id AND rp.permission_id = p.id
  );

COMMIT;

-- Verification query
-- SELECT p.name, r.code as role
-- FROM role_permissions rp
-- JOIN roles r ON r.id = rp.role_id
-- JOIN permissions p ON p.id = rp.permission_id
-- WHERE p.name LIKE 'identifiers.%'
-- ORDER BY p.name, r.code;
