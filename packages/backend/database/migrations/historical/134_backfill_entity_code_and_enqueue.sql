-- Migration 134: Backfill entity_code on service_requests where NULL
-- Also enqueue PAID requests into assignment_outbox for processing
--
-- Context: 9 PAID service_requests have entity_code=NULL because they were
-- created before the persist path set entity_code. The outbox enqueue guard
-- skips requests with NULL entity_code, so these requests are stuck in PAID
-- status with no agent assignment.
--
-- Strategy:
-- 1. Resolve entity_code from entity_location_id (FK → entity_locations.entity_code)
-- 2. Fallback: resolve from workflow_code → entities.workflow_codes JSONB
-- 3. Enqueue resolved requests into assignment_outbox for cron processing

-- Step 1: Backfill entity_code from entity_location_id
UPDATE service_requests sr
SET entity_code = el.entity_code,
    updated_at = NOW()
FROM entity_locations el
WHERE sr.entity_location_id = el.id
  AND sr.entity_code IS NULL
  AND el.entity_code IS NOT NULL;

-- Step 2: Backfill entity_code from workflow_code → entities.workflow_codes
UPDATE service_requests sr
SET entity_code = (
    SELECT e.code FROM entities e
    WHERE e.workflow_codes ? sr.workflow_code
      AND e.is_active = true
    LIMIT 1
),
    updated_at = NOW()
WHERE sr.entity_code IS NULL
  AND sr.workflow_code IS NOT NULL;

-- Step 3: Enqueue PAID requests that are not yet in outbox
INSERT INTO assignment_outbox (
    id, service_request_id, workflow_code, entity_code,
    entity_location_id, status, retry_count, max_retries,
    created_at, updated_at, next_retry_at
)
SELECT
    gen_random_uuid(),
    sr.id,
    sr.workflow_code,
    sr.entity_code,
    sr.entity_location_id,
    'pending',
    0,
    5,
    NOW(),
    NOW(),
    NOW()
FROM service_requests sr
WHERE sr.status = 'PAID'
  AND sr.payment_status = 'completed'
  AND sr.entity_code IS NOT NULL
  AND sr.assigned_to IS NULL
  AND NOT EXISTS (
    SELECT 1 FROM assignment_outbox ao
    WHERE ao.service_request_id = sr.id
      AND ao.status IN ('pending', 'processing', 'completed')
  )
ON CONFLICT DO NOTHING;
