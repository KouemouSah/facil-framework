/**
 * Batch Requests API Client
 *
 * Follows the WizardSessionApiClient pattern for consistency.
 * All endpoints target /api/v1/batch-requests.
 *
 * @see packages/backend/app/modules/batch_requests/api/batch_routes.py
 */

import { getAuthData, setAuthData, clearAuthData } from '@/core/auth/storage'
import type {
  BackendBatchRequest,
  BackendBatchDetailResponse,
  BackendBatchListResponse,
  BackendBatchSession,
  BackendBatchItem,
  BackendClassifyResponse,
  BackendExtractResponse,
  BackendBatchFormConfig,
  BackendPreparePaymentResponse,
  BackendSubmitResponse,
  BackendSharedDocument,
  BatchRequest,
  BatchDetail,
  BatchItem,
  BatchListResponse,
  BatchSession,
  ClassifyResponse,
  ExtractResponse,
  BatchFormConfig,
  PreparePaymentResult,
  SubmitResult,
  SharedDocument,
  BatchCreateRequest,
  BeneficiaryCreateRequest,
  BeneficiaryUpdateRequest,
  SubmitRequest,
  SessionBeneficiary,
  BackendSessionBeneficiary,
  BatchWorkflowsResponse,
} from '../types'
import {
  transformBatchRequest,
  transformBatchItem,
  transformBatchSession,
  transformClassifyResponse,
  transformExtractResponse,
  transformFormConfig,
  transformPreparePayment,
  transformSubmitResult,
  transformSharedDocument,
  transformSessionBeneficiary,
  toBackendBatchCreate,
  toBackendBeneficiaryCreate,
  toBackendBeneficiaryUpdate,
  toBackendSubmit,
} from '../types'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const API_VERSION = '/api/v1'
const ENDPOINT_BASE = '/batch-requests'

// ============================================================================
// TOKEN REFRESH STATE (module-level, shared across concurrent requests)
// ============================================================================

let isRefreshing = false
let failedQueue: Array<{
  resolve: (token: string) => void
  reject: (error: Error) => void
}> = []

const processQueue = (error: Error | null, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error)
    } else {
      prom.resolve(token!)
    }
  })
  failedQueue = []
}

// ============================================================================
// BATCH REQUESTS API CLIENT
// ============================================================================

class BatchApiClient {
  private baseUrl: string

  constructor() {
    this.baseUrl = `${API_BASE_URL}${API_VERSION}${ENDPOINT_BASE}`
  }

  private getToken(): string | null {
    if (typeof window === 'undefined') return null
    const authData = getAuthData()
    return authData?.access_token || null
  }

