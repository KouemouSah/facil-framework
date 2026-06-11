-- Migration 223: OMS Agent Roles, Profiles, and Test Users
--
-- Creates the complete OMS agent infrastructure (0 technical debt):
--   - 3 OMS permissions (view_bundles, process_obligations, manage_bundles)
--   - 17 new roles (8 agent + 8 supervisor + 1 polyvalent) with menu_config + dashboard_config
--   - Permission assignments for all 17 roles + OMS additions to agent_tesoro/supervisor_tesoro
--   - 17 test users (all in Malabo, password: TestOms2026!)
--   - 17 agent_profiles linked to OMS entities + entity_locations
--   - TESORO menu extension with OMS section
--
-- Depends on: 218 (foundations), 221 (entities+locations), 222 (routing view fix)

BEGIN;

-- Audit trigger on role_permissions requires current user
SET LOCAL app.current_user_id = '7c6073e3-66b0-45ba-be8d-80fcf98b7ad2';

-- ============================================================
-- 1. OMS Permissions (3)
-- ============================================================
-- Migration 220 was not executed — creating permissions here

INSERT INTO permissions (name, resource, action, description, is_critical, module_name)
VALUES
    ('fiscal_service.view_bundles', 'fiscal_service', 'view_bundles',
     'Ver paquetes de servicios, licencias y obligaciones', false, 'fiscal_service'),
    ('fiscal_service.manage_bundles', 'fiscal_service', 'manage_bundles',
     'Gestionar paquetes, licencias, obligaciones y reglas de configuracion', true, 'fiscal_service'),
    ('fiscal_service.process_obligations', 'fiscal_service', 'process_obligations',
     'Validar pagos, actualizar estado de obligaciones (agentes OMS)', false, 'fiscal_service')
ON CONFLICT (name) DO NOTHING;

-- ============================================================
-- 2. Roles (17 new) with menu_config + dashboard_config
-- ============================================================

