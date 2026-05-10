-- Migration 133: Recreate v_agent_work_queue_priority with entity_code routing
--
-- Fixes:
-- 1. Old view JOINs only on ministry_id (nullable since migration 132)
-- 2. Missing entity_code column (added by migration 131)
-- 3. Missing item_type column (needed for service_request vs declaration)
-- 4. entity_code is now the primary routing column
--
-- Date: 2026-02-25

DROP VIEW IF EXISTS v_agent_work_queue_priority;

CREATE VIEW v_agent_work_queue_priority AS
SELECT
    awq.id AS queue_id,
    awq.item_type,
    awq.item_id,
    awq.entity_code,
    e.name AS entity_name,
    awq.ministry_id,
    m.name_es AS ministry_name,
    awq.declaration_type,
    awq.amount AS calculated_tax,
    awq.priority_score AS priority,
    awq.sla_deadline,
    awq.sla_status,
    awq.status AS queue_status,
    awq.assigned_to AS assigned_user_id,
    ap.id AS agent_profile_id,
    u.full_name AS agent_name,
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
LEFT JOIN entities e ON awq.entity_code = e.code
LEFT JOIN ministries m ON awq.ministry_id = m.id
LEFT JOIN users u ON awq.assigned_to = u.id
LEFT JOIN agent_profiles ap ON ap.user_id = u.id AND ap.is_active = true
WHERE awq.status IN ('pending', 'in_progress', 'assigned')
ORDER BY awq.priority_score DESC, awq.created_at ASC;

COMMENT ON VIEW v_agent_work_queue_priority IS
    'Prioritized work queue view. Routes by entity_code (primary, migration 131). '
    'ministry_id kept for legacy declaration compat. '
    'Includes both service_requests and declarations.';
