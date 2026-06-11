-- ============================================================================
-- Migration 078: Complete Agent Roles Configuration
-- ============================================================================
-- Purpose:
--   1. Add menu_config and dashboard_config for all agent roles
--   2. Create missing roles (supervisor, agent_extranjeria, agent_policia)
--   3. Add appointments menu to roles with RDV
--   4. Assign service_request.view_queue_stats permission for Stats Cards
--
-- Phase 5.4 of Dashboard Config + Appointments Management
--
-- Roles handled:
--   EXISTING (update config):
--     - agent_cnedoge_pasaporte (with appointments)
--     - agent_cnedoge_residencia (with appointments)
--     - agent_dgt (with appointments)
--     - agent_onrc (with appointments)
--     - agent_ofive (with appointments)
--     - supervisor_tesoro (treasury supervisor)
--
--   NEW (create + config):
--     - supervisor (generic supervisor for all entities)
--     - agent_extranjeria (immigration - with appointments)
--     - agent_policia (police - with appointments)
--
-- Author: Claude Code
-- Date: 2026-01-26
-- ============================================================================

BEGIN;

-- =============================================================================
-- SECTION A: CREATE NEW ROLES
-- =============================================================================

-- -----------------------------------------------------------------------------
-- A.1 CREATE SUPERVISOR ROLE (generic)
-- -----------------------------------------------------------------------------

INSERT INTO roles (code, name, description, entity_type, is_system)
VALUES (
    'supervisor',
    'Supervisor',
    'Supervisor générique avec accès à la gestion d''équipe, escalations et performance',
    'supervisor',
    false
)
ON CONFLICT (code) DO NOTHING;

-- -----------------------------------------------------------------------------
-- A.2 CREATE AGENT_EXTRANJERIA ROLE
-- -----------------------------------------------------------------------------

INSERT INTO roles (code, name, description, entity_type, is_system)
VALUES (
    'agent_extranjeria',
    'Agent Extranjeria',
    'Agent du service d''immigration pour les permis de résidence et visas',
    'agent',
    false
)
ON CONFLICT (code) DO NOTHING;

-- -----------------------------------------------------------------------------
-- A.3 CREATE AGENT_POLICIA ROLE
-- -----------------------------------------------------------------------------

INSERT INTO roles (code, name, description, entity_type, is_system)
VALUES (
    'agent_policia',
    'Agent Policia',
    'Agent de police pour les vérifications et certificats',
    'agent',
    false
)
ON CONFLICT (code) DO NOTHING;


-- =============================================================================
-- SECTION B: UPDATE EXISTING AGENT ROLES WITH APPOINTMENTS
-- =============================================================================

-- -----------------------------------------------------------------------------
-- B.1 AGENT_CNEDOGE_PASAPORTE - With appointments
-- -----------------------------------------------------------------------------

UPDATE roles SET
    menu_config = '{
        "version": "1.0",
        "source": "role",
        "menus": [
            {
                "id": "dashboard",
                "titleKey": "agent.nav.dashboard",
                "href": "/dashboard/agent/cnedoge-pasaporte",
                "icon": "LayoutDashboard"
            },
            {
                "id": "pasaportes",
                "titleKey": "agent.nav.passports",
                "icon": "Plane",
                "items": [
                    {"id": "pending", "titleKey": "agent.nav.pending", "href": "/dashboard/agent/cnedoge-pasaporte/pasaportes/pending", "icon": "Clock", "permission": "service_request.view_queue"},
                    {"id": "validation", "titleKey": "agent.nav.validation", "href": "/dashboard/agent/cnedoge-pasaporte/pasaportes/validation", "icon": "CheckCircle", "permission": "service_request.process"},
                    {"id": "history", "titleKey": "agent.nav.history", "href": "/dashboard/agent/cnedoge-pasaporte/pasaportes/history", "icon": "History", "permission": "service_request.view"}
                ]
            },
            {
                "id": "appointments",
                "titleKey": "agent.nav.appointments",
                "href": "/dashboard/agent/cnedoge-pasaporte/appointments",
                "icon": "Calendar",
                "permission": "service_request.view_appointments"
            }
        ]
    }'::jsonb,
    dashboard_config = '{
        "version": "1.0",
        "layout": "grid",
        "widgets": [
            {"id": "alerts", "visible": true, "position": 1, "size": "medium"},
            {"id": "urgent_requests", "visible": true, "position": 2, "size": "medium"},
            {"id": "calendar_slots", "visible": true, "position": 3, "size": "full"},
            {"id": "today_appointments", "visible": true, "position": 4, "size": "medium"},
            {"id": "workflow_distribution", "visible": true, "position": 5, "size": "medium"}
        ]
    }'::jsonb
