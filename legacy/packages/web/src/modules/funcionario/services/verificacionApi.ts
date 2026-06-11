/**
 * Funcionario Verification API Service
 * API calls for civil servant verification workflow
 *
 * Supports both:
 * - Session-based flow (v2) - Recommended
 * - Legacy flow (v1) - Deprecated
 */

import { fetchClient } from '@/core/api/fetchClient'
import type {
  MyVerificationStatus,
  DocumentPreviewResponse,
  DocumentValidateResponse,
  CreateVerificacionResponse,
  SubmitVerificacionResponse,
  DocumentoTipoPrueba,
  // Session-based types (v2)
  SessionStartResponse,
  SessionPreviewResponse,
  SessionStatusResponse,
  SessionFormReviewResponse,
  SessionSubmitResponse,
  SessionSubmitRequest,
} from '../types'

const BASE_PATH = '/verificacion-funcionario'

/**
 * Helper function for FormData uploads
 * Uses native fetch to properly handle multipart/form-data
 */
async function uploadFormData<T>(endpoint: string, formData: FormData): Promise<T> {
  const baseUrl = fetchClient.getBaseUrl()
  const token = fetchClient.getAuthToken()

  const headers: HeadersInit = {}
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  // Note: Don't set Content-Type - browser will set it with boundary for FormData

  const response = await fetch(`${baseUrl}${endpoint}`, {
    method: 'POST',
    headers,
    body: formData,
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({
      detail: `HTTP ${response.status}: ${response.statusText}`,
    }))
    const errorMessage = typeof errorData.detail === 'string'
      ? errorData.detail
      : errorData.message || `HTTP ${response.status}`
    const error = new Error(errorMessage) as Error & { code?: string }
    if (response.status === 410) {
      error.code = 'SESSION_EXPIRED'
    }
    throw error
  }

  return response.json()
}

export const verificacionApi = {
  /**
   * Get current user's verification status
   */
  async getMyStatus(): Promise<MyVerificationStatus> {
    return fetchClient.get<MyVerificationStatus>(`${BASE_PATH}/my-status`)
  },

  // ===========================================================================
  // SESSION-BASED FLOW (v2) - Recommended
  // All data in cache until final validation. 30-minute expiration.
  // ===========================================================================

  /**
   * Start a new verification session
   * Creates session in cache with 30-minute TTL
   */
  async startSession(matricula: string): Promise<SessionStartResponse> {
    const formData = new FormData()
    formData.append('matricula', matricula)

    return uploadFormData<SessionStartResponse>(
      `${BASE_PATH}/session/start`,
      formData
    )
  },

  /**
   * Preview document in session
   * Extracts data using OCR and stores in session cache
   * Renews session TTL to 30 minutes
   */
  async sessionPreviewDocument(
    sessionId: string,
    file: File,
    documentCode: 'dip' | DocumentoTipoPrueba
  ): Promise<SessionPreviewResponse> {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('document_code', documentCode)

    return uploadFormData<SessionPreviewResponse>(
      `${BASE_PATH}/session/${sessionId}/preview`,
      formData
    )
  },

  /**
   * Get session status
   * Lightweight check for documents, validation, and readiness
   */
  async getSessionStatus(sessionId: string): Promise<SessionStatusResponse> {
    return fetchClient.get<SessionStatusResponse>(`${BASE_PATH}/session/${sessionId}/status`)
  },

  /**
   * Get form review data from session
   * Returns auto-filled data from document extractions
   */
  async getSessionFormReview(sessionId: string): Promise<SessionFormReviewResponse> {
    return fetchClient.get<SessionFormReviewResponse>(`${BASE_PATH}/session/${sessionId}/form-review`)
  },

  /**
   * Validate and submit verification (atomic transaction)
   *
   * ATOMIC OPERATION:
   * 1. Validates all documents present
   * 2. Merges form_data with extractions
   * 3. Uploads documents to Firebase (parallel)
   * 4. Creates database entry
   * 5. Deletes session from cache
   *
   * If any step fails, nothing is persisted.
   */
  async sessionValidateAndSubmit(
    sessionId: string,
    request: SessionSubmitRequest = {}
  ): Promise<SessionSubmitResponse> {
    return fetchClient.post<SessionSubmitResponse>(
      `${BASE_PATH}/session/${sessionId}/validate-and-submit`,
      request
    )
  },

  /**
   * Cancel and delete a session
   */
  async cancelSession(sessionId: string): Promise<{ success: boolean; message: string }> {
    return fetchClient.delete<{ success: boolean; message: string }>(
      `${BASE_PATH}/session/${sessionId}`
    )
  },

  // ===========================================================================
  // LEGACY FLOW (v1) - Deprecated
  // Use session-based flow instead
  // ===========================================================================

  /**
   * @deprecated Use startSession() instead
   * Create a new verification request
   */
  async createVerification(matricula: string): Promise<CreateVerificacionResponse> {
    return fetchClient.post<CreateVerificacionResponse>(BASE_PATH, { matricula })
  },

  /**
   * @deprecated Use sessionPreviewDocument() instead
   * Preview document extraction (Step 1)
   */
  async previewDocument(
    verificacionId: string,
    file: File,
    documentCode: 'dip' | DocumentoTipoPrueba,
    existingExtractions?: Record<string, unknown>
  ): Promise<DocumentPreviewResponse> {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('document_code', documentCode)
    if (existingExtractions) {
      formData.append('existing_extractions', JSON.stringify(existingExtractions))
    }

    return uploadFormData<DocumentPreviewResponse>(
      `${BASE_PATH}/${verificacionId}/documents/preview`,
      formData
    )
  },

  /**
   * @deprecated Use sessionValidateAndSubmit() instead
   * Validate and save document (Step 2)
   */
  async validateDocument(
    verificacionId: string,
    previewId: string,
    confirmedData: Record<string, unknown>
  ): Promise<DocumentValidateResponse> {
    const formData = new FormData()
    formData.append('preview_id', previewId)
    formData.append('confirmed_data', JSON.stringify(confirmedData))

    return uploadFormData<DocumentValidateResponse>(
      `${BASE_PATH}/${verificacionId}/documents/validate`,
      formData
    )
  },

  /**
   * @deprecated Use sessionValidateAndSubmit() instead
   * Submit verification for agent review
   */
  async submitVerification(verificacionId: string): Promise<SubmitVerificacionResponse> {
    return fetchClient.post<SubmitVerificacionResponse>(`${BASE_PATH}/${verificacionId}/submit`)
  },
}
