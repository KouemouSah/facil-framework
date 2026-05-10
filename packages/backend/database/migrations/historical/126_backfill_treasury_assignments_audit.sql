-- Migration 126: Backfill treasury assignment statuses and audit trail
--
-- Problem: validate_payment/reject_payment/escalate_payment never updated
-- assignments.status or inserted into payment_validation_audit.
-- This migration fixes existing out-of-sync records.
--
-- After this migration, the code fix in admin_routes.py will keep them in sync going forward.

BEGIN;

-- 1. Mark validated payments' assignments as completed
UPDATE assignments a
SET status = 'completed',
    completed_at = sp.validated_at,
    processing_duration_hours = EXTRACT(EPOCH FROM (sp.validated_at - a.assigned_at)) / 3600,
    updated_at = NOW()
FROM service_payments sp
WHERE a.item_id = sp.id
  AND a.item_type = 'payment_validation'
  AND sp.workflow_status = 'completed'
  AND a.status = 'assigned';

-- 2. Mark rejected payments' assignments as rejected
UPDATE assignments a
SET status = 'rejected',
    completed_at = sp.validated_at,
    processing_duration_hours = EXTRACT(EPOCH FROM (sp.validated_at - a.assigned_at)) / 3600,
    updated_at = NOW()
FROM service_payments sp
WHERE a.item_id = sp.id
  AND a.item_type = 'payment_validation'
  AND sp.workflow_status = 'rejected_by_agent'
  AND a.status = 'assigned';

-- 3. Mark escalated payments' assignments as cancelled
UPDATE assignments a
SET status = 'cancelled',
    completed_at = sp.escalated_at,
    processing_duration_hours = EXTRACT(EPOCH FROM (sp.escalated_at - a.assigned_at)) / 3600,
    notes = 'Escalated: ' || COALESCE(sp.escalation_reason, 'N/A'),
    updated_at = NOW()
FROM service_payments sp
WHERE a.item_id = sp.id
  AND a.item_type = 'payment_validation'
  AND sp.workflow_status = 'escalated_supervisor'
  AND a.status = 'assigned';

-- 4. Backfill payment_validation_audit for validated payments
INSERT INTO payment_validation_audit
    (id, payment_id, agent_profile_id, agent_user_id, action, from_status, to_status, comment, created_at)
SELECT
    gen_random_uuid(),
    sp.id,
    sp.validated_by_agent_id,
    (SELECT user_id FROM agent_profiles WHERE id = sp.validated_by_agent_id),
    'approve'::agent_action_type,
    'pending_agent_review'::payment_workflow_status,
    'completed'::payment_workflow_status,
    sp.validation_comment,
    sp.validated_at
FROM service_payments sp
WHERE sp.workflow_status = 'completed'
  AND sp.validated_by_agent_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM payment_validation_audit pva
      WHERE pva.payment_id = sp.id AND pva.action = 'approve'
  );

-- 5. Backfill payment_validation_audit for rejected payments
INSERT INTO payment_validation_audit
    (id, payment_id, agent_profile_id, agent_user_id, action, from_status, to_status, comment, created_at)
SELECT
    gen_random_uuid(),
    sp.id,
    sp.validated_by_agent_id,
    (SELECT user_id FROM agent_profiles WHERE id = sp.validated_by_agent_id),
    'reject'::agent_action_type,
    'pending_agent_review'::payment_workflow_status,
    'rejected_by_agent'::payment_workflow_status,
    sp.validation_comment,
    sp.validated_at
FROM service_payments sp
WHERE sp.workflow_status = 'rejected_by_agent'
  AND sp.validated_by_agent_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM payment_validation_audit pva
      WHERE pva.payment_id = sp.id AND pva.action = 'reject'
  );

COMMIT;
