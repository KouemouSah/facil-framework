"""
Assignment Repository - Data access for assignment operations

Based on DATABASE_SCHEMA_REFERENCE.md (2026-01-18):
- Table: assignments (unified, Migration 053)
- Uses agent_profile_id, item_id, item_type
- Columns: assigned_by_profile_id, reassigned_to_profile_id
"""

from typing import Optional, List
from uuid import UUID
from datetime import datetime
from loguru import logger

from app.modules.assignment.models.assignment_history import (
    Assignment,
    AssignmentCreate,
    AssignmentUpdate,
    AssignmentStatus,
    AssignmentMethod,
    ReassignmentCreate,
    ReassignmentReason,
)

# Shared column lists to keep all methods consistent
_ASSIGNMENT_COLS = """
    a.id, a.item_id, a.item_type, a.agent_profile_id, a.assigned_by_profile_id,
    a.assignment_method, a.status, a.priority_level, a.notes, a.deadline,
    a.assigned_at, a.started_at, a.completed_at, a.processing_duration_hours,
    a.deadline_met, a.validation_status, a.quality_score,
    a.auto_assignment_score, a.rule_applied_id,
    a.reassigned_at, a.reassignment_reason, a.reassignment_notes,
    a.reassigned_to_profile_id,
    a.created_at, a.updated_at
"""

_ASSIGNMENT_JOINS = """
    FROM assignments a
    LEFT JOIN agent_profiles ap_agent ON ap_agent.id = a.agent_profile_id
    LEFT JOIN users u_agent ON u_agent.id = ap_agent.user_id
    LEFT JOIN agent_profiles ap_assigner ON ap_assigner.id = a.assigned_by_profile_id
    LEFT JOIN users u_assigner ON u_assigner.id = ap_assigner.user_id
    LEFT JOIN agent_profiles ap_reassigned ON ap_reassigned.id = a.reassigned_to_profile_id
    LEFT JOIN users u_reassigned ON u_reassigned.id = ap_reassigned.user_id
"""

_NAME_COLS = """
    u_agent.full_name as agent_name,
    u_assigner.full_name as assigned_by_name,
    u_reassigned.full_name as reassigned_to_name
"""

# For INSERT/UPDATE RETURNING (no JOINs available)
_RETURNING_COLS = """
    RETURNING id, item_id, item_type, agent_profile_id, assigned_by_profile_id,
              assignment_method, status, priority_level, notes, deadline,
              assigned_at, started_at, completed_at, processing_duration_hours,
              deadline_met, validation_status, quality_score,
              auto_assignment_score, rule_applied_id,
              reassigned_at, reassignment_reason, reassignment_notes,
              reassigned_to_profile_id,
              created_at, updated_at
"""


