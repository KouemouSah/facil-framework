"""
Assignment History Models - Pydantic schemas for assignment tracking

Based on DATABASE_SCHEMA_REFERENCE.md (2026-01-18):
- Table: assignments (unified, Migration 053)
- Uses agent_profile_id, item_id, item_type (Migration 053/054)
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from uuid import UUID


class AssignmentStatus(str, Enum):
    """Assignment status enum - aligned with assignment_status_enum in DB"""
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    PENDING_REVIEW = "pending_review"
    COMPLETED = "completed"
    REASSIGNED = "reassigned"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class AssignmentMethod(str, Enum):
    """Assignment method enum - aligned with assignment_method_enum in DB"""
    AUTO = "auto"
    MANUAL = "manual"
    SELF_ASSIGNED = "self_assigned"
    ESCALATED = "escalated"


class ReassignmentReason(str, Enum):
    """Reason for reassignment - aligned with reassignment_reason_enum in DB

    DB values (from DATABASE_SCHEMA_REFERENCE.md):
    workload_imbalance, agent_unavailable, specialization_mismatch,
    quality_issue, deadline_missed, agent_request, supervisor_decision, complexity_change
    """
    WORKLOAD_IMBALANCE = "workload_imbalance"
    AGENT_UNAVAILABLE = "agent_unavailable"
    SPECIALIZATION_MISMATCH = "specialization_mismatch"
    QUALITY_ISSUE = "quality_issue"
    DEADLINE_MISSED = "deadline_missed"
    AGENT_REQUEST = "agent_request"
    SUPERVISOR_DECISION = "supervisor_decision"
    COMPLEXITY_CHANGE = "complexity_change"


class AssignmentCreate(BaseModel):
    """Create assignment request - aligned with assignments table"""
    item_id: UUID = Field(..., description="UUID of the item (tax_declaration, service_request, etc.)")
    item_type: str = Field(..., description="Type: declaration type or workflow code")
    agent_profile_id: UUID = Field(..., description="Reference to agent_profiles.id")
    assignment_method: AssignmentMethod = Field(AssignmentMethod.MANUAL, description="How was this assigned")
    priority_level: int = Field(default=5, ge=1, le=10, description="Priority 1-10")
    notes: Optional[str] = None
    deadline: Optional[datetime] = None


class AssignmentUpdate(BaseModel):
    """Update assignment request"""
    status: Optional[AssignmentStatus] = None
    priority_level: Optional[int] = Field(None, ge=1, le=10)
    notes: Optional[str] = None
    validation_status: Optional[str] = None
    quality_score: Optional[float] = None


class Assignment(BaseModel):
    """Assignment response model - aligned with assignments table"""
    id: UUID
    item_id: UUID = Field(..., description="UUID of the assigned item")
    item_type: str = Field(..., description="Type of item (declaration type or workflow code)")
    agent_profile_id: UUID = Field(..., description="Reference to agent_profiles.id")
    agent_name: Optional[str] = Field(None, description="Joined: agent full name")
    assigned_by_profile_id: Optional[UUID] = Field(None, description="Supervisor who assigned")
    assigned_by_name: Optional[str] = Field(None, description="Joined: assigner full name")
    assignment_method: AssignmentMethod = AssignmentMethod.MANUAL
    status: AssignmentStatus
    priority_level: int = Field(5, description="Priority 1-10")
    assigned_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    processing_duration_hours: Optional[float] = None
    deadline: Optional[datetime] = None
    deadline_met: Optional[bool] = None
    notes: Optional[str] = None
    validation_status: Optional[str] = None
    quality_score: Optional[float] = None
    # Auto-assignment scoring
    auto_assignment_score: Optional[float] = None
    rule_applied_id: Optional[UUID] = None
    # Reassignment fields
    reassigned_at: Optional[datetime] = None
    reassignment_reason: Optional[ReassignmentReason] = None
    reassignment_notes: Optional[str] = None
    reassigned_to_profile_id: Optional[UUID] = None
    reassigned_to_name: Optional[str] = Field(None, description="Joined: reassignee full name")
    # Audit timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ReassignmentCreate(BaseModel):
    """Reassignment request - uses agent_profile_id"""
    assignment_id: UUID
    new_agent_profile_id: UUID = Field(..., description="Reference to agent_profiles.id")
    reason: ReassignmentReason
    notes: Optional[str] = None


class AssignmentStats(BaseModel):
    """Assignment statistics"""
    total_assignments: int = 0
    pending_count: int = 0
    in_progress_count: int = 0
    completed_count: int = 0
    average_processing_time_hours: Optional[float] = None


class AssignmentBulkReassign(BaseModel):
    """Bulk reassignment request - uses agent_profile_id"""
    assignment_ids: List[UUID]
    new_agent_profile_id: UUID = Field(..., description="Reference to agent_profiles.id")
    reason: ReassignmentReason
    notes: Optional[str] = None


class BulkReassignResult(BaseModel):
    """Bulk reassignment result"""
    successful: int = 0
    failed: int = 0
    errors: List[Dict[str, Any]] = []


class AgentAssignmentStats(BaseModel):
    """Agent assignment statistics - computed from assignments table

    This is a response model for agent performance metrics,
    computed via aggregations on the assignments table.
    """
    agent_profile_id: UUID = Field(..., description="Reference to agent_profiles.id")
    period_days: int = Field(..., description="Number of days for the statistics period")
    total_assignments: int = 0
    completed_assignments: int = 0
    pending_assignments: int = 0
    rejected_assignments: int = 0
    avg_processing_time_hours: float = 0.0
    success_rate: float = 0.0
    quality_score_avg: float = 0.0
    deadline_compliance_rate: float = 0.0
    by_status: Dict[str, int] = Field(default_factory=dict, description="Count by assignment status")
    by_type: Dict[str, int] = Field(default_factory=dict, description="Count by item_type")
