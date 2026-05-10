-- Migration 113: Add escalation columns to service_requests
-- =============================================================================
-- The escalation system was previously tied to agent_work_queue (legacy
-- declaration-era table, currently EMPTY). Service requests need their own
-- escalation tracking directly on the table.
-- =============================================================================

-- Add escalation columns
ALTER TABLE service_requests
    ADD COLUMN IF NOT EXISTS escalated BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS escalated_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS escalated_by UUID REFERENCES users(id),
    ADD COLUMN IF NOT EXISTS escalation_reason TEXT;

-- Partial index for fast escalation queries (filtered by entity)
CREATE INDEX IF NOT EXISTS idx_service_requests_escalated
    ON service_requests (entity_code, escalated_at DESC)
    WHERE escalated = true;

-- Comment for documentation
COMMENT ON COLUMN service_requests.escalated IS 'Whether this request has been escalated to a supervisor';
COMMENT ON COLUMN service_requests.escalated_at IS 'Timestamp of escalation';
COMMENT ON COLUMN service_requests.escalated_by IS 'User ID of the agent who escalated';
COMMENT ON COLUMN service_requests.escalation_reason IS 'Reason provided by the agent for escalation';
