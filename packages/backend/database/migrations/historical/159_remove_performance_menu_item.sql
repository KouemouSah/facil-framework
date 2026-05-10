-- ================================================================
-- Migration 159: Remove "Rendimiento" (performance) menu item
--
-- Reason: Page has zero operational value for supervisors:
--   - agent_workflow_proficiency: 0 rows (never populated)
--   - 3/5 sections completely empty
--   - 2/5 sections duplicate team/workload page
--   - Designed for multi-workflow entities, not single-workflow treasury
--   - All useful metrics already on team/workload (sortable + export)
--
-- Removes from: supervisor, supervisor_tesoro menu_config
-- ================================================================

-- Remove "performance" item from supervisor role's team submenu
UPDATE roles
SET menu_config = jsonb_set(
    menu_config,
    '{menus}',
    (
        SELECT jsonb_agg(
            CASE
                WHEN menu_item->>'id' = 'team' THEN
                    jsonb_set(
                        menu_item,
                        '{items}',
                        (
                            SELECT COALESCE(jsonb_agg(item), '[]'::jsonb)
                            FROM jsonb_array_elements(menu_item->'items') item
                            WHERE item->>'id' != 'performance'
                        )
                    )
                ELSE menu_item
            END
        )
        FROM jsonb_array_elements(menu_config->'menus') menu_item
    )
),
updated_at = NOW()
WHERE code IN ('supervisor', 'supervisor_tesoro')
  AND menu_config IS NOT NULL
  AND menu_config->'menus' IS NOT NULL;