DO $$
DECLARE
    -- ── Menu configs ──

    -- Payment Validator agents (AYUNTAMIENTO, CAMARA)
    v_menu_pv_agent JSONB := '{
      "menus":[
        {"id":"dashboard","href":"/dashboard/agent/oms/validator","icon":"LayoutDashboard","titleKey":"oms.nav.dashboard"},
        {"id":"validation","icon":"CreditCard","titleKey":"oms.nav.payments","items":[
          {"id":"pending","href":"/dashboard/agent/oms/validation","icon":"CheckCircle","titleKey":"oms.nav.pendingValidation","permission":"fiscal_service.process_obligations"},
          {"id":"history","href":"/dashboard/agent/oms/validation/history","icon":"History","titleKey":"oms.nav.validationHistory","permission":"fiscal_service.view_bundles"}
        ]},
        {"id":"licenses","href":"/dashboard/agent/oms/licenses","icon":"Briefcase","titleKey":"oms.nav.licenses","permission":"fiscal_service.view_bundles"}
      ],
      "source":"role","version":"1.0"
    }'::jsonb;

    -- Post-Payment Processor agents (MIN_*, polyvalent)
    v_menu_pp_agent JSONB := '{
      "menus":[
        {"id":"dashboard","href":"/dashboard/agent/oms/processor","icon":"LayoutDashboard","titleKey":"oms.nav.dashboard"},
        {"id":"queue","icon":"ListTodo","titleKey":"oms.nav.obligations","items":[
          {"id":"pending","href":"/dashboard/agent/oms/queue","icon":"Clock","titleKey":"oms.nav.pendingProcessing","permission":"fiscal_service.process_obligations"},
          {"id":"completed","href":"/dashboard/agent/oms/queue/completed","icon":"CheckCircle2","titleKey":"oms.nav.completedObligations","permission":"fiscal_service.view_bundles"}
        ]},
        {"id":"documents","href":"/dashboard/agent/oms/documents","icon":"FileText","titleKey":"oms.nav.documents","permission":"fiscal_service.process_obligations"},
        {"id":"licenses","href":"/dashboard/agent/oms/licenses","icon":"Briefcase","titleKey":"oms.nav.licenses","permission":"fiscal_service.view_bundles"}
      ],
      "source":"role","version":"1.0"
    }'::jsonb;

    -- Payment Validator supervisors (AYUNTAMIENTO, CAMARA)
    v_menu_pv_sup JSONB := '{
      "menus":[
        {"id":"dashboard","href":"/dashboard/supervisor/oms","icon":"LayoutDashboard","titleKey":"oms.nav.dashboard"},
        {"id":"team","icon":"Users","titleKey":"supervisor.nav.team","items":[
          {"id":"agents","href":"/dashboard/supervisor/team/agents","icon":"User","titleKey":"supervisor.nav.agents","permission":"agent.list"},
          {"id":"workload","href":"/dashboard/supervisor/team/workload","icon":"BarChart2","titleKey":"supervisor.nav.workload","permission":"agent.view_workload"}
        ]},
        {"id":"validation","icon":"CreditCard","titleKey":"oms.nav.payments","items":[
          {"id":"pending","href":"/dashboard/agent/oms/validation","icon":"CheckCircle","titleKey":"oms.nav.pendingValidation","permission":"fiscal_service.process_obligations"},
          {"id":"escalations","href":"/dashboard/supervisor/oms/escalations","icon":"AlertTriangle","titleKey":"supervisor.nav.escalations","permission":"queue.escalate"}
        ]},
        {"id":"stats","href":"/dashboard/supervisor/oms/stats","icon":"TrendingUp","titleKey":"oms.nav.stats","permission":"fiscal_service.view_bundles"}
      ],
      "source":"role","version":"1.0"
    }'::jsonb;

    -- Post-Payment Processor supervisors (MIN_*)
    v_menu_pp_sup JSONB := '{
      "menus":[
        {"id":"dashboard","href":"/dashboard/supervisor/oms","icon":"LayoutDashboard","titleKey":"oms.nav.dashboard"},
        {"id":"team","icon":"Users","titleKey":"supervisor.nav.team","items":[
          {"id":"agents","href":"/dashboard/supervisor/team/agents","icon":"User","titleKey":"supervisor.nav.agents","permission":"agent.list"},
          {"id":"workload","href":"/dashboard/supervisor/team/workload","icon":"BarChart2","titleKey":"supervisor.nav.workload","permission":"agent.view_workload"}
        ]},
        {"id":"queue","icon":"ListTodo","titleKey":"oms.nav.obligations","items":[
          {"id":"pending","href":"/dashboard/agent/oms/queue","icon":"Clock","titleKey":"oms.nav.pendingProcessing","permission":"fiscal_service.process_obligations"},
          {"id":"escalations","href":"/dashboard/supervisor/oms/escalations","icon":"AlertTriangle","titleKey":"supervisor.nav.escalations","permission":"queue.escalate"}
        ]},
        {"id":"stats","href":"/dashboard/supervisor/oms/stats","icon":"TrendingUp","titleKey":"oms.nav.stats","permission":"fiscal_service.view_bundles"}
      ],
      "source":"role","version":"1.0"
    }'::jsonb;

    -- ── Dashboard configs ──

    v_dash_pv JSONB := '{
      "layout":"grid","version":"1.0","widgets":[
        {"id":"oms_pending_validations","size":"medium","visible":true,"position":1},
        {"id":"oms_validated_today","size":"medium","visible":true,"position":2},
        {"id":"oms_overdue_alerts","size":"full","visible":true,"position":3},
        {"id":"oms_compliance_summary","size":"medium","visible":true,"position":4}
      ]
    }'::jsonb;

    v_dash_pp JSONB := '{
      "layout":"grid","version":"1.0","widgets":[
        {"id":"oms_pending_processing","size":"medium","visible":true,"position":1},
        {"id":"oms_processed_today","size":"medium","visible":true,"position":2},
        {"id":"oms_documents_pending","size":"medium","visible":true,"position":3},
        {"id":"oms_ministry_stats","size":"full","visible":true,"position":4}
      ]
    }'::jsonb;

    v_dash_sup JSONB := '{
      "layout":"grid","version":"1.0","widgets":[
        {"id":"oms_team_overview","size":"full","visible":true,"position":1},
        {"id":"oms_pending_escalations","size":"medium","visible":true,"position":2},
        {"id":"oms_performance_stats","size":"medium","visible":true,"position":3},
        {"id":"oms_compliance_summary","size":"full","visible":true,"position":4}
      ]
    }'::jsonb;

