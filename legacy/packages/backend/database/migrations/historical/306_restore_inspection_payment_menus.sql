-- Migration 305: Restore inspection + payment validation menus
--
-- Migration 303 did a full SET of menu_config, destroying menus that were
-- appended by migration 249 (field_inspections) and should-have-been-added
-- by migration 294 (treasury validation for AYUNT/CAMARA).
--
-- This migration restores the COMPLETE menu for all 17 OMS roles:
-- - AYUNT/CAMARA agents: entity dashboard + treasury validation + OMS queue + inspections + companies
-- - MIN_* agents: OMS dashboard + OMS queue + inspections + companies
-- - AYUNT/CAMARA supervisors: supervisor dashboard + team + validation + OMS + inspection supervision + companies
-- - MIN_* supervisors: supervisor dashboard + team + OMS + inspection supervision + companies

BEGIN;

-- ============================================================================
-- 1. AYUNTAMIENTO/CAMARA agents — FULL menu (payment validators + OMS + inspections)
-- ============================================================================

UPDATE roles
SET menu_config = '{
  "menus":[
    {"id":"dashboard","href":"/dashboard/agent/ayuntamiento","icon":"LayoutDashboard","titleKey":"oms.nav.dashboard"},
    {"id":"validation","icon":"CreditCard","titleKey":"treasury.nav.validation","items":[
      {"id":"pending","href":"/dashboard/agent/treasury/validation","icon":"CheckCircle","titleKey":"treasury.nav.validation","permission":"treasury.validate_payment"},
      {"id":"history","href":"/dashboard/agent/treasury/validation/history","icon":"History","titleKey":"treasury.nav.transactions","permission":"treasury.validate_payment"}
    ]},
    {"id":"queue","icon":"ListTodo","titleKey":"oms.nav.obligations","items":[
      {"id":"oms_pending","href":"/dashboard/agent/oms/queue","icon":"Clock","titleKey":"oms.nav.pendingProcessing","permission":"fiscal_service.process_obligations"},
      {"id":"oms_completed","href":"/dashboard/agent/oms/queue/completed","icon":"CheckCircle2","titleKey":"oms.nav.completedObligations","permission":"fiscal_service.view_bundles"}
    ]},
    {"id":"licenses","icon":"Briefcase","titleKey":"oms.nav.licenses","items":[
      {"id":"overview","href":"/dashboard/agent/oms/licenses","icon":"FileCheck","titleKey":"oms.nav.licensesOverview","permission":"fiscal_service.view_bundles"},
      {"id":"compliance","href":"/dashboard/agent/oms/compliance","icon":"ShieldCheck","titleKey":"oms.nav.compliance","permission":"fiscal_service.view_bundles"}
    ]},
    {"id":"field_inspections","icon":"ClipboardCheck","titleKey":"inspection.nav.inspections","items":[
      {"id":"field_dashboard","href":"/dashboard/agent/oms/field","icon":"Activity","titleKey":"inspection.nav.dashboard","permission":"inspection.view_own"},
      {"id":"field_scan","href":"/dashboard/agent/oms/field/scan","icon":"QrCode","titleKey":"inspection.nav.scan","permission":"inspection.create"},
      {"id":"field_reconcile","href":"/dashboard/agent/oms/field/reconcile","icon":"Wallet","titleKey":"inspection.nav.reconcile","permission":"inspection.collect_payment"}
    ]},
    {"id":"companies","icon":"Building2","titleKey":"agent.nav.companies","items":[
      {"id":"company_debt","href":"/dashboard/agent/companies/debt","icon":"DollarSign","titleKey":"agent.nav.companyDebt","permission":"company.view"},
      {"id":"company_lookup","href":"/dashboard/agent/companies/lookup","icon":"Search","titleKey":"agent.nav.companyLookup","permission":"company.view"}
    ]}
  ],
  "source":"role","version":"1.3"
}'::jsonb
WHERE code = 'agent_ayuntamiento';

