-- Migration 239: Assign company.* permissions to all roles
-- BUG: 13 company permissions existed but were NEVER assigned to any role.
-- All company pages showed 0 data due to 403 errors.

BEGIN;

SELECT set_config('app.current_user_id',
    (SELECT id::text FROM users WHERE role = 'admin' LIMIT 1), true);
SELECT set_config('app.client_ip', '127.0.0.1', true);

DO $$
DECLARE
    v_role_id UUID;
    v_perm_id UUID;
    v_perm_name TEXT;
BEGIN
    -- Admin roles: ALL 13 company permissions
    FOR v_role_id IN (SELECT id FROM roles WHERE code IN ('admin', 'super_admin', 'admin_services'))
    LOOP
        FOR v_perm_id IN (SELECT id FROM permissions WHERE name LIKE 'company.%')
        LOOP
            INSERT INTO role_permissions (role_id, permission_id)
            VALUES (v_role_id, v_perm_id) ON CONFLICT DO NOTHING;
        END LOOP;
    END LOOP;

    -- ONRC supervisor: all except delete
    FOR v_role_id IN (SELECT id FROM roles WHERE code = 'supervisor_onrc')
    LOOP
        FOR v_perm_id IN (SELECT id FROM permissions WHERE name LIKE 'company.%' AND name != 'company.delete')
        LOOP
            INSERT INTO role_permissions (role_id, permission_id)
            VALUES (v_role_id, v_perm_id) ON CONFLICT DO NOTHING;
        END LOOP;
    END LOOP;

    -- ONRC agent: view + create + update + verify + classify
    FOR v_role_id IN (SELECT id FROM roles WHERE code = 'agent_onrc')
    LOOP
        FOR v_perm_name IN SELECT unnest(ARRAY[
            'company.view', 'company.view_all', 'company.create', 'company.update',
            'company.verify', 'company.classify', 'company.view_classification'])
        LOOP
            SELECT id INTO v_perm_id FROM permissions WHERE name = v_perm_name;
            IF v_perm_id IS NOT NULL THEN
                INSERT INTO role_permissions (role_id, permission_id)
                VALUES (v_role_id, v_perm_id) ON CONFLICT DO NOTHING;
            END IF;
        END LOOP;
    END LOOP;

    -- Ministry supervisors: view + entity_scoped + stats + view_classification
    FOR v_role_id IN (SELECT id FROM roles WHERE code IN (
        'supervisor_tesoro', 'supervisor_ayuntamiento', 'supervisor_camara',
        'supervisor_min_hacienda', 'supervisor_min_comercio'))
    LOOP
        FOR v_perm_name IN SELECT unnest(ARRAY[
            'company.view', 'company.view_entity_scoped', 'company.view_stats', 'company.view_classification'])
        LOOP
            SELECT id INTO v_perm_id FROM permissions WHERE name = v_perm_name;
            IF v_perm_id IS NOT NULL THEN
                INSERT INTO role_permissions (role_id, permission_id)
                VALUES (v_role_id, v_perm_id) ON CONFLICT DO NOTHING;
            END IF;
        END LOOP;
    END LOOP;

    -- Ministry agents: view + view_classification
    FOR v_role_id IN (SELECT id FROM roles WHERE code IN (
        'agent_tesoro', 'agent_ayuntamiento', 'agent_camara',
        'agent_min_hacienda', 'agent_min_comercio'))
    LOOP
        FOR v_perm_name IN SELECT unnest(ARRAY['company.view', 'company.view_classification'])
        LOOP
            SELECT id INTO v_perm_id FROM permissions WHERE name = v_perm_name;
            IF v_perm_id IS NOT NULL THEN
                INSERT INTO role_permissions (role_id, permission_id)
                VALUES (v_role_id, v_perm_id) ON CONFLICT DO NOTHING;
            END IF;
        END LOOP;
    END LOOP;
END;
$$;

COMMIT;