BEGIN
    -- 2a. Payment validator agents (2)
    INSERT INTO roles (code, name, description, is_system, menu_config, dashboard_config)
    VALUES
        ('agent_ayuntamiento', 'Agente Ayuntamiento',
         'Agente de validacion de pagos municipales - Ayuntamiento', false,
         v_menu_pv_agent, v_dash_pv),
        ('agent_camara', 'Agente Camara de Comercio',
         'Agente de validacion de pagos camara - Camara de Comercio', false,
         v_menu_pv_agent, v_dash_pv)
    ON CONFLICT (code) DO NOTHING;

    -- 2b. Post-payment processor agents (6)
    INSERT INTO roles (code, name, description, is_system, menu_config, dashboard_config)
    VALUES
        ('agent_min_comercio', 'Agente Min. Comercio',
         'Agente OMS post-pago - Ministerio de Comercio (ministry_id=87, 600 items)', false,
         v_menu_pp_agent, v_dash_pp),
        ('agent_min_hacienda', 'Agente Min. Hacienda',
         'Agente OMS post-pago - Ministerio de Hacienda (ministry_id=91, 120 items)', false,
         v_menu_pp_agent, v_dash_pp),
        ('agent_min_informacion', 'Agente Min. Informacion',
         'Agente OMS post-pago - Ministerio de Informacion (ministry_id=92, 144 items)', false,
         v_menu_pp_agent, v_dash_pp),
        ('agent_min_turismo', 'Agente Min. Turismo',
         'Agente OMS post-pago - Ministerio de Turismo (ministry_id=103, 36 items)', false,
         v_menu_pp_agent, v_dash_pp),
        ('agent_min_agricultura', 'Agente Min. Agricultura',
         'Agente OMS post-pago - Ministerio de Agricultura (ministry_id=104, 24 items)', false,
         v_menu_pp_agent, v_dash_pp),
        ('agent_min_electricidad', 'Agente Min. Electricidad',
         'Agente OMS post-pago - Ministerio de Electricidad (ministry_id=105, 24 items)', false,
         v_menu_pp_agent, v_dash_pp)
    ON CONFLICT (code) DO NOTHING;

    -- 2c. Polyvalent agent (1) — TESORO entity, Mode B consolidated
    INSERT INTO roles (code, name, description, is_system, menu_config, dashboard_config)
    VALUES
        ('agent_oms_polyvalent', 'Agente OMS Polivalente',
         'Super-agente polivalente OMS - traite TOUTES les obligations Mode B consolide (entite TESORO)', false,
         v_menu_pp_agent, v_dash_pp)
    ON CONFLICT (code) DO NOTHING;

    -- 2d. Payment validator supervisors (2)
    INSERT INTO roles (code, name, description, is_system, menu_config, dashboard_config)
    VALUES
        ('supervisor_ayuntamiento', 'Supervisor Ayuntamiento',
         'Supervisor validacion pagos municipales - Ayuntamiento', false,
         v_menu_pv_sup, v_dash_sup),
        ('supervisor_camara', 'Supervisor Camara de Comercio',
         'Supervisor validacion pagos camara - Camara de Comercio', false,
         v_menu_pv_sup, v_dash_sup)
    ON CONFLICT (code) DO NOTHING;

    -- 2e. Post-payment processor supervisors (6)
    INSERT INTO roles (code, name, description, is_system, menu_config, dashboard_config)
    VALUES
        ('supervisor_min_comercio', 'Supervisor Min. Comercio',
         'Supervisor OMS post-pago - Ministerio de Comercio', false,
         v_menu_pp_sup, v_dash_sup),
        ('supervisor_min_hacienda', 'Supervisor Min. Hacienda',
         'Supervisor OMS post-pago - Ministerio de Hacienda', false,
         v_menu_pp_sup, v_dash_sup),
        ('supervisor_min_informacion', 'Supervisor Min. Informacion',
         'Supervisor OMS post-pago - Ministerio de Informacion', false,
         v_menu_pp_sup, v_dash_sup),
        ('supervisor_min_turismo', 'Supervisor Min. Turismo',
         'Supervisor OMS post-pago - Ministerio de Turismo', false,
         v_menu_pp_sup, v_dash_sup),
        ('supervisor_min_agricultura', 'Supervisor Min. Agricultura',
         'Supervisor OMS post-pago - Ministerio de Agricultura', false,
         v_menu_pp_sup, v_dash_sup),
        ('supervisor_min_electricidad', 'Supervisor Min. Electricidad',
         'Supervisor OMS post-pago - Ministerio de Electricidad', false,
         v_menu_pp_sup, v_dash_sup)
    ON CONFLICT (code) DO NOTHING;
END $$;

-- ============================================================
-- 3. Permission Assignments
-- ============================================================

