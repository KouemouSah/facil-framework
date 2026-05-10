-- ============================================================================
-- Migration 065: Add Supervisor and Escalation Permissions
-- ============================================================================
-- Purpose: Add supervisor and escalation permissions for future use
--
-- VERIFIED AGAINST DATABASE STATE (2026-01-25):
--   - Existing roles: agent_tesoro (ONLY agent role that exists)
--   - NON-EXISTENT: supervisor_agent, supervisor_tesoro, ministry_validator, etc.
--
-- This migration:
--   1. ADDS permissions for supervisor and escalation features
--   2. ADDS include_escalation column to workflow_menu_mapping
--   3. UPDATES agent_tesoro menu to include escalation
--   4. Does NOT update non-existent roles (clean migration)
--
-- NOTE: When supervisor/ministry roles are created in the future,
-- they should be assigned these permissions via role_permissions.
--
-- Author: Claude Code Expert
-- Date: 2026-01-19
-- Revised: 2026-01-25 (removed references to non-existent roles)
-- ============================================================================

BEGIN;

-- =============================================================================
-- 1. ADD SUPERVISOR PERMISSIONS
-- =============================================================================
-- These permissions will be used when supervisor roles are created

INSERT INTO permissions (name, resource, action, description, is_critical, module_name, created_at, updated_at)
VALUES
    -- Dashboard permissions
    ('supervisor.dashboard.view', 'supervisor_dashboard', 'read', 'Ver dashboard de supervisor', FALSE, 'supervisor', NOW(), NOW()),

    -- Team Management
    ('supervisor.team.view', 'supervisor_team', 'read', 'Ver equipo bajo supervision', FALSE, 'supervisor', NOW(), NOW()),
    ('supervisor.team.manage', 'supervisor_team', 'write', 'Gestionar equipo (activar/desactivar agentes)', TRUE, 'supervisor', NOW(), NOW()),

    -- Workload Management
    ('supervisor.workload.view', 'supervisor_workload', 'read', 'Ver distribucion de carga de trabajo', FALSE, 'supervisor', NOW(), NOW()),
    ('supervisor.workload.balance', 'supervisor_workload', 'write', 'Reequilibrar carga de trabajo entre agentes', TRUE, 'supervisor', NOW(), NOW()),

    -- Assignment Rules
    ('supervisor.rules.view', 'assignment_rules', 'read', 'Ver reglas de asignacion automatica', FALSE, 'supervisor', NOW(), NOW()),
    ('supervisor.rules.create', 'assignment_rules', 'create', 'Crear reglas de asignacion', TRUE, 'supervisor', NOW(), NOW()),
    ('supervisor.rules.update', 'assignment_rules', 'update', 'Modificar reglas de asignacion', TRUE, 'supervisor', NOW(), NOW()),
    ('supervisor.rules.delete', 'assignment_rules', 'delete', 'Eliminar reglas de asignacion', TRUE, 'supervisor', NOW(), NOW()),
    ('supervisor.rules.activate', 'assignment_rules', 'activate', 'Activar/desactivar reglas', TRUE, 'supervisor', NOW(), NOW()),

    -- Performance Stats
    ('supervisor.stats.view', 'supervisor_stats', 'read', 'Ver estadisticas de rendimiento del equipo', FALSE, 'supervisor', NOW(), NOW()),
    ('supervisor.stats.export', 'supervisor_stats', 'export', 'Exportar estadisticas del equipo', FALSE, 'supervisor', NOW(), NOW()),

    -- Escalation Management (Supervisor receiving escalations)
    ('supervisor.escalations.view', 'escalations', 'read', 'Ver escalaciones recibidas', FALSE, 'supervisor', NOW(), NOW()),
    ('supervisor.escalations.resolve', 'escalations', 'resolve', 'Resolver escalaciones', TRUE, 'supervisor', NOW(), NOW()),
    ('supervisor.escalations.reassign', 'escalations', 'reassign', 'Reasignar casos escalados', TRUE, 'supervisor', NOW(), NOW()),

    -- Escalation Initiation (Agents initiating escalations)
    ('agent.escalation.create', 'escalations', 'create', 'Escalar caso a supervisor', FALSE, 'agent', NOW(), NOW()),
    ('agent.escalation.view_own', 'escalations', 'read_own', 'Ver mis escalaciones enviadas', FALSE, 'agent', NOW(), NOW())
ON CONFLICT (name) DO NOTHING;

-- =============================================================================
-- 2. ADD ESCALATION COLUMN TO WORKFLOW_MENU_MAPPING
-- =============================================================================

ALTER TABLE workflow_menu_mapping ADD COLUMN IF NOT EXISTS include_escalation BOOLEAN DEFAULT TRUE;
COMMENT ON COLUMN workflow_menu_mapping.include_escalation IS 'Include escalation menu item for this workflow group';

-- Enable escalation for all workflow mappings
UPDATE workflow_menu_mapping SET include_escalation = TRUE WHERE include_escalation IS NULL;

-- =============================================================================
-- 3. GRANT ESCALATION PERMISSIONS TO AGENT_TESORO (ONLY EXISTING ROLE)
-- =============================================================================

