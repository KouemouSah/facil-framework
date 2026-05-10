-- Migration 303: Fix OMS menu_config — v2 (unconditional)
--
-- Migration 302 had WHERE ... LIKE guards that assumed migration 272's menu
-- format, but migration 272 used INSERT ON CONFLICT DO NOTHING — so the actual
-- menu_config came from migration 247 which has different URLs. The LIKE guards
-- matched 0 rows and 302 was a no-op.
--
-- This migration replaces menu_config unconditionally for all OMS roles.
-- Idempotent: full replacement produces same result on re-run.
--
-- Also fixes dashboard_config widget duplication (P9).

BEGIN;

-- ============================================================================
-- 1. Payment Validator agents (AYUNTAMIENTO, CAMARA)
-- ============================================================================
UPDATE roles
SET menu_config = '{
  "menus":[
    {"id":"dashboard","href":"/dashboard/agent/oms","icon":"LayoutDashboard","titleKey":"oms.nav.dashboard"},
    {"id":"queue","icon":"ListTodo","titleKey":"oms.nav.obligations","items":[
      {"id":"pending","href":"/dashboard/agent/oms/queue","icon":"Clock","titleKey":"oms.nav.pendingProcessing","permission":"fiscal_service.process_obligations"},
      {"id":"completed","href":"/dashboard/agent/oms/queue/completed","icon":"CheckCircle2","titleKey":"oms.nav.completedObligations","permission":"fiscal_service.view_bundles"}
    ]},
    {"id":"licenses","icon":"Briefcase","titleKey":"oms.nav.licenses","items":[
      {"id":"overview","href":"/dashboard/agent/oms/licenses","icon":"FileCheck","titleKey":"oms.nav.licensesOverview","permission":"fiscal_service.view_bundles"},
      {"id":"compliance","href":"/dashboard/agent/oms/compliance","icon":"ShieldCheck","titleKey":"oms.nav.compliance","permission":"fiscal_service.view_bundles"}
    ]},
    {"id":"companies","icon":"Building2","titleKey":"agent.nav.companies","items":[
      {"id":"company_debt","href":"/dashboard/agent/companies/debt","icon":"DollarSign","titleKey":"agent.nav.companyDebt","permission":"company.view"},
      {"id":"company_lookup","href":"/dashboard/agent/companies/lookup","icon":"Search","titleKey":"agent.nav.companyLookup","permission":"company.view"}
    ]}
  ],
  "source":"role","version":"1.2"
}'::jsonb
WHERE code IN ('agent_ayuntamiento', 'agent_camara');

-- ============================================================================
-- 2. Post-Payment Processor agents (MIN_*, polyvalent)
-- ============================================================================
UPDATE roles
SET menu_config = '{
  "menus":[
    {"id":"dashboard","href":"/dashboard/agent/oms","icon":"LayoutDashboard","titleKey":"oms.nav.dashboard"},
    {"id":"queue","icon":"ListTodo","titleKey":"oms.nav.obligations","items":[
      {"id":"pending","href":"/dashboard/agent/oms/queue","icon":"Clock","titleKey":"oms.nav.pendingProcessing","permission":"fiscal_service.process_obligations"},
      {"id":"completed","href":"/dashboard/agent/oms/queue/completed","icon":"CheckCircle2","titleKey":"oms.nav.completedObligations","permission":"fiscal_service.view_bundles"}
    ]},
    {"id":"licenses","icon":"Briefcase","titleKey":"oms.nav.licenses","items":[
      {"id":"overview","href":"/dashboard/agent/oms/licenses","icon":"FileCheck","titleKey":"oms.nav.licensesOverview","permission":"fiscal_service.view_bundles"},
      {"id":"compliance","href":"/dashboard/agent/oms/compliance","icon":"ShieldCheck","titleKey":"oms.nav.compliance","permission":"fiscal_service.view_bundles"}
    ]},
    {"id":"companies","icon":"Building2","titleKey":"agent.nav.companies","items":[
      {"id":"company_debt","href":"/dashboard/agent/companies/debt","icon":"DollarSign","titleKey":"agent.nav.companyDebt","permission":"company.view"},
      {"id":"company_lookup","href":"/dashboard/agent/companies/lookup","icon":"Search","titleKey":"agent.nav.companyLookup","permission":"company.view"}
    ]}
  ],
  "source":"role","version":"1.2"
}'::jsonb
WHERE code IN (
    'agent_min_comercio', 'agent_min_hacienda', 'agent_min_informacion',
    'agent_min_turismo', 'agent_min_agricultura', 'agent_min_electricidad',
    'agent_oms_polyvalent'
);