-- 3a. OMS agent roles: view_bundles + process_obligations (9 roles x 2 perms = 18)
INSERT INTO role_permissions (role_id, permission_id, granted, created_by)
SELECT r.id, p.id, true, '7c6073e3-66b0-45ba-be8d-80fcf98b7ad2'::uuid
FROM roles r
CROSS JOIN permissions p
WHERE r.code IN (
    'agent_ayuntamiento', 'agent_camara',
    'agent_min_comercio', 'agent_min_hacienda', 'agent_min_informacion',
    'agent_min_turismo', 'agent_min_agricultura', 'agent_min_electricidad',
    'agent_oms_polyvalent'
)
AND p.name IN ('fiscal_service.view_bundles', 'fiscal_service.process_obligations')
ON CONFLICT DO NOTHING;

-- 3b. OMS supervisor roles: OMS perms + team management (8 roles x 9 perms = 72)
INSERT INTO role_permissions (role_id, permission_id, granted, created_by)
SELECT r.id, p.id, true, '7c6073e3-66b0-45ba-be8d-80fcf98b7ad2'::uuid
FROM roles r
CROSS JOIN permissions p
WHERE r.code IN (
    'supervisor_ayuntamiento', 'supervisor_camara',
    'supervisor_min_comercio', 'supervisor_min_hacienda', 'supervisor_min_informacion',
    'supervisor_min_turismo', 'supervisor_min_agricultura', 'supervisor_min_electricidad'
)
AND p.name IN (
    'fiscal_service.view_bundles',
    'fiscal_service.process_obligations',
    'fiscal_service.manage_bundles',
    'agent.list', 'agent.view', 'agent.view_workload', 'agent.view_performance',
    'queue.escalate', 'queue.view'
)
ON CONFLICT DO NOTHING;

-- 3c. Add OMS permissions to existing agent_tesoro (2 perms)
INSERT INTO role_permissions (role_id, permission_id, granted, created_by)
SELECT r.id, p.id, true, '7c6073e3-66b0-45ba-be8d-80fcf98b7ad2'::uuid
FROM roles r CROSS JOIN permissions p
WHERE r.code = 'agent_tesoro'
AND p.name IN ('fiscal_service.view_bundles', 'fiscal_service.process_obligations')
ON CONFLICT DO NOTHING;

-- 3d. Add OMS permissions to existing supervisor_tesoro (3 perms)
INSERT INTO role_permissions (role_id, permission_id, granted, created_by)
SELECT r.id, p.id, true, '7c6073e3-66b0-45ba-be8d-80fcf98b7ad2'::uuid
FROM roles r CROSS JOIN permissions p
WHERE r.code = 'supervisor_tesoro'
AND p.name IN (
    'fiscal_service.view_bundles',
    'fiscal_service.process_obligations',
    'fiscal_service.manage_bundles'
)
ON CONFLICT DO NOTHING;

-- ============================================================
-- 4. Extend TESORO Menus with OMS Section
-- ============================================================

-- agent_tesoro: append OMS submenu (licenses + compliance)
UPDATE roles SET menu_config = jsonb_set(
    menu_config, '{menus}',
    (menu_config->'menus') || '[{
        "id":"oms","icon":"Briefcase","titleKey":"oms.nav.licenses",
        "items":[
            {"id":"licenses_overview","href":"/dashboard/agent/oms/licenses","icon":"FileCheck",
             "titleKey":"oms.nav.licensesOverview","permission":"fiscal_service.view_bundles"},
            {"id":"compliance","href":"/dashboard/agent/oms/compliance","icon":"ShieldCheck",
             "titleKey":"oms.nav.compliance","permission":"fiscal_service.view_bundles"}
        ]
    }]'::jsonb
)
WHERE code = 'agent_tesoro' AND menu_config IS NOT NULL;

-- supervisor_tesoro: append OMS submenu (licenses + compliance + config)
UPDATE roles SET menu_config = jsonb_set(
    menu_config, '{menus}',
    (menu_config->'menus') || '[{
        "id":"oms","icon":"Briefcase","titleKey":"oms.nav.licenses",
        "items":[
            {"id":"licenses_overview","href":"/dashboard/agent/oms/licenses","icon":"FileCheck",
             "titleKey":"oms.nav.licensesOverview","permission":"fiscal_service.view_bundles"},
            {"id":"compliance","href":"/dashboard/agent/oms/compliance","icon":"ShieldCheck",
             "titleKey":"oms.nav.compliance","permission":"fiscal_service.view_bundles"},
            {"id":"config","href":"/dashboard/admin/fiscal-services","icon":"Settings",
             "titleKey":"oms.nav.config","permission":"fiscal_service.manage_bundles"}
        ]
    }]'::jsonb
)
WHERE code = 'supervisor_tesoro' AND menu_config IS NOT NULL;

