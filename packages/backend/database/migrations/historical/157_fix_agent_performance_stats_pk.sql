-- Migration 157: Fix agent_performance_stats PK and backfill data
--
-- Problem: PK = agent_id (INT, NOT NULL) but ensure_performance_stats() inserts
-- agent_id=0 for ALL agents → second agent fails with duplicate key.
-- Result: table is EMPTY (0 rows), all performance metrics are NULL.
--
-- Solution: Migrate PK from agent_id to agent_profile_id, then backfill from
-- payment_validation_audit + assignments.

-- Step 1: Fix PK
ALTER TABLE agent_performance_stats DROP CONSTRAINT agent_performance_stats_pkey;
ALTER TABLE agent_performance_stats DROP CONSTRAINT agent_performance_stats_agent_profile_id_key;
ALTER TABLE agent_performance_stats ADD PRIMARY KEY (agent_profile_id);
ALTER TABLE agent_performance_stats ALTER COLUMN agent_id DROP NOT NULL;
ALTER TABLE agent_performance_stats ALTER COLUMN agent_id SET DEFAULT 0;

-- Step 2: Backfill from payment_validation_audit for active agents
-- ministry_id resolved via entity chain: agent_profile → entity → entity.ministry_id
-- (ap.ministry_id is legacy and NULL for some agents like CNEDOGE)
INSERT INTO agent_performance_stats (
    agent_id, agent_profile_id, ministry_id,
    current_month_processed, current_month_approved,
    current_month_rejected, current_month_escalated,
    sla_respected_count, sla_missed_count,
    avg_processing_minutes,
    current_active_locks, max_concurrent_locks,
    stats_period_start, updated_at
)
SELECT
    0,
    ap.id,
    COALESCE(e.ministry_id, ap.ministry_id, 0),
    COALESCE(COUNT(*) FILTER (WHERE pva.action IN ('approve','reject')), 0),
    COALESCE(COUNT(*) FILTER (WHERE pva.action = 'approve'), 0),
    COALESCE(COUNT(*) FILTER (WHERE pva.action = 'reject'), 0),
    COALESCE(COUNT(*) FILTER (WHERE pva.action = 'escalate'), 0),
    COALESCE(COUNT(*) FILTER (WHERE pva.action IN ('approve','reject')
        AND EXTRACT(EPOCH FROM (pva.created_at - sp.created_at))/3600 <= 24), 0),
    COALESCE(COUNT(*) FILTER (WHERE pva.action IN ('approve','reject')
        AND EXTRACT(EPOCH FROM (pva.created_at - sp.created_at))/3600 > 24), 0),
    COALESCE(AVG(pva.action_duration_seconds) FILTER (
        WHERE pva.action IN ('approve','reject')) / 60.0, 0),
    0, 0,
    date_trunc('month', CURRENT_DATE)::date,
    NOW()
FROM agent_profiles ap
LEFT JOIN entities e ON e.id = ap.entity_id
LEFT JOIN payment_validation_audit pva ON pva.agent_profile_id = ap.id
    AND pva.created_at >= date_trunc('month', CURRENT_DATE)
LEFT JOIN service_payments sp ON sp.id = pva.payment_id
WHERE ap.is_active = true
GROUP BY ap.id, ap.ministry_id, e.ministry_id
ON CONFLICT (agent_profile_id) DO UPDATE SET
    current_month_processed = EXCLUDED.current_month_processed,
    current_month_approved = EXCLUDED.current_month_approved,
    current_month_rejected = EXCLUDED.current_month_rejected,
    current_month_escalated = EXCLUDED.current_month_escalated,
    sla_respected_count = EXCLUDED.sla_respected_count,
    sla_missed_count = EXCLUDED.sla_missed_count,
    avg_processing_minutes = EXCLUDED.avg_processing_minutes,
    updated_at = NOW();

-- Step 3: Update agent_workloads timestamps from assignments
UPDATE agent_workloads aw
SET
    last_completion_at = sub.last_completed,
    last_assignment_at = sub.last_assigned,
    last_updated_at = NOW()
FROM (
    SELECT
        a.agent_profile_id,
        MAX(a.completed_at) as last_completed,
        MAX(a.assigned_at) as last_assigned
    FROM assignments a
    WHERE a.item_type = 'payment_validation'
    GROUP BY a.agent_profile_id
) sub
WHERE aw.agent_profile_id = sub.agent_profile_id;
