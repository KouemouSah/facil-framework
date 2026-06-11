"""
Pydantic models for Verified Identifiers module.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum

from pydantic import BaseModel, Field


class IdentifierType(str, Enum):
    """Supported identifier types."""
    DNI = "dni"
    PASAPORTE = "pasaporte"
    PERMISO_RESIDENCIA = "permiso_residencia"
    CERTIFICADO_CONDUCIR = "certificado_conducir"
    MATRICULA_VEHICULO = "matricula_vehiculo"
    NIF = "nif"
    CONTRATO_ORNC = "contrato_ornc"
    REGISTRO_CIVIL = "registro_civil"
    CUVE = "cuve"
    PERMISO_CIRCULACION = "permiso_circulacion"
    # Funcionario verification types
    MATRICULA_FUNCIONARIO = "matricula_funcionario"
    NUMERO_NOMBRAMIENTO = "numero_nombramiento"
    CARNET_FUNCIONARIO = "carnet_funcionario"
    # Social security (from migration 081)
    NUMERO_SEGURIDAD_SOCIAL = "numero_seguridad_social"
    # Nota de Ingreso (Residencia Phase 2)
    NUMERO_NOTA = "numero_nota"


class VerificationSource(str, Enum):
    """External sources for verification."""
    CNEDOGE = "cnedoge"
    TRAFICO = "trafico"
    HACIENDA = "hacienda"
    ORNC = "ornc"
    REGISTRO_CIVIL = "registro_civil"
    REGISTRO_VEHICULOS = "registro_vehiculos"
    MINISTERIO_FUNCION_PUBLICA = "ministerio_funcion_publica"
    AGENT_MANUAL = "agent_manual"
    API_INTEGRATION = "api_integration"
    # Social security (from migration 081)
    SEGURIDAD_SOCIAL = "seguridad_social"


class VerificationStatus(str, Enum):
    """Status of verification for a service request."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    VERIFIED = "verified"
    PARTIAL_VERIFICATION = "partial_verification"
    NOT_FOUND = "not_found"
    VERIFIED_MANUALLY = "verified_manually"
    VERIFICATION_FAILED = "verification_failed"


# =============================================================================
# CREATE / IMPORT MODELS
# =============================================================================

class VerifiedIdentifierCreate(BaseModel):
    """Model for creating a verified identifier."""
    identifier: str = Field(..., description="The identifier value (e.g., DIP number)")
    identifier_type: IdentifierType = Field(..., description="Type of identifier")
    source: VerificationSource = Field(..., description="Source of verification")
    expires_at: Optional[datetime] = Field(None, description="When the identifier expires")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class BatchImportRequest(BaseModel):
    """Model for batch import request."""
    source: VerificationSource = Field(..., description="Source of identifiers")
    identifier_type: IdentifierType = Field(..., description="Type of identifiers")


class BatchImportRecord(BaseModel):
    """Single record in batch import."""
    identifier: str
    expires_at: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class BatchImportResult(BaseModel):
    """Result of batch import operation."""
    total: int = Field(..., description="Total records in import file")
    imported: int = Field(..., description="Successfully imported records")
    skipped: int = Field(0, description="Skipped records (duplicates)")
    errors: List[Dict[str, str]] = Field(default_factory=list, description="Error details")

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total == 0:
            return 0.0
        return (self.imported / self.total) * 100


# =============================================================================
# VERIFICATION RESULT MODELS
# =============================================================================

class VerificationResult(BaseModel):
    """Result of verifying a single identifier."""
    verified: bool = Field(..., description="Whether identifier was found and valid")
    source: Optional[str] = Field(None, description="Source of verification if found")
    verified_at: Optional[datetime] = Field(None, description="When the identifier was verified")
    expires_at: Optional[datetime] = Field(None, description="Expiration date of identifier")
    reason: Optional[str] = Field(None, description="Reason if not verified (not_found, expired)")
    document_code: Optional[str] = Field(None, description="Document code that was checked")
    is_required: bool = Field(True, description="Whether this verification is required")


class ServiceRequestVerificationResult(BaseModel):
    """Complete verification result for a service request."""
    request_id: str
    status: VerificationStatus
    results: Dict[str, VerificationResult] = Field(
        default_factory=dict,
        description="Results per identifier type"
    )
    errors: List[Dict[str, str]] = Field(default_factory=list)
    verified_at: Optional[datetime] = None


# =============================================================================
# MANUAL VERIFICATION MODELS
# =============================================================================

class ManualVerificationRequest(BaseModel):
    """Request to manually verify a service request."""
    notes: Optional[str] = Field(None, max_length=500, description="Agent notes for manual verification")
    identifier_types: Optional[List[IdentifierType]] = Field(
        None,
        description="Specific identifier types to verify manually. If None, verifies all."
    )


class ReVerificationRequest(BaseModel):
    """Request to re-verify a service request."""
    reason: Optional[str] = Field(None, max_length=500, description="Reason for re-verification")


# =============================================================================
# RESPONSE MODELS
# =============================================================================

class VerifiedIdentifierResponse(BaseModel):
    """Response model for verified identifier (without sensitive data)."""
    id: str
    identifier_type: IdentifierType
    source: VerificationSource
    verified_at: datetime
    expires_at: Optional[datetime]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class VerificationConfigResponse(BaseModel):
    """Response model for document verification configuration."""
    id: str
    document_code: str
    identifier_type: IdentifierType
    extraction_paths: List[str]
    source: VerificationSource
    is_required: bool
    normalization_regex: Optional[str]
    is_active: bool

    class Config:
        from_attributes = True


class VerificationStatsResponse(BaseModel):
    """Statistics about verified identifiers."""
    total_identifiers: int
    by_type: Dict[str, int]
    by_source: Dict[str, int]
    active_count: int
    expired_count: int
    expiring_soon: int  # Expiring in next 30 days


class VerificationQueueStats(BaseModel):
    """Statistics about verification queue."""
    pending: int
    processing: int
    completed: int
    failed: int
    avg_retry_count: float


# =============================================================================
# DASHBOARD MODELS
# =============================================================================

class VerificationDashboardItem(BaseModel):
    """Item for verification dashboard view."""
    request_id: str
    request_reference: str
    workflow_code: str
    verification_status: VerificationStatus
    verification_details: Optional[Dict[str, Any]]
    queue_status: Optional[str]
    retry_count: int = 0
    error_message: Optional[str]
    user_name: Optional[str]
    user_email: Optional[str]
    request_created_at: datetime