WHERE code = 'agent_cnedoge_pasaporte';

-- -----------------------------------------------------------------------------
-- B.2 AGENT_CNEDOGE_RESIDENCIA - With appointments
-- -----------------------------------------------------------------------------

UPDATE roles SET
    menu_config = '{
        "version": "1.0",
        "source": "role",
        "menus": [
            {
                "id": "dashboard",
                "titleKey": "agent.nav.dashboard",
                "href": "/dashboard/agent/cnedoge-residencia",
                "icon": "LayoutDashboard"
            },
            {
                "id": "residencias",
                "titleKey": "agent.nav.residences",
                "icon": "Globe",
                "items": [
                    {"id": "pending", "titleKey": "agent.nav.pending", "href": "/dashboard/agent/cnedoge-residencia/residencias/pending", "icon": "Clock", "permission": "service_request.view_queue"},
                    {"id": "validation", "titleKey": "agent.nav.validation", "href": "/dashboard/agent/cnedoge-residencia/residencias/validation", "icon": "CheckCircle", "permission": "service_request.process"},
                    {"id": "history", "titleKey": "agent.nav.history", "href": "/dashboard/agent/cnedoge-residencia/residencias/history", "icon": "History", "permission": "service_request.view"}
                ]
            },
            {
                "id": "appointments",
                "titleKey": "agent.nav.appointments",
                "href": "/dashboard/agent/cnedoge-residencia/appointments",
                "icon": "Calendar",
                "permission": "service_request.view_appointments"
            }
        ]
    }'::jsonb,
    dashboard_config = '{
        "version": "1.0",
        "layout": "grid",
        "widgets": [
            {"id": "alerts", "visible": true, "position": 1, "size": "medium"},
            {"id": "urgent_requests", "visible": true, "position": 2, "size": "medium"},
            {"id": "calendar_slots", "visible": true, "position": 3, "size": "full"},
            {"id": "today_appointments", "visible": true, "position": 4, "size": "medium"},
            {"id": "workflow_distribution", "visible": true, "position": 5, "size": "medium"}
        ]
    }'::jsonb
WHERE code = 'agent_cnedoge_residencia';

-- -----------------------------------------------------------------------------
-- B.3 AGENT_DGT - With appointments (licencias)
-- -----------------------------------------------------------------------------

UPDATE roles SET
    menu_config = '{
        "version": "1.0",
        "source": "role",
        "menus": [
            {
                "id": "dashboard",
                "titleKey": "agent.nav.dashboard",
                "href": "/dashboard/agent/dgt",
                "icon": "LayoutDashboard"
            },
            {
                "id": "licencias",
                "titleKey": "agent.nav.licenses",
                "icon": "Car",
                "items": [
                    {"id": "pending", "titleKey": "agent.nav.pending", "href": "/dashboard/agent/dgt/licencias/pending", "icon": "Clock", "permission": "service_request.view_queue"},
                    {"id": "validation", "titleKey": "agent.nav.validation", "href": "/dashboard/agent/dgt/licencias/validation", "icon": "CheckCircle", "permission": "service_request.process"},
                    {"id": "history", "titleKey": "agent.nav.history", "href": "/dashboard/agent/dgt/licencias/history", "icon": "History", "permission": "service_request.view"}
                ]
            },
            {
                "id": "appointments",
                "titleKey": "agent.nav.appointments",
                "href": "/dashboard/agent/dgt/appointments",
                "icon": "Calendar",
                "permission": "service_request.view_appointments"
            }
        ]
    }'::jsonb,
    dashboard_config = '{
        "version": "1.0",
        "layout": "grid",
        "widgets": [
            {"id": "alerts", "visible": true, "position": 1, "size": "medium"},
            {"id": "urgent_requests", "visible": true, "position": 2, "size": "medium"},
            {"id": "calendar_slots", "visible": true, "position": 3, "size": "full"},
            {"id": "today_appointments", "visible": true, "position": 4, "size": "medium"},
            {"id": "workflow_distribution", "visible": true, "position": 5, "size": "medium"}
        ]
    }'::jsonb
