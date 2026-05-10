-- Migration 247: Fix OMS Menu Configs — Align with existing pages
-- Date: 2026-03-21
-- Problem: menu_config JSON points to 9+ pages that DON'T EXIST
-- Fix: Update all OMS agent/supervisor menus to point to REAL pages only
--
-- Existing pages:
--   /dashboard/agent/oms                     (queue)
--   /dashboard/agent/oms/licenses            (license list)
--   /dashboard/agent/oms/licenses/[id]       (license detail)
--   /dashboard/agent/oms/compliance          (compliance by fee_type)
--   /dashboard/supervisor/oms/team           (team performance)
--   /dashboard/supervisor/team/agents        (agent list)
--   /dashboard/supervisor/team/workload      (workload)
--   /dashboard/supervisor/escalations/pending (escalations)
--   /dashboard/supervisor/companies/dashboard (site dashboard)
--   /dashboard/supervisor/companies/ministry-dashboard (ministry dashboard)
--   /dashboard/supervisor/companies          (company list)
--   /dashboard/agent/companies/debt          (company debt)
--   /dashboard/agent/companies/lookup        (company lookup)

-- ============================================================
-- 1. AGENT VALIDATOR roles (ayuntamiento, camara)
-- ============================================================

UPDATE roles SET menu_config = '{
  "menus": [
    {
      "id": "dashboard",
      "href": "/dashboard/agent/oms",
      "icon": "LayoutDashboard",
      "titleKey": "oms.nav.dashboard"
    },
    {
      "id": "oms",
      "icon": "ClipboardList",
      "titleKey": "oms.nav.obligations",
      "items": [
        {
          "id": "oms_queue",
          "href": "/dashboard/agent/oms",
          "icon": "Clock",
          "titleKey": "oms.nav.queue",
          "permission": "fiscal_service.process_obligations"
        },
        {
          "id": "oms_licenses",
          "href": "/dashboard/agent/oms/licenses",
          "icon": "FileCheck",
          "titleKey": "oms.nav.licensesOverview",
          "permission": "fiscal_service.view_bundles"
        },
        {
          "id": "oms_compliance",
          "href": "/dashboard/agent/oms/compliance",
          "icon": "ShieldCheck",
          "titleKey": "oms.nav.compliance",
          "permission": "fiscal_service.view_bundles"
        }
      ]
    },
    {
      "id": "companies",
      "icon": "Building2",
      "titleKey": "agent.nav.companies",
      "items": [
        {
          "id": "company_debt",
          "href": "/dashboard/agent/companies/debt",
          "icon": "DollarSign",
          "titleKey": "agent.nav.companyDebt",
          "permission": "company.view"
        },
        {
          "id": "company_lookup",
          "href": "/dashboard/agent/companies/lookup",
          "icon": "Search",
          "titleKey": "agent.nav.companyLookup",
          "permission": "company.view"
        }
      ]
    }
  ],
  "source": "role",
  "version": "2.0"
}'::jsonb
WHERE code IN ('agent_ayuntamiento', 'agent_camara');

-- ============================================================
-- 2. AGENT PROCESSOR roles (min_*, polyvalent)
-- ============================================================

UPDATE roles SET menu_config = '{
  "menus": [
    {
      "id": "dashboard",
      "href": "/dashboard/agent/oms",
      "icon": "LayoutDashboard",
      "titleKey": "oms.nav.dashboard"
    },
    {
      "id": "oms",
      "icon": "ClipboardList",
      "titleKey": "oms.nav.obligations",
      "items": [
        {
          "id": "oms_queue",
          "href": "/dashboard/agent/oms",
          "icon": "Clock",
          "titleKey": "oms.nav.queue",
          "permission": "fiscal_service.process_obligations"
        },
        {
          "id": "oms_licenses",
          "href": "/dashboard/agent/oms/licenses",
          "icon": "FileCheck",
          "titleKey": "oms.nav.licensesOverview",
          "permission": "fiscal_service.view_bundles"
        },
        {
          "id": "oms_compliance",
          "href": "/dashboard/agent/oms/compliance",
          "icon": "ShieldCheck",
          "titleKey": "oms.nav.compliance",
          "permission": "fiscal_service.view_bundles"
        }
      ]
    },
    {
      "id": "companies",
      "icon": "Building2",
      "titleKey": "agent.nav.companies",
      "items": [
        {
          "id": "company_debt",
          "href": "/dashboard/agent/companies/debt",
          "icon": "DollarSign",
          "titleKey": "agent.nav.companyDebt",
          "permission": "company.view"
        },
        {
          "id": "company_lookup",
          "href": "/dashboard/agent/companies/lookup",
          "icon": "Search",
          "titleKey": "agent.nav.companyLookup",
          "permission": "company.view"
        }
      ]
    }
  ],
  "source": "role",
  "version": "2.0"
}'::jsonb
WHERE code IN (
  'agent_min_comercio', 'agent_min_hacienda', 'agent_min_informacion',
  'agent_min_turismo', 'agent_min_agricultura', 'agent_min_electricidad',
  'agent_oms_polyvalent'
);

-- ============================================================
-- 3. SUPERVISOR OMS roles (ayuntamiento, camara, min_*)
-- ============================================================

