-- Migration 144: Add AI Analyst menu item to supervisor_tesoro and agent_tesoro roles
-- Phase 4 of Treasury Dashboard Pilotage plan

-- Add analyst menu item to supervisor_tesoro under "reports" section
UPDATE roles
SET menu_config = jsonb_set(
  menu_config,
  '{menus}',
  (
    SELECT jsonb_agg(
      CASE
        WHEN elem->>'id' = 'reports' THEN
          jsonb_set(
            elem,
            '{items}',
            (elem->'items') || jsonb_build_object(
              'id', 'analyst',
              'href', '/dashboard/agent/treasury/analyst',
              'icon', 'Sparkles',
              'titleKey', 'treasury.analyst.nav',
              'permission', 'treasury_stat.view'
            )
          )
        ELSE elem
      END
    )
    FROM jsonb_array_elements(menu_config->'menus') AS elem
  )
)
WHERE code = 'supervisor_tesoro'
  AND menu_config IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM jsonb_array_elements(menu_config->'menus') AS m,
                  jsonb_array_elements(m->'items') AS item
    WHERE m->>'id' = 'reports' AND item->>'id' = 'analyst'
  );

-- Add analyst as a top-level menu item for agent_tesoro (they have fewer menus)
UPDATE roles
SET menu_config = jsonb_set(
  menu_config,
  '{menus}',
  (menu_config->'menus') || jsonb_build_array(
    jsonb_build_object(
      'id', 'analyst',
      'href', '/dashboard/agent/treasury/analyst',
      'icon', 'Sparkles',
      'titleKey', 'treasury.analyst.nav',
      'permission', 'treasury_stat.view'
    )
  )
)
WHERE code = 'agent_tesoro'
  AND menu_config IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM jsonb_array_elements(menu_config->'menus') AS m
    WHERE m->>'id' = 'analyst'
  );
