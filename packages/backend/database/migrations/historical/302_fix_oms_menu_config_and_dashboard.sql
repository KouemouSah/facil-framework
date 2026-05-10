-- Migration 302: Fix OMS menu_config broken hrefs + dashboard widget duplicate
--
-- P4: Menu "Obligations" pointed to /oms/queue and /oms/queue/completed
--     (404s in migration 272). New Next.js pages now exist at those paths.
--     Fix remaining broken hrefs: /oms/processor → /oms (main page has KPIs),
--     /oms/validator → /oms, /oms/validation → /oms/queue.
--
-- P9: dashboard_config for PV agents (AYUNT/CAMARA) has oms_overdue_alerts +
--     oms_compliance_summary which both render AlertsWidget → remove duplicate.
--
-- Idempotent: WHERE ... LIKE guards prevent double-applying.

BEGIN;

-- ============================================================================
-- P4a: Post-Payment Processor agent menus (agent_min_*, agent_oms_polyvalent)
-- Fix /oms/processor → /oms, keep queue submenu, remove /oms/documents (404)
-- ============================================================================
UPDATE roles
SET menu_config = '{
  "menus":[
    {"id":"dashboard","href":"/dashboard/agent/oms","icon":"LayoutDashboard","titleKey":"oms.nav.dashboard"},
    {"id":"queue","icon":"ListTodo","titleKey":"oms.nav.obligations","items":[
      {"id":"pending","href":"/dashboard/agent/oms/queue","icon":"Clock","titleKey":"oms.nav.pendingProcessing","permission":"fiscal_service.process_obligations"},
      {"id":"completed","href":"/dashboard/agent/oms/queue/completed","icon":"CheckCircle2","titleKey":"oms.nav.completedObligations","permission":"fiscal_service.view_bundles"}
    ]},
    {"id":"licenses","href":"/dashboard/agent/oms/licenses","icon":"Briefcase","titleKey":"oms.nav.licenses","permission":"fiscal_service.view_bundles"},
    {"id":"compliance","href":"/dashboard/agent/oms/compliance","icon":"Shield","titleKey":"oms.nav.compliance","permission":"fiscal_service.view_bundles"}
  ],
  "source":"role","version":"1.1"
}'::jsonb
WHERE code IN (
    'agent_min_comercio', 'agent_min_hacienda', 'agent_min_informacion',
    'agent_min_turismo', 'agent_min_agricultura', 'agent_min_electricidad',
    'agent_oms_polyvalent'
)
AND menu_config IS NOT NULL
AND menu_config::text LIKE '%oms/processor%';

-- ============================================================================
-- P4b: Payment Validator agent menus (agent_ayuntamiento, agent_camara)
-- Fix /oms/validator → /oms, /oms/validation → /oms/queue
-- ============================================================================
UPDATE roles
SET menu_config = '{
  "menus":[
    {"id":"dashboard","href":"/dashboard/agent/oms","icon":"LayoutDashboard","titleKey":"oms.nav.dashboard"},
    {"id":"queue","icon":"ListTodo","titleKey":"oms.nav.obligations","items":[
      {"id":"pending","href":"/dashboard/agent/oms/queue","icon":"Clock","titleKey":"oms.nav.pendingProcessing","permission":"fiscal_service.process_obligations"},
      {"id":"completed","href":"/dashboard/agent/oms/queue/completed","icon":"CheckCircle2","titleKey":"oms.nav.completedObligations","permission":"fiscal_service.view_bundles"}
    ]},
    {"id":"licenses","href":"/dashboard/agent/oms/licenses","icon":"Briefcase","titleKey":"oms.nav.licenses","permission":"fiscal_service.view_bundles"},
    {"id":"compliance","href":"/dashboard/agent/oms/compliance","icon":"Shield","titleKey":"oms.nav.compliance","permission":"fiscal_service.view_bundles"}
  ],
  "source":"role","version":"1.1"
}'::jsonb
WHERE code IN ('agent_ayuntamiento', 'agent_camara')
AND menu_config IS NOT NULL
AND menu_config::text LIKE '%oms/valid%';

