/**
 * Documents API Service
 * Handles document management operations (upload, OCR, extraction, validation)
 *
 * @module documents/services
 * @author Claude Code
 * @date 2025-11-26
 *
 * BACKEND ALIGNMENT:
 * Routes: /api/v1/documents (from app/modules/documents/api/document_routes.py)
 * - GET    /api/v1/documents/              → get_api_info
 * - POST   /api/v1/documents/upload        → upload_document
 * - POST   /api/v1/documents/bulk-upload   → bulk_upload_documents
 * - GET    /api/v1/documents/list          → list_documents
 * - GET    /api/v1/documents/{id}          → get_document
 * - GET    /api/v1/documents/{id}/download → download_document
 * - POST   /api/v1/documents/{id}/process  → process_document
 * - POST   /api/v1/documents/{id}/ocr      → run_ocr
 * - GET    /api/v1/documents/stats         → get_stats
 * - DELETE /api/v1/documents/{id}          → delete_document
 */

import { fetchClient } from '@/core/api';
import type {
  Document,
  DocumentUploadOptions,
  DocumentUploadResponse,
  DocumentListResponse,
  DocumentSearchFilter,
  OCRResult,
  DocumentProcessingStats,
} from '../types';

// =============================================================================
// CONFIGURATION
// =============================================================================

const DOCUMENTS_BASE = '/documents';

// =============================================================================
// DOCUMENTS API
// =============================================================================

