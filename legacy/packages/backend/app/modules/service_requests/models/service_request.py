"""
Pydantic models for service_requests.
Aligned with database schema from migration 020.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime, date, time
from uuid import UUID

from .enums import ServiceRequestStatus, ServiceRequestPriority, SolicitudType


# === Request Models ===

class ServiceRequestCreate(BaseModel):
    """Create a new service request"""
    workflow_code: str = Field(..., min_length=1, max_length=100)
    solicitud_type: SolicitudType = SolicitudType.EXPEDICION
    fiscal_service_id: Optional[int] = None
    priority: ServiceRequestPriority = ServiceRequestPriority.NORMAL
    form_data: Dict[str, Any] = Field(default_factory=dict)

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
                "workflow_code": "RESIDENCIA_PRIMERA_VEZ",
                "solicitud_type": "expedicion",
                "priority": "NORMAL"
            }
        }


class ServiceRequestUpdate(BaseModel):
    """Update service request fields"""
    status: Optional[ServiceRequestStatus] = None
    priority: Optional[ServiceRequestPriority] = None
    form_data: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None
    assigned_to: Optional[UUID] = None
    entity_code: Optional[str] = None
    cita_date: Optional[date] = None
    cita_time: Optional[time] = None
    cita_location: Optional[str] = None


# === Document Models ===

class RequiredDocument(BaseModel):
    """Document required for a workflow"""
    document_code: str
    document_name: str
    is_required: bool = True
    display_order: int = 0
    accepted_formats: List[str] = Field(default_factory=lambda: ["pdf", "jpg", "png"])
    max_size_mb: int = 10
    extraction_schema_key: Optional[str] = Field(
        None,
        description="Key to the JSON schema for Gemini extraction (e.g., 'DIP_GQ_V1')"
    )
    instructions: Optional[str] = Field(
        None,
        description="Instructions for the user uploading this document"
    )


class ProvidedDocument(BaseModel):
    """
    Document provided by user.
    Maps to service_request_documents table (migration 020).
    """
    id: UUID
    document_code: str
    document_name: str
    file_path: str
    file_name: str
    file_size: Optional[int] = None
    mime_type: Optional[str] = None

    # Extraction results (Gemini/Tesseract)
    extraction_data: Dict[str, Any] = Field(default_factory=dict)
    extraction_confidence: Optional[float] = None
    extraction_status: str = "pending"

    # Validation by agent
    is_valid: Optional[bool] = None
    validation_errors: List[str] = Field(default_factory=list)
    validated_by: Optional[UUID] = None
    validated_at: Optional[datetime] = None

    # Audit
    source: str = "user_upload"
    uploaded_by: Optional[UUID] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# === Tariff Models ===

class TariffBreakdown(BaseModel):
    """Tariff calculation breakdown"""
    base_amount: float
    supplements: List[Dict[str, Any]] = Field(default_factory=list)
    supplements_total: float = 0
    penalties_amount: float = 0
    total_amount: float
    currency: str = "XAF"


# === Response Models ===

class ServiceRequestResponse(BaseModel):
    """
    Complete response for a service request.
    Maps to service_requests table (migration 020).
    """
    id: UUID
    reference: str
    user_id: UUID
    workflow_code: str
    solicitud_type: SolicitudType
    fiscal_service_id: Optional[int] = None
    status: ServiceRequestStatus
    priority: ServiceRequestPriority

    # Documents (computed, not in DB)
    required_documents: List[RequiredDocument] = Field(default_factory=list)
    provided_documents: List[ProvidedDocument] = Field(default_factory=list)
    missing_documents: List[RequiredDocument] = Field(default_factory=list)
    documents_progress: str = "0/0"

    # Form data & extraction
    form_data: Dict[str, Any] = Field(default_factory=dict)
    extracted_data: Dict[str, Any] = Field(default_factory=dict)
    extraction_confidence: Optional[float] = None
    validations: Dict[str, Any] = Field(default_factory=dict)

    # Tariff (computed from base_amount, supplements_amount, etc.)
    tariff: Optional[TariffBreakdown] = None

    # Batch (if created from a batch submission)
    batch_id: Optional[UUID] = None
    company_id: Optional[UUID] = None

    # Assignment
    assigned_to: Optional[UUID] = None
    assigned_at: Optional[datetime] = None
    entity_code: Optional[str] = None

    # Payment
    payment_id: Optional[UUID] = None
    payment_status: Optional[str] = None
    paid_at: Optional[datetime] = None

    # Cita (appointment)
    cita_date: Optional[date] = None
    cita_time: Optional[time] = None
    cita_location: Optional[str] = None

    # Timestamps
    created_at: datetime
    updated_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    validated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    # Notes & Rejection
    notes: Optional[str] = None
    rejection_reason: Optional[str] = None

    # Audit
    created_by: Optional[UUID] = None

    class Config:
        from_attributes = True


class ServiceRequestListResponse(BaseModel):
    """Paginated list response for service requests."""
    requests: List[ServiceRequestResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class DocumentUploadResponse(BaseModel):
    """Response after uploading a document (legacy - kept for compatibility)"""
    document_id: UUID
    document_code: str
    extraction: Dict[str, Any]
    confidence: float
    processor: str  # "gemini", "tesseract", "manual"
    status: str  # "success", "failed", "manual_review"
    needs_review: bool = False


# === NEW FLOW: Preview + Validate ===

class FieldIndicator(BaseModel):
    """Per-field confidence and risk indicator for UI display"""
    field_name: str
    value: Optional[Any] = None
    confidence: float = Field(ge=0, le=1, description="Field extraction confidence")
    status: str = Field(
        default="ok",
        description="ok, warning, error, missing"
    )
    risk_level: Optional[str] = Field(
        default=None,
        description="low, medium, high, critical - if risk detected"
    )
    risk_message: Optional[str] = Field(
        default=None,
        description="Risk message to display to user"
    )
    requires_attention: bool = Field(
        default=False,
        description="True if field needs user attention"
    )
    suggestion: Optional[str] = Field(
        default=None,
        description="Suggested action for user"
    )


class RiskAnalysisResult(BaseModel):
    """Complete risk analysis result"""
    risk_level: str = Field(..., description="low, medium, high, critical")
    risk_score: int = Field(ge=0, le=100, description="Overall risk score 0-100")
    risk_factors: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of detected risk factors"
    )
    recommendations: List[str] = Field(
        default_factory=list,
        description="Actionable recommendations"
    )
    requires_rejection: bool = Field(
        default=False,
        description="Document should be rejected"
    )
    requires_review: bool = Field(
        default=False,
        description="Document needs manual review"
    )
    factors_count: Dict[str, int] = Field(
        default_factory=dict,
        description="Count of factors by severity"
    )
    # Identity mismatch fields for cross-document validation
    identity_mismatches: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of identity mismatches between documents (name, DOB, ID number conflicts)"
    )
    has_blocking_mismatches: bool = Field(
        default=False,
        description="True if critical identity mismatches were detected that should block form submission"
    )


class DocumentExtractionPreview(BaseModel):
    """
    Response after extraction preview (BEFORE user validation).
    Document is NOT yet uploaded to Firebase Storage.

    Includes:
    - Extracted data with per-field confidence indicators
    - Complete risk analysis
    - Visual indicators for problematic fields
    """
    preview_id: str = Field(..., description="Temporary ID for this preview session")
    document_code: str
    document_name: str
    file_name: str
    file_size: int
    mime_type: str

    # Extraction results for user review
    extraction: Dict[str, Any] = Field(
        default_factory=dict,
        description="Extracted data from Gemini/Tesseract"
    )
    confidence: float = Field(
        ..., ge=0, le=1,
        description="Overall confidence score (0.0 - 1.0)"
    )
    processor: str = Field(..., description="gemini, tesseract, or hybrid")

    # Per-field indicators for UI
    field_indicators: List[FieldIndicator] = Field(
        default_factory=list,
        description="Per-field confidence and risk indicators for visual display"
    )

    # Risk Analysis
    risk_analysis: Optional[RiskAnalysisResult] = Field(
        default=None,
        description="Complete risk analysis result"
    )

    # Status
    extraction_status: str = Field(
        ...,
        description="success, pending_validation, low_confidence, requires_review, rejected"
    )
    needs_correction: bool = Field(
        default=False,
        description="True if confidence < 70% and user should review"
    )

    # Document type detection
    detected_document_type: Optional[str] = Field(
        default=None,
        description="AI-detected document type (may differ from expected)"
    )
    document_type_match: bool = Field(
        default=True,
        description="True if detected type matches expected type"
    )

    # Schema info for frontend form generation
    expected_fields: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of expected fields with labels and types"
    )

    # Expiry (preview is temporary)
    expires_at: datetime = Field(..., description="Preview expires after 30 minutes")

    # Processing info
    processing_time_ms: Optional[int] = Field(
        default=None,
        description="Time taken to process document in milliseconds"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "preview_id": "prev_abc123",
                "document_code": "dip_gq",
                "document_name": "Documento de Identidad Personal",
                "file_name": "mi_dip.pdf",
                "file_size": 1024000,
                "mime_type": "application/pdf",
                "extraction": {
                    "numero_documento": "A12345678",
                    "nombres": "JUAN CARLOS",
                    "apellidos": "NGUEMA OBIANG",
                    "fecha_nacimiento": "1985-03-15"
                },
                "confidence": 0.85,
                "processor": "gemini",
                "field_indicators": [
                    {
                        "field_name": "numero_documento",
                        "value": "A12345678",
                        "confidence": 0.95,
                        "status": "ok",
                        "requires_attention": False
                    },
                    {
                        "field_name": "fecha_nacimiento",
                        "value": "1985-03-15",
                        "confidence": 0.60,
                        "status": "warning",
                        "risk_level": "medium",
                        "risk_message": "Low confidence - please verify",
                        "requires_attention": True,
                        "suggestion": "Check date format DD/MM/YYYY"
                    }
                ],
                "risk_analysis": {
                    "risk_level": "low",
                    "risk_score": 15,
                    "risk_factors": [],
                    "recommendations": ["No significant risks detected"],
                    "requires_rejection": False,
                    "requires_review": False,
                    "factors_count": {"critical": 0, "high": 0, "medium": 0, "low": 1}
                },
                "extraction_status": "pending_validation",
                "needs_correction": False,
                "detected_document_type": "dni",
                "document_type_match": True,
                "expires_at": "2025-12-27T19:30:00Z",
                "processing_time_ms": 1250
            }
        }


class DocumentValidationRequest(BaseModel):
    """
    Request to validate (confirm or correct) extracted data.
    After validation, document is uploaded to Firebase Storage.
    """
    preview_id: str = Field(..., description="Preview ID from extraction preview")

    # User can confirm or provide corrected data
    confirmed_data: Dict[str, Any] = Field(
        ...,
        description="User-confirmed or corrected extraction data"
    )

    # Optional user notes
    user_notes: Optional[str] = Field(
        None, max_length=500,
        description="Optional notes from user about this document"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "preview_id": "prev_abc123",
                "confirmed_data": {
                    "numero_documento": "A12345678",
                    "nombres": "JUAN CARLOS",
                    "apellidos": "NGUEMA OBIANG",
                    "fecha_nacimiento": "1985-03-15"
                }
            }
        }


class DocumentValidationResponse(BaseModel):
    """Response after user validates extraction and document is saved"""
    document_id: UUID
    document_code: str
    document_name: str
    file_path: str = Field(..., description="Firebase Storage path")
    extraction_data: Dict[str, Any]
    extraction_confidence: float
    is_validated: bool = True
    validated_at: datetime


# === Workflow Step Execution Models ===

class StepExecutionRequest(BaseModel):
    """Request to execute a workflow step"""
    step_data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Data for the step (selections, form data, etc.)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "step_data": {
                    "selection": "NUEVO",
                    "confirmed_data": {"nombres": "JUAN CARLOS"}
                }
            }
        }


class StepInfo(BaseModel):
    """Information about a workflow step"""
    number: int
    id: str
    type: str
    title_es: str


class StepExecutionResponse(BaseModel):
    """Response from executing a workflow step"""
    step_number: int
    step_id: str
    step_type: str
    success: bool

    # Step-specific results
    options: Optional[List[Any]] = None
    selection: Optional[str] = None
    documents_required: Optional[List[Dict[str, Any]]] = None
    missing_documents: Optional[List[Dict[str, Any]]] = None
    form_data: Optional[Dict[str, Any]] = None
    extracted_data: Optional[Dict[str, Any]] = None
    requires_review: Optional[bool] = None
    validation_complete: Optional[bool] = None
    has_errors: Optional[bool] = None
    errors: Optional[List[Dict[str, Any]]] = None
    warnings: Optional[List[Dict[str, Any]]] = None
    amount: Optional[float] = None
    tariff_breakdown: Optional[Dict[str, Any]] = None
    payment_methods: Optional[List[str]] = None

    # Navigation
    next_step: Optional[StepInfo] = None
    error: Optional[str] = None


class FormDataResponse(BaseModel):
    """
    Response with pre-filled form data from document extraction.

    This applies the workflow's form_mapping to transform extracted_data
    into a flat form structure ready for frontend display.
    """
    form_data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Pre-filled form fields from extraction"
    )
    extracted_data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Raw extracted data by document"
    )
    form_schema: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Form schema for frontend rendering (optional)"
    )
    requires_review: bool = Field(
        default=True,
        description="True if user should review and confirm data"
    )
    completion_percentage: float = Field(
        default=0,
        ge=0, le=100,
        description="Percentage of required fields filled"
    )
    missing_fields: List[str] = Field(
        default_factory=list,
        description="List of required fields that are empty"
    )


class CitizenSummaryResponse(BaseModel):
    """
    Summary of service request for citizen confirmation.

    This is the 'formulaire recapitulatif' shown before final submission.
    """
    request_id: UUID
    reference: str
    workflow_code: str
    workflow_name_es: str
    solicitud_type: str
    sub_type: Optional[str] = None

    # Personal data extracted
    personal_data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Personal information extracted from documents"
    )

    # Documents summary
    documents_uploaded: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of uploaded documents with status"
    )
    documents_complete: bool = False

    # Tariff summary
    tariff_summary: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Cost breakdown"
    )

    # Validation status
    validation_passed: bool = False
    validation_warnings: List[str] = Field(default_factory=list)

    # Ready for submission?
    can_submit: bool = False
    blockers: List[str] = Field(
        default_factory=list,
        description="Reasons why submission is blocked"
    )


# === Validation Models ===

class ValidationResultResponse(BaseModel):
    """
    Result of a validation check for API response.
    Matches frontend ValidationResult type.
    """
    rule_id: str = Field(..., description="Unique identifier for the validation rule")
    is_valid: bool = Field(..., description="Whether the validation passed")
    severity: str = Field(
        default="error",
        description="Severity level: error, warning, or info"
    )
    message_es: str = Field(
        default="",
        description="Message in Spanish"
    )
    field: Optional[str] = Field(
        default=None,
        description="The field being validated"
    )
    document_code: Optional[str] = Field(
        default=None,
        description="The document being validated"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "rule_id": "dip_number_format",
                "is_valid": False,
                "severity": "error",
                "message_es": "El numero de DIP no tiene el formato correcto",
                "field": "numero_dip",
                "document_code": "dip"
            }
        }


class PaymentStatusResponse(BaseModel):
    """
    Payment status for a service request.
    Used for polling after initiating payment.
    """
    status: str = Field(
        ...,
        description="Current payment status: pending, processing, completed, failed"
    )
    paid: bool = Field(
        ...,
        description="True if payment has been completed"
    )
    payment_id: Optional[str] = Field(
        default=None,
        description="The payment ID if exists"
    )
    amount: Optional[float] = Field(
        default=None,
        description="Payment amount"
    )
    currency: str = Field(
        default="XAF",
        description="Currency code"
    )
    payment_method: Optional[str] = Field(
        default=None,
        description="Payment method used"
    )
    completed_at: Optional[datetime] = Field(
        default=None,
        description="When payment was completed"
    )


# ===================================================================
# PAYMENT METHODS & INITIATION
# ===================================================================

class PaymentMethodInfo(BaseModel):
    """Information about a single payment method."""
    code: str = Field(..., description="Payment method code")
    label_es: str = Field(..., description="Spanish label")
    label_en: str = Field(..., description="English label")
    label_fr: str = Field(..., description="French label")
    processor_type: str = Field(..., description="Processor type: bange_api or manual")
    requires_phone: bool = Field(default=False, description="Whether phone number is required")
    requires_redirect: bool = Field(default=False, description="Whether redirect to payment gateway")
    requires_agent_validation: bool = Field(default=False, description="Whether agent validation needed")


class PaymentMethodsResponse(BaseModel):
    """Response with available payment methods."""
    methods: List[PaymentMethodInfo] = Field(..., description="List of available payment methods")
    default_method: Optional[str] = Field(default=None, description="Recommended default method")


# === Detail View Models (Mi Solicitud dynamic page) ===

class StepperPhase(BaseModel):
    """A step/phase in the workflow stepper."""
    id: str = Field(..., description="Step ID e.g. 'selection', 'upload', 'form_review_1'")
    title_es: str = Field(..., description="Step title in Spanish")
    step_type: str = Field(..., description="Step type: selection, upload, form_review, appointment, payment, confirmation")
    number: int = Field(..., description="Step number in sequence")
    is_optional: bool = Field(default=False)


class DataSectionField(BaseModel):
    """A single field in a data section."""
    label: str
    value: Optional[str] = None


class DataSection(BaseModel):
    """A section of data fields (e.g. 'Datos Personales', 'Domicilio')."""
    title: str
    fields: List[DataSectionField] = Field(default_factory=list)


class CitizenNotification(BaseModel):
    """A notification visible to the citizen."""
    id: str
    action: str = Field(..., description="Action type e.g. STATUS_CHANGE, AGENT_ACTION")
    title: str = Field(..., description="Human-readable title")
    message: Optional[str] = Field(None, description="Detail message")
    performed_at: datetime
    performer_role: Optional[str] = Field(None, description="Role of performer (agent, system) - never the name")
    is_new: bool = Field(default=False, description="True if after citizen_last_viewed_at")
    new_status: Optional[str] = Field(None, description="New status if STATUS_CHANGE")


# ═══════════════════════════════════════════════════════════════
# CITIZEN DASHBOARD SUMMARY MODELS
# ═══════════════════════════════════════════════════════════════


class DashboardSummaryStats(BaseModel):
    """Aggregated statistics for citizen dashboard."""
    active: int = 0
    completed: int = 0
    pending_action: int = 0
    total_paid: float = 0.0


class DashboardRecentRequest(BaseModel):
    """Lightweight request for dashboard list."""
    id: str
    reference: str
    workflow_code: str
    workflow_label: str = ""
    status: str
    solicitud_type: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    total_amount: Optional[float] = None


class DashboardRecentPayment(BaseModel):
    """Recent service payment for dashboard."""
    id: str
    service_request_id: str
    request_reference: str
    workflow_code: str
    workflow_label: str = ""
    amount: float
    currency: str = "XAF"
    status: str
    payment_method: Optional[str] = None
    created_at: datetime


class DashboardUpcomingAppointment(BaseModel):
    """Next upcoming appointment."""
    request_id: str
    request_reference: str
    workflow_code: str
    workflow_label: str = ""
    appointment_date: datetime
    time: Optional[str] = None
    location: Optional[str] = None


class DashboardActionRequired(BaseModel):
    """Request needing citizen action."""
    request_id: str
    reference: str
    workflow_code: str
    workflow_label: str = ""
    status: str
    message: str


class DashboardSummaryResponse(BaseModel):
    """Complete citizen dashboard data — single endpoint, single call."""
    stats: DashboardSummaryStats
    recent_requests: List[DashboardRecentRequest] = Field(default_factory=list)
    recent_payments: List[DashboardRecentPayment] = Field(default_factory=list)
    notifications: List[CitizenNotification] = Field(default_factory=list)
    unread_count: int = 0
    upcoming_appointment: Optional[DashboardUpcomingAppointment] = None
    action_required: List[DashboardActionRequired] = Field(default_factory=list)


class DocumentInfo(BaseModel):
    """Document info with signed download URL for citizen preview."""
    id: str
    document_code: str
    document_name: str
    file_name: str
    mime_type: Optional[str] = None
    file_url: Optional[str] = None


class DetailViewResponse(BaseModel):
    """
    Combined response for the citizen 'Mi Solicitud' detail page.
    Single endpoint replacing multiple separate API calls.
    """
    # Core request data
    request: ServiceRequestResponse

    # Dynamic stepper
    stepper_phases: List[StepperPhase] = Field(default_factory=list)
    current_phase_index: int = Field(default=0, description="Index of current phase in stepper_phases")

    # Dynamic data sections (same as PDF)
    data_sections: List[DataSection] = Field(default_factory=list)

    # Citizen notifications
    citizen_notifications: List[CitizenNotification] = Field(default_factory=list)
    unread_notification_count: int = Field(default=0)

    # Photo URL
    photo_url: Optional[str] = None

    # Tariff
    tariff: Optional[Dict[str, Any]] = None

    # Payment status
    payment_status: Optional[str] = None
    payment_reference: Optional[str] = None
    receipt_number: Optional[str] = None

    # Appointment
    appointment: Optional[Dict[str, Any]] = None

    # Documents with signed URLs
    documents: List[DocumentInfo] = Field(default_factory=list)

    # Workflow metadata
    workflow_name_es: str = ""
    workflow_name: str = Field(default="", description="Translated workflow name (based on Accept-Language)")
    solicitud_type_display: Optional[str] = None

    # Bundle-specific (only for BUNDLE_PAYMENT workflow)
    bundle_details: Optional[Dict[str, Any]] = None


class PaymentInitiateRequest(BaseModel):
    """Request to initiate a payment."""
    payment_method: str = Field(..., description="Payment method code")
    phone_number: Optional[str] = Field(None, description="Phone number for Mobile Money")
    return_url: Optional[str] = Field(None, description="URL to redirect after payment")


class PaymentInitiateResponse(BaseModel):
    """Response after initiating payment."""
    success: bool = Field(..., description="Whether initiation was successful")
    payment_id: str = Field(..., description="Internal payment ID")
    payment_reference: Optional[str] = Field(None, description="External reference")
    status: str = Field(..., description="Initial payment status")
    redirect_url: Optional[str] = Field(None, description="URL to redirect for payment")
    requires_action: bool = Field(default=False, description="Whether user action is required")
    action_type: Optional[str] = Field(None, description="Type of action required")
    message_es: Optional[str] = Field(None, description="Message for user in Spanish")
    expires_at: Optional[datetime] = Field(None, description="When this payment request expires")
    error: Optional[str] = Field(None, description="Error message if success=false")
