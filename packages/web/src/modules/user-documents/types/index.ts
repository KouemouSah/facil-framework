/**
 * User Documents Module Types
 * Type definitions for the citizen document vault (coffre-fort documentaire)
 *
 * @module user-documents/types
 * @date 2026-04-05
 *
 * BACKEND ALIGNMENT:
 * - Schemas from: app/modules/user_documents/models/
 * - Routes from: app/modules/user_documents/api/user_document_routes.py
 * - Base URL: /api/v1/user-documents
 */

// =============================================================================
// ENUMS
// =============================================================================

/** Source of the document */
export type DocumentSource = 'personal' | 'wizard_import' | 'platform_generated';

/** Document classification category */
export type DocumentCategory =
  | 'identity'
  | 'vehicle'
  | 'legal'
  | 'financial'
  | 'administrative'
  | 'medical'
  | 'education'
  | 'photo'
  | 'business'
  | 'employment'
  | 'other';

/** Document lifecycle status */
export type DocumentStatus = 'active' | 'archived' | 'expired' | 'deleted';

/** OCR/AI extraction pipeline status */
export type ExtractionStatus = 'pending' | 'processing' | 'completed' | 'failed';

/** Computed expiry status based on expiry_date vs current date */
export type ExpiryStatus = 'valid' | 'expiring_soon' | 'expired' | 'no_expiry';

/** Alert severity levels */
export type AlertSeverity = 'info' | 'warning' | 'critical';

/** Bulk actions available on multiple documents */
export type BulkAction = 'archive' | 'delete' | 'download';

// =============================================================================
// MODELS
// =============================================================================

/**
 * Workflow tag linking a document to a workflow requirement
 */
export interface WorkflowTag {
  workflow_code: string;
  document_code: string;
  relevance_score: number;
}

/**
 * Full user document entity (detail view)
 * BACKEND: UserDocumentResponse
 */
export interface UserDocument {
  // Primary — matches backend UserDocumentResponse exactly
  id: string;
  user_id: string;
  document_type: string;
  category: DocumentCategory;
  source: DocumentSource;
  status: DocumentStatus;
  // File info
  file_name: string;
  display_name?: string;
  file_size_bytes: number;
  mime_type: string;
  file_hash: string;
  thumbnail_path?: string;
  // Classification
  classification_method?: string;
  classification_confidence?: number;
  // Extraction
  extraction_status: ExtractionStatus;
  extraction_confidence?: number;
  extracted_data?: Record<string, unknown>;
  // Identity (denormalized from extraction)
  holder_name?: string;
  document_number?: string;
  issuing_authority?: string;
  // Dates
  expiry_date?: string;
  issue_date?: string;
  // User metadata
  notes?: string;
  color_label?: string;
  is_verified: boolean;
  // Source tracking
  source_request_id?: string;
  // Computed
  days_until_expiry?: number;
  expiry_status?: ExpiryStatus;
  workflow_tags?: string[];
  // Timestamps
  created_at: string;
  updated_at?: string;
}

/**
 * Lightweight document item for list views
 * BACKEND: UserDocumentListItem
 */
export interface UserDocumentListItem {
  // Matches backend UserDocumentListItem exactly
  id: string;
  document_type: string;
  category: DocumentCategory;
  file_name: string;
  display_name?: string;
  expiry_date?: string;
  days_until_expiry?: number;
  expiry_status?: ExpiryStatus;
  status: DocumentStatus;
  source: DocumentSource;
  is_verified: boolean;
  workflow_tags?: string[];
  thumbnail_path?: string;
  mime_type: string;
  file_size_bytes: number;
  created_at: string;
}

/**
 * Paginated list response with cursor-based pagination and quota info
 * BACKEND: UserDocumentListResponse
 */
export interface UserDocumentListResponse {
  items: UserDocumentListItem[];
  next_cursor?: string;
  total_count: number;
  quota_used_bytes: number;
  quota_max_bytes: number;
}

/**
 * Aggregated document statistics for the vault dashboard
 * BACKEND: UserDocumentStats
 */
export interface UserDocumentStats {
  total_active: number;
  personal_count: number;
  wizard_count: number;
  generated_count: number;
  quota_used_bytes: number;
  quota_max_bytes: number;
  quota_percentage: number;
  expired_count: number;
  expiring_count: number;
}

/**
 * Single item in a workflow readiness check
 */
export interface ReadinessItem {
  code: string;
  name: string;
  status?: string;
  days_until_expiry?: number | null;
  /** @deprecated Use days_until_expiry */
  days?: number;
  // Phase 2: vault document reference for auto-fill
  vault_document_id?: string | null;
  vault_display_name?: string | null;
  vault_file_name?: string | null;
}

/**
 * Result of checking document readiness for a given workflow
 * BACKEND: ReadinessResult
 */
export interface ReadinessResult {
  workflow_code: string;
  readiness_score: number;
  total_required: number;
  available: number;
  missing_count: number;
  ready: ReadinessItem[];
  missing: ReadinessItem[];
  expiring: ReadinessItem[];
  can_start: boolean;
}

/**
 * Platform-generated document (certificates, receipts, etc.)
 * BACKEND: GeneratedDocumentItem
 */
