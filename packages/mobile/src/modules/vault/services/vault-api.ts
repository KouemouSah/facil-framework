/**
 * Vault API — thin wrappers over apiGet/apiPost/apiPut/apiDelete/apiUpload.
 *
 * Backend: app/modules/user_documents/api/user_documents_routes.py
 * All paths centralised in `API_ENDPOINTS.userDocuments.*` (P0).
 */

import { Platform } from 'react-native';

import { apiDelete, apiGet, apiPost, apiPut, apiUpload } from '@core/api/client';
import { API_ENDPOINTS } from '@core/api/endpoints';

import type {
  AlertResponse,
  GeneratedDocumentResponse,
  HashCheckResponse,
  ReadinessResult,
  UploadResult,
  UserDocumentBulkAction,
  UserDocumentListItem,
  UserDocumentListResponse,
  UserDocumentResponse,
  UserDocumentStats,
  UserDocumentUpdate,
  VaultAllowedMime,
} from '../types/vault.types';

// ---------------------------------------------------------------------------
// List + stats + search
// ---------------------------------------------------------------------------

export interface ListVaultParams {
  source?: 'personal_upload' | 'wizard_upload' | 'platform_generated';
  category?: string;
  status?: 'active' | 'archived' | 'expired';
  expiry_status?: 'valid' | 'expiring_soon' | 'expired';
  search?: string;
  cursor?: string;
  limit?: number;
  [key: string]: unknown;
}

export async function listVault(
  params: ListVaultParams = {},
): Promise<UserDocumentListResponse> {
  return apiGet<UserDocumentListResponse>(API_ENDPOINTS.userDocuments.list, params);
}

export async function getVaultStats(): Promise<UserDocumentStats> {
  return apiGet<UserDocumentStats>(API_ENDPOINTS.userDocuments.stats);
}

export async function searchVault(q: string): Promise<UserDocumentListItem[]> {
  return apiGet<UserDocumentListItem[]>(API_ENDPOINTS.userDocuments.search, { q });
}

// ---------------------------------------------------------------------------
// Detail + lifecycle
// ---------------------------------------------------------------------------

export async function getVaultDocument(id: string): Promise<UserDocumentResponse> {
  return apiGet<UserDocumentResponse>(API_ENDPOINTS.userDocuments.detail(id));
}

export async function updateVaultDocument(
  id: string,
  patch: UserDocumentUpdate,
): Promise<UserDocumentResponse> {
  return apiPut<UserDocumentResponse>(API_ENDPOINTS.userDocuments.update(id), patch);
}

export async function archiveVaultDocument(id: string): Promise<UserDocumentResponse> {
  return apiPut<UserDocumentResponse>(API_ENDPOINTS.userDocuments.archive(id), {});
}

export async function deleteVaultDocument(id: string): Promise<{ success: boolean; id: string }> {
  return apiDelete<{ success: boolean; id: string }>(API_ENDPOINTS.userDocuments.delete(id));
}

export async function permanentDeleteVaultDocument(
  id: string,
): Promise<{ success: boolean; id: string }> {
  return apiDelete<{ success: boolean; id: string }>(
    API_ENDPOINTS.userDocuments.permanentDelete(id),
  );
}

export async function reclassifyVaultDocument(
  id: string,
  body: { document_type: string; notes?: string },
): Promise<UserDocumentResponse> {
  return apiPut<UserDocumentResponse>(API_ENDPOINTS.userDocuments.reclassify(id), body);
}

export async function getVaultVersions(id: string): Promise<UserDocumentListItem[]> {
  return apiGet<UserDocumentListItem[]>(API_ENDPOINTS.userDocuments.versions(id));
}

// ---------------------------------------------------------------------------
// Download / thumbnail (Firebase signed URLs)
// ---------------------------------------------------------------------------

export interface SignedUrlResponse {
  url: string;
  expires_in_seconds: number;
  file_name?: string;
  mime_type?: string;
}

export async function getDownloadUrl(id: string): Promise<SignedUrlResponse> {
  return apiGet<SignedUrlResponse>(API_ENDPOINTS.userDocuments.download(id));
}

export async function getThumbnailUrl(id: string): Promise<SignedUrlResponse> {
  return apiGet<SignedUrlResponse>(API_ENDPOINTS.userDocuments.thumbnail(id));
}

// ---------------------------------------------------------------------------
// Upload — single + bulk + dedup pre-check
// ---------------------------------------------------------------------------

export interface UploadVaultParams {
  fileUri: string;
  fileName: string;
  mimeType: VaultAllowedMime;
  documentTypeHint?: string;
  notes?: string;
  onProgress?: (progress: number) => void;
}