INSERT INTO role_permissions (role_id, permission_id, created_at)
SELECT r.id, p.id, NOW()
FROM roles r
CROSS JOIN permissions p
WHERE r.code = 'agent_tesoro'
  AND p.name IN (
    'agent.escalation.create',
    'agent.escalation.view_own'
  )
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- =============================================================================
-- 4. UPDATE AGENT_TESORO MENU WITH ESCALATION
-- =============================================================================
-- agent_tesoro is the ONLY existing agent role - update its menu
-- ALIGNED WITH: packages/web/src/modules/agent-dashboard/config/entity-menus.ts TESORO_CONFIG

UPDATE roles SET menu_config = '{
    "version": "1.0",
    "source": "role",
    "menus": [
        {
            "id": "dashboard",
            "titleKey": "agent.nav.dashboard",
            "href": "/dashboard/agent/treasury",
            "icon": "LayoutDashboard"
        },
        {
            "id": "payments",
            "titleKey": "agent.nav.payments",
            "icon": "CreditCard",
            "items": [
                {"id": "validation", "titleKey": "agent.nav.validation", "href": "/dashboard/agent/treasury/validation", "icon": "CheckCircle", "permission": "treasury.validate_payment"},
                {"id": "reconciliation", "titleKey": "agent.nav.reconciliation", "href": "/dashboard/agent/treasury/reconciliation", "icon": "RefreshCw", "permission": "treasury.reconcile"},
                {"id": "transactions", "titleKey": "agent.nav.transactions", "href": "/dashboard/agent/treasury/transactions", "icon": "History", "permission": "treasury.view_payment"}
            ]
        },
        {
            "id": "reports",
            "titleKey": "agent.nav.reports",
            "icon": "BarChart3",
            "items": [
                {"id": "stats", "titleKey": "agent.nav.stats", "href": "/dashboard/agent/treasury/stats", "icon": "TrendingUp", "permission": "treasury_stat.view"},
                {"id": "analytics", "titleKey": "agent.nav.analytics", "href": "/dashboard/agent/treasury/analytics", "icon": "Activity", "permission": "treasury_stat.view"},
                {"id": "audit", "titleKey": "agent.nav.audit", "href": "/dashboard/agent/treasury/audit", "icon": "FileSearch", "permission": "treasury_audit.view"},
                {"id": "sla", "titleKey": "agent.nav.slaStats", "href": "/dashboard/agent/treasury/stats/sla", "icon": "BarChart3", "permission": "treasury_stat.view"},
                {"id": "anomalies", "titleKey": "agent.nav.anomalies", "href": "/dashboard/agent/treasury/anomalies", "icon": "ShieldAlert", "permission": "treasury_anomaly.view"},
                {"id": "exports", "titleKey": "agent.nav.exports", "href": "/dashboard/agent/treasury/exports", "icon": "FileSpreadsheet", "permission": "treasury_export.view"}
            ]
        },
        {
            "id": "escalations",
            "titleKey": "agent.nav.myEscalations",
            "icon": "AlertTriangle",
            "permission": "agent.escalation.view_own",
            "items": [
                {"id": "create", "titleKey": "agent.nav.escalate", "href": "/dashboard/agent/escalations/new", "icon": "AlertCircle", "permission": "agent.escalation.create"},
                {"id": "my_escalations", "titleKey": "agent.nav.myEscalations", "href": "/dashboard/agent/escalations", "icon": "List", "permission": "agent.escalation.view_own"}
            ]
        },
        {
            "id": "settings",
            "titleKey": "agent.nav.settings",
            "icon": "Settings",
            "permission": "treasury.manage_settings",
            "items": [
                {"id": "banks", "titleKey": "agent.nav.banks", "href": "/dashboard/agent/treasury/settings/banks", "icon": "Building2", "permission": "treasury.manage_settings"},
                {"id": "payment-methods", "titleKey": "agent.nav.paymentMethods", "href": "/dashboard/agent/treasury/settings/payment-methods", "icon": "Banknote", "permission": "treasury.manage_settings"}
            ]
        }
    ]
}',
dashboard_config = '{
    "version": "1.0",
    "layout": "grid",
    "widgets": [
        {"id": "pending_payments", "visible": true, "position": 1, "size": "small"},
        {"id": "in_progress_payments", "visible": true, "position": 2, "size": "small"},
        {"id": "completed_payments", "visible": true, "position": 3, "size": "small"},
        {"id": "my_escalations", "visible": true, "position": 4, "size": "small"},
        {"id": "recent_activity", "visible": true, "position": 5, "size": "large"}
    ]
}'
WHERE code = 'agent_tesoro';

COMMIT;

-- =============================================================================
-- VERIFICATION
-- =============================================================================

SELECT
    'Migration 065 completed' AS status,
    (SELECT COUNT(*) FROM permissions WHERE name LIKE 'supervisor.%') AS supervisor_permissions,
    (SELECT COUNT(*) FROM permissions WHERE name LIKE 'agent.escalation.%') AS agent_escalation_permissions;

-- Verify agent_tesoro has escalation menu
SELECT
    r.code,
    CASE WHEN r.menu_config::text LIKE '%escalation%' THEN 'Yes' ELSE 'No' END as has_escalation_menu
FROM roles r
WHERE r.code = 'agent_tesoro';

-- ============================================================================
-- END OF MIGRATION 065
-- ============================================================================
