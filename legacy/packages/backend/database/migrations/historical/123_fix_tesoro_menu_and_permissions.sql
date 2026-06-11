-- Migration 123: Fix TESORO agent menu, permissions, and dashboard_config
--
-- Problems fixed:
-- 1. agent_tesoro menu had escalation links pointing to service_request pages
--    (TESORO agents don't handle service_requests, they validate payments)
-- 2. agent_tesoro had service_request.process and service_request.escalate
--    permissions that are service_request-specific, not payment-specific
-- 3. dashboard_config had recent_activity widget that queries service_request_history
--    instead of payment validation history

-- ============================================================================
-- PHASE 1: Remove escalation menu from agent_tesoro
-- (TESORO uses SLA-based auto-escalation, not manual service_request escalation)
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
    }
  ],
  "source": "role",
  "version": "2.1"
}'::jsonb
WHERE code = 'agent_tesoro';

-- ============================================================================
-- PHASE 2: Remove service_request.process and service_request.escalate
-- from agent_tesoro (these are service_request module permissions, not treasury)
-- Keep service_request.view (needed for generic agent widgets)
-- ============================================================================

DELETE FROM role_permissions
WHERE role_id = (SELECT id FROM roles WHERE code = 'agent_tesoro')
  AND permission_id IN (
    SELECT id FROM permissions WHERE name IN (
      'service_request.process',
      'service_request.escalate'
    )
  );

-- ============================================================================
-- PHASE 3: Replace recent_activity widget with a treasury-relevant widget
-- recent_activity queries service_request_history (wrong domain for TESORO)
-- ============================================================================

UPDATE roles
SET dashboard_config = '{
  "layout": "grid",
  "version": "2.1",
  "widgets": [
    {"id": "pending_payments", "size": "medium", "visible": true, "position": 1},
    {"id": "in_progress_payments", "size": "medium", "visible": true, "position": 2},
    {"id": "completed_payments", "size": "medium", "visible": true, "position": 3}
  ]
}'::jsonb
WHERE code = 'agent_tesoro';

-- ============================================================================
-- VERIFY
-- ============================================================================

DO $$
DECLARE
  menu_version TEXT;
  dash_version TEXT;
  has_process BOOLEAN;
  has_escalate BOOLEAN;
  has_view BOOLEAN;
BEGIN
  SELECT menu_config->>'version', dashboard_config->>'version'
  INTO menu_version, dash_version
  FROM roles WHERE code = 'agent_tesoro';

  SELECT EXISTS(
    SELECT 1 FROM role_permissions rp
    JOIN roles r ON r.id = rp.role_id
    JOIN permissions p ON p.id = rp.permission_id
    WHERE r.code = 'agent_tesoro' AND p.name = 'service_request.process'
  ) INTO has_process;

  SELECT EXISTS(
    SELECT 1 FROM role_permissions rp
    JOIN roles r ON r.id = rp.role_id
    JOIN permissions p ON p.id = rp.permission_id
    WHERE r.code = 'agent_tesoro' AND p.name = 'service_request.escalate'
  ) INTO has_escalate;

  SELECT EXISTS(
    SELECT 1 FROM role_permissions rp
    JOIN roles r ON r.id = rp.role_id
    JOIN permissions p ON p.id = rp.permission_id
    WHERE r.code = 'agent_tesoro' AND p.name = 'service_request.view'
  ) INTO has_view;

  RAISE NOTICE 'menu_config version: % (expected 2.1)', menu_version;
  RAISE NOTICE 'dashboard_config version: % (expected 2.1)', dash_version;
  RAISE NOTICE 'service_request.process: % (expected false)', has_process;
  RAISE NOTICE 'service_request.escalate: % (expected false)', has_escalate;
  RAISE NOTICE 'service_request.view: % (expected true)', has_view;
END $$;