class AssignmentRepository:
    """Repository for assignment data operations"""

    def __init__(self):
        logger.info("AssignmentRepository initialized")

    async def create(
        self,
        db,
        data: AssignmentCreate,
        assigned_by_profile_id: Optional[UUID] = None
    ) -> Assignment:
        """Create a new assignment

        Args:
            db: Database connection
            data: AssignmentCreate with item_id, item_type, agent_profile_id
            assigned_by_profile_id: UUID of supervisor's agent_profile (optional)
        """
        query = f"""
            INSERT INTO assignments
            (item_id, item_type, agent_profile_id, assigned_by_profile_id,
             assignment_method, status, priority_level, notes, deadline, assigned_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW())
            {_RETURNING_COLS}
        """
        row = await db.fetchrow(
            query,
            data.item_id,
            data.item_type,
            data.agent_profile_id,
            assigned_by_profile_id,
            data.assignment_method.value,
            AssignmentStatus.ASSIGNED.value,
            data.priority_level,
            data.notes,
            data.deadline
        )
        return Assignment(**dict(row)) if row else None

    async def get_by_id(self, db, assignment_id: UUID) -> Optional[Assignment]:
        """Get assignment by ID with agent name JOINs"""
        query = f"""
            SELECT {_ASSIGNMENT_COLS},
                   {_NAME_COLS}
            {_ASSIGNMENT_JOINS}
            WHERE a.id = $1
        """
        row = await db.fetchrow(query, assignment_id)
        return Assignment(**dict(row)) if row else None

    async def update(
        self,
        db,
        assignment_id: UUID,
        data: AssignmentUpdate
    ) -> Optional[Assignment]:
        """Update assignment"""
        updates = []
        values = []
        param_count = 1

        if data.status:
            updates.append(f"status = ${param_count}")
            values.append(data.status.value)
            param_count += 1

            # Auto-update timestamps based on status
            if data.status == AssignmentStatus.IN_PROGRESS:
                updates.append("started_at = COALESCE(started_at, NOW())")
            elif data.status == AssignmentStatus.COMPLETED:
                updates.append("completed_at = NOW()")
                updates.append("""
                    processing_duration_hours = EXTRACT(EPOCH FROM (NOW() - COALESCE(started_at, assigned_at))) / 3600
                """)

        if data.priority_level is not None:
            updates.append(f"priority_level = ${param_count}")
            values.append(data.priority_level)
            param_count += 1

        if data.notes is not None:
            updates.append(f"notes = ${param_count}")
            values.append(data.notes)
            param_count += 1

        if data.validation_status is not None:
            updates.append(f"validation_status = ${param_count}")
            values.append(data.validation_status)
            param_count += 1

        if data.quality_score is not None:
            updates.append(f"quality_score = ${param_count}")
            values.append(data.quality_score)
            param_count += 1

        if not updates:
            return await self.get_by_id(db, assignment_id)

        updates.append("updated_at = NOW()")
        values.append(assignment_id)

        query = f"""
            UPDATE assignments
            SET {', '.join(updates)}
            WHERE id = ${param_count}
            {_RETURNING_COLS}
        """
        row = await db.fetchrow(query, *values)
        return Assignment(**dict(row)) if row else None

    async def reassign(
        self,
        db,
        data: ReassignmentCreate,
        reassigned_by_profile_id: UUID
    ) -> Optional[Assignment]:
        """Reassign to another agent

        Args:
            db: Database connection
            data: ReassignmentCreate with assignment_id, new_agent_profile_id, reason
            reassigned_by_profile_id: UUID of supervisor's agent_profile who is doing the reassignment
        """
        query = f"""
            UPDATE assignments
            SET reassigned_to_profile_id = $1,
                reassignment_reason = $2,
                reassignment_notes = $3,
                reassigned_at = NOW(),
                status = $4,
                updated_at = NOW()
            WHERE id = $5
            {_RETURNING_COLS}
        """
        row = await db.fetchrow(
            query,
            data.new_agent_profile_id,
            data.reason.value,
            data.notes,
            AssignmentStatus.REASSIGNED.value,
            data.assignment_id
        )
        return Assignment(**dict(row)) if row else None

    async def list_all(
        self,
        db,
        agent_profile_id: Optional[UUID] = None,
        status: Optional[str] = None,
        item_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        entity_id: Optional[UUID] = None,
    ) -> List[Assignment]:
        """List assignments with optional filters

        Args:
            db: Database connection
            agent_profile_id: Filter by agent_profile.id
            status: Filter by assignment status
            item_type: Filter by item type (declaration type or workflow code)
            limit: Max results
            offset: Pagination offset
            entity_id: Filter by agent's entity_id (supervisor scoping)
        """
        conditions = []
        values = []
        param_count = 1

        if agent_profile_id:
            conditions.append(f"a.agent_profile_id = ${param_count}")
            values.append(agent_profile_id)
            param_count += 1

        if status:
            conditions.append(f"a.status = ${param_count}")
            values.append(status)
            param_count += 1

        if item_type:
            conditions.append(f"a.item_type = ${param_count}")
            values.append(item_type)
            param_count += 1

        if entity_id:
            conditions.append(f"ap_agent.entity_id = ${param_count}")
            values.append(entity_id)
            param_count += 1

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        values.extend([limit, offset])
        query = f"""
            SELECT {_ASSIGNMENT_COLS},
                   {_NAME_COLS}
            {_ASSIGNMENT_JOINS}
            {where_clause}
            ORDER BY a.assigned_at DESC
            LIMIT ${param_count} OFFSET ${param_count + 1}
        """
        rows = await db.fetch(query, *values)
        return [Assignment(**dict(row)) for row in rows]

    async def get_active_assignments(
        self,
        db,
        agent_profile_id: Optional[UUID] = None
    ) -> List[Assignment]:
        """Get active (non-completed) assignments

        Args:
            db: Database connection
            agent_profile_id: Filter by agent_profile.id (optional)
        """
        conditions = ["a.status NOT IN ('completed', 'cancelled', 'rejected')"]
        values = []
        param_count = 1

        if agent_profile_id:
            conditions.append(f"a.agent_profile_id = ${param_count}")
            values.append(agent_profile_id)
            param_count += 1

        where_clause = f"WHERE {' AND '.join(conditions)}"

        query = f"""
            SELECT {_ASSIGNMENT_COLS},
                   {_NAME_COLS}
            {_ASSIGNMENT_JOINS}
            {where_clause}
            ORDER BY a.priority_level DESC, a.assigned_at ASC
        """
        rows = await db.fetch(query, *values)
        return [Assignment(**dict(row)) for row in rows]

    async def get_overdue_assignments(self, db) -> List[Assignment]:
        """Get assignments past their deadline"""
        query = f"""
            SELECT {_ASSIGNMENT_COLS},
                   {_NAME_COLS}
            {_ASSIGNMENT_JOINS}
            WHERE a.deadline < NOW()
            AND a.status NOT IN ('completed', 'cancelled', 'rejected')
            ORDER BY a.deadline ASC
        """
        rows = await db.fetch(query)
        return [Assignment(**dict(row)) for row in rows]

    async def get_agent_stats(
        self,
        db,
        agent_profile_id: UUID,
        period_days: int = 30
    ):
        """Get agent statistics for a period

        Args:
            db: Database connection
            agent_profile_id: UUID of the agent_profile
            period_days: Number of days to look back
        """
        from app.modules.assignment.models.assignment_history import AgentAssignmentStats

        query = """
            SELECT
                $1::uuid as agent_profile_id,
                $2::int as period_days,
                COUNT(*) as total_assignments,
                COUNT(*) FILTER (WHERE status = 'completed') as completed_assignments,
                COUNT(*) FILTER (WHERE status IN ('assigned', 'in_progress', 'pending_review')) as pending_assignments,
                COUNT(*) FILTER (WHERE status = 'rejected') as rejected_assignments,
                AVG(processing_duration_hours) FILTER (WHERE status = 'completed') as avg_processing_time_hours,
                COALESCE(
                    COUNT(*) FILTER (WHERE status = 'completed')::float /
                    NULLIF(COUNT(*) FILTER (WHERE status IN ('completed', 'rejected')), 0),
                    0
                ) as success_rate,
                AVG(quality_score) FILTER (WHERE quality_score IS NOT NULL) as quality_score_avg,
                COALESCE(
                    COUNT(*) FILTER (WHERE deadline_met = true)::float /
                    NULLIF(COUNT(*) FILTER (WHERE deadline IS NOT NULL AND status = 'completed'), 0),
                    0
                ) as deadline_compliance_rate
            FROM assignments
            WHERE agent_profile_id = $1
            AND assigned_at >= NOW() - MAKE_INTERVAL(days => $2)
        """
        row = await db.fetchrow(query, agent_profile_id, period_days)

        # Get by status breakdown
        status_query = """
            SELECT status, COUNT(*) as count
            FROM assignments
            WHERE agent_profile_id = $1
            AND assigned_at >= NOW() - MAKE_INTERVAL(days => $2)
            GROUP BY status
        """
        status_rows = await db.fetch(status_query, agent_profile_id, period_days)
        by_status = {r['status']: r['count'] for r in status_rows}

        # Get by type breakdown
        type_query = """
            SELECT item_type, COUNT(*) as count
            FROM assignments
            WHERE agent_profile_id = $1
            AND assigned_at >= NOW() - MAKE_INTERVAL(days => $2)
            GROUP BY item_type
        """
        type_rows = await db.fetch(type_query, agent_profile_id, period_days)
        by_type = {r['item_type']: r['count'] for r in type_rows}

        return AgentAssignmentStats(
            agent_profile_id=agent_profile_id,
            period_days=period_days,
            total_assignments=row['total_assignments'] or 0,
            completed_assignments=row['completed_assignments'] or 0,
            pending_assignments=row['pending_assignments'] or 0,
            rejected_assignments=row['rejected_assignments'] or 0,
            avg_processing_time_hours=float(row['avg_processing_time_hours'] or 0),
            success_rate=float(row['success_rate'] or 0),
            quality_score_avg=float(row['quality_score_avg'] or 0),
            deadline_compliance_rate=float(row['deadline_compliance_rate'] or 0),
            by_status=by_status,
            by_type=by_type
        )

    async def get_supervisor_stats(
        self,
        db,
        supervisor_profile_id: UUID,
        period_days: int = 30
    ) -> dict:
        """Get statistics for assignments created/managed by a supervisor

        Args:
            db: Database connection
            supervisor_profile_id: UUID of the supervisor's agent_profile
            period_days: Number of days to look back

        Returns:
            Dict with supervisor statistics
        """
        query = """
            SELECT
                COUNT(*) FILTER (WHERE assignment_method = 'manual') as manual_assignments,
                COUNT(*) FILTER (WHERE assignment_method = 'auto') as auto_assignments,
                COUNT(*) FILTER (WHERE reassigned_at IS NOT NULL) as reassignments,
                COUNT(*) as total_assignments,
                COUNT(*) FILTER (WHERE status = 'completed') as completed_assignments,
                AVG(processing_duration_hours) FILTER (WHERE status = 'completed') as avg_processing_time
            FROM assignments
            WHERE assigned_by_profile_id = $1
            AND assigned_at >= NOW() - MAKE_INTERVAL(days => $2)
        """
        row = await db.fetchrow(query, supervisor_profile_id, period_days)

        return {
            "supervisor_profile_id": str(supervisor_profile_id),
            "period_days": period_days,
            "manual_assignments": row['manual_assignments'] or 0 if row else 0,
            "auto_assignments": row['auto_assignments'] or 0 if row else 0,
            "reassignments": row['reassignments'] or 0 if row else 0,
            "total_assignments": row['total_assignments'] or 0 if row else 0,
            "completed_assignments": row['completed_assignments'] or 0 if row else 0,
            "avg_processing_time_hours": float(row['avg_processing_time'] or 0) if row else 0.0,
        }


def get_assignment_repository(db=None) -> AssignmentRepository:
    """Dependency injection for AssignmentRepository"""
    return AssignmentRepository()