WHERE code = 'agent_dgt';

-- -----------------------------------------------------------------------------
-- B.4 AGENT_EXTRANJERIA - With appointments (immigration)
-- -----------------------------------------------------------------------------

UPDATE roles SET
    menu_config = '{
        "version": "1.0",
        "source": "role",
        "menus": [
            {
                "id": "dashboard",
                "titleKey": "agent.nav.dashboard",
                "href": "/dashboard/agent/extranjeria",
                "icon": "LayoutDashboard"
            },
            {
                "id": "immigration",
                "titleKey": "agent.nav.immigration",
                "icon": "Globe",
                "items": [
                    {"id": "pending", "titleKey": "agent.nav.pending", "href": "/dashboard/agent/extranjeria/immigration/pending", "icon": "Clock", "permission": "service_request.view_queue"},
                    {"id": "validation", "titleKey": "agent.nav.validation", "href": "/dashboard/agent/extranjeria/immigration/validation", "icon": "CheckCircle", "permission": "service_request.process"},
                    {"id": "history", "titleKey": "agent.nav.history", "href": "/dashboard/agent/extranjeria/immigration/history", "icon": "History", "permission": "service_request.view"}
                ]
            },
            {
                "id": "appointments",
                "titleKey": "agent.nav.appointments",
                "href": "/dashboard/agent/extranjeria/appointments",
                "icon": "Calendar",
                "permission": "service_request.view_appointments"
            }
        ]
    }'::jsonb,
    dashboard_config = '{
        "version": "1.0",
        "layout": "grid",
        "widgets": [
            {"id": "alerts", "visible": true, "position": 1, "size": "medium"},
            {"id": "urgent_requests", "visible": true, "position": 2, "size": "medium"},
            {"id": "calendar_slots", "visible": true, "position": 3, "size": "full"},
            {"id": "today_appointments", "visible": true, "position": 4, "size": "medium"},
            {"id": "workflow_distribution", "visible": true, "position": 5, "size": "medium"}
        ]
    }'::jsonb
WHERE code = 'agent_extranjeria';


-- =============================================================================
-- SECTION C: UPDATE REMAINING AGENT ROLES WITH APPOINTMENTS
-- =============================================================================

-- -----------------------------------------------------------------------------
-- C.1 AGENT_ONRC - With appointments (contracts)
-- -----------------------------------------------------------------------------

