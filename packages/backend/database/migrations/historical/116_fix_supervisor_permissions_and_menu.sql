-- Migration 116: Fix supervisor permissions and menu_config
-- Fixes:
--   P0: Create 3 missing escalation permissions (escalations.view/assign/resolve)
--   P1: Update supervisor menu_config (add Reports, Resolved Escalations)
--   P5: Fix permission reference agent.list → agent.view in menu_config
--
-- Date: 2026-02-21

BEGIN;

-- =============================================================================
-- P0: Create missing escalation permissions
-- Without these, ALL supervisor escalation endpoints return 403
-- =============================================================================

INSERT INTO permissions (id, name, resource, action, description, module_name, is_critical)
VALUES
  (gen_random_uuid(), 'escalations.view', 'escalations', 'read', 'View escalated service requests', 'escalations', false),
  (gen_random_uuid(), 'escalations.assign', 'escalations', 'write', 'Assign escalated requests to agents', 'escalations', false),
  (gen_random_uuid(), 'escalations.resolve', 'escalations', 'write', 'Resolve, approve, or reject escalations', 'escalations', true)
ON CONFLICT (name) DO NOTHING;

-- Assign to supervisor role
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.code = 'supervisor'
  AND p.name IN ('escalations.view', 'escalations.assign', 'escalations.resolve')
ON CONFLICT DO NOTHING;

-- Also assign escalations.view to supervisor_tesoro (read-only visibility)
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.code = 'supervisor_tesoro'
  AND p.name = 'escalations.view'
ON CONFLICT DO NOTHING;

-- =============================================================================
-- P1 + P5: Update supervisor menu_config
-- Add Reports page, Resolved Escalations sub-item, fix agent.list → agent.view
-- =============================================================================

UPDATE roles
SET menu_config = '{
  "menus": [
    {
      "id": "dashboard",
      "href": "/dashboard/supervisor",
      "icon": "LayoutDashboard",
      "titleKey": "supervisor.nav.dashboard"
    },
    {
      "id": "team",
      "icon": "Users",
      "titleKey": "supervisor.nav.team",
      "items": [
        {
          "id": "agents",
          "href": "/dashboard/supervisor/team/agents",
          "icon": "User",
          "titleKey": "supervisor.nav.agents",
          "permission": "agent.view"
        },
        {
          "id": "workload",
          "href": "/dashboard/supervisor/team/workload",
          "icon": "BarChart2",
          "titleKey": "supervisor.nav.workload",
          "permission": "agent.view_workload"
        },
        {
          "id": "performance",
          "href": "/dashboard/supervisor/team/performance",
          "icon": "TrendingUp",
          "titleKey": "supervisor.nav.performance",
          "permission": "agent.view_performance"
        }
      ]
    },
    {
      "id": "escalations",
      "icon": "AlertTriangle",
      "titleKey": "supervisor.nav.escalations",
      "items": [
        {
          "id": "pending",
          "href": "/dashboard/supervisor/escalations/pending",
          "icon": "Clock",
          "titleKey": "supervisor.nav.pendingEscalations",
          "permission": "escalations.view"
        },
        {
          "id": "resolved",
          "href": "/dashboard/supervisor/escalations/resolved",
          "icon": "CheckCircle",
          "titleKey": "supervisor.nav.resolvedEscalations",
          "permission": "escalations.view"
        }
      ]
    },
    {
      "id": "assignments",
      "icon": "Settings2",
      "titleKey": "supervisor.nav.assignments",
      "items": [
        {
          "id": "rules",
          "href": "/dashboard/supervisor/assignments/rules",
          "icon": "ListChecks",
          "titleKey": "supervisor.nav.rules",
          "permission": "rules.view"
        }
      ]
    },
    {
      "id": "reports",
      "href": "/dashboard/supervisor/reports",
      "icon": "FileBarChart",
      "titleKey": "supervisor.nav.reports",
      "permission": "dashboard.view"
    }
  ],
  "source": "role",
  "version": "1.1"
}'::jsonb
WHERE code = 'supervisor';

COMMIT;
