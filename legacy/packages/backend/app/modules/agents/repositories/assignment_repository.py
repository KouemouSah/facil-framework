"""Assignment Repository - Data access for assignments and work queue"""

from typing import Optional, List, Dict, Any
from loguru import logger
import asyncpg
from datetime import datetime, timedelta, timezone

from app.modules.agents.models import (
    AssignmentCreate,
    AssignmentUpdate,
    AssignmentStatus,
)


class AssignmentRepository:
    """Repository for assignments and agent work queue"""

    # ========================================================================
    # ASSIGNMENTS
    # ========================================================================

    async def create_assignment(
        self,
        conn: asyncpg.Connection,
        assignment: AssignmentCreate,
    ) -> Dict[str, Any]:
        """Create new assignment.
        LEGACY: Uses old model fields. Modern: assignment/ module.
        """
        query = """
            INSERT INTO assignments (
                item_id, item_type, agent_profile_id, assigned_by_profile_id,
                assignment_method, status, notes, auto_assignment_score,
                score_breakdown, rule_applied_id, deadline, priority_level,
                assigned_at, created_at, updated_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, NOW(), NOW(), NOW())
            RETURNING *
        """
        result = await conn.fetchrow(
            query,
            assignment.declaration_id,
            assignment.declaration_type,
            assignment.agent_id,
            assignment.assigned_by,
            assignment.assignment_method.value,
            assignment.status.value,
            assignment.notes,
            assignment.auto_assignment_score,
            assignment.score_breakdown,
            assignment.rule_applied_id,
            assignment.deadline,
            assignment.priority_level,
        )
        return dict(result)

    async def get_assignment_by_id(
        self,
        conn: asyncpg.Connection,
        assignment_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get assignment by ID"""
        query = """
            SELECT * FROM assignments WHERE id = $1
        """
        result = await conn.fetchrow(query, assignment_id)
        return dict(result) if result else None

    async def get_assignments_by_item(
        self,
        conn: asyncpg.Connection,
        item_id: str,
    ) -> List[Dict[str, Any]]:
        """Get all assignments for an item (service request).
        LEGACY: Modern: assignment/ module.
        """
        query = """
            SELECT * FROM assignments
            WHERE item_id = $1
            ORDER BY assigned_at DESC
        """
        results = await conn.fetch(query, item_id)
        return [dict(r) for r in results]

    async def get_assignments_by_agent(
        self,
        conn: asyncpg.Connection,
        agent_id: str,
        status: Optional[AssignmentStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[List[Dict[str, Any]], int]:
        """Get assignments for an agent"""
        where_clause = "WHERE agent_profile_id = $1"
        params = [agent_id]

        if status:
            where_clause += " AND status = $2"
            params.append(status.value)

        count_query = f"SELECT COUNT(*) FROM assignments {where_clause}"
        total = await conn.fetchval(count_query, *params)

        data_query = f"""
            SELECT * FROM assignments
            {where_clause}
            ORDER BY assigned_at DESC
            LIMIT ${len(params) + 1} OFFSET ${len(params) + 2}
        """
        params.extend([limit, offset])
        results = await conn.fetch(data_query, *params)
        return [dict(r) for r in results], total

    async def update_assignment(
        self,
        conn: asyncpg.Connection,
        assignment_id: str,
        update_data: AssignmentUpdate,
    ) -> Optional[Dict[str, Any]]:
        """Update assignment"""
        updates = []
        params = [assignment_id]
        param_idx = 2

        for field, value in update_data.dict(exclude_unset=True).items():
            if value is not None:
                if field == "status" or field == "reassignment_reason":
                    value = value.value if hasattr(value, "value") else value
                updates.append(f"{field} = ${param_idx}")
                params.append(value)
                param_idx += 1

        if not updates:
            return await self.get_assignment_by_id(conn, assignment_id)

        updates.append(f"updated_at = ${param_idx}")
        params.append(datetime.now(timezone.utc))

        query = f"""
            UPDATE assignments
            SET {', '.join(updates)}
            WHERE id = $1
            RETURNING *
        """
        result = await conn.fetchrow(query, *params)
        return dict(result) if result else None

    async def reassign(
        self,
        conn: asyncpg.Connection,
        assignment_id: str,
        new_agent_id: str,
        reason: str,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Reassign to another agent"""
        query = """
            UPDATE assignments
            SET status = 'reassigned',
                reassigned_to_profile_id = $2,
                reassigned_at = NOW(),
                reassignment_reason = $3,
                reassignment_notes = $4,
                updated_at = NOW()
            WHERE id = $1
            RETURNING *
        """
        result = await conn.fetchrow(query, assignment_id, new_agent_id, reason, notes)
        return dict(result)

    async def complete_assignment(
        self,
        conn: asyncpg.Connection,
        assignment_id: str,
        quality_score: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Mark assignment as completed"""
        query = """
            UPDATE assignments
            SET status = 'completed',
                completed_at = NOW(),
                processing_duration_hours = EXTRACT(EPOCH FROM (NOW() - started_at)) / 3600,
                deadline_met = (NOW() <= deadline),
                quality_score = $2,
                updated_at = NOW()
            WHERE id = $1
            RETURNING *
        """
        result = await conn.fetchrow(query, assignment_id, quality_score)
        return dict(result)

    # ========================================================================
    # AGENT WORK QUEUE — COMMENTED OUT (migration to entity_code routing)
    # ========================================================================
    # These methods are superseded by:
    #   - service_requests: agent_queue_service.py (entity_code routing)
    #   - assignments: assignment/ module (entity_id routing)
    # See migrations 131-133.
    #
    # KNOWN ISSUES in this code:
    #   - add_to_queue() uses ministry_id (now nullable, entity_code is primary)
    #   - get_next_queue_items() filters by ministry_id (should use entity_code)
    #   - get_sla_violations() has SQL INJECTION (f-string interpolation line 324)
    #   - escalate_queue_item() uses hardcoded +10 (should use ESCALATION_BOOST)
    #
    # DO NOT UNCOMMENT without fixing these issues first.

    # async def add_to_queue(
    #     self,
    #     conn: asyncpg.Connection,
    #     queue_item: AgentWorkQueueCreate,
    # ) -> Dict[str, Any]:
    #     """Add item to work queue.
    #     DEPRECATED: Uses ministry_id. Modern: agent_queue_service.add_to_queue()
    #     """
    #     query = """
    #         INSERT INTO agent_work_queue (
    #             item_type, item_id, ministry_id, amount, declaration_type,
    #             priority_score, sla_deadline, assigned_to, escalated,
    #             escalated_at, escalated_by, escalation_reason, status,
    #             created_at, updated_at
    #         )
    #         VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, NOW(), NOW())
    #         RETURNING *
    #     """
    #     result = await conn.fetchrow(
    #         query,
    #         queue_item.item_type,
    #         queue_item.item_id,
    #         queue_item.ministry_id,
    #         queue_item.amount,
    #         queue_item.declaration_type,
    #         queue_item.priority_score,
    #         queue_item.sla_deadline,
    #         queue_item.assigned_to,
    #         queue_item.escalated,
    #         queue_item.escalated_at,
    #         queue_item.escalated_by,
    #         queue_item.escalation_reason,
    #         queue_item.status,
    #     )
    #     return dict(result)

    # async def get_queue_item(
    #     self,
    #     conn: asyncpg.Connection,
    #     queue_id: str,
    # ) -> Optional[Dict[str, Any]]:
    #     """Get queue item by ID.
    #     DEPRECATED: Modern: agent_queue_service._get_queue_item()
    #     """
    #     query = """
    #         SELECT * FROM agent_work_queue WHERE id = $1
    #     """
    #     result = await conn.fetchrow(query, queue_id)
    #     return dict(result) if result else None

    # async def get_next_queue_items(
    #     self,
    #     conn: asyncpg.Connection,
    #     ministry_id: int,
    #     limit: int = 10,
    # ) -> List[Dict[str, Any]]:
    #     """Get next items from queue (highest priority, oldest first).
    #     DEPRECATED: Filters by ministry_id. Modern: agent_queue_service.get_pending_items()
    #     """
    #     query = """
    #         SELECT * FROM agent_work_queue
    #         WHERE ministry_id = $1
    #           AND status = 'pending'
    #         ORDER BY priority_score DESC, created_at ASC
    #         LIMIT $2
    #     """
    #     results = await conn.fetch(query, ministry_id, limit)
    #     return [dict(r) for r in results]

    # async def assign_queue_item(
    #     self,
    #     conn: asyncpg.Connection,
    #     queue_id: str,
    #     agent_id: str,
    # ) -> Dict[str, Any]:
    #     """Assign queue item to agent.
    #     DEPRECATED: Modern uses auto-assignment via outbox pattern.
    #     """
    #     query = """
    #         UPDATE agent_work_queue
    #         SET assigned_to = $2,
    #             assigned_at = NOW(),
    #             status = 'assigned',
    #             updated_at = NOW()
    #         WHERE id = $1
    #         RETURNING *
    #     """
    #     result = await conn.fetchrow(query, queue_id, agent_id)
    #     return dict(result)

    # async def complete_queue_item(
    #     self,
    #     conn: asyncpg.Connection,
    #     queue_id: str,
    #     completed_by: str,
    # ) -> Dict[str, Any]:
    #     """Mark queue item as completed.
    #     DEPRECATED: Modern: agent_queue_service.complete_item()
    #     """
    #     query = """
    #         UPDATE agent_work_queue
    #         SET status = 'completed',
    #             completed_at = NOW(),
    #             completed_by = $2,
    #             updated_at = NOW()
    #         WHERE id = $1
    #         RETURNING *
    #     """
    #     result = await conn.fetchrow(query, queue_id, completed_by)
    #     return dict(result)

    # async def escalate_queue_item(
    #     self,
    #     conn: asyncpg.Connection,
    #     queue_id: str,
    #     escalated_by: str,
    #     reason: str,
    # ) -> Dict[str, Any]:
    #     """Escalate queue item.
    #     DEPRECATED: Modern: agent_queue_service.escalate_item()
    #     Uses hardcoded +10 instead of ESCALATION_BOOST from settings.
    #     """
    #     query = """
    #         UPDATE agent_work_queue
    #         SET escalated = true,
    #             escalated_at = NOW(),
    #             escalated_by = $2,
    #             escalation_reason = $3,
    #             priority_score = priority_score + 10,
    #             updated_at = NOW()
    #         WHERE id = $1
    #         RETURNING *
    #     """
    #     result = await conn.fetchrow(query, queue_id, escalated_by, reason)
    #     return dict(result)

    # async def get_sla_violations(
    #     self,
    #     conn: asyncpg.Connection,
    #     ministry_id: Optional[int] = None,
    # ) -> List[Dict[str, Any]]:
    #     """Get items with SLA violations.
    #     DEPRECATED: Modern: agent_queue_service.get_queue_stats() (sla_violations count)
    #     BUG: SQL INJECTION via f-string on ministry_id (line below).
    #     """
    #     where_clause = "WHERE sla_deadline < NOW() AND status NOT IN ('completed', 'cancelled')"
    #     if ministry_id:
    #         # BUG: SQL injection — should use parameterized query
    #         where_clause += f" AND ministry_id = {ministry_id}"
    #
    #     query = f"""
    #         SELECT * FROM agent_work_queue
    #         {where_clause}
    #         ORDER BY sla_deadline ASC
    #     """
    #     results = await conn.fetch(query)
    #     return [dict(r) for r in results]