UPDATE roles SET
    menu_config = '{
        "version": "1.0",
        "source": "role",
        "menus": [
            {
                "id": "dashboard",
                "titleKey": "agent.nav.dashboard",
                "href": "/dashboard/agent/onrc",
                "icon": "LayoutDashboard"
            },
            {
                "id": "contratos",
                "titleKey": "agent.nav.contracts",
                "icon": "FileSignature",
                "items": [
                    {"id": "pending", "titleKey": "agent.nav.pending", "href": "/dashboard/agent/onrc/contratos/pending", "icon": "Clock", "permission": "service_request.view_queue"},
                    {"id": "validation", "titleKey": "agent.nav.validation", "href": "/dashboard/agent/onrc/contratos/validation", "icon": "CheckCircle", "permission": "service_request.process"},
                    {"id": "history", "titleKey": "agent.nav.history", "href": "/dashboard/agent/onrc/contratos/history", "icon": "History", "permission": "service_request.view"}
                ]
            },
            {
                "id": "appointments",
                "titleKey": "agent.nav.appointments",
                "href": "/dashboard/agent/onrc/appointments",
                "icon": "Calendar",
                "permission": "service_request.view_appointments"
            }
        ]
    }'::jsonb,
    dashboard_config = '{
        "version": "1.0",
        "layout": "grid",
        "widgets": [
            {"id": "alerts", "visible": true, "position": 1, "size": "medium"},
            {"id": "urgent_requests", "visible": true, "position": 2, "size": "medium"},
            {"id": "calendar_slots", "visible": true, "position": 3, "size": "full"},
            {"id": "today_appointments", "visible": true, "position": 4, "size": "medium"},
            {"id": "workflow_distribution", "visible": true, "position": 5, "size": "medium"}
        ]
    }'::jsonb
WHERE code = 'agent_onrc';

-- -----------------------------------------------------------------------------
-- C.2 AGENT_OFIVE - With appointments (vehicles)
-- -----------------------------------------------------------------------------

UPDATE roles SET
    menu_config = '{
        "version": "1.0",
        "source": "role",
        "menus": [
            {
                "id": "dashboard",
                "titleKey": "agent.nav.dashboard",
                "href": "/dashboard/agent/ofive",
                "icon": "LayoutDashboard"
            },
            {
                "id": "vehiculos",
                "titleKey": "agent.nav.vehicles",
                "icon": "Truck",
                "items": [
                    {"id": "pending", "titleKey": "agent.nav.pending", "href": "/dashboard/agent/ofive/vehiculos/pending", "icon": "Clock", "permission": "service_request.view_queue"},
                    {"id": "validation", "titleKey": "agent.nav.validation", "href": "/dashboard/agent/ofive/vehiculos/validation", "icon": "CheckCircle", "permission": "service_request.process"},
                    {"id": "history", "titleKey": "agent.nav.history", "href": "/dashboard/agent/ofive/vehiculos/history", "icon": "History", "permission": "service_request.view"}
                ]
            },
            {
                "id": "appointments",
                "titleKey": "agent.nav.appointments",
                "href": "/dashboard/agent/ofive/appointments",
                "icon": "Calendar",
                "permission": "service_request.view_appointments"
            }
        ]
    }'::jsonb,
    dashboard_config = '{
        "version": "1.0",
        "layout": "grid",
        "widgets": [
            {"id": "alerts", "visible": true, "position": 1, "size": "medium"},
            {"id": "urgent_requests", "visible": true, "position": 2, "size": "medium"},
            {"id": "calendar_slots", "visible": true, "position": 3, "size": "full"},
            {"id": "today_appointments", "visible": true, "position": 4, "size": "medium"},
            {"id": "workflow_distribution", "visible": true, "position": 5, "size": "medium"}
        ]
    }'::jsonb
WHERE code = 'agent_ofive';

-- -----------------------------------------------------------------------------
-- C.3 AGENT_POLICIA - With appointments (police verifications)
-- -----------------------------------------------------------------------------

