/**
 * Documents Module Types
 * Type definitions for document management (upload, OCR, extraction, validation)
 *
 * @module documents/types
 * @author Claude Code
 * @date 2025-11-26
 *
 * BACKEND ALIGNMENT:
 * - Schemas from: app/modules/documents/models/document.py
 * - Routes from: app/modules/documents/api/document_routes.py
 */

// =============================================================================
// ENUMS
// =============================================================================

/**
 * Document processing modes
 * BACKEND: DocumentProcessingMode enum
 */
export type DocumentProcessingMode =
  | 'server_processing' // Server-side OCR (Tesseract)
  | 'lite_mode' // Lightweight processing
  | 'cloud_vision'; // Google Cloud Vision API

/**
 * OCR processing status
 * BACKEND: DocumentOCRStatus enum
 */
export type DocumentOCRStatus =
  | 'pending'
  | 'processing'
  | 'completed'
  | 'failed';

/**
 * Data extraction status
 * BACKEND: DocumentExtractionStatus enum
 */
export type DocumentExtractionStatus =
  | 'pending'
  | 'processing'
  | 'completed'
  | 'failed';

/**
 * Document validation status
 * BACKEND: DocumentValidationStatus enum
 */
export type DocumentValidationStatus =
  | 'pending'
  | 'validated'
  | 'rejected';

/**
 * Document access level
 * BACKEND: DocumentAccessLevel enum
 */
export type DocumentAccessLevel =
  | 'private'
  | 'shared'
  | 'public';

/**
 * Document types
 * BACKEND: DocumentType enum (fiscal declarations + generic types)
 */
export type DocumentType =
  // Fiscal declarations
  | 'declaration_iva'
  | 'declaration_retencion'
  | 'declaration_cuota_min'
  | 'declaration_petroliferos'
  | 'declaration_sueldos'
  | 'declaration_irpf'
  // Services
  | 'fiscal_service'
  | 'nota_ingreso'
  // Identity
  | 'passport'
  | 'national_id'
  | 'nif_card'
  | 'residence_permit'
  // Business
  | 'business_registration'
  | 'tax_id_certificate'
  | 'business_license'
  | 'company_statutes'
  // Financial
  | 'payslip'
  | 'bank_statement'
  | 'invoice'
  | 'tax_return'
  | 'balance_sheet'
  | 'profit_loss_statement'
  // Support
  | 'proof_of_address'
  | 'contract'
  | 'certificate'
  | 'birth_certificate'
  | 'receipt'
  // Generic
  | 'other';

/**
 * Document subtypes (for fiscal declarations)
 * BACKEND: DocumentSubtype enum
 */
export type DocumentSubtype =
  // IVA
  | 'iva_destajo'
  | 'iva_real'
  // Retención
  | 'retencion_3pct_petrolero'
  | 'retencion_5pct_petrolero'
  | 'retencion_10pct_comun'
  | 'retencion_10pct_petrolero'
  // Cuota Mínima
  | 'cuota_min_comun'
  | 'cuota_min_petrolera'
  // Productos Petroleros
  | 'petroliferos_fmi'
  | 'petroliferos_ivs'
  // Sueldos
  | 'sueldos_comun'
  | 'sueldos_petrolero';

// =============================================================================
// DOCUMENT MODEL
// =============================================================================

/**
 * Document entity
 * BACKEND: DocumentResponse in document.py
 */
export interface Document {
  id: string;
  user_id: string;
  original_filename: string;
  document_type: DocumentType;
  document_subtype?: string;
  description?: string;

  // File info
  file_path: string;
  file_url: string;
  file_size_bytes: number;
  mime_type: string;
  file_hash: string;

  // Processing
  processing_mode: DocumentProcessingMode;
  ocr_status: DocumentOCRStatus;
  extraction_status: DocumentExtractionStatus;
  validation_status: DocumentValidationStatus;

  // OCR results
  ocr_text?: string;
  ocr_confidence?: number;
  ocr_provider?: string;

  // Extraction results
  extracted_data?: Record<string, unknown>;
  extraction_confidence?: number;
  field_confidences?: Record<string, number>;

  // Form mapping
  form_mapping?: Record<string, unknown>;

  // Relationships
  related_to_type?: string;
  related_to_id?: string;

  // Access
  access_level: DocumentAccessLevel;

  // Timestamps
  processing_started_at?: string;
  processing_completed_at?: string;
  processing_duration_ms?: number;
  uploaded_at: string;
  updated_at: string;

  // Computed fields (from DocumentResponse)
  processing_status?: string;
  can_retry?: boolean;
  next_actions?: Array<{ action: string; url: string }>;
}

// =============================================================================
// REQUEST/RESPONSE TYPES
// =============================================================================

/**
 * Document upload options
 */
export interface DocumentUploadOptions {
  document_type?: DocumentType;
  document_subtype?: DocumentSubtype;
  processing_mode?: DocumentProcessingMode;
  auto_process?: boolean;
  metadata?: Record<string, unknown>;
  // Phase 2 support
  type_compte?: string;
  fiscal_service_id?: string;
  declaration_id?: string;
}

/**
 * Upload response
 * BACKEND: DocumentResponse
 */
export interface DocumentUploadResponse extends Document {
  message?: string;
}

/**
 * Paginated documents response
 * BACKEND: DocumentListResponse
 */
export interface DocumentListResponse {
  documents: Document[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

/**
 * Document search filters
 * BACKEND: DocumentSearchFilter
 */
export interface DocumentSearchFilter {
  user_id?: string;
  document_type?: DocumentType;
  document_subtype?: string;
  processing_status?: string;
  ocr_status?: DocumentOCRStatus;
  extraction_status?: DocumentExtractionStatus;
  validation_status?: DocumentValidationStatus;
  date_from?: string;
  date_to?: string;
  page?: number;
  size?: number;
}

/**
 * OCR result
 * BACKEND: OCRResult from ocr_service.py
 */
export interface OCRResult {
  success: boolean;
  text: string;
  confidence: number;
  word_confidences?: Array<{ word: string; confidence: number }>;
  processing_time_ms: number;
  provider: string;
  language?: string;
  errors: string[];
  metadata?: Record<string, unknown>;
}

/**
 * Extraction result
 * BACKEND: ExtractionResult from extraction_service.py
 */
export interface ExtractionResult {
  success: boolean;
  data: Record<string, unknown>;
  confidence: number;
  field_confidences: Record<string, number>;
  processing_time_ms: number;
  errors: string[];
  warnings: string[];
  metadata?: Record<string, unknown>;
}

/**
 * Processing statistics
 * BACKEND: DocumentProcessingStats
 */
export interface DocumentProcessingStats {
  total_documents: number;
  pending_ocr: number;
  completed_ocr: number;
  failed_ocr: number;
  pending_extraction: number;
  completed_extraction: number;
  avg_processing_time_ms?: number;
  avg_ocr_confidence?: number;
  avg_extraction_confidence?: number;
  documents_by_type: Record<string, number>;
}
