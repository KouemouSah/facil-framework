-- ============================================================================
-- MIGRATION 149: Add admin.monitoring permission for database monitoring
-- Date: 2026-03-01
-- Context: New monitoring endpoints (pg_stat_statements, connection pool,
--          database stats, lock status) require a dedicated permission.
-- ============================================================================

BEGIN;

-- 1. Insert the permission
INSERT INTO permissions (name, resource, action, description, module_name)
VALUES ('admin.monitoring', 'monitoring', 'view', 'View database monitoring metrics (pg_stat_statements, pool, locks)', 'admin')
ON CONFLICT (name) DO NOTHING;

-- 2. Assign to admin role
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r, permissions p
WHERE r.code = 'admin'
  AND p.name = 'admin.monitoring'
ON CONFLICT DO NOTHING;

-- 3. Verify
DO $$
DECLARE
    v_perm_exists BOOLEAN;
    v_assigned BOOLEAN;
BEGIN
    SELECT EXISTS(SELECT 1 FROM permissions WHERE name = 'admin.monitoring') INTO v_perm_exists;
    SELECT EXISTS(
        SELECT 1 FROM role_permissions rp
        JOIN roles r ON r.id = rp.role_id
        JOIN permissions p ON p.id = rp.permission_id
        WHERE r.code = 'admin' AND p.name = 'admin.monitoring'
    ) INTO v_assigned;

    IF NOT v_perm_exists THEN
        RAISE EXCEPTION 'Migration 149: Permission admin.monitoring not created';
    END IF;
    IF NOT v_assigned THEN
        RAISE EXCEPTION 'Migration 149: Permission not assigned to admin role';
    END IF;
    RAISE NOTICE 'Migration 149: admin.monitoring permission created and assigned to admin role';
END $$;

COMMIT;
