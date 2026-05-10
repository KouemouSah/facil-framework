-- Migration 151: Partial indexes for Operations Center dashboard queries
-- These indexes speed up the 4 parallel queries in GET /admin/monitoring/operations/dashboard

-- Index for pipeline query: service_requests excluding DRAFT (most rows are DRAFT)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_service_requests_active_pipeline
ON service_requests (status)
WHERE status != 'DRAFT';

-- Index for stale payment locks query
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_service_payments_stale_locks
ON service_payments (assigned_at)
WHERE assigned_agent_id IS NOT NULL AND workflow_status = 'agent_reviewing';