export const documentsApi = {
  // ===========================================================================
  // INFO
  // ===========================================================================

  /**
   * Get API info and capabilities
   * BACKEND: GET /api/v1/documents/
   */
  getInfo: async (): Promise<Record<string, unknown>> => {
    return fetchClient.get(`${DOCUMENTS_BASE}/`);
  },

  // ===========================================================================
  // UPLOAD
  // ===========================================================================

  /**
   * Upload a single document
   * BACKEND: POST /api/v1/documents/upload
   *
   * LIMITS:
   * - Max file size: 50MB
   * - Supported formats: PDF, JPG, PNG, TIFF, WEBP, DOC, DOCX
   */
  upload: async (
    file: File,
    options?: DocumentUploadOptions
  ): Promise<DocumentUploadResponse> => {
    const formData = new FormData();
    formData.append('file', file);

    if (options?.document_type) {
      formData.append('document_type', options.document_type);
    }
    if (options?.document_subtype) {
      formData.append('document_subtype', options.document_subtype);
    }
    if (options?.processing_mode) {
      formData.append('processing_mode', options.processing_mode);
    }
    if (options?.auto_process !== undefined) {
      formData.append('auto_process', String(options.auto_process));
    }
    if (options?.metadata) {
      formData.append('metadata', JSON.stringify(options.metadata));
    }
    // Phase 2 support
    if (options?.type_compte) {
      formData.append('type_compte', options.type_compte);
    }
    if (options?.fiscal_service_id) {
      formData.append('fiscal_service_id', options.fiscal_service_id);
    }
    if (options?.declaration_id) {
      formData.append('declaration_id', options.declaration_id);
    }

    const response = await fetch(`${fetchClient.getBaseUrl()}${DOCUMENTS_BASE}/upload`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${fetchClient.getAuthToken()}`,
      },
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || 'Document upload failed');
    }

    return response.json();
  },

  /**
   * Bulk upload documents (max 10)
   * BACKEND: POST /api/v1/documents/bulk-upload
   */
  bulkUpload: async (
    files: File[],
    options?: DocumentUploadOptions
  ): Promise<DocumentUploadResponse[]> => {
    const formData = new FormData();

    files.forEach((file) => {
      formData.append('files', file);
    });

    if (options?.document_type) {
      formData.append('document_type', options.document_type);
    }
    if (options?.auto_process !== undefined) {
      formData.append('auto_process', String(options.auto_process));
    }

    const response = await fetch(`${fetchClient.getBaseUrl()}${DOCUMENTS_BASE}/bulk-upload`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${fetchClient.getAuthToken()}`,
      },
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || 'Bulk upload failed');
    }

    return response.json();
  },

  // ===========================================================================
  // LIST & GET
  // ===========================================================================

  /**
   * List user documents with pagination
   * BACKEND: GET /api/v1/documents/list
   */
  list: async (params?: {
    document_type?: string;
    processing_status?: string;
    date_from?: string;
    date_to?: string;
    page?: number;
    size?: number;
  }): Promise<DocumentListResponse> => {
    return fetchClient.get<DocumentListResponse>(`${DOCUMENTS_BASE}/list`, params);
  },

  /**
   * Get document by ID
   * BACKEND: GET /api/v1/documents/{document_id}
   */
  getById: async (documentId: string): Promise<Document> => {
    return fetchClient.get<Document>(`${DOCUMENTS_BASE}/${documentId}`);
  },

  /**
   * Download document (returns signed URL)
   * BACKEND: GET /api/v1/documents/{document_id}/download
   */
  download: async (documentId: string): Promise<{ download_url: string; expires_in: number }> => {
    return fetchClient.get(`${DOCUMENTS_BASE}/${documentId}/download`);
  },

  /**
   * Search documents with filters
   * BACKEND: POST /api/v1/documents/search (if exists) or use list with filters
   */
  search: async (filters: DocumentSearchFilter): Promise<DocumentListResponse> => {
    return fetchClient.get<DocumentListResponse>(`${DOCUMENTS_BASE}/list`, {
      document_type: filters.document_type,
      ocr_status: filters.ocr_status,
      extraction_status: filters.extraction_status,
      validation_status: filters.validation_status,
      date_from: filters.date_from,
      date_to: filters.date_to,
      page: filters.page,
      size: filters.size,
    });
  },

  // ===========================================================================
  // PROCESSING
  // ===========================================================================

  /**
   * Process document (full pipeline: OCR + extraction + validation)
   * BACKEND: POST /api/v1/documents/{document_id}/process
   */
  process: async (documentId: string): Promise<Document> => {
    return fetchClient.post<Document>(`${DOCUMENTS_BASE}/${documentId}/process`);
  },

  /**
   * Run OCR only on document
   * BACKEND: POST /api/v1/documents/{document_id}/ocr
   *
   * @param provider - 'tesseract_server' | 'tesseract_lite' | 'cloud_vision'
   */
  runOCR: async (
    documentId: string,
    provider?: string
  ): Promise<OCRResult> => {
    return fetchClient.post<OCRResult>(
      `${DOCUMENTS_BASE}/${documentId}/ocr`,
      provider ? { provider } : undefined
    );
  },

  /**
   * Retry failed processing
   * BACKEND: POST /api/v1/documents/{document_id}/retry (if exists)
   */
  retry: async (documentId: string): Promise<Document> => {
    return fetchClient.post<Document>(`${DOCUMENTS_BASE}/${documentId}/process`);
  },

  // ===========================================================================
  // STATISTICS
  // ===========================================================================

  /**
   * Get user document statistics
   * BACKEND: GET /api/v1/documents/stats
   */
  getStats: async (): Promise<DocumentProcessingStats> => {
    return fetchClient.get<DocumentProcessingStats>(`${DOCUMENTS_BASE}/stats`);
  },

  // ===========================================================================
  // DELETE
  // ===========================================================================

  /**
   * Delete document
   * BACKEND: DELETE /api/v1/documents/{document_id}
   *
   * @param hardDelete - true for permanent deletion, false for soft delete
   */
  delete: async (documentId: string, hardDelete: boolean = false): Promise<void> => {
    await fetchClient.delete(`${DOCUMENTS_BASE}/${documentId}`, {
      hard_delete: hardDelete,
    });
  },
};

// =============================================================================
// EXPORTS
// =============================================================================

export default documentsApi;
