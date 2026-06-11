-- Migration 185: Backfill submitted_at for existing SUBMITTED requests
-- Bug: agent_queue_handler set status='SUBMITTED' but never set submitted_at
-- Result: SLA always showed "-" (green on_track) because sla_remaining_hours was null

-- Backfill: use created_at as best approximation for existing requests
UPDATE service_requests
SET submitted_at = COALESCE(
    -- Try to find the actual submission timestamp from history
    (SELECT created_at FROM service_request_history
     WHERE service_request_id = service_requests.id
       AND new_status = 'SUBMITTED'
     ORDER BY created_at ASC LIMIT 1),
    -- Fallback to created_at
    created_at
)
WHERE submitted_at IS NULL
  AND status NOT IN ('DRAFT', 'CANCELLED');
