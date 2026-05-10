"""
Rules Repository - Data access for assignment rules

Based on DATABASE_SCHEMA_REFERENCE.md (2026-01-18):
- Table: assignment_rules
- Uses rule_status_enum (active, inactive, draft, archived)
- JSONB columns: conditions, actions
"""

from typing import Optional, List
from uuid import UUID
import json
from loguru import logger

from app.modules.assignment.models.assignment_rule import (
    AssignmentRule,
    AssignmentRuleCreate,
    AssignmentRuleUpdate,
    RuleStatus,
)


# All columns from assignment_rules table
RULE_COLUMNS = """
    id, name, description, entity_type, entity_id,
    conditions, actions, priority, status,
    times_applied, times_matched, successful_assignments, failed_assignments,
    success_rate, last_applied_at,
    created_by, created_at, updated_at, updated_by
"""


class RulesRepository:
    """Repository for assignment rules data operations"""

    def __init__(self, db=None):
        self._db = db

    def _process_row(self, row) -> dict:
        """Process DB row to handle JSONB fields"""
        if not row:
            return None
        data = dict(row)
        # JSONB fields are already parsed by asyncpg
        return data

    async def create(
        self,
        db,
        data: AssignmentRuleCreate,
        created_by: UUID
    ) -> AssignmentRule:
        """Create a new assignment rule

        Args:
            db: Database connection
            data: AssignmentRuleCreate with entity_type, conditions, actions
            created_by: UUID of the user creating the rule
        """
        query = f"""
            INSERT INTO assignment_rules
            (name, description, entity_type, entity_id, conditions, actions,
             priority, status, created_by)
            VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb, $7, $8, $9)
            RETURNING {RULE_COLUMNS}
        """
        row = await db.fetchrow(
            query,
            data.name,
            data.description,
            data.entity_type,
            data.entity_id,
            json.dumps(data.conditions),
            json.dumps(data.actions),
            data.priority,
            data.status.value,
            created_by
        )
        processed = self._process_row(row)
        return AssignmentRule(**processed) if processed else None

    async def get_by_id(self, db, rule_id: UUID) -> Optional[AssignmentRule]:
        """Get rule by ID"""
        query = f"""
            SELECT {RULE_COLUMNS}
            FROM assignment_rules
            WHERE id = $1
        """
        row = await db.fetchrow(query, rule_id)
        processed = self._process_row(row)
        return AssignmentRule(**processed) if processed else None

    async def get_active_rules(
        self,
        db,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None
    ) -> List[AssignmentRule]:
        """Get all active assignment rules

        Args:
            db: Database connection
            entity_type: Filter by entity type (optional)
            entity_id: Filter by entity ID (optional)
        """
        conditions = ["status = 'active'"]
        values = []
        param_count = 1

        if entity_type:
            conditions.append(f"entity_type = ${param_count}")
            values.append(entity_type)
            param_count += 1

        if entity_id:
            conditions.append(f"entity_id = ${param_count}")
            values.append(entity_id)
            param_count += 1

        where_clause = " AND ".join(conditions)

        query = f"""
            SELECT {RULE_COLUMNS}
            FROM assignment_rules
            WHERE {where_clause}
            ORDER BY priority DESC
        """
        rows = await db.fetch(query, *values)
        return [AssignmentRule(**self._process_row(row)) for row in rows]

    async def list_all(
        self,
        db,
        entity_type: Optional[str] = None,
        status: Optional[RuleStatus] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[AssignmentRule]:
        """List all assignment rules with filters

        Args:
            db: Database connection
            entity_type: Filter by entity type (optional)
            status: Filter by status (optional)
            limit: Max results
            offset: Pagination offset
        """
        conditions = []
        values = []
        param_count = 1

        if entity_type:
            conditions.append(f"entity_type = ${param_count}")
            values.append(entity_type)
            param_count += 1

        if status:
            conditions.append(f"status = ${param_count}")
            values.append(status.value)
            param_count += 1

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        values.extend([limit, offset])
        query = f"""
            SELECT {RULE_COLUMNS}
            FROM assignment_rules
            {where_clause}
            ORDER BY priority DESC, created_at DESC
            LIMIT ${param_count} OFFSET ${param_count + 1}
        """
        rows = await db.fetch(query, *values)
        return [AssignmentRule(**self._process_row(row)) for row in rows]

    async def update(
        self,
        db,
        rule_id: UUID,
        data: AssignmentRuleUpdate,
        updated_by: UUID
    ) -> Optional[AssignmentRule]:
        """Update an assignment rule

        Args:
            db: Database connection
            rule_id: UUID of the rule to update
            data: AssignmentRuleUpdate with fields to update
            updated_by: UUID of the user updating the rule
        """
        updates = []
        values = []
        param_count = 1

        if data.name is not None:
            updates.append(f"name = ${param_count}")
            values.append(data.name)
            param_count += 1

        if data.description is not None:
            updates.append(f"description = ${param_count}")
            values.append(data.description)
            param_count += 1

        if data.entity_type is not None:
            updates.append(f"entity_type = ${param_count}")
            values.append(data.entity_type)
            param_count += 1

        if data.entity_id is not None:
            updates.append(f"entity_id = ${param_count}")
            values.append(data.entity_id)
            param_count += 1

        if data.conditions is not None:
            updates.append(f"conditions = ${param_count}::jsonb")
            values.append(json.dumps(data.conditions))
            param_count += 1

        if data.actions is not None:
            updates.append(f"actions = ${param_count}::jsonb")
            values.append(json.dumps(data.actions))
            param_count += 1

        if data.priority is not None:
            updates.append(f"priority = ${param_count}")
            values.append(data.priority)
            param_count += 1

        if data.status is not None:
            updates.append(f"status = ${param_count}")
            values.append(data.status.value)
            param_count += 1

        if not updates:
            return await self.get_by_id(db, rule_id)

        updates.append("updated_at = NOW()")
        updates.append(f"updated_by = ${param_count}")
        values.append(updated_by)
        param_count += 1

        values.append(rule_id)

        query = f"""
            UPDATE assignment_rules
            SET {', '.join(updates)}
            WHERE id = ${param_count}
            RETURNING {RULE_COLUMNS}
        """
        row = await db.fetchrow(query, *values)
        processed = self._process_row(row)
        return AssignmentRule(**processed) if processed else None

    async def increment_stats(
        self,
        db,
        rule_id: UUID,
        matched: bool,
        successful: bool
    ) -> None:
        """Increment rule statistics after evaluation

        Args:
            db: Database connection
            rule_id: UUID of the rule
            matched: Whether the rule conditions matched
            successful: Whether the assignment was successful
        """
        query = """
            UPDATE assignment_rules
            SET times_applied = times_applied + 1,
                times_matched = times_matched + CASE WHEN $2 THEN 1 ELSE 0 END,
                successful_assignments = successful_assignments + CASE WHEN $3 THEN 1 ELSE 0 END,
                failed_assignments = failed_assignments + CASE WHEN NOT $3 AND $2 THEN 1 ELSE 0 END,
                success_rate = CASE
                    WHEN (successful_assignments + failed_assignments + 1) > 0
                    THEN (successful_assignments + CASE WHEN $3 THEN 1 ELSE 0 END)::numeric /
                         (successful_assignments + failed_assignments + 1)
                    ELSE 0
                END,
                last_applied_at = NOW(),
                updated_at = NOW()
            WHERE id = $1
        """
        await db.execute(query, rule_id, matched, successful)

    async def get_all(
        self,
        db=None,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        status: Optional[RuleStatus] = None,
        order_by_priority: bool = True,
        limit: int = 100,
        offset: int = 0
    ) -> List[AssignmentRule]:
        """Get all assignment rules with filters (used by supervisor_routes)

        Args:
            db: Database connection (falls back to self._db)
            entity_type: Filter by entity type (optional)
            entity_id: Filter by entity ID (optional)
            status: Filter by status (optional)
            order_by_priority: Sort by priority DESC (default True)
            limit: Max results
            offset: Pagination offset
        """
        conn = db or self._db
        conditions = []
        values = []
        param_count = 1

        if entity_type:
            conditions.append(f"entity_type = ${param_count}")
            values.append(entity_type)
            param_count += 1

        if entity_id:
            conditions.append(f"entity_id = ${param_count}")
            values.append(str(entity_id))
            param_count += 1

        if status:
            conditions.append(f"status = ${param_count}")
            values.append(status.value if hasattr(status, 'value') else str(status))
            param_count += 1

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        order = "ORDER BY priority DESC, created_at DESC" if order_by_priority else "ORDER BY created_at DESC"

        values.extend([limit, offset])
        query = f"""
            SELECT {RULE_COLUMNS}
            FROM assignment_rules
            {where_clause}
            {order}
            LIMIT ${param_count} OFFSET ${param_count + 1}
        """
        rows = await conn.fetch(query, *values)
        return [AssignmentRule(**self._process_row(row)) for row in rows]

    async def count(
        self,
        db=None,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        status: Optional[RuleStatus] = None,
    ) -> int:
        """Count assignment rules with same filters as get_all()"""
        conn = db or self._db
        conditions = []
        values = []
        param_count = 1

        if entity_type:
            conditions.append(f"entity_type = ${param_count}")
            values.append(entity_type)
            param_count += 1

        if entity_id:
            conditions.append(f"entity_id = ${param_count}")
            values.append(str(entity_id))
            param_count += 1

        if status:
            conditions.append(f"status = ${param_count}")
            values.append(status.value if hasattr(status, 'value') else str(status))
            param_count += 1

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        query = f"SELECT COUNT(*) FROM assignment_rules {where_clause}"
        return await conn.fetchval(query, *values)

    async def activate(self, db=None, rule_id: UUID = None) -> Optional[AssignmentRule]:
        """Activate a rule (draft/inactive → active)"""
        conn = db or self._db
        # Accept positional: activate(db, rule_id) or activate(rule_id)
        if rule_id is None and db is not None and isinstance(db, UUID):
            rule_id = db
            conn = self._db
        query = f"""
            UPDATE assignment_rules
            SET status = 'active',
                updated_at = NOW()
            WHERE id = $1
            RETURNING {RULE_COLUMNS}
        """
        row = await conn.fetchrow(query, rule_id)
        processed = self._process_row(row)
        return AssignmentRule(**processed) if processed else None

    async def deactivate(self, db=None, rule_id: UUID = None) -> Optional[AssignmentRule]:
        """Deactivate a rule (active → inactive)"""
        conn = db or self._db
        # Accept positional: deactivate(db, rule_id) or deactivate(rule_id)
        if rule_id is None and db is not None and isinstance(db, UUID):
            rule_id = db
            conn = self._db
        query = f"""
            UPDATE assignment_rules
            SET status = 'inactive',
                updated_at = NOW()
            WHERE id = $1
            RETURNING {RULE_COLUMNS}
        """
        row = await conn.fetchrow(query, rule_id)
        processed = self._process_row(row)
        return AssignmentRule(**processed) if processed else None

    async def delete(self, db, rule_id: UUID) -> bool:
        """Delete an assignment rule (hard delete)"""
        query = "DELETE FROM assignment_rules WHERE id = $1"
        result = await db.execute(query, rule_id)
        return result == "DELETE 1"

    async def archive(self, db, rule_id: UUID, updated_by: UUID) -> Optional[AssignmentRule]:
        """Archive a rule (soft delete via status)

        Args:
            db: Database connection
            rule_id: UUID of the rule to archive
            updated_by: UUID of the user archiving the rule
        """
        query = f"""
            UPDATE assignment_rules
            SET status = 'archived',
                updated_at = NOW(),
                updated_by = $2
            WHERE id = $1
            RETURNING {RULE_COLUMNS}
        """
        row = await db.fetchrow(query, rule_id, updated_by)
        processed = self._process_row(row)
        return AssignmentRule(**processed) if processed else None

    async def get_effectiveness_report(
        self,
        entity_type: Optional[str] = None,
        min_times_applied: int = 10,
        db=None,
    ) -> List[dict]:
        """Get rule effectiveness report sorted by score DESC.

        Returns rows with: id, name, priority, times_applied, times_matched,
        success_rate, effectiveness_score (success_rate*100), application_rate
        ((times_applied/times_matched)*100), last_applied_at.

        Filters:
        - status = 'active' (skip archived/inactive)
        - times_applied >= min_times_applied
        - entity_type if provided

        Used by GET /api/v1/supervisor/rules/effectiveness/report.
        """
        conn = db or self._db
        params: list = [min_times_applied]
        entity_filter = ""
        if entity_type:
            entity_filter = f"AND entity_type = ${len(params) + 1}"
            params.append(entity_type)

        query = f"""
            SELECT
                id,
                name,
                priority,
                times_applied,
                times_matched,
                COALESCE(success_rate, 0) AS success_rate,
                (COALESCE(success_rate, 0) * 100) AS effectiveness_score,
                CASE
                    WHEN times_matched > 0
                        THEN (times_applied::numeric / times_matched) * 100
                    ELSE 0
                END AS application_rate,
                last_applied_at
            FROM assignment_rules
            WHERE status = 'active'
              AND times_applied >= $1
              {entity_filter}
            ORDER BY effectiveness_score DESC, times_applied DESC
        """
        rows = await conn.fetch(query, *params)
        return [dict(row) for row in rows]


def get_rules_repository(db=None) -> RulesRepository:
    """Dependency injection for RulesRepository"""
    return RulesRepository(db=db)
