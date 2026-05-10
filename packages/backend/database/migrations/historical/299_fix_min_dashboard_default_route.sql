-- Migration 299: Fix MIN_* agent default dashboard route
--
-- MIN_* agents landed on /dashboard/agent/oms/processor (SR-level "Dossiers
-- en Attente" page, always empty for obligation processors) instead of
-- /dashboard/agent/oms (OMS obligation queue with real data).
--
-- Fix: update the first menu item href from /oms/processor to /oms.
-- Idempotent: only updates if the old value is present.

DO $$
DECLARE
    v_admin_id uuid;
    v_role record;
    v_mc jsonb;
    v_menu jsonb;
    v_idx int;
BEGIN
    -- Set audit user
    SELECT id INTO v_admin_id FROM users
    WHERE role_id IN (SELECT id FROM roles WHERE code IN ('super_admin', 'admin'))
    LIMIT 1;
    IF v_admin_id IS NOT NULL THEN
        PERFORM set_config('app.current_user_id', v_admin_id::text, true);
    END IF;

    FOR v_role IN
        SELECT id, code, menu_config FROM roles
        WHERE code LIKE 'agent_min_%'
          AND menu_config IS NOT NULL
    LOOP
        v_mc := v_role.menu_config;
        -- Find the dashboard menu item with href /dashboard/agent/oms/processor
        FOR v_idx IN 0..jsonb_array_length(v_mc->'menus') - 1 LOOP
            v_menu := v_mc->'menus'->v_idx;
            IF v_menu->>'id' = 'dashboard'
               AND v_menu->>'href' = '/dashboard/agent/oms/processor' THEN
                v_mc := jsonb_set(
                    v_mc,
                    ARRAY['menus', v_idx::text, 'href'],
                    '"/dashboard/agent/oms"'::jsonb
                );
                UPDATE roles SET menu_config = v_mc WHERE id = v_role.id;
                RAISE NOTICE 'Fixed % dashboard route', v_role.code;
            END IF;
        END LOOP;
    END LOOP;
END;
$$;
