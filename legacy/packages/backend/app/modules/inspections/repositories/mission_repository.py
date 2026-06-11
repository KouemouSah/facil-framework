"""Mission Repository — Data access layer for field mission planning."""

import logging
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple
from uuid import UUID

logger = logging.getLogger(__name__)


class MissionRepository:
    """Data access for field_missions and field_mission_agents tables."""

    # ============================================================
    # CREATE
    # ============================================================

    @staticmethod
    async def create(conn, data: Dict) -> Dict:
        """Insert a new field mission."""
        row = await conn.fetchrow("""
            INSERT INTO field_missions (
                entity_id, entity_location_id, supervisor_id,
                mission_date, title, notes, zone_ids, status
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING *
        """,
            data["entity_id"], data["entity_location_id"],
            data["supervisor_id"], data["mission_date"],
            data.get("title"), data.get("notes"),
            data.get("zone_ids"), data.get("status", "planned"),
        )
        return dict(row) if row else None

    # ============================================================
    # READ
    # ============================================================

    @staticmethod
    async def get_by_id(conn, mission_id: UUID) -> Optional[Dict]:
        """Get mission with enriched entity/location/supervisor data."""
        row = await conn.fetchrow("""
            SELECT fm.*,
                   e.code AS entity_code,
                   el.location_name AS location_name,
                   u.full_name AS supervisor_name,
                   (SELECT COUNT(*) FROM field_mission_agents fma
                    WHERE fma.mission_id = fm.id) AS agents_count
            FROM field_missions fm
            JOIN entities e ON e.id = fm.entity_id
            JOIN entity_locations el ON el.id = fm.entity_location_id
            JOIN users u ON u.id = fm.supervisor_id
            WHERE fm.id = $1
        """, mission_id)
        return dict(row) if row else None

    @staticmethod
    async def list_by_entity(
        conn, entity_id: UUID,
        entity_location_id: Optional[UUID] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        status: Optional[str] = None,
        page: int = 1, page_size: int = 20,
    ) -> Tuple[List[Dict], int]:
        """Paginated list of missions for an entity.

        If entity_location_id is set, only return missions for that location
        (non-main-office supervisors).
        """
        conditions = ["fm.entity_id = $1"]
        params: list = [entity_id]
        idx = 2

        if entity_location_id:
            conditions.append(f"fm.entity_location_id = ${idx}")
            params.append(entity_location_id)
            idx += 1

        if date_from:
            conditions.append(f"fm.mission_date >= ${idx}")
            params.append(date_from)
            idx += 1

        if date_to:
            conditions.append(f"fm.mission_date <= ${idx}")
            params.append(date_to)
            idx += 1

        if status:
            conditions.append(f"fm.status = ${idx}")
            params.append(status)
            idx += 1

        where = " AND ".join(conditions)

        count_row = await conn.fetchrow(
            f"SELECT COUNT(*) FROM field_missions fm WHERE {where}", *params
        )
        total = count_row["count"]

        rows = await conn.fetch(f"""
            SELECT fm.id, fm.mission_date, fm.title, fm.status,
                   e.code AS entity_code,
                   el.location_name AS location_name,
                   COALESCE(agg.agents_count, 0) AS agents_count,
                   COALESCE(agg.inspections_done, 0) AS inspections_done,
                   COALESCE(agg.inspections_target, 0) AS inspections_target,
                   fm.created_at
            FROM field_missions fm
            JOIN entities e ON e.id = fm.entity_id
            JOIN entity_locations el ON el.id = fm.entity_location_id
            LEFT JOIN LATERAL (
                SELECT COUNT(*)::int AS agents_count,
                       COALESCE(SUM(actual_inspections), 0)::int AS inspections_done,
                       COALESCE(SUM(target_inspections), 0)::int AS inspections_target
                FROM field_mission_agents WHERE mission_id = fm.id
            ) agg ON true
            WHERE {where}
            ORDER BY fm.mission_date DESC
            LIMIT ${idx} OFFSET ${idx + 1}
        """, *params, page_size, (page - 1) * page_size)

        return [dict(r) for r in rows], total

    # ============================================================
    # UPDATE
    # ============================================================

    UPDATABLE_COLUMNS = frozenset({
        "title", "notes", "zone_ids", "status",
        "started_at", "completed_at",
    })

    @staticmethod
    async def update(conn, mission_id: UUID, data: Dict) -> Dict:
        """Update mission fields (whitelist-protected)."""
        if not data:
            return await MissionRepository.get_by_id(conn, mission_id)

        invalid_keys = set(data.keys()) - MissionRepository.UPDATABLE_COLUMNS
        if invalid_keys:
            raise ValueError(
                f"Invalid update columns: {invalid_keys}. "
                f"Allowed: {MissionRepository.UPDATABLE_COLUMNS}"
            )

        set_clauses = []
        params = []
        idx = 1

        for key, value in data.items():
            set_clauses.append(f"{key} = ${idx}")
            params.append(value)
            idx += 1

        set_clauses.append("updated_at = NOW()")
        params.append(mission_id)

        row = await conn.fetchrow(f"""
            UPDATE field_missions
            SET {', '.join(set_clauses)}
            WHERE id = ${idx}
            RETURNING *
        """, *params)

        if not row:
            return None

        # Re-fetch with JOINs for enriched response
        return await MissionRepository.get_by_id(conn, mission_id)

    # ============================================================
    # DELETE
    # ============================================================

    @staticmethod
    async def delete(conn, mission_id: UUID) -> bool:
        """Delete a mission only if status is 'planned'."""
        result = await conn.execute("""
            DELETE FROM field_missions
            WHERE id = $1 AND status = 'planned'
        """, mission_id)
        # asyncpg returns "DELETE N" where N is affected rows
        return result == "DELETE 1"

    # ============================================================
    # AGENTS
    # ============================================================

    @staticmethod
    async def add_agents(conn, mission_id: UUID, agents: List[Dict]) -> List[Dict]:
        """Batch insert agents into a mission."""
        results = []
        for agent in agents:
            row = await conn.fetchrow("""
                INSERT INTO field_mission_agents (
                    mission_id, agent_id, agent_profile_id,
                    assigned_zones, target_inspections, notes, status
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING *
            """,
                mission_id,
                agent["agent_id"], agent["agent_profile_id"],
                agent.get("assigned_zones"), agent.get("target_inspections", 10),
                agent.get("notes"), "assigned",
            )
            if row:
                results.append(dict(row))

        # Touch mission updated_at
        await conn.execute("""
            UPDATE field_missions SET updated_at = NOW() WHERE id = $1
        """, mission_id)

        return results

    @staticmethod
    async def remove_agent(conn, mission_id: UUID, agent_id: UUID) -> bool:
        """Remove an agent from a mission."""
        result = await conn.execute("""
            DELETE FROM field_mission_agents
            WHERE mission_id = $1 AND agent_id = $2
        """, mission_id, agent_id)
        return result == "DELETE 1"

    @staticmethod
    async def get_mission_agents(conn, mission_id: UUID) -> List[Dict]:
        """Get all agents for a mission with enriched user data."""
        rows = await conn.fetch("""
            SELECT fma.*,
                   u.full_name AS agent_name,
                   ap.working_days,
                   CASE WHEN ap.is_active THEN 'available' ELSE 'unavailable' END AS availability_status,
                   CASE
                       WHEN fma.target_inspections > 0
                       THEN fma.actual_inspections * 100.0 / fma.target_inspections
                       ELSE 0.0
                   END AS progress_pct
            FROM field_mission_agents fma
            JOIN users u ON u.id = fma.agent_id
            JOIN agent_profiles ap ON ap.id = fma.agent_profile_id
            WHERE fma.mission_id = $1
            ORDER BY u.full_name ASC
        """, mission_id)
        return [dict(r) for r in rows]

    # ============================================================
    # PLANNING HELPERS
    # ============================================================

    @staticmethod
    async def suggest_zones(
        conn, entity_id: UUID, limit: int = 10,
        entity_location_id: Optional[UUID] = None,
    ) -> List[Dict]:
        """Suggest zones based on inspection coverage and pending obligations.

        If entity_location_id is provided, only zones with companies in that
        location's city are returned (relevant for AYUNTAMIENTO/CAMARA_COMERCIO).
        """
        loc_filter_fi = ""
        loc_filter_lo = ""
        params: list = [entity_id]

        if entity_location_id:
            # Get city_id for this location
            city_id = await conn.fetchval(
                "SELECT city_id FROM entity_locations WHERE id = $1",
                entity_location_id,
            )
            if city_id:
                params.append(city_id)
                city_param = f"${len(params)}"
                # Filter obligations by city through companies
                loc_filter_lo = f"""
                    AND cl.id IN (
                        SELECT cl2.id FROM commercial_licenses cl2
                        JOIN companies c2 ON c2.id = cl2.company_id
                        WHERE c2.city_id = {city_param}
                    )
                """

        rows = await conn.fetch(f"""
            WITH last_inspected AS (
                SELECT cl.zone_id,
                       MAX(fi.inspection_date) AS last_inspection_date
                FROM field_inspections fi
                JOIN commercial_licenses cl ON cl.id = fi.license_id
                WHERE fi.entity_id = $1 AND fi.status != 'cancelled'
                GROUP BY cl.zone_id
            ),
            zone_obligations AS (
                SELECT cl.zone_id,
                       COUNT(*)::int AS pending_count
                FROM license_obligations lo
                JOIN commercial_licenses cl ON cl.id = lo.license_id
                WHERE lo.status IN ('pending', 'overdue')
                {loc_filter_lo}
                GROUP BY cl.zone_id
            )
            SELECT
                cz.id AS zone_id,
                cz.zone_code,
                cz.name_es AS zone_name,
                cz.zone_tier AS zone_tier,
                CASE
                    WHEN li.last_inspection_date IS NULL THEN NULL
                    ELSE (CURRENT_DATE - li.last_inspection_date)::int
                END AS days_since_last_inspection,
                COALESCE(zo.pending_count, 0) AS pending_obligations_count,
                CASE
                    WHEN li.last_inspection_date IS NULL THEN 'high'
                    WHEN (CURRENT_DATE - li.last_inspection_date) > 30 THEN 'high'
                    WHEN (CURRENT_DATE - li.last_inspection_date) > 14 THEN 'medium'
                    ELSE 'low'
                END AS suggested_priority
            FROM commerce_zones cz
            LEFT JOIN last_inspected li ON li.zone_id = cz.id
            LEFT JOIN zone_obligations zo ON zo.zone_id = cz.id
            ORDER BY
                (COALESCE(zo.pending_count, 0) *
                 COALESCE(CURRENT_DATE - li.last_inspection_date, 9999)
                 / 30.0) DESC
            LIMIT ${len(params) + 1}::int
        """, *params, limit)
        return [dict(r) for r in rows]

    @staticmethod
    async def get_agents_availability(
        conn, entity_id: UUID, mission_date: date,
        entity_location_id: Optional[UUID] = None,
    ) -> List[Dict]:
        """Get agent availability for a specific date.

        If entity_location_id is provided, only return agents assigned to that
        location. This prevents cross-site assignment (e.g., assigning a Bata
        agent to a Malabo mission).
        """
        location_filter = ""
        params: list = [entity_id, mission_date]
        if entity_location_id:
            location_filter = "AND ap.entity_location_id = $3"
            params.append(entity_location_id)

        rows = await conn.fetch(f"""
            SELECT
                ap.user_id AS agent_id,
                ap.id AS agent_profile_id,
                u.full_name AS agent_name,
                ap.entity_location_id,
                el.city AS location_city,
                NOT EXISTS(
                    SELECT 1 FROM field_mission_agents fma
                    JOIN field_missions fm ON fm.id = fma.mission_id
                    WHERE fma.agent_id = ap.user_id
                      AND fm.mission_date = $2
                      AND fm.status != 'cancelled'
                ) AS is_available,
                (
                    SELECT fm2.title
                    FROM field_mission_agents fma2
                    JOIN field_missions fm2 ON fm2.id = fma2.mission_id
                    WHERE fma2.agent_id = ap.user_id
                      AND fm2.mission_date = $2
                      AND fm2.status != 'cancelled'
                    LIMIT 1
                ) AS current_mission,
                ap.working_days,
                CASE WHEN ap.is_active THEN 'available' ELSE 'unavailable' END AS availability_status
            FROM agent_profiles ap
            JOIN users u ON u.id = ap.user_id
            LEFT JOIN entity_locations el ON el.id = ap.entity_location_id
            WHERE ap.entity_id = $1
              AND ap.is_active = true
              AND ap.is_supervisor = false
              {location_filter}
            ORDER BY u.full_name ASC
        """, *params)
        return [dict(r) for r in rows]

    # ============================================================
    # COMPLETE / PROGRESS
    # ============================================================

    @staticmethod
    async def complete_mission(conn, mission_id: UUID) -> Optional[Dict]:
        """Mark mission as completed (only from in_progress)."""
        row = await conn.fetchrow("""
            UPDATE field_missions
            SET status = 'completed', completed_at = NOW(), updated_at = NOW()
            WHERE id = $1 AND status = 'in_progress'
            RETURNING *
        """, mission_id)

        if not row:
            return None

        # Also complete all assigned/active agents
        await conn.execute("""
            UPDATE field_mission_agents
            SET status = 'completed', completed_at = NOW()
            WHERE mission_id = $1 AND status IN ('assigned', 'active')
        """, mission_id)

        # Re-fetch with JOINs
        return await MissionRepository.get_by_id(conn, mission_id)

    @staticmethod
    async def update_agent_actual_inspections(conn, mission_id: UUID):
        """Sync actual_inspections from field_inspections count."""
        await conn.execute("""
            UPDATE field_mission_agents fma
            SET actual_inspections = (
                SELECT COUNT(*)
                FROM field_inspections fi
                WHERE fi.mission_id = fma.mission_id
                  AND fi.agent_id = fma.agent_id
                  AND fi.status != 'cancelled'
            )
            WHERE fma.mission_id = $1
        """, mission_id)

    # ============================================================
    # ANALYTICS
    # ============================================================

    @staticmethod
    async def get_mission_analytics(
        conn, entity_id: UUID,
        date_from: date, date_to: date,
        entity_location_id: Optional[UUID] = None,
    ) -> Dict:
        """Aggregated mission analytics for a period."""
        loc_filter = ""
        params: list = [entity_id, date_from, date_to]
        if entity_location_id:
            loc_filter = "AND fm.entity_location_id = $4"
            params.append(entity_location_id)

        # Summary stats
        summary = await conn.fetchrow(f"""
            SELECT
                COUNT(*) AS total_missions,
                COUNT(*) FILTER (WHERE fm.status = 'completed') AS completed,
                COUNT(*) FILTER (WHERE fm.status = 'cancelled') AS cancelled,
                COUNT(*) FILTER (WHERE fm.status = 'in_progress') AS in_progress,
                COUNT(*) FILTER (WHERE fm.status = 'planned') AS planned,
                ROUND(AVG(EXTRACT(EPOCH FROM (fm.completed_at - fm.started_at)) / 3600)
                    FILTER (WHERE fm.completed_at IS NOT NULL AND fm.started_at IS NOT NULL), 1
                ) AS avg_duration_hours,
                COALESCE(SUM(agg.actual), 0) AS total_inspections_actual,
                COALESCE(SUM(agg.target), 0) AS total_inspections_target,
                COALESCE(SUM(agg.collected), 0) AS total_collected
            FROM field_missions fm
            LEFT JOIN LATERAL (
                SELECT
                    SUM(fma.actual_inspections)::int AS actual,
                    SUM(fma.target_inspections)::int AS target,
                    COALESCE(SUM(fi_agg.collected), 0) AS collected
                FROM field_mission_agents fma
                LEFT JOIN LATERAL (
                    SELECT COALESCE(SUM(payment_amount), 0) AS collected
                    FROM field_inspections
                    WHERE mission_id = fm.id AND payment_collected
                ) fi_agg ON true
                WHERE fma.mission_id = fm.id
            ) agg ON true
            WHERE fm.entity_id = $1
              AND fm.mission_date BETWEEN $2 AND $3
              {loc_filter}
        """, *params)

        total = summary["total_missions"] or 0
        completed = summary["completed"] or 0
        actual = summary["total_inspections_actual"] or 0
        target = summary["total_inspections_target"] or 0

        # Conformity from inspections linked to missions in period
        conformity_row = await conn.fetchrow(f"""
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE fi.result = 'conforme') AS conforme
            FROM field_inspections fi
            JOIN field_missions fm ON fm.id = fi.mission_id
            WHERE fm.entity_id = $1
              AND fm.mission_date BETWEEN $2 AND $3
              AND fi.result IS NOT NULL
              {loc_filter}
        """, *params)
        conf_total = conformity_row["total"] or 0
        conformity_rate = round(conformity_row["conforme"] / conf_total * 100, 1) if conf_total > 0 else 0

        # Weekly trends (last 8 weeks or within range)
        trends = await conn.fetch(f"""
            SELECT
                date_trunc('week', fm.mission_date)::date AS week,
                COUNT(DISTINCT fm.id) AS missions,
                COALESCE(SUM(fma.actual_inspections), 0)::int AS inspections,
                ROUND(
                    COUNT(*) FILTER (WHERE fi.result = 'conforme')::numeric
                    / NULLIF(COUNT(*) FILTER (WHERE fi.result IS NOT NULL), 0) * 100, 1
                ) AS conformity
            FROM field_missions fm
            LEFT JOIN field_mission_agents fma ON fma.mission_id = fm.id
            LEFT JOIN field_inspections fi ON fi.mission_id = fm.id
            WHERE fm.entity_id = $1
              AND fm.mission_date BETWEEN $2 AND $3
              {loc_filter}
            GROUP BY 1
            ORDER BY 1
        """, *params)

        # Top agents by mission performance
        top_agents = await conn.fetch(f"""
            SELECT
                u.first_name || ' ' || u.last_name AS agent_name,
                COUNT(DISTINCT fma.mission_id) AS missions_count,
                SUM(fma.actual_inspections)::int AS inspections,
                ROUND(
                    SUM(fma.actual_inspections)::numeric
                    / NULLIF(SUM(fma.target_inspections), 0) * 100, 1
                ) AS avg_target_pct
            FROM field_mission_agents fma
            JOIN field_missions fm ON fm.id = fma.mission_id
            JOIN users u ON u.id = fma.agent_id
            WHERE fm.entity_id = $1
              AND fm.mission_date BETWEEN $2 AND $3
              AND fma.status != 'absent'
              {loc_filter}
            GROUP BY u.id, u.first_name, u.last_name
            ORDER BY inspections DESC
            LIMIT 10
        """, *params)

        # Stale zones (> 30 days without inspection), location-scoped
        stale_loc_filter = ""
        stale_params: list = [entity_id]
        if entity_location_id:
            stale_loc_filter = "AND fi.entity_location_id = $2"
            stale_params.append(entity_location_id)

        stale_zones = await conn.fetch(f"""
            SELECT
                cz.zone_code, cz.name_es AS zone_name,
                (CURRENT_DATE - MAX(fi.inspection_date))::int AS days_since,
                COUNT(lo.id) FILTER (WHERE lo.status IN ('pending','overdue')) AS pending_count
            FROM commerce_zones cz
            LEFT JOIN field_inspections fi ON fi.zone_id = cz.id
                AND fi.entity_id = $1 AND fi.status != 'cancelled'
                {stale_loc_filter}
            LEFT JOIN commercial_licenses cl ON cl.zone_id = cz.id
            LEFT JOIN license_obligations lo ON lo.license_id = cl.id
            GROUP BY cz.id, cz.zone_code, cz.name_es
            HAVING MAX(fi.inspection_date) IS NULL
                OR (CURRENT_DATE - MAX(fi.inspection_date)) > 30
            ORDER BY days_since DESC NULLS FIRST
            LIMIT 10
        """, *stale_params)

        return {
            "period": {"date_from": str(date_from), "date_to": str(date_to)},
            "summary": {
                "total_missions": total,
                "completed": completed,
                "cancelled": summary["cancelled"] or 0,
                "in_progress": summary["in_progress"] or 0,
                "planned": summary["planned"] or 0,
                "completion_rate": round(completed / total * 100, 1) if total > 0 else 0,
                "avg_duration_hours": float(summary["avg_duration_hours"] or 0),
                "total_inspections_actual": actual,
                "total_inspections_target": target,
                "target_achievement_rate": round(actual / target * 100, 1) if target > 0 else 0,
                "conformity_rate": conformity_rate,
                "total_collected": float(summary["total_collected"] or 0),
            },
            "trends": [dict(r) for r in trends],
            "top_agents": [dict(r) for r in top_agents],
            "stale_zones": [dict(r) for r in stale_zones],
            "status_breakdown": {
                "planned": summary["planned"] or 0,
                "in_progress": summary["in_progress"] or 0,
                "completed": completed,
                "cancelled": summary["cancelled"] or 0,
            },
            "deltas": await MissionRepository._compute_deltas(
                conn, entity_id, date_from, date_to, entity_location_id,
                current_summary={
                    "total": total, "completed": completed,
                    "actual": actual, "target": target,
                    "conformity": conformity_rate,
                    "collected": float(summary["total_collected"] or 0),
                },
            ),
            "agent_zone_matrix": await MissionRepository._get_agent_zone_matrix(
                conn, entity_id, date_from, date_to, entity_location_id,
            ),
            "zone_conformity": await MissionRepository._get_zone_conformity(
                conn, entity_id, date_from, date_to, entity_location_id,
            ),
        }

    @staticmethod
    async def _compute_deltas(
        conn, entity_id: UUID, date_from: date, date_to: date,
        entity_location_id: Optional[UUID], current_summary: Dict,
    ) -> Dict:
        """Compare current period with previous period of same length."""
        period_days = (date_to - date_from).days
        prev_to = date_from - timedelta(days=1)
        prev_from = prev_to - timedelta(days=period_days)

        loc_filter = ""
        params: list = [entity_id, prev_from, prev_to]
        if entity_location_id:
            loc_filter = "AND fm.entity_location_id = $4"
            params.append(entity_location_id)

        prev = await conn.fetchrow(f"""
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE fm.status = 'completed') AS completed,
                COALESCE(SUM(agg.actual), 0) AS actual,
                COALESCE(SUM(agg.target), 0) AS target,
                COALESCE(SUM(agg.collected), 0) AS collected
            FROM field_missions fm
            LEFT JOIN LATERAL (
                SELECT SUM(fma.actual_inspections)::int AS actual,
                       SUM(fma.target_inspections)::int AS target,
                       COALESCE(SUM(fi_agg.collected), 0) AS collected
                FROM field_mission_agents fma
                LEFT JOIN LATERAL (
                    SELECT COALESCE(SUM(payment_amount), 0) AS collected
                    FROM field_inspections WHERE mission_id = fm.id AND payment_collected
                ) fi_agg ON true
                WHERE fma.mission_id = fm.id
            ) agg ON true
            WHERE fm.entity_id = $1
              AND fm.mission_date BETWEEN $2 AND $3
              {loc_filter}
        """, *params)

        def delta(current: float, previous: float) -> float:
            if previous == 0:
                return 100.0 if current > 0 else 0.0
            return round((current - previous) / previous * 100, 1)

        prev_total = prev["total"] or 0
        prev_completed = prev["completed"] or 0
        prev_actual = prev["actual"] or 0

        return {
            "missions": delta(current_summary["total"], prev_total),
            "completion": delta(current_summary["completed"], prev_completed),
            "inspections": delta(current_summary["actual"], prev_actual),
            "collected": delta(current_summary["collected"], float(prev["collected"] or 0)),
        }

    @staticmethod
    async def _get_agent_zone_matrix(
        conn, entity_id: UUID, date_from: date, date_to: date,
        entity_location_id: Optional[UUID],
    ) -> List[Dict]:
        """Agent × Zone inspection count matrix for heatmap."""
        loc_filter = ""
        params: list = [entity_id, date_from, date_to]
        if entity_location_id:
            loc_filter = "AND fi.entity_location_id = $4"
            params.append(entity_location_id)

        rows = await conn.fetch(f"""
            SELECT
                u.first_name || ' ' || u.last_name AS agent_name,
                cz.zone_code,
                COUNT(*)::int AS inspections
            FROM field_inspections fi
            JOIN users u ON u.id = fi.agent_id
            LEFT JOIN commerce_zones cz ON cz.id = fi.zone_id
            WHERE fi.entity_id = $1
              AND fi.inspection_date BETWEEN $2 AND $3
              AND fi.status != 'cancelled'
              AND cz.zone_code IS NOT NULL
              {loc_filter}
            GROUP BY u.first_name, u.last_name, cz.zone_code
            ORDER BY u.first_name, cz.zone_code
        """, *params)
        return [dict(r) for r in rows]

    @staticmethod
    async def _get_zone_conformity(
        conn, entity_id: UUID, date_from: date, date_to: date,
        entity_location_id: Optional[UUID],
    ) -> List[Dict]:
        """Conformity rate per zone — cross-dimensional analysis."""
        loc_filter = ""
        params: list = [entity_id, date_from, date_to]
        if entity_location_id:
            loc_filter = "AND fi.entity_location_id = $4"
            params.append(entity_location_id)

        rows = await conn.fetch(f"""
            SELECT
                cz.zone_code,
                cz.name_es AS zone_name,
                COUNT(*)::int AS total,
                COUNT(*) FILTER (WHERE fi.result = 'conforme')::int AS conforme,
                COUNT(*) FILTER (WHERE fi.result = 'non_conforme')::int AS non_conforme,
                ROUND(
                    COUNT(*) FILTER (WHERE fi.result = 'conforme')::numeric
                    / NULLIF(COUNT(*) FILTER (WHERE fi.result IS NOT NULL), 0) * 100, 1
                ) AS conformity_rate
            FROM field_inspections fi
            JOIN commerce_zones cz ON cz.id = fi.zone_id
            WHERE fi.entity_id = $1
              AND fi.inspection_date BETWEEN $2 AND $3
              AND fi.status != 'cancelled'
              {loc_filter}
            GROUP BY cz.zone_code, cz.name_es
            ORDER BY conformity_rate ASC NULLS LAST
            LIMIT 12
        """, *params)
        return [dict(r) for r in rows]
