"""Workload Repository - Data access for agent workload and performance stats"""

from typing import Optional, List, Dict, Any
from loguru import logger
import asyncpg
from datetime import date

from app.modules.agents.models import AgentWorkloadUpdate


class WorkloadRepository:
    """Repository for agent workloads and performance stats"""

    # ========================================================================
    # AGENT_WORKLOADS
    # ========================================================================

    async def get_workload(
        self,
        conn: asyncpg.Connection,
        agent_id: str,
    ) -> Optional[Dict[str, Any]]:
        """DEPRECATED: agent_workloads.agent_id is 100% NULL. Use get_workload_by_profile_id()."""
        query = """
            SELECT * FROM agent_workloads WHERE agent_id = $1
        """
        result = await conn.fetchrow(query, agent_id)
        return dict(result) if result else None

    async def get_workload_by_profile_id(
        self,
        conn: asyncpg.Connection,
        agent_profile_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get agent workload by agent_profile_id (migration 054+)"""
        query = """
            SELECT * FROM agent_workloads WHERE agent_profile_id = $1
        """
        result = await conn.fetchrow(query, agent_profile_id)
        return dict(result) if result else None

    async def create_workload(
        self,
        conn: asyncpg.Connection,
        agent_id: str,
    ) -> Dict[str, Any]:
        """DEPRECATED: agent_workloads.agent_id is 100% NULL. Use create_workload_for_profile()."""
        query = """
            INSERT INTO agent_workloads (
                agent_id, current_assignments, pending_declarations,
                in_progress_declarations, max_concurrent_assignments,
                capacity_percentage, workload_status, availability,
                last_updated_at
            )
            VALUES ($1, 0, 0, 0, 20, 0.00, 'available', 'available', NOW())
            ON CONFLICT (agent_id) DO NOTHING
            RETURNING *
        """
        result = await conn.fetchrow(query, agent_id)
        return dict(result) if result else None

    async def create_workload_for_profile(
        self,
        conn: asyncpg.Connection,
        agent_profile_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Create initial workload record for agent profile (migration 047+)

        Uses agent_profile_id as the primary identifier per migration 054.
        """
        query = """
            INSERT INTO agent_workloads (
                agent_profile_id, current_assignments, pending_declarations,
                in_progress_declarations, max_concurrent_assignments,
                capacity_percentage, workload_status, availability,
                last_updated_at
            )
            VALUES ($1, 0, 0, 0, 20, 0.00, 'available', 'available', NOW())
            ON CONFLICT (agent_profile_id) DO NOTHING
            RETURNING *
        """
        result = await conn.fetchrow(query, agent_profile_id)
        return dict(result) if result else None

    async def update_workload(
        self,
        conn: asyncpg.Connection,
        agent_profile_id: str,
        update_data: AgentWorkloadUpdate,
    ) -> Optional[Dict[str, Any]]:
        """Update agent workload by agent_profile_id"""
        updates = []
        params = [agent_profile_id]
        param_idx = 2

        for field, value in update_data.dict(exclude_unset=True).items():
            if value is not None:
                if field in ["workload_status", "availability"]:
                    value = value.value if hasattr(value, "value") else value
                updates.append(f"{field} = ${param_idx}")
                params.append(value)
                param_idx += 1

        if not updates:
            return await self.get_workload_by_profile_id(conn, agent_profile_id)

        updates.append(f"last_updated_at = ${param_idx}")
        params.append("NOW()")

        query = f"""
            UPDATE agent_workloads
            SET {', '.join(updates)}
            WHERE agent_profile_id = $1
            RETURNING *
        """
        result = await conn.fetchrow(query, *params)
        return dict(result) if result else None

    async def increment_assignments(
        self,
        conn: asyncpg.Connection,
        agent_id: str,
    ) -> Dict[str, Any]:
        """DEPRECATED: Uses dead agent_id column. No live callers."""
        query = """
            UPDATE agent_workloads
            SET current_assignments = current_assignments + 1,
                pending_declarations = pending_declarations + 1,
                capacity_percentage = ((current_assignments + 1)::numeric / max_concurrent_assignments::numeric) * 100,
                workload_status = CASE
                    WHEN ((current_assignments + 1)::numeric / max_concurrent_assignments::numeric) >= 1.0 THEN 'overloaded'::workload_status_enum
                    WHEN ((current_assignments + 1)::numeric / max_concurrent_assignments::numeric) >= 0.8 THEN 'busy'::workload_status_enum
                    WHEN ((current_assignments + 1)::numeric / max_concurrent_assignments::numeric) >= 0.5 THEN 'normal'::workload_status_enum
                    ELSE 'available'::workload_status_enum
                END,
                last_assignment_at = NOW(),
                last_updated_at = NOW()
            WHERE agent_id = $1
            RETURNING *
        """
        result = await conn.fetchrow(query, agent_id)
        return dict(result)

    async def decrement_assignments(
        self,
        conn: asyncpg.Connection,
        agent_id: str,
    ) -> Dict[str, Any]:
        """DEPRECATED: Uses dead agent_id column. No live callers."""
        query = """
            UPDATE agent_workloads
            SET current_assignments = GREATEST(0, current_assignments - 1),
                pending_declarations = GREATEST(0, pending_declarations - 1),
                capacity_percentage = (GREATEST(0, current_assignments - 1)::numeric / max_concurrent_assignments::numeric) * 100,
                workload_status = CASE
                    WHEN (GREATEST(0, current_assignments - 1)::numeric / max_concurrent_assignments::numeric) >= 1.0 THEN 'overloaded'::workload_status_enum
                    WHEN (GREATEST(0, current_assignments - 1)::numeric / max_concurrent_assignments::numeric) >= 0.8 THEN 'busy'::workload_status_enum
                    WHEN (GREATEST(0, current_assignments - 1)::numeric / max_concurrent_assignments::numeric) >= 0.5 THEN 'normal'::workload_status_enum
                    ELSE 'available'::workload_status_enum
                END,
                last_completion_at = NOW(),
                last_updated_at = NOW()
            WHERE agent_id = $1
            RETURNING *
        """
        result = await conn.fetchrow(query, agent_id)
        return dict(result)

    async def start_assignment(
        self,
        conn: asyncpg.Connection,
        agent_id: str,
    ) -> Dict[str, Any]:
        """DEPRECATED: Uses dead agent_id column. No live callers."""
        query = """
            UPDATE agent_workloads
            SET pending_declarations = GREATEST(0, pending_declarations - 1),
                in_progress_declarations = in_progress_declarations + 1,
                last_updated_at = NOW()
            WHERE agent_id = $1
            RETURNING *
        """
        result = await conn.fetchrow(query, agent_id)
        return dict(result)

    async def complete_assignment(
        self,
        conn: asyncpg.Connection,
        agent_id: str,
    ) -> Dict[str, Any]:
        """DEPRECATED: Uses dead agent_id column. No live callers."""
        query = """
            UPDATE agent_workloads
            SET in_progress_declarations = GREATEST(0, in_progress_declarations - 1),
                current_assignments = GREATEST(0, current_assignments - 1),
                capacity_percentage = (GREATEST(0, current_assignments - 1)::numeric / max_concurrent_assignments::numeric) * 100,
                workload_status = CASE
                    WHEN (GREATEST(0, current_assignments - 1)::numeric / max_concurrent_assignments::numeric) >= 1.0 THEN 'overloaded'::workload_status_enum
                    WHEN (GREATEST(0, current_assignments - 1)::numeric / max_concurrent_assignments::numeric) >= 0.8 THEN 'busy'::workload_status_enum
                    WHEN (GREATEST(0, current_assignments - 1)::numeric / max_concurrent_assignments::numeric) >= 0.5 THEN 'normal'::workload_status_enum
                    ELSE 'available'::workload_status_enum
                END,
                avg_daily_completions = avg_daily_completions + 1,
                last_completion_at = NOW(),
                last_updated_at = NOW()
            WHERE agent_id = $1
            RETURNING *
        """
        result = await conn.fetchrow(query, agent_id)
        return dict(result)

    async def get_available_agents(
        self,
        conn: asyncpg.Connection,
        ministry_id: int,
        max_capacity_percentage: float = 80.0,
        entity_location_id: Optional["UUID"] = None,
    ) -> List[Dict[str, Any]]:
        """Get agents with available capacity.

        Considers both direct ministry assignment and entity-based assignment.
        An agent can be linked to a ministry directly (ap.ministry_id) or
        through an entity (ap.entity_id -> entities.ministry_id).

        When entity_location_id is provided, prefers agents bound to that
        specific site, but includes supervisor/floating agents (NULL location)
        as well. Falls back to all entity agents if no site-specific ones found.
        """
        location_filter = ""
        params: list = [ministry_id, max_capacity_percentage]

        if entity_location_id:
            # Filter: agents at this specific site
            # OR root-entity agents with NULL location (sees all sites under their entity)
            # Department-level agents MUST have entity_location_id set (even supervisors)
            location_filter = (
                "AND (ap.entity_location_id = $3"
                " OR (ap.entity_location_id IS NULL"
                "     AND EXISTS (SELECT 1 FROM entities e2 WHERE e2.id = ap.entity_id AND e2.parent_entity_id IS NULL)))"
            )
            params.append(entity_location_id)

        query = f"""
            SELECT aw.*, COALESCE(ap.ministry_id, e.ministry_id) as ministry_id
            FROM agent_workloads aw
            JOIN agent_profiles ap ON aw.agent_profile_id = ap.id
            LEFT JOIN entities e ON ap.entity_id = e.id
            WHERE (ap.ministry_id = $1 OR e.ministry_id = $1)
              AND ap.is_active = true
              AND aw.availability = 'available'
              AND aw.capacity_percentage < $2
              AND aw.workload_status != 'overloaded'
              {location_filter}
            ORDER BY aw.capacity_percentage ASC, aw.quality_score_avg DESC
        """
        results = await conn.fetch(query, *params)

        # Fallback: if no agents found with location filter, retry without it
        if not results and entity_location_id:
            fallback_query = """
                SELECT aw.*, COALESCE(ap.ministry_id, e.ministry_id) as ministry_id
                FROM agent_workloads aw
                JOIN agent_profiles ap ON aw.agent_profile_id = ap.id
                LEFT JOIN entities e ON ap.entity_id = e.id
                WHERE (ap.ministry_id = $1 OR e.ministry_id = $1)
                  AND ap.is_active = true
                  AND aw.availability = 'available'
                  AND aw.capacity_percentage < $2
                  AND aw.workload_status != 'overloaded'
                ORDER BY aw.capacity_percentage ASC, aw.quality_score_avg DESC
            """
            results = await conn.fetch(fallback_query, ministry_id, max_capacity_percentage)

        return [dict(r) for r in results]

    async def get_overloaded_agents(
        self,
        conn: asyncpg.Connection,
        ministry_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get overloaded agents for rebalancing.

        Considers both direct ministry assignment and entity-based assignment.
        """
        where_clause = "WHERE aw.workload_status = 'overloaded'"
        params = []

        if ministry_id:
            where_clause += " AND (ap.ministry_id = $1 OR e.ministry_id = $1)"
            params.append(ministry_id)

        query = f"""
            SELECT aw.*, COALESCE(ap.ministry_id, e.ministry_id) as ministry_id
            FROM agent_workloads aw
            JOIN agent_profiles ap ON aw.agent_profile_id = ap.id
            LEFT JOIN entities e ON ap.entity_id = e.id
            {where_clause}
            ORDER BY aw.capacity_percentage DESC
        """
        results = await conn.fetch(query, *params)
        return [dict(r) for r in results]

    # ========================================================================
    # AGENT_PERFORMANCE_STATS
    # ========================================================================

    async def get_performance_stats(
        self,
        conn: asyncpg.Connection,
        agent_id: int,
    ) -> Optional[Dict[str, Any]]:
        """Get agent performance stats by legacy agent_id (INTEGER)"""
        query = """
            SELECT * FROM agent_performance_stats WHERE agent_id = $1
        """
        result = await conn.fetchrow(query, agent_id)
        return dict(result) if result else None

    async def get_performance_by_profile_id(
        self,
        conn: asyncpg.Connection,
        agent_profile_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get agent performance stats by agent_profile_id (UUID).

        Computes performance from TWO sources via 3 CTEs (one scan per table):
        1. assignments table — for workflow-based agents (CNEDOGE, DGT, etc.)
        2. payment_validation_audit — for payment-based agents (TESORO)
        3. service_payments — for active lock count

        Both sources are combined so the endpoint works for any agent type.
        """
        query = """
            WITH assignment_stats AS (
                SELECT
                    COUNT(*) FILTER (WHERE status = 'completed') as processed,
                    COUNT(*) FILTER (WHERE status = 'completed'
                        AND validation_status = 'approved') as approved,
                    COUNT(*) FILTER (WHERE status = 'completed'
                        AND validation_status = 'rejected') as rejected,
                    COUNT(*) FILTER (WHERE status = 'completed'
                        AND validation_status = 'escalated') as escalated,
                    ROUND(COALESCE(
                        AVG(EXTRACT(EPOCH FROM (completed_at - started_at)) / 60)
                            FILTER (WHERE status = 'completed'),
                        0
                    )::numeric, 2) as avg_minutes,
                    COUNT(*) FILTER (WHERE deadline_met = true) as sla_ok,
                    COUNT(*) FILTER (WHERE deadline_met = false) as sla_miss,
                    COUNT(*) FILTER (WHERE deadline_met IS NOT NULL) as sla_total,
                    MAX(completed_at) as last_completed
                FROM assignments
                WHERE agent_profile_id = $1::uuid
                AND created_at >= date_trunc('month', CURRENT_DATE)
            ),
            payment_stats AS (
                SELECT
                    COUNT(*) as processed,
                    COUNT(*) FILTER (WHERE action = 'approve') as approved,
                    COUNT(*) FILTER (WHERE action = 'reject') as rejected,
                    COUNT(*) FILTER (WHERE action = 'escalate') as escalated,
                    MAX(created_at) as last_action
                FROM payment_validation_audit
                WHERE agent_profile_id = $1::uuid
                AND created_at >= date_trunc('month', CURRENT_DATE)
            ),
            lock_stats AS (
                SELECT COUNT(*)::int as active_locks
                FROM service_payments
                WHERE assigned_agent_id = $1::uuid
                AND workflow_status = 'agent_reviewing'
            )
            SELECT
                $1 as agent_profile_id,
                (a.processed + p.processed) as current_month_processed,
                (a.approved + p.approved) as current_month_approved,
                (a.rejected + p.rejected) as current_month_rejected,
                (a.escalated + p.escalated) as current_month_escalated,
                a.avg_minutes as avg_processing_minutes,
                NULL::numeric as avg_lock_duration_minutes,
                a.sla_ok as sla_respected_count,
                a.sla_miss as sla_missed_count,
                CASE WHEN a.sla_total > 0
                    THEN ROUND(a.sla_ok::numeric / a.sla_total * 100, 2)
                    ELSE NULL
                END as sla_respect_percentage,
                l.active_locks as current_active_locks,
                0 as max_concurrent_locks,
                GREATEST(a.last_completed, p.last_action) as last_action_at,
                NULL::timestamp as last_login_at,
                date_trunc('month', CURRENT_DATE)::date as stats_period_start,
                NULL::date as stats_period_end,
                NOW() as updated_at
            FROM assignment_stats a
            CROSS JOIN payment_stats p
            CROSS JOIN lock_stats l
        """
        try:
            result = await conn.fetchrow(query, agent_profile_id)
            return dict(result) if result else None
        except Exception as e:
            logger.warning(f"Error fetching performance by profile_id {agent_profile_id}: {e}")
            return None

    async def ensure_performance_stats(
        self,
        conn: asyncpg.Connection,
        agent_profile_id: str,
    ) -> None:
        """Ensure performance stats row exists for agent (UPSERT on agent_profile_id).

        After migration 157, agent_profile_id is PK (was agent_id INT before).
        ministry_id resolved via entity chain: agent_profile → entity → entity.ministry_id
        (ap.ministry_id is legacy and NULL for some agents like CNEDOGE).
        """
        await conn.execute("""
            INSERT INTO agent_performance_stats (
                agent_id, agent_profile_id, ministry_id,
                current_month_processed, current_month_approved,
                current_month_rejected, current_month_escalated,
                sla_respected_count, sla_missed_count,
                current_active_locks, max_concurrent_locks,
                stats_period_start, updated_at
            )
            SELECT
                0, ap.id, COALESCE(e.ministry_id, ap.ministry_id, 0),
                0, 0, 0, 0, 0, 0, 0, 0,
                date_trunc('month', CURRENT_DATE)::date, NOW()
            FROM agent_profiles ap
            LEFT JOIN entities e ON e.id = ap.entity_id
            WHERE ap.id = $1::uuid
            ON CONFLICT (agent_profile_id) DO NOTHING
        """, agent_profile_id)

    async def increment_processed(
        self,
        conn: asyncpg.Connection,
        agent_profile_id: str,
    ) -> None:
        """Increment processed count"""
        await self.ensure_performance_stats(conn, agent_profile_id)
        await conn.execute("""
            UPDATE agent_performance_stats
            SET current_month_processed = current_month_processed + 1,
                updated_at = NOW()
            WHERE agent_profile_id = $1::uuid
        """, agent_profile_id)

    async def increment_approved(
        self,
        conn: asyncpg.Connection,
        agent_profile_id: str,
    ) -> None:
        """Increment approved count"""
        await self.ensure_performance_stats(conn, agent_profile_id)
        await conn.execute("""
            UPDATE agent_performance_stats
            SET current_month_approved = current_month_approved + 1,
                last_action_at = NOW(),
                updated_at = NOW()
            WHERE agent_profile_id = $1::uuid
        """, agent_profile_id)

    async def increment_rejected(
        self,
        conn: asyncpg.Connection,
        agent_profile_id: str,
    ) -> None:
        """Increment rejected count"""
        await self.ensure_performance_stats(conn, agent_profile_id)
        await conn.execute("""
            UPDATE agent_performance_stats
            SET current_month_rejected = current_month_rejected + 1,
                last_action_at = NOW(),
                updated_at = NOW()
            WHERE agent_profile_id = $1::uuid
        """, agent_profile_id)

    async def increment_escalated(
        self,
        conn: asyncpg.Connection,
        agent_profile_id: str,
    ) -> None:
        """Increment escalated count"""
        await self.ensure_performance_stats(conn, agent_profile_id)
        await conn.execute("""
            UPDATE agent_performance_stats
            SET current_month_escalated = current_month_escalated + 1,
                last_action_at = NOW(),
                updated_at = NOW()
            WHERE agent_profile_id = $1::uuid
        """, agent_profile_id)

    async def update_sla_stats(
        self,
        conn: asyncpg.Connection,
        agent_profile_id: str,
        sla_respected: bool,
    ) -> None:
        """Update SLA statistics.

        sla_respect_percentage is a GENERATED ALWAYS column (computed by
        Postgres from sla_respected_count + sla_missed_count). Writing to
        it raises GeneratedAlwaysError, so we only bump the raw counters
        and let the DB derive the percentage.
        """
        await self.ensure_performance_stats(conn, agent_profile_id)
        field = "sla_respected_count" if sla_respected else "sla_missed_count"
        await conn.execute(f"""
            UPDATE agent_performance_stats
            SET {field} = {field} + 1,
                updated_at = NOW()
            WHERE agent_profile_id = $1::uuid
        """, agent_profile_id)

    async def get_top_performers(
        self,
        conn: asyncpg.Connection,
        ministry_id: int,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get top performing agents.

        Considers both direct ministry assignment and entity-based assignment.
        """
        query = """
            SELECT aps.*, ap.user_id
            FROM agent_performance_stats aps
            JOIN agent_profiles ap ON aps.agent_profile_id = ap.id
            LEFT JOIN entities e ON ap.entity_id = e.id
            WHERE (ap.ministry_id = $1 OR e.ministry_id = $1)
              AND ap.is_active = true
            ORDER BY
                aps.sla_respect_percentage DESC,
                aps.current_month_processed DESC,
                aps.avg_processing_minutes ASC
            LIMIT $2
        """
        results = await conn.fetch(query, ministry_id, limit)
        return [dict(r) for r in results]

    async def reset_monthly_stats(
        self,
        conn: asyncpg.Connection,
    ) -> int:
        """Reset monthly statistics (run at month start).

        sla_respect_percentage is a GENERATED ALWAYS column — Postgres
        recomputes it automatically from sla_respected_count +
        sla_missed_count. Resetting the raw counters to 0 sets the
        percentage to 0 via the CASE WHEN (count=0) branch.
        """
        query = """
            UPDATE agent_performance_stats
            SET current_month_processed = 0,
                current_month_approved = 0,
                current_month_rejected = 0,
                current_month_escalated = 0,
                sla_respected_count = 0,
                sla_missed_count = 0,
                stats_period_start = CURRENT_DATE,
                stats_period_end = NULL,
                updated_at = NOW()
            WHERE stats_period_start < CURRENT_DATE - INTERVAL '1 month'
            RETURNING agent_id
        """
        results = await conn.fetch(query)
        return len(results)

    # ========================================================================
    # METHODS USING DATABASE VIEWS - Optimized queries with pre-joined data
    # ========================================================================

    async def get_workload_dashboard(
        self,
        conn: asyncpg.Connection,
        agent_id: Optional[str] = None,
        ministry_id: Optional[int] = None,
        load_level: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[List[Dict[str, Any]], int]:
        """
        Get agent workload dashboard using v_agents_workload_dashboard view

        This view includes:
        - Agent info (name, email, ministry)
        - Real-time workload metrics
        - Capacity calculations
        - Performance metrics
        - Availability status

        Args:
            conn: Database connection
            agent_id: Optional filter by specific agent
            ministry_id: Optional filter by ministry
            load_level: Optional filter (LOW, MEDIUM, HIGH, FULL)
            limit: Max results
            offset: Pagination offset

        Returns:
            Tuple of (agents list, total count)
        """
        try:
            where_conditions = []
            params = []

            if agent_id:
                where_conditions.append(f"user_id = ${len(params) + 1}")
                params.append(agent_id)

            if ministry_id:
                where_conditions.append(f"ministry_id = ${len(params) + 1}")
                params.append(ministry_id)

            if load_level:
                where_conditions.append(f"load_level = ${len(params) + 1}")
                params.append(load_level)

            where_clause = f"WHERE {' AND '.join(where_conditions)}" if where_conditions else ""

            # Count query
            count_query = f"""
                SELECT COUNT(*) FROM v_agents_workload_dashboard
                {where_clause}
            """
            total = await conn.fetchval(count_query, *params)

            # Data query
            params.extend([limit, offset])
            data_query = f"""
                SELECT * FROM v_agents_workload_dashboard
                {where_clause}
                ORDER BY capacity_percentage ASC, is_active DESC
                LIMIT ${len(params) - 1} OFFSET ${len(params)}
            """

            results = await conn.fetch(data_query, *params)
            agents = [dict(r) for r in results]

            return agents, total

        except Exception as e:
            logger.error(f"Error fetching workload dashboard: {str(e)}")
            raise

    async def list_available_agents_by_ministry(
        self,
        conn: asyncpg.Connection,
    ) -> List[Dict[str, Any]]:
        """
        List available agents grouped by ministry using v_available_agents_by_ministry view

        This view includes:
        - Ministry-level aggregations
        - Total/active/available agent counts
        - Capacity metrics per ministry
        - Average performance metrics

        Returns:
            List of ministry availability data
        """
        try:
            query = """
                SELECT * FROM v_available_agents_by_ministry
                ORDER BY available_capacity DESC
            """

            results = await conn.fetch(query)
            return [dict(r) for r in results]

        except Exception as e:
            logger.error(f"Error fetching available agents by ministry: {str(e)}")
            raise

    async def get_agent_performance_rankings(
        self,
        conn: asyncpg.Connection,
        ministry_id: Optional[int] = None,
        performance_tier: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Get agent performance rankings using v_agent_performance_rankings view

        This view includes:
        - Composite performance scores
        - Overall and ministry-specific rankings
        - Performance tiers (EXCELLENT, GOOD, AVERAGE, NEEDS_IMPROVEMENT)
        - Processing metrics

        Args:
            conn: Database connection
            ministry_id: Optional filter by ministry
            performance_tier: Optional filter by tier
            limit: Max results

        Returns:
            List of ranked agents
        """
        try:
            where_conditions = []
            params = []

            if ministry_id:
                where_conditions.append(f"ministry_id = ${len(params) + 1}")
                params.append(ministry_id)

            if performance_tier:
                where_conditions.append(f"performance_tier = ${len(params) + 1}")
                params.append(performance_tier)

            where_clause = f"WHERE {' AND '.join(where_conditions)}" if where_conditions else ""

            params.append(limit)
            query = f"""
                SELECT * FROM v_agent_performance_rankings
                {where_clause}
                ORDER BY performance_score DESC
                LIMIT ${len(params)}
            """

            results = await conn.fetch(query, *params)
            return [dict(r) for r in results]

        except Exception as e:
            logger.error(f"Error fetching agent performance rankings: {str(e)}")
            raise

    async def get_admin_alerts_dashboard(self, conn) -> dict:
        """
        Single aggregated SQL returning all admin alerts.
        O(1) per CTE via existing partial indexes.
        Returns dict matching AdminAlertsDashboard model.
        """
        try:
            query = """
            WITH inactive_agents AS (
                SELECT ap.id as agent_profile_id,
                       u.full_name as agent_name,
                       e.code as entity_code,
                       aw.last_assignment_at,
                       aw.last_completion_at,
                       EXTRACT(EPOCH FROM (NOW() - GREATEST(
                           COALESCE(aw.last_assignment_at, ap.created_at),
                           COALESCE(aw.last_completion_at, ap.created_at)
                       ))) / 3600 as inactive_hours
                FROM agent_profiles ap
                JOIN agent_workloads aw ON aw.agent_profile_id = ap.id
                JOIN users u ON u.id = ap.user_id
                LEFT JOIN entities e ON e.id = ap.entity_id
                WHERE ap.is_active = true
                AND GREATEST(
                    COALESCE(aw.last_assignment_at, ap.created_at),
                    COALESCE(aw.last_completion_at, ap.created_at)
                ) < NOW() - INTERVAL '48 hours'
            ),
            overloaded_agents AS (
                SELECT ap.id as agent_profile_id,
                       u.full_name as agent_name,
                       e.code as entity_code,
                       aw.capacity_percentage,
                       aw.current_assignments,
                       aw.max_concurrent_assignments
                FROM agent_profiles ap
                JOIN agent_workloads aw ON aw.agent_profile_id = ap.id
                JOIN users u ON u.id = ap.user_id
                LEFT JOIN entities e ON e.id = ap.entity_id
                WHERE ap.is_active = true
                AND aw.capacity_percentage > 80
            ),
            stale_locks AS (
                SELECT sp.id as payment_id,
                       sp.payment_reference,
                       sp.assigned_agent_id as agent_profile_id,
                       u.full_name as agent_name,
                       sp.assigned_at as locked_at,
                       EXTRACT(EPOCH FROM (NOW() - sp.assigned_at)) / 3600 as locked_hours
                FROM service_payments sp
                JOIN agent_profiles ap ON ap.id = sp.assigned_agent_id
                JOIN users u ON u.id = ap.user_id
                WHERE sp.assigned_agent_id IS NOT NULL
                AND sp.assigned_at < NOW() - INTERVAL '4 hours'
                AND sp.workflow_status = 'agent_reviewing'
            ),
            sla_at_risk AS (
                SELECT sp.id as payment_id,
                       sp.payment_reference,
                       sp.sla_target_date,
                       EXTRACT(EPOCH FROM (sp.sla_target_date - NOW())) / 3600 as hours_remaining
                FROM service_payments sp
                WHERE sp.workflow_status = 'pending_agent_review'
                AND sp.sla_target_date IS NOT NULL
                AND sp.sla_target_date < NOW() + INTERVAL '24 hours'
                AND sp.sla_target_date > NOW()
            ),
            workload_summary AS (
                SELECT e.code as entity_code,
                       e.name as entity_name,
                       COUNT(ap.id)::int as agent_count,
                       COUNT(*) FILTER (WHERE aw.capacity_percentage > 80)::int as overloaded_count,
                       COALESCE(AVG(aw.capacity_percentage), 0)::int as avg_capacity,
                       COALESCE(SUM(aw.current_assignments), 0)::int as total_assignments
                FROM agent_profiles ap
                JOIN agent_workloads aw ON aw.agent_profile_id = ap.id
                LEFT JOIN entities e ON e.id = ap.entity_id
                WHERE ap.is_active = true
                GROUP BY e.code, e.name
            )
            SELECT json_build_object(
                'inactive_count', (SELECT COUNT(*)::int FROM inactive_agents),
                'overloaded_count', (SELECT COUNT(*)::int FROM overloaded_agents),
                'stale_locks_count', (SELECT COUNT(*)::int FROM stale_locks),
                'sla_at_risk_count', (SELECT COUNT(*)::int FROM sla_at_risk),
                'inactive_agents', COALESCE((SELECT json_agg(row_to_json(t)) FROM inactive_agents t), '[]'::json),
                'overloaded_agents', COALESCE((SELECT json_agg(row_to_json(t)) FROM overloaded_agents t), '[]'::json),
                'stale_locks', COALESCE((SELECT json_agg(row_to_json(t)) FROM stale_locks t), '[]'::json),
                'sla_at_risk', COALESCE((SELECT json_agg(row_to_json(t)) FROM sla_at_risk t), '[]'::json),
                'workload_by_entity', COALESCE((SELECT json_agg(row_to_json(t)) FROM workload_summary t), '[]'::json)
            ) as dashboard
            """
            row = await conn.fetchrow(query)
            if not row:
                return {
                    'inactive_count': 0, 'overloaded_count': 0,
                    'stale_locks_count': 0, 'sla_at_risk_count': 0,
                    'total_alerts': 0,
                    'inactive_agents': [], 'overloaded_agents': [],
                    'stale_locks': [], 'sla_at_risk': [],
                    'workload_by_entity': [],
                }

            import json as json_lib
            dashboard = row['dashboard']
            if isinstance(dashboard, str):
                dashboard = json_lib.loads(dashboard)

            dashboard['total_alerts'] = (
                dashboard.get('inactive_count', 0) +
                dashboard.get('overloaded_count', 0) +
                dashboard.get('stale_locks_count', 0) +
                dashboard.get('sla_at_risk_count', 0)
            )
            return dashboard

        except Exception as e:
            logger.error(f"Error fetching admin alerts dashboard: {str(e)}")
            return {
                'inactive_count': 0, 'overloaded_count': 0,
                'stale_locks_count': 0, 'sla_at_risk_count': 0,
                'total_alerts': 0,
                'inactive_agents': [], 'overloaded_agents': [],
                'stale_locks': [], 'sla_at_risk': [],
                'workload_by_entity': [],
            }