UPDATE roles SET menu_config = '{
  "menus": [
    {
      "id": "dashboard",
      "href": "/dashboard/agent/oms",
      "icon": "LayoutDashboard",
      "titleKey": "oms.nav.dashboard"
    },
    {
      "id": "team",
      "icon": "Users",
      "titleKey": "supervisor.nav.team",
      "items": [
        {
          "id": "oms_team",
          "href": "/dashboard/supervisor/oms/team",
          "icon": "BarChart2",
          "titleKey": "oms.nav.team",
          "permission": "fiscal_service.process_obligations"
        },
        {
          "id": "agents",
          "href": "/dashboard/supervisor/team/agents",
          "icon": "User",
          "titleKey": "supervisor.nav.agents",
          "permission": "agent.list"
        },
        {
          "id": "workload",
          "href": "/dashboard/supervisor/team/workload",
          "icon": "BarChart2",
          "titleKey": "supervisor.nav.workload",
          "permission": "agent.view_workload"
        }
      ]
    },
    {
      "id": "oms",
      "icon": "ClipboardList",
      "titleKey": "oms.nav.obligations",
      "items": [
        {
          "id": "oms_queue",
          "href": "/dashboard/agent/oms",
          "icon": "Clock",
          "titleKey": "oms.nav.queue",
          "permission": "fiscal_service.process_obligations"
        },
        {
          "id": "oms_licenses",
          "href": "/dashboard/agent/oms/licenses",
          "icon": "FileCheck",
          "titleKey": "oms.nav.licensesOverview",
          "permission": "fiscal_service.view_bundles"
        },
        {
          "id": "oms_compliance",
          "href": "/dashboard/agent/oms/compliance",
          "icon": "ShieldCheck",
          "titleKey": "oms.nav.compliance",
          "permission": "fiscal_service.view_bundles"
        }
      ]
    },
    {
      "id": "escalations",
      "href": "/dashboard/supervisor/escalations/pending",
      "icon": "AlertTriangle",
      "titleKey": "oms.nav.escalations",
      "permission": "queue.escalate"
    },
    {
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
    }
  ],
  "source": "role",
  "version": "2.0"
}'::jsonb
WHERE code IN (
  'supervisor_ayuntamiento', 'supervisor_camara',
  'supervisor_min_comercio', 'supervisor_min_hacienda', 'supervisor_min_informacion',
  'supervisor_min_turismo', 'supervisor_min_agricultura', 'supervisor_min_electricidad'
);

-- ============================================================
-- 4. SUPERVISOR TESORO (polyvalent supervisor — national scope)
-- Keep existing treasury menu + add OMS section
-- ============================================================

UPDATE roles SET menu_config = jsonb_set(
  menu_config,
  '{menus}',
  menu_config->'menus' || '[
    {
      "id": "oms",
      "icon": "ClipboardList",
      "titleKey": "oms.nav.obligations",
      "items": [
        {
          "id": "oms_queue",
          "href": "/dashboard/agent/oms",
          "icon": "Clock",
          "titleKey": "oms.nav.queue",
          "permission": "fiscal_service.process_obligations"
        },
        {
          "id": "oms_team",
          "href": "/dashboard/supervisor/oms/team",
          "icon": "BarChart2",
          "titleKey": "oms.nav.team",
          "permission": "fiscal_service.process_obligations"
        },
        {
          "id": "oms_licenses",
          "href": "/dashboard/agent/oms/licenses",
          "icon": "FileCheck",
          "titleKey": "oms.nav.licensesOverview",
          "permission": "fiscal_service.view_bundles"
        },
        {
          "id": "oms_compliance",
          "href": "/dashboard/agent/oms/compliance",
          "icon": "ShieldCheck",
          "titleKey": "oms.nav.compliance",
          "permission": "fiscal_service.view_bundles"
        }
      ]
    }
  ]'::jsonb
)
WHERE code = 'supervisor_tesoro'
  AND NOT EXISTS (
    SELECT 1 FROM jsonb_array_elements(menu_config->'menus') m
    WHERE m->>'id' = 'oms'
  );

-- ============================================================
-- Verification
-- ============================================================

DO $$
DECLARE
    v_broken_count int;
    v_fixed_count int;
BEGIN
    -- Count roles with broken links (old version)
    SELECT COUNT(*) INTO v_broken_count
    FROM roles r,
         jsonb_array_elements(r.menu_config->'menus') m
    WHERE (m->>'href' LIKE '%/validator%'
        OR m->>'href' LIKE '%/processor%'
        OR m->>'href' LIKE '%/queue/completed%'
        OR m->>'href' LIKE '%/oms/documents%'
        OR m->>'href' LIKE '%/oms/validation%')
      AND r.code LIKE 'agent_%' OR r.code LIKE 'supervisor_%';

    -- Count roles with v2.0 menus
    SELECT COUNT(*) INTO v_fixed_count
    FROM roles r
    WHERE r.menu_config->>'version' = '2.0'
      AND r.code LIKE '%ayuntamiento%' OR r.code LIKE '%camara%'
      OR r.code LIKE 'agent_min_%' OR r.code LIKE 'supervisor_min_%'
      OR r.code = 'agent_oms_polyvalent';

    RAISE NOTICE '=== Migration 247 Verification ===';
    RAISE NOTICE 'Broken menu links remaining: %', v_broken_count;
    RAISE NOTICE 'Roles with v2.0 menus: %', v_fixed_count;

    IF v_broken_count > 0 THEN
        RAISE WARNING 'Some broken links remain — manual check needed';
    END IF;
END $$;