UPDATE roles
SET menu_config = '{
  "menus":[
    {"id":"dashboard","href":"/dashboard/agent/camara-comercio","icon":"LayoutDashboard","titleKey":"oms.nav.dashboard"},
    {"id":"validation","icon":"CreditCard","titleKey":"treasury.nav.validation","items":[
      {"id":"pending","href":"/dashboard/agent/treasury/validation","icon":"CheckCircle","titleKey":"treasury.nav.validation","permission":"treasury.validate_payment"},
      {"id":"history","href":"/dashboard/agent/treasury/validation/history","icon":"History","titleKey":"treasury.nav.transactions","permission":"treasury.validate_payment"}
    ]},
    {"id":"queue","icon":"ListTodo","titleKey":"oms.nav.obligations","items":[
      {"id":"oms_pending","href":"/dashboard/agent/oms/queue","icon":"Clock","titleKey":"oms.nav.pendingProcessing","permission":"fiscal_service.process_obligations"},
      {"id":"oms_completed","href":"/dashboard/agent/oms/queue/completed","icon":"CheckCircle2","titleKey":"oms.nav.completedObligations","permission":"fiscal_service.view_bundles"}
    ]},
    {"id":"licenses","icon":"Briefcase","titleKey":"oms.nav.licenses","items":[
      {"id":"overview","href":"/dashboard/agent/oms/licenses","icon":"FileCheck","titleKey":"oms.nav.licensesOverview","permission":"fiscal_service.view_bundles"},
      {"id":"compliance","href":"/dashboard/agent/oms/compliance","icon":"ShieldCheck","titleKey":"oms.nav.compliance","permission":"fiscal_service.view_bundles"}
    ]},
    {"id":"field_inspections","icon":"ClipboardCheck","titleKey":"inspection.nav.inspections","items":[
      {"id":"field_dashboard","href":"/dashboard/agent/oms/field","icon":"Activity","titleKey":"inspection.nav.dashboard","permission":"inspection.view_own"},
      {"id":"field_scan","href":"/dashboard/agent/oms/field/scan","icon":"QrCode","titleKey":"inspection.nav.scan","permission":"inspection.create"},
      {"id":"field_reconcile","href":"/dashboard/agent/oms/field/reconcile","icon":"Wallet","titleKey":"inspection.nav.reconcile","permission":"inspection.collect_payment"}
    ]},
    {"id":"companies","icon":"Building2","titleKey":"agent.nav.companies","items":[
      {"id":"company_debt","href":"/dashboard/agent/companies/debt","icon":"DollarSign","titleKey":"agent.nav.companyDebt","permission":"company.view"},
      {"id":"company_lookup","href":"/dashboard/agent/companies/lookup","icon":"Search","titleKey":"agent.nav.companyLookup","permission":"company.view"}
    ]}
  ],
  "source":"role","version":"1.3"
}'::jsonb
WHERE code = 'agent_camara';

-- ============================================================================
-- 2. MIN_* agents — each gets their entity-specific dashboard
-- Dashboard slug follows entity-url convention: MIN_HACIENDA → min-hacienda
-- ============================================================================

-- Helper: shared menu body (everything except dashboard href)
-- Each role gets a separate UPDATE for its entity-specific dashboard.