-- ============================================================================
-- P4c: Post-Payment Processor supervisor menus (supervisor_min_*)
-- Fix /oms/queue hrefs, keep team + supervisor dashboard
-- ============================================================================
UPDATE roles
SET menu_config = '{
  "menus":[
    {"id":"dashboard","href":"/dashboard/supervisor/oms","icon":"LayoutDashboard","titleKey":"oms.nav.dashboard"},
    {"id":"queue","icon":"ListTodo","titleKey":"oms.nav.obligations","items":[
      {"id":"pending","href":"/dashboard/agent/oms/queue","icon":"Clock","titleKey":"oms.nav.pendingProcessing","permission":"fiscal_service.process_obligations"},
      {"id":"completed","href":"/dashboard/agent/oms/queue/completed","icon":"CheckCircle2","titleKey":"oms.nav.completedObligations","permission":"fiscal_service.view_bundles"}
    ]},
    {"id":"team","icon":"Users","titleKey":"supervisor.nav.team","items":[
      {"id":"agents","href":"/dashboard/supervisor/team/agents","icon":"User","titleKey":"supervisor.nav.agents","permission":"agent.list"},
      {"id":"workload","href":"/dashboard/supervisor/team/workload","icon":"BarChart2","titleKey":"supervisor.nav.workload","permission":"agent.view_workload"}
    ]},
    {"id":"licenses","href":"/dashboard/agent/oms/licenses","icon":"Briefcase","titleKey":"oms.nav.licenses","permission":"fiscal_service.view_bundles"}
  ],
  "source":"role","version":"1.1"
}'::jsonb
WHERE code IN (
    'supervisor_min_comercio', 'supervisor_min_hacienda', 'supervisor_min_informacion',
    'supervisor_min_turismo', 'supervisor_min_agricultura', 'supervisor_min_electricidad'
)
AND menu_config IS NOT NULL
AND menu_config::text LIKE '%oms/queue%';

-- ============================================================================
-- P4d: Payment Validator supervisor menus (supervisor_ayuntamiento, supervisor_camara)
-- Fix /oms/validation hrefs, keep team + supervisor dashboard
-- ============================================================================
UPDATE roles
SET menu_config = '{
  "menus":[
    {"id":"dashboard","href":"/dashboard/supervisor/oms","icon":"LayoutDashboard","titleKey":"oms.nav.dashboard"},
    {"id":"queue","icon":"ListTodo","titleKey":"oms.nav.obligations","items":[
      {"id":"pending","href":"/dashboard/agent/oms/queue","icon":"Clock","titleKey":"oms.nav.pendingProcessing","permission":"fiscal_service.process_obligations"},
      {"id":"completed","href":"/dashboard/agent/oms/queue/completed","icon":"CheckCircle2","titleKey":"oms.nav.completedObligations","permission":"fiscal_service.view_bundles"}
    ]},
    {"id":"team","icon":"Users","titleKey":"supervisor.nav.team","items":[
      {"id":"agents","href":"/dashboard/supervisor/team/agents","icon":"User","titleKey":"supervisor.nav.agents","permission":"agent.list"},
      {"id":"workload","href":"/dashboard/supervisor/team/workload","icon":"BarChart2","titleKey":"supervisor.nav.workload","permission":"agent.view_workload"}
    ]},
    {"id":"licenses","href":"/dashboard/agent/oms/licenses","icon":"Briefcase","titleKey":"oms.nav.licenses","permission":"fiscal_service.view_bundles"}
  ],
  "source":"role","version":"1.1"
}'::jsonb
WHERE code IN ('supervisor_ayuntamiento', 'supervisor_camara')
AND menu_config IS NOT NULL
AND menu_config::text LIKE '%oms/valid%';

-- ============================================================================
-- P9: Remove duplicate widget from PV dashboard_config
-- oms_overdue_alerts + oms_compliance_summary both render AlertsWidget.
-- Keep oms_overdue_alerts (position 3), drop oms_compliance_summary.
-- ============================================================================
UPDATE roles
SET dashboard_config = '{
  "layout":"grid","version":"1.1","widgets":[
    {"id":"oms_pending_validations","size":"medium","visible":true,"position":1},
    {"id":"oms_validated_today","size":"medium","visible":true,"position":2},
    {"id":"oms_overdue_alerts","size":"full","visible":true,"position":3}
  ]
}'::jsonb
WHERE code IN ('agent_ayuntamiento', 'agent_camara', 'supervisor_ayuntamiento', 'supervisor_camara')
AND dashboard_config IS NOT NULL
AND dashboard_config::text LIKE '%oms_compliance_summary%';

COMMIT;
