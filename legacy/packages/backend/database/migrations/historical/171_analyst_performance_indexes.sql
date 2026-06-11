-- Migration 171: Performance indexes for Treasury Analyst AI tools (1M+ scale)
-- Only adds what's MISSING (26 existing indexes already cover most queries)
-- Uses CREATE INDEX CONCURRENTLY for zero-downtime

-- 1. payment_validation_audit: agent_user_id for performance + rejection analysis
-- Existing idx_payment_audit_agent_date uses agent_id (deprecated INT FK),
-- NOT agent_user_id (UUID FK used by new queries).
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pva_agent_user_action
ON payment_validation_audit(agent_user_id, created_at DESC)
WHERE agent_user_id IS NOT NULL;

-- 2. service_payments: pending payments without entity filter for aging + pipeline
-- Existing idx_sp_entity_pending has entity_code as lead column = unusable
-- without entity filter at 1M+ rows. This covers get_payment_aging + get_workflow_pipeline.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sp_pending_created
ON service_payments(created_at, sla_target_date)
WHERE workflow_status IN ('pending_agent_review', 'agent_reviewing')
  AND requires_agent_validation = true;
