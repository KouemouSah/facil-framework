-- Migration 076: Assign agent.view_performance permission to 'agent' role
-- Purpose: Allow all agents to view their personal statistics on /dashboard/agent/stats
-- Date: 2026-01-25
--
-- This migration fixes the 500 error on the stats page by ensuring:
-- 1. The permission exists in the permissions table
-- 2. The permission is assigned to the 'agent' role
-- 3. All users with role='agent' have the permission via role_permissions

BEGIN;

-- Step 1: Ensure the permission exists (inserted by permission_registry, but just in case)
INSERT INTO permissions (name, resource, action, description, is_critical, module_name)
SELECT 'agent.view_performance', 'agent', 'view_performance', 'Ver estadísticas de rendimiento', false, 'agent'
WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE name = 'agent.view_performance');

-- Step 2: Get the permission ID
DO $$
DECLARE
    v_permission_id UUID;
    v_agent_role_id UUID;
BEGIN
    -- Get the permission ID
    SELECT id INTO v_permission_id FROM permissions WHERE name = 'agent.view_performance';

    IF v_permission_id IS NULL THEN
        RAISE EXCEPTION 'Permission agent.view_performance not found';
    END IF;

    -- Assign to 'agent' role if it exists
    SELECT id INTO v_agent_role_id FROM roles WHERE code = 'agent';
    IF v_agent_role_id IS NOT NULL THEN
        INSERT INTO role_permissions (role_id, permission_id)
        VALUES (v_agent_role_id, v_permission_id)
        ON CONFLICT (role_id, permission_id) DO NOTHING;

        RAISE NOTICE 'Assigned agent.view_performance to agent role';
    END IF;

    -- Also assign to entity-specific agent roles
    INSERT INTO role_permissions (role_id, permission_id)
    SELECT r.id, v_permission_id
    FROM roles r
    WHERE r.code LIKE 'agent_%'
    ON CONFLICT (role_id, permission_id) DO NOTHING;

    RAISE NOTICE 'Assigned agent.view_performance to all agent_* roles';

    -- Assign to supervisor and admin roles too
    INSERT INTO role_permissions (role_id, permission_id)
    SELECT r.id, v_permission_id
    FROM roles r
    WHERE r.code IN ('supervisor', 'admin', 'supervisor_tesoro')
    ON CONFLICT (role_id, permission_id) DO NOTHING;

    RAISE NOTICE 'Assigned agent.view_performance to supervisor/admin roles';
END $$;

-- Verification: Count how many roles now have this permission
DO $$
DECLARE
    v_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_count
    FROM role_permissions rp
    JOIN permissions p ON p.id = rp.permission_id
    WHERE p.name = 'agent.view_performance';

    RAISE NOTICE 'Total roles with agent.view_performance permission: %', v_count;
END $$;

COMMIT;
