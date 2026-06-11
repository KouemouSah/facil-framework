"""
Ministry Agents Models - Agent management, assignments, and workload

Based on DATABASE_SCHEMA_REFERENCE.md tables:
- ministry_agents
- agent_work_queue
- assignments
- agent_performance_stats
- agent_workloads
"""

from typing import Optional, List, Dict, Any, Union
from uuid import UUID
from pydantic import BaseModel, Field, field_validator
from datetime import datetime, time, date
from enum import Enum
from decimal import Decimal
import json


# ============================================================================
# ENUMS (from DATABASE_SCHEMA_REFERENCE.md)
# ============================================================================

class AgentActionType(str, Enum):
    """Agent actions in the system"""
    LOCK_FOR_REVIEW = "lock_for_review"
    APPROVE = "approve"
    REJECT = "reject"
    REQUEST_DOCUMENTS = "request_documents"
    ADD_COMMENT = "add_comment"
    ESCALATE = "escalate"
    UNLOCK_RELEASE = "unlock_release"
    ASSIGN_TO_COLLEAGUE = "assign_to_colleague"


class AgentAvailability(str, Enum):
    """Agent availability status"""
    AVAILABLE = "available"
    ON_LEAVE = "on_leave"
    SICK_LEAVE = "sick_leave"
    TRAINING = "training"
    MISSION = "mission"
    TEMPORARILY_UNAVAILABLE = "temporarily_unavailable"


class AssignmentMethod(str, Enum):
    """How the assignment was made"""
    AUTO = "auto"
    MANUAL = "manual"
    SELF_ASSIGNED = "self_assigned"
    ESCALATED = "escalated"


class AssignmentStatus(str, Enum):
    """Assignment status"""
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    PENDING_REVIEW = "pending_review"
    COMPLETED = "completed"
    REASSIGNED = "reassigned"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class ReassignmentReason(str, Enum):
    """Reason for reassignment"""
    WORKLOAD_IMBALANCE = "workload_imbalance"
    AGENT_UNAVAILABLE = "agent_unavailable"
    SPECIALIZATION_MISMATCH = "specialization_mismatch"
    QUALITY_ISSUE = "quality_issue"
    DEADLINE_MISSED = "deadline_missed"
    AGENT_REQUEST = "agent_request"
    SUPERVISOR_DECISION = "supervisor_decision"
    COMPLEXITY_CHANGE = "complexity_change"


class WorkloadStatus(str, Enum):
    """Agent workload status"""
    AVAILABLE = "available"
    NORMAL = "normal"
    BUSY = "busy"
    OVERLOADED = "overloaded"
    UNAVAILABLE = "unavailable"


# ============================================================================
# MINISTRY_AGENTS - Agent configuration and permissions
# ============================================================================

class MinistryAgentBase(BaseModel):
    """Base ministry agent fields (legacy - ministry_agents table dropped)"""
    user_id: str
    ministry_id: int
    can_approve_unlimited: bool = False
    max_approval_amount: Optional[Decimal] = None
    can_escalate: bool = True
    can_assign_tasks: bool = False
    is_active: bool = True
    is_backup_agent: bool = False
    backup_for_agent_id: Optional[str] = None
    working_hours_start: Optional[time] = None
    working_hours_end: Optional[time] = None
    working_days: Optional[List[str]] = Field(default_factory=list)


class MinistryAgentCreate(MinistryAgentBase):
    """Create ministry agent"""
    assigned_by: Optional[str] = None


class MinistryAgentUpdate(BaseModel):
    """Update ministry agent (legacy - ministry_agents table dropped)"""
    can_approve_unlimited: Optional[bool] = None
    max_approval_amount: Optional[Decimal] = None
    can_escalate: Optional[bool] = None
    can_assign_tasks: Optional[bool] = None
    is_active: Optional[bool] = None
    is_backup_agent: Optional[bool] = None
    backup_for_agent_id: Optional[str] = None
    working_hours_start: Optional[time] = None
    working_hours_end: Optional[time] = None
    working_days: Optional[List[str]] = None


