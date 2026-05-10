"""
Document Services for TaxasGE Backend
Business logic for document processing (OCR, extraction, validation)

Services:
- OCRService: Tesseract and Google Document AI OCR processing
  - Tesseract: Free OCR for simple documents
  - Google Document AI: Premium AI with FORM_PARSER processor ONLY
    * Universal form field extraction (key-value pairs)
    * Works for ALL document types: IVA, IRPF, invoices, receipts, tax forms
    * Automatic field detection (no document-specific logic needed)

- DocumentService: Document processing orchestration (upload → OCR → extraction → validation)
  - Coordinates StorageService + OCRService
  - Full pipeline with queue management

- StorageService: Firebase Storage (GCP) integration
  - Follows storage.rules bucket structure
  - Path types: user-documents, profile-pictures, temp-uploads, etc.
  - Metadata and size validation (5MB docs, 2MB images)

Project: taxasge-dev (dev), taxasge-pro (prod)
"""

from app.modules.documents.services.ocr_service import (
    OCRService, OCRResult, OCRConfig, ocr_service
)
from app.modules.documents.services.document_service import DocumentService
from app.modules.documents.services.storage_service import (
    FirebaseStorageService, UploadResult, DownloadResult, StorageConfig,
    firebase_storage_service, storage_service, get_taxasge_folder_info
)
from app.modules.documents.services.extraction_service import (
    ExtractionService, ExtractionResult, extraction_service
)

__all__ = [
    # OCR Service (REAL implementation)
    "OCRService", "OCRResult", "OCRConfig", "ocr_service",
    # Document Service
    "DocumentService",
    # Storage Service (REAL implementation)
    "FirebaseStorageService", "UploadResult", "DownloadResult", "StorageConfig",
    "firebase_storage_service", "storage_service", "get_taxasge_folder_info",
    # Extraction Service (REAL implementation)
    "ExtractionService", "ExtractionResult", "extraction_service"
]
