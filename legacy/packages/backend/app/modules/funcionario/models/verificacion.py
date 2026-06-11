"""
Pydantic models for Funcionario Verification.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field


class VerificacionStatus(str, Enum):
    """Status of a verification request."""
    PENDIENTE = "pendiente"
    APROBADO = "aprobado"
    RECHAZADO = "rechazado"


class DocumentoTipoPrueba(str, Enum):
    """Types of proof documents accepted for verification."""
    NOMBRAMIENTO = "nombramiento"
    CARNET_FUNCIONARIO = "carnet_funcionario"
    CONTRATO_FUNCIONARIO = "contrato_funcionario"


# =============================================================================
# REQUEST MODELS
# =============================================================================

class VerificacionCreate(BaseModel):
    """Request to create a new verification."""
    matricula: str = Field(..., min_length=4, max_length=50, description="Matricula del funcionario")

    class Config:
        json_schema_extra = {
            "example": {
                "matricula": "FP-12345"
            }
        }


class VerificacionProcessRequest(BaseModel):
    """Request to process (approve/reject) a verification."""
    action: str = Field(..., pattern="^(aprobar|rechazar)$", description="Action: aprobar or rechazar")
    matricula_existe: bool = Field(False, description="Agent verified matricula exists in SIGEF")
    nombre_coincide: bool = Field(False, description="Agent verified name matches")
    dip_coincide: bool = Field(False, description="Agent verified DIP matches")
    rejection_reason: Optional[str] = Field(None, description="Reason for rejection (required if action=rechazar)")
    notes: Optional[str] = Field(None, description="Agent notes")

    class Config:
        json_schema_extra = {
            "example": {
                "action": "aprobar",
                "matricula_existe": True,
                "nombre_coincide": True,
                "dip_coincide": True,
                "notes": "Verificado en SIGEF"
            }
        }


class BatchApproveRequest(BaseModel):
    """Request to batch approve multiple verifications."""
    verificacion_ids: List[UUID] = Field(..., min_length=1, description="List of verification IDs to approve")
    notes: Optional[str] = Field(None, description="Notes for all approvals")

    class Config:
        json_schema_extra = {
            "example": {
                "verificacion_ids": ["uuid-1", "uuid-2", "uuid-3"],
                "notes": "Batch approval - auto-validated"
            }
        }


# =============================================================================
# RESPONSE MODELS
# =============================================================================

class DocumentExtractionSummary(BaseModel):
    """Summary of extracted data from a document."""
    file_id: Optional[str] = None
    file_name: Optional[str] = None
    extraction_confidence: Optional[float] = None
    processor: Optional[str] = None
    extracted_at: Optional[str] = None


class ValidacionCruzada(BaseModel):
    """Cross-validation results between documents."""
    nombre_dip: Optional[str] = None
    nombre_documento: Optional[str] = None
    nombres_coinciden: bool = False
    similitud_nombre: float = 0.0
    matricula_documento: Optional[str] = None
    matricula_ingresada: Optional[str] = None
    matriculas_coinciden: bool = False
    validacion_automatica_posible: bool = False


class VerificacionResponse(BaseModel):
    """Response for a verification request."""
    id: UUID
    user_id: UUID
    matricula: str
    status: VerificacionStatus

    # Form data summary
    tipo_documento_prueba: Optional[DocumentoTipoPrueba] = None
    tiene_dip: bool = False
    tiene_documento_prueba: bool = False
    validacion_cruzada: Optional[ValidacionCruzada] = None

    # Auto-verification result (from verified_identifiers)
    pre_verified: bool = False
    pre_verified_source: Optional[str] = None

    # Processing info
    processed_by: Optional[UUID] = None
    processed_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    notes: Optional[str] = None

    # Checklist
    verificacion_matricula_existe: bool = False
    verificacion_nombre_coincide: bool = False
    verificacion_dip_coincide: bool = False

    # Timestamps
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class VerificacionDetailResponse(VerificacionResponse):
    """Detailed response including verification_data for agents."""
    verification_data: Dict[str, Any] = Field(default_factory=dict)

    # User info (for agent dashboard)
    user_email: Optional[str] = None
    user_full_name: Optional[str] = None
    user_phone: Optional[str] = None


class VerificacionListResponse(BaseModel):
    """Paginated list of verifications."""
    items: List[VerificacionResponse]
    total: int
    page: int
    page_size: int
    total_pages: int

    # Stats
    pendientes: int = 0
    pendientes_auto_validables: int = 0
    pendientes_pre_verificados: int = 0  # Pre-verified in verified_identifiers
    aprobadas: int = 0
    rechazadas: int = 0


class BatchApproveResponse(BaseModel):
    """Response for batch approval."""
    success: bool
    total: int
    approved: int
    errors: int
    results: List[Dict[str, Any]] = Field(default_factory=list)


class MyVerificationStatusResponse(BaseModel):
    """Response for user's own verification status."""
    has_verification: bool = False
    status: Optional[VerificacionStatus] = None
    matricula: Optional[str] = None
    submitted_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None

    # If approved
    is_verified_funcionario: bool = False
    funcionario_verified_at: Optional[datetime] = None

    # Can submit new request?
    can_submit_new: bool = True
    message: Optional[str] = None


