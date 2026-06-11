-- Migration 243: Fix supervisor menus + company permissions
--
-- Problems found during audit:
-- 1. Site Dashboard (/supervisor/companies/dashboard) absent from ALL supervisor menus
-- 2. 4 supervisors (agricultura, electricidad, informacion, turismo) missing companies menu entirely
-- 3. 4 supervisors missing company.view, company.view_entity_scoped, company.view_stats permissions
-- 4. 4 agents missing company.view, company.view_classification permissions

BEGIN;

-- ═══════════════════════════════════════════════════════════════
-- FIX 1: Add company permissions to 4 supervisors that lack them
-- ═══════════════════════════════════════════════════════════════

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.code IN ('supervisor_min_agricultura', 'supervisor_min_electricidad', 'supervisor_min_informacion', 'supervisor_min_turismo')
  AND p.name IN ('company.view', 'company.view_classification', 'company.view_entity_scoped', 'company.view_stats')
ON CONFLICT DO NOTHING;

-- ═══════════════════════════════════════════════════════════════
-- FIX 2: Add company.view + company.view_classification to 4 agents
-- ═══════════════════════════════════════════════════════════════

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.code IN ('agent_min_agricultura', 'agent_min_electricidad', 'agent_min_informacion', 'agent_min_turismo')
  AND p.name IN ('company.view', 'company.view_classification')
ON CONFLICT DO NOTHING;

-- ═══════════════════════════════════════════════════════════════
-- FIX 3: Add site_dashboard to companies menu for 5 supervisors
-- that already have the companies menu but lack the dashboard item
-- ═══════════════════════════════════════════════════════════════

-- For each supervisor with existing companies menu, prepend site_dashboard item
DO $$
DECLARE
  site_dashboard_item jsonb := '{
    "id": "site_dashboard",
    "href": "/dashboard/supervisor/companies/dashboard",
    "icon": "MapPin",
    "titleKey": "supervisor.nav.siteDashboard",
    "permission": "company.view_entity_scoped"
  }'::jsonb;
  role_code text;
  menu_idx int;
BEGIN
  FOR role_code IN
    SELECT r.code FROM roles r
    WHERE r.menu_config IS NOT NULL
      AND r.menu_config::text LIKE '%companies%'
      AND r.menu_config::text NOT LIKE '%companies/dashboard%'
      AND r.code LIKE 'supervisor_%'
  LOOP
    -- Find the index of the companies menu group
    SELECT ordinality - 1 INTO menu_idx
    FROM roles r, jsonb_array_elements(r.menu_config->'menus') WITH ORDINALITY AS elem
    WHERE r.code = role_code AND elem.value->>'id' = 'companies';

    IF menu_idx IS NOT NULL THEN
      -- Prepend site_dashboard as first item in companies.items
      UPDATE roles
      SET menu_config = jsonb_set(
        menu_config,
        ARRAY['menus', menu_idx::text, 'items'],
        site_dashboard_item || (menu_config->'menus'->menu_idx->'items')
      )
      WHERE code = role_code;

      RAISE NOTICE 'Added site_dashboard to % (menu index %)', role_code, menu_idx;
    END IF;
  END LOOP;
END $$;

-- ═══════════════════════════════════════════════════════════════
-- FIX 4: Add entire companies menu block to 4 supervisors that lack it
-- ═══════════════════════════════════════════════════════════════

DO $$
DECLARE
  companies_menu jsonb := '{
    "id": "companies",
    "icon": "Building2",
    "titleKey": "supervisor.nav.companies",
    "items": [
      {
        "id": "site_dashboard",
        "href": "/dashboard/supervisor/companies/dashboard",
        "icon": "MapPin",
        "titleKey": "supervisor.nav.siteDashboard",
        "permission": "company.view_entity_scoped"
      },
      {
        "id": "ministry_dashboard",
        "href": "/dashboard/supervisor/companies/ministry-dashboard",
        "icon": "BarChart3",
        "titleKey": "supervisor.nav.ministryDashboard",
        "permission": "company.view_entity_scoped"
      },
      {
        "id": "companies_list",
        "href": "/dashboard/supervisor/companies",
        "icon": "List",
        "titleKey": "supervisor.nav.companiesList",
        "permission": "company.view_entity_scoped"
      },
      {
        "id": "company_debt",
        "href": "/dashboard/agent/companies/debt",
        "icon": "DollarSign",
        "titleKey": "supervisor.nav.companyDebt",
        "permission": "company.view"
      }
    ]
  }'::jsonb;
  role_code text;
BEGIN
  FOR role_code IN
    SELECT r.code FROM roles r
    WHERE r.code IN ('supervisor_min_agricultura', 'supervisor_min_electricidad', 'supervisor_min_informacion', 'supervisor_min_turismo')
      AND r.menu_config IS NOT NULL
      AND r.menu_config::text NOT LIKE '%companies%'
  LOOP
    UPDATE roles
    SET menu_config = jsonb_set(
      menu_config,
      '{menus}',
      (menu_config->'menus') || companies_menu
    )
    WHERE code = role_code;

    RAISE NOTICE 'Added companies menu block to %', role_code;
  END LOOP;
END $$;

COMMIT;
