-- Migration 152: Partial index for completed payments by validated_at
-- Covers supervisor-overview queries: payment_flow, method_distribution, top_services
-- These 3 queries all scan service_payments WHERE workflow_status = 'completed' AND validated_at >= $1

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sp_completed_validated_at
ON service_payments (validated_at)
WHERE workflow_status = 'completed';