UPDATE roles SET menu_config = jsonb_build_object(
  'menus', jsonb_build_array(
    '{"id":"dashboard","href":"/dashboard/agent/min-comercio","icon":"LayoutDashboard","titleKey":"oms.nav.dashboard"}'::jsonb,
    '{"id":"queue","icon":"ListTodo","titleKey":"oms.nav.obligations","items":[{"id":"oms_pending","href":"/dashboard/agent/oms/queue","icon":"Clock","titleKey":"oms.nav.pendingProcessing","permission":"fiscal_service.process_obligations"},{"id":"oms_completed","href":"/dashboard/agent/oms/queue/completed","icon":"CheckCircle2","titleKey":"oms.nav.completedObligations","permission":"fiscal_service.view_bundles"}]}'::jsonb,
    '{"id":"licenses","icon":"Briefcase","titleKey":"oms.nav.licenses","items":[{"id":"overview","href":"/dashboard/agent/oms/licenses","icon":"FileCheck","titleKey":"oms.nav.licensesOverview","permission":"fiscal_service.view_bundles"},{"id":"compliance","href":"/dashboard/agent/oms/compliance","icon":"ShieldCheck","titleKey":"oms.nav.compliance","permission":"fiscal_service.view_bundles"}]}'::jsonb,
    '{"id":"field_inspections","icon":"ClipboardCheck","titleKey":"inspection.nav.inspections","items":[{"id":"field_dashboard","href":"/dashboard/agent/oms/field","icon":"Activity","titleKey":"inspection.nav.dashboard","permission":"inspection.view_own"},{"id":"field_scan","href":"/dashboard/agent/oms/field/scan","icon":"QrCode","titleKey":"inspection.nav.scan","permission":"inspection.create"},{"id":"field_reconcile","href":"/dashboard/agent/oms/field/reconcile","icon":"Wallet","titleKey":"inspection.nav.reconcile","permission":"inspection.collect_payment"}]}'::jsonb,
    '{"id":"companies","icon":"Building2","titleKey":"agent.nav.companies","items":[{"id":"company_debt","href":"/dashboard/agent/companies/debt","icon":"DollarSign","titleKey":"agent.nav.companyDebt","permission":"company.view"},{"id":"company_lookup","href":"/dashboard/agent/companies/lookup","icon":"Search","titleKey":"agent.nav.companyLookup","permission":"company.view"}]}'::jsonb
  ),
  'source', '"role"'::jsonb,
  'version', '"1.3"'::jsonb
) WHERE code = 'agent_min_comercio';

UPDATE roles SET menu_config = jsonb_set(
  (SELECT menu_config FROM roles WHERE code = 'agent_min_comercio'),
  '{menus,0,href}', '"/dashboard/agent/min-hacienda"'::jsonb
) WHERE code = 'agent_min_hacienda';

UPDATE roles SET menu_config = jsonb_set(
  (SELECT menu_config FROM roles WHERE code = 'agent_min_comercio'),
  '{menus,0,href}', '"/dashboard/agent/min-informacion"'::jsonb
) WHERE code = 'agent_min_informacion';

UPDATE roles SET menu_config = jsonb_set(
  (SELECT menu_config FROM roles WHERE code = 'agent_min_comercio'),
  '{menus,0,href}', '"/dashboard/agent/min-turismo"'::jsonb
) WHERE code = 'agent_min_turismo';

UPDATE roles SET menu_config = jsonb_set(
  (SELECT menu_config FROM roles WHERE code = 'agent_min_comercio'),
  '{menus,0,href}', '"/dashboard/agent/min-agricultura"'::jsonb
) WHERE code = 'agent_min_agricultura';

UPDATE roles SET menu_config = jsonb_set(
  (SELECT menu_config FROM roles WHERE code = 'agent_min_comercio'),
  '{menus,0,href}', '"/dashboard/agent/min-electricidad"'::jsonb
) WHERE code = 'agent_min_electricidad';

UPDATE roles SET menu_config = jsonb_set(
  (SELECT menu_config FROM roles WHERE code = 'agent_min_comercio'),
  '{menus,0,href}', '"/dashboard/agent/treasury"'::jsonb
) WHERE code = 'agent_oms_polyvalent';

-- ============================================================================
-- 3. AYUNTAMIENTO/CAMARA supervisors — team + validation + OMS + inspection supervision + companies
-- ============================================================================

