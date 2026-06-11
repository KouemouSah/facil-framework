"""Analytics Service — Business logic for inspection analytics.

Enforces supervisor authorization, default date ranges, and IDOR protection.
Delegates all data access to AnalyticsRepository.
"""

import logging
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from app.modules.inspections.repositories.analytics_repository import (
    AnalyticsRepository,
)
from app.modules.inspections.services.inspection_service import (
    InspectionService,
    _log_audit,
)

logger = logging.getLogger(__name__)

# Default analytics window: last 30 days
DEFAULT_LOOKBACK_DAYS = 30


class AnalyticsService:
    """Business logic for inspection analytics (supervisor-only)."""

    # ============================================================
    # HELPERS
    # ============================================================

    @staticmethod
    def _default_dates(
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> Tuple[date, date]:
        """Apply default date range: last 30 days if not specified."""
        dt_to = date_to or date.today()
        dt_from = date_from or (dt_to - timedelta(days=DEFAULT_LOOKBACK_DAYS))
        return dt_from, dt_to

    @staticmethod
    async def _resolve_supervisor_context(conn, user_id: UUID) -> Dict:
        """Resolve and enforce supervisor role.

        Raises ValueError if user is not a supervisor.
        """
        ctx = await InspectionService.resolve_inspector_context(conn, user_id)
        if not ctx["is_supervisor"]:
            raise ValueError("Analytics access requires supervisor role")
        return ctx

    # ============================================================
    # AGENT PERFORMANCE
    # ============================================================

    @staticmethod
    async def get_agent_performance(
        conn, user_id: UUID,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        page: int = 1, page_size: int = 50,
    ) -> Dict:
        """Get paginated agent performance metrics for supervisor's entity.

        Returns: {items, total, period_start, period_end}
        """
        ctx = await AnalyticsService._resolve_supervisor_context(conn, user_id)
        dt_from, dt_to = AnalyticsService._default_dates(date_from, date_to)

        items, total = await AnalyticsRepository.get_agent_performance(
            conn, ctx["entity_id"], dt_from, dt_to, page, page_size,
            city_id=ctx.get("queue_city_id"),
        )

        return {
            "items": items,
            "total": total,
            "period_start": dt_from,
            "period_end": dt_to,
        }

    # ============================================================
    # AGENT DETAIL
    # ============================================================

    @staticmethod
    async def get_agent_detail(
        conn, user_id: UUID, agent_id: UUID,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> Dict:
        """Get detailed performance for a single agent.

        IDOR protection: verifies agent belongs to same entity as supervisor.
        """
        ctx = await AnalyticsService._resolve_supervisor_context(conn, user_id)
        dt_from, dt_to = AnalyticsService._default_dates(date_from, date_to)

        # IDOR: verify agent belongs to same entity
        agent_check = await conn.fetchrow("""
            SELECT ap.entity_id
            FROM agent_profiles ap
            WHERE ap.user_id = $1 AND ap.is_active = true
        """, agent_id)

        if not agent_check:
            raise ValueError(f"Agent {agent_id} not found or inactive")

        if agent_check["entity_id"] != ctx["entity_id"]:
            raise ValueError(
                "Cannot view analytics for agents from another entity"
            )

        result = await AnalyticsRepository.get_agent_detail(
            conn, agent_id, ctx["entity_id"], dt_from, dt_to,
        )

        return result

    # ============================================================
    # ZONE ANALYTICS
    # ============================================================

    @staticmethod
    async def get_zone_analytics(
        conn, user_id: UUID,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> Dict:
        """Get zone-level analytics with coverage summary.

        Returns: {items, total_zones, covered_zones, stale_zones}
        """
        ctx = await AnalyticsService._resolve_supervisor_context(conn, user_id)
        dt_from, dt_to = AnalyticsService._default_dates(date_from, date_to)

        items = await AnalyticsRepository.get_zone_analytics(
            conn, ctx["entity_id"], dt_from, dt_to,
            city_id=ctx.get("queue_city_id"),
        )

        # Compute summary totals
        total_zones = len(items)
        covered_zones = sum(
            1 for z in items if z.get("coverage_status") == "ok"
        )
        stale_zones = sum(
            1 for z in items
            if z.get("coverage_status") in ("warning", "critical")
        )

        return {
            "items": items,
            "total_zones": total_zones,
            "covered_zones": covered_zones,
            "stale_zones": stale_zones,
        }

    # ============================================================
    # TRENDS
    # ============================================================

    @staticmethod
    async def get_trends(
        conn, user_id: UUID,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        granularity: str = "weekly",
    ) -> Dict:
        """Get time series trend data for supervisor's entity.

        Returns: {data, granularity, date_from, date_to}
        """
        ctx = await AnalyticsService._resolve_supervisor_context(conn, user_id)
        dt_from, dt_to = AnalyticsService._default_dates(date_from, date_to)

        valid_granularities = ("daily", "weekly", "monthly")
        if granularity not in valid_granularities:
            raise ValueError(
                f"Invalid granularity '{granularity}'. "
                f"Must be one of: {', '.join(valid_granularities)}"
            )

        data = await AnalyticsRepository.get_trends(
            conn, ctx["entity_id"], dt_from, dt_to, granularity,
            city_id=ctx.get("queue_city_id"),
        )

        return {
            "data": data,
            "granularity": granularity,
            "date_from": dt_from,
            "date_to": dt_to,
        }

    # ============================================================
    # COMPARISON
    # ============================================================

    @staticmethod
    async def get_comparison(
        conn, user_id: UUID,
        compare_type: str, ids: List[str],
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> Dict:
        """Compare two agents, zones, or time periods side by side.

        Returns: {compare_type, items, date_from, date_to}
        """
        ctx = await AnalyticsService._resolve_supervisor_context(conn, user_id)
        dt_from, dt_to = AnalyticsService._default_dates(date_from, date_to)

        valid_types = ("agents", "zones", "periods")
        if compare_type not in valid_types:
            raise ValueError(
                f"Invalid compare_type '{compare_type}'. "
                f"Must be one of: {', '.join(valid_types)}"
            )

        if len(ids) != 2:
            raise ValueError("Exactly 2 IDs are required for comparison")

        # A01/IDOR: For agent comparison, verify both agents belong to this entity
        if compare_type == "agents":
            for agent_id_str in ids:
                try:
                    aid = UUID(agent_id_str)
                except ValueError:
                    raise ValueError(f"Invalid agent UUID: {agent_id_str}")
                agent_check = await conn.fetchrow(
                    "SELECT entity_id FROM agent_profiles WHERE user_id = $1 AND is_active = true",
                    aid,
                )
                if not agent_check or agent_check["entity_id"] != ctx["entity_id"]:
                    raise ValueError("Agent not found or belongs to another entity")

        items = await AnalyticsRepository.get_comparison(
            conn, ctx["entity_id"], compare_type, ids, dt_from, dt_to,
        )

        return {
            "compare_type": compare_type,
            "items": items,
            "date_from": dt_from,
            "date_to": dt_to,
        }

    # ============================================================
    # PRIORITY ZONES
    # ============================================================

    @staticmethod
    async def get_priority_zones(
        conn, user_id: UUID, limit: int = 20,
    ) -> Dict:
        """Get zones ranked by inspection priority score.

        Returns: {items, total}
        """
        ctx = await AnalyticsService._resolve_supervisor_context(conn, user_id)

        # Clamp limit to reasonable range
        limit = max(1, min(limit, 100))

        items = await AnalyticsRepository.get_priority_zones(
            conn, ctx["entity_id"], limit,
        )

        return {
            "items": items,
            "total": len(items),
        }
