"""
User Documents Module Models — Pydantic v2 models

Coffre-fort documentaire: personal document vault for citizens.
Handles upload, classification (Gemini AI), expiry tracking,
workflow readiness checks, and generated documents.

Tables: user_documents, user_document_workflow_tags,
        user_document_access_log, user_document_alerts,
        user_agent_memory, user_agent_permissions
"""

from datetime import date, datetime
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ============================================================================
# TYPE ALIASES (Literal unions — lightweight alternative to str Enum)
# ============================================================================

DocumentSource = Literal["personal", "wizard_import", "platform_generated"]

DocumentCategory = Literal[
    "identity",
    "vehicle",
    "legal",
    "financial",
    "administrative",
    "medical",
    "education",
    "photo",
    "business",
    "employment",
    "other",
]

DocumentStatus = Literal["active", "archived", "expired", "deleted"]

ExtractionStatus = Literal["pending", "processing", "completed", "failed"]

ClassificationMethod = Literal["manual", "gemini", "rules"]

AlertType = Literal[
    "expiry_warning",
    "expiry_critical",
    "expired",
    "renewal_suggestion",
    "duplicate_detected",
    "missing_for_workflow",
]

AlertSeverity = Literal["info", "warning", "critical"]

GenerationType = Literal[
    "receipt",
    "payment_receipt",
    "certificate",
    "attestation",
    "summary",
    "request_summary",
    "confirmation",
]

BulkAction = Literal["archive", "delete", "download"]

ExpiryStatus = Literal["valid", "expiring_soon", "expired", "no_expiry"]

ReadinessStatus = Literal["ready", "expiring", "missing"]


# ============================================================================
# CONFIGURATION CONSTANTS
# ============================================================================

VAULT_QUOTA_BYTES: int = 100 * 1024 * 1024  # 100 Mo
MAX_FILE_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 Mo
MAX_BULK_UPLOAD: int = 5
SIGNED_URL_EXPIRY_SECONDS: int = 900  # 15 min
ALLOWED_MIME_TYPES: List[str] = [
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp",
]


# ============================================================================
# REQUEST MODELS
# ============================================================================

class UserDocumentUpload(BaseModel):
    """Request body for document upload endpoint.

    The file itself is sent as multipart form-data;
    these fields are the optional metadata sent alongside.
    """

    document_type_hint: Optional[str] = Field(
        None,
        max_length=100,
        description=(
            "Optional hint for the document type (e.g. 'passport', 'national_id'). "
            "If omitted, Gemini classification will determine the type."
        ),
    )
    notes: Optional[str] = Field(
        None,
        max_length=1000,
        description="Free-text notes attached to the document by the user.",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "document_type_hint": "passport",
                "notes": "Mon passeport biométrique GE, renouvelé en 2025.",
            }
        }
    )


class UserDocumentUpdate(BaseModel):
    """Request body for updating document metadata.

    Only non-None fields are applied (partial update).
    """

    display_name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=255,
        description="User-facing display name for the document.",
    )
    notes: Optional[str] = Field(
        None,
        max_length=1000,
        description="Free-text notes.",
    )
    color_label: Optional[str] = Field(
        None,
        max_length=30,
        description="Color label for UI grouping (e.g. 'blue', 'red', 'green').",
    )
    category: Optional[DocumentCategory] = Field(
        None,
        description="Document category override.",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "display_name": "Pasaporte Juan 2025",
                "notes": "Renouvelé le 15 mars 2025",
                "color_label": "blue",
                "category": "identity",
            }
        }
    )


class UserDocumentBulkAction(BaseModel):
    """Request body for bulk operations on multiple documents."""

    action: BulkAction = Field(
        ...,
        description="The bulk action to perform: archive, delete, or download.",
    )
    document_ids: List[UUID] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="List of document IDs to apply the action to.",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "action": "archive",
                "document_ids": [
                    "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                    "b2c3d4e5-f6a7-8901-bcde-f12345678901",
                ],
            }
        }
    )


# ============================================================================
# RESPONSE MODELS
# ============================================================================