class MinistryAgentResponse(MinistryAgentBase):
    """Ministry agent response"""
    id: str
    assigned_at: datetime
    assigned_by: Optional[str] = None
    deactivated_at: Optional[datetime] = None
    deactivated_by: Optional[str] = None
    deactivation_reason: Optional[str] = None

    class Config:
        from_attributes = True


class MinistryAgent(MinistryAgentResponse):
    """Full ministry agent model"""
    pass


# ============================================================================
# AGENT_WORK_QUEUE - Task queue with SLA tracking
# ============================================================================

class AgentWorkQueueBase(BaseModel):
    """Base work queue fields.

    Routing: entity_code (primary, migration 131).
    ministry_id: nullable legacy field kept for backward compat.
    """
    item_type: str
    item_id: str
    entity_code: Optional[str] = None
    ministry_id: Optional[int] = None
    amount: Optional[Decimal] = None
    declaration_type: Optional[str] = None
    priority_score: Decimal = Decimal("0")
    sla_deadline: Optional[datetime] = None
    assigned_to: Optional[str] = None
    escalated: bool = False
    escalated_at: Optional[datetime] = None
    escalated_by: Optional[str] = None
    escalation_reason: Optional[str] = None
    status: str = "pending"


class AgentWorkQueueCreate(AgentWorkQueueBase):
    """Create work queue item"""
    pass


class AgentWorkQueueResponse(AgentWorkQueueBase):
    """Work queue response"""
    id: str
    sla_status: Optional[str] = None
    assigned_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    completed_by: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AgentWorkQueue(AgentWorkQueueResponse):
    """Full work queue model"""
    pass


# ============================================================================
# ASSIGNMENTS - Assignment history and tracking
# ============================================================================

class AssignmentBase(BaseModel):
    """Base assignment fields"""
    declaration_id: str
    declaration_type: str
    agent_id: str
    assigned_by: Optional[str] = None
    assignment_method: AssignmentMethod = AssignmentMethod.AUTO
    status: AssignmentStatus = AssignmentStatus.ASSIGNED
    notes: Optional[str] = None
    auto_assignment_score: Optional[Decimal] = None
    score_breakdown: Optional[Dict[str, Any]] = None
    rule_applied_id: Optional[str] = None
    deadline: Optional[datetime] = None
    priority_level: Optional[str] = None


class AssignmentCreate(AssignmentBase):
    """Create assignment"""
    pass


class AssignmentUpdate(BaseModel):
    """Update assignment"""
    status: Optional[AssignmentStatus] = None
    notes: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    reassigned_to: Optional[str] = None
    reassignment_reason: Optional[ReassignmentReason] = None
    reassignment_notes: Optional[str] = None
    validation_status: Optional[str] = None
    quality_score: Optional[Decimal] = None


class AssignmentResponse(AssignmentBase):
    """Assignment response"""
    id: str
    assigned_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    processing_duration_hours: Optional[Decimal] = None
    deadline_met: Optional[bool] = None
    reassigned_to: Optional[str] = None
    reassigned_at: Optional[datetime] = None
    reassignment_reason: Optional[ReassignmentReason] = None
    reassignment_notes: Optional[str] = None
    validation_status: Optional[str] = None
    quality_score: Optional[Decimal] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class Assignment(AssignmentResponse):
    """Full assignment model"""
    pass


# ============================================================================
# AGENT_PERFORMANCE_STATS - Performance metrics
# ============================================================================

