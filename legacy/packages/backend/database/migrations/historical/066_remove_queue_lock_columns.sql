-- Migration 066: Remove deprecated lock columns from agent_work_queue
-- =====================================================================
--
-- Context:
-- With the implementation of auto-assignment (commit 647a7c11), the lock
-- mechanism in agent_work_queue is no longer needed:
-- - Items are automatically assigned to agents on submission
-- - Agents only see their assigned items (no concurrent access)
-- - The lock was for "pull" architecture, we now use "push" architecture
--
-- Changes:
-- 1. Recreate v_agent_work_queue_priority view WITHOUT locked_until
-- 2. Drop locked_until column from agent_work_queue
--
-- Date: 2026-01-23
-- Author: Claude Code

-- =====================================================================
-- STEP 1: Drop and recreate the view WITHOUT locked_until column
-- =====================================================================

DROP VIEW IF EXISTS v_agent_work_queue_priority;

CREATE VIEW v_agent_work_queue_priority AS
SELECT
    awq.id AS queue_id,
    awq.ministry_id,
    m.name_es AS ministry_name,
    awq.item_id AS declaration_id,
    awq.declaration_type,
    awq.amount AS calculated_tax,
    awq.priority_score AS priority,
    awq.sla_deadline,
    awq.sla_status,
    awq.status AS queue_status,
    awq.assigned_to AS assigned_user_id,
    ap.id AS agent_profile_id,
    u.full_name AS agent_name,
    -- locked_until column removed (no longer needed with auto-assignment)
    awq.escalated,
    awq.escalation_reason,
    awq.created_at,
    EXTRACT(EPOCH FROM (NOW() - awq.created_at)) / 3600 AS hours_in_queue,
    CASE
        WHEN awq.sla_deadline IS NOT NULL AND NOW() > awq.sla_deadline THEN true
        ELSE false
    END AS is_overdue,
    CASE
        WHEN awq.sla_deadline IS NOT NULL THEN
            EXTRACT(EPOCH FROM (awq.sla_deadline - NOW())) / 3600
        ELSE NULL
    END AS hours_until_deadline
FROM agent_work_queue awq
LEFT JOIN ministries m ON awq.ministry_id = m.id
LEFT JOIN users u ON awq.assigned_to = u.id
LEFT JOIN agent_profiles ap ON ap.user_id = u.id AND ap.is_active = true
WHERE awq.status IN ('pending', 'in_progress', 'assigned')
ORDER BY awq.priority_score DESC, awq.created_at ASC;

COMMENT ON VIEW v_agent_work_queue_priority IS 'Work queue prioritized by score and SLA (lock mechanism removed with auto-assignment)';

-- =====================================================================
-- STEP 2: Drop the locked_until column
-- =====================================================================

ALTER TABLE agent_work_queue DROP COLUMN IF EXISTS locked_until;

-- =====================================================================
-- STEP 3: Update comments to reflect new architecture
-- =====================================================================

COMMENT ON TABLE agent_work_queue IS
'Queue for agent work items (service_requests, declarations).
With auto-assignment architecture, items are automatically assigned to agents
on submission. This table is used for:
- SLA tracking (sla_deadline)
- Priority scoring (priority_score)
- Escalation management (escalated, escalated_at)
- Performance metrics';

COMMENT ON COLUMN agent_work_queue.assigned_to IS
'Agent user_id assigned to this item (set by auto-assignment on submission)';

COMMENT ON COLUMN agent_work_queue.assigned_at IS
'Timestamp when item was assigned (set by auto-assignment)';

-- =====================================================================
-- STEP 4: Verify migration
-- =====================================================================

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'agent_work_queue'
        AND column_name = 'locked_until'
    ) THEN
        RAISE EXCEPTION 'Migration failed: locked_until column still exists';
    END IF;

    RAISE NOTICE 'Migration 066 completed: locked_until column removed from agent_work_queue';
END $$;
