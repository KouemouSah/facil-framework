-- Migration 305: Add 'waiting_documents' + 'escalated' to agent_work_queue status
--
-- waiting_documents: When an agent requests additional documents via make_decision,
-- the queue entry transitions to 'waiting_documents' (not 'cancelled') so the SAME
-- agent gets the dossier back when the citizen re-submits. Preserves agent continuity
-- and SLA timeline.
--
-- escalated: agent_routes.py line 1867 sets status='escalated' directly to remove the
-- item from the agent's active queue after escalation. Previously a latent bug — this
-- status was never in the CHECK constraint and would have crashed on first real escalation.
-- Note: agent_queue_service.escalate_item() uses status='pending' + escalated=true
-- (different pattern: re-assignable). Both patterns are valid.

DO $$
BEGIN
    ALTER TABLE agent_work_queue
        DROP CONSTRAINT IF EXISTS agent_work_queue_status_check;

    ALTER TABLE agent_work_queue
        ADD CONSTRAINT agent_work_queue_status_check
        CHECK (status IN (
            'pending',
            'assigned',
            'in_progress',
            'completed',
            'cancelled',
            'waiting_documents',
            'escalated'
        ));

    RAISE NOTICE 'Migration 305: agent_work_queue status constraint updated (+ waiting_documents, escalated)';
END $$;
