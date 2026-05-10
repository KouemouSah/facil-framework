-- Migration 130: Assignment Outbox Table
-- Implements Transactional Outbox pattern for guaranteed delivery
-- of entity agent assignment events after payment completion.
--
-- Replaces fire-and-forget EventBus.publish_nowait(PAYMENT_COMPLETED)
-- with a persistent queue processed by cron every minute.

-- 1. Create the outbox table
CREATE TABLE IF NOT EXISTS assignment_outbox (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- What triggered this outbox entry
    event_type TEXT NOT NULL DEFAULT 'PAYMENT_COMPLETED',

    -- The service_request to assign
    service_request_id UUID NOT NULL REFERENCES service_requests(id),

    -- Denormalized from service_requests for cron processing
    -- (avoids JOIN during FOR UPDATE SKIP LOCKED sweep)
    workflow_code TEXT NOT NULL,
    entity_code TEXT NOT NULL,
    entity_location_id UUID,

    -- Source payment info (audit trail)
    payment_id TEXT,
    payment_method TEXT,

    -- Batch support
    batch_id UUID,

    -- Processing state
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'dead_letter')),

    -- Retry tracking
    retry_count INT NOT NULL DEFAULT 0,
    max_retries INT NOT NULL DEFAULT 5,
    next_retry_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_error TEXT,

    -- Processing metadata
    processed_at TIMESTAMPTZ,
    locked_at TIMESTAMPTZ,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. Indexes

-- Primary cron query: SELECT ... WHERE status='pending' AND next_retry_at <= NOW()
CREATE INDEX idx_assignment_outbox_pending
    ON assignment_outbox (next_retry_at ASC)
    WHERE status = 'pending';

-- Idempotency: one item per service_request (pending/processing/completed)
-- Allows re-insertion only after dead_letter (health check re-enqueue)
CREATE UNIQUE INDEX idx_assignment_outbox_sr_active
    ON assignment_outbox (service_request_id)
    WHERE status IN ('pending', 'processing', 'completed');

-- Monitoring: find dead letters
CREATE INDEX idx_assignment_outbox_dead_letter
    ON assignment_outbox (created_at DESC)
    WHERE status = 'dead_letter';

-- 3. Comment
COMMENT ON TABLE assignment_outbox IS
    'Transactional outbox for guaranteed entity agent assignment after payment completion. '
    'Items are inserted in the same transaction as payment validation and processed by cron.';
