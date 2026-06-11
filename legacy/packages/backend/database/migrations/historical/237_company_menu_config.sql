-- Migration 237: Add company menus to role configurations
--
-- Strategy: Keep dynamic menus intact. Only ADD empresa entries where needed.
-- - Module-based roles (agent_tesoro, etc.): append to existing menu_config.menus
-- - Workflow-based roles (agent_onrc, supervisor_onrc): add via workflow_menu_mapping
--
-- VERIFIED: ministry agents/supervisors have menu_config with menus array
-- VERIFIED: agent_onrc/supervisor_onrc use workflow-based menus (menu_config IS NULL)

BEGIN;

-- ═══════════════════════════════════════════════════════════════════
-- 1. Ministry agents (module-based): append empresa menu to existing menus
-- ═══════════════════════════════════════════════════════════════════

UPDATE roles
SET menu_config = jsonb_set(
    menu_config,
    '{menus}',
    (menu_config->'menus') || jsonb_build_array(
        jsonb_build_object(
            'id', 'companies',
            'icon', 'Building2',
            'titleKey', 'agent.nav.companies',
            'items', jsonb_build_array(
                jsonb_build_object(
                    'id', 'company_debt',
                    'href', '/dashboard/agent/companies/debt',
                    'icon', 'DollarSign',
                    'titleKey', 'agent.nav.companyDebt',
                    'permission', 'company.view'
                ),
                jsonb_build_object(
                    'id', 'company_lookup',
                    'href', '/dashboard/agent/companies/lookup',
                    'icon', 'Search',
                    'titleKey', 'agent.nav.companyLookup',
                    'permission', 'company.view'
                )
            )
        )
    ),
    '{version}',
    '"3.0"'::jsonb
)
WHERE code IN ('agent_tesoro', 'agent_ayuntamiento', 'agent_camara',
               'agent_min_hacienda', 'agent_min_comercio')
  AND menu_config IS NOT NULL
  AND NOT (menu_config::text LIKE '%company_debt%');

-- ═══════════════════════════════════════════════════════════════════
-- 2. Ministry supervisors (module-based): append empresa dashboard menu
-- ═══════════════════════════════════════════════════════════════════

UPDATE roles
SET menu_config = jsonb_set(
    menu_config,
    '{menus}',
    (menu_config->'menus') || jsonb_build_array(
        jsonb_build_object(
            'id', 'companies',
            'icon', 'Building2',
            'titleKey', 'supervisor.nav.companies',
            'items', jsonb_build_array(
                jsonb_build_object(
                    'id', 'ministry_dashboard',
                    'href', '/dashboard/supervisor/companies/ministry-dashboard',
                    'icon', 'BarChart3',
                    'titleKey', 'supervisor.nav.ministryDashboard',
                    'permission', 'company.view_entity_scoped'
                ),
                jsonb_build_object(
                    'id', 'companies_list',
                    'href', '/dashboard/supervisor/companies',
                    'icon', 'List',
                    'titleKey', 'supervisor.nav.companiesList',
                    'permission', 'company.view_entity_scoped'
                ),
                jsonb_build_object(
                    'id', 'company_debt',
                    'href', '/dashboard/agent/companies/debt',
                    'icon', 'DollarSign',
                    'titleKey', 'supervisor.nav.companyDebt',
                    'permission', 'company.view'
                )
            )
        )
    ),
    '{version}',
    '"3.0"'::jsonb
)
WHERE code IN ('supervisor_tesoro', 'supervisor_ayuntamiento', 'supervisor_camara',
               'supervisor_min_hacienda', 'supervisor_min_comercio')
  AND menu_config IS NOT NULL
  AND NOT (menu_config::text LIKE '%ministry_dashboard%');

-- ═══════════════════════════════════════════════════════════════════
-- 3. ONRC agent/supervisor (workflow-based): add via workflow_menu_mapping
--    These roles keep their dynamic menus — we add a company entry
-- ═══════════════════════════════════════════════════════════════════

INSERT INTO workflow_menu_mapping (
    workflow_pattern, menu_group_id, menu_title_key, menu_icon,
    display_order, include_pending, include_validation, include_appointments,
    include_history, permission_prefix, is_active, custom_sub_items
)
VALUES (
    'EMPRESA_%',
    'empresas',
    'agent.nav.companies',
    'Building2',
    10,
    false,
    false,
    false,
    false,
    'company',
    true,
    jsonb_build_array(
        jsonb_build_object(
            'id', 'lookup',
            'icon', 'Search',
            'action', 'lookup',
            'is_active', true,
            'title_key', 'agent.nav.companyLookup',
            'display_order', 1,
            'href', '/dashboard/agent/companies/lookup'
        ),
        jsonb_build_object(
            'id', 'companies_list',
            'icon', 'List',
            'action', 'list',
            'is_active', true,
            'title_key', 'agent.nav.companiesList',
            'display_order', 2,
            'href', '/dashboard/supervisor/companies'
        )
    )
)
ON CONFLICT DO NOTHING;

-- ═══════════════════════════════════════════════════════════════════
-- 4. i18n keys for menu navigation (stored in translations table)
-- ═══════════════════════════════════════════════════════════════════

-- Note: i18n keys are defined in messages/es|en|fr.json files.
-- The keys used above: agent.nav.companies, agent.nav.companyDebt,
-- agent.nav.companyLookup, supervisor.nav.companies,
-- supervisor.nav.ministryDashboard, supervisor.nav.companiesList

COMMIT;
