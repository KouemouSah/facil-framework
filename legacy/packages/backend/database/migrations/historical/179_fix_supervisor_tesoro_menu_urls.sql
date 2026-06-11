-- Migration 179: Fix supervisor_tesoro menu_config — manual assignment URL
-- Problem: "Asignación Manual" points to /dashboard/admin/assignments/new/manual
-- but that page does NOT exist. The correct page is at /dashboard/supervisor/assignments/manual
-- Result: clicking "Asignación Manual" shows a blank white page

UPDATE roles
SET menu_config = jsonb_set(
  menu_config,
  '{menus}',
  (
    SELECT jsonb_agg(
      CASE
        WHEN menu_item->>'id' = 'assignments' THEN
          jsonb_set(
            menu_item,
            '{items}',
            (
              SELECT jsonb_agg(
                CASE
                  WHEN sub_item->>'id' = 'manual' THEN
                    jsonb_set(sub_item, '{href}', '"/dashboard/supervisor/assignments/manual"'::jsonb)
                  ELSE sub_item
                END
              )
              FROM jsonb_array_elements(menu_item->'items') AS sub_item
            )
          )
        ELSE menu_item
      END
    )
    FROM jsonb_array_elements(menu_config->'menus') AS menu_item
  )
),
updated_at = NOW()
WHERE code = 'supervisor_tesoro'
  AND menu_config IS NOT NULL
  AND menu_config::text LIKE '%admin/assignments/new/manual%';
