-- ============================================================================
-- MIGRATION 334: Fix agent_min_* dashboard hrefs (Bug 4-bis)
-- Date: 2026-05-06
-- Context: discovered during the post-migration-332 verification audit.
--
-- Problem: migration 300 set the dashboard menu href for each `agent_min_*`
--      role to `/dashboard/agent/<slug>` (e.g. `/dashboard/agent/min-comercio`,
--      `/dashboard/agent/min-hacienda`, etc.). Those Next.js pages do NOT
--      exist in the frontend. Only `/dashboard/agent/page.tsx` (root) and
--      entity-specific routes that ARE shipped (cnedoge-pasaporte, oms,
--      treasury, companies) exist. Hitting a phantom URL produces the same
--      blank-page + console-error as Bug 4 (supcomercio1).
--
-- Affected agent_min_* roles (6) — same families as supervisor_min_*:
--   agent_min_comercio
--   agent_min_hacienda
--   agent_min_informacion
--   agent_min_turismo
--   agent_min_agricultura
--   agent_min_electricidad
--
-- Fix: rewrite each `dashboard` menu item href to `/dashboard/agent` (the
--      root agent page). That page calls `useAgentDashboard()` and uses
--      `getBasePath()` to auto-redirect agents to their entity-aware home
--      based on the user's profile entity_code, so the agent ends up at
--      the correct existing page (e.g. `/dashboard/agent/oms` for OMS
--      ministries) without needing per-entity Next.js pages.
--
-- Alternative considered: point directly at `/dashboard/agent/oms` (the
-- queue) for ministries that route to OMS. Rejected because (a) it
-- requires per-role hardcoded mapping and (b) the root agent page already
-- handles this dispatch logic dynamically.
--
-- Idempotent: re-running this migration is safe — jsonb_set is idempotent
--      when the target value already matches.
-- ============================================================================

BEGIN;

UPDATE roles
SET menu_config = jsonb_set(
    menu_config,
    '{menus,0,href}',
    '"/dashboard/agent"'::jsonb
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
    v_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_count
    FROM roles
    WHERE code IN (
        'agent_min_comercio',
        'agent_min_hacienda',
        'agent_min_informacion',
        'agent_min_turismo',
        'agent_min_agricultura',
        'agent_min_electricidad'
    )
    AND menu_config->'menus'->0->>'href' = '/dashboard/agent';

    RAISE NOTICE 'Migration 334: % agent_min_* roles now point to /dashboard/agent', v_count;
END $$;

COMMIT;
