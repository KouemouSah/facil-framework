-- Migration 175: Add analyst.ask permission for unified analyst endpoint
-- Phase 3 of Dynamic Supervisor Agent Architecture

BEGIN;

-- 1. Create the permission
INSERT INTO permissions (name, resource, action, description, module_name)
VALUES ('analyst.ask', 'analyst', 'ask', 'Access unified AI analyst endpoint', 'agents')
ON CONFLICT (name) DO NOTHING;

-- 2. Assign to all agent roles + supervisor roles + admin roles
-- Get the permission ID
DO $$
DECLARE
    perm_id UUID;
    role_record RECORD;
BEGIN
    SELECT id INTO perm_id FROM permissions WHERE name = 'analyst.ask';
    IF perm_id IS NULL THEN
        RAISE EXCEPTION 'Permission analyst.ask not found after INSERT';
    END IF;

    -- Assign to ALL roles that have agent.view_performance (all agent roles have this)
    FOR role_record IN
        SELECT DISTINCT rp.role_id
        FROM role_permissions rp
        JOIN permissions p ON p.id = rp.permission_id
        WHERE p.name IN ('agent.view_performance', 'agent.view', 'treasury_stat.view')
    LOOP
        INSERT INTO role_permissions (role_id, permission_id)
        VALUES (role_record.role_id, perm_id)
        ON CONFLICT DO NOTHING;
    END LOOP;

    -- Also assign to superadmin if it exists
    FOR role_record IN
        SELECT id FROM roles WHERE code = 'superadmin'
    LOOP
        INSERT INTO role_permissions (role_id, permission_id)
        VALUES (role_record.id, perm_id)
        ON CONFLICT DO NOTHING;
    END LOOP;

    RAISE NOTICE 'analyst.ask permission assigned to all agent/supervisor/admin roles';
END $$;

COMMIT;
