"""
Assignment Service - Business logic for manual assignment operations

Based on DATABASE_SCHEMA_REFERENCE.md (2026-01-18):
- Table: assignments (Migration 053)
- Uses agent_profile_id instead of agent_id
- Uses item_id + item_type instead of declaration_id + declaration_type

Handles:
- Manual assignment of items to agents
- Reassignment with history tracking
- Assignment status updates
"""

from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta, timezone
from fastapi import Depends
from loguru import logger

from app.config import get_settings
from app.modules.assignment.models.assignment_history import (
    Assignment,
    AssignmentCreate,
    AssignmentUpdate,
    AssignmentStatus,
    AssignmentMethod,
    ReassignmentCreate,
    ReassignmentReason,
)
from app.modules.assignment.repositories.assignment_repository import (
    AssignmentRepository,
    get_assignment_repository,
)


class AssignmentService:
    """Service for manual assignment operations"""

    def __init__(self, repository: Optional[AssignmentRepository] = None):
        self.repository = repository or AssignmentRepository()
        logger.info("AssignmentService initialized")

    async def assign_to_agent(
        self,
        db,
        item_id: UUID,
        item_type: str,
        agent_profile_id: UUID,
        supervisor_id: Optional[UUID] = None,
        notes: Optional[str] = None,
        priority_level: int = 5,
        deadline_days: Optional[int] = None
    ) -> Assignment:
        """Manually assign an item to an agent

        Args:
            db: Database connection
            item_id: UUID of the item (tax_declaration, service_request, etc.)
            item_type: Type of item (declaration type or workflow code)
            agent_profile_id: UUID of the agent_profile to assign to
            supervisor_id: UUID of supervisor's agent_profile (optional)
            notes: Assignment notes
            priority_level: Priority 1-10 (default 5)
            deadline_days: Days until deadline (optional)
        """
        deadline = None
        if deadline_days:
            deadline = datetime.now(timezone.utc) + timedelta(days=deadline_days)

        data = AssignmentCreate(
            item_id=item_id,
            item_type=item_type,
            agent_profile_id=agent_profile_id,
            assignment_method=AssignmentMethod.MANUAL,
            priority_level=priority_level,
            notes=notes,
            deadline=deadline
        )

        assignment = await self.repository.create(db, data, supervisor_id)
        logger.info(f"Manual assignment created: {assignment.id} for item {item_id}")
        return assignment

    async def create_assignment(
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
        return await self.repository.create(db, data, assigned_by_profile_id)

    async def get_assignment(self, db, assignment_id: UUID) -> Optional[Assignment]:
        """Get assignment by ID"""
        return await self.repository.get_by_id(db, assignment_id)

    async def start_processing(self, db, assignment_id: UUID) -> Optional[Assignment]:
        """Start processing an assignment (assigned → in_progress)

        Args:
            db: Database connection
            assignment_id: UUID of the assignment
        """
        data = AssignmentUpdate(status=AssignmentStatus.IN_PROGRESS)
        assignment = await self.repository.update(db, assignment_id, data)
        if assignment:
            logger.info(f"Assignment {assignment_id} started processing")
        return assignment

    async def complete_assignment(
        self,
        db,
        assignment_id: UUID,
        validation_status: str,
        quality_score: Optional[float] = None
    ) -> Optional[Assignment]:
        """Complete an assignment

        Args:
            db: Database connection
            assignment_id: UUID of the assignment
            validation_status: "approved" or "rejected"
            quality_score: Quality score 0-10 (optional)
        """
        status = AssignmentStatus.COMPLETED if validation_status == "approved" else AssignmentStatus.REJECTED
        data = AssignmentUpdate(
            status=status,
            validation_status=validation_status,
            quality_score=quality_score
        )
        assignment = await self.repository.update(db, assignment_id, data)
        if assignment:
            logger.info(f"Assignment {assignment_id} completed with status: {validation_status}")
        return assignment

    async def update_assignment(
        self,
        db,
        assignment_id: UUID,
        data: AssignmentUpdate
    ) -> Optional[Assignment]:
        """Update assignment"""
        return await self.repository.update(db, assignment_id, data)

    async def reassign_to_new_agent(
        self,
        db,
        assignment_id: UUID,
        new_agent_profile_id: UUID,
        reason: ReassignmentReason,
        supervisor_id: UUID,
        notes: Optional[str] = None
    ) -> Optional[Assignment]:
        """Reassign item to another agent

        Args:
            db: Database connection
            assignment_id: UUID of the assignment to reassign
            new_agent_profile_id: UUID of the new agent's agent_profile
            reason: ReassignmentReason enum value
            supervisor_id: UUID of supervisor's agent_profile doing the reassignment
            notes: Reassignment notes (optional)
        """
        data = ReassignmentCreate(
            assignment_id=assignment_id,
            new_agent_profile_id=new_agent_profile_id,
            reason=reason,
            notes=notes
        )
        assignment = await self.repository.reassign(db, data, supervisor_id)
        if assignment:
            logger.info(f"Assignment {assignment_id} reassigned to {new_agent_profile_id}")
        return assignment

    async def reassign(
        self,
        db,
        data: ReassignmentCreate,
        reassigned_by_profile_id: UUID
    ) -> Optional[Assignment]:
        """Reassign using ReassignmentCreate model

        Args:
            db: Database connection
            data: ReassignmentCreate with assignment_id, new_agent_profile_id, reason
            reassigned_by_profile_id: UUID of supervisor's agent_profile
        """
        return await self.repository.reassign(db, data, reassigned_by_profile_id)

    async def cancel_assignment(self, db, assignment_id: UUID) -> Optional[Assignment]:
        """Cancel an assignment

        Args:
            db: Database connection
            assignment_id: UUID of the assignment to cancel
        """
        data = AssignmentUpdate(status=AssignmentStatus.CANCELLED)
        assignment = await self.repository.update(db, assignment_id, data)
        if assignment:
            logger.info(f"Assignment {assignment_id} cancelled")
        return assignment

    async def update_priority(
        self,
        db,
        assignment_id: UUID,
        priority_level: int
    ) -> Optional[Assignment]:
        """Update assignment priority

        Args:
            db: Database connection
            assignment_id: UUID of the assignment
            priority_level: New priority 1-10
        """
        data = AssignmentUpdate(priority_level=priority_level)
        assignment = await self.repository.update(db, assignment_id, data)
        if assignment:
            logger.info(f"Assignment {assignment_id} priority updated to {priority_level}")
        return assignment

    async def extend_deadline(
        self,
        db,
        assignment_id: UUID,
        additional_days: int
    ) -> Optional[Assignment]:
        """Extend assignment deadline

        Args:
            db: Database connection
            assignment_id: UUID of the assignment
            additional_days: Number of days to add to deadline
        """
        # Get current assignment to check deadline
        assignment = await self.repository.get_by_id(db, assignment_id)
        if not assignment:
            return None

        # Calculate new deadline
        current_deadline = assignment.deadline or datetime.now(timezone.utc)
        new_deadline = current_deadline + timedelta(days=additional_days)

        # Update via raw SQL since deadline isn't in AssignmentUpdate
        query = """
            UPDATE assignments
            SET deadline = $1, updated_at = NOW()
            WHERE id = $2
        """
        await db.execute(query, new_deadline, assignment_id)

        logger.info(f"Assignment {assignment_id} deadline extended by {additional_days} days")
        return await self.repository.get_by_id(db, assignment_id)

    async def update_notes(
        self,
        db,
        assignment_id: UUID,
        notes: str
    ) -> Optional[Assignment]:
        """Update assignment notes

        Args:
            db: Database connection
            assignment_id: UUID of the assignment
            notes: New notes content
        """
        data = AssignmentUpdate(notes=notes)
        assignment = await self.repository.update(db, assignment_id, data)
        if assignment:
            logger.info(f"Assignment {assignment_id} notes updated")
        return assignment

    async def list_assignments(
        self,
        db,
        agent_profile_id: Optional[UUID] = None,
        status: Optional[str] = None,
        item_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Assignment]:
        """List assignments with optional filters

        Args:
            db: Database connection
            agent_profile_id: Filter by agent_profile.id (optional)
            status: Filter by assignment status (optional)
            item_type: Filter by item type (optional)
            limit: Max results
            offset: Pagination offset
        """
        return await self.repository.list_all(
            db=db,
            agent_profile_id=agent_profile_id,
            status=status,
            item_type=item_type,
            limit=limit,
            offset=offset
        )

    def should_escalate(
        self,
        assignment: Assignment,
        current_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Check if an assignment should be escalated.

        Ported from legacy agents/services/assignment_service.py.
        Evaluates 3 escalation criteria using configurable thresholds:
        1. SLA deadline violation or approaching deadline
        2. Processing duration exceeding max hours
        3. Stuck in pending_review status too long

        Args:
            assignment: Assignment model instance
            current_time: Override for testing (defaults to now)

        Returns:
            {"should_escalate": bool, "reason": Optional[str], "urgency": str}
        """
        if current_time is None:
            current_time = datetime.now(timezone.utc)

        settings = get_settings()
        reasons: List[str] = []
        urgency = "normal"

        # 1. SLA deadline check
        if assignment.deadline:
            if current_time > assignment.deadline:
                reasons.append("SLA deadline violated")
                urgency = "critical"
            else:
                hours_remaining = (assignment.deadline - current_time).total_seconds() / 3600
                if hours_remaining < settings.ESCALATION_SLA_HIGH_HOURS:
                    reasons.append(f"Approaching SLA deadline ({hours_remaining:.1f}h remaining)")
                    if urgency != "critical":
                        urgency = "high"

        # 2. Processing duration check
        if assignment.started_at:
            hours_elapsed = (current_time - assignment.started_at).total_seconds() / 3600
            if hours_elapsed > settings.ESCALATION_PROCESSING_MAX_HOURS:
                reasons.append(f"Processing for {hours_elapsed:.1f} hours")
                if urgency != "critical":
                    urgency = "high"

        # 3. Stuck in pending_review
        if assignment.status == AssignmentStatus.PENDING_REVIEW and assignment.assigned_at:
            last_update = assignment.reassigned_at or assignment.assigned_at
            hours_pending = (current_time - last_update).total_seconds() / 3600
            if hours_pending > settings.ESCALATION_PENDING_REVIEW_MAX_HOURS:
                reasons.append(f"Pending review for {hours_pending:.1f} hours")
                if urgency != "critical":
                    urgency = "high"

        return {
            "should_escalate": len(reasons) > 0,
            "reason": "; ".join(reasons) if reasons else None,
            "urgency": urgency,
        }

    async def validate_reassignment(
        self,
        db,
        assignment_id: UUID,
        new_agent_profile_id: UUID,
        reason: ReassignmentReason,
    ) -> Dict[str, Any]:
        """Validate a reassignment request before executing it.

        Ported from legacy agents/services/assignment_service.py.
        Guards against:
        1. Reassigning completed/cancelled assignments
        2. Reassigning to the same agent
        3. Reassigning too soon (cooldown period)

        Args:
            db: Database connection
            assignment_id: UUID of the assignment
            new_agent_profile_id: Target agent_profile.id
            reason: ReassignmentReason enum value

        Returns:
            {"is_valid": bool, "errors": List[str]}
        """
        errors: List[str] = []

        assignment = await self.repository.get_by_id(db, assignment_id)
        if not assignment:
            return {"is_valid": False, "errors": ["Assignment not found"]}

        # Cannot reassign terminal statuses
        terminal = {AssignmentStatus.COMPLETED, AssignmentStatus.CANCELLED, AssignmentStatus.REJECTED}
        if assignment.status in terminal:
            errors.append(f"Cannot reassign assignment with status '{assignment.status.value}'")

        # Cannot reassign to the same agent
        if assignment.agent_profile_id == new_agent_profile_id:
            errors.append("Cannot reassign to the same agent")

        # Cooldown: prevent rapid reassignments
        settings = get_settings()
        if assignment.reassigned_at:
            hours_since = (datetime.now(timezone.utc) - assignment.reassigned_at).total_seconds() / 3600
            if hours_since < settings.REASSIGNMENT_COOLDOWN_HOURS:
                wait_minutes = int((settings.REASSIGNMENT_COOLDOWN_HOURS - hours_since) * 60)
                errors.append(
                    f"Assignment was recently reassigned (wait {wait_minutes} more minutes)"
                )

        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
        }


def get_assignment_service(
    repository: AssignmentRepository = Depends(get_assignment_repository)
) -> AssignmentService:
    """Dependency injection for AssignmentService"""
    return AssignmentService(repository)
