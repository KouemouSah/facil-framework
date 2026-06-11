"""Mission Auto-Assigner — Intelligent agent assignment for field missions.

Scoring algorithm:
1. Zone expertise: +2 pts per past inspection in mission zones
2. Recent workload: -1 pt per inspection in last 7 days (load-balance)
3. Performance: +1 pt per 10% conformity rate above 70%
4. Availability: binary filter (must be available on mission date)

Returns a ranked proposal that the supervisor can accept/modify.
"""

import logging
from datetime import date, timedelta
from typing import Dict, List, Optional
from uuid import UUID

logger = logging.getLogger(__name__)


class MissionAutoAssigner:
    """Proposes agent assignments for a mission based on scoring."""

    @staticmethod
    async def propose_assignments(
        conn,
        mission_id: UUID,
        entity_id: UUID,
        entity_location_id: UUID,
        zone_ids: Optional[List[UUID]],
        target_total: int = 50,
    ) -> List[Dict]:
        """Propose optimal agent assignments for a mission.

        Args:
            conn: Database connection
            mission_id: Mission to assign agents to
            entity_id: Entity scope
            entity_location_id: Location scope (prevents cross-site)
            zone_ids: Target zones for the mission
            target_total: Total inspections target across all agents

        Returns:
            List of proposed assignments with scores, sorted by score DESC.
        """
        # Get default target per agent from system rules
        default_target = await conn.fetchval("""
            SELECT rule_value::int FROM system_rules
            WHERE rule_code = 'FIELD_MISSION_DEFAULT_TARGET' AND is_active = true
        """) or 10

        mission_date = await conn.fetchval(
            "SELECT mission_date FROM field_missions WHERE id = $1", mission_id,
        )
        if not mission_date:
            return []

        # Fetch available agents (same location, not assigned elsewhere that day)
        agents = await conn.fetch("""
            SELECT
                ap.user_id AS agent_id,
                ap.id AS agent_profile_id,
                u.first_name || ' ' || u.last_name AS agent_name,
                ap.working_days
            FROM agent_profiles ap
            JOIN users u ON u.id = ap.user_id
            WHERE ap.entity_id = $1
              AND ap.entity_location_id = $2
              AND ap.is_active = true
              AND ap.is_supervisor = false
              AND u.status = 'active'
              AND NOT EXISTS (
                  SELECT 1 FROM field_mission_agents fma
                  JOIN field_missions fm ON fm.id = fma.mission_id
                  WHERE fma.agent_id = ap.user_id
                    AND fm.mission_date = $3
                    AND fm.status IN ('planned', 'in_progress')
              )
        """, entity_id, entity_location_id, mission_date)

        if not agents:
            return []

        agent_ids = [a["agent_id"] for a in agents]

        # Score 1: Zone expertise — inspections in target zones last 90 days
        zone_scores: Dict[UUID, int] = {}
        if zone_ids:
            zone_rows = await conn.fetch("""
                SELECT fi.agent_id, COUNT(*)::int AS zone_inspections
                FROM field_inspections fi
                WHERE fi.agent_id = ANY($1::uuid[])
                  AND fi.zone_id = ANY($2::uuid[])
                  AND fi.inspection_date >= CURRENT_DATE - 90
                  AND fi.status != 'cancelled'
                GROUP BY fi.agent_id
            """, agent_ids, zone_ids)
            zone_scores = {r["agent_id"]: r["zone_inspections"] for r in zone_rows}

        # Score 2: Recent workload — inspections in last 7 days (penalise heavy load)
        workload_rows = await conn.fetch("""
            SELECT agent_id, COUNT(*)::int AS recent_count
            FROM field_inspections
            WHERE agent_id = ANY($1::uuid[])
              AND inspection_date >= CURRENT_DATE - 7
              AND status != 'cancelled'
            GROUP BY agent_id
        """, agent_ids)
        workload_scores = {r["agent_id"]: r["recent_count"] for r in workload_rows}

        # Score 3: Performance — conformity rate last 30 days
        perf_rows = await conn.fetch("""
            SELECT agent_id,
                   COUNT(*) AS total,
                   COUNT(*) FILTER (WHERE result = 'conforme') AS conforme
            FROM field_inspections
            WHERE agent_id = ANY($1::uuid[])
              AND inspection_date >= CURRENT_DATE - 30
              AND result IS NOT NULL
              AND status != 'cancelled'
            GROUP BY agent_id
        """, agent_ids)
        perf_scores: Dict[UUID, float] = {}
        for r in perf_rows:
            if r["total"] > 0:
                perf_scores[r["agent_id"]] = r["conforme"] / r["total"] * 100

        # Calculate composite score per agent
        scored_agents = []
        for agent in agents:
            aid = agent["agent_id"]
            zone_pts = (zone_scores.get(aid, 0) * 2)  # +2 per zone inspection
            workload_pts = -(workload_scores.get(aid, 0))  # -1 per recent inspection
            conformity = perf_scores.get(aid, 70.0)
            perf_pts = max(0, (conformity - 70) / 10)  # +1 per 10% above 70%

            total_score = round(zone_pts + workload_pts + perf_pts, 1)

            scored_agents.append({
                "agent_id": str(aid),
                "agent_profile_id": str(agent["agent_profile_id"]),
                "agent_name": agent["agent_name"],
                "score": total_score,
                "zone_expertise": zone_scores.get(aid, 0),
                "recent_workload": workload_scores.get(aid, 0),
                "conformity_rate": round(conformity, 1),
                "target_inspections": default_target,
                "assigned_zones": [str(z) for z in zone_ids] if zone_ids else [],
            })

        # Sort by score DESC
        scored_agents.sort(key=lambda a: a["score"], reverse=True)

        # Select top N agents needed to cover target_total
        agents_needed = max(1, -(-target_total // default_target))  # ceil division
        proposed = scored_agents[:agents_needed]

        # Adjust last agent's target if total doesn't divide evenly
        if proposed:
            assigned_so_far = (len(proposed) - 1) * default_target
            remaining = max(1, target_total - assigned_so_far)
            proposed[-1]["target_inspections"] = min(remaining, default_target)

        return proposed
