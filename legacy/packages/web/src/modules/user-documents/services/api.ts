/**
 * User Documents API Service
 * Handles citizen document vault operations (upload, search, readiness, alerts, export)
 *
 * @module user-documents/services
 * @date 2026-04-05
 *
 * BACKEND ALIGNMENT:
 * Routes: /api/v1/user-documents (from app/modules/user_documents/api/user_document_routes.py)
 *
 * UPLOAD:
 * - POST   /upload                          -> upload single document
 * - POST   /bulk-upload                     -> upload multiple documents (max 10)
 *
 * CRUD:
 * - GET    /                                -> list documents (cursor-based pagination)
 * - GET    /{id}                            -> get document detail
 * - GET    /{id}/download                   -> get signed download URL
 * - GET    /{id}/thumbnail                  -> get thumbnail URL
 * - PUT    /{id}                            -> update metadata
 * - PUT    /{id}/reclassify                 -> re-run AI classification
 * - PUT    /{id}/archive                    -> soft archive
 * - DELETE /{id}                            -> soft delete
 * - POST   /bulk-action                     -> archive/delete/download multiple
 *
 * GENERATED:
 * - GET    /generated                       -> list platform-generated documents
 * - GET    /generated/{id}/download         -> download generated document
 *
 * SEARCH & STATS:
 * - GET    /search                          -> full-text search with filters
 * - GET    /stats                           -> aggregated statistics
 * - GET    /readiness                       -> workflow readiness check
 * - GET    /for-workflow/{workflow_code}     -> documents matching workflow
 *
 * ALERTS:
 * - GET    /alerts                          -> list proactive alerts
 * - PUT    /alerts/{id}/read               -> mark alert as read
 * - PUT    /alerts/{id}/dismiss            -> dismiss alert
 *
 * VERSIONS & EXPORT:
 * - GET    /{id}/versions                   -> version history
 * - POST   /export                          -> start ZIP export
 * - GET    /export/{id}/status              -> check export status
 * - GET    /export/{id}/download            -> get export download URL
 */

import apiClient from '@/core/api/client';
import type { AgentPermissionCatalogEntry } from '../types';
import type {
  UserDocument,
  UserDocumentListItem,
  UserDocumentListResponse,
  UserDocumentStats,
  ReadinessResult,
  GeneratedDocument,
  DocumentAlert,
  UploadResult,
  DocumentUpdateRequest,
  BulkActionRequest,
  DocumentFilters,
  DocumentCategory,
  ExpiryStatus,
  AlertSeverity,
  AgentPermission,
  AgentMemory,
  ExportStatus,
} from '../types';

// =============================================================================
// CONFIGURATION
// =============================================================================

const BASE = '/user-documents';

// =============================================================================
// HELPER: strip undefined values from params object
// =============================================================================

function cleanParams(
  obj: Record<string, string | number | boolean | undefined | null>
): Record<string, string | number | boolean> {
  const result: Record<string, string | number | boolean> = {};
  for (const [key, value] of Object.entries(obj)) {
    if (value !== undefined && value !== null) {
      result[key] = value;
    }
  }
  return result;
}

// =============================================================================
// USER DOCUMENTS API
// =============================================================================

