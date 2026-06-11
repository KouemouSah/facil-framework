-- Migration 298: Grant treasury.view_payment to AYUNT + CAMARA agents
--
-- AYUNT and CAMARA agents validate bundle payment splits (same pipeline as
-- TESORO). Without this permission, the dashboard widget /dashboard/widgets/
-- pending-payments returns 403 → "Erreur de chargement des paiements".
--
-- The TreasuryAgentContext scopes by entity_code, so AYUNT agents only see
-- AYUNT payments, CAMARA only CAMARA. No cross-entity leak.
--
-- Idempotent: ON CONFLICT DO NOTHING.

DO $$
DECLARE
    v_perm_id uuid;
    v_role_id uuid;
    v_admin_id uuid;
    v_roles text[] := ARRAY['agent_ayuntamiento', 'supervisor_ayuntamiento',
                            'agent_camara', 'supervisor_camara'];
    v_role text;
BEGIN
    -- Set audit user
    SELECT id INTO v_admin_id FROM users
    WHERE role_id = (SELECT id FROM roles WHERE code = 'super_admin' LIMIT 1)
    LIMIT 1;
    IF v_admin_id IS NOT NULL THEN
        PERFORM set_config('app.current_user_id', v_admin_id::text, true);
    END IF;

    SELECT id INTO v_perm_id FROM permissions WHERE name = 'treasury.view_payment';
    IF v_perm_id IS NULL THEN
        RAISE NOTICE 'Permission treasury.view_payment not found, skipping';
        RETURN;
    END IF;

    FOREACH v_role IN ARRAY v_roles LOOP
        SELECT id INTO v_role_id FROM roles WHERE code = v_role;
        IF v_role_id IS NOT NULL THEN
            INSERT INTO role_permissions (role_id, permission_id)
            VALUES (v_role_id, v_perm_id)
            ON CONFLICT DO NOTHING;
            RAISE NOTICE 'Granted treasury.view_payment to %', v_role;
        END IF;
    END LOOP;
END;
$$;