  /**
   * Refresh the access token using the stored refresh token.
   */
  private async refreshAccessToken(): Promise<string> {
    const authData = getAuthData()
    if (!authData?.refresh_token) {
      clearAuthData()
      throw new Error('No refresh token available')
    }

    try {
      const response = await fetch(
        `${API_BASE_URL}${API_VERSION}/auth/refresh`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: authData.refresh_token }),
        }
      )

      if (!response.ok) {
        clearAuthData()
        throw new Error('Token refresh failed')
      }

      const data = await response.json()
      setAuthData({
        ...authData,
        access_token: data.access_token,
        refresh_token: data.refresh_token || authData.refresh_token,
      })
      return data.access_token
    } catch {
      clearAuthData()
      throw new Error('Token refresh failed')
    }
  }

  /**
   * Make an authenticated JSON request with automatic token refresh.
   */
  private async request<T>(
    path: string,
    options: RequestInit = {}
  ): Promise<T> {
    const token = this.getToken()
    if (!token) {
      throw new Error('Not authenticated')
    }

    const url = path.startsWith('http') ? path : `${this.baseUrl}${path}`
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
      ...(options.headers as Record<string, string>),
    }

    const response = await fetch(url, { ...options, headers })

    // Handle 401 with token refresh
    if (response.status === 401) {
      if (isRefreshing) {
        return new Promise<T>((resolve, reject) => {
          failedQueue.push({
            resolve: async (newToken: string) => {
              try {
                const retryHeaders = { ...headers, Authorization: `Bearer ${newToken}` }
                const retryResponse = await fetch(url, { ...options, headers: retryHeaders })
                if (!retryResponse.ok) {
                  const errData = await retryResponse.json().catch(() => ({}))
                  reject(new Error(errData.detail || `HTTP ${retryResponse.status}`))
                  return
                }
                if (retryResponse.status === 204) {
                  resolve(undefined as never)
                  return
                }
                resolve(await retryResponse.json())
              } catch (err) {
                reject(err)
              }
            },
            reject,
          })
        })
      }

      isRefreshing = true
      try {
        const newToken = await this.refreshAccessToken()
        processQueue(null, newToken)
        isRefreshing = false

        const retryHeaders = { ...headers, Authorization: `Bearer ${newToken}` }
        const retryResponse = await fetch(url, { ...options, headers: retryHeaders })
        if (!retryResponse.ok) {
          const errData = await retryResponse.json().catch(() => ({}))
          throw new Error(errData.detail || `HTTP ${retryResponse.status}`)
        }
        if (retryResponse.status === 204) {
          return undefined as unknown as T
        }
        return await retryResponse.json()
      } catch (err) {
        processQueue(err as Error)
        isRefreshing = false
        throw err
      }
    }

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}))
      const error = new Error(
        typeof errData.detail === 'string'
          ? errData.detail
          : errData.detail?.message || `HTTP ${response.status}`
      ) as Error & { code?: string; status?: number }
      error.code = errData.detail?.code
      error.status = response.status
      throw error
    }

    // Handle 204 No Content
    if (response.status === 204) {
      return undefined as unknown as T
    }

    return await response.json()
  }

  /**
   * Make an authenticated multipart/form-data request (file uploads).
   * Shares the token refresh queue with request() to avoid double-refresh.
   */
  private async uploadRequest<T>(
    path: string,
    formData: FormData
  ): Promise<T> {
    const token = this.getToken()
    if (!token) {
      throw new Error('Not authenticated')
    }

    const url = `${this.baseUrl}${path}`
    const doFetch = (t: string) =>
      fetch(url, {
        method: 'POST',
        headers: { Authorization: `Bearer ${t}` },
        body: formData,
      })

    const response = await doFetch(token)

    if (response.status === 401) {
      // Use shared refresh queue to avoid concurrent double-refresh
      if (isRefreshing) {
        return new Promise<T>((resolve, reject) => {
          failedQueue.push({
            resolve: async (newToken: string) => {
              try {
                const retryResponse = await doFetch(newToken)
                if (!retryResponse.ok) {
                  const errData = await retryResponse.json().catch(() => ({}))
                  reject(new Error(errData.detail || `HTTP ${retryResponse.status}`))
                  return
                }
                resolve(await retryResponse.json())
              } catch (err) {
                reject(err)
              }
            },
            reject,
          })
        })
      }

      isRefreshing = true
      try {
        const newToken = await this.refreshAccessToken()
        processQueue(null, newToken)
        isRefreshing = false

        const retryResponse = await doFetch(newToken)
        if (!retryResponse.ok) {
          const errData = await retryResponse.json().catch(() => ({}))
          throw new Error(errData.detail || `HTTP ${retryResponse.status}`)
        }
        return await retryResponse.json()
      } catch (err) {
        processQueue(err as Error)
        isRefreshing = false
        throw err
      }
    }

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}))
      throw new Error(
        typeof errData.detail === 'string'
          ? errData.detail
          : errData.detail?.message || `HTTP ${response.status}`
      )
    }

    return await response.json()
  }

  // =========================================================================
  // BATCH CRUD
  // =========================================================================

  async createBatch(data: BatchCreateRequest): Promise<BatchRequest> {
    const raw = await this.request<BackendBatchRequest>('/', {
      method: 'POST',
      body: JSON.stringify(toBackendBatchCreate(data)),
    })
    return transformBatchRequest(raw)
  }

  async listBatches(params?: {
    status?: string
    page?: number
    pageSize?: number
  }): Promise<BatchListResponse> {
    const searchParams = new URLSearchParams()
    if (params?.status) searchParams.set('status', params.status)
    if (params?.page) searchParams.set('page', String(params.page))
    if (params?.pageSize) searchParams.set('page_size', String(params.pageSize))

    const qs = searchParams.toString()
    const raw = await this.request<BackendBatchListResponse>(
      `/${qs ? `?${qs}` : ''}`
    )
    return {
      batches: raw.batches.map(transformBatchRequest),
      total: raw.total,
      page: raw.page,
      pageSize: raw.page_size,
      totalPages: raw.total_pages,
    }
  }

  async getBatch(batchId: string): Promise<BatchDetail> {
    const raw = await this.request<BackendBatchDetailResponse>(`/${batchId}`)
    return {
      ...transformBatchRequest(raw),
      items: (raw.items || []).map(transformBatchItem),
    }
  }

  async updateBatch(
    batchId: string,
    data: { notes?: string; entity_code?: string }
  ): Promise<BatchRequest> {
    const raw = await this.request<BackendBatchRequest>(`/${batchId}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    })
    return transformBatchRequest(raw)
  }

  async advanceBatchStatus(
    batchId: string,
    status: string
  ): Promise<BatchRequest> {
    const raw = await this.request<BackendBatchRequest>(
      `/${batchId}/status?status=${encodeURIComponent(status)}`,
      { method: 'PATCH' }
    )
    return transformBatchRequest(raw)
  }

  async deleteBatch(batchId: string): Promise<void> {
    await this.request<void>(`/${batchId}`, { method: 'DELETE' })
  }

  // =========================================================================
  // BATCH ITEMS (Beneficiaries) CRUD
  // =========================================================================

  async listItems(batchId: string, status?: string): Promise<BatchItem[]> {
    const qs = status ? `?status=${encodeURIComponent(status)}` : ''
    const raw = await this.request<BackendBatchItem[]>(
      `/${batchId}/items${qs}`
    )
    return raw.map(transformBatchItem)
  }

  async addItem(
    batchId: string,
    data: BeneficiaryCreateRequest
  ): Promise<BatchItem> {
    const raw = await this.request<BackendBatchItem>(
      `/${batchId}/items`,
      { method: 'POST', body: JSON.stringify(toBackendBeneficiaryCreate(data)) }
    )
    return transformBatchItem(raw)
  }

  async addItemsBulk(
    batchId: string,
    items: BeneficiaryCreateRequest[]
  ): Promise<BatchItem[]> {
    const raw = await this.request<BackendBatchItem[]>(
      `/${batchId}/items/bulk`,
      { method: 'POST', body: JSON.stringify({ items: items.map(toBackendBeneficiaryCreate) }) }
    )
    return raw.map(transformBatchItem)
  }

  async updateItem(
    batchId: string,
    itemId: string,
    data: BeneficiaryUpdateRequest
  ): Promise<BatchItem> {
    const raw = await this.request<BackendBatchItem>(
      `/${batchId}/items/${itemId}`,
      { method: 'PUT', body: JSON.stringify(toBackendBeneficiaryUpdate(data)) }
    )
    return transformBatchItem(raw)
  }

  async deleteItem(batchId: string, itemId: string): Promise<void> {
    await this.request<void>(`/${batchId}/items/${itemId}`, {
      method: 'DELETE',
    })
  }

  // =========================================================================
  // SESSION LIFECYCLE
  // =========================================================================

  async startSession(data: BatchCreateRequest): Promise<BatchSession> {
    const raw = await this.request<BackendBatchSession>('/sessions', {
      method: 'POST',
      body: JSON.stringify(toBackendBatchCreate(data)),
    })
    return transformBatchSession(raw)
  }

  async getSession(sessionId: string): Promise<BatchSession> {
    const raw = await this.request<BackendBatchSession>(
      `/sessions/${sessionId}`
    )
    return transformBatchSession(raw)
  }

  async cancelSession(sessionId: string): Promise<void> {
    await this.request<void>(`/sessions/${sessionId}`, { method: 'DELETE' })
  }

  // =========================================================================
  // SESSION BENEFICIARIES
  // =========================================================================

  async sessionAddBeneficiary(
    sessionId: string,
    data: BeneficiaryCreateRequest
  ): Promise<SessionBeneficiary> {
    const raw = await this.request<BackendSessionBeneficiary>(
      `/sessions/${sessionId}/beneficiaries`,
      { method: 'POST', body: JSON.stringify(toBackendBeneficiaryCreate(data)) }
    )
    return transformSessionBeneficiary(raw)
  }

  async sessionImportCsv(
    sessionId: string,
    file: File
  ): Promise<{ imported: number; beneficiaries: SessionBeneficiary[] }> {
    const formData = new FormData()
    formData.append('file', file)
    const raw = await this.uploadRequest<{
      imported: number
      beneficiaries: BackendSessionBeneficiary[]
    }>(`/sessions/${sessionId}/beneficiaries/import`, formData)
    return {
      imported: raw.imported,
      beneficiaries: raw.beneficiaries.map(transformSessionBeneficiary),
    }
  }

  async sessionUpdateBeneficiary(
    sessionId: string,
    beneficiaryId: string,
    data: BeneficiaryUpdateRequest
  ): Promise<SessionBeneficiary> {
    const raw = await this.request<BackendSessionBeneficiary>(
      `/sessions/${sessionId}/beneficiaries/${beneficiaryId}`,
      { method: 'PUT', body: JSON.stringify(toBackendBeneficiaryUpdate(data)) }
    )
    return transformSessionBeneficiary(raw)
  }

  async sessionRemoveBeneficiary(
    sessionId: string,
    beneficiaryId: string
  ): Promise<void> {
    await this.request<void>(
      `/sessions/${sessionId}/beneficiaries/${beneficiaryId}`,
      { method: 'DELETE' }
    )
  }

  /** F-022: Reorder a beneficiary (move up or down) */
  async sessionReorderBeneficiary(
    sessionId: string,
    beneficiaryId: string,
    direction: 'up' | 'down'
  ): Promise<void> {
    await this.request<unknown>(
      `/sessions/${sessionId}/beneficiaries/${beneficiaryId}/reorder?direction=${direction}`,
      { method: 'POST' }
    )
  }

  // =========================================================================
  // SESSION SHARED DOCUMENTS
  // =========================================================================

  async sessionUploadSharedDocument(
    sessionId: string,
    file: File,
    documentCode: string
  ): Promise<SharedDocument> {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('document_code', documentCode)
    const raw = await this.uploadRequest<BackendSharedDocument>(
      `/sessions/${sessionId}/shared-documents`,
      formData
    )
    return transformSharedDocument(raw)
  }

  async sessionRemoveSharedDocument(
    sessionId: string,
    documentCode: string
  ): Promise<void> {
    await this.request<void>(
      `/sessions/${sessionId}/shared-documents/${documentCode}`,
      { method: 'DELETE' }
    )
  }

  // =========================================================================
  // CLASSIFICATION + EXTRACTION (Phase 3)
  // =========================================================================

  async sessionClassifyDocuments(
    sessionId: string,
    files: File[]
  ): Promise<ClassifyResponse> {
    const formData = new FormData()
    files.forEach((file) => formData.append('files', file))

    const raw = await this.uploadRequest<BackendClassifyResponse>(
      `/sessions/${sessionId}/classify`,
      formData
    )
    return transformClassifyResponse(raw)
  }

  async sessionConfirmAssignments(
    sessionId: string,
    assignments: Array<{
      file_path: string
      document_type: string
      beneficiary_id: string | null
    }>
  ): Promise<{ confirmed: number }> {
    return this.request(`/sessions/${sessionId}/assignments`, {
      method: 'PUT',
      body: JSON.stringify(assignments),
    })
  }

  async sessionExtractDocuments(
    sessionId: string
  ): Promise<ExtractResponse> {
    const raw = await this.request<BackendExtractResponse>(
      `/sessions/${sessionId}/extract`,
      { method: 'POST' }
    )
    return transformExtractResponse(raw)
  }

  // =========================================================================
  // FORM CONFIG + FORM DATA (DataGrid)
  // =========================================================================

  async sessionGetFormConfig(sessionId: string): Promise<BatchFormConfig> {
    const raw = await this.request<BackendBatchFormConfig>(
      `/sessions/${sessionId}/form-config`
    )
    return transformFormConfig(raw)
  }

  async sessionSaveFormData(
    sessionId: string,
    formDataGrid: Record<string, Record<string, unknown>>
  ): Promise<{ saved: boolean; beneficiaries_updated: number }> {
    return this.request(`/sessions/${sessionId}/form-data`, {
      method: 'PUT',
      body: JSON.stringify(formDataGrid),
    })
  }

  // =========================================================================
  // PAYMENT + SUBMIT (Phase 4)
  // =========================================================================

  async sessionPreparePayment(
    sessionId: string
  ): Promise<PreparePaymentResult> {
    const raw = await this.request<BackendPreparePaymentResponse>(
      `/sessions/${sessionId}/prepare-payment`,
      { method: 'POST' }
    )
    return transformPreparePayment(raw)
  }

  async sessionSubmit(
    sessionId: string,
    data: SubmitRequest
  ): Promise<SubmitResult> {
    const raw = await this.request<BackendSubmitResponse>(
      `/sessions/${sessionId}/submit`,
      { method: 'POST', body: JSON.stringify(toBackendSubmit(data)) }
    )
    return transformSubmitResult(raw)
  }

  // ================================================================
  // WORKFLOW METADATA (F-005/F-006/F-007)
  // ================================================================

  /** Get available workflows with solicitud types and document requirements. */
  async getAvailableWorkflows(): Promise<BatchWorkflowsResponse> {
    return await this.request<BatchWorkflowsResponse>('/workflows', { method: 'GET' })
  }
}

// ============================================================================
// SINGLETON EXPORT
// ============================================================================

export const batchApi = new BatchApiClient()
