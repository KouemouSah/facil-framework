/**
 * API Client for Verified Identifiers Module
 * Identity verification endpoints for CNEDOGE agents
 */

import apiClient from '@/core/api/client';
import type {
  PendingVerificationListResponse,
  PendingVerificationListResponseApi,
  PendingVerificationItem,
  PendingVerificationItemApi,
  VerificationDetail,
  VerificationDetailApi,
  VerifyIdentifierRequest,
  VerifyIdentifierRequestApi,
  VerifyIdentifierResponse,
  VerifyIdentifierResponseApi,
  VerifyBatchRequest,
  VerifyBatchRequestApi,
  VerifyBatchResponse,
  VerifyBatchResponseApi,
  RejectIdentifierRequest,
  RejectIdentifierRequestApi,
  RejectIdentifierResponse,
  RejectIdentifierResponseApi,
  ExtractedIdentifier,
  ExtractedIdentifierApi,
  DocumentInfo,
  DocumentInfoApi,
  VerificationFilters,
} from '../types';

const BASE_URL = '/verified-identifiers';

// =============================================================================
// TRANSFORMERS (snake_case -> camelCase)
// =============================================================================

function transformExtractedIdentifier(
  api: ExtractedIdentifierApi
): ExtractedIdentifier {
  return {
    identifierType: api.identifier_type as ExtractedIdentifier['identifierType'],
    value: api.value,
    documentCode: api.document_code,
    documentName: api.document_name,
    confidence: api.confidence,
    expiresAt: api.expires_at,
    status: api.status as ExtractedIdentifier['status'],
    verifiedAt: api.verified_at,
    source: api.source as ExtractedIdentifier['source'],
  };
}

function transformPendingItem(
  api: PendingVerificationItemApi
): PendingVerificationItem {
  return {
    id: api.id,
    reference: api.reference,
    workflowCode: api.workflow_code,
    solicitudType: api.solicitud_type,
    status: api.status,
    verificationStatus: api.verification_status,
    citizenName: api.citizen_name,
    submittedAt: api.submitted_at,
    identifiers: api.identifiers.map(transformExtractedIdentifier),
    pendingCount: api.pending_count,
    verifiedCount: api.verified_count,
    documentsCount: api.documents_count,
  };
}

function transformDocumentInfo(api: DocumentInfoApi): DocumentInfo {
  return {
    id: api.id,
    documentCode: api.document_code,
    documentName: api.document_name,
    filePath: api.file_path,
    fileName: api.file_name,
    fileUrl: api.file_url,
    mimeType: api.mime_type,
    extractionData: api.extraction_data,
    extractionConfidence: api.extraction_confidence,
    extractionStatus: api.extraction_status,
  };
}

function transformVerificationDetail(
  api: VerificationDetailApi
): VerificationDetail {
  return {
    id: api.id,
    reference: api.reference,
    workflowCode: api.workflow_code,
    solicitudType: api.solicitud_type,
    status: api.status,
    verificationStatus: api.verification_status,
    citizenName: api.citizen_name,
    citizenEmail: api.citizen_email,
    submittedAt: api.submitted_at,
    documents: api.documents.map(transformDocumentInfo),
    identifiers: api.identifiers.map(transformExtractedIdentifier),
    verificationDetails: api.verification_details,
    previousId: api.previous_id,
    nextId: api.next_id,
  };
}

function transformVerifyResponse(
  api: VerifyIdentifierResponseApi
): VerifyIdentifierResponse {
  return {
    verifiedIdentifierId: api.verified_identifier_id,
    identifierType: api.identifier_type,
    status: api.status,
    allVerified: api.all_verified,
    requestVerificationStatus: api.request_verification_status,
  };
}

function transformVerifyBatchResponse(
  api: VerifyBatchResponseApi
): VerifyBatchResponse {
  return {
    verifiedCount: api.verified_count,
    failedCount: api.failed_count,
    results: api.results.map((r) => ({
      identifierType: r.identifier_type,
      status: r.status,
      verifiedIdentifierId: r.verified_identifier_id,
      error: r.error,
    })),
    allVerified: api.all_verified,
    requestVerificationStatus: api.request_verification_status,
  };
}

function transformRejectResponse(
  api: RejectIdentifierResponseApi
): RejectIdentifierResponse {
  return {
    status: api.status,
    identifierType: api.identifier_type,
    reason: api.reason,
    requestVerificationStatus: api.request_verification_status,
    message: api.message,
  };
}

// =============================================================================
// API FUNCTIONS
// =============================================================================

/**
 * Get list of pending verifications for an entity
 */
export async function getPendingVerifications(
  filters: VerificationFilters
): Promise<PendingVerificationListResponse> {
  const params = new URLSearchParams({
    entity_code: filters.entityCode,
    verification_status: filters.verificationStatus || 'pending',
    page: String(filters.page || 1),
    page_size: String(filters.pageSize || 20),
  });

  const response = await apiClient.get<PendingVerificationListResponseApi>(
    `${BASE_URL}/pending?${params.toString()}`
  );

  return {
    items: response.data.items.map(transformPendingItem),
    total: response.data.total,
    page: response.data.page,
    pageSize: response.data.page_size,
  };
}

/**
 * Get detailed verification info for a service request
 */
export async function getVerificationDetails(
  requestId: string,
  entityCode: string
): Promise<VerificationDetail> {
  const params = new URLSearchParams({
    entity_code: entityCode,
  });

  const response = await apiClient.get<VerificationDetailApi>(
    `${BASE_URL}/requests/${requestId}/verification-details?${params.toString()}`
  );

  return transformVerificationDetail(response.data);
}

/**
 * Verify a single identifier and store in cache
 */
export async function verifyIdentifier(
  requestId: string,
  data: VerifyIdentifierRequest
): Promise<VerifyIdentifierResponse> {
  const payload: VerifyIdentifierRequestApi = {
    identifier_type: data.identifierType,
    identifier_value: data.identifierValue,
    expires_at: data.expiresAt,
    notes: data.notes,
  };

  const response = await apiClient.post<VerifyIdentifierResponseApi>(
    `${BASE_URL}/requests/${requestId}/verify-identifier`,
    payload
  );

  return transformVerifyResponse(response.data);
}

/**
 * Verify multiple identifiers at once
 */
export async function verifyBatch(
  requestId: string,
  data: VerifyBatchRequest
): Promise<VerifyBatchResponse> {
  const payload: VerifyBatchRequestApi = {
    identifiers: data.identifiers.map((i) => ({
      identifier_type: i.identifierType,
      identifier_value: i.identifierValue,
      expires_at: i.expiresAt,
      notes: i.notes,
    })),
    notes: data.notes,
  };

  const response = await apiClient.post<VerifyBatchResponseApi>(
    `${BASE_URL}/requests/${requestId}/verify-batch`,
    payload
  );

  return transformVerifyBatchResponse(response.data);
}

/**
 * Reject an identifier with optional fraud marking
 */
export async function rejectIdentifier(
  requestId: string,
  data: RejectIdentifierRequest
): Promise<RejectIdentifierResponse> {
  const payload: RejectIdentifierRequestApi = {
    identifier_type: data.identifierType,
    identifier_value: data.identifierValue,
    reason: data.reason,
    is_fraud: data.isFraud,
  };

  const response = await apiClient.post<RejectIdentifierResponseApi>(
    `${BASE_URL}/requests/${requestId}/reject-identifier`,
    payload
  );

  return transformRejectResponse(response.data);
}