UPDATE roles SET
    menu_config = '{
        "version": "1.0",
        "source": "role",
        "menus": [
            {
                "id": "dashboard",
                "titleKey": "agent.nav.dashboard",
                "href": "/dashboard/agent/policia",
                "icon": "LayoutDashboard"
            },
            {
                "id": "verificaciones",
                "titleKey": "agent.nav.verifications",
                "icon": "Shield",
                "items": [
                    {"id": "pending", "titleKey": "agent.nav.pending", "href": "/dashboard/agent/policia/verificaciones/pending", "icon": "Clock", "permission": "service_request.view_queue"},
                    {"id": "validation", "titleKey": "agent.nav.validation", "href": "/dashboard/agent/policia/verificaciones/validation", "icon": "CheckCircle", "permission": "service_request.process"},
                    {"id": "history", "titleKey": "agent.nav.history", "href": "/dashboard/agent/policia/verificaciones/history", "icon": "History", "permission": "service_request.view"}
                ]
            },
            {
                "id": "appointments",
                "titleKey": "agent.nav.appointments",
                "href": "/dashboard/agent/policia/appointments",
                "icon": "Calendar",
                "permission": "service_request.view_appointments"
            }
        ]
    }'::jsonb,
    dashboard_config = '{
        "version": "1.0",
        "layout": "grid",
        "widgets": [
            {"id": "alerts", "visible": true, "position": 1, "size": "medium"},
            {"id": "urgent_requests", "visible": true, "position": 2, "size": "medium"},
            {"id": "calendar_slots", "visible": true, "position": 3, "size": "full"},
            {"id": "today_appointments", "visible": true, "position": 4, "size": "medium"},
            {"id": "workflow_distribution", "visible": true, "position": 5, "size": "medium"}
        ]
    }'::jsonb
WHERE code = 'agent_policia';


-- =============================================================================
-- SECTION D: UPDATE SUPERVISOR ROLES
-- =============================================================================

-- -----------------------------------------------------------------------------
-- D.1 SUPERVISOR (generic)
-- -----------------------------------------------------------------------------

UPDATE roles SET
    menu_config = '{
        "version": "1.0",
        "source": "role",
        "menus": [
            {
                "id": "dashboard",
                "titleKey": "supervisor.nav.dashboard",
                "href": "/dashboard/supervisor",
                "icon": "LayoutDashboard"
            },
            {
                "id": "team",
                "titleKey": "supervisor.nav.team",
                "icon": "Users",
                "items": [
                    {"id": "agents", "titleKey": "supervisor.nav.agents", "href": "/dashboard/supervisor/team/agents", "icon": "User", "permission": "agent.list"},
                    {"id": "workload", "titleKey": "supervisor.nav.workload", "href": "/dashboard/supervisor/team/workload", "icon": "BarChart2", "permission": "agent.view_workload"},
                    {"id": "performance", "titleKey": "supervisor.nav.performance", "href": "/dashboard/supervisor/team/performance", "icon": "TrendingUp", "permission": "agent.view_performance"}
                ]
            },
            {
                "id": "escalations",
                "titleKey": "supervisor.nav.escalations",
                "icon": "AlertTriangle",
                "items": [
                    {"id": "pending", "titleKey": "supervisor.nav.pendingEscalations", "href": "/dashboard/supervisor/escalations/pending", "icon": "Clock", "permission": "queue.escalate"}
                ]
            },
            {
                "id": "assignments",
                "titleKey": "supervisor.nav.assignments",
                "icon": "Settings2",
                "items": [
                    {"id": "list", "titleKey": "supervisor.nav.assignmentsList", "href": "/dashboard/admin/assignments", "icon": "ClipboardList", "permission": "assignment.list"},
                    {"id": "manual", "titleKey": "supervisor.nav.manualAssignment", "href": "/dashboard/admin/assignments/new/manual", "icon": "UserPlus", "permission": "assignment.reassign"},
                    {"id": "rules", "titleKey": "supervisor.nav.rules", "href": "/dashboard/supervisor/assignments/rules", "icon": "ListChecks", "permission": "rules.view"}
                ]
            }
        ]
    }'::jsonb,
    dashboard_config = '{
        "version": "1.0",
        "layout": "grid",
        "widgets": [
            {"id": "team_workload", "visible": true, "position": 1, "size": "large"},
            {"id": "escalations", "visible": true, "position": 2, "size": "medium"},
            {"id": "workflow_distribution", "visible": true, "position": 3, "size": "medium"},
            {"id": "alerts", "visible": true, "position": 4, "size": "small"}
        ]
    }'::jsonb
WHERE code = 'supervisor';

-- -----------------------------------------------------------------------------
-- D.2 SUPERVISOR_TESORO
-- -----------------------------------------------------------------------------

