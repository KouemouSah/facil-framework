-- Migration 136: Fix priority trigger bug + add complexity_score
-- Date: 2026-02-26
--
-- CRITICAL BUG: trg_calculate_priority BEFORE INSERT trigger silently
-- overwrites Python-calculated priority_score with 0 for ALL service_request
-- items in agent_work_queue. The trigger function calculate_queue_priority()
-- was designed for declaration-centric legacy flow and always returns 0 for
-- service_requests. Python _calculate_priority() in agent_queue_service.py
-- is the authoritative calculator.
--
-- Also cleans up dead infrastructure (orphaned functions) and adds
-- complexity_score for intelligent predictive escalation routing.

BEGIN;

-- 1. DROP the offending trigger (keeps function for reference/audit)
DROP TRIGGER IF EXISTS trg_calculate_priority ON agent_work_queue;

-- 2. DROP orphaned function: mv_agent_performance was already dropped,
--    calling refresh_agent_performance() would crash with relation-not-found
DROP FUNCTION IF EXISTS refresh_agent_performance();

-- 3. ADD complexity_score column for intelligent escalation routing
--    Computed from: workflow_weight(30%) + doc_count(30%) + amount_tier(40%)
--    Used by predictive escalation in auto_assignment_service._score_and_select()
ALTER TABLE agent_work_queue ADD COLUMN IF NOT EXISTS complexity_score INTEGER NOT NULL DEFAULT 0;
COMMENT ON COLUMN agent_work_queue.complexity_score IS
    'Computed complexity: workflow_weight(30%) + doc_count(30%) + amount_tier(40%). Used by predictive escalation.';

-- 4. Backfill priority_score for existing items (currently all 0 due to trigger bug)
--    Use workflow.priority_weight as base + SLA boost
UPDATE agent_work_queue q SET
    priority_score = COALESCE(w.priority_weight, 50)
        + CASE
            WHEN w.sla_hours IS NOT NULL AND w.sla_hours <= 24 THEN 20
            WHEN w.sla_hours IS NOT NULL AND w.sla_hours <= 48 THEN 10
            ELSE 0
          END
FROM service_requests sr
JOIN workflows w ON w.code = sr.workflow_code
WHERE q.item_id = sr.id
  AND q.status IN ('pending', 'assigned')
  AND q.priority_score = 0;

-- 5. Backfill complexity_score from available signals
--    Formula: workflow_weight(30%) + doc_count(30%) + payment_amount_tier(40%)
--    Note: risk_score not available on service_requests (Gemini stores in uploaded_files.extracted_data)
UPDATE agent_work_queue q SET
    complexity_score = LEAST(100, GREATEST(0, (
        -- Workflow weight component (30%): priority_weight 0-100 → 0-30
        COALESCE(w.priority_weight, 50) * 0.3

        -- Document count component (30%): more docs = more complex
        + LEAST(COALESCE(doc_counts.cnt, 0), 10) * 3

        -- Payment amount tier component (40%): higher amount = more scrutiny
        + CASE
            WHEN COALESCE(sp.total_amount, 0) > 500000 THEN 40
            WHEN COALESCE(sp.total_amount, 0) > 100000 THEN 30
            WHEN COALESCE(sp.total_amount, 0) > 50000 THEN 20
            WHEN COALESCE(sp.total_amount, 0) > 10000 THEN 10
            ELSE 5
          END
    )::INTEGER))
FROM service_requests sr
JOIN workflows w ON w.code = sr.workflow_code
LEFT JOIN service_payments sp ON sp.service_request_id = sr.id
    AND sp.status NOT IN ('cancelled', 'failed')
LEFT JOIN LATERAL (
    SELECT COUNT(*) AS cnt
    FROM uploaded_files uf
    WHERE uf.related_to_id = sr.id
      AND uf.related_to_type = 'service_request'
) doc_counts ON true
WHERE q.item_id = sr.id
  AND q.status IN ('pending', 'assigned');

COMMIT;
