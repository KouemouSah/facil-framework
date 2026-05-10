"""
Pydantic models for Wizard Session (Cache-First Architecture).

These models support the cache-first wizard where all data stays in Redis
until payment is initiated. No DB/Firebase writes until user confirms payment.

@since v2.0 - Cache-first wizard migration
@see .claude/plans/CACHE_FIRST_WIZARD_MIGRATION_PLAN.md
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Any, List
from datetime import datetime, date, time
from uuid import UUID
from enum import Enum


# =============================================================================
# ENUMS
# =============================================================================

class WizardSessionStatus(str, Enum):
    """Status of a wizard session."""
    ACTIVE = "active"              # Session is active, user is working
    DOCUMENTS_UPLOADED = "documents_uploaded"  # All documents uploaded
    READY_FOR_PAYMENT = "ready_for_payment"    # Form reviewed, ready to pay
    PAYMENT_INITIATED = "payment_initiated"    # Payment started
    PERSISTED = "persisted"        # Data persisted to DB (success)
    EXPIRED = "expired"            # Session expired (TTL)
    CANCELLED = "cancelled"        # User cancelled


# =============================================================================
# SESSION DATA MODELS
# =============================================================================

class SessionDocumentData(BaseModel):
    """Document data stored in session cache."""
    document_code: str
    document_name: Optional[str] = None
    file_name: str
    file_size: int
    mime_type: str
    content_b64: str = Field(..., description="Base64-encoded file content")

    # Extraction results
    extraction: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=0, ge=0, le=1)
    processor: str = Field(default="unknown", description="gemini, tesseract, hybrid")
    extraction_status: str = Field(default="pending", description="pending, success, failed, manual_review")

    # Risk analysis
    risk_analysis: Optional[Dict[str, Any]] = None

    # Timestamps
    previewed_at: datetime
    confirmed_at: Optional[datetime] = None

    # User corrections (if any)
    user_corrections: Optional[Dict[str, Any]] = None

    class Config:
        json_schema_extra = {
            "example": {
                "document_code": "dip",
                "file_name": "mi_dip.pdf",
                "file_size": 1024000,
                "mime_type": "application/pdf",
                "content_b64": "...",
                "extraction": {"numero_documento": "A12345678"},
                "confidence": 0.95,
                "processor": "gemini",
                "extraction_status": "success",
                "previewed_at": "2026-02-05T10:00:00Z"
            }
        }


class WizardSessionData(BaseModel):
    """
    Complete wizard session data stored in Redis cache.

    This contains ALL wizard state until payment is initiated.
    No database record exists until persist_to_db() is called.
    """
    # Session identification
    session_id: str
    user_id: str

    # Workflow info
    workflow_code: str
    solicitud_type: str  # expedicion, renovacion, duplicado
    sub_type: Optional[str] = None  # NUEVO, PERDIDA, ROBO, DETERIORO, etc.
    motivo: Optional[str] = None  # For renovacion: VENCIMIENTO, PERDIDA, etc.

    # Entity assignment
    entity_code: Optional[str] = None

    # Session status
    status: WizardSessionStatus = WizardSessionStatus.ACTIVE

    # Documents (by document_code)
    documents: Dict[str, SessionDocumentData] = Field(default_factory=dict)

    # Merged extracted data (from all documents)
    extracted_data: Dict[str, Any] = Field(default_factory=dict)

    # User-edited form data
    form_data: Dict[str, Any] = Field(default_factory=dict)

    # Minor info (for pasaporte)
    is_minor: bool = False

    # Current step in wizard
    current_step: int = 1
    current_step_id: Optional[str] = None

    # Tariff calculation (computed on prepare_for_payment)
    tariff: Optional[Dict[str, Any]] = None

    # Appointment selection (cached before payment, not a real hold)
    appointment_data: Optional[Dict[str, Any]] = None

    # Site selection (for non-appointment workflows)
    site_selection: Optional[Dict[str, Any]] = None

    # Validation results
    validation_results: Optional[List[Dict[str, Any]]] = None
    has_errors: bool = False

    # Timestamps
    created_at: datetime
    updated_at: datetime
    expires_at: datetime

    # Audit
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

    class Config:
        use_enum_values = True


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class WizardSessionCreate(BaseModel):
    """Request to start a new wizard session."""
    workflow_code: str = Field(..., min_length=1, max_length=100)
    solicitud_type: str = Field(default="expedicion", description="expedicion, renovacion, duplicado")
    sub_type: Optional[str] = Field(None, description="Workflow-specific sub-type")
    motivo: Optional[str] = Field(None, description="Reason for renovacion")
    is_minor: bool = Field(default=False, description="Is the applicant a minor?")
    auto_fill_vault: bool = Field(
        default=False,
        description="Auto-fill documents from vault if matching docs exist.",
    )

    @field_validator("workflow_code")
    @classmethod
    def validate_workflow_code(cls, v: str) -> str:
        """Validate workflow_code exists in registered workflows."""
        from ..services.workflow_engine import workflow_engine
        code = v.strip().upper()
        if not code:
            raise ValueError("workflow_code cannot be empty")
        wf = workflow_engine.get_workflow_by_string(code)
        if not wf:
            raise ValueError(f"Unknown workflow_code: {code}")
        return code

    class Config:
        json_schema_extra = {
            "example": {
                "workflow_code": "PASAPORTE_NUEVO",
                "solicitud_type": "renovacion",
                "motivo": "VENCIMIENTO",
                "is_minor": False
            }
        }


class WizardSessionResponse(BaseModel):
    """Response after starting or retrieving a wizard session."""
    session_id: str
    workflow_code: str
    solicitud_type: str
    sub_type: Optional[str] = None
    motivo: Optional[str] = None
    is_minor: bool = False

    status: WizardSessionStatus
    current_step: int
    current_step_id: Optional[str] = None

    # Documents summary (without content_b64)
    documents_count: int = 0
    documents_uploaded: List[str] = Field(default_factory=list)

    # Form data (for restore)
    form_data: Dict[str, Any] = Field(default_factory=dict)
    extracted_data: Dict[str, Any] = Field(default_factory=dict)

    # Tariff (if calculated)
    tariff: Optional[Dict[str, Any]] = None

    # Session timing
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
    ttl_seconds: int

    # Required documents for this workflow/solicitud_type
    required_documents: List[Dict[str, Any]] = Field(default_factory=list)

    # Workflow capabilities
    requires_appointment: bool = False
    entity_code: Optional[str] = None

    # Appointment selection (cached in session, not a real hold)
    appointment_data: Optional[Dict[str, Any]] = None

    # Site selection (for non-appointment workflows)
    site_selection: Optional[Dict[str, Any]] = None

    class Config:
        use_enum_values = True
        json_schema_extra = {
            "example": {
                "session_id": "wizard_session_abc123",
                "workflow_code": "PASAPORTE",
                "solicitud_type": "renovacion",
                "status": "active",
                "current_step": 3,
                "documents_count": 2,
                "documents_uploaded": ["dip", "pasaporte_antiguo"],
                "expires_at": "2026-02-05T10:30:00Z",
                "ttl_seconds": 1800
            }
        }


class WizardDocumentPreviewResponse(BaseModel):
    """Response after previewing a document extraction."""
    session_id: str
    document_code: str
    document_name: Optional[str] = None
    file_name: str
    file_size: int

    # Extraction results
    extraction: Dict[str, Any]
    confidence: float
    processor: str
    extraction_status: str
    needs_correction: bool = False

    # Risk analysis
    risk_analysis: Optional[Dict[str, Any]] = None

    # Cross-document validation (if applicable)
    cross_validation: Optional[Dict[str, Any]] = None

    # Session timing
    expires_at: datetime
    ttl_seconds: int

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "wizard_session_abc123",
                "document_code": "dip",
                "file_name": "mi_dip.pdf",
                "file_size": 1024000,
                "extraction": {"numero_documento": "A12345678"},
                "confidence": 0.95,
                "processor": "gemini",
                "extraction_status": "success",
                "needs_correction": False,
                "expires_at": "2026-02-05T10:30:00Z",
                "ttl_seconds": 1800
            }
        }


class WizardDocumentConfirmRequest(BaseModel):
    """Request to confirm document extraction (with optional corrections)."""
    document_code: str
    confirmed_data: Dict[str, Any] = Field(..., description="User-confirmed or corrected data")
    user_notes: Optional[str] = Field(None, max_length=500)


class WizardFormDataSaveRequest(BaseModel):
    """Request to save form data to session."""
    form_data: Dict[str, Any] = Field(..., description="Form data to save")
    step_id: Optional[str] = Field(None, description="Current step ID")


class PaymentMethodInfoResponse(BaseModel):
    """Payment method info for frontend display."""
    code: str
    label_es: str
    label_en: str
    label_fr: str
    processor_type: str
    requires_phone: bool
    requires_redirect: bool
    requires_agent_validation: bool


class WizardPreparePaymentResponse(BaseModel):
    """Response after preparing for payment."""
    session_id: str
    ready_for_payment: bool

    # Tariff breakdown
    tariff: Dict[str, Any]
    total_amount: float
    currency: str = "XAF"

    # Validation status
    validation_passed: bool
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[Dict[str, Any]] = Field(default_factory=list)

    # Documents status
    all_documents_uploaded: bool
    missing_documents: List[str] = Field(default_factory=list)

    # Payment methods
    payment_methods: List[PaymentMethodInfoResponse] = Field(default_factory=list)
    default_payment_method: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "wizard_session_abc123",
                "ready_for_payment": True,
                "tariff": {"base_amount": 50000, "supplements": [], "total_amount": 50000},
                "total_amount": 50000,
                "currency": "XAF",
                "validation_passed": True,
                "errors": [],
                "warnings": [],
                "all_documents_uploaded": True,
                "missing_documents": []
            }
        }


class WizardPersistResult(BaseModel):
    """Result after persisting session to database."""
    success: bool
    service_request_id: Optional[UUID] = None
    reference: Optional[str] = None
    payment_id: Optional[str] = None

    error: Optional[str] = None
    error_code: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "service_request_id": "123e4567-e89b-12d3-a456-426614174000",
                "reference": "PAS-2026-00001",
                "payment_id": "pay_abc123"
            }
        }


class WizardInitiatePaymentRequest(BaseModel):
    """Request to atomically persist session + initiate payment."""
    payment_method: str = Field(..., description="Payment method: mobile_money, card, bank_transfer, cash, check")
    phone_number: Optional[str] = Field(None, description="Phone number (required for mobile_money)")
    treasury_location_id: Optional[str] = Field(None, description="Treasury office location ID for cash/check payments")
    return_url: Optional[str] = Field(
        None,
        max_length=512,
        description=(
            "Optional return URL for the payment gateway redirect (used by mobile clients to deep-link "
            "back into the app after BANGE checkout). Must use one of the allowed mobile schemes "
            "(e.g. 'facil://...') or share the same origin as the configured FRONTEND_URL. "
            "If omitted, the backend uses the default web FRONTEND_URL."
        ),
    )

    @field_validator("return_url")
    @classmethod
    def _validate_return_url(cls, value: Optional[str]) -> Optional[str]:
        if value is None or value == "":
            return None
        from urllib.parse import urlparse
        from app.config import settings

        allowed_schemes = {
            s.strip().lower()
            for s in (settings.MOBILE_DEEP_LINK_SCHEMES or "").split(",")
            if s.strip()
        }
        parsed = urlparse(value)
        scheme = (parsed.scheme or "").lower()
        if not scheme:
            raise ValueError("return_url must be an absolute URL with a scheme")

        if scheme in allowed_schemes:
            return value

        if scheme in ("http", "https"):
            frontend = urlparse(settings.FRONTEND_URL)
            if not frontend.netloc:
                raise ValueError("FRONTEND_URL is misconfigured; cannot validate return_url origin")
            if parsed.netloc.lower() != frontend.netloc.lower():
                raise ValueError(
                    "return_url origin is not allowed (must match FRONTEND_URL or use a registered mobile scheme)"
                )
            return value

        raise ValueError(f"return_url scheme '{scheme}' is not allowed")

    class Config:
        json_schema_extra = {
            "example": {
                "payment_method": "mobile_money",
                "phone_number": "+240222123456",
                "return_url": "facil://wizard/payment-result?session_id=abc&service_request_id=def"
            }
        }


class WizardInitiatePaymentResponse(BaseModel):
    """Response after atomic persist + payment initiation."""
    # Persist result
    success: bool
    service_request_id: Optional[UUID] = None
    reference: Optional[str] = None

    # Payment result
    payment_id: Optional[str] = None
    payment_reference: Optional[str] = None
    payment_status: Optional[str] = None
    redirect_url: Optional[str] = None
    requires_action: bool = False
    action_type: Optional[str] = None  # "redirect", "agent_validation_cash", "agent_validation_check"
    message_es: Optional[str] = None
    expires_at: Optional[datetime] = None

    # Workflow capabilities (for frontend navigation)
    requires_appointment: bool = False

    # Appointment confirmation (set when appointment was held+confirmed atomically)
    appointment_confirmed: bool = False
    appointment_date: Optional[str] = None
    appointment_time: Optional[str] = None
    appointment_location: Optional[str] = None

    # Error info
    error: Optional[str] = None
    error_code: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "service_request_id": "123e4567-e89b-12d3-a456-426614174000",
                "reference": "PAS-2026-00001",
                "payment_id": "pay_abc123",
                "payment_status": "pending",
                "redirect_url": "https://pay.bange.gq/checkout/abc123",
                "requires_action": True,
                "action_type": "redirect",
                "requires_appointment": True,
            }
        }


# =============================================================================
# SITE SELECTION & APPOINTMENT SELECTION REQUEST MODELS
# =============================================================================

class SiteSelectionRequest(BaseModel):
    """Request to save site selection (non-appointment workflows)."""
    entity_location_id: UUID = Field(..., description="FK to entity_locations table")
    location_name: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, max_length=100)
    entity_code: Optional[str] = Field(None, max_length=50)

    class Config:
        json_schema_extra = {
            "example": {
                "entity_location_id": "550e8400-e29b-41d4-a716-446655440000",
                "location_name": "CNEDOGE Malabo",
                "city": "Malabo",
            }
        }


class AppointmentSelectionRequest(BaseModel):
    """Request to save appointment selection in session cache."""
    entity_location_id: UUID = Field(..., description="FK to entity_locations table")
    location_name: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, max_length=100)
    appointment_date: date = Field(..., description="Appointment date (YYYY-MM-DD)")
    appointment_time: time = Field(..., description="Appointment time (HH:MM:SS)")
    slot_config_id: Optional[UUID] = Field(None, description="FK to appointment_slot_configs")

    class Config:
        json_schema_extra = {
            "example": {
                "entity_location_id": "550e8400-e29b-41d4-a716-446655440000",
                "location_name": "CNEDOGE Malabo",
                "city": "Malabo",
                "appointment_date": "2026-03-15",
                "appointment_time": "09:00:00",
            }
        }