export async function checkHash(fileHash: string): Promise<HashCheckResponse> {
  return apiGet<HashCheckResponse>(API_ENDPOINTS.userDocuments.checkHash(fileHash));
}

export async function uploadVaultDocument(
  params: UploadVaultParams,
): Promise<UploadResult> {
  const { fileUri, fileName, mimeType, documentTypeHint, notes, onProgress } = params;
  const formData = new FormData();
  formData.append('file', {
    uri: Platform.OS === 'android' ? fileUri : fileUri.replace('file://', ''),
    name: fileName,
    type: mimeType,
  } as unknown as Blob);

  // Backend reads document_type_hint and notes as Query params on POST /upload.
  const queryParts: string[] = [];
  if (documentTypeHint) {
    queryParts.push(`document_type_hint=${encodeURIComponent(documentTypeHint)}`);
  }
  if (notes) {
    queryParts.push(`notes=${encodeURIComponent(notes)}`);
  }
  const url = queryParts.length
    ? `${API_ENDPOINTS.userDocuments.upload}?${queryParts.join('&')}`
    : API_ENDPOINTS.userDocuments.upload;

  return apiUpload<UploadResult>(url, formData, onProgress);
}

// ---------------------------------------------------------------------------
// Generated documents (platform-issued)
// ---------------------------------------------------------------------------

export interface ListGeneratedParams {
  generation_type?: string;
  cursor?: string;
  limit?: number;
  [key: string]: unknown;
}

export async function listGenerated(
  params: ListGeneratedParams = {},
): Promise<GeneratedDocumentResponse[]> {
  return apiGet<GeneratedDocumentResponse[]>(
    API_ENDPOINTS.userDocuments.generated,
    params,
  );
}

// ---------------------------------------------------------------------------
// Readiness (pre-flight check before starting a workflow)
// ---------------------------------------------------------------------------

export async function getReadinessAll(): Promise<ReadinessResult[]> {
  return apiGet<ReadinessResult[]>(API_ENDPOINTS.userDocuments.readinessAll);
}

export async function getReadinessForWorkflow(
  workflowCode: string,
): Promise<ReadinessResult> {
  return apiGet<ReadinessResult>(API_ENDPOINTS.userDocuments.readiness(workflowCode));
}

export async function getDocumentsForWorkflow(
  workflowCode: string,
): Promise<UserDocumentResponse[]> {
  return apiGet<UserDocumentResponse[]>(
    API_ENDPOINTS.userDocuments.forWorkflow(workflowCode),
  );
}

// ---------------------------------------------------------------------------
// Alerts
// ---------------------------------------------------------------------------

export interface ListAlertsParams {
  severity?: 'critical' | 'warning' | 'info';
  is_read?: boolean;
  limit?: number;
  [key: string]: unknown;
}

export async function listAlerts(
  params: ListAlertsParams = {},
): Promise<AlertResponse[]> {
  return apiGet<AlertResponse[]>(API_ENDPOINTS.userDocuments.alerts, params);
}

export async function markAlertRead(alertId: string): Promise<AlertResponse> {
  return apiPut<AlertResponse>(API_ENDPOINTS.userDocuments.alertRead(alertId), {});
}

export async function dismissAlert(alertId: string): Promise<AlertResponse> {
  return apiPut<AlertResponse>(API_ENDPOINTS.userDocuments.alertDismiss(alertId), {});
}

// ---------------------------------------------------------------------------
// Bulk + export
// ---------------------------------------------------------------------------

export interface BulkActionResponse {
  action: string;
  total: number;
  succeeded: number;
  failed: number;
  download_urls?: string[];
}

export async function bulkAction(
  payload: UserDocumentBulkAction,
): Promise<BulkActionResponse> {
  return apiPost<BulkActionResponse>(API_ENDPOINTS.userDocuments.bulkAction, payload);
}

export interface ExportStartResponse {
  export_id: string;
  status: string;
  total_documents: number;
  category?: string;
}

export async function startExport(category?: string): Promise<ExportStartResponse> {
  const url = category
    ? `${API_ENDPOINTS.userDocuments.exportStart}?category=${encodeURIComponent(category)}`
    : API_ENDPOINTS.userDocuments.exportStart;
  return apiPost<ExportStartResponse>(url, {});
}

export interface ExportStatusResponse {
  status: 'processing' | 'completed' | 'failed';
  completed_at?: string;
  error?: string;
}

export async function getExportStatus(exportId: string): Promise<ExportStatusResponse> {
  return apiGet<ExportStatusResponse>(API_ENDPOINTS.userDocuments.exportStatus(exportId));
}

export async function getExportDownload(exportId: string): Promise<SignedUrlResponse> {
  return apiGet<SignedUrlResponse>(API_ENDPOINTS.userDocuments.exportDownload(exportId));
}
