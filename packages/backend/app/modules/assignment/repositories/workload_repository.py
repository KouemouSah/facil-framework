"""
Workload Repository - Data access for agent workload tracking

Based on DATABASE_SCHEMA_REFERENCE.md (2026-01-18):
- Migration 053: `assignments` table (unified) with `agent_profile_id`
- Migration 054: `agent_workloads` uses `agent_profile_id` (agent_id deprecated)
- Table `declaration_assignments` no longer exists
"""

from typing import Optional, List
from uuid import UUID
from datetime import date
from loguru import logger

from app.modules.assignment.models.agent_workload import (
    AgentWorkload,
    AgentWorkloadStats,
    AgentPerformanceMetrics,
    AgentCapacityForecast,
    WorkloadBalanceReport,
)


class WorkloadRepository:
    """Repository for agent workload data operations"""

    def __init__(self):
        logger.info("WorkloadRepository initialized")

    async def get_agent_workload(self, db, agent_profile_id: UUID) -> Optional[AgentWorkload]:
        """Get current workload for an agent profile

        Args:
            db: Database connection
            agent_profile_id: UUID of the agent_profile (not user_id)
        """
        query = """
            SELECT
                ap.id as agent_profile_id,
                ap.user_id,
                COALESCE(u.full_name, u.first_name || ' ' || u.last_name) as agent_name,
                u.email as agent_email,
                COUNT(a.id) FILTER (WHERE a.status IN ('assigned', 'in_progress')) as current_assignments,
                COALESCE(aw.max_concurrent_assignments, 20) as max_concurrent_assignments,
                COUNT(a.id) FILTER (WHERE a.status = 'assigned') as pending_declarations,
                COUNT(a.id) FILTER (WHERE a.status = 'in_progress') as in_progress_declarations,
                COUNT(a.id) FILTER (WHERE a.status = 'completed' AND a.completed_at::date = CURRENT_DATE) as completed_today,
                MAX(a.assigned_at) as last_assignment_at,
                COALESCE(aw.workload_status::text, 'available') as workload_status,
                COALESCE(aw.availability::text, 'available') as availability,
                COALESCE(aw.success_rate, 0) as success_rate,
                aw.avg_processing_time_hours,
                ap.specializations
            FROM agent_profiles ap
            INNER JOIN users u ON u.id = ap.user_id
            LEFT JOIN agent_workloads aw ON aw.agent_profile_id = ap.id
            LEFT JOIN assignments a ON a.agent_profile_id = ap.id
            WHERE ap.id = $1
            GROUP BY ap.id, ap.user_id, u.id, u.full_name, u.first_name, u.last_name, u.email,
                     aw.max_concurrent_assignments, aw.workload_status, aw.availability,
                     aw.success_rate, aw.avg_processing_time_hours, ap.specializations
        """
        row = await db.fetchrow(query, agent_profile_id)
        if not row:
            return None

        data = dict(row)
        current = data.get('current_assignments', 0) or 0
        max_assign = data.get('max_concurrent_assignments', 20) or 20
        data['capacity_percentage'] = (current / max_assign) * 100 if max_assign > 0 else 0
        data['is_available'] = current < max_assign

        return AgentWorkload(**data)

    async def get_available_agents(
        self,
        db,
        max_workload_pct: float = 80,
        entity_id: Optional[UUID] = None,
        workflow_code: Optional[str] = None,
        entity_code: Optional[str] = None,
        entity_location_id: Optional[UUID] = None,
    ) -> List[AgentWorkload]:
        """Get available agents for assignment

        Migration 048: Uses unified 'agent' role with agent_profiles table
        Migration 053/054: Uses assignments table with agent_profile_id
        Migration 058: Entity-based routing via agent_profiles.entity_id
        Migration 104: Site-based routing via agent_profiles.entity_location_id

        Args:
            db: Database connection
            max_workload_pct: Maximum workload percentage (default 80%)
            entity_id: Filter agents by entity_id (CRITICAL for correct routing)
            workflow_code: Alternative: find entity by workflow_code and filter agents
            entity_code: Alternative: find entity by code (e.g., 'TESORO') and filter agents
            entity_location_id: Filter agents by specific site (NULL agents = supervisors, included)

        Returns:
            List of available agents, filtered by entity and optionally location
        """
        # If entity_code provided but no entity_id, find the entity by code
        if entity_code and not entity_id:
            entity_id = await self._get_entity_id_by_code(db, entity_code)
            if entity_id:
                logger.info(f"Resolved entity_code '{entity_code}' to entity_id '{entity_id}'")

        # If workflow_code provided but no entity_id, find the entity
        if workflow_code and not entity_id:
            entity_id = await self._get_entity_id_for_workflow(db, workflow_code)
            if entity_id:
                logger.info(f"Resolved workflow_code '{workflow_code}' to entity_id '{entity_id}'")

        # Build query with optional entity + location filters
        params = [max_workload_pct]
        entity_filter = ""
        location_filter = ""

        if entity_id:
            entity_filter = f"AND ap.entity_id = ${len(params) + 1}"
            params.append(entity_id)
            logger.info(f"Filtering agents by entity_id: {entity_id}")

        if entity_location_id:
            # Match agents at this specific site
            # OR root-entity agents with NULL location (e.g., root-level supervisors who see all sites)
            # Department-level agents MUST have entity_location_id set (even supervisors)
            location_filter = (
                f"AND (ap.entity_location_id = ${len(params) + 1}"
                f" OR (ap.entity_location_id IS NULL"
                f"     AND EXISTS (SELECT 1 FROM entities e2 WHERE e2.id = ap.entity_id AND e2.parent_entity_id IS NULL)))"
            )
            params.append(entity_location_id)
            logger.info(f"Filtering agents by entity_location_id: {entity_location_id}")

        query = f"""
            SELECT
                ap.id as agent_profile_id,
                ap.user_id,
                ap.entity_id,
                COALESCE(u.full_name, u.first_name || ' ' || u.last_name) as agent_name,
                u.email as agent_email,
                COUNT(a.id) FILTER (WHERE a.status IN ('assigned', 'in_progress')) as current_assignments,
                COALESCE(aw.max_concurrent_assignments, 20) as max_concurrent_assignments,
                COUNT(a.id) FILTER (WHERE a.status = 'assigned') as pending_declarations,
                COUNT(a.id) FILTER (WHERE a.status = 'in_progress') as in_progress_declarations,
                COUNT(a.id) FILTER (WHERE a.status = 'completed' AND a.completed_at::date = CURRENT_DATE) as completed_today,
                MAX(a.assigned_at) as last_assignment_at,
                COALESCE(aw.workload_status::text, 'available') as workload_status,
                COALESCE(aw.availability::text, 'available') as availability,
                COALESCE(aw.success_rate, 0) as success_rate,
                aw.avg_processing_time_hours,
                ap.specializations
            FROM agent_profiles ap
            INNER JOIN users u ON u.id = ap.user_id
            LEFT JOIN agent_workloads aw ON aw.agent_profile_id = ap.id
            LEFT JOIN assignments a ON a.agent_profile_id = ap.id
            WHERE ap.is_active = true
            AND u.role = 'agent'
            AND u.status = 'active'
            AND ap.is_supervisor = false
            AND COALESCE(aw.availability::text, 'available') = 'available'
            {entity_filter}
            {location_filter}
            GROUP BY ap.id, ap.user_id, ap.entity_id, u.id, u.full_name, u.first_name, u.last_name, u.email,
                     aw.max_concurrent_assignments, aw.workload_status, aw.availability,
                     aw.success_rate, aw.avg_processing_time_hours, ap.specializations
            HAVING (COUNT(a.id) FILTER (WHERE a.status IN ('assigned', 'in_progress'))::float /
                    COALESCE(aw.max_concurrent_assignments, 20)) * 100 <= $1
            ORDER BY COUNT(a.id) FILTER (WHERE a.status IN ('assigned', 'in_progress')) ASC
        """
        rows = await db.fetch(query, *params)

        # Location-strict fallback: if the capacity threshold excluded all
        # agents at the target site, retry at the SAME site WITHOUT the
        # capacity threshold. Location scope is absolute — work for a site
        # must always go to an agent at that site, even if overloaded.
        # Entity-wide fallback (routing to another city) is NEVER allowed
        # when entity_location_id is set.
        if not rows and entity_location_id:
            logger.info(
                f"No agents under capacity at location {entity_location_id}, "
                f"retrying same site without capacity threshold (strict location)"
            )
            fallback_params = []
            fallback_entity_filter = ""
            fallback_location_filter = ""
            if entity_id:
                fallback_entity_filter = f"AND ap.entity_id = ${len(fallback_params) + 1}"
                fallback_params.append(entity_id)
            fallback_location_filter = (
                f"AND (ap.entity_location_id = ${len(fallback_params) + 1}"
                f" OR (ap.entity_location_id IS NULL"
                f"     AND EXISTS (SELECT 1 FROM entities e2 WHERE e2.id = ap.entity_id AND e2.parent_entity_id IS NULL)))"
            )
            fallback_params.append(entity_location_id)
            fallback_query = f"""
                SELECT
                    ap.id as agent_profile_id,
                    ap.user_id,
                    ap.entity_id,
                    COALESCE(u.full_name, u.first_name || ' ' || u.last_name) as agent_name,
                    u.email as agent_email,
                    COUNT(a.id) FILTER (WHERE a.status IN ('assigned', 'in_progress')) as current_assignments,
                    COALESCE(aw.max_concurrent_assignments, 20) as max_concurrent_assignments,
                    COUNT(a.id) FILTER (WHERE a.status = 'assigned') as pending_declarations,
                    COUNT(a.id) FILTER (WHERE a.status = 'in_progress') as in_progress_declarations,
                    COUNT(a.id) FILTER (WHERE a.status = 'completed' AND a.completed_at::date = CURRENT_DATE) as completed_today,
                    MAX(a.assigned_at) as last_assignment_at,
                    COALESCE(aw.workload_status::text, 'available') as workload_status,
                    COALESCE(aw.availability::text, 'available') as availability,
                    COALESCE(aw.success_rate, 0) as success_rate,
                    aw.avg_processing_time_hours,
                    ap.specializations
                FROM agent_profiles ap
                INNER JOIN users u ON u.id = ap.user_id
                LEFT JOIN agent_workloads aw ON aw.agent_profile_id = ap.id
                LEFT JOIN assignments a ON a.agent_profile_id = ap.id
                WHERE ap.is_active = true
                AND u.role = 'agent'
                AND u.status = 'active'
                AND ap.is_supervisor = false
                AND COALESCE(aw.availability::text, 'available') = 'available'
                {fallback_entity_filter}
                {fallback_location_filter}
                GROUP BY ap.id, ap.user_id, ap.entity_id, u.id, u.full_name, u.first_name, u.last_name, u.email,
                         aw.max_concurrent_assignments, aw.workload_status, aw.availability,
                         aw.success_rate, aw.avg_processing_time_hours, ap.specializations
                ORDER BY COUNT(a.id) FILTER (WHERE a.status IN ('assigned', 'in_progress')) ASC
            """
            rows = await db.fetch(fallback_query, *fallback_params)
            if rows:
                logger.info(
                    f"Strict location fallback: found {len(rows)} agent(s) "
                    f"at location {entity_location_id} (over capacity, "
                    f"but location scope takes precedence)"
                )

        if not rows and entity_id:
            logger.warning(
                f"No available agents found for entity_id: {entity_id}"
                + (f" at location {entity_location_id}" if entity_location_id else "")
            )

        agents = []
        for row in rows:
            data = dict(row)
            current = data.get('current_assignments', 0) or 0
            max_assign = data.get('max_concurrent_assignments', 20) or 20
            data['capacity_percentage'] = (current / max_assign) * 100 if max_assign > 0 else 0
            data['is_available'] = True
            # Remove entity_id from data as it's not in AgentWorkload model
            data.pop('entity_id', None)
            agents.append(AgentWorkload(**data))

        logger.info(f"Found {len(agents)} available agents" + (f" for entity {entity_id}" if entity_id else ""))
        return agents

    async def _get_entity_id_by_code(self, db, entity_code: str) -> Optional[UUID]:
        """Find entity by its code

        Args:
            db: Database connection
            entity_code: The entity code (e.g., 'TESORO', 'CNEDOGE_PASAPORTE')

        Returns:
            entity_id if found, None otherwise
        """
        row = await db.fetchrow("""
            SELECT id FROM entities
            WHERE code = $1 AND is_active = true
        """, entity_code)

        if row:
            return row['id']

        logger.warning(f"No entity found for entity_code: {entity_code}")
        return None

    async def _get_entity_id_for_workflow(self, db, workflow_code: str) -> Optional[UUID]:
        """Find the entity that handles a specific workflow_code

        Searches entities.workflow_codes JSONB array for the workflow.

        Args:
            db: Database connection
            workflow_code: The workflow code (e.g., 'PASAPORTE_NUEVO')

        Returns:
            entity_id if found, None otherwise
        """
        # Search for entity where workflow_code is in the workflow_codes JSONB array
        row = await db.fetchrow("""
            SELECT id FROM entities
            WHERE workflow_codes ? $1
            AND is_active = true
            ORDER BY
                CASE entity_type
                    WHEN 'department' THEN 1
                    WHEN 'entity' THEN 2
                    ELSE 3
                END
            LIMIT 1
        """, workflow_code)

        if row:
            return row['id']

        logger.warning(f"No entity found for workflow_code: {workflow_code}")
        return None

    async def get_workload_balance_report(
        self,
        db,
        entity_id: Optional[UUID] = None,
    ) -> WorkloadBalanceReport:
        """Compute workload balance report for a team (entity-scoped or global).

        Args:
            db: Database connection
            entity_id: Optional entity_id to scope the report. None = all agents.

        Returns:
            WorkloadBalanceReport with team-wide metrics and balance score.
        """
        params: list = []
        entity_filter = ""
        if entity_id:
            entity_filter = f"AND ap.entity_id = ${len(params) + 1}"
            params.append(entity_id)

        query = f"""
            SELECT
                COUNT(*) as total_agents,
                COUNT(*) FILTER (
                    WHERE COALESCE(aw.availability::text, 'available') = 'available'
                ) as available_agents,
                COUNT(*) FILTER (
                    WHERE COALESCE(aw.workload_status::text, 'available') IN ('normal', 'busy')
                ) as busy_agents,
                COUNT(*) FILTER (
                    WHERE COALESCE(aw.workload_status::text, 'available') = 'overloaded'
                ) as overloaded_agents,
                COUNT(*) FILTER (
                    WHERE COALESCE(aw.availability::text, 'available') != 'available'
                ) as unavailable_agents,
                COALESCE(SUM(
                    (SELECT COUNT(*) FROM assignments a
                     WHERE a.agent_profile_id = ap.id
                     AND a.status IN ('assigned', 'in_progress'))
                ), 0) as total_assignments,
                COALESCE(AVG(
                    (SELECT COUNT(*) FROM assignments a
                     WHERE a.agent_profile_id = ap.id
                     AND a.status IN ('assigned', 'in_progress'))
                ), 0) as avg_assignments,
                COALESCE(MIN(
                    (SELECT COUNT(*) FROM assignments a
                     WHERE a.agent_profile_id = ap.id
                     AND a.status IN ('assigned', 'in_progress'))
                ), 0) as min_assignments,
                COALESCE(MAX(
                    (SELECT COUNT(*) FROM assignments a
                     WHERE a.agent_profile_id = ap.id
                     AND a.status IN ('assigned', 'in_progress'))
                ), 0) as max_assignments
            FROM agent_profiles ap
            INNER JOIN users u ON u.id = ap.user_id
            LEFT JOIN agent_workloads aw ON aw.agent_profile_id = ap.id
            WHERE ap.is_active = true
            AND u.role = 'agent'
            AND u.status = 'active'
            AND ap.is_supervisor = false
            {entity_filter}
        """
        row = await db.fetchrow(query, *params)

        total = int(row['total_agents']) if row else 0
        available = int(row['available_agents']) if row else 0
        overloaded = int(row['overloaded_agents']) if row else 0
        min_a = int(row['min_assignments']) if row else 0
        max_a = int(row['max_assignments']) if row else 0
        avg_a = float(row['avg_assignments']) if row else 0.0
        total_assignments = int(row['total_assignments']) if row else 0

        # Compute balance score: 100 = perfect, lower = more imbalanced
        if total <= 1 or max_a == 0:
            balance_score = 100.0
        else:
            spread = max_a - min_a
            balance_score = max(0.0, 100.0 - (spread / max(avg_a, 1)) * 25)

        rebalancing_needed = balance_score < 70 or overloaded > 0

        return WorkloadBalanceReport(
            total_agents=total,
            available_agents=available,
            busy_agents=int(row['busy_agents']) if row else 0,
            overloaded_agents=overloaded,
            unavailable_agents=int(row['unavailable_agents']) if row else 0,
            total_assignments=total_assignments,
            avg_assignments_per_agent=round(avg_a, 1),
            min_assignments=min_a,
            max_assignments=max_a,
            balance_score=round(min(balance_score, 100.0), 1),
            rebalancing_needed=rebalancing_needed,
        )

    async def get_workload_stats(
        self,
        db,
        agent_profile_id: UUID,
        start_date: date,
        end_date: date
    ) -> AgentWorkloadStats:
        """Get workload statistics for a period

        Args:
            db: Database connection
            agent_profile_id: UUID of the agent_profile (not user_id)
            start_date: Period start date
            end_date: Period end date
        """
        query = """
            SELECT
                COUNT(id) FILTER (WHERE status = 'completed') as total_completed,
                COUNT(id) as total_assigned,
                AVG(EXTRACT(EPOCH FROM (completed_at - assigned_at)) / 3600)
                    FILTER (WHERE status = 'completed') as avg_time
            FROM assignments
            WHERE agent_profile_id = $1
            AND assigned_at::date BETWEEN $2 AND $3
        """
        row = await db.fetchrow(query, agent_profile_id, start_date, end_date)
        data = dict(row) if row else {}

        return AgentWorkloadStats(
            period_start=start_date,
            period_end=end_date,
            total_assigned=data.get('total_assigned', 0) or 0,
            total_completed=data.get('total_completed', 0) or 0,
            average_processing_time_hours=data.get('avg_time', 0) or 0,
            completion_rate=(
                (data.get('total_completed', 0) or 0) /
                (data.get('total_assigned', 1) or 1)
            ) * 100
        )


    async def get_capacity_forecast(
        self,
        db,
        agent_profile_id: UUID,
        horizon_days: int = 7
    ) -> AgentCapacityForecast:
        """Get capacity forecast for an agent

        Args:
            db: Database connection
            agent_profile_id: UUID of the agent_profile
            horizon_days: Number of days to forecast

        Returns:
            AgentCapacityForecast with predictions
        """
        # Get current workload
        workload = await self.get_agent_workload(db, agent_profile_id)
        if not workload:
            raise ValueError(f"Agent profile {agent_profile_id} not found")

        # Calculate historical averages
        query = """
            SELECT
                COUNT(*) FILTER (WHERE status = 'completed')::float / NULLIF($2, 0) as avg_completions_per_day,
                COUNT(*) FILTER (WHERE status = 'assigned')::float / NULLIF($2, 0) as avg_new_per_day
            FROM assignments
            WHERE agent_profile_id = $1
            AND assigned_at >= NOW() - ($2 || ' days')::interval
        """
        row = await db.fetchrow(query, agent_profile_id, horizon_days)

        avg_completions = float(row['avg_completions_per_day'] or 0) if row else 0
        avg_new = float(row['avg_new_per_day'] or 0) if row else 0

        # Calculate forecast
        forecasted_completions = int(avg_completions * horizon_days)
        forecasted_new = int(avg_new * horizon_days)
        current_assignments = workload.current_assignments
        max_assignments = workload.max_concurrent_assignments

        forecasted_assignments = max(0, current_assignments - forecasted_completions + forecasted_new)
        forecasted_capacity_pct = (forecasted_assignments / max_assignments) * 100 if max_assignments > 0 else 0

        # Calculate recommendations
        available_capacity = max_assignments - forecasted_assignments
        can_accept = forecasted_capacity_pct < 80
        max_recommended = max(0, int(available_capacity * 0.8))  # 80% of available

        # Confidence based on data availability
        confidence = min(1.0, horizon_days / 30.0)  # Higher confidence with more history

        return AgentCapacityForecast(
            agent_profile_id=agent_profile_id,
            agent_name=workload.agent_name,
            horizon_days=horizon_days,
            current_assignments=current_assignments,
            current_capacity_pct=workload.capacity_percentage,
            max_concurrent_assignments=max_assignments,
            forecasted_completions=forecasted_completions,
            forecasted_new_assignments=forecasted_new,
            forecasted_capacity_pct=forecasted_capacity_pct,
            can_accept_new=can_accept,
            max_recommended_new=max_recommended,
            forecast_confidence=confidence
        )


def get_workload_repository(db=None) -> WorkloadRepository:
    """Dependency injection for WorkloadRepository"""
    return WorkloadRepository()