-- ============================================================================
-- 3. Payment Validator supervisors (AYUNTAMIENTO, CAMARA)
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
    {"id":"licenses","icon":"Briefcase","titleKey":"oms.nav.licenses","items":[
      {"id":"overview","href":"/dashboard/agent/oms/licenses","icon":"FileCheck","titleKey":"oms.nav.licensesOverview","permission":"fiscal_service.view_bundles"},
      {"id":"compliance","href":"/dashboard/agent/oms/compliance","icon":"ShieldCheck","titleKey":"oms.nav.compliance","permission":"fiscal_service.view_bundles"}
    ]},
    {"id":"companies","icon":"Building2","titleKey":"agent.nav.companies","items":[
      {"id":"company_debt","href":"/dashboard/agent/companies/debt","icon":"DollarSign","titleKey":"agent.nav.companyDebt","permission":"company.view"},
      {"id":"company_lookup","href":"/dashboard/agent/companies/lookup","icon":"Search","titleKey":"agent.nav.companyLookup","permission":"company.view"}
    ]}
  ],
  "source":"role","version":"1.2"
}'::jsonb
WHERE code IN ('supervisor_ayuntamiento', 'supervisor_camara');

-- ============================================================================
-- 4. Post-Payment Processor supervisors (MIN_*)
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
    {"id":"licenses","icon":"Briefcase","titleKey":"oms.nav.licenses","items":[
      {"id":"overview","href":"/dashboard/agent/oms/licenses","icon":"FileCheck","titleKey":"oms.nav.licensesOverview","permission":"fiscal_service.view_bundles"},
      {"id":"compliance","href":"/dashboard/agent/oms/compliance","icon":"ShieldCheck","titleKey":"oms.nav.compliance","permission":"fiscal_service.view_bundles"}
    ]},
    {"id":"companies","icon":"Building2","titleKey":"agent.nav.companies","items":[
      {"id":"company_debt","href":"/dashboard/agent/companies/debt","icon":"DollarSign","titleKey":"agent.nav.companyDebt","permission":"company.view"},
      {"id":"company_lookup","href":"/dashboard/agent/companies/lookup","icon":"Search","titleKey":"agent.nav.companyLookup","permission":"company.view"}
    ]}
  ],
  "source":"role","version":"1.2"
}'::jsonb
WHERE code IN (
    'supervisor_min_comercio', 'supervisor_min_hacienda', 'supervisor_min_informacion',
    'supervisor_min_turismo', 'supervisor_min_agricultura', 'supervisor_min_electricidad'
);

-- ============================================================================
-- 5a. Fix dashboard_config widget duplicate (P9) — AGENTS only
-- oms_overdue_alerts + oms_compliance_summary both render AlertsWidget
-- ONLY update agent roles. Supervisors have different widgets
-- (team_overview, escalations, performance) that must NOT be overwritten.
-- ============================================================================
UPDATE roles
SET dashboard_config = '{
  "layout":"grid","version":"1.1","widgets":[
    {"id":"oms_pending_validations","size":"medium","visible":true,"position":1},
    {"id":"oms_validated_today","size":"medium","visible":true,"position":2},
    {"id":"oms_overdue_alerts","size":"full","visible":true,"position":3}
  ]
}'::jsonb
WHERE code IN ('agent_ayuntamiento', 'agent_camara')
AND dashboard_config IS NOT NULL;

-- 5b. Fix supervisor dashboard_config — remove duplicate but KEEP supervisor widgets
UPDATE roles
SET dashboard_config = '{
  "layout":"grid","version":"1.1","widgets":[
    {"id":"oms_team_overview","size":"full","visible":true,"position":1},
    {"id":"oms_pending_escalations","size":"medium","visible":true,"position":2},
    {"id":"oms_performance_stats","size":"medium","visible":true,"position":3}
  ]
}'::jsonb
WHERE code IN ('supervisor_ayuntamiento', 'supervisor_camara')
AND dashboard_config IS NOT NULL;

-- ============================================================================
-- 6. Grant company.view to MIN_* agents and supervisors
-- Without this permission, the Companies submenu items are hidden by frontend.
-- AYUNT/CAMARA already have this from migration 247. MIN_* don't.
-- Idempotent: ON CONFLICT DO NOTHING.
-- ============================================================================
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.code IN (
    'agent_min_comercio', 'agent_min_hacienda', 'agent_min_informacion',
    'agent_min_turismo', 'agent_min_agricultura', 'agent_min_electricidad',
    'agent_oms_polyvalent',
    'supervisor_min_comercio', 'supervisor_min_hacienda', 'supervisor_min_informacion',
    'supervisor_min_turismo', 'supervisor_min_agricultura', 'supervisor_min_electricidad'
)
AND p.name = 'company.view'
ON CONFLICT DO NOTHING;

-- ============================================================================
-- 7. Invalidate Redis menu cache (best-effort)
-- The menu service caches per agent_profile_id with 5-min TTL.
-- After this migration, agents must wait max 5 min or re-login.
-- ============================================================================

COMMIT;
