"""
Pydantic models for service request history/audit trail.

Provides models for:
- History entry representation
- History list responses with pagination
- Filtering options for history queries
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class HistoryActionType(str, Enum):
    """
    Types of actions recorded in service_request_history.
    Must match values used in repository INSERT statements.
    Includes consolidated entries from OCR logs and assignments.
    """
    # Status changes
    STATUS_CHANGE = "status_change"
    STATUS_CORRECTION = "status_correction"

    # Document actions
    DOCUMENT_ADDED = "document_added"
    DOCUMENT_REMOVED = "document_removed"

    # OCR processing (from gemini_processing_logs)
    OCR_COMPLETED = "ocr_completed"
    OCR_FAILED = "ocr_failed"

    # Assignment actions (from assignments table)
    ASSIGNED = "assigned"
    REASSIGNED = "reassigned"

    # Appointment actions
    CITA_SCHEDULED = "cita_scheduled"
    CITA_RESCHEDULED = "cita_rescheduled"
    CITA_CANCELLED = "cita_cancelled"

    # Verification
    VERIFICATION_UPDATED = "verification_updated"

    # Agent actions
    AGENT_ACTION = "agent_action_taken"

    # Payment actions
    PAYMENT_INITIATED = "payment_initiated"
    PAYMENT_RECEIVED = "payment_received"
    PAYMENT_FAILED = "payment_failed"

    # Communication
    COMMENT_ADDED = "comment_added"

    # Validation (for audit trail)
    VALIDATION_FAILED = "validation_failed"
    VALIDATION_BLOCKED = "validation_blocked"

    # Escalation actions
    ESCALATED = "escalated"
    ESCALATION_RESOLVED = "escalation_resolved"
    ESCALATION_ASSIGNED = "escalation_assigned"
    SUPERVISOR_APPROVE = "supervisor_approve"
    SUPERVISOR_REJECT = "supervisor_reject"
    ESCALATION_SLA_ESCALATED = "escalation_sla_escalated"
    ESCALATION_SLA_EXPIRED = "escalation_sla_expired"


class HistoryEntrySource(str, Enum):
    """
    Source table of the history entry.
    Used to track where consolidated data came from.
    """
    HISTORY = "history"       # service_request_history table
    OCR = "ocr"               # gemini_processing_logs table
    ASSIGNMENT = "assignment" # assignments table


class HistoryActionSource(str, Enum):
    """
    Source/origin of the history action.
    Helps distinguish user actions from system actions.
    """
    USER = "user"           # Citizen-initiated action
    AGENT = "agent"         # Agent-initiated action
    SYSTEM = "system"       # Automatic workflow transition
    WEBHOOK = "webhook"     # External webhook (payment, etc.)
    MIGRATION = "migration" # Data correction/migration


class PerformerInfo(BaseModel):
    """Information about who performed the action."""
    user_id: Optional[UUID] = Field(None, description="User ID if action was user-initiated")
    full_name: Optional[str] = Field(None, description="User's full name")
    email: Optional[str] = Field(None, description="User's email")
    role: Optional[str] = Field(None, description="User's role (citizen, agent, admin)")
    is_system: bool = Field(False, description="True if action was system-initiated")

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "full_name": "María López García",
                "email": "maria.lopez@cnedoge.gq",
                "role": "agent",
                "is_system": False
            }
        }


class HistoryEntry(BaseModel):
    """
    Single entry in the service request history timeline.
    Represents one action/event that occurred on the request.
    """
    id: UUID = Field(..., description="Unique history entry ID")
    action: HistoryActionType = Field(..., description="Type of action performed")
    action_source: Optional[HistoryActionSource] = Field(
        None,
        description="Source of the action (user, agent, system)"
    )
    source: Optional[HistoryEntrySource] = Field(
        None,
        description="Data source table (history, ocr, assignment)"
    )

    # Status transition (for status_change actions)
    previous_status: Optional[str] = Field(None, description="Status before the change")
    new_status: Optional[str] = Field(None, description="Status after the change")

    # Action details
    details: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional details specific to the action type"
    )
    comment: Optional[str] = Field(None, description="Comment or note added with the action")

    # Performer information
    performed_by: Optional[PerformerInfo] = Field(
        None,
        description="Who performed the action (null for system actions)"
    )
    performed_at: datetime = Field(..., description="When the action was performed")

    # Context (optional)
    ip_address: Optional[str] = Field(None, description="IP address of the request")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174001",
                "action": "status_change",
                "action_source": "agent",
                "previous_status": "SUBMITTED",
                "new_status": "UNDER_REVIEW",
                "details": {},
                "comment": "Dossier pris en charge",
                "performed_by": {
                    "user_id": "123e4567-e89b-12d3-a456-426614174000",
                    "full_name": "María López",
                    "role": "agent"
                },
                "performed_at": "2026-01-27T14:30:00Z"
            }
        }


class DocumentHistoryEntry(BaseModel):
    """
    Document-related history entry with OCR details.
    Extended from HistoryEntry for document actions.
    """
    id: UUID
    action: HistoryActionType  # document_added, document_removed
    document_code: str = Field(..., description="Document type code (e.g., DIP_ANVERSO)")
    document_name: str = Field(..., description="Human-readable document name")
    file_name: Optional[str] = Field(None, description="Original filename")

    # OCR extraction details (from gemini_processing_logs)
    extraction_confidence: Optional[float] = Field(
        None,
        ge=0, le=1,
        description="OCR confidence score (0-1)"
    )
    extraction_status: Optional[str] = Field(None, description="success, failed, manual_review")
    risk_score: Optional[float] = Field(None, ge=0, le=1, description="Risk score if analyzed")
    risk_factors: Optional[List[str]] = Field(None, description="Risk factors detected")

    performed_by: Optional[PerformerInfo] = None
    performed_at: datetime


class AssignmentHistoryEntry(BaseModel):
    """
    Assignment-related history entry.
    Tracks agent assignments and reassignments.
    """
    id: UUID
    action: HistoryActionType  # assigned, reassigned

    # Assignment details
    assigned_to: Optional[PerformerInfo] = Field(None, description="Agent assigned to")
    assigned_from: Optional[PerformerInfo] = Field(None, description="Previous agent (for reassignment)")
    assignment_method: Optional[str] = Field(
        None,
        description="auto, manual, self_assigned, escalated"
    )
    reassignment_reason: Optional[str] = Field(None, description="Reason for reassignment")

    performed_by: Optional[PerformerInfo] = None
    performed_at: datetime


class HistoryFilters(BaseModel):
    """Filters for querying history entries."""
    action_types: Optional[List[HistoryActionType]] = Field(
        None,
        description="Filter by action types"
    )
    from_date: Optional[datetime] = Field(None, description="Start date (inclusive)")
    to_date: Optional[datetime] = Field(None, description="End date (inclusive)")
    performed_by: Optional[UUID] = Field(None, description="Filter by performer user ID")
    include_system: bool = Field(True, description="Include system-initiated actions")


class HistoryListResponse(BaseModel):
    """
    Response for service request history endpoint.
    Contains the timeline of all events for a request.
    """
    request_id: UUID = Field(..., description="Service request ID")
    reference: str = Field(..., description="Request reference number")
    workflow_code: str = Field(..., description="Workflow type code")
    solicitud_type: Optional[str] = Field(None, description="Request type (expedicion, renovacion)")
    citizen_name: str = Field(..., description="Citizen's full name")
    current_status: str = Field(..., description="Current status of the request")

    # Timeline entries
    entries: List[HistoryEntry] = Field(
        default_factory=list,
        description="History entries ordered by date DESC"
    )

    # Pagination
    total: int = Field(..., description="Total number of history entries")
    page: int = Field(1, description="Current page number")
    page_size: int = Field(50, description="Entries per page")

    # Summary statistics
    total_status_changes: int = Field(0, description="Number of status changes")
    total_documents: int = Field(0, description="Number of documents added")
    total_assignments: int = Field(0, description="Number of (re)assignments")
    first_action_at: Optional[datetime] = Field(None, description="Date of first action")
    last_action_at: Optional[datetime] = Field(None, description="Date of most recent action")

    class Config:
        json_schema_extra = {
            "example": {
                "request_id": "123e4567-e89b-12d3-a456-426614174000",
                "reference": "SR-2026-001234",
                "workflow_code": "PASAPORTE_NUEVO",
                "solicitud_type": "expedicion",
                "citizen_name": "Juan García Pérez",
                "current_status": "UNDER_REVIEW",
                "entries": [],
                "total": 15,
                "page": 1,
                "page_size": 50,
                "total_status_changes": 5,
                "total_documents": 4,
                "total_assignments": 2,
                "first_action_at": "2026-01-20T10:00:00Z",
                "last_action_at": "2026-01-27T14:30:00Z"
            }
        }


class HistorySummaryItem(BaseModel):
    """
    Summary item for the history list page.
    Shows minimal info for each request with history.
    """
    request_id: UUID
    reference: str
    workflow_code: str
    citizen_name: str
    current_status: str

    # Summary
    last_action: HistoryActionType
    last_action_at: datetime
    last_performer: Optional[str] = Field(None, description="Name of last performer")
    total_actions: int = Field(0, description="Total history entries")

    # Quick stats
    days_since_created: int = Field(0, description="Days since request creation")
    is_stale: bool = Field(False, description="True if no action in 7+ days")


class HistoryListSummaryResponse(BaseModel):
    """
    Response for the history list page (multiple requests).
    Used by /agent/service-requests/history endpoint.
    """
    items: List[HistorySummaryItem] = Field(default_factory=list)
    total: int = Field(0)
    page: int = Field(1)
    page_size: int = Field(20)

    # Filters applied
    workflow_codes: Optional[List[str]] = Field(None)
    status_filter: Optional[str] = Field(None)
