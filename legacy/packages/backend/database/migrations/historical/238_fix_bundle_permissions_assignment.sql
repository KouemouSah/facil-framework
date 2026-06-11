-- Migration 238: Assign missing fiscal_service bundle permissions
--
-- BUG: fiscal_service.view_bundles, manage_bundles, process_obligations
-- were created in the permissions table but NEVER assigned to any role.
-- This caused 403 errors on ALL bundle/license/config-rules endpoints.
--
-- Fix: Assign to appropriate roles:
--   admin/super_admin/admin_services: view_bundles + manage_bundles
--   agents: view_bundles + process_obligations
--   supervisors: view_bundles + manage_bundles + process_obligations

BEGIN;

-- Set session context for audit trigger
SELECT set_config('app.current_user_id',
    (SELECT id::text FROM users WHERE role = 'admin' LIMIT 1),
    true);
SELECT set_config('app.client_ip', '127.0.0.1', true);

DO $$
DECLARE
    v_view_id UUID;
    v_manage_id UUID;
    v_process_id UUID;
    v_role_id UUID;
BEGIN
    SELECT id INTO v_view_id FROM permissions WHERE name = 'fiscal_service.view_bundles';
    SELECT id INTO v_manage_id FROM permissions WHERE name = 'fiscal_service.manage_bundles';
    SELECT id INTO v_process_id FROM permissions WHERE name = 'fiscal_service.process_obligations';

    IF v_view_id IS NULL THEN
        RAISE NOTICE 'Permissions not found, skipping';
        RETURN;
    END IF;

    -- Admin roles: view + manage
    FOR v_role_id IN (SELECT id FROM roles WHERE code IN ('admin', 'super_admin', 'admin_services'))
    LOOP
        INSERT INTO role_permissions (role_id, permission_id) VALUES (v_role_id, v_view_id) ON CONFLICT DO NOTHING;
        INSERT INTO role_permissions (role_id, permission_id) VALUES (v_role_id, v_manage_id) ON CONFLICT DO NOTHING;
    END LOOP;

    -- Agent roles: view + process
    FOR v_role_id IN (SELECT id FROM roles WHERE code IN (
        'agent_tesoro', 'agent_ayuntamiento', 'agent_camara',
        'agent_min_hacienda', 'agent_min_comercio', 'agent_onrc'))
    LOOP
        INSERT INTO role_permissions (role_id, permission_id) VALUES (v_role_id, v_view_id) ON CONFLICT DO NOTHING;
        INSERT INTO role_permissions (role_id, permission_id) VALUES (v_role_id, v_process_id) ON CONFLICT DO NOTHING;
    END LOOP;

    -- Supervisor roles: view + manage + process
    FOR v_role_id IN (SELECT id FROM roles WHERE code IN (
        'supervisor_tesoro', 'supervisor_ayuntamiento', 'supervisor_camara',
        'supervisor_min_hacienda', 'supervisor_min_comercio', 'supervisor_onrc'))
    LOOP
        INSERT INTO role_permissions (role_id, permission_id) VALUES (v_role_id, v_view_id) ON CONFLICT DO NOTHING;
        INSERT INTO role_permissions (role_id, permission_id) VALUES (v_role_id, v_manage_id) ON CONFLICT DO NOTHING;
        INSERT INTO role_permissions (role_id, permission_id) VALUES (v_role_id, v_process_id) ON CONFLICT DO NOTHING;
    END LOOP;
END;
$$;

COMMIT;
