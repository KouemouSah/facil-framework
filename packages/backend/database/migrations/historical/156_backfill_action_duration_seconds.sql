-- Migration 156: Backfill action_duration_seconds for existing audit records
-- This column was never populated before. New meaning: total time from payment
-- creation (sp.created_at) to agent action (pva.created_at), in seconds.
-- Going forward, the 3 INSERT statements (approve/reject/escalate) compute this live.

UPDATE payment_validation_audit pva
SET action_duration_seconds = EXTRACT(EPOCH FROM (pva.created_at - sp.created_at))::int
FROM service_payments sp
WHERE sp.id = pva.payment_id
  AND pva.action_duration_seconds IS NULL;