class UserDocumentResponse(BaseModel):
    """Full document detail response — all DB columns plus computed fields."""

    # Primary identifiers
    id: UUID = Field(..., description="Document unique identifier.")
    user_id: UUID = Field(..., description="Owner user ID.")

    # Core metadata
    document_type: str = Field(..., description="Classified document type code.")
    category: DocumentCategory = Field(..., description="Document category.")
    source: DocumentSource = Field(..., description="How the document entered the vault.")
    status: DocumentStatus = Field("active", description="Current document status.")

    # File information
    file_name: str = Field(..., description="Original uploaded file name.")
    display_name: Optional[str] = Field(None, description="User-facing display name.")
    file_size_bytes: int = Field(..., description="File size in bytes.")
    mime_type: str = Field(..., description="MIME type of the file.")
    file_hash: str = Field(..., description="SHA-256 hash for deduplication.")
    thumbnail_path: Optional[str] = Field(None, description="Path to generated thumbnail.")

    # Classification
    classification_method: Optional[ClassificationMethod] = Field(
        None, description="How the type was determined."
    )
    classification_confidence: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="AI classification confidence (0-1)."
    )

    # OCR / Extraction
    extraction_status: ExtractionStatus = Field(
        "pending", description="Status of AI data extraction."
    )
    extraction_confidence: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="AI extraction confidence (0-1)."
    )
    extracted_data: Optional[Dict[str, Any]] = Field(
        None, description="Structured data extracted by Gemini."
    )

    # Identity fields (denormalized from extraction_data)
    holder_name: Optional[str] = Field(None, description="Document holder name.")
    document_number: Optional[str] = Field(None, description="Document number (e.g. DIP number).")
    issuing_authority: Optional[str] = Field(None, description="Issuing authority.")

    # Expiry tracking
    expiry_date: Optional[date] = Field(None, description="Document expiry date.")
    issue_date: Optional[date] = Field(None, description="Document issue date.")

    # User metadata
    notes: Optional[str] = Field(None, description="User notes.")
    color_label: Optional[str] = Field(None, description="Color label for UI.")
    is_verified: bool = Field(False, description="Whether the document has been verified by an agent.")

    # Source tracking
    source_request_id: Optional[UUID] = Field(
        None, description="Service request that imported this document (wizard_import)."
    )

    # Computed fields (not stored in DB, calculated at query time)
    days_until_expiry: Optional[int] = Field(
        None,
        description="Days until expiry (negative = expired). None if no expiry date.",
    )
    expiry_status: ExpiryStatus = Field(
        "no_expiry",
        description="Computed expiry status: valid, expiring_soon, expired, no_expiry.",
    )
    workflow_tags: List[str] = Field(
        default_factory=list,
        description="Workflow codes where this document can be used.",
    )

    # Timestamps
    created_at: datetime = Field(..., description="Upload timestamp.")
    updated_at: Optional[datetime] = Field(None, description="Last modification timestamp.")

    model_config = ConfigDict(from_attributes=True)


class UserDocumentListItem(BaseModel):
    """Lightweight document representation for list views.

    Contains only the fields needed to render a card / row in the vault UI.
    """

    id: UUID
    document_type: str
    category: DocumentCategory
    file_name: str
    display_name: Optional[str] = None
    expiry_date: Optional[date] = None
    days_until_expiry: Optional[int] = None
    expiry_status: ExpiryStatus = "no_expiry"
    status: DocumentStatus = "active"
    source: DocumentSource = "personal"
    is_verified: bool = False
    workflow_tags: List[str] = Field(default_factory=list)
    thumbnail_path: Optional[str] = None
    mime_type: str = "application/octet-stream"
    file_size_bytes: int = 0
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserDocumentListResponse(BaseModel):
    """Paginated document list with cursor-based pagination and quota info."""

    items: List[UserDocumentListItem] = Field(
        ..., description="Page of document items."
    )
    next_cursor: Optional[str] = Field(
        None,
        description="Opaque cursor for the next page. None if this is the last page.",
    )
    total_count: int = Field(..., ge=0, description="Total documents matching filter.")
    quota_used_bytes: int = Field(
        ..., ge=0, description="Total storage used by user (bytes)."
    )
    quota_max_bytes: int = Field(
        VAULT_QUOTA_BYTES,
        description="Maximum storage quota (bytes).",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [],
                "next_cursor": "eyJpZCI6ICIuLi4ifQ==",
                "total_count": 42,
                "quota_used_bytes": 15_728_640,
                "quota_max_bytes": 104_857_600,
            }
        }
    )