class AgentPerformanceStats(BaseModel):
    """Agent performance statistics"""
    agent_id: int
    ministry_id: int
    current_month_processed: int = 0
    current_month_approved: int = 0
    current_month_rejected: int = 0
    current_month_escalated: int = 0
    avg_processing_minutes: Optional[Decimal] = None
    avg_lock_duration_minutes: Optional[Decimal] = None
    sla_respected_count: int = 0
    sla_missed_count: int = 0
    sla_respect_percentage: Optional[Decimal] = None
    current_active_locks: int = 0
    max_concurrent_locks: int = 0
    last_action_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None
    stats_period_start: date = Field(default_factory=date.today)
    stats_period_end: Optional[date] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True


# ============================================================================
# AGENT_WORKLOADS - Real-time workload tracking
# ============================================================================

class AgentWorkloadBase(BaseModel):
    """Base workload fields"""
    current_assignments: int = 0
    pending_declarations: int = 0
    in_progress_declarations: int = 0
    max_concurrent_assignments: int = 20
    capacity_percentage: Decimal = Decimal("0.00")
    workload_status: WorkloadStatus = WorkloadStatus.AVAILABLE
    availability: AgentAvailability = AgentAvailability.AVAILABLE
    availability_reason: Optional[str] = None
    unavailable_until: Optional[datetime] = None


class AgentWorkloadUpdate(BaseModel):
    """Update agent workload"""
    current_assignments: Optional[int] = None
    pending_declarations: Optional[int] = None
    in_progress_declarations: Optional[int] = None
    max_concurrent_assignments: Optional[int] = None
    capacity_percentage: Optional[Decimal] = None
    workload_status: Optional[WorkloadStatus] = None
    availability: Optional[AgentAvailability] = None
    availability_reason: Optional[str] = None
    unavailable_until: Optional[datetime] = None
    active_specializations: Optional[List[str]] = None
    preferred_declaration_types: Optional[List[str]] = None


class AgentWorkload(AgentWorkloadBase):
    """Full agent workload model.

    Note: The database uses agent_profile_id (UUID) as the primary identifier
    since migration 054. The legacy agent_id column may still exist for
    backward compatibility.
    """
    id: Union[str, UUID]
    # Primary identifier (migration 054+)
    agent_profile_id: Optional[Union[str, UUID]] = None
    # Legacy field (kept for backward compatibility)
    agent_id: Optional[Union[str, UUID]] = None
    avg_processing_time_hours: Optional[Decimal] = None
    avg_daily_completions: Decimal = Decimal("0.00")
    completion_rate_7d: Decimal = Decimal("0.00")
    quality_score_avg: Decimal = Decimal("0.00")
    success_rate: Decimal = Decimal("0.0000")
    deadline_compliance_rate: Decimal = Decimal("0.0000")
    active_specializations: List[str] = Field(default_factory=list)
    preferred_declaration_types: List[str] = Field(default_factory=list)
    oldest_pending_assignment_date: Optional[datetime] = None
    avg_pending_duration_hours: Optional[Decimal] = None
    last_assignment_at: Optional[datetime] = None
    last_completion_at: Optional[datetime] = None
    last_updated_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator('active_specializations', 'preferred_declaration_types', mode='before')
    @classmethod
    def parse_jsonb_lists(cls, v):
        """Handle JSONB columns that may come as strings from asyncpg."""
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return []
        return v if v is not None else []

    class Config:
        from_attributes = True


# ============================================================================
# ADMIN ALERTS DASHBOARD
# ============================================================================

class AdminAlertsDashboard(BaseModel):
    """Aggregated alerts for the admin agents dashboard."""
    inactive_count: int = 0
    overloaded_count: int = 0
    stale_locks_count: int = 0
    sla_at_risk_count: int = 0
    total_alerts: int = 0
    inactive_agents: Optional[List[Dict[str, Any]]] = None
    overloaded_agents: Optional[List[Dict[str, Any]]] = None
    stale_locks: Optional[List[Dict[str, Any]]] = None
    sla_at_risk: Optional[List[Dict[str, Any]]] = None
    workload_by_entity: Optional[List[Dict[str, Any]]] = None
    llm_briefing: Optional[str] = None
    llm_priority: str = "normal"
