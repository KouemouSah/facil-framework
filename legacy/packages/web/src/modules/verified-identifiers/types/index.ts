/**
 * Types for Verified Identifiers Module
 * Identity verification for CNEDOGE agents
 */

// =============================================================================
// ENUMS
// =============================================================================

export type IdentifierStatus =
  | 'pending'
  | 'verified'
  | 'verified_manually'
  | 'rejected'
  | 'fraud';

export type IdentifierType =
  | 'dni'
  | 'pasaporte'
  | 'permiso_residencia'
  | 'certificado_conducir'
  | 'matricula_vehiculo'
  | 'nif'
  | 'contrato_ornc'
  | 'registro_civil'
  | 'cuve'
  | 'permiso_circulacion'
  | 'matricula_funcionario'
  | 'numero_nombramiento'
  | 'carnet_funcionario';

export type VerificationSource =
  | 'cnedoge'
  | 'trafico'
  | 'hacienda'
  | 'ornc'
  | 'registro_civil'
  | 'registro_vehiculos'
  | 'ministerio_funcion_publica'
  | 'agent_manual'
  | 'api_integration';

// =============================================================================
// EXTRACTED IDENTIFIER
// =============================================================================

export interface ExtractedIdentifier {
  identifierType: IdentifierType;
  value: string;
  documentCode: string;
  documentName: string;
  confidence: number | null;
  expiresAt: string | null;
  status: IdentifierStatus;
  verifiedAt: string | null;
  source: VerificationSource | null;
}

// API response (snake_case)
export interface ExtractedIdentifierApi {
  identifier_type: string;
  value: string;
  document_code: string;
  document_name: string;
  confidence: number | null;
  expires_at: string | null;
  status: string;
  verified_at: string | null;
  source: string | null;
}

// =============================================================================
// PENDING VERIFICATION
// =============================================================================

export interface PendingVerificationItem {
  id: string;
  reference: string;
  workflowCode: string;
  solicitudType: string;
  status: string;
  verificationStatus: string;
  citizenName: string;
  submittedAt: string | null;
  identifiers: ExtractedIdentifier[];
  pendingCount: number;
  verifiedCount: number;
  documentsCount: number;
}

export interface PendingVerificationItemApi {
  id: string;
  reference: string;
  workflow_code: string;
  solicitud_type: string;
  status: string;
  verification_status: string;
  citizen_name: string;
  submitted_at: string | null;
  identifiers: ExtractedIdentifierApi[];
  pending_count: number;
  verified_count: number;
  documents_count: number;
}

export interface PendingVerificationListResponse {
  items: PendingVerificationItem[];
  total: number;
  page: number;
  pageSize: number;
}

export interface PendingVerificationListResponseApi {
  items: PendingVerificationItemApi[];
  total: number;
  page: number;
  page_size: number;
}

// =============================================================================
// VERIFICATION DETAIL
// =============================================================================

export interface DocumentInfo {
  id: string;
  documentCode: string;
  documentName: string;
  filePath: string;
  fileName: string;
  fileUrl: string | null;  // Signed URL for document access
  mimeType: string | null;
  extractionData: Record<string, unknown> | null;
  extractionConfidence: number | null;
  extractionStatus: string | null;
}

export interface DocumentInfoApi {
  id: string;
  document_code: string;
  document_name: string;
  file_path: string;
  file_name: string;
  file_url: string | null;  // Signed URL for document access
  mime_type: string | null;
  extraction_data: Record<string, unknown> | null;
  extraction_confidence: number | null;
  extraction_status: string | null;
}

export interface VerificationDetail {
  id: string;
  reference: string;
  workflowCode: string;
  solicitudType: string;
  status: string;
  verificationStatus: string;
  citizenName: string;
  citizenEmail: string | null;
  submittedAt: string | null;
  documents: DocumentInfo[];
  identifiers: ExtractedIdentifier[];
  verificationDetails: Record<string, unknown> | null;
  previousId: string | null;
  nextId: string | null;
}

export interface VerificationDetailApi {
  id: string;
  reference: string;
  workflow_code: string;
  solicitud_type: string;
  status: string;
  verification_status: string;
  citizen_name: string;
  citizen_email: string | null;
  submitted_at: string | null;
  documents: DocumentInfoApi[];
  identifiers: ExtractedIdentifierApi[];
  verification_details: Record<string, unknown> | null;
  previous_id: string | null;
  next_id: string | null;
}

// =============================================================================
// VERIFICATION ACTIONS
// =============================================================================

export interface VerifyIdentifierRequest {
  identifierType: string;
  identifierValue: string;
  expiresAt?: string | null;
  notes?: string | null;
}

export interface VerifyIdentifierRequestApi {
  identifier_type: string;
  identifier_value: string;
  expires_at?: string | null;
  notes?: string | null;
}

export interface VerifyIdentifierResponse {
  verifiedIdentifierId: string;
  identifierType: string;
  status: string;
  allVerified: boolean;
  requestVerificationStatus: string;
}

export interface VerifyIdentifierResponseApi {
  verified_identifier_id: string;
  identifier_type: string;
  status: string;
  all_verified: boolean;
  request_verification_status: string;
}

export interface VerifyBatchRequest {
  identifiers: VerifyIdentifierRequest[];
  notes?: string | null;
}

export interface VerifyBatchRequestApi {
  identifiers: VerifyIdentifierRequestApi[];
  notes?: string | null;
}

export interface VerifyBatchResponse {
  verifiedCount: number;
  failedCount: number;
  results: Array<{
    identifierType: string;
    status: string;
    verifiedIdentifierId?: string;
    error?: string;
  }>;
  allVerified: boolean;
  requestVerificationStatus: string;
}

export interface VerifyBatchResponseApi {
  verified_count: number;
  failed_count: number;
  results: Array<{
    identifier_type: string;
    status: string;
    verified_identifier_id?: string;
    error?: string;
  }>;
  all_verified: boolean;
  request_verification_status: string;
}

export interface RejectIdentifierRequest {
  identifierType: string;
  identifierValue: string;
  reason: string;
  isFraud: boolean;
}

export interface RejectIdentifierRequestApi {
  identifier_type: string;
  identifier_value: string;
  reason: string;
  is_fraud: boolean;
}

export interface RejectIdentifierResponse {
  status: string;
  identifierType: string;
  reason: string;
  requestVerificationStatus: string;
  message: string;
}

export interface RejectIdentifierResponseApi {
  status: string;
  identifier_type: string;
  reason: string;
  request_verification_status: string;
  message: string;
}

// =============================================================================
// FILTERS
// =============================================================================

export interface VerificationFilters {
  entityCode: string;
  verificationStatus?: string;
  page?: number;
  pageSize?: number;
}
