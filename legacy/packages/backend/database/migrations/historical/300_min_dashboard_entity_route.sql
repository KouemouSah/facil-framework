-- Migration 300: Route MIN_* dashboard to entity dashboard page
--
-- MIN_* agents were landing on /dashboard/agent/oms (OMS queue) instead of
-- their entity dashboard (/dashboard/agent/min-hacienda, etc.) which has
-- stats cards powered by the obligation processor path in get_queue_stats.
--
-- Each MIN_* role gets a unique dashboard href derived from its entity slug.

DO $$
DECLARE
    v_admin_id uuid;
    v_role record;
    v_mc jsonb;
    v_idx int;
    v_menu jsonb;
    v_slug text;
    v_new_href text;
BEGIN
    SELECT id INTO v_admin_id FROM users
    WHERE role_id IN (SELECT id FROM roles WHERE code IN ('super_admin', 'admin'))
    LIMIT 1;
    IF v_admin_id IS NOT NULL THEN
        PERFORM set_config('app.current_user_id', v_admin_id::text, true);
    END IF;

    FOR v_role IN
        SELECT id, code, menu_config FROM roles
        WHERE code LIKE 'agent_min_%' AND menu_config IS NOT NULL
    LOOP
        v_mc := v_role.menu_config;
        v_slug := REPLACE(SUBSTRING(v_role.code FROM 7), '_', '-');
        v_new_href := '/dashboard/agent/' || v_slug;

        FOR v_idx IN 0..jsonb_array_length(v_mc->'menus') - 1 LOOP
            v_menu := v_mc->'menus'->v_idx;
            IF v_menu->>'id' = 'dashboard' THEN
                v_mc := jsonb_set(
                    v_mc,
                    ARRAY['menus', v_idx::text, 'href'],
                    to_jsonb(v_new_href)
                );
                UPDATE roles SET menu_config = v_mc WHERE id = v_role.id;
                RAISE NOTICE 'Fixed % dashboard -> %', v_role.code, v_new_href;
            END IF;
        END LOOP;
    END LOOP;
END;
$$;