-- ============================================================
-- 5. Test Users (17) — password: TestOms2026!
-- ============================================================

WITH user_data(email, first_name, last_name, role_code) AS (VALUES
    ('agent.ayuntamiento@test.gq'::varchar,  'Agent'::varchar,      'Ayuntamiento'::varchar,  'agent_ayuntamiento'::varchar),
    ('sup.ayuntamiento@test.gq',             'Supervisor',          'Ayuntamiento',           'supervisor_ayuntamiento'),
    ('agent.camara@test.gq',                 'Agent',               'Camara',                 'agent_camara'),
    ('sup.camara@test.gq',                   'Supervisor',          'Camara',                 'supervisor_camara'),
    ('agent.min.comercio@test.gq',           'Agent',               'Min. Comercio',          'agent_min_comercio'),
    ('sup.min.comercio@test.gq',             'Supervisor',          'Min. Comercio',          'supervisor_min_comercio'),
    ('agent.min.hacienda@test.gq',           'Agent',               'Min. Hacienda',          'agent_min_hacienda'),
    ('sup.min.hacienda@test.gq',             'Supervisor',          'Min. Hacienda',          'supervisor_min_hacienda'),
    ('agent.min.informacion@test.gq',        'Agent',               'Min. Informacion',       'agent_min_informacion'),
    ('sup.min.informacion@test.gq',          'Supervisor',          'Min. Informacion',       'supervisor_min_informacion'),
    ('agent.min.turismo@test.gq',            'Agent',               'Min. Turismo',           'agent_min_turismo'),
    ('sup.min.turismo@test.gq',              'Supervisor',          'Min. Turismo',           'supervisor_min_turismo'),
    ('agent.min.agricultura@test.gq',        'Agent',               'Min. Agricultura',       'agent_min_agricultura'),
    ('sup.min.agricultura@test.gq',          'Supervisor',          'Min. Agricultura',       'supervisor_min_agricultura'),
    ('agent.min.electricidad@test.gq',       'Agent',               'Min. Electricidad',      'agent_min_electricidad'),
    ('sup.min.electricidad@test.gq',         'Supervisor',          'Min. Electricidad',      'supervisor_min_electricidad'),
    ('agent.polyvalent@test.gq',             'Agent',               'OMS Polivalente',        'agent_oms_polyvalent')
)
INSERT INTO users (email, password_hash, first_name, last_name,
                   role, status, role_id, email_verified, city, preferred_language)
SELECT
    ud.email,
    '$2b$12$mqCWP2tCtg7pJ8p9bP3peOiRwRrv39LmVi.2ctaMTVb1VzK9KJKx.',
    ud.first_name, ud.last_name,
    'agent'::user_role_enum, 'active'::user_status_enum,
    r.id, true, 'Malabo', 'es'
FROM user_data ud
JOIN roles r ON r.code = ud.role_code
WHERE NOT EXISTS (SELECT 1 FROM users u2 WHERE u2.email = ud.email);

-- ============================================================
-- 6. Agent Profiles (17)
-- ============================================================
-- Links users to OMS entities + Malabo locations
-- ministry_id matches entity.ministry_id (NULL for polyvalent = no ministry filter)

WITH profile_data(user_email, entity_code, ministry_id_val, is_sup) AS (VALUES
    ('agent.ayuntamiento@test.gq'::varchar,    'AYUNTAMIENTO'::varchar,  107::int,    false::boolean),
    ('sup.ayuntamiento@test.gq',               'AYUNTAMIENTO',           107,         true),
    ('agent.camara@test.gq',                   'CAMARA_COMERCIO',        108,         false),
    ('sup.camara@test.gq',                     'CAMARA_COMERCIO',        108,         true),
    ('agent.min.comercio@test.gq',             'MIN_COMERCIO',           87,          false),
    ('sup.min.comercio@test.gq',               'MIN_COMERCIO',           87,          true),
    ('agent.min.hacienda@test.gq',             'MIN_HACIENDA',           91,          false),
    ('sup.min.hacienda@test.gq',               'MIN_HACIENDA',           91,          true),
    ('agent.min.informacion@test.gq',          'MIN_INFORMACION',        92,          false),
    ('sup.min.informacion@test.gq',            'MIN_INFORMACION',        92,          true),
    ('agent.min.turismo@test.gq',              'MIN_TURISMO',            103,         false),
    ('sup.min.turismo@test.gq',                'MIN_TURISMO',            103,         true),
    ('agent.min.agricultura@test.gq',          'MIN_AGRICULTURA',        104,         false),
    ('sup.min.agricultura@test.gq',            'MIN_AGRICULTURA',        104,         true),
    ('agent.min.electricidad@test.gq',         'MIN_ELECTRICIDAD',       105,         false),
    ('sup.min.electricidad@test.gq',           'MIN_ELECTRICIDAD',       105,         true),
    ('agent.polyvalent@test.gq',               'TESORO',                 NULL::int,   false)
)
INSERT INTO agent_profiles (user_id, agent_type, entity_id, ministry_id,
                            entity_location_id, is_supervisor)
