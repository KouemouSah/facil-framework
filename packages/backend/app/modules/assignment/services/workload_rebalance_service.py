"""
Workload Rebalance Service
Extracted from supervisor_routes.py for reuse in cron jobs.

Author: Claude Code
Date: 2026-02-22
"""

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

logger = logging.getLogger(__name__)


async def rebalance_entity_workload(
    entity_id: Optional[UUID],
    db,
    performed_by: Optional[UUID] = None,
) -> Dict[str, Any]:
    """
    Rebalance workload for a specific entity (or all if entity_id is None).

    Returns dict with reassignments_made, details, message.
    """
    # Get current workload distribution
    # availability is on agent_workloads, not agent_profiles
    query = """
        SELECT
            ap.id as agent_profile_id,
            ap.user_id,
            u.full_name as agent_name,
            ap.specializations,
            COUNT(a.id) FILTER (WHERE a.status IN ('assigned', 'in_progress', 'pending_review')) as active_count
        FROM agent_profiles ap
        JOIN users u ON ap.user_id = u.id
        LEFT JOIN agent_workloads aw ON aw.agent_profile_id = ap.id
        LEFT JOIN assignments a ON a.agent_profile_id = ap.id
            AND a.status IN ('assigned', 'in_progress', 'pending_review')
        WHERE ap.is_active = true
            AND ap.is_supervisor = false
            AND COALESCE(aw.availability::text, 'available') = 'available'
    """
    params: list = []
    if entity_id:
        query += " AND ap.entity_id = $1"
        params.append(entity_id)

    query += " GROUP BY ap.id, ap.user_id, u.full_name, ap.specializations ORDER BY active_count DESC"
    agents = await db.fetch(query, *params)

    if len(agents) < 2:
        return {"reassignments_made": 0, "details": [], "message": "Not enough agents"}

    from app.config import get_settings
    settings = get_settings()

    avg_load = sum(a['active_count'] for a in agents) / len(agents)
    overloaded = [a for a in agents if a['active_count'] > avg_load + settings.REBALANCE_OVERLOAD_OFFSET]
    underloaded = [a for a in agents if a['active_count'] < avg_load - settings.REBALANCE_UNDERLOAD_OFFSET]

    if not overloaded or not underloaded:
        return {"reassignments_made": 0, "details": [], "message": "Already balanced"}

    max_reassignments = settings.REBALANCE_MAX_REASSIGNMENTS_PER_RUN

    under_loads = {a['agent_profile_id']: a['active_count'] for a in underloaded}
    details: List[Dict[str, str]] = []

    for over_agent in overloaded:
        if len(details) >= max_reassignments:
            break
        excess = int(over_agent['active_count'] - avg_load)
        if excess <= 0:
            continue

        # Mobility scoring: priority-based (sla_deadline is on agent_work_queue, not service_requests)
        # Use submitted_at + workflows.sla_hours as SLA pressure proxy
        movable = await db.fetch("""
            SELECT a.id, a.item_id,
                   sr.workflow_code,
                   CASE
                       WHEN sr.priority::text = 'URGENT' THEN $3
                       WHEN sr.priority::text = 'HIGH' THEN $4
                       WHEN sr.submitted_at IS NOT NULL AND w.sla_hours IS NOT NULL
                            AND sr.submitted_at + (w.sla_hours * interval '1 hour') < NOW() + INTERVAL '4 hours' THEN $5
                       WHEN sr.priority::text = 'NORMAL' THEN $6
                       ELSE $7
                   END as mobility_score
            FROM assignments a
            LEFT JOIN service_requests sr ON a.item_id = sr.id
            LEFT JOIN workflows w ON w.code = sr.workflow_code
            WHERE a.agent_profile_id = $1
                AND a.status = 'assigned'
            ORDER BY mobility_score ASC, a.assigned_at ASC
            LIMIT $2
        """, over_agent['agent_profile_id'], excess,
            settings.REBALANCE_MOBILITY_URGENT,
            settings.REBALANCE_MOBILITY_HIGH,
            settings.REBALANCE_MOBILITY_SLA_PRESSURE,
            settings.REBALANCE_MOBILITY_NORMAL,
            settings.REBALANCE_MOBILITY_DEFAULT)

        for assignment in movable:
            best_target = None
            workflow = assignment.get('workflow_code')

            # Prefer underloaded agents who specialize in this workflow
            for ua in underloaded:
                current_load = under_loads.get(ua['agent_profile_id'], ua['active_count'])
                if current_load >= avg_load:
                    continue
                if workflow and ua.get('specializations'):
                    specs = ua['specializations'] if isinstance(ua['specializations'], list) else []
                    if workflow in specs:
                        best_target = ua
                        break

            # Fallback: any underloaded agent
            if not best_target:
                for ua in underloaded:
                    current_load = under_loads.get(ua['agent_profile_id'], ua['active_count'])
                    if current_load < avg_load:
                        best_target = ua
                        break

            if not best_target:
                break

            if len(details) >= max_reassignments:
                break

            # reassignment_reason_enum: 'workload_imbalance'
            await db.execute("""
                UPDATE assignments
                SET agent_profile_id = $1, status = 'assigned',
                    reassigned_at = NOW(),
                    reassignment_reason = 'workload_imbalance'::reassignment_reason_enum,
                    updated_at = NOW()
                WHERE id = $2
            """, best_target['agent_profile_id'], assignment['id'])

            if assignment['item_id']:
                # assigned_to is UUID, user_id is UUID — no cast needed
                await db.execute("""
                    UPDATE service_requests SET assigned_to = (
                        SELECT user_id FROM agent_profiles WHERE id = $1
                    ) WHERE id = $2
                """, best_target['agent_profile_id'], assignment['item_id'])

                # service_request_history.performed_by is UUID (nullable)
                await db.execute("""
                    INSERT INTO service_request_history
                    (service_request_id, action, performed_by, comment)
                    VALUES ($1, 'rebalanced', $2, $3)
                """, assignment['item_id'], performed_by,
                    f"Auto-rebalance: {over_agent['agent_name']} → {best_target['agent_name']}")

            details.append({
                "from_agent": over_agent['agent_name'],
                "to_agent": best_target['agent_name'],
                "request_id": str(assignment['item_id']),
                "workflow_code": assignment.get('workflow_code') or 'unknown',
            })

            under_loads[best_target['agent_profile_id']] = under_loads.get(
                best_target['agent_profile_id'], best_target['active_count']
            ) + 1

    logger.info(f"Entity {entity_id}: {len(details)} assignments rebalanced")
    return {
        "reassignments_made": len(details),
        "details": details,
        "message": f"{len(details)} assignments rebalanced",
    }
