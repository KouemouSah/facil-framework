-- ================================================================
-- Migration 160: Add webhook.view to supervisor_tesoro
--
-- The reconciliation page at /treasury/reconciliation calls
-- GET /webhooks/transactions/unreconciled which requires webhook.view.
-- supervisor_tesoro had treasury.reconcile but NOT webhook.view → 403.
-- ================================================================

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r, permissions p
WHERE r.code = 'supervisor_tesoro'
  AND p.name = 'webhook.view'
ON CONFLICT DO NOTHING;
