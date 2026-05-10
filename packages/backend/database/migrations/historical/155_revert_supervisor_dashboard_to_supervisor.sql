-- Migration 155: Revert supervisor_tesoro dashboard to /dashboard/supervisor
--
-- Migration 154 changed dashboard → /dashboard/agent/treasury and removed treasury_overview.
-- New plan: The supervisor dashboard page at /dashboard/supervisor will be ENHANCED
-- with treasury charts directly. No need for a separate Vista General menu item (Option A).
--
-- This migration:
--   1. Reverts dashboard href back to /dashboard/supervisor
--   2. Does NOT re-add treasury_overview (all content now in the enhanced supervisor dashboard)

UPDATE roles
SET menu_config = jsonb_set(
    menu_config,
    '{menus,0,href}',
    '"/dashboard/supervisor"'::jsonb
)
WHERE code = 'supervisor_tesoro'
  AND menu_config->'menus'->0->>'id' = 'dashboard'
  AND menu_config->'menus'->0->>'href' = '/dashboard/agent/treasury';
