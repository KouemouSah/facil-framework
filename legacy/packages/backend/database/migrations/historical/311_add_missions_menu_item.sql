-- Migration 311: Add missions menu item to supervisor inspection menus
--
-- Adds "Missions" entry in the inspection_supervision menu group.
-- Uses 'menus' key (not 'items') matching actual menu_config structure.
-- Safe: only adds if missions_hub not already present.
--
-- NOTE: Applied directly via Python script on 2026-04-24 for all 9 supervisor roles.
-- This SQL is kept for documentation and future environments.

BEGIN;

-- For each supervisor role that has inspection_supervision but not missions_hub:
UPDATE roles
SET menu_config = jsonb_set(
    menu_config,
    '{menus}',
    (
        SELECT jsonb_agg(
            CASE
                WHEN item->>'id' = 'inspection_supervision' THEN
                    jsonb_set(
                        item,
                        '{items}',
                        COALESCE(item->'items', '[]'::jsonb) || '[{"id":"missions_hub","href":"/dashboard/supervisor/inspections/missions","icon":"CalendarDays","titleKey":"inspection.nav.missions","permission":"inspection.manage_missions"}]'::jsonb
                    )
                ELSE item
            END
        )
        FROM jsonb_array_elements(menu_config->'menus') AS item
    )
)
WHERE code IN (
    'supervisor_ayuntamiento', 'supervisor_camara',
    'supervisor_min_comercio', 'supervisor_min_hacienda',
    'supervisor_min_informacion', 'supervisor_min_turismo',
    'supervisor_min_agricultura', 'supervisor_min_electricidad',
    'supervisor_tesoro'
)
AND menu_config IS NOT NULL
AND menu_config->'menus' IS NOT NULL
AND NOT (menu_config::text LIKE '%missions_hub%');

COMMIT;
