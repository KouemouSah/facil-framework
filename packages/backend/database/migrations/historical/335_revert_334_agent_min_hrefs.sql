-- ============================================================================
-- MIGRATION 335: REVERT migration 334 — agent_min_* hrefs restored
-- Date: 2026-05-06
-- Context: HOTFIX after user verification that the original routes worked.
--
-- Problem: migration 334 (committed earlier today) rewrote the dashboard
--      href for the 6 agent_min_* roles to `/dashboard/agent` based on
--      the false assumption that `/dashboard/agent/min-*` returned a
--      blank page. The user verified post-push (images 1.png, 2.png) that
--      `/dashboard/agent/min-comercio` and `/dashboard/agent/min-hacienda`
--      DO render correctly.
--
-- Why migration 334 was wrong: the Next.js shell-glob audit
-- (`find ... -type d`) mis-handled the literal-bracket folder
-- `[entityCode]/` and missed it. That dynamic route
-- (`dashboard/agent/[entityCode]/page.tsx`) catches any slug like
-- `min-comercio`, `min-hacienda`, … and renders `GenericEntityDashboard`
-- with the resolved entity_code. So the menu_config hrefs set by
-- migration 300 were correct all along.
--
-- Fix: restore each agent_min_* role's dashboard href to its
-- entity-specific slug (the original migration-300 value):
--   agent_min_comercio       → /dashboard/agent/min-comercio
--   agent_min_hacienda       → /dashboard/agent/min-hacienda
--   agent_min_informacion    → /dashboard/agent/min-informacion
--   agent_min_turismo        → /dashboard/agent/min-turismo
--   agent_min_agricultura    → /dashboard/agent/min-agricultura
--   agent_min_electricidad   → /dashboard/agent/min-electricidad
--
-- Note: migration 332 (supervisor_min_*) remains correct because the
-- supervisor branch has NO `[entityCode]` dynamic route — the original
-- migration-306 hrefs (`/dashboard/supervisor/min-*`) really were
-- phantom for supervisors.
--
-- Idempotent: jsonb_set is idempotent when the target value matches.
-- ============================================================================

BEGIN;

-- Restore each agent_min_* href in lock-step with the role code suffix
UPDATE roles
SET menu_config = jsonb_set(
    menu_config,
    '{menus,0,href}',
    to_jsonb('/dashboard/agent/' || REPLACE(SUBSTRING(code FROM 7), '_', '-'))
)
WHERE code IN (
    'agent_min_comercio',
    'agent_min_hacienda',
    'agent_min_informacion',
    'agent_min_turismo',
    'agent_min_agricultura',
    'agent_min_electricidad'
)
AND menu_config IS NOT NULL
AND menu_config->'menus'->0->>'id' = 'dashboard';

-- Verification
DO $$
DECLARE
    v_role record;
    v_expected text;
    v_actual text;
    v_count INTEGER := 0;
BEGIN
    FOR v_role IN
        SELECT code, menu_config->'menus'->0->>'href' AS href
        FROM roles
        WHERE code IN (
            'agent_min_comercio',
            'agent_min_hacienda',
            'agent_min_informacion',
            'agent_min_turismo',
            'agent_min_agricultura',
            'agent_min_electricidad'
        )
    LOOP
        v_expected := '/dashboard/agent/' || REPLACE(SUBSTRING(v_role.code FROM 7), '_', '-');
        v_actual := v_role.href;
        IF v_actual = v_expected THEN
            v_count := v_count + 1;
        ELSE
            RAISE WARNING 'Migration 335: role % has href=% (expected %)',
                v_role.code, v_actual, v_expected;
        END IF;
    END LOOP;
    RAISE NOTICE 'Migration 335: % / 6 agent_min_* roles restored to entity slug', v_count;
END $$;

COMMIT;
