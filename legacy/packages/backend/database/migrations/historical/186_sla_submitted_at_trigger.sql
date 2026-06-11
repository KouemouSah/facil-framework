-- Migration 186: SLA guard — auto-set submitted_at on SUBMITTED transition
-- Prevents future code paths from forgetting submitted_at (which breaks SLA computation)
-- Also cleans up orphaned queue items from request_documents flow

BEGIN;

-- 1. Trigger: auto-set submitted_at when status transitions to SUBMITTED
CREATE OR REPLACE FUNCTION fn_auto_set_submitted_at()
RETURNS TRIGGER AS $$
BEGIN
  IF NEW.status = 'SUBMITTED' AND (OLD.status IS NULL OR OLD.status != 'SUBMITTED') THEN
    IF NEW.submitted_at IS NULL THEN
      NEW.submitted_at := NOW();
    END IF;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Drop if exists (idempotent)
DROP TRIGGER IF EXISTS trg_auto_submitted_at ON service_requests;

CREATE TRIGGER trg_auto_submitted_at
  BEFORE UPDATE ON service_requests
  FOR EACH ROW
  EXECUTE FUNCTION fn_auto_set_submitted_at();

-- 2. Clean up orphaned queue items from request_documents flow
-- When agent does "request_documents", queue item is set to pending/NULL
-- but when citizen re-submits, a NEW queue item is created.
-- Old ones stay forever as pending orphans.
UPDATE agent_work_queue
SET status = 'cancelled',
    updated_at = NOW()
WHERE status = 'pending'
  AND assigned_to IS NULL
  AND item_type = 'service_request'
  AND item_id IN (
    SELECT id FROM service_requests
    WHERE status NOT IN ('SUBMITTED', 'UNDER_REVIEW', 'DOSSIER_VALIDE')
  )
  AND EXISTS (
    -- Only cancel if there's a NEWER queue item for the same request
    SELECT 1 FROM agent_work_queue awq2
    WHERE awq2.item_id = agent_work_queue.item_id
      AND awq2.item_type = 'service_request'
      AND awq2.id != agent_work_queue.id
      AND awq2.created_at > agent_work_queue.created_at
  );

COMMIT;
