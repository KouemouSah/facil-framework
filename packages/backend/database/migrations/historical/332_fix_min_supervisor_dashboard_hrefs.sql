-- ============================================================================
-- MIGRATION 332: Fix MIN_* supervisor dashboard hrefs
-- Date: 2026-05-06
-- Bug: supcomercio1 login redirects to /dashboard/supervisor/min-comercio
--      which is a phantom route (does not exist in the Next.js frontend).
--      Result: blank white page + console error
--      "NotFoundError: Failed to execute 'removeChild' on 'Node'"
--      Reported by user 2026-05-06.
--
-- Root cause: migration 306 wrote hrefs pointing to per-entity supervisor
--      routes (`/dashboard/supervisor/min-comercio`, `/dashboard/supervisor/
--      min-hacienda`, etc.) for the 6 MIN_* supervisor roles, but those
--      pages were never created. Frontend only ships:
--          - /dashboard/supervisor/entity-dashboard      (generic OMS)
--          - /dashboard/supervisor/oms/[...slug]          (catch-all redirect)
--
-- Fix: rewrite the `dashboard` menu item href to point to the existing
--      generic entity-dashboard route. The route auto-detects the
--      supervisor's entity_code (via /agents/profiles/me) and renders the
--      appropriate dashboard.
--
-- Affected roles (6):
--   supervisor_min_comercio
--   supervisor_min_hacienda
--   supervisor_min_informacion
--   supervisor_min_turismo
--   supervisor_min_agricultura
--   supervisor_min_electricidad
--
-- Idempotent: re-running this migration is safe — jsonb_set is idempotent
--      when the target value already matches.
-- ============================================================================

BEGIN;

UPDATE roles
SET menu_config = jsonb_set(
    menu_config,
    '{menus,0,href}',
    '"/dashboard/supervisor/entity-dashboard"'::jsonb
)
WHERE code IN (
    'supervisor_min_comercio',
    'supervisor_min_hacienda',
    'supervisor_min_informacion',
    'supervisor_min_turismo',
    'supervisor_min_agricultura',
    'supervisor_min_electricidad'
)
AND menu_config IS NOT NULL
AND menu_config->'menus'->0->>'id' = 'dashboard';

-- Verification: count rows updated; expected 6 (one per MIN_* supervisor)
DO $$
DECLARE
    v_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_count
    FROM roles
    WHERE code IN (
        'supervisor_min_comercio',
        'supervisor_min_hacienda',
        'supervisor_min_informacion',
        'supervisor_min_turismo',
        'supervisor_min_agricultura',
        'supervisor_min_electricidad'
    )
    AND menu_config->'menus'->0->>'href' = '/dashboard/supervisor/entity-dashboard';

    RAISE NOTICE 'Migration 332: % supervisor_min_* roles now point to entity-dashboard', v_count;
END $$;

COMMIT;