UPDATE roles SET
    menu_config = '{
        "version": "1.0",
        "source": "role",
        "menus": [
            {
                "id": "dashboard",
                "titleKey": "supervisor.nav.dashboard",
                "href": "/dashboard/supervisor",
                "icon": "LayoutDashboard"
            },
            {
                "id": "treasury_overview",
                "titleKey": "supervisor.nav.treasuryOverview",
                "href": "/dashboard/agent/treasury",
                "icon": "Wallet",
                "permission": "treasury.view_payment"
            },
            {
                "id": "team",
                "titleKey": "supervisor.nav.team",
                "icon": "Users",
                "items": [
                    {"id": "agents", "titleKey": "supervisor.nav.agents", "href": "/dashboard/supervisor/team/agents", "icon": "User", "permission": "agent.list"},
                    {"id": "workload", "titleKey": "supervisor.nav.workload", "href": "/dashboard/supervisor/team/workload", "icon": "BarChart2", "permission": "agent.view_workload"},
                    {"id": "performance", "titleKey": "supervisor.nav.performance", "href": "/dashboard/supervisor/team/performance", "icon": "TrendingUp", "permission": "agent.view_performance"},
                    {"id": "agent_stats", "titleKey": "supervisor.nav.agentStats", "href": "/dashboard/agent/treasury/stats/agents", "icon": "BarChart3", "permission": "treasury_stat.view"}
                ]
            },
            {
                "id": "escalations",
                "titleKey": "supervisor.nav.escalations",
                "icon": "AlertTriangle",
                "items": [
                    {"id": "pending", "titleKey": "supervisor.nav.pendingEscalations", "href": "/dashboard/supervisor/escalations/pending", "icon": "Clock", "permission": "queue.escalate"}
                ]
            },
            {
                "id": "assignments",
                "titleKey": "supervisor.nav.assignments",
                "icon": "Settings2",
                "items": [
                    {"id": "list", "titleKey": "supervisor.nav.assignmentsList", "href": "/dashboard/admin/assignments", "icon": "ClipboardList", "permission": "assignment.list"},
                    {"id": "manual", "titleKey": "supervisor.nav.manualAssignment", "href": "/dashboard/admin/assignments/new/manual", "icon": "UserPlus", "permission": "assignment.reassign"},
                    {"id": "rules", "titleKey": "supervisor.nav.rules", "href": "/dashboard/supervisor/assignments/rules", "icon": "ListChecks", "permission": "rules.view"}
                ]
            },
            {
                "id": "reports",
                "titleKey": "supervisor.nav.reports",
                "icon": "FileText",
                "items": [
                    {"id": "sla", "titleKey": "supervisor.nav.sla", "href": "/dashboard/agent/treasury/stats/sla", "icon": "Clock", "permission": "treasury_stat.view"},
                    {"id": "analytics", "titleKey": "supervisor.nav.analytics", "href": "/dashboard/agent/treasury/analytics", "icon": "Activity", "permission": "treasury_stat.view"},
                    {"id": "anomalies", "titleKey": "supervisor.nav.anomalies", "href": "/dashboard/agent/treasury/anomalies", "icon": "ShieldAlert", "permission": "treasury_anomaly.view"}
                ]
            }
        ]
    }'::jsonb,
    dashboard_config = '{
        "version": "1.0",
        "layout": "grid",
        "widgets": [
            {"id": "pending_payments", "visible": true, "position": 1, "size": "medium"},
            {"id": "team_workload", "visible": true, "position": 2, "size": "large"},
            {"id": "escalations", "visible": true, "position": 3, "size": "medium"},
            {"id": "anomaly_summary", "visible": true, "position": 4, "size": "medium"},
            {"id": "alerts", "visible": true, "position": 5, "size": "small"}
        ]
    }'::jsonb
WHERE code = 'supervisor_tesoro';


-- =============================================================================
-- SECTION E: ASSIGN PERMISSIONS
-- =============================================================================

