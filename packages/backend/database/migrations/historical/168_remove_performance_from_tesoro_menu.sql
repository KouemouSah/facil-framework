-- Migration 168: Remove dead "performance" menu item from supervisor_tesoro
-- The performance page was never implemented for treasury supervisors.
-- The menu item points to /dashboard/supervisor/team/performance which does not exist.

-- Remove the "performance" sub-item from the "team" group in supervisor_tesoro menu_config
UPDATE roles
SET menu_config = jsonb_set(
    menu_config,
    '{menus}',
    (
        SELECT jsonb_agg(
            CASE
                WHEN elem->>'id' = 'team' THEN
                    jsonb_set(
                        elem,
                        '{items}',
                        (
                            SELECT jsonb_agg(sub)
                            FROM jsonb_array_elements(elem->'items') AS sub
                            WHERE sub->>'id' != 'performance'
                        )
                    )
                ELSE elem
            END
        )
        FROM jsonb_array_elements(menu_config->'menus') AS elem
    )
),
updated_at = NOW()
WHERE code = 'supervisor_tesoro'
  AND menu_config IS NOT NULL
  AND menu_config->'menus' IS NOT NULL;
