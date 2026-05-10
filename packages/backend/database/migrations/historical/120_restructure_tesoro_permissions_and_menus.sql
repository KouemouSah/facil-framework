-- Migration 120: Restructure TESORO agent/supervisor roles
-- Principle: Agents = validate payments only. Supervisors = reports, settings, reconciliation.
-- Separation of duties: validator != reconciler != exporter

-- ============================================================================
-- PHASE 1: Remove report/settings/reconciliation permissions from agent_tesoro
-- ============================================================================

DELETE FROM role_permissions
WHERE role_id = (SELECT id FROM roles WHERE code = 'agent_tesoro')
  AND permission_id IN (
    SELECT id FROM permissions WHERE name IN (
      'treasury_stat.view',
      'treasury_stat.export',
      'treasury_audit.view',
      'treasury_audit.export',
      'treasury_anomaly.view',
      'treasury_anomaly.create',
      'treasury_anomaly.update',
      'treasury_anomaly.resolve',
      'treasury_export.view',
      'treasury_export.create',
      'treasury_export.download',
      'treasury.manage_settings',
      'treasury.reconcile',
      'treasury.view_reconciliation',
      -- Also remove generic report permissions (supervisor-level)
      'reports.view_financial',
      'reports.view_performance',
      'reports.generate',
      'reports.export_excel',
      'reports.export_pdf'
    )
  );

-- Add escalation permissions to agent_tesoro (needed for escalation menu)
INSERT INTO role_permissions (role_id, permission_id)
SELECT
  (SELECT id FROM roles WHERE code = 'agent_tesoro'),
  p.id
FROM permissions p
WHERE p.name IN ('agent.escalation.create', 'agent.escalation.view_own')
  AND NOT EXISTS (
    SELECT 1 FROM role_permissions rp
    WHERE rp.role_id = (SELECT id FROM roles WHERE code = 'agent_tesoro')
      AND rp.permission_id = p.id
  );

-- ============================================================================
-- PHASE 2: Ensure supervisor_tesoro has ALL required permissions
-- ============================================================================

-- Add any missing report/financial permissions to supervisor
INSERT INTO role_permissions (role_id, permission_id)
SELECT
  (SELECT id FROM roles WHERE code = 'supervisor_tesoro'),
  p.id
FROM permissions p
WHERE p.name IN (
  'reports.view',
  'reports.view_financial',
  'reports.view_performance',
  'reports.generate',
  'reports.export_excel',
  'reports.export_pdf',
  'receipt.view',
  'receipt.regenerate',
  'payment.view',
  'payment.view_all',
  'payment.view_reconciliation',
  'agent.escalation.create',
  'agent.escalation.view_own'
)
AND NOT EXISTS (
  SELECT 1 FROM role_permissions rp
  WHERE rp.role_id = (SELECT id FROM roles WHERE code = 'supervisor_tesoro')
    AND rp.permission_id = p.id
);

-- ============================================================================
-- PHASE 3: Update menu_config for agent_tesoro (simplified)
-- ============================================================================

UPDATE roles
SET menu_config = '{
  "menus": [
    {
      "id": "dashboard",
      "href": "/dashboard/agent/treasury",
      "icon": "LayoutDashboard",
      "titleKey": "agent.nav.dashboard"
    },
    {
      "id": "payments",
      "icon": "CreditCard",
      "titleKey": "agent.nav.payments",
      "items": [
        {
          "id": "validation",
          "href": "/dashboard/agent/treasury/validation",
          "icon": "CheckCircle",
          "titleKey": "agent.nav.validation",
          "permission": "treasury.validate_payment"
        },
        {
          "id": "my_transactions",
          "href": "/dashboard/agent/treasury/transactions",
          "icon": "History",
          "titleKey": "agent.nav.myTransactions",
          "permission": "treasury.view_payment"
        }
      ]
    },
    {
      "id": "escalations",
      "icon": "AlertTriangle",
      "titleKey": "agent.nav.myEscalations",
      "items": [
        {
          "id": "create",
          "href": "/dashboard/agent/escalations/new",
          "icon": "AlertCircle",
          "titleKey": "agent.nav.escalate"
        },
        {
          "id": "my_escalations",
          "href": "/dashboard/agent/escalations",
          "icon": "List",
          "titleKey": "agent.nav.myEscalations"
        }
      ]
    }
  ],
  "source": "role",
  "version": "2.0"
}'::jsonb
WHERE code = 'agent_tesoro';

