-- Migration 124: Batch Payment Grouping + Manual Escalation for TESORO
--
-- Changes:
-- 1. Update v_pending_payment_validations view to include batch_id, batch_reference, batch_total_items
-- 2. Also include escalation columns for supervisor visibility
-- 3. Broaden WHERE clause to include escalated statuses (not just pending_agent_review)
-- 4. Update agent_tesoro menu_config to add escalations link (v2.2)

-- ============================================================================
-- PHASE 1: Recreate v_pending_payment_validations with batch + escalation data
-- NOTE: DROP+CREATE required because column set changes (17 -> 25 columns).
--       CREATE OR REPLACE fails when column names change at existing positions.
-- ============================================================================

DROP VIEW IF EXISTS v_pending_payment_validations;

CREATE VIEW v_pending_payment_validations AS
SELECT
    sp.id AS payment_id,
    sp.payment_reference,
    sp.service_request_id,
    sr.reference AS request_reference,
    sr.workflow_code,
    sp.user_id,
    u.full_name AS user_name,
    u.email AS user_email,
    sp.payment_method,
    sp.total_amount,
    sp.currency,
    sp.workflow_status,
    sp.assigned_agent_id AS assigned_agent_profile_id,
    assigned_ap.user_id AS assigned_to_user_id,
    assigned_user.full_name AS assigned_to_name,
    -- Batch fields
    sp.batch_id,
    br.reference AS batch_reference,
    br.total_items AS batch_total_items,
    -- Escalation fields
    sp.escalated_to_agent_id,
    sp.escalation_level,
    sp.escalation_reason,
    sp.escalated_at,
    sp.sla_escalated,
    -- Timestamps
    sp.created_at,
    EXTRACT(EPOCH FROM (NOW() - sp.created_at)) / 3600 AS hours_waiting
FROM service_payments sp
LEFT JOIN service_requests sr ON sp.service_request_id = sr.id
LEFT JOIN users u ON sp.user_id = u.id
LEFT JOIN agent_profiles assigned_ap ON sp.assigned_agent_id = assigned_ap.id
LEFT JOIN users assigned_user ON assigned_ap.user_id = assigned_user.id
LEFT JOIN batch_requests br ON sp.batch_id = br.id
WHERE sp.requires_agent_validation = true
ORDER BY sp.created_at;

-- ============================================================================
-- PHASE 2: Update agent_tesoro menu_config to add escalations link (v2.2)
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
          "id": "my_escalations",
          "href": "/dashboard/agent/treasury/escalations",
          "icon": "AlertTriangle",
          "titleKey": "agent.nav.myEscalations",
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
  "version": "2.2"
}'::jsonb
WHERE code = 'agent_tesoro';

-- ============================================================================
-- VERIFY
-- ============================================================================

DO $$
DECLARE
  menu_version TEXT;
  view_cols INTEGER;
BEGIN
  -- Check menu version
  SELECT menu_config->>'version'
  INTO menu_version
  FROM roles WHERE code = 'agent_tesoro';

  -- Check view has batch_id column
  SELECT COUNT(*) INTO view_cols
  FROM information_schema.columns
  WHERE table_name = 'v_pending_payment_validations'
    AND column_name IN ('batch_id', 'batch_reference', 'batch_total_items', 'escalation_level', 'escalated_at');

  RAISE NOTICE 'agent_tesoro menu_config version: % (expected 2.2)', menu_version;
  RAISE NOTICE 'View batch+escalation columns: % / 5 expected', view_cols;
END $$;