export const userDocumentsApi = {
  // ===========================================================================
  // UPLOAD
  // ===========================================================================

  /**
   * Upload a single document to the vault
   * BACKEND: POST /api/v1/user-documents/upload
   *
   * Uses multipart/form-data. Axios sets Content-Type automatically
   * when given a FormData body (including the boundary).
   *
   * @param file - The file to upload
   * @param documentTypeHint - Optional hint for AI classification (e.g. "DIP_GE_V1")
   * @param notes - Optional user notes
   */
  upload: async (
    file: File,
    documentTypeHint?: string,
    notes?: string
  ): Promise<UploadResult> => {
    const formData = new FormData();
    formData.append('file', file);

    if (documentTypeHint) {
      formData.append('document_type_hint', documentTypeHint);
    }
    if (notes) {
      formData.append('notes', notes);
    }

    const response = await apiClient.post<UploadResult>(
      `${BASE}/upload`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }
    );
    return response.data;
  },

  /**
   * Bulk upload multiple documents (max 10)
   * BACKEND: POST /api/v1/user-documents/bulk-upload
   *
   * @param files - Array of files to upload
   * @param documentTypeHint - Optional classification hint applied to all files
   */
  bulkUpload: async (
    files: File[],
    documentTypeHint?: string
  ): Promise<UploadResult[]> => {
    const formData = new FormData();

    files.forEach((file) => {
      formData.append('files', file);
    });

    if (documentTypeHint) {
      formData.append('document_type_hint', documentTypeHint);
    }

    const response = await apiClient.post<UploadResult[]>(
      `${BASE}/bulk-upload`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }
    );
    return response.data;
  },

  // ===========================================================================
  // DEDUP — Pre-upload hash check (Phase 1)
  // ===========================================================================

  /**
   * Check if a file with the given SHA-256 hash already exists in vault.
   * BACKEND: GET /api/v1/user-documents/check-hash/{file_hash}
   *
   * @param fileHash - SHA-256 hex digest (64 chars)
   * @returns { exists, document? } — document has id, display_name, expiry_status
   */
  checkHash: async (
    fileHash: string
  ): Promise<{
    exists: boolean;
    document?: {
      id: string;
      display_name: string;
      file_name: string;
      document_type: string;
      expiry_date: string | null;
      expiry_status: string | null;
      status: string;
    };
  }> => {
    const response = await apiClient.get(`${BASE}/check-hash/${fileHash}`);
    return response.data;
  },

  // ===========================================================================
  // LIST & GET
  // ===========================================================================

  /**
   * List user documents with cursor-based pagination and filters
   * BACKEND: GET /api/v1/user-documents/
   */
  list: async (filters?: DocumentFilters): Promise<UserDocumentListResponse> => {
    const params = filters
      ? cleanParams({
          source: filters.source,
          category: filters.category,
          status: filters.status,
          expiry_status: filters.expiry_status,
          search: filters.search,
          cursor: filters.cursor,
          limit: filters.limit,
        })
      : undefined;

    const response = await apiClient.get<UserDocumentListResponse>(BASE, { params });
    return response.data;
  },

  /**
   * Get full document detail by ID
   * BACKEND: GET /api/v1/user-documents/{id}
   */
  getById: async (id: string): Promise<UserDocument> => {
    const response = await apiClient.get<UserDocument>(`${BASE}/${id}`);
    return response.data;
  },

  /**
   * Get a signed download URL for a document
   * BACKEND: GET /api/v1/user-documents/{id}/download
   *
   * @returns Signed URL with expiration
   */
  getDownloadUrl: async (
    id: string
  ): Promise<{ url: string; expires_in_seconds: number }> => {
    const response = await apiClient.get<{ url: string; expires_in_seconds: number }>(
      `${BASE}/${id}/download`
    );
    return response.data;
  },

  /**
   * Get thumbnail URL for a document
   * BACKEND: GET /api/v1/user-documents/{id}/thumbnail
   */
  getThumbnailUrl: async (id: string): Promise<{ url: string }> => {
    const response = await apiClient.get<{ url: string }>(
      `${BASE}/${id}/thumbnail`
    );
    return response.data;
  },

  // ===========================================================================
  // UPDATE & CLASSIFY
  // ===========================================================================

  /**
   * Update document metadata (display name, notes, color, category)
   * BACKEND: PUT /api/v1/user-documents/{id}
   */
  update: async (id: string, data: DocumentUpdateRequest): Promise<UserDocument> => {
    const response = await apiClient.put<UserDocument>(`${BASE}/${id}`, data);
    return response.data;
  },

  /**
   * Re-run AI classification on a document
   * BACKEND: PUT /api/v1/user-documents/{id}/reclassify
   */
  reclassify: async (id: string): Promise<UserDocument> => {
    const response = await apiClient.put<UserDocument>(`${BASE}/${id}/reclassify`);
    return response.data;
  },

  // ===========================================================================
  // ARCHIVE & DELETE
  // ===========================================================================

  /**
   * Archive a document (soft archive, reversible)
   * BACKEND: PUT /api/v1/user-documents/{id}/archive
   */
  archive: async (id: string): Promise<void> => {
    await apiClient.put(`${BASE}/${id}/archive`);
  },

  /**
   * Delete a document (soft delete)
   * BACKEND: DELETE /api/v1/user-documents/{id}
   */
  deleteDoc: async (id: string): Promise<void> => {
    await apiClient.delete(`${BASE}/${id}`);
  },

  /**
   * Permanently delete a document (RGPD right to erasure)
   * Removes file from Firebase Storage + all DB records. Irreversible.
   * BACKEND: DELETE /api/v1/user-documents/{id}/permanent
   */
  permanentDelete: async (id: string): Promise<void> => {
    await apiClient.delete(`${BASE}/${id}/permanent`);
  },

  /**
   * Perform a bulk action on multiple documents
   * BACKEND: POST /api/v1/user-documents/bulk-action
   *
   * @returns Number of documents processed
   */
  bulkAction: async (data: BulkActionRequest): Promise<{ processed: number }> => {
    const response = await apiClient.post<{ processed: number }>(
      `${BASE}/bulk-action`,
      data
    );
    return response.data;
  },

  // ===========================================================================
  // GENERATED DOCUMENTS
  // ===========================================================================

  /**
   * List platform-generated documents (certificates, receipts, etc.)
   * BACKEND: GET /api/v1/user-documents/generated
   */
  listGenerated: async (
    generationType?: string,
    cursor?: string,
    limit?: number
  ): Promise<{ items: GeneratedDocument[]; next_cursor?: string }> => {
    const params = cleanParams({
      generation_type: generationType,
      cursor,
      limit,
    });

    const response = await apiClient.get(`${BASE}/generated`, { params });
    const data = response.data;

    // Backend returns flat array List[GeneratedDocumentResponse],
    // frontend expects { items, next_cursor }. Normalize both formats.
    if (Array.isArray(data)) {
      return { items: data as GeneratedDocument[], next_cursor: undefined };
    }
    return data as { items: GeneratedDocument[]; next_cursor?: string };
  },

  /**
   * Get download URL for a generated document
   * BACKEND: GET /api/v1/user-documents/generated/{id}/download
   */
  getGeneratedDownloadUrl: async (id: string): Promise<{ url: string }> => {
    const response = await apiClient.get<{ url: string }>(
      `${BASE}/generated/${id}/download`
    );
    return response.data;
  },

  // ===========================================================================
  // SEARCH & STATS
  // ===========================================================================

  /**
   * Full-text search across documents with optional filters
   * BACKEND: GET /api/v1/user-documents/search
   */
  search: async (
    query: string,
    category?: DocumentCategory,
    expiryStatus?: ExpiryStatus,
    limit?: number
  ): Promise<UserDocumentListItem[]> => {
    const params = cleanParams({
      q: query,
      category,
      expiry_status: expiryStatus,
      limit,
    });

    const response = await apiClient.get<UserDocumentListItem[]>(
      `${BASE}/search`,
      { params }
    );
    return response.data;
  },

  /**
   * Get aggregated document vault statistics
   * BACKEND: GET /api/v1/user-documents/stats
   */
  getStats: async (): Promise<UserDocumentStats> => {
    const response = await apiClient.get<UserDocumentStats>(`${BASE}/stats`);
    return response.data;
  },

  // ===========================================================================
  // WORKFLOW READINESS
  // ===========================================================================

  /**
   * Check document readiness for one or all workflows
   * BACKEND: GET /api/v1/user-documents/readiness
   *
   * If workflowCode is provided, returns a single ReadinessResult.
   * Otherwise, returns an array of ReadinessResult for all relevant workflows.
   */
  getReadiness: async (
    workflowCode?: string
  ): Promise<ReadinessResult | ReadinessResult[]> => {
    const params = workflowCode
      ? cleanParams({ workflow_code: workflowCode })
      : undefined;

    const response = await apiClient.get<ReadinessResult | ReadinessResult[]>(
      `${BASE}/readiness`,
      { params }
    );
    return response.data;
  },

  /**
   * Get documents that match a specific workflow's requirements
   * BACKEND: GET /api/v1/user-documents/for-workflow/{workflow_code}
   */
  getForWorkflow: async (workflowCode: string): Promise<UserDocumentListItem[]> => {
    const response = await apiClient.get<UserDocumentListItem[]>(
      `${BASE}/for-workflow/${workflowCode}`
    );
    return response.data;
  },

  // ===========================================================================
  // ALERTS
  // ===========================================================================

  /**
   * List proactive document alerts (expiry warnings, missing docs, etc.)
   * BACKEND: GET /api/v1/user-documents/alerts
   */
  getAlerts: async (
    severity?: AlertSeverity,
    isRead?: boolean,
    limit?: number
  ): Promise<DocumentAlert[]> => {
    const params = cleanParams({
      severity,
      is_read: isRead,
      limit,
    });

    const response = await apiClient.get<DocumentAlert[]>(
      `${BASE}/alerts`,
      { params }
    );
    return response.data;
  },

  /**
   * Mark an alert as read
   * BACKEND: PUT /api/v1/user-documents/alerts/{alertId}/read
   */
  markAlertRead: async (alertId: string): Promise<void> => {
    await apiClient.put(`${BASE}/alerts/${alertId}/read`);
  },

  /**
   * Dismiss an alert (hide permanently)
   * BACKEND: PUT /api/v1/user-documents/alerts/{alertId}/dismiss
   */
  dismissAlert: async (alertId: string): Promise<void> => {
    await apiClient.put(`${BASE}/alerts/${alertId}/dismiss`);
  },

  // ===========================================================================
  // VERSIONS
  // ===========================================================================

  /**
   * Get version history for a document (all documents that replace or are replaced by this one)
   * BACKEND: GET /api/v1/user-documents/{documentId}/versions
   */
  getVersions: async (documentId: string): Promise<UserDocumentListItem[]> => {
    const response = await apiClient.get<UserDocumentListItem[]>(
      `${BASE}/${documentId}/versions`
    );
    return response.data;
  },

  // ===========================================================================
  // EXPORT
  // ===========================================================================

  /**
   * Start a ZIP export of all active documents
   * BACKEND: POST /api/v1/user-documents/export
   *
   * @returns An export ID to track/download the export
   */
  startExport: async (): Promise<{ export_id: string }> => {
    const response = await apiClient.post<{ export_id: string }>(
      `${BASE}/export`
    );
    return response.data;
  },

  /**
   * Check the status of an ongoing export
   * BACKEND: GET /api/v1/user-documents/export/{exportId}/status
   */
  getExportStatus: async (exportId: string): Promise<ExportStatus> => {
    const response = await apiClient.get<ExportStatus>(
      `${BASE}/export/${exportId}/status`
    );
    return response.data;
  },

  /**
   * Get the download URL for a completed export
   * BACKEND: GET /api/v1/user-documents/export/{exportId}/download
   */
  getExportDownloadUrl: async (exportId: string): Promise<{ url: string }> => {
    const response = await apiClient.get<{ url: string }>(
      `${BASE}/export/${exportId}/download`
    );
    return response.data;
  },

  // ===========================================================================
  // AGENT PERMISSIONS
  // ===========================================================================

  /**
   * Fetch the authoritative permission catalog from the backend.
   * This is the source of truth — the frontend no longer hardcodes the list
   * of permission types. Each entry carries a status flag so the UI can
   * render disabled "coming soon" toggles for features not yet wired.
   * BACKEND: GET /api/v1/user-documents/agent/permission-catalog
   */
  getAgentPermissionCatalog: async (): Promise<AgentPermissionCatalogEntry[]> => {
    const response = await apiClient.get<{
      catalog: AgentPermissionCatalogEntry[];
      total: number;
    }>(`${BASE}/agent/permission-catalog`);
    return response.data.catalog;
  },

  /**
   * List agent permissions for the current user
   * BACKEND: GET /api/v1/user-documents/agent/permissions
   */
  listPermissions: async (): Promise<AgentPermission[]> => {
    const response = await apiClient.get<AgentPermission[]>(
      `${BASE}/agent/permissions`
    );
    return response.data;
  },

  /**
   * Grant or update an agent permission
   * BACKEND: POST /api/v1/user-documents/agent/permissions
   */
  grantPermission: async (data: {
    permission_type: string;
    scope?: string;
    level?: number;
  }): Promise<AgentPermission> => {
    const response = await apiClient.post<AgentPermission>(
      `${BASE}/agent/permissions`,
      data
    );
    return response.data;
  },

  /**
   * Revoke (deactivate) an agent permission
   * BACKEND: DELETE /api/v1/user-documents/agent/permissions/{permissionId}
   */
  revokePermission: async (permissionId: string): Promise<void> => {
    await apiClient.delete(`${BASE}/agent/permissions/${permissionId}`);
  },

  // ===========================================================================
  // AGENT MEMORY
  // ===========================================================================

  /**
   * List agent learned memories for the current user
   * BACKEND: GET /api/v1/user-documents/agent/memory
   */
  listMemories: async (): Promise<AgentMemory[]> => {
    const response = await apiClient.get<AgentMemory[]>(
      `${BASE}/agent/memory`
    );
    return response.data;
  },

  /**
   * Delete a specific agent memory
   * BACKEND: DELETE /api/v1/user-documents/agent/memory/{memoryId}
   */
  deleteMemory: async (memoryId: string): Promise<void> => {
    await apiClient.delete(`${BASE}/agent/memory/${memoryId}`);
  },

  /**
   * Reset (clear) all agent memories for the current user
   * BACKEND: DELETE /api/v1/user-documents/agent/memory
   */
  resetMemories: async (): Promise<void> => {
    await apiClient.delete(`${BASE}/agent/memory`);
  },
};

// =============================================================================
// EXPORTS
// =============================================================================

export default userDocumentsApi;