-- ============================================================================
-- PHASE 4: Update menu_config for supervisor_tesoro (enriched)
-- ============================================================================

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
      "id": "treasury_overview",
      "href": "/dashboard/agent/treasury",
      "icon": "Wallet",
      "titleKey": "supervisor.nav.treasuryOverview",
      "permission": "treasury.view_payment"
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
          "permission": "agent.list"
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
      "id": "payments",
      "icon": "CreditCard",
      "titleKey": "supervisor.nav.payments",
      "items": [
        {
          "id": "validation",
          "href": "/dashboard/agent/treasury/validation",
          "icon": "CheckCircle",
          "titleKey": "supervisor.nav.validation",
          "permission": "treasury.validate_payment"
        },
        {
          "id": "reconciliation",
          "href": "/dashboard/agent/treasury/reconciliation",
          "icon": "RefreshCw",
          "titleKey": "supervisor.nav.reconciliation",
          "permission": "treasury.reconcile"
        },
        {
          "id": "transactions",
          "href": "/dashboard/agent/treasury/transactions",
          "icon": "History",
          "titleKey": "supervisor.nav.transactions",
          "permission": "treasury.view_payment"
        }
      ]
    },
    {
      "id": "reports",
      "icon": "BarChart3",
      "titleKey": "supervisor.nav.reports",
      "items": [
        {
          "id": "stats",
          "href": "/dashboard/agent/treasury/stats",
          "icon": "TrendingUp",
          "titleKey": "supervisor.nav.stats",
          "permission": "treasury_stat.view"
        },
        {
          "id": "analytics",
          "href": "/dashboard/agent/treasury/analytics",
          "icon": "Activity",
          "titleKey": "supervisor.nav.analytics",
          "permission": "treasury_stat.view"
        },
        {
          "id": "agent_stats",
          "href": "/dashboard/agent/treasury/stats/agents",
          "icon": "BarChart3",
          "titleKey": "supervisor.nav.agentStats",
          "permission": "treasury_stat.view"
        },
        {
          "id": "sla",
          "href": "/dashboard/agent/treasury/stats/sla",
          "icon": "Clock",
          "titleKey": "supervisor.nav.sla",
          "permission": "treasury_stat.view"
        },
        {
          "id": "audit",
          "href": "/dashboard/agent/treasury/audit",
          "icon": "FileSearch",
          "titleKey": "supervisor.nav.audit",
          "permission": "treasury_audit.view"
        },
        {
          "id": "anomalies",
          "href": "/dashboard/agent/treasury/anomalies",
          "icon": "ShieldAlert",
          "titleKey": "supervisor.nav.anomalies",
          "permission": "treasury_anomaly.view"
        },
        {
          "id": "exports",
          "href": "/dashboard/agent/treasury/exports",
          "icon": "FileSpreadsheet",
          "titleKey": "supervisor.nav.exports",
          "permission": "treasury_export.view"
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
          "permission": "queue.escalate"
        }
      ]
    },
    {
      "id": "assignments",
      "icon": "Settings2",
      "titleKey": "supervisor.nav.assignments",
      "items": [
        {
          "id": "list",
          "href": "/dashboard/admin/assignments",
          "icon": "ClipboardList",
          "titleKey": "supervisor.nav.assignmentsList",
          "permission": "assignment.list"
        },
        {
          "id": "manual",
          "href": "/dashboard/admin/assignments/new/manual",
          "icon": "UserPlus",
          "titleKey": "supervisor.nav.manualAssignment",
          "permission": "assignment.reassign"
        },
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
      "id": "settings",
      "icon": "Settings",
      "titleKey": "supervisor.nav.settings",
      "permission": "treasury.manage_settings",
      "items": [
        {
          "id": "banks",
          "href": "/dashboard/agent/treasury/settings/banks",
          "icon": "Building2",
          "titleKey": "supervisor.nav.banks",
          "permission": "treasury.manage_settings"
        },
        {
          "id": "payment-methods",
          "href": "/dashboard/agent/treasury/settings/payment-methods",
          "icon": "Banknote",
          "titleKey": "supervisor.nav.paymentMethods",
          "permission": "treasury.manage_settings"
        }
      ]
    }
  ],
  "source": "role",
  "version": "2.0"
}'::jsonb
WHERE code = 'supervisor_tesoro';

-- ============================================================================
-- PHASE 5: Update dashboard_config for agent_tesoro (personal widgets only)
-- ============================================================================

UPDATE roles
SET dashboard_config = '{
  "layout": "grid",
  "version": "2.0",
  "widgets": [
    {"id": "pending_payments", "size": "medium", "visible": true, "position": 1},
    {"id": "in_progress_payments", "size": "medium", "visible": true, "position": 2},
    {"id": "completed_payments", "size": "medium", "visible": true, "position": 3},
    {"id": "recent_activity", "size": "large", "visible": true, "position": 4}
  ]
}'::jsonb
WHERE code = 'agent_tesoro';

-- Supervisor dashboard_config stays the same (team-oriented widgets)

-- ============================================================================
-- VERIFY
-- ============================================================================

DO $$
DECLARE
    agent_perm_count INTEGER;
    sup_perm_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO agent_perm_count
    FROM role_permissions rp
    JOIN roles r ON r.id = rp.role_id
    WHERE r.code = 'agent_tesoro';

    SELECT COUNT(*) INTO sup_perm_count
    FROM role_permissions rp
    JOIN roles r ON r.id = rp.role_id
    WHERE r.code = 'supervisor_tesoro';

    RAISE NOTICE 'agent_tesoro: % permissions (expected ~21)', agent_perm_count;
    RAISE NOTICE 'supervisor_tesoro: % permissions (expected ~55)', sup_perm_count;
END $$;
