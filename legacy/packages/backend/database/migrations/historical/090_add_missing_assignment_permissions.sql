-- Migration: 090_add_missing_assignment_permissions.sql
-- Date: 2026-02-06
-- Description: Add 2 missing permissions: assignment.update_notes and assignment.view_stats
--              These permissions are used by active endpoints but were never seeded in DB,
--              causing 403 errors for all users.
-- Endpoints affected:
--   PATCH /assignments/{id}/notes  → @require_permission("assignment.update_notes")
--   GET   /assignments/stats/summary → @require_permission("assignment.view_stats")

BEGIN;

-- 1. Insert the 2 missing permissions
INSERT INTO permissions (name, resource, action, description, module_name, is_critical)
VALUES
    ('assignment.update_notes', 'assignment', 'update_notes', 'Actualizar notas de asignación', 'agent', false),
    ('assignment.view_stats', 'assignment', 'view_stats', 'Ver estadísticas de asignaciones', 'agent', false)
ON CONFLICT (name) DO NOTHING;

-- 2. Assign assignment.update_notes to: supervisor, admin, ADMIN, supervisor_tesoro
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.code IN ('supervisor', 'admin', 'ADMIN', 'supervisor_tesoro')
  AND p.name = 'assignment.update_notes'
  AND NOT EXISTS (
    SELECT 1 FROM role_permissions rp
    WHERE rp.role_id = r.id AND rp.permission_id = p.id
  );

-- 3. Assign assignment.view_stats to: supervisor, admin, ADMIN, supervisor_tesoro
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.code IN ('supervisor', 'admin', 'ADMIN', 'supervisor_tesoro')
  AND p.name = 'assignment.view_stats'
  AND NOT EXISTS (
    SELECT 1 FROM role_permissions rp
    WHERE rp.role_id = r.id AND rp.permission_id = p.id
  );

COMMIT;

-- Verification query (run after migration):
-- SELECT r.code, p.name
-- FROM role_permissions rp
-- JOIN roles r ON r.id = rp.role_id
-- JOIN permissions p ON p.id = rp.permission_id
-- WHERE p.name IN ('assignment.update_notes', 'assignment.view_stats')
-- ORDER BY r.code, p.name;
