-- Migration 153: Redirect agent_tesoro dashboard to generic entity page
--
-- Problem: Both agent_tesoro and supervisor_tesoro land on /dashboard/agent/treasury
-- which is the custom supervisor dashboard. This causes:
-- 1. Agents see supervisor skeletons that fail (403) then fall back to widgets
-- 2. DynamicDashboard widgets duplicate between generic entity page and treasury page
--
-- Solution: Point agent_tesoro dashboard to /dashboard/agent/tesoro (generic entity page)
-- so the custom treasury page becomes supervisor-only.

UPDATE roles
SET menu_config = jsonb_set(
    menu_config,
    '{menus,0,href}',
    '"/dashboard/agent/tesoro"'::jsonb
)
WHERE code = 'agent_tesoro'
  AND menu_config->'menus'->0->>'id' = 'dashboard'
  AND menu_config->'menus'->0->>'href' = '/dashboard/agent/treasury';