class DocumentExtraction(BaseModel):
    """Full extraction data for a document."""
    file_id: Optional[str] = None
    file_name: Optional[str] = None
    file_url: Optional[str] = None
    mime_type: Optional[str] = None
    extraction: Dict[str, Any] = Field(default_factory=dict)
    extraction_confidence: Optional[float] = None
    processor: Optional[str] = None
    uploaded_at: Optional[str] = None
    risk_analysis: Optional[Dict[str, Any]] = None


class MyVerificationResponse(BaseModel):
    """
    Full verification data for the user's own verification.

    Includes all extracted data for auto-fill in form_review.
    """
    id: UUID
    matricula: str
    status: VerificacionStatus
    created_at: datetime
    updated_at: datetime

    # Document status
    tipo_documento_prueba: Optional[DocumentoTipoPrueba] = None
    tiene_dip: bool = False
    tiene_documento_prueba: bool = False

    # Cross-validation
    validacion_cruzada: Optional[ValidacionCruzada] = None

    # Document extractions (for auto-fill)
    dip: Optional[DocumentExtraction] = None
    documento_prueba: Optional[DocumentExtraction] = None

    # Processing info (if processed)
    processed_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None

    class Config:
        from_attributes = True


class FormReviewField(BaseModel):
    """A field for form_review with auto-fill data."""
    field_name: str
    field_label_es: str
    value: Optional[str] = None
    source_document: Optional[str] = None  # dip, nombramiento, etc.
    source_path: Optional[str] = None  # extraction path
    confidence: Optional[float] = None
    is_editable: bool = True
    is_required: bool = False
    validation_pattern: Optional[str] = None


class FormReviewSection(BaseModel):
    """A section of the form_review."""
    section_id: str
    section_title_es: str
    fields: List[FormReviewField] = Field(default_factory=list)


class FormReviewResponse(BaseModel):
    """
    Structured data for form_review auto-fill.

    Provides extracted data organized by sections for the frontend wizard.
    Built by verificacion_service.build_form_review_data().
    """
    verificacion_id: UUID
    status: VerificacionStatus

    # Step metadata (from FORM_REVIEW_CONFIG)
    step_id: str = "form_review"
    title_es: str = "Verificar Datos Extraídos"
    description_es: str = "Revise y corrija los datos extraídos de sus documentos antes de enviar la solicitud"

    # Proof document type (nombramiento, carnet_funcionario, contrato_funcionario)
    proof_document_type: Optional[str] = None

    # Validation status
    cross_validation_passed: bool = False
    auto_validable: bool = False
    warnings: List[Dict[str, Any]] = Field(default_factory=list)

    # Form sections with auto-filled data
    sections: List[Dict[str, Any]] = Field(default_factory=list)  # Use Dict for flexibility

    # Raw extraction data (for custom handling)
    raw_extractions: Dict[str, Any] = Field(default_factory=dict)
