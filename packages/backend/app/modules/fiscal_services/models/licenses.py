"""Commercial Licenses Models — Pydantic v2 models for OMS (Obligation Management System).

3 tables:
  - commercial_licenses (annual dossier)
  - license_obligations (1 per bundle item per license)
  - license_compliance_events (append-only audit trail)
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from enum import Enum

from pydantic import BaseModel, Field, ConfigDict, field_validator


# ============================================================
# Enums
# ============================================================

class LicenseStatus(str, Enum):
    """License dossier lifecycle status."""
    open = "open"
    partial = "partial"
    complete = "complete"
    overdue = "overdue"
    suspended = "suspended"
    closed = "closed"


class ObligationStatus(str, Enum):
    """Individual obligation lifecycle status."""
    pending = "pending"
    selected = "selected"
    payment_pending = "payment_pending"
    paid = "paid"
    processing = "processing"
    completed = "completed"
    overdue = "overdue"
    waived = "waived"
    cancelled = "cancelled"


class ComplianceEventType(str, Enum):
    """Compliance event types for audit trail."""
    license_created = "license_created"
    obligation_created = "obligation_created"
    payment_initiated = "payment_initiated"
    payment_validated = "payment_validated"
    obligation_routed = "obligation_routed"
    agent_approved = "agent_approved"
    agent_rejected = "agent_rejected"
    document_issued = "document_issued"
    obligation_completed = "obligation_completed"
    overdue_flagged = "overdue_flagged"
    penalty_applied = "penalty_applied"
    reminder_sent = "reminder_sent"
    license_completed = "license_completed"
    license_renewed = "license_renewed"
    license_suspended = "license_suspended"
    config_changed = "config_changed"
    waived = "waived"


class ProcessingMode(str, Enum):
    """License processing mode (snapshot from bundle at creation)."""
    per_line = "per_line"
    consolidated = "consolidated"


# ============================================================
# Request Models — commercial_licenses
# ============================================================

class LicenseCreate(BaseModel):
    """Create a commercial license dossier.

    total_amount, obligations_total, deadline are computed by the service
    from the bundle configuration — NOT supplied by the client.
    """
    company_id: UUID
    bundle_id: UUID
    zone_id: UUID
    city_id: Optional[UUID] = None
    fiscal_year: int = Field(..., ge=2020, le=2100)
    service_request_id: Optional[UUID] = None


class LicenseUpdate(BaseModel):
    """Update a license dossier (admin: status changes only).

    Counter fields (amount_paid, obligations_paid, etc.) are managed
    exclusively by the service layer via update_license_counters().
    """
    status: LicenseStatus


class LicenseRenewRequest(BaseModel):
    """Renew a license for a new fiscal year."""
    fiscal_year: int = Field(..., ge=2020, le=2100)


# ============================================================
# Request Models — license_obligations
# ============================================================

class ObligationStatusUpdate(BaseModel):
    """Update obligation status (used by payment + agent workflows)."""
    status: ObligationStatus
    payment_id: Optional[UUID] = None
    paid_at: Optional[datetime] = None
    user_document_id: Optional[UUID] = None
    issued_document_id: Optional[UUID] = None
    penalty_amount: Optional[Decimal] = Field(None, ge=0)


class BatchObligationStatusUpdate(BaseModel):
    """Batch update multiple obligations at once (e.g., grouped payment)."""
    obligation_ids: List[UUID] = Field(..., min_length=1, max_length=200)
    status: ObligationStatus
    payment_id: Optional[UUID] = None
    paid_at: Optional[datetime] = None

    @field_validator("obligation_ids")
    @classmethod
    def unique_ids(cls, v: List[UUID]) -> List[UUID]:
        if len(v) != len(set(v)):
            raise ValueError("Duplicate obligation IDs")
        return v


# ============================================================
# Response Models — commercial_licenses
# ============================================================

class LicenseResponse(BaseModel):
    """Full license dossier response."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    service_request_id: Optional[UUID] = None
    bundle_id: UUID
    zone_id: UUID
    city_id: Optional[UUID] = None
    fiscal_year: int
    processing_mode: str

    total_amount: Decimal
    amount_paid: Decimal
    penalty_amount: Decimal

    obligations_total: int
    obligations_paid: int
    obligations_overdue: int
    compliance_score: Optional[Decimal] = None

    status: str
    deadline: Optional[date] = None
    opened_at: datetime
    completed_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None

    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    # Enriched (from JOINs)
    company_name: Optional[str] = None
    company_nif: Optional[str] = None
    company_registration_number: Optional[str] = None
    bundle_name: Optional[str] = None
    zone_code: Optional[str] = None


