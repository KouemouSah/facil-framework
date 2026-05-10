"""
Pydantic models for batch_requests.
Aligned with database schema from migration 100.
"""
from decimal import Decimal
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from enum import Enum


# === Enums ===

class BatchStatus(str, Enum):
    """Status for a batch request."""
    DRAFT = "DRAFT"
    UPLOADING = "UPLOADING"
    CLASSIFYING = "CLASSIFYING"
    REVIEW = "REVIEW"
    PAYMENT_PENDING = "PAYMENT_PENDING"
    PAID = "PAID"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"


class BatchItemStatus(str, Enum):
    """Status for a batch request item (beneficiary)."""
    PENDING = "PENDING"
    DOCUMENTS_ASSIGNED = "DOCUMENTS_ASSIGNED"
    REVIEW = "REVIEW"
    READY = "READY"
    SUBMITTED = "SUBMITTED"
    EXCLUDED = "EXCLUDED"


# Allowed status transitions for citizen PATCH (non-terminal only)
CITIZEN_ALLOWED_STATUS_TRANSITIONS: Dict[str, List[str]] = {
    "DRAFT": ["UPLOADING"],
    "UPLOADING": ["REVIEW"],
    "REVIEW": ["UPLOADING"],  # go back to add more docs
}


# === Request Models ===

class BatchRequestCreate(BaseModel):
    """Create a new batch request."""
    workflow_code: str = Field(..., min_length=1, max_length=100)
    solicitud_type: str = Field(default="expedicion", max_length=50)

    @field_validator("workflow_code")
    @classmethod
    def validate_workflow_code(cls, v: str) -> str:
        """Validate workflow_code exists in registered workflows."""
        from app.modules.service_requests.services.workflow_engine import workflow_engine
        code = v.strip().upper()
        if not code:
            raise ValueError("workflow_code cannot be empty")
        wf = workflow_engine.get_workflow_by_string(code)
        if not wf:
            raise ValueError(f"Unknown workflow_code: {code}")
        return code
    company_id: Optional[UUID] = Field(None, description="Optional company ID")
    entity_code: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = None


class BatchRequestUpdate(BaseModel):
    """Update a batch request (citizen-facing: notes + entity_code only)."""
    notes: Optional[str] = None
    entity_code: Optional[str] = None


class BatchRequestItemCreate(BaseModel):
    """Add a beneficiary to a batch."""
    beneficiary_name: str = Field(..., min_length=1, max_length=255)
    beneficiary_identifier: Optional[str] = Field(None, max_length=100)
    beneficiary_identifier_type: Optional[str] = Field(None, max_length=50)
    beneficiary_email: Optional[str] = Field(None, max_length=255)
    beneficiary_phone: Optional[str] = Field(None, max_length=50)
    conditions: Dict[str, Any] = Field(default_factory=dict)
    item_order: Optional[int] = None


class BatchRequestItemUpdate(BaseModel):
    """Update a beneficiary item."""
    beneficiary_name: Optional[str] = Field(None, max_length=255)
    beneficiary_identifier: Optional[str] = Field(None, max_length=100)
    beneficiary_identifier_type: Optional[str] = Field(None, max_length=50)
    beneficiary_email: Optional[str] = Field(None, max_length=255)
    beneficiary_phone: Optional[str] = Field(None, max_length=50)
    conditions: Optional[Dict[str, Any]] = None
    form_data: Optional[Dict[str, Any]] = None
    status: Optional[BatchItemStatus] = None
    item_amount: Optional[Decimal] = None


class BatchItemsBulkCreate(BaseModel):
    """Add multiple beneficiaries at once."""
    items: List[BatchRequestItemCreate] = Field(..., min_length=1, max_length=500)


# === Response Models ===

class BatchRequestItemResponse(BaseModel):
    """Response for a single batch item (beneficiary)."""
    id: UUID
    batch_id: UUID

    # Beneficiary
    beneficiary_name: str
    beneficiary_identifier: Optional[str] = None
    beneficiary_identifier_type: Optional[str] = None
    beneficiary_email: Optional[str] = None
    beneficiary_phone: Optional[str] = None

    # Status
    status: BatchItemStatus
    service_request_id: Optional[UUID] = None

    # Documents
    assigned_documents: List[Dict[str, Any]] = Field(default_factory=list)
    required_documents: List[str] = Field(default_factory=list)
    missing_documents: List[str] = Field(default_factory=list)

    # Conditions & data
    conditions: Dict[str, Any] = Field(default_factory=dict)
    form_data: Dict[str, Any] = Field(default_factory=dict)

    # Amount
    item_amount: Optional[Decimal] = None

    # Validation
    validation_errors: List[Dict[str, Any]] = Field(default_factory=list)

    item_order: int = 0
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class BatchRequestResponse(BaseModel):
    """Complete response for a batch request."""
    id: UUID
    reference: Optional[str] = None
    submitted_by: UUID
    company_id: Optional[UUID] = None
    workflow_code: str
    solicitud_type: str
    entity_code: Optional[str] = None

    # Counts
    total_items: int = 0
    items_ready: int = 0
    items_submitted: int = 0
    items_completed: int = 0

    # Status
    status: BatchStatus

    # Shared documents
    shared_documents: List[Dict[str, Any]] = Field(default_factory=list)

    # Payment (Decimal for precision)
    per_item_amount: Optional[Decimal] = None
    total_amount: Optional[Decimal] = None
    currency: str = "XAF"

    # Timestamps
    created_at: datetime
    updated_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    notes: Optional[str] = None

    class Config:
        from_attributes = True


class BatchRequestDetailResponse(BatchRequestResponse):
    """Batch response with items included."""
    items: List[BatchRequestItemResponse] = Field(default_factory=list)


class BatchRequestListResponse(BaseModel):
    """Paginated list response for batch requests."""
    batches: List[BatchRequestResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# === Agent-facing Response Models ===

class AgentBatchItemResponse(BatchRequestItemResponse):
    """Extends item with live service_request status for agent views."""
    sr_status: Optional[str] = None
    sr_reference: Optional[str] = None
    sr_assigned_to: Optional[str] = None
    sr_payment_status: Optional[str] = None


class AgentBatchDetailResponse(BatchRequestResponse):
    """Batch detail for agents, with items including live SR status."""
    items: List[AgentBatchItemResponse] = Field(default_factory=list)
    submitted_by_name: Optional[str] = None
    submitted_by_email: Optional[str] = None


class BulkDecisionRequest(BaseModel):
    """Request body for bulk approve/reject."""
    decision: str = Field(..., pattern="^(approve|reject)$")
    item_ids: Optional[List[UUID]] = None  # If None, applies to all pending items
    comments: Optional[str] = None
    rejection_reason: Optional[str] = None


class BulkDecisionResponse(BaseModel):
    """Response for bulk decision."""
    processed: int = 0
    failed: int = 0
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    batch_completed: bool = False
