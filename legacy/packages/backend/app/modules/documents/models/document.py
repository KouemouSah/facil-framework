"""
📄 Document Models - Pydantic Schemas
Models for document management, OCR, and extraction
Aligned with uploaded_files and ocr_extraction_results tables

Author: Claude Code
Date: 2025-11-13
Version: 2.0 - Reorganized with core/documents/
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
from uuid import UUID
from pydantic import BaseModel, Field, validator


# ============================================================================
# ENUMS
# ============================================================================

class DocumentProcessingMode(str, Enum):
    """Document processing modes"""
    server_processing = "server_processing"  # Server-side OCR (Tesseract)
    lite_mode = "lite_mode"  # Lightweight processing
    cloud_vision = "cloud_vision"  # Google Cloud Vision API


class DocumentOCRStatus(str, Enum):
    """OCR processing status"""
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class DocumentExtractionStatus(str, Enum):
    """Data extraction status"""
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class DocumentValidationStatus(str, Enum):
    """Document validation status"""
    pending = "pending"
    validated = "validated"
    rejected = "rejected"


class DocumentAccessLevel(str, Enum):
    """Document access levels"""
    private = "private"
    shared = "shared"
    public = "public"


class DocumentSubtype(str, Enum):
    """
    Common document subtypes for fiscal declarations
    Used with DocumentType for specific variations
    """
    # IVA subtypes
    iva_destajo = "destajo"
    iva_real = "real"

    # Retención subtypes
    retencion_3pct_petrolero = "3pct_petrolero"
    retencion_5pct_petrolero = "5pct_petrolero"
    retencion_10pct_comun = "10pct_comun"
    retencion_10pct_petrolero = "10pct_petrolero"

    # Cuota Mínima subtypes
    cuota_min_comun = "comun"
    cuota_min_petrolera = "petrolera"

    # Productos Petroleros subtypes
    petroliferos_fmi = "fmi"
    petroliferos_ivs = "ivs"

    # Sueldos subtypes
    sueldos_comun = "comun"
    sueldos_petrolero = "petrolero"


class DocumentType(str, Enum):
    """
    Supported document types (generics)
    Use document_subtype field for specific variations

    Examples:
    - declaration_iva + subtype="destajo" → IVA Destajo
    - declaration_iva + subtype="real" → IVA Real
    - declaration_retencion + subtype="3pct_petrolero" → Retención 3% Petrolífero

    See DocumentSubtype enum for common subtype values
    """
    # Déclarations fiscales (6 types génériques)
    declaration_iva = "declaration_iva"                      # Subtypes: destajo, real
    declaration_retencion = "declaration_retencion"          # Subtypes: 3pct_petrolero, 5pct_petrolero, 10pct_comun, 10pct_petrolero
    declaration_cuota_min = "declaration_cuota_min"          # Subtypes: comun, petrolera
    declaration_petroliferos = "declaration_petroliferos"    # Subtypes: fmi, ivs
    declaration_sueldos = "declaration_sueldos"              # Subtypes: comun, petrolero
    declaration_irpf = "declaration_irpf"                    # Generic IRPF (legacy, prefer declaration_retencion)

    # Services fiscaux (generic)
    fiscal_service = "fiscal_service"
    nota_ingreso = "nota_ingreso"

    # Documents identité (3)
    passport = "passport"
    national_id = "national_id"
    nif_card = "nif_card"
    residence_permit = "residence_permit"

    # Documents entreprise (4)
    business_registration = "business_registration"
    tax_id_certificate = "tax_id_certificate"
    business_license = "business_license"
    company_statutes = "company_statutes"

    # Documents financiers (6)
    payslip = "payslip"
    bank_statement = "bank_statement"
    invoice = "invoice"
    tax_return = "tax_return"
    balance_sheet = "balance_sheet"
    profit_loss_statement = "profit_loss_statement"

    # Documents support (5)
    proof_of_address = "proof_of_address"
    contract = "contract"
    certificate = "certificate"
    birth_certificate = "birth_certificate"
    receipt = "receipt"

    # Generic
    other = "other"


# ============================================================================
# SUBTYPE MAPPING REFERENCE
# ============================================================================
# Use this mapping to determine valid subtypes for each DocumentType:
#
# declaration_iva:
#   - "destajo" (IVA al Destajo)
#   - "real" (IVA Real)
#
# declaration_retencion:
#   - "3pct_petrolero" (Retención 3% Sector Petrolero)
#   - "5pct_petrolero" (Retención 5% Sector Petrolero)
#   - "10pct_comun" (Retención 10% Sector Común)
#   - "10pct_petrolero" (Retención 10% Sector Petrolero)
#
# declaration_cuota_min:
#   - "comun" (Cuota Mínima Fiscal Sector Común)
#   - "petrolera" (Cuota Mínima Fiscal Sector Petrolero)
#
# declaration_petroliferos:
#   - "fmi" (Productos Petroleros FMI)
#   - "ivs" (Productos Petroleros IVS)
#
# declaration_sueldos:
#   - "comun" (Impuesto sobre Sueldos Sector Común)
#   - "petrolero" (Impuesto sobre Sueldos Sector Petrolero)


# ============================================================================
# BASE MODELS
# ============================================================================

class DocumentBase(BaseModel):
    """Base document fields"""
    user_id: UUID = Field(..., description="Document owner user ID")
    original_filename: str = Field(..., description="Original uploaded filename")
    document_type: DocumentType = Field(..., description="Document type classification")
    document_subtype: Optional[str] = Field(None, description="Document subtype for specialized handling")
    description: Optional[str] = Field(None, description="User-provided description")

    class Config:
        use_enum_values = True


class DocumentCreate(DocumentBase):
    """Schema for creating a new document"""
    file_path: str = Field(..., description="Firebase Storage path")
    file_url: str = Field(..., description="Public download URL")
    file_size_bytes: int = Field(..., description="File size in bytes")
    mime_type: str = Field(..., description="MIME type")
    file_hash: str = Field(..., description="SHA-256 file hash")
    processing_mode: DocumentProcessingMode = Field(
        default=DocumentProcessingMode.server_processing,
        description="OCR processing mode"
    )
    related_to_type: Optional[str] = Field(None, description="Related entity type (tax_declaration, payment)")
    related_to_id: Optional[UUID] = Field(None, description="Related entity ID")


class DocumentUpdate(BaseModel):
    """Schema for updating document metadata"""
    description: Optional[str] = None
    document_type: Optional[DocumentType] = None
    document_subtype: Optional[str] = None
    validation_status: Optional[DocumentValidationStatus] = None

    class Config:
        use_enum_values = True


class Document(DocumentBase):
    """Complete document model (from database)"""
    id: UUID = Field(..., description="Document unique identifier")
    file_path: str = Field(..., description="Firebase Storage path")
    file_url: str = Field(..., description="Public download URL")
    file_size_bytes: int = Field(..., description="File size in bytes")
    mime_type: str = Field(..., description="MIME type")
    file_hash: str = Field(..., description="SHA-256 file hash")

    # Processing status
    processing_mode: DocumentProcessingMode
    ocr_status: DocumentOCRStatus = Field(default=DocumentOCRStatus.pending)
    extraction_status: DocumentExtractionStatus = Field(default=DocumentExtractionStatus.pending)
    validation_status: DocumentValidationStatus = Field(default=DocumentValidationStatus.pending)

    # OCR results
    ocr_text: Optional[str] = Field(None, description="Extracted OCR text")
    ocr_confidence: Optional[float] = Field(None, description="OCR confidence score (0-1)")
    ocr_provider: Optional[str] = Field(None, description="OCR provider used")

    # Extracted data
    extracted_data: Optional[Dict[str, Any]] = Field(None, description="Structured extracted data")
    extraction_confidence: Optional[float] = Field(None, description="Extraction confidence (0-1)")

    # Form mapping (NEW - for pre-fill)
    form_mapping: Optional[Dict[str, Any]] = Field(None, description="Form mapping for frontend pre-fill")

    # Relationships
    related_to_type: Optional[str] = None
    related_to_id: Optional[UUID] = None

    # Access control
    access_level: DocumentAccessLevel = Field(default=DocumentAccessLevel.private)

    # Metadata
    processing_started_at: Optional[datetime] = None
    processing_completed_at: Optional[datetime] = None
    processing_duration_ms: Optional[int] = None
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        use_enum_values = True
        orm_mode = True


# ============================================================================
# RESPONSE MODELS
# ============================================================================

class DocumentResponse(Document):
    """Document response with additional computed fields"""
    processing_status: Optional[str] = Field(None, description="Overall processing status")
    can_retry: Optional[bool] = Field(None, description="Whether processing can be retried")
    next_actions: Optional[List[Dict[str, str]]] = Field(None, description="Suggested next actions")

    class Config:
        use_enum_values = True


class DocumentListResponse(BaseModel):
    """Paginated document list response"""
    documents: List[DocumentResponse] = Field(..., description="List of documents")
    total: int = Field(..., description="Total count")
    page: int = Field(..., description="Current page")
    size: int = Field(..., description="Page size")
    pages: int = Field(..., description="Total pages")


# ============================================================================
# SEARCH & FILTER MODELS
# ============================================================================

class DocumentSearchFilter(BaseModel):
    """Document search filter"""
    user_id: Optional[UUID] = None
    document_type: Optional[DocumentType] = None
    document_subtype: Optional[str] = None
    processing_status: Optional[str] = None
    ocr_status: Optional[DocumentOCRStatus] = None
    extraction_status: Optional[DocumentExtractionStatus] = None
    validation_status: Optional[DocumentValidationStatus] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=100)

    class Config:
        use_enum_values = True


# ============================================================================
# PROCESSING REQUEST MODELS
# ============================================================================

class OCRRequest(BaseModel):
    """Request to run OCR on a document"""
    document_id: UUID = Field(..., description="Document ID to process")
    force_reprocess: bool = Field(default=False, description="Force reprocessing even if already done")
    provider: Optional[str] = Field(None, description="Specific OCR provider (tesseract, google_vision)")


class ExtractionRequest(BaseModel):
    """Request to extract structured data"""
    document_id: UUID = Field(..., description="Document ID to extract from")
    force_reprocess: bool = Field(default=False, description="Force re-extraction")
    enable_form_mapping: bool = Field(default=True, description="Enable form mapping for pre-fill")


class ValidationRequest(BaseModel):
    """Request to validate document data"""
    document_id: UUID = Field(..., description="Document ID to validate")
    validation_rules: Optional[Dict[str, Any]] = Field(None, description="Custom validation rules")


# ============================================================================
# STATISTICS MODELS
# ============================================================================

class DocumentProcessingStats(BaseModel):
    """Document processing statistics"""
    total_documents: int = Field(..., description="Total documents uploaded")
    pending_ocr: int = Field(..., description="Documents pending OCR")
    completed_ocr: int = Field(..., description="Documents with completed OCR")
    failed_ocr: int = Field(..., description="Documents with failed OCR")
    pending_extraction: int = Field(..., description="Documents pending extraction")
    completed_extraction: int = Field(..., description="Documents with completed extraction")
    avg_processing_time_ms: Optional[float] = Field(None, description="Average processing time")
    avg_ocr_confidence: Optional[float] = Field(None, description="Average OCR confidence")
    avg_extraction_confidence: Optional[float] = Field(None, description="Average extraction confidence")
    documents_by_type: Dict[str, int] = Field(default_factory=dict, description="Count by document type")
