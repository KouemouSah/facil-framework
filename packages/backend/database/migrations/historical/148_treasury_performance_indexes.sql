-- ============================================================================
-- MIGRATION 148: Performance indexes for treasury hot paths at 1M+ scale
-- Date: 2026-03-01
-- Context: With entity_code on service_payments (migration 146) and
--          refactored materialized views (migration 147), add targeted
--          indexes for the remaining treasury hot paths:
--          1. Agent dashboard: pending payments by entity + assigned agent
--          2. SLA monitoring: payments approaching SLA deadline
--          3. Agent workload: payments per agent by status
--          Avoids duplicating existing coverage (idx_sp_entity_status_date,
--          idx_sp_entity_completed, idx_service_payments_pending_validation).
-- ============================================================================

BEGIN;

-- ============================================================================
-- Index 1: Agent pending queue by entity
-- Hot path: agent dashboard filtered by their entity's pending payments
-- Covers: workflow_status IN ('pending_agent_review', 'agent_reviewing', 'requires_documents')
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_sp_entity_pending
    ON service_payments (entity_code, assigned_agent_id, created_at)
    WHERE workflow_status IN ('pending_agent_review', 'agent_reviewing');

-- ============================================================================
-- Index 2: SLA monitoring for supervisor alerts
-- Hot path: supervisor-overview q_sla_alerts() — payments with SLA deadline < 6 hours
-- Covers: requires_agent_validation = true, sla_target_date ordering
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_sp_sla_target
    ON service_payments (sla_target_date ASC)
    WHERE workflow_status IN ('pending_agent_review', 'agent_reviewing')
      AND requires_agent_validation = true
      AND sla_target_date IS NOT NULL;

-- ============================================================================
-- Index 3: Agent performance lookup
-- Hot path: agent stats queries that JOIN payment_validation_audit with service_payments
-- Covers: validated_by_agent_id + workflow_status for performance queries
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_sp_validated_agent_date
    ON service_payments (validated_by_agent_id, validated_at DESC)
    WHERE validated_by_agent_id IS NOT NULL;

-- ============================================================================
-- Verify
-- ============================================================================
DO $$
DECLARE
    v_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_count
    FROM pg_indexes
    WHERE tablename = 'service_payments'
      AND indexname IN ('idx_sp_entity_pending', 'idx_sp_sla_target', 'idx_sp_validated_agent_date');

    IF v_count = 3 THEN
        RAISE NOTICE 'Migration 148: All 3 performance indexes created successfully';
    ELSE
        RAISE EXCEPTION 'Migration 148: Expected 3 indexes, found %', v_count;
    END IF;

    -- Total index count for monitoring
    SELECT COUNT(*) INTO v_count FROM pg_indexes WHERE tablename = 'service_payments';
    RAISE NOTICE 'Migration 148: service_payments now has % total indexes', v_count;
END $$;

COMMIT;
