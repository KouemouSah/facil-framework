-- Migration 119: Assign orphan treasury payments to existing TESORO agent
-- Problem: 7 cash payments stuck at pending_agent_review with assigned_agent_id = NULL
-- Root cause: Auto-assignment was broken before site-based routing fix (commit f4dc2ebb)
-- Fix: Assign all orphans to the sole active TESORO agent
-- NOTE: Already executed on production 2026-02-22

-- Step 1: Assign orphan payments
UPDATE service_payments sp
SET assigned_agent_id = ap.id,
    updated_at = NOW()
FROM agent_profiles ap
JOIN entities e ON e.id = ap.entity_id
WHERE e.code = 'TESORO'
  AND ap.is_active = true
  AND sp.workflow_status = 'pending_agent_review'
  AND sp.assigned_agent_id IS NULL
  AND sp.payment_method IN ('cash', 'check');

-- Verify
DO $$
DECLARE
    orphan_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO orphan_count
    FROM service_payments
    WHERE workflow_status = 'pending_agent_review'
      AND assigned_agent_id IS NULL
      AND payment_method IN ('cash', 'check');

    IF orphan_count = 0 THEN
        RAISE NOTICE 'All orphan payments assigned successfully';
    ELSE
        RAISE WARNING '% orphan payments still unassigned', orphan_count;
    END IF;
END $$;
