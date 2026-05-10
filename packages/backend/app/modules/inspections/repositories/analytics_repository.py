"""Analytics Repository — Data access layer for inspection analytics.

Aggregation queries for agent performance, zone coverage, trends,
comparisons, and priority zone scoring.
"""

import asyncio
import logging
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple
from uuid import UUID

logger = logging.getLogger(__name__)


class AnalyticsRepository:
    """Data access for inspection analytics (read-only aggregations)."""

    # ============================================================
    # AGENT PERFORMANCE
    # ============================================================

    @staticmethod
    async def get_agent_performance(
        conn, entity_id: UUID,
        date_from: date, date_to: date,
        page: int = 1, page_size: int = 50,
        city_id: Optional[UUID] = None,
    ) -> Tuple[List[Dict], int]:
        """Aggregate inspection metrics per agent for an entity and date range.

        city_id: if provided, filters inspections by entity_location's city.
        Only supervisors at main office pass city_id=None (global scope).

        Returns paginated list of agent stats + total count.
        """
        # Build city filter
        city_join = ""
        city_cond = ""
        params_base = [entity_id, date_from, date_to]
        if city_id is not None:
            city_join = "JOIN entity_locations el ON el.id = fi.entity_location_id"
            city_cond = f"AND el.city_id = ${len(params_base) + 1}"
            params_base.append(city_id)

        # Count distinct agents first
        count_row = await conn.fetchrow(f"""
            SELECT COUNT(DISTINCT fi.agent_id)
            FROM field_inspections fi
            {city_join}
            WHERE fi.entity_id = $1
              AND fi.inspection_date BETWEEN $2 AND $3
              AND fi.status != 'cancelled'
              {city_cond}
        """, *params_base)
        total = count_row["count"]

        idx = len(params_base) + 1
        params_data = params_base + [page_size, (page - 1) * page_size]

        rows = await conn.fetch(f"""
            WITH agent_stats AS (
                SELECT
                    fi.agent_id,
                    u.full_name AS agent_name,
                    e.code AS entity_code,
                    COUNT(*) AS inspections_total,
                    COUNT(*) FILTER (WHERE fi.result = 'conforme') AS conforme,
                    COUNT(*) FILTER (WHERE fi.result = 'non_conforme') AS non_conforme,
                    COUNT(*) FILTER (WHERE fi.payment_collected) AS collections_count,
                    COALESCE(SUM(fi.payment_amount) FILTER (WHERE fi.payment_collected), 0) AS collected_amount,
                    COUNT(*) FILTER (WHERE fi.mise_en_demeure_issued) AS med_count,
                    COUNT(*) FILTER (WHERE fi.seal_applied) AS seal_count,
                    ROUND(AVG(fi.duration_minutes) FILTER (WHERE fi.duration_minutes IS NOT NULL), 1) AS avg_duration_minutes,
                    COUNT(DISTINCT fi.zone_id) AS zones_covered,
                    COUNT(DISTINCT fi.inspection_date) AS days_active
                FROM field_inspections fi
                JOIN users u ON u.id = fi.agent_id
                JOIN entities e ON e.id = fi.entity_id
                {city_join}
                WHERE fi.entity_id = $1
                  AND fi.inspection_date BETWEEN $2 AND $3
                  AND fi.status != 'cancelled'
                  {city_cond}
                GROUP BY fi.agent_id, u.full_name, e.code
            )
            SELECT
                agent_id, agent_name, entity_code,
                inspections_total, conforme, non_conforme,
                CASE
                    WHEN inspections_total > 0
                    THEN ROUND(100.0 * conforme / inspections_total, 1)
                    ELSE 0
                END AS conformity_rate,
                collections_count, collected_amount,
                med_count, seal_count,
                avg_duration_minutes, zones_covered, days_active
            FROM agent_stats
            ORDER BY inspections_total DESC
            LIMIT ${idx} OFFSET ${idx + 1}
        """, *params_data)

        return [dict(r) for r in rows], total

    # ============================================================
    # AGENT DETAIL
    # ============================================================

    @staticmethod
    async def get_agent_detail(
        conn, agent_id: UUID, entity_id: UUID,
        date_from: date, date_to: date,
    ) -> Dict:
        """Detailed performance for a single agent with sub-breakdowns.

        Returns aggregate stats + recent inspections + zone breakdown + weekly trend.
        Executed sequentially on the same connection (asyncpg does not support
        concurrent queries on a single connection).
        """
        # Main aggregate (same CTE as get_agent_performance but single agent)
        async def _get_aggregate():
            row = await conn.fetchrow("""
                SELECT
                    fi.agent_id,
                    u.full_name AS agent_name,
                    e.code AS entity_code,
                    COUNT(*) AS inspections_total,
                    COUNT(*) FILTER (WHERE fi.result = 'conforme') AS conforme,
                    COUNT(*) FILTER (WHERE fi.result = 'non_conforme') AS non_conforme,
                    COUNT(*) FILTER (WHERE fi.payment_collected) AS collections_count,
                    COALESCE(SUM(fi.payment_amount) FILTER (WHERE fi.payment_collected), 0) AS collected_amount,
                    COUNT(*) FILTER (WHERE fi.mise_en_demeure_issued) AS med_count,
                    COUNT(*) FILTER (WHERE fi.seal_applied) AS seal_count,
                    ROUND(AVG(fi.duration_minutes) FILTER (WHERE fi.duration_minutes IS NOT NULL), 1) AS avg_duration_minutes,
                    COUNT(DISTINCT fi.zone_id) AS zones_covered,
                    COUNT(DISTINCT fi.inspection_date) AS days_active
                FROM field_inspections fi
                JOIN users u ON u.id = fi.agent_id
                JOIN entities e ON e.id = fi.entity_id
                WHERE fi.agent_id = $1
                  AND fi.entity_id = $2
                  AND fi.inspection_date BETWEEN $3 AND $4
                  AND fi.status != 'cancelled'
                GROUP BY fi.agent_id, u.full_name, e.code
            """, agent_id, entity_id, date_from, date_to)
            if not row:
                return None
            result = dict(row)
            total = result["inspections_total"]
            result["conformity_rate"] = (
                round(100.0 * result["conforme"] / total, 1) if total > 0 else 0
            )
            return result

        # Recent inspections (last 20)
        async def _get_recent():
            rows = await conn.fetch("""
                SELECT fi.id, fi.inspection_date,
                       c.legal_name AS company_name,
                       COALESCE(c.nif, c.registration_number) AS company_nif,
                       fi.result, fi.status, fi.payment_amount
                FROM field_inspections fi
                JOIN companies c ON c.id = fi.company_id
                WHERE fi.agent_id = $1
                  AND fi.entity_id = $2
                  AND fi.inspection_date BETWEEN $3 AND $4
                  AND fi.status != 'cancelled'
                ORDER BY fi.inspection_date DESC, fi.created_at DESC
                LIMIT 20
            """, agent_id, entity_id, date_from, date_to)
            return [dict(r) for r in rows]

        # Zone breakdown
        async def _get_zone_breakdown():
            rows = await conn.fetch("""
                SELECT
                    cz.zone_code, cz.name_es AS zone_name,
                    COUNT(*) AS inspections,
                    COUNT(*) FILTER (WHERE fi.result = 'conforme') AS conforme,
                    COALESCE(SUM(fi.payment_amount) FILTER (WHERE fi.payment_collected), 0) AS collected_amount
                FROM field_inspections fi
                LEFT JOIN commerce_zones cz ON cz.id = fi.zone_id
                WHERE fi.agent_id = $1
                  AND fi.entity_id = $2
                  AND fi.inspection_date BETWEEN $3 AND $4
                  AND fi.status != 'cancelled'
                GROUP BY cz.zone_code, cz.name_es
                ORDER BY inspections DESC
            """, agent_id, entity_id, date_from, date_to)
            return [dict(r) for r in rows]

        # Weekly trend
        async def _get_weekly_trend():
            rows = await conn.fetch("""
                SELECT
                    DATE_TRUNC('week', fi.inspection_date)::DATE AS week_start,
                    COUNT(*) AS inspections,
                    COUNT(*) FILTER (WHERE fi.result = 'conforme') AS conforme,
                    COUNT(*) FILTER (WHERE fi.result = 'non_conforme') AS non_conforme,
                    COALESCE(SUM(fi.payment_amount) FILTER (WHERE fi.payment_collected), 0) AS collected_amount
                FROM field_inspections fi
                WHERE fi.agent_id = $1
                  AND fi.entity_id = $2
                  AND fi.inspection_date BETWEEN $3 AND $4
                  AND fi.status != 'cancelled'
                GROUP BY DATE_TRUNC('week', fi.inspection_date)::DATE
                ORDER BY week_start ASC
            """, agent_id, entity_id, date_from, date_to)
            return [dict(r) for r in rows]

        # Sequential execution — asyncpg does not support concurrent queries
        # on a single connection (would raise InterfaceError)
        aggregate = await _get_aggregate()
        recent = await _get_recent()
        zone_breakdown = await _get_zone_breakdown()
        weekly_trend = await _get_weekly_trend()

        if not aggregate:
            return {
                "agent_id": agent_id,
                "agent_name": "",
                "entity_code": "",
                "inspections_total": 0,
                "conforme": 0,
                "non_conforme": 0,
                "conformity_rate": 0,
                "collections_count": 0,
                "collected_amount": 0,
                "med_count": 0,
                "seal_count": 0,
                "avg_duration_minutes": None,
                "zones_covered": 0,
                "days_active": 0,
                "recent_inspections": [],
                "zone_breakdown": [],
                "weekly_trend": [],
            }

        aggregate["recent_inspections"] = recent
        aggregate["zone_breakdown"] = zone_breakdown
        aggregate["weekly_trend"] = weekly_trend
        return aggregate

    # ============================================================
    # ZONE ANALYTICS
    # ============================================================

    @staticmethod
    async def get_zone_analytics(
        conn, entity_id: UUID,
        date_from: date, date_to: date,
        city_id: Optional[UUID] = None,
    ) -> List[Dict]:
        """Zone-level analytics using mv_inspection_zone_analytics (if available).

        Falls back to direct query on field_inspections if the materialized view
        does not exist (e.g. first deploy before REFRESH).
        Adds days_since_last_inspection and coverage_status per zone.
        """
        try:
            rows = await conn.fetch("""
                WITH zone_agg AS (
                    SELECT
                        zone_id, zone_code, zone_name, zone_tier,
                        SUM(inspections)::INT AS inspections,
                        SUM(conforme)::INT AS conforme,
                        SUM(non_conforme)::INT AS non_conforme,
                        SUM(collections)::INT AS collections,
                        SUM(collected_amount) AS collected_amount,
                        SUM(med_count)::INT AS med_count,
                        SUM(seal_count)::INT AS seal_count,
                        SUM(agents_active)::INT AS agents_active,
                        ROUND(AVG(avg_duration_minutes), 1) AS avg_duration_minutes
                    FROM mv_inspection_zone_analytics
                    WHERE entity_id = $1 AND week_start BETWEEN $2 AND $3
                    GROUP BY zone_id, zone_code, zone_name, zone_tier
                ),
                last_inspection AS (
                    SELECT zone_id, MAX(inspection_date) AS last_date
                    FROM field_inspections
                    WHERE entity_id = $1 AND status != 'cancelled'
                    GROUP BY zone_id
                )
                SELECT
                    za.*,
                    CASE
                        WHEN za.inspections > 0
                        THEN ROUND(100.0 * za.conforme / za.inspections, 1)
                        ELSE 0
                    END AS conformity_rate,
                    COALESCE(CURRENT_DATE - li.last_date, 9999) AS days_since_last_inspection,
                    CASE
                        WHEN COALESCE(CURRENT_DATE - li.last_date, 9999) > 30 THEN 'critical'
                        WHEN COALESCE(CURRENT_DATE - li.last_date, 9999) > 14 THEN 'warning'
                        ELSE 'ok'
                    END AS coverage_status
                FROM zone_agg za
                LEFT JOIN last_inspection li ON li.zone_id = za.zone_id
                ORDER BY za.inspections DESC
            """, entity_id, date_from, date_to)
            return [dict(r) for r in rows]
        except Exception as e:
            # Fallback: materialized view may not exist yet
            logger.warning(
                f"mv_inspection_zone_analytics query failed, using fallback: {e}"
            )
            return await AnalyticsRepository._zone_analytics_fallback(
                conn, entity_id, date_from, date_to
            )

    @staticmethod
    async def _zone_analytics_fallback(
        conn, entity_id: UUID,
        date_from: date, date_to: date,
    ) -> List[Dict]:
        """Direct query fallback when materialized view is unavailable."""
        rows = await conn.fetch("""
            WITH zone_agg AS (
                SELECT
                    fi.zone_id,
                    cz.zone_code,
                    cz.name_es AS zone_name,
                    cz.zone_tier,
                    COUNT(*)::INT AS inspections,
                    COUNT(*) FILTER (WHERE fi.result = 'conforme')::INT AS conforme,
                    COUNT(*) FILTER (WHERE fi.result = 'non_conforme')::INT AS non_conforme,
                    COUNT(*) FILTER (WHERE fi.payment_collected)::INT AS collections,
                    COALESCE(SUM(fi.payment_amount) FILTER (WHERE fi.payment_collected), 0) AS collected_amount,
                    COUNT(*) FILTER (WHERE fi.mise_en_demeure_issued)::INT AS med_count,
                    COUNT(*) FILTER (WHERE fi.seal_applied)::INT AS seal_count,
                    COUNT(DISTINCT fi.agent_id)::INT AS agents_active,
                    ROUND(AVG(fi.duration_minutes) FILTER (WHERE fi.duration_minutes IS NOT NULL), 1) AS avg_duration_minutes
                FROM field_inspections fi
                LEFT JOIN commerce_zones cz ON cz.id = fi.zone_id
                WHERE fi.entity_id = $1
                  AND fi.inspection_date BETWEEN $2 AND $3
                  AND fi.status != 'cancelled'
                GROUP BY fi.zone_id, cz.zone_code, cz.name_es, cz.zone_tier
            ),
            last_inspection AS (
                SELECT zone_id, MAX(inspection_date) AS last_date
                FROM field_inspections
                WHERE entity_id = $1 AND status != 'cancelled'
                GROUP BY zone_id
            )
            SELECT
                za.*,
                CASE
                    WHEN za.inspections > 0
                    THEN ROUND(100.0 * za.conforme / za.inspections, 1)
                    ELSE 0
                END AS conformity_rate,
                COALESCE(CURRENT_DATE - li.last_date, 9999) AS days_since_last_inspection,
                CASE
                    WHEN COALESCE(CURRENT_DATE - li.last_date, 9999) > 30 THEN 'critical'
                    WHEN COALESCE(CURRENT_DATE - li.last_date, 9999) > 14 THEN 'warning'
                    ELSE 'ok'
                END AS coverage_status
            FROM zone_agg za
            LEFT JOIN last_inspection li ON li.zone_id = za.zone_id
            ORDER BY za.inspections DESC
        """, entity_id, date_from, date_to)
        return [dict(r) for r in rows]

    # ============================================================
    # TRENDS
    # ============================================================

    @staticmethod
    async def get_trends(
        conn, entity_id: UUID,
        date_from: date, date_to: date,
        granularity: str = "weekly",
        city_id: Optional[UUID] = None,
    ) -> List[Dict]:
        """Time series of inspection metrics with gap-filling via generate_series.

        Granularity: 'daily', 'weekly', or 'monthly'.
        """
        trunc_map = {
            "daily": "day",
            "weekly": "week",
            "monthly": "month",
        }
        trunc = trunc_map.get(granularity, "week")

        interval_map = {
            "daily": "1 day",
            "weekly": "1 week",
            "monthly": "1 month",
        }
        interval = interval_map.get(granularity, "1 week")

        rows = await conn.fetch(f"""
            WITH series AS (
                SELECT generate_series(
                    DATE_TRUNC('{trunc}', $2::DATE)::DATE,
                    DATE_TRUNC('{trunc}', $3::DATE)::DATE,
                    '{interval}'::INTERVAL
                )::DATE AS period_start
            ),
            agg AS (
                SELECT
                    DATE_TRUNC('{trunc}', fi.inspection_date)::DATE AS period_start,
                    COUNT(*)::INT AS inspections,
                    COUNT(*) FILTER (WHERE fi.result = 'conforme')::INT AS conforme,
                    COUNT(*) FILTER (WHERE fi.result = 'non_conforme')::INT AS non_conforme,
                    COUNT(*) FILTER (WHERE fi.payment_collected)::INT AS collections,
                    COALESCE(SUM(fi.payment_amount) FILTER (WHERE fi.payment_collected), 0) AS collected_amount,
                    COUNT(*) FILTER (WHERE fi.mise_en_demeure_issued)::INT AS med_count,
                    COUNT(*) FILTER (WHERE fi.seal_applied)::INT AS seal_count
                FROM field_inspections fi
                {"JOIN entity_locations el ON el.id = fi.entity_location_id" if city_id else ""}
                WHERE fi.entity_id = $1
                  AND fi.inspection_date BETWEEN $2 AND $3
                  AND fi.status != 'cancelled'
                  {"AND el.city_id = $4" if city_id else ""}
                GROUP BY DATE_TRUNC('{trunc}', fi.inspection_date)::DATE
            )
            SELECT
                TO_CHAR(s.period_start, 'YYYY-MM-DD') AS period,
                s.period_start,
                COALESCE(a.inspections, 0) AS inspections,
                COALESCE(a.conforme, 0) AS conforme,
                COALESCE(a.non_conforme, 0) AS non_conforme,
                CASE
                    WHEN COALESCE(a.inspections, 0) > 0
                    THEN ROUND(100.0 * COALESCE(a.conforme, 0) / a.inspections, 1)
                    ELSE 0
                END AS conformity_rate,
                COALESCE(a.collections, 0) AS collections,
                COALESCE(a.collected_amount, 0) AS collected_amount,
                COALESCE(a.med_count, 0) AS med_count,
                COALESCE(a.seal_count, 0) AS seal_count
            FROM series s
            LEFT JOIN agg a ON a.period_start = s.period_start
            ORDER BY s.period_start ASC
        """, entity_id, date_from, date_to, *([city_id] if city_id else []))

        return [dict(r) for r in rows]

    # ============================================================
    # COMPARISON
    # ============================================================

    @staticmethod
    async def get_comparison(
        conn, entity_id: UUID,
        compare_type: str, ids: List[str],
        date_from: date, date_to: date,
    ) -> List[Dict]:
        """Side-by-side comparison of agents, zones, or time periods.

        compare_type:
        - 'agents': Compare two agent_ids
        - 'zones': Compare two zone_ids
        - 'periods': Same entity, two date ranges (ids = [date1, date2] as ISO strings)
        """
        if compare_type == "agents":
            agent_ids = [UUID(i) for i in ids]
            rows = await conn.fetch("""
                SELECT
                    fi.agent_id::TEXT AS item_id,
                    u.full_name AS label,
                    COUNT(*)::INT AS inspections,
                    COUNT(*) FILTER (WHERE fi.result = 'conforme')::INT AS conforme,
                    COUNT(*) FILTER (WHERE fi.result = 'non_conforme')::INT AS non_conforme,
                    CASE
                        WHEN COUNT(*) > 0
                        THEN ROUND(100.0 * COUNT(*) FILTER (WHERE fi.result = 'conforme') / COUNT(*), 1)
                        ELSE 0
                    END AS conformity_rate,
                    COUNT(*) FILTER (WHERE fi.payment_collected)::INT AS collections,
                    COALESCE(SUM(fi.payment_amount) FILTER (WHERE fi.payment_collected), 0) AS collected_amount,
                    COUNT(*) FILTER (WHERE fi.mise_en_demeure_issued)::INT AS med_count,
                    COUNT(*) FILTER (WHERE fi.seal_applied)::INT AS seal_count
                FROM field_inspections fi
                JOIN users u ON u.id = fi.agent_id
                WHERE fi.entity_id = $1
                  AND fi.agent_id = ANY($2::UUID[])
                  AND fi.inspection_date BETWEEN $3 AND $4
                  AND fi.status != 'cancelled'
                GROUP BY fi.agent_id, u.full_name
                ORDER BY inspections DESC
            """, entity_id, agent_ids, date_from, date_to)
            return [dict(r) for r in rows]

        elif compare_type == "zones":
            zone_ids = [UUID(i) for i in ids]
            rows = await conn.fetch("""
                SELECT
                    fi.zone_id::TEXT AS item_id,
                    COALESCE(cz.name_es, 'Sin zona') AS label,
                    COUNT(*)::INT AS inspections,
                    COUNT(*) FILTER (WHERE fi.result = 'conforme')::INT AS conforme,
                    COUNT(*) FILTER (WHERE fi.result = 'non_conforme')::INT AS non_conforme,
                    CASE
                        WHEN COUNT(*) > 0
                        THEN ROUND(100.0 * COUNT(*) FILTER (WHERE fi.result = 'conforme') / COUNT(*), 1)
                        ELSE 0
                    END AS conformity_rate,
                    COUNT(*) FILTER (WHERE fi.payment_collected)::INT AS collections,
                    COALESCE(SUM(fi.payment_amount) FILTER (WHERE fi.payment_collected), 0) AS collected_amount,
                    COUNT(*) FILTER (WHERE fi.mise_en_demeure_issued)::INT AS med_count,
                    COUNT(*) FILTER (WHERE fi.seal_applied)::INT AS seal_count
                FROM field_inspections fi
                LEFT JOIN commerce_zones cz ON cz.id = fi.zone_id
                WHERE fi.entity_id = $1
                  AND fi.zone_id = ANY($2::UUID[])
                  AND fi.inspection_date BETWEEN $3 AND $4
                  AND fi.status != 'cancelled'
                GROUP BY fi.zone_id, cz.name_es
                ORDER BY inspections DESC
            """, entity_id, zone_ids, date_from, date_to)
            return [dict(r) for r in rows]

        elif compare_type == "periods":
            # ids = [period1_end_date_iso, period2_end_date_iso]
            # Each period has the same duration as date_from..date_to
            period_duration = (date_to - date_from).days
            period1_end = date.fromisoformat(ids[0])
            period1_start = period1_end - timedelta(days=period_duration)
            period2_end = date.fromisoformat(ids[1])
            period2_start = period2_end - timedelta(days=period_duration)

            rows = await conn.fetch("""
                WITH period_data AS (
                    SELECT
                        CASE
                            WHEN fi.inspection_date BETWEEN $2 AND $3 THEN 'period_1'
                            WHEN fi.inspection_date BETWEEN $4 AND $5 THEN 'period_2'
                        END AS period_label,
                        fi.result, fi.payment_collected, fi.payment_amount,
                        fi.mise_en_demeure_issued, fi.seal_applied
                    FROM field_inspections fi
                    WHERE fi.entity_id = $1
                      AND fi.status != 'cancelled'
                      AND (
                          fi.inspection_date BETWEEN $2 AND $3
                          OR fi.inspection_date BETWEEN $4 AND $5
                      )
                )
                SELECT
                    period_label AS label,
                    COUNT(*)::INT AS inspections,
                    COUNT(*) FILTER (WHERE result = 'conforme')::INT AS conforme,
                    COUNT(*) FILTER (WHERE result = 'non_conforme')::INT AS non_conforme,
                    CASE
                        WHEN COUNT(*) > 0
                        THEN ROUND(100.0 * COUNT(*) FILTER (WHERE result = 'conforme') / COUNT(*), 1)
                        ELSE 0
                    END AS conformity_rate,
                    COUNT(*) FILTER (WHERE payment_collected)::INT AS collections,
                    COALESCE(SUM(payment_amount) FILTER (WHERE payment_collected), 0) AS collected_amount,
                    COUNT(*) FILTER (WHERE mise_en_demeure_issued)::INT AS med_count,
                    COUNT(*) FILTER (WHERE seal_applied)::INT AS seal_count
                FROM period_data
                WHERE period_label IS NOT NULL
                GROUP BY period_label
                ORDER BY period_label ASC
            """, entity_id, period1_start, period1_end, period2_start, period2_end)

            items = []
            for r in rows:
                d = dict(r)
                # Replace generic label with readable date range
                if d["label"] == "period_1":
                    d["label"] = f"{period1_start} - {period1_end}"
                elif d["label"] == "period_2":
                    d["label"] = f"{period2_start} - {period2_end}"
                items.append(d)
            return items

        else:
            raise ValueError(f"Invalid compare_type: {compare_type}")

    # ============================================================
    # PRIORITY ZONES
    # ============================================================

    @staticmethod
    async def get_priority_zones(
        conn, entity_id: UUID, limit: int = 20,
    ) -> List[Dict]:
        """Score and rank zones by inspection priority.

        Priority score = (pending_amount / 10000) * (days_since_last / 30) + penalty_weight.
        Higher score = more urgent to inspect.
        """
        rows = await conn.fetch("""
            WITH all_zones AS (
                SELECT id AS zone_id, zone_code, name_es AS zone_name, zone_tier
                FROM commerce_zones
            ),
            last_inspected AS (
                SELECT fi.zone_id, MAX(fi.inspection_date) AS last_date
                FROM field_inspections fi
                WHERE fi.entity_id = $1
                  AND fi.status != 'cancelled'
                GROUP BY fi.zone_id
            ),
            zone_obligations AS (
                SELECT
                    cl.zone_id,
                    COUNT(*) FILTER (WHERE lo.status IN ('pending', 'overdue'))::INT AS pending_count,
                    COALESCE(SUM(lo.amount + lo.penalty_amount) FILTER (
                        WHERE lo.status IN ('pending', 'overdue')
                    ), 0) AS pending_amount,
                    COALESCE(SUM(lo.penalty_amount) FILTER (
                        WHERE lo.status IN ('pending', 'overdue')
                    ), 0) AS penalty_total
                FROM license_obligations lo
                JOIN commercial_licenses cl ON cl.id = lo.license_id
                WHERE cl.zone_id IS NOT NULL
                GROUP BY cl.zone_id
            )
            SELECT
                az.zone_id, az.zone_code, az.zone_name, az.zone_tier,
                COALESCE(CURRENT_DATE - li.last_date, 9999) AS days_since_last_inspection,
                COALESCE(zo.pending_count, 0) AS pending_obligations,
                COALESCE(zo.pending_amount, 0) AS pending_amount,
                ROUND(
                    (COALESCE(zo.pending_amount, 0) / 10000.0)
                    * (COALESCE(CURRENT_DATE - li.last_date, 9999) / 30.0)
                    + (COALESCE(zo.penalty_total, 0) / 10000.0),
                    2
                ) AS priority_score,
                GREATEST(CEIL(COALESCE(zo.pending_count, 0) / 10.0), 1)::INT AS recommended_agents
            FROM all_zones az
            LEFT JOIN last_inspected li ON li.zone_id = az.zone_id
            LEFT JOIN zone_obligations zo ON zo.zone_id = az.zone_id
            ORDER BY priority_score DESC
            LIMIT $2
        """, entity_id, limit)

        return [dict(r) for r in rows]