class LicenseSummary(BaseModel):
    """Lightweight license for list views."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    fiscal_year: int
    status: str
    total_amount: Decimal
    amount_paid: Decimal
    compliance_score: Optional[Decimal] = None
    obligations_total: int
    obligations_paid: int
    deadline: Optional[date] = None

    # Enriched
    company_name: Optional[str] = None
    company_nif: Optional[str] = None
    company_registration_number: Optional[str] = None
    bundle_name: Optional[str] = None
    zone_code: Optional[str] = None


class LicenseListResponse(BaseModel):
    """Paginated list of licenses."""
    items: List[LicenseSummary]
    total: int
    page: int
    page_size: int


# ============================================================
# Response Models — license_obligations
# ============================================================

class ObligationResponse(BaseModel):
    """Full obligation response."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    license_id: UUID
    bundle_item_id: UUID
    fiscal_service_id: int
    ministry_id: Optional[int] = None
    fee_type: str

    amount: Decimal
    penalty_amount: Decimal
    due_date: Optional[date] = None

    penalty_config: Optional[Dict] = None
    deadline_config: Optional[Dict] = None

    @field_validator("penalty_config", "deadline_config", mode="before")
    @classmethod
    def parse_jsonb_config(cls, v):
        if isinstance(v, str):
            import json
            try:
                return json.loads(v)
            except (json.JSONDecodeError, ValueError):
                return None
        return v

    @field_validator("penalty_config", "deadline_config", mode="before")
    @classmethod
    def parse_jsonb_config(cls, v):
        """Handle JSONB stored as string by asyncpg."""
        if isinstance(v, str):
            import json
            try:
                return json.loads(v)
            except (json.JSONDecodeError, ValueError):
                return None
        return v

    status: str
    payment_id: Optional[UUID] = None
    paid_at: Optional[datetime] = None

    user_document_id: Optional[UUID] = None
    issued_document_id: Optional[UUID] = None

    previous_year_paid: Optional[bool] = None
    previous_year_checked_at: Optional[datetime] = None

    created_at: datetime
    updated_at: datetime

    # Enriched (from JOINs)
    service_name: Optional[str] = None
    service_code: Optional[str] = None
    ministry_name: Optional[str] = None


class ObligationListResponse(BaseModel):
    """Paginated list of obligations with server-side aggregated KPIs.

    KPIs are computed from ALL matching obligations (not just the current page),
    so the frontend can display accurate totals regardless of pagination.
    """
    items: List[ObligationResponse]
    total: int
    page: int
    page_size: int
    # Server-side KPIs — aggregated from ALL matching obligations (no page_size limit)
    total_amount: Decimal = Decimal("0")
    paid_amount: Decimal = Decimal("0")
    penalty_amount: Decimal = Decimal("0")
    paid_count: int = 0
    pending_count: int = 0
    overdue_count: int = 0


# ============================================================
# Response Models — license_compliance_events
# ============================================================

class ComplianceEventResponse(BaseModel):
    """Compliance event response."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    license_id: UUID
    obligation_id: Optional[UUID] = None
    event_type: str
    event_data: Optional[Dict] = None
    triggered_by: Optional[UUID] = None
    created_at: datetime


class ComplianceEventListResponse(BaseModel):
    """Paginated list of compliance events."""
    items: List[ComplianceEventResponse]
    total: int
    page: int
    page_size: int


# ============================================================
# OMS Agent Queue Models
# ============================================================

class AgentQueueItem(BaseModel):
    """Single obligation in agent's processing queue."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    license_id: UUID
    bundle_item_id: UUID
    fiscal_service_id: int
    ministry_id: Optional[int] = None
    fee_type: str

    amount: Decimal
    penalty_amount: Decimal = Decimal("0")
    due_date: Optional[date] = None
    status: str
    created_at: datetime

    # Enriched (from JOINs)
    service_name: Optional[str] = None
    service_code: Optional[str] = None
    ministry_name: Optional[str] = None
    company_name: Optional[str] = None
    company_nif: Optional[str] = None
    company_registration_number: Optional[str] = None
    fiscal_year: Optional[int] = None
    zone_code: Optional[str] = None
    processing_mode: Optional[str] = None


class AgentQueueResponse(BaseModel):
    """Paginated agent queue."""
    items: List[AgentQueueItem]
    total: int
    page: int
    page_size: int


class AgentQueueStats(BaseModel):
    """Agent OMS dashboard stats."""
    pending_count: int = 0
    completed_today: int = 0
    total_amount_pending: Decimal = Decimal("0")
    total_amount_completed_today: Decimal = Decimal("0")
    awaiting_document: int = 0
    not_started: int = 0


class ProcessObligationRequest(BaseModel):
    """Request to process an obligation (processing -> completed)."""
    issued_document_id: Optional[UUID] = None
    notes: Optional[str] = Field(None, max_length=500)


class RejectObligationRequest(BaseModel):
    """Request to reject an obligation (processing -> paid for re-routing)."""
    reason: str = Field(..., min_length=5, max_length=500)


class BatchProcessRequest(BaseModel):
    """Batch process multiple obligations."""
    obligation_ids: List[UUID] = Field(..., min_length=1, max_length=100)
    issued_document_id: Optional[UUID] = None

    @field_validator("obligation_ids")
    @classmethod
    def unique_ids(cls, v: List[UUID]) -> List[UUID]:
        if len(v) != len(set(v)):
            raise ValueError("Duplicate obligation IDs")
        return v