UPDATE roles
SET menu_config = '{
  "menus":[
    {"id":"dashboard","href":"/dashboard/supervisor/oms","icon":"LayoutDashboard","titleKey":"oms.nav.dashboard"},
    {"id":"team","icon":"Users","titleKey":"supervisor.nav.team","items":[
      {"id":"oms_team","href":"/dashboard/supervisor/oms/team","icon":"BarChart2","titleKey":"oms.nav.team","permission":"fiscal_service.process_obligations"},
      {"id":"agents","href":"/dashboard/supervisor/team/agents","icon":"User","titleKey":"supervisor.nav.agents","permission":"agent.list"},
      {"id":"workload","href":"/dashboard/supervisor/team/workload","icon":"BarChart2","titleKey":"supervisor.nav.workload","permission":"agent.view_workload"}
    ]},
    {"id":"validation","icon":"CreditCard","titleKey":"treasury.nav.validation","items":[
      {"id":"pending","href":"/dashboard/agent/treasury/validation","icon":"CheckCircle","titleKey":"treasury.nav.validation","permission":"treasury.validate_payment"},
      {"id":"escalations","href":"/dashboard/supervisor/oms/escalations","icon":"AlertTriangle","titleKey":"supervisor.nav.escalations","permission":"queue.escalate"}
    ]},
    {"id":"queue","icon":"ListTodo","titleKey":"oms.nav.obligations","items":[
      {"id":"oms_pending","href":"/dashboard/agent/oms/queue","icon":"Clock","titleKey":"oms.nav.pendingProcessing","permission":"fiscal_service.process_obligations"},
      {"id":"oms_completed","href":"/dashboard/agent/oms/queue/completed","icon":"CheckCircle2","titleKey":"oms.nav.completedObligations","permission":"fiscal_service.view_bundles"}
    ]},
    {"id":"licenses","icon":"Briefcase","titleKey":"oms.nav.licenses","items":[
      {"id":"overview","href":"/dashboard/agent/oms/licenses","icon":"FileCheck","titleKey":"oms.nav.licensesOverview","permission":"fiscal_service.view_bundles"},
      {"id":"compliance","href":"/dashboard/agent/oms/compliance","icon":"ShieldCheck","titleKey":"oms.nav.compliance","permission":"fiscal_service.view_bundles"}
    ]},
    {"id":"inspection_supervision","icon":"Shield","titleKey":"inspection.nav.supervision","items":[
      {"id":"inspection_overview","href":"/dashboard/supervisor/inspections","icon":"BarChart3","titleKey":"inspection.nav.overview","permission":"inspection.view_entity"},
      {"id":"pending_seals","href":"/dashboard/supervisor/inspections/pending-seals","icon":"ShieldAlert","titleKey":"inspection.nav.pendingSeals","permission":"inspection.seal_approve"},
      {"id":"agent_field_perf","href":"/dashboard/supervisor/inspections/agents","icon":"Users","titleKey":"inspection.nav.agentPerformance","permission":"inspection.view_reports"}
    ]},
    {"id":"companies","icon":"Building2","titleKey":"supervisor.nav.companies","items":[
      {"id":"site_dashboard","href":"/dashboard/supervisor/companies/dashboard","icon":"MapPin","titleKey":"supervisor.nav.siteDashboard","permission":"company.view_entity_scoped"},
      {"id":"companies_list","href":"/dashboard/supervisor/companies","icon":"List","titleKey":"supervisor.nav.companiesList","permission":"company.view_entity_scoped"},
      {"id":"company_debt","href":"/dashboard/agent/companies/debt","icon":"DollarSign","titleKey":"supervisor.nav.companyDebt","permission":"company.view"}
    ]}
  ],
  "source":"role","version":"1.3"
}'::jsonb
WHERE code IN ('supervisor_ayuntamiento', 'supervisor_camara');

-- ============================================================================
-- 4. MIN_* supervisors — each gets entity-specific supervisor dashboard
-- ============================================================================

