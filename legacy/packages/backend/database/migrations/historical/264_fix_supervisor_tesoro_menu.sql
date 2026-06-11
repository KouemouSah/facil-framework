-- Migration 175: Remove duplicate stats/agents and stats/sla sidebar entries
-- These are now tabs within the StatsTabNav component on /stats page
-- Also fix supervisor dashboard overview endpoint (current_user["id"] -> current_user.id done in code)

UPDATE roles
SET menu_config = jsonb_set(
  menu_config,
  '{menus}',
  (
    SELECT jsonb_agg(
      CASE
        WHEN menu_item->>'id' = 'reports' THEN
          jsonb_set(
            menu_item,
            '{items}',
            (
              SELECT COALESCE(jsonb_agg(item), '[]'::jsonb)
              FROM jsonb_array_elements(menu_item->'items') item
              WHERE item->>'id' NOT IN ('agent_stats', 'sla')
            )
          )
        ELSE menu_item
      END
    )
    FROM jsonb_array_elements(menu_config->'menus') menu_item
  )
)
WHERE code = 'supervisor_tesoro'
  AND menu_config IS NOT NULL
  AND EXISTS (
    SELECT 1 FROM jsonb_array_elements(menu_config->'menus') m
    WHERE m->>'id' = 'reports'
    AND EXISTS (
      SELECT 1 FROM jsonb_array_elements(m->'items') i
      WHERE i->>'id' IN ('agent_stats', 'sla')
    )
  );
