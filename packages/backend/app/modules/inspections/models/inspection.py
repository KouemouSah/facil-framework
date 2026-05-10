"""Field Inspection Models — Pydantic v2 models for inspections module."""

from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID
from enum import Enum

from pydantic import BaseModel, Field, field_validator


# ============================================================
# Enums
# ============================================================

class InspectionStatus(str, Enum):
    in_progress = "in_progress"
    completed = "completed"
    mise_en_demeure = "mise_en_demeure"
    seal_proposed = "seal_proposed"
    seal_approved = "seal_approved"
    seal_rejected = "seal_rejected"
    cancelled = "cancelled"


class InspectionResult(str, Enum):
    conforme = "conforme"
    non_conforme = "non_conforme"
    pending = "pending"


class SealReason(str, Enum):
    non_paiement_apres_med = "non_paiement_apres_med"
    activite_non_autorisee = "activite_non_autorisee"
    fraude_fiscale = "fraude_fiscale"
    faux_documents = "faux_documents"
    refus_controle = "refus_controle"
    non_conformite_grave = "non_conformite_grave"
    decision_judiciaire = "decision_judiciaire"
    ordre_ministeriel = "ordre_ministeriel"


# ============================================================
# Request Models
# ============================================================

class InspectionCreate(BaseModel):
    """Create a new field inspection."""
    license_id: UUID
    company_id: UUID
    mission_id: Optional[UUID] = None
    zone_id: Optional[UUID] = None
    notes: Optional[str] = Field(None, max_length=2000)


class InspectionUpdate(BaseModel):
    """Update inspection during field work (photos, GPS, notes, activity check)."""
    activity_conforme: Optional[bool] = None
    activity_declared: Optional[str] = Field(None, max_length=200)
    activity_observed: Optional[str] = Field(None, max_length=200)
    photos: Optional[List[str]] = None  # URLs from Supabase Storage
    gps_latitude: Optional[Decimal] = None
    gps_longitude: Optional[Decimal] = None
    gps_accuracy: Optional[Decimal] = None
    notes: Optional[str] = Field(None, max_length=2000)
    agent_signature: Optional[str] = None  # Base64 PNG data URL from SignaturePad


class InspectionCompleteRequest(BaseModel):
    """Complete an inspection as conforme."""
    notes: Optional[str] = Field(None, max_length=2000)


class MiseEnDemeureRequest(BaseModel):
    """Issue mise en demeure (formal notice)."""
    obligation_ids: List[UUID] = Field(..., min_length=1)
    deadline_hours: int = Field(72, ge=24, le=720)
    notes: Optional[str] = Field(None, max_length=2000)


class SealProposeRequest(BaseModel):
    """Propose sealing a business."""
    reason: SealReason
    notes: Optional[str] = Field(None, max_length=2000)
    photo: Optional[str] = None  # Seal photo URL

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v):
        if not v:
            raise ValueError("Seal reason is required")
        return v


class SealApproveRequest(BaseModel):
    """Supervisor approves or rejects a seal proposal."""
    approved: bool
    notes: Optional[str] = Field(None, max_length=2000)


class FieldCollectRequest(BaseModel):
    """Collect payment in the field."""
    obligation_ids: List[UUID] = Field(..., min_length=1)
    method: str = Field(..., pattern="^(cash|mobile_money)$")
    amount: Decimal = Field(..., gt=0)
    phone_number: Optional[str] = Field(None, max_length=20)
    notes: Optional[str] = Field(None, max_length=500)

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v, info):
        if info.data.get("method") == "mobile_money" and not v:
            raise ValueError("Phone number required for mobile money")
        return v


# ============================================================
# Response Models
# ============================================================

class InspectionResponse(BaseModel):
    """Full inspection response."""
    model_config = {"from_attributes": True}

    id: UUID
    agent_id: UUID
    agent_profile_id: UUID
    entity_id: UUID
    entity_location_id: UUID
    license_id: UUID
    company_id: UUID
    inspection_date: date
    status: InspectionStatus
    result: Optional[InspectionResult] = None

    activity_conforme: Optional[bool] = None
    activity_declared: Optional[str] = None
    activity_observed: Optional[str] = None

    unpaid_obligations_count: int = 0
    unpaid_obligations_amount: Decimal = Decimal("0")
    total_obligations_count: int = 0

    photos: List[str] = []

    @field_validator("photos", mode="before")
    @classmethod
    def parse_photos(cls, v):
        """Handle photos stored as JSON string in DB (JSONB → text edge case)."""
        if isinstance(v, str):
            import json
            try:
                return json.loads(v)
            except (json.JSONDecodeError, ValueError):
                return []
        return v or []
    gps_latitude: Optional[Decimal] = None
    gps_longitude: Optional[Decimal] = None
    gps_accuracy: Optional[Decimal] = None
    notes: Optional[str] = None

    mise_en_demeure_issued: bool = False
    mise_en_demeure_deadline: Optional[datetime] = None
    mise_en_demeure_obligations: Optional[List[str]] = None

    @field_validator("mise_en_demeure_obligations", mode="before")
    @classmethod
    def parse_med_obligations(cls, v):
        """Handle JSONB stored as string."""
        if isinstance(v, str):
            import json
            try:
                return json.loads(v)
            except (json.JSONDecodeError, ValueError):
                return None
        return v

    seal_applied: bool = False
    seal_reason: Optional[str] = None
    seal_notes: Optional[str] = None
    seal_photo: Optional[str] = None
    seal_proposed_at: Optional[datetime] = None
    seal_approved_by: Optional[UUID] = None
    seal_approved_at: Optional[datetime] = None
    seal_rejection_reason: Optional[str] = None

    payment_collected: bool = False
    payment_id: Optional[UUID] = None
    payment_receipt_number: Optional[str] = None
    payment_amount: Optional[Decimal] = None

    agent_signature: Optional[str] = None

    created_at: datetime
    updated_at: datetime

    # Enriched fields (from JOINs)
    company_name: Optional[str] = None
    company_nif: Optional[str] = None
    agent_name: Optional[str] = None
    entity_code: Optional[str] = None