export interface GeneratedDocument {
  id: string;
  generation_type: string;
  /** Primary title from backend */
  title?: string;
  title_es?: string;
  title_fr?: string;
  title_en?: string;
  reference_number?: string;
  file_name: string;
  file_size_bytes?: number;
  service_request_id?: string;
  verification_code?: string;
  created_at: string;
}

/**
 * Proactive alert for document expiry, missing requirements, etc.
 * BACKEND: DocumentAlert
 */
export interface DocumentAlert {
  // Matches backend AlertResponse exactly
  id: string;
  alert_type: string;
  severity: AlertSeverity;
  title: string;
  title_es?: string;
  title_fr?: string;
  title_en?: string;
  message: string;
  message_es?: string;
  message_fr?: string;
  message_en?: string;
  suggested_action?: string;
  action_params?: Record<string, unknown>;
  is_read: boolean;
  is_dismissed: boolean;
  trigger_date?: string;
  created_at: string;
}

/**
 * Upload result for a single file
 * BACKEND: UploadResult
 */
export interface UploadResult {
  id: string;
  status: 'processing' | 'duplicate';
  file_name: string;
  file_size_bytes: number;
  /** Populated when status='duplicate' — info about the existing document */
  duplicate?: { existing_document_id: string };
  /** @deprecated Use duplicate?.existing_document_id */
  existing_document_id?: string;
  /** Number of older versions auto-archived during upload */
  archived_count?: number;
}

/**
 * Export job status (for ZIP export polling)
 * BACKEND: ExportStatusResponse
 */
export interface ExportStatus {
  export_id: string;
  status: 'processing' | 'completed' | 'failed';
  file_path?: string;
  file_size?: number;
  document_count?: number;
  error?: string;
  updated_at: string;
}

// =============================================================================
// REQUEST TYPES
// =============================================================================

/**
 * Partial update payload for a user document
 * BACKEND: DocumentUpdateRequest
 */
export interface DocumentUpdateRequest {
  display_name?: string;
  notes?: string;
  color_label?: string;
  document_category?: DocumentCategory;
}

/**
 * Bulk action request payload
 * BACKEND: BulkActionRequest
 */
export interface BulkActionRequest {
  action: BulkAction;
  document_ids: string[];
}

// =============================================================================
// FILTER TYPES
// =============================================================================

/**
 * Query parameters for the document list endpoint
 */
export interface DocumentFilters {
  source?: DocumentSource;
  category?: DocumentCategory;
  status?: DocumentStatus;
  expiry_status?: ExpiryStatus;
  search?: string;
  cursor?: string;
  limit?: number;
  offset?: number;
}

// =============================================================================
// AGENT TYPES (Phase 2 - Behavioral Memory & Proactive Agent)
// =============================================================================

/**
 * Agent permission granting document-level actions
 * BACKEND: AgentPermissionResponse
 */
export interface AgentPermission {
  id: string;
  permission_type: string;
  scope?: string;
  level: number;
  usage_count: number;
  is_active: boolean;
  granted_at: string;
  last_used_at?: string;
}

/**
 * Single entry in the authoritative agent permission catalog returned
 * by `GET /user-documents/agent/permission-catalog`. This is the source
 * of truth — the frontend renders `AgentSettingsPanel` rows from this
 * list instead of a hardcoded array.
 *
 * `status === 'coming_soon'` → the permission exists in the BD schema
 * but no backend tool is wired to it yet; the UI renders a disabled
 * toggle with a "coming soon" badge to keep user trust.
 */
export interface AgentPermissionCatalogEntry {
  key: string;
  status: 'available' | 'coming_soon';
  tool_name: string | null;
  max_level: number;
  /** Lucide icon name, resolved to a LucideIcon by the frontend registry. */
  icon: string;
  always_on: boolean;
}

/**
 * Agent learned memory entry from user interactions
 * BACKEND: AgentMemoryResponse
 */
export interface AgentMemory {
  id: string;
  memory_type: string;
  content: string;
  content_key?: string;
  confidence: number;
  confirmation_count: number;
  rejection_count: number;
  learned_from: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  last_used_at?: string;
}

// =============================================================================
// DISPLAY CONSTANTS
// =============================================================================

/**
 * Multilingual labels for document categories
 */
export const CATEGORY_LABELS: Record<DocumentCategory, { es: string; fr: string; en: string }> = {
  identity: { es: 'Identidad', fr: 'Identit\u00e9', en: 'Identity' },
  vehicle: { es: 'Veh\u00edculo', fr: 'V\u00e9hicule', en: 'Vehicle' },
  legal: { es: 'Legal', fr: 'Juridique', en: 'Legal' },
  financial: { es: 'Financiero', fr: 'Financier', en: 'Financial' },
  administrative: { es: 'Administrativo', fr: 'Administratif', en: 'Administrative' },
  medical: { es: 'M\u00e9dico', fr: 'M\u00e9dical', en: 'Medical' },
  education: { es: 'Educaci\u00f3n', fr: '\u00c9ducation', en: 'Education' },
  photo: { es: 'Foto', fr: 'Photo', en: 'Photo' },
  business: { es: 'Empresa', fr: 'Entreprise', en: 'Business' },
  employment: { es: 'Empleo', fr: 'Emploi', en: 'Employment' },
  other: { es: 'Otro', fr: 'Autre', en: 'Other' },
};