class UserDocumentStats(BaseModel):
    """Aggregate statistics for the user's document vault."""

    total_active: int = Field(0, ge=0, description="Total active documents.")
    personal_count: int = Field(0, ge=0, description="Documents uploaded manually.")
    wizard_count: int = Field(0, ge=0, description="Documents imported from wizard sessions.")
    generated_count: int = Field(0, ge=0, description="Documents generated by the platform.")

    quota_used_bytes: int = Field(0, ge=0, description="Storage used (bytes).")
    quota_max_bytes: int = Field(
        VAULT_QUOTA_BYTES, description="Storage quota limit (bytes)."
    )
    quota_percentage: float = Field(
        0.0,
        ge=0.0,
        le=100.0,
        description="Percentage of quota used.",
    )

    expired_count: int = Field(0, ge=0, description="Documents with passed expiry date.")
    expiring_count: int = Field(
        0, ge=0, description="Documents expiring within 30 days."
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_active": 12,
                "personal_count": 8,
                "wizard_count": 3,
                "generated_count": 1,
                "quota_used_bytes": 15_728_640,
                "quota_max_bytes": 104_857_600,
                "quota_percentage": 15.0,
                "expired_count": 1,
                "expiring_count": 2,
            }
        }
    )


# ============================================================================
# READINESS MODELS (workflow-readiness check)
# ============================================================================

class ReadinessItem(BaseModel):
    """Readiness status of a single required document for a workflow."""

    code: str = Field(
        ..., description="Document type code (e.g. 'passport', 'national_id')."
    )
    name: str = Field(
        ..., description="Human-readable document name (localized)."
    )
    status: ReadinessStatus = Field(
        ..., description="ready = valid doc exists, expiring = <30d, missing = not found."
    )
    days_until_expiry: Optional[int] = Field(
        None,
        description="Days until the matched document expires. None if missing or no expiry.",
    )
    # Phase 2: vault document reference for auto-fill
    vault_document_id: Optional[UUID] = Field(
        None,
        description="ID of the matching vault document (for auto-fill in wizard).",
    )
    vault_display_name: Optional[str] = Field(
        None,
        description="Display name of the matching vault document.",
    )
    vault_file_name: Optional[str] = Field(
        None,
        description="File name of the matching vault document.",
    )

    model_config = ConfigDict(from_attributes=True)


class ReadinessResult(BaseModel):
    """Readiness assessment for a specific workflow.

    Tells the user whether they have all required documents
    to start a service request.
    """

    workflow_code: str = Field(
        ..., description="Workflow code (e.g. 'PASAPORTE_BIOMETRICO')."
    )
    readiness_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Percentage of required documents available and valid.",
    )
    total_required: int = Field(
        ..., ge=0, description="Total number of documents required."
    )
    available: int = Field(
        ..., ge=0, description="Number of required documents available in vault."
    )
    missing_count: int = Field(
        ..., ge=0, description="Number of missing required documents."
    )

    ready: List[ReadinessItem] = Field(
        default_factory=list,
        description="Documents that are available and valid.",
    )
    missing: List[ReadinessItem] = Field(
        default_factory=list,
        description="Documents that are missing from the vault.",
    )
    expiring: List[ReadinessItem] = Field(
        default_factory=list,
        description="Documents that are available but expiring within 30 days.",
    )

    can_start: bool = Field(
        ...,
        description="True if all required documents are present (even if some are expiring).",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "workflow_code": "PASAPORTE_BIOMETRICO",
                "readiness_score": 75.0,
                "total_required": 4,
                "available": 3,
                "missing_count": 1,
                "ready": [
                    {"code": "national_id", "name": "DIP", "status": "ready", "days_until_expiry": 365},
                ],
                "missing": [
                    {"code": "birth_certificate", "name": "Acta de nacimiento", "status": "missing", "days_until_expiry": None},
                ],
                "expiring": [
                    {"code": "photo", "name": "Photo d'identité", "status": "expiring", "days_until_expiry": 15},
                ],
                "can_start": False,
            }
        }
    )