SELECT
    u.id, 'entity_agent', e.id, pd.ministry_id_val, el.id, pd.is_sup
FROM profile_data pd
JOIN users u ON u.email = pd.user_email
JOIN entities e ON e.code = pd.entity_code
JOIN entity_locations el ON el.entity_id = e.id AND el.city = 'Malabo'
WHERE NOT EXISTS (SELECT 1 FROM agent_profiles ap WHERE ap.user_id = u.id);

COMMIT;

-- ============================================================
-- Verification Queries (run after migration)
-- ============================================================
--
-- 1. All 17 roles created with configs:
-- SELECT code, name, menu_config IS NOT NULL AS has_menu, dashboard_config IS NOT NULL AS has_dash
-- FROM roles WHERE code LIKE 'agent_min_%' OR code LIKE 'supervisor_min_%'
--    OR code IN ('agent_ayuntamiento','agent_camara','supervisor_ayuntamiento','supervisor_camara','agent_oms_polyvalent')
-- ORDER BY code;
-- Expected: 17 rows, all has_menu=true, has_dash=true
--
-- 2. Permissions exist:
-- SELECT name FROM permissions WHERE name LIKE 'fiscal_service.%_bundles' OR name = 'fiscal_service.process_obligations';
-- Expected: 3 rows
--
-- 3. Agent role permissions (9 agents x 2 perms):
-- SELECT r.code, p.name FROM role_permissions rp
-- JOIN roles r ON r.id = rp.role_id JOIN permissions p ON p.id = rp.permission_id
-- WHERE r.code LIKE 'agent_%' AND p.name LIKE 'fiscal_service.%'
-- ORDER BY r.code, p.name;
-- Expected: 20 rows (9 new agents x 2 + agent_tesoro x 2)
--
-- 4. Supervisor role permissions (8 sups x 9 perms):
-- SELECT r.code, COUNT(*) FROM role_permissions rp
-- JOIN roles r ON r.id = rp.role_id
-- WHERE r.code LIKE 'supervisor_%' AND r.code NOT IN ('supervisor_tesoro','supervisor_cnedoge_pasaporte',
--     'supervisor_cnedoge_residencia','supervisor_dgt','supervisor_extranjeria','supervisor_itv',
--     'supervisor_minfp','supervisor_ofive','supervisor_onrc','supervisor_policia')
-- GROUP BY r.code ORDER BY r.code;
-- Expected: 8 rows, each with count=9
--
-- 5. TESORO menu extended:
-- SELECT jsonb_array_length(menu_config->'menus') FROM roles WHERE code = 'agent_tesoro';
-- Expected: 4 (was 3 + 1 OMS)
-- SELECT jsonb_array_length(menu_config->'menus') FROM roles WHERE code = 'supervisor_tesoro';
-- Expected: 8 (was 7 + 1 OMS)
--
-- 6. Test users created:
-- SELECT u.email, u.role, r.code AS role_code FROM users u
-- JOIN roles r ON r.id = u.role_id WHERE u.email LIKE '%@test.gq' ORDER BY u.email;
-- Expected: 17 rows, all role='agent'
--
-- 7. Agent profiles linked to entities:
-- SELECT u.email, ap.agent_type, e.code AS entity_code, ap.ministry_id,
--        el.city, ap.is_supervisor
-- FROM agent_profiles ap
-- JOIN users u ON u.id = ap.user_id
-- JOIN entities e ON e.id = ap.entity_id
-- JOIN entity_locations el ON el.id = ap.entity_location_id
-- WHERE u.email LIKE '%@test.gq'
-- ORDER BY u.email;
-- Expected: 17 rows, all city='Malabo', polyvalent has ministry_id=NULL