UPDATE roles
SET menu_config = '{
  "menus":[
    {"id":"dashboard","href":"/dashboard/supervisor/min-comercio","icon":"LayoutDashboard","titleKey":"oms.nav.dashboard"},
    {"id":"team","icon":"Users","titleKey":"supervisor.nav.team","items":[
      {"id":"oms_team","href":"/dashboard/supervisor/oms/team","icon":"BarChart2","titleKey":"oms.nav.team","permission":"fiscal_service.process_obligations"},
      {"id":"agents","href":"/dashboard/supervisor/team/agents","icon":"User","titleKey":"supervisor.nav.agents","permission":"agent.list"},
      {"id":"workload","href":"/dashboard/supervisor/team/workload","icon":"BarChart2","titleKey":"supervisor.nav.workload","permission":"agent.view_workload"}
    ]},
    {"id":"queue","icon":"ListTodo","titleKey":"oms.nav.obligations","items":[
      {"id":"oms_pending","href":"/dashboard/agent/oms/queue","icon":"Clock","titleKey":"oms.nav.pendingProcessing","permission":"fiscal_service.process_obligations"},
      {"id":"oms_completed","href":"/dashboard/agent/oms/queue/completed","icon":"CheckCircle2","titleKey":"oms.nav.completedObligations","permission":"fiscal_service.view_bundles"}
    ]},
    {"id":"licenses","icon":"Briefcase","titleKey":"oms.nav.licenses","items":[
      {"id":"overview","href":"/dashboard/agent/oms/licenses","icon":"FileCheck","titleKey":"oms.nav.licensesOverview","permission":"fiscal_service.view_bundles"},
      {"id":"compliance","href":"/dashboard/agent/oms/compliance","icon":"ShieldCheck","titleKey":"oms.nav.compliance","permission":"fiscal_service.view_bundles"}
    ]},
    {"id":"inspection_supervision","icon":"Shield","titleKey":"inspection.nav.supervision","items":[
      {"id":"inspection_overview","href":"/dashboard/supervisor/inspections","icon":"BarChart3","titleKey":"inspection.nav.overview","permission":"inspection.view_entity"},
      {"id":"pending_seals","href":"/dashboard/supervisor/inspections/pending-seals","icon":"ShieldAlert","titleKey":"inspection.nav.pendingSeals","permission":"inspection.seal_approve"},
      {"id":"agent_field_perf","href":"/dashboard/supervisor/inspections/agents","icon":"Users","titleKey":"inspection.nav.agentPerformance","permission":"inspection.view_reports"}
    ]},
    {"id":"companies","icon":"Building2","titleKey":"supervisor.nav.companies","items":[
      {"id":"site_dashboard","href":"/dashboard/supervisor/companies/dashboard","icon":"MapPin","titleKey":"supervisor.nav.siteDashboard","permission":"company.view_entity_scoped"},
      {"id":"companies_list","href":"/dashboard/supervisor/companies","icon":"List","titleKey":"supervisor.nav.companiesList","permission":"company.view_entity_scoped"},
      {"id":"company_debt","href":"/dashboard/agent/companies/debt","icon":"DollarSign","titleKey":"supervisor.nav.companyDebt","permission":"company.view"}
    ]}
  ],
  "source":"role","version":"1.3"
}'::jsonb
WHERE code = 'supervisor_min_comercio';

UPDATE roles SET menu_config = jsonb_set(
  (SELECT menu_config FROM roles WHERE code = 'supervisor_min_comercio'),
  '{menus,0,href}', '"/dashboard/supervisor/min-hacienda"'::jsonb
) WHERE code = 'supervisor_min_hacienda';

UPDATE roles SET menu_config = jsonb_set(
  (SELECT menu_config FROM roles WHERE code = 'supervisor_min_comercio'),
  '{menus,0,href}', '"/dashboard/supervisor/min-informacion"'::jsonb
) WHERE code = 'supervisor_min_informacion';

UPDATE roles SET menu_config = jsonb_set(
  (SELECT menu_config FROM roles WHERE code = 'supervisor_min_comercio'),
  '{menus,0,href}', '"/dashboard/supervisor/min-turismo"'::jsonb
) WHERE code = 'supervisor_min_turismo';

UPDATE roles SET menu_config = jsonb_set(
  (SELECT menu_config FROM roles WHERE code = 'supervisor_min_comercio'),
  '{menus,0,href}', '"/dashboard/supervisor/min-agricultura"'::jsonb
) WHERE code = 'supervisor_min_agricultura';

UPDATE roles SET menu_config = jsonb_set(
  (SELECT menu_config FROM roles WHERE code = 'supervisor_min_comercio'),
  '{menus,0,href}', '"/dashboard/supervisor/min-electricidad"'::jsonb
) WHERE code = 'supervisor_min_electricidad';

COMMIT;