# ============================================================================
# GENERATED DOCUMENT MODELS
# ============================================================================

class GeneratedDocumentResponse(BaseModel):
    """Response for a platform-generated document (receipt, certificate, etc.)."""

    id: UUID = Field(..., description="Document ID.")
    generation_type: GenerationType = Field(
        ..., description="Type of generated document."
    )
    title: str = Field("", description="Document title (primary).")
    title_es: Optional[str] = Field(None, description="Title in Spanish.")
    title_fr: Optional[str] = Field(None, description="Title in French.")
    title_en: Optional[str] = Field(None, description="Title in English.")
    reference_number: Optional[str] = Field(
        None, description="Official reference number."
    )
    file_name: str = Field(..., description="Generated file name.")
    created_at: datetime = Field(..., description="Generation timestamp.")
    service_request_id: Optional[UUID] = Field(
        None, description="Related service request, if any."
    )
    verification_code: Optional[str] = Field(
        None,
        description="QR / verification code for document authenticity check.",
    )

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# ALERT MODELS
# ============================================================================

class AlertResponse(BaseModel):
    """Response for a document alert (expiry warning, renewal, etc.)."""

    id: UUID = Field(..., description="Alert unique identifier.")
    alert_type: AlertType = Field(..., description="Type of alert.")
    severity: AlertSeverity = Field(..., description="Alert severity level.")
    title: str = Field("", description="Alert title (primary/fallback).")
    title_es: Optional[str] = Field(None, description="Title in Spanish.")
    title_fr: Optional[str] = Field(None, description="Title in French.")
    title_en: Optional[str] = Field(None, description="Title in English.")
    message: str = Field("", description="Alert body message (primary/fallback).")
    message_es: Optional[str] = Field(None, description="Message in Spanish.")
    message_fr: Optional[str] = Field(None, description="Message in French.")
    message_en: Optional[str] = Field(None, description="Message in English.")
    suggested_action: Optional[str] = Field(
        None,
        description="Suggested action label (e.g. 'Renew now', 'Upload replacement').",
    )
    action_params: Optional[Dict[str, Any]] = Field(
        None,
        description="Parameters for the action (e.g. workflow_code, document_id).",
    )
    is_read: bool = Field(False, description="Whether the user has read this alert.")
    is_dismissed: bool = Field(False, description="Whether the user dismissed this alert.")
    trigger_date: Optional[date] = Field(
        None, description="Date that triggered the alert (e.g. expiry date)."
    )
    created_at: datetime = Field(..., description="Alert creation timestamp.")

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# UPLOAD RESULT
# ============================================================================

class DuplicateInfo(BaseModel):
    """Information about a detected duplicate document."""

    existing_document_id: UUID = Field(
        ..., description="ID of the existing document with the same hash."
    )

    model_config = ConfigDict(from_attributes=True)


class UploadResult(BaseModel):
    """Response returned after a document upload attempt.

    Status meanings:
    - 'processing': New document uploaded, Gemini classification running async.
    - 'duplicate': Identical file already in vault. No new upload performed.
      The `id` points to the existing document.
    """

    id: UUID = Field(..., description="Document ID (new or existing if duplicate).")
    status: Literal["processing", "duplicate"] = Field(
        "processing",
        description="'processing' = new upload, 'duplicate' = reused existing.",
    )
    file_name: str = Field(..., description="Original file name as uploaded.")
    file_size_bytes: int = Field(..., ge=0, description="File size in bytes.")
    duplicate: Optional[DuplicateInfo] = Field(
        None,
        description="Populated when a duplicate hash was detected.",
    )
    archived_count: int = Field(
        0,
        ge=0,
        description="Number of older versions of the same document type that were auto-archived.",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "c4d5e6f7-a8b9-0123-cdef-456789abcdef",
                "status": "processing",
                "file_name": "pasaporte_scan.pdf",
                "file_size_bytes": 1_258_291,
                "duplicate": None,
                "archived_count": 0,
            }
        }
    )