class InspectionListItem(BaseModel):
    """Compact inspection for list views."""
    model_config = {"from_attributes": True}

    id: UUID
    inspection_date: date
    status: InspectionStatus
    result: Optional[InspectionResult] = None
    company_name: Optional[str] = None
    company_nif: Optional[str] = None
    unpaid_obligations_count: int = 0
    unpaid_obligations_amount: Decimal = Decimal("0")
    seal_applied: bool = False
    mise_en_demeure_issued: bool = False
    payment_collected: bool = False
    agent_name: Optional[str] = None
    entity_code: Optional[str] = None
    created_at: datetime


class InspectionListResponse(BaseModel):
    items: List[InspectionListItem]
    total: int
    page: int
    page_size: int


class InspectionStats(BaseModel):
    """Agent or entity inspection stats."""
    total: int = 0
    conforme: int = 0
    non_conforme: int = 0
    mise_en_demeure: int = 0
    seals_proposed: int = 0
    seals_approved: int = 0
    payments_collected: int = 0
    total_collected_amount: Decimal = Decimal("0")
    avg_duration_minutes: Optional[Decimal] = None


class PendingSealItem(BaseModel):
    """Seal pending supervisor approval."""
    model_config = {"from_attributes": True}

    id: UUID
    inspection_date: date
    company_name: Optional[str] = None
    company_nif: Optional[str] = None
    seal_reason: Optional[str] = None
    seal_notes: Optional[str] = None
    seal_photo: Optional[str] = None
    seal_proposed_at: Optional[datetime] = None
    agent_name: Optional[str] = None
    photos: List[str] = []

    @field_validator("photos", mode="before")
    @classmethod
    def parse_photos(cls, v):
        if isinstance(v, str):
            import json
            try:
                return json.loads(v)
            except (json.JSONDecodeError, ValueError):
                return []
        return v or []
    gps_latitude: Optional[Decimal] = None
    gps_longitude: Optional[Decimal] = None
    unpaid_obligations_amount: Decimal = Decimal("0")
    unpaid_obligations_count: int = 0


class SupervisorDashboardResponse(BaseModel):
    """Supervisor inspection dashboard data."""
    today: InspectionStats
    week: InspectionStats
    pending_seals: List[PendingSealItem]
    overdue_med: int = 0
    unreconciled_cash_amount: Decimal = Decimal("0")
    unreconciled_cash_count: int = 0
    recent_inspections: List[InspectionListItem] = []


class ReconciliationItem(BaseModel):
    """Cash collection for reconciliation."""
    model_config = {"from_attributes": True}

    id: UUID
    inspection_date: date
    company_name: Optional[str] = None
    company_nif: Optional[str] = None
    payment_amount: Optional[Decimal] = None
    payment_receipt_number: Optional[str] = None
    created_at: datetime


class ReconciliationResponse(BaseModel):
    items: List[ReconciliationItem]
    total_amount: Decimal = Decimal("0")
    total_count: int = 0


class LicenseVerificationResponse(BaseModel):
    """Enhanced license verification for agent mode."""
    license_id: UUID
    company_id: UUID
    company_name: Optional[str] = None
    company_nif: Optional[str] = None
    company_registration_number: Optional[str] = None
    forma_juridica: Optional[str] = None
    commerce_type: Optional[str] = None
    zone_code: Optional[str] = None
    city_name: Optional[str] = None
    fiscal_year: int
    license_status: str
    total_amount: Decimal
    amount_paid: Decimal
    compliance_score: Optional[Decimal] = None
    obligations: List[Dict] = []
    previous_inspections: List[InspectionListItem] = []
    active_mise_en_demeure: Optional[Dict] = None
    seal_history: List[Dict] = []


# ============================================================
# Live Status (Phase 8 — Real-Time View)
# ============================================================

class AgentLiveStatus(BaseModel):
    """Real-time status of a field agent."""
    agent_id: UUID
    agent_profile_id: UUID
    agent_name: str
    status: str  # 'active', 'idle', 'offline'
    last_activity_at: Optional[datetime] = None
    minutes_since_activity: Optional[int] = None
    inspections_today: int = 0
    cash_collected_today: Decimal = Decimal("0")
    current_inspection_id: Optional[UUID] = None
    last_gps_latitude: Optional[Decimal] = None
    last_gps_longitude: Optional[Decimal] = None


class LiveStatusCounters(BaseModel):
    """Aggregate live counters for the entity."""
    active_agents: int = 0
    idle_agents: int = 0
    offline_agents: int = 0
    total_agents: int = 0
    inspections_today: int = 0
    inspections_in_progress: int = 0
    cash_collected_today: Decimal = Decimal("0")
    cash_pending_reconciliation: Decimal = Decimal("0")


class LiveStatusResponse(BaseModel):
    """Full real-time status response."""
    agents: List[AgentLiveStatus] = []
    counters: LiveStatusCounters = LiveStatusCounters()
    cached_at: Optional[datetime] = None
