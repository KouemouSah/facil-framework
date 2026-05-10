-- ============================================================================
-- Migration 102: Fix batch reference generation race condition
--
-- Problem: Concurrent INSERTs into batch_requests can generate duplicate
--          references because SELECT MAX() + INSERT is not atomic.
-- Solution: pg_advisory_xact_lock ensures only one trigger runs at a time.
-- ============================================================================

CREATE OR REPLACE FUNCTION generate_batch_reference()
RETURNS TRIGGER AS $$
DECLARE
    year_str TEXT := TO_CHAR(NOW(), 'YYYY');
    seq_num INT;
BEGIN
    -- Advisory lock prevents concurrent triggers from reading same MAX
    -- Lock key: hash of 'batch_ref' (stable across restarts)
    PERFORM pg_advisory_xact_lock(hashtext('batch_reference_gen'));

    SELECT COALESCE(MAX(CAST(SUBSTRING(reference FROM 'LOT-' || year_str || '-(\d+)') AS INT)), 0) + 1
    INTO seq_num FROM batch_requests WHERE reference LIKE 'LOT-' || year_str || '-%';

    NEW.reference := 'LOT-' || year_str || '-' || LPAD(seq_num::TEXT, 5, '0');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Also add a UNIQUE index on reference as a safety net
CREATE UNIQUE INDEX IF NOT EXISTS idx_batch_requests_reference_unique
    ON batch_requests(reference);

-- Index on workflow_code for agent queries (WHERE workflow_code = ANY($1::text[]))
CREATE INDEX IF NOT EXISTS idx_batch_requests_workflow_code
    ON batch_requests(workflow_code);

-- Index on submitted_by for citizen batch list queries
CREATE INDEX IF NOT EXISTS idx_batch_requests_submitted_by
    ON batch_requests(submitted_by);
