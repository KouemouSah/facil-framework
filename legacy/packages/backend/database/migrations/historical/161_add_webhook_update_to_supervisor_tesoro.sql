-- ================================================================
-- Migration 161: Add webhook.update to supervisor_tesoro
--
-- The reconciliation page manual reconcile button calls
-- POST /webhooks/transactions/reconcile which requires webhook.update.
-- supervisor_tesoro had webhook.view (migration 160) but NOT webhook.update → 403.
-- ================================================================

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r, permissions p
WHERE r.code = 'supervisor_tesoro'
  AND p.name = 'webhook.update'
ON CONFLICT DO NOTHING;
