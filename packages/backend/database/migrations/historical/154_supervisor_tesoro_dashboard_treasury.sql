-- Migration 154: Make Vista General Tesorería the supervisor's home page
--
-- Problem: supervisor_tesoro has:
--   dashboard → /dashboard/supervisor (generic supervisor page)
--   treasury_overview → /dashboard/agent/treasury (custom treasury page)
-- The Vista General is a separate menu item, not the home page.
-- The initial redirect lands on an orphan generic entity page.
--
-- Solution:
--   1. Change dashboard href → /dashboard/agent/treasury (Vista General = Panel de Control)
--   2. Remove treasury_overview menu item (now redundant)

-- Step 1: Change dashboard href to treasury page
UPDATE roles
SET menu_config = jsonb_set(
    menu_config,
    '{menus,0,href}',
    '"/dashboard/agent/treasury"'::jsonb
)
WHERE code = 'supervisor_tesoro'
  AND menu_config->'menus'->0->>'id' = 'dashboard'
  AND menu_config->'menus'->0->>'href' = '/dashboard/supervisor';

-- Step 2: Remove treasury_overview menu item (index 1)
-- Use jsonb array manipulation: rebuild menus array without the treasury_overview item
UPDATE roles
SET menu_config = jsonb_set(
    menu_config,
    '{menus}',
    (
        SELECT jsonb_agg(elem)
        FROM jsonb_array_elements(menu_config->'menus') AS elem
        WHERE elem->>'id' != 'treasury_overview'
    )
)
WHERE code = 'supervisor_tesoro'
  AND EXISTS (
    SELECT 1 FROM jsonb_array_elements(menu_config->'menus') AS elem
    WHERE elem->>'id' = 'treasury_overview'
  );
