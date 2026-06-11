"""
Service Payment Models.

Models for payments associated with service_requests (passport, residence, etc.).
Uses the service_payments table with agent workflow support.
"""

from pydantic import BaseModel, Field, computed_field
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal
from enum import Enum

from .payment import PaymentMethod, PaymentStatus


# =============================================================================
# HELPER: Supplement extraction from calculation_details JSON
# =============================================================================

def extract_supplements_amount(calculation_details: Optional[Dict[str, Any]]) -> Decimal:
    """Extract supplements_total from calculation_details JSON."""
    if calculation_details:
        return Decimal(str(calculation_details.get("supplements_total", 0)))
    return Decimal("0")


def extract_supplements_list(calculation_details: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extract supplements array from calculation_details JSON."""
    if calculation_details:
        return calculation_details.get("supplements", [])
    return []


class PaymentWorkflowStatus(str, Enum):
    """
    Workflow status for payments requiring agent review.
    Must match database enum: payment_workflow_status (15 values)

    Note: locked_by_agent was removed - with auto-assignment architecture,
    agents only see their assigned payments, so locking is obsolete.
    """
    # Initial states
    SUBMITTED = "submitted"
    AUTO_PROCESSING = "auto_processing"
    AUTO_APPROVED = "auto_approved"

    # Agent review states
    PENDING_AGENT_REVIEW = "pending_agent_review"
    AGENT_REVIEWING = "agent_reviewing"

    # Document states
    REQUIRES_DOCUMENTS = "requires_documents"
    DOCS_RESUBMITTED = "docs_resubmitted"

    # Resolution states
    APPROVED_BY_AGENT = "approved_by_agent"
    REJECTED_BY_AGENT = "rejected_by_agent"

    # Escalation states
    ESCALATED_SUPERVISOR = "escalated_supervisor"
    SUPERVISOR_REVIEWING = "supervisor_reviewing"

    # Terminal states
    COMPLETED = "completed"
    CANCELLED_BY_USER = "cancelled_by_user"
    CANCELLED_BY_AGENT = "cancelled_by_agent"
    EXPIRED = "expired"


class ServicePaymentBase(BaseModel):
    """Base model for service payments."""

    # Identifier - links to service_request
    service_request_id: str = Field(
        ...,
        description="FK to service_requests (required)"
    )

    user_id: str = Field(..., description="User UUID")
    company_id: Optional[str] = Field(None, description="Company UUID if applicable")

    # Payment details
    payment_method: PaymentMethod = Field(..., description="Payment method")
    payment_type: str = Field(default="full", description="full, partial, installment")
    base_amount: Decimal = Field(..., ge=0, description="Base amount before fees")
    penalties: Decimal = Field(default=Decimal("0"), ge=0)
    discounts: Decimal = Field(default=Decimal("0"), ge=0)
    total_amount: Decimal = Field(..., ge=0, description="Final amount to pay")
    currency: str = Field(default="XAF")


class ServicePaymentCreate(BaseModel):
    """Model for creating a service payment."""

    service_request_id: str = Field(..., description="Service request UUID")
    user_id: str = Field(..., description="User UUID")
    payment_method: PaymentMethod = Field(..., description="Payment method")
    total_amount: Decimal = Field(..., ge=0, description="Amount to pay")
    currency: str = Field(default="XAF")

    # Optional
    company_id: Optional[str] = None
    payment_type: str = Field(default="full")


class ServicePaymentResponse(BaseModel):
    """Response model for service payments."""

    id: str = Field(..., description="Payment UUID")
    payment_reference: str = Field(..., description="Unique payment reference")

    # Target
    service_request_id: Optional[str] = None

    # User
    user_id: str
    user_email: Optional[str] = None
    user_name: Optional[str] = None

    # Amounts
    payment_method: PaymentMethod
    payment_type: str
    base_amount: Decimal
    penalties: Decimal = Decimal("0")
    discounts: Decimal = Decimal("0")
    total_amount: Decimal
    currency: str = "XAF"

    # Tariff breakdown (from TariffBreakdown stored as JSONB)
    calculation_details: Optional[Dict[str, Any]] = Field(
        None,
        description="Itemized tariff breakdown: base_amount, supplements[], penalties, total"
    )

    # Computed fields for supplements (extracted from calculation_details)
    @computed_field
    @property
    def supplements_amount(self) -> Decimal:
        """Total supplements amount extracted from calculation_details JSON."""
        return extract_supplements_amount(self.calculation_details)

    @computed_field
    @property
    def supplements(self) -> List[Dict[str, Any]]:
        """List of supplements extracted from calculation_details JSON."""
        return extract_supplements_list(self.calculation_details)

    # Batch reference (if created from a batch submission)
    batch_id: Optional[str] = None

    # Status
    status: PaymentStatus
    workflow_status: PaymentWorkflowStatus

    # Gateway integration (BANGE, Ecobank, etc.)
    gateway_transaction_id: Optional[str] = None

    # Agent workflow
    requires_agent_validation: bool = False
    # UUID-based agent profile references
    validated_by_agent_id: Optional[str] = None
    validated_at: Optional[datetime] = None
    validation_comment: Optional[str] = None

    # Receipt
    receipt_number: Optional[str] = None
    receipt_url: Optional[str] = None

    # Timestamps
    paid_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ServicePaymentListResponse(BaseModel):
    """List response for service payments."""

    payments: List[ServicePaymentResponse]
    total: int
    page: int
    page_size: int


class PendingValidationResponse(BaseModel):
    """Response model for Treasury dashboard - pending validations."""

    payment_id: str
    payment_reference: str
    service_request_id: Optional[str] = None
    request_reference: Optional[str] = None
    workflow_code: Optional[str] = None

    # User
    user_id: str
    user_name: Optional[str] = None
    user_email: Optional[str] = None

    # Payment
    payment_method: PaymentMethod
    total_amount: Decimal
    currency: str = "XAF"

    # Tariff breakdown for agent review (itemized details)
    calculation_details: Optional[Dict[str, Any]] = Field(
        None,
        description="Itemized tariff breakdown: base_amount, supplements[], penalties, total"
    )

    # Computed fields for supplements (extracted from calculation_details)
    @computed_field
    @property
    def supplements_amount(self) -> Decimal:
        """Total supplements amount extracted from calculation_details JSON."""
        return extract_supplements_amount(self.calculation_details)

    @computed_field
    @property
    def supplements(self) -> List[Dict[str, Any]]:
        """List of supplements extracted from calculation_details JSON."""
        return extract_supplements_list(self.calculation_details)

    # Status
    workflow_status: PaymentWorkflowStatus

    # SLA tracking
    sla_target_date: Optional[datetime] = None
    submitted_at: Optional[datetime] = None

    # Timing
    created_at: datetime
    hours_waiting: float = Field(..., description="Hours since payment was created")


class PaymentValidationRequest(BaseModel):
    """Request model for agent validation."""

    comment: Optional[str] = Field(None, max_length=500, description="Validation comment")


class PaymentRejectionRequest(BaseModel):
    """Request model for agent rejection."""

    reason: str = Field(..., min_length=10, max_length=500, description="Rejection reason")


class PaymentLockRequest(BaseModel):
    """Request model for agent lock."""

    duration_minutes: int = Field(
        default=15,
        ge=5,
        le=60,
        description="Lock duration in minutes (5-60)"
    )
