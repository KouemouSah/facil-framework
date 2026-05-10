"""User Documents Models — re-exports for convenient imports."""

from app.modules.user_documents.models.user_document import (
    # Type aliases
    AlertSeverity,
    AlertType,
    BulkAction,
    ClassificationMethod,
    DocumentCategory,
    DocumentSource,
    DocumentStatus,
    ExpiryStatus,
    ExtractionStatus,
    GenerationType,
    ReadinessStatus,
    # Constants
    ALLOWED_MIME_TYPES,
    MAX_BULK_UPLOAD,
    MAX_FILE_SIZE_BYTES,
    SIGNED_URL_EXPIRY_SECONDS,
    VAULT_QUOTA_BYTES,
    # Request models
    UserDocumentBulkAction,
    UserDocumentUpdate,
    UserDocumentUpload,
    # Response models
    AlertResponse,
    DuplicateInfo,
    GeneratedDocumentResponse,
    ReadinessItem,
    ReadinessResult,
    UploadResult,
    UserDocumentListItem,
    UserDocumentListResponse,
    UserDocumentResponse,
    UserDocumentStats,
)

__all__ = [
    # Type aliases
    "AlertSeverity",
    "AlertType",
    "BulkAction",
    "ClassificationMethod",
    "DocumentCategory",
    "DocumentSource",
    "DocumentStatus",
    "ExpiryStatus",
    "ExtractionStatus",
    "GenerationType",
    "ReadinessStatus",
    # Constants
    "ALLOWED_MIME_TYPES",
    "MAX_BULK_UPLOAD",
    "MAX_FILE_SIZE_BYTES",
    "SIGNED_URL_EXPIRY_SECONDS",
    "VAULT_QUOTA_BYTES",
    # Request models
    "UserDocumentBulkAction",
    "UserDocumentUpdate",
    "UserDocumentUpload",
    # Response models
    "AlertResponse",
    "DuplicateInfo",
    "GeneratedDocumentResponse",
    "ReadinessItem",
    "ReadinessResult",
    "UploadResult",
    "UserDocumentListItem",
    "UserDocumentListResponse",
    "UserDocumentResponse",
    "UserDocumentStats",
]