-- -----------------------------------------------------------------------------
-- E.1 Add service_request.view_queue_stats to all agent roles
-- Required for Stats Cards (Pending, In Progress, Completed Today, This Week)
-- -----------------------------------------------------------------------------

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.code IN (
    'agent_cnedoge_pasaporte',
    'agent_cnedoge_residencia',
    'agent_dgt',
    'agent_ofive',
    'agent_onrc',
    'agent_tesoro',
    'agent_extranjeria',
    'agent_policia',
    'supervisor',
    'supervisor_tesoro'
)
AND p.name = 'service_request.view_queue_stats'
ON CONFLICT DO NOTHING;

-- -----------------------------------------------------------------------------
-- E.2 Add base service_request permissions to new agent roles
-- -----------------------------------------------------------------------------

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.code IN ('agent_extranjeria', 'agent_policia')
AND p.name IN (
    'service_request.view',
    'service_request.view_my_queue',
    'service_request.view_queue',
    'service_request.view_documents',
    'service_request.view_appointments',
    'service_request.assign_to_self',
    'service_request.process',
    'service_request.approve',
    'service_request.reject',
    'service_request.request_documents',
    'service_request.schedule_appointment',
    'service_request.reschedule_appointment',
    'service_request.cancel_appointment',
    'service_request.release',
    'document.view',
    'document.download'
)
ON CONFLICT DO NOTHING;

-- -----------------------------------------------------------------------------
-- E.3 Add supervisor permissions to supervisor roles
-- Using existing permission names from agent, assignment, queue, rules modules
-- -----------------------------------------------------------------------------

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.code IN ('supervisor', 'supervisor_tesoro')
AND p.name IN (
    -- Team management (agent module)
    'agent.list',
    'agent.view',
    'agent.view_workload',
    'agent.view_performance',
    'agent.manage_workload',
    'agent.set_availability',
    -- Assignments (assignment module)
    'assignment.list',
    'assignment.view',
    'assignment.create',
    'assignment.reassign',
    'assignment.update_priority',
    -- Queue & escalations
    'queue.view',
    'queue.escalate',
    'queue.assign',
    -- Rules
    'rules.view',
    'rules.create',
    'rules.edit',
    'rules.activate',
    -- Service requests (read access)
    'service_request.view',
    'service_request.view_queue'
)
ON CONFLICT DO NOTHING;

COMMIT;

-- =============================================================================
-- VERIFICATION
-- =============================================================================

SELECT 'Migration 078 completed' AS status;

-- Check all agent roles with config
SELECT
    code,
    name,
    entity_type,
    menu_config IS NOT NULL as has_menu_config,
    dashboard_config IS NOT NULL as has_dashboard_config,
    CASE WHEN menu_config IS NOT NULL
         THEN jsonb_array_length(menu_config->'menus')
         ELSE 0
    END as menu_count
FROM roles
WHERE code LIKE 'agent_%' OR code LIKE 'supervisor%'
ORDER BY code;

-- Check appointments menu presence
SELECT
    code,
    COALESCE(menu_config->'menus' @> '[{"id": "appointments"}]'::jsonb, false) as has_appointments_menu
FROM roles
WHERE code IN (
    'agent_cnedoge_pasaporte', 'agent_cnedoge_residencia', 'agent_dgt',
    'agent_extranjeria', 'agent_onrc', 'agent_ofive', 'agent_policia'
);

-- Check service_request.view_queue_stats permission assignment
SELECT
    r.code as role_code,
    EXISTS (
        SELECT 1 FROM role_permissions rp
        JOIN permissions p ON p.id = rp.permission_id
        WHERE rp.role_id = r.id AND p.name = 'service_request.view_queue_stats'
    ) as has_view_queue_stats
FROM roles r
WHERE r.code LIKE 'agent_%' OR r.code LIKE 'supervisor%'
ORDER BY r.code;

-- ============================================================================
-- END OF MIGRATION 078
-- ============================================================================
