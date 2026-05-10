/**
 * Wizard Session API Client - Cache-First Architecture
 *
 * Follows the ServiceRequestsApiClient pattern for consistency.
 * All endpoints target /api/v1/wizard-sessions.
 *
 * @since v2.0 - Cache-first wizard migration
 * @see .claude/plans/CACHE_FIRST_WIZARD_MIGRATION_PLAN.md
 */

import { getAuthData, setAuthData, clearAuthData } from '@/core/auth/storage'
import type {
  BackendWizardSessionResponse,
  BackendDocumentPreviewResponse,
  BackendPreparePaymentResponse,
  BackendPersistResult,
  BackendInitiatePaymentResponse,
  WizardSession,
  DocumentPreview,
  PreparePaymentResult,
  PersistResult,
  InitiatePaymentResult,
  WizardSessionCreateRequest,
  DocumentConfirmRequest,
  FormDataSaveRequest,
} from '../types/wizard-session'
import type { FormConfigResponse } from '../types/form-config'
import {
  transformSession,
  transformDocumentPreview,
  transformPreparePayment,
  transformPersistResult,
  transformInitiatePayment,
} from '../types/wizard-session'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const API_VERSION = '/api/v1'
const ENDPOINT_BASE = '/wizard-sessions'

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
// WIZARD SESSION API CLIENT
// ============================================================================

class WizardSessionApiClient {
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
   * Handles concurrent 401s with a queue to avoid multiple refresh calls.
   */
  private async handleTokenRefresh(): Promise<string | null> {
    if (isRefreshing) {
      // Another request is already refreshing — wait for it
      return new Promise<string>((resolve, reject) => {
        failedQueue.push({ resolve, reject })
      })
    }

    isRefreshing = true
    const authData = getAuthData()

    if (!authData?.refresh_token) {
      this.handleAuthFailure()
      isRefreshing = false
      return null
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
        throw new Error(`Refresh failed: ${response.status}`)
      }

      const { access_token, refresh_token } = await response.json()

      setAuthData({
        ...authData,
        access_token,
        refresh_token,
      })

      console.log('[WizardSession] Token refreshed successfully')
      processQueue(null, access_token)
      isRefreshing = false
      return access_token
    } catch (error) {
      console.error('[WizardSession] Token refresh failed:', error)
      processQueue(error as Error, null)
      this.handleAuthFailure()
      isRefreshing = false
      return null
    }
  }

  private handleAuthFailure(): void {
    clearAuthData()
    if (typeof window !== 'undefined') {
      const pathParts = window.location.pathname.split('/')
      const locale =
        pathParts[1] && ['es', 'fr', 'en'].includes(pathParts[1])
          ? pathParts[1]
          : 'es'
      window.location.href = `/${locale}/auth`
    }
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {},
    _isRetry = false,
  ): Promise<T> {
    const token = this.getToken()
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    }

    const url = `${this.baseUrl}${endpoint}`
    console.log(`[WizardSession] ${options.method || 'GET'} ${url}`)

    try {
      const response = await fetch(url, {
        ...options,
        headers,
      })

      console.log(`[WizardSession] Response status: ${response.status}`)

      // Handle 401 with automatic token refresh (one retry only)
      if (response.status === 401 && !_isRetry) {
        console.log('[WizardSession] 401 detected, attempting token refresh...')
        const newToken = await this.handleTokenRefresh()
        if (newToken) {
          return this.request<T>(endpoint, options, true)
        }
      }

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        let errorMessage = `API Error: ${response.status}`
        if (errorData.detail) {
          if (typeof errorData.detail === 'string') {
            errorMessage = errorData.detail
          } else if (typeof errorData.detail === 'object') {
            const locale =
              typeof window !== 'undefined'
                ? document.documentElement.lang || 'es'
                : 'es'
            errorMessage =
              (locale === 'es'
                ? errorData.detail.message_es
                : locale === 'fr'
                  ? errorData.detail.message_fr
                  : errorData.detail.message_en) ||
              errorData.detail.message ||
              errorData.detail.msg ||
              JSON.stringify(errorData.detail)
          }
        }
        console.error(`[WizardSession] Error: ${errorMessage}`)
        throw new Error(errorMessage)
      }

      if (response.status === 204) {
        return {} as T
      }

      const data = await response.json()
      console.log(`[WizardSession] Success`)
      return data
    } catch (error) {
      console.error(`[WizardSession] Fetch error:`, error)
      throw error
    }
  }

  private async uploadRequest<T>(
    endpoint: string,
    formData: FormData,
    _isRetry = false,
  ): Promise<T> {
    const token = this.getToken()
    const headers: HeadersInit = {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    }

    const url = `${this.baseUrl}${endpoint}`
    console.log(`[WizardSession] UPLOAD ${url}`)

    const response = await fetch(url, {
      method: 'POST',
      headers,
      body: formData,
    })

    // Handle 401 with automatic token refresh (one retry only)
    if (response.status === 401 && !_isRetry) {
      console.log('[WizardSession] Upload 401 detected, attempting token refresh...')
      const newToken = await this.handleTokenRefresh()
      if (newToken) {
        return this.uploadRequest<T>(endpoint, formData, true)
      }
    }

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      let errorMessage = `Upload Error: ${response.status}`
      if (errorData.detail) {
        if (typeof errorData.detail === 'string') {
          errorMessage = errorData.detail
        } else if (typeof errorData.detail === 'object') {
          const locale =
            typeof window !== 'undefined'
              ? document.documentElement.lang || 'es'
              : 'es'
          errorMessage =
            (locale === 'es'
              ? errorData.detail.message_es
              : locale === 'fr'
                ? errorData.detail.message_fr
                : errorData.detail.message_en) ||
            errorData.detail.message ||
            errorData.detail.msg ||
            JSON.stringify(errorData.detail)
        }
      }
      throw new Error(errorMessage)
    }

    return response.json()
  }

  // ==========================================================================
  // SESSION LIFECYCLE
  // ==========================================================================

  /**
   * Start a new wizard session (cache only, no DB write).
   * POST /wizard-sessions
   */
  async createSession(
    data: WizardSessionCreateRequest
  ): Promise<WizardSession> {
    const raw = await this.request<BackendWizardSessionResponse>('', {
      method: 'POST',
      body: JSON.stringify(data),
    })
    return transformSession(raw)
  }

  /**
   * Get existing wizard session state.
   * GET /wizard-sessions/{sessionId}
   */
  async getSession(sessionId: string): Promise<WizardSession> {
    const raw = await this.request<BackendWizardSessionResponse>(
      `/${sessionId}`
    )
    return transformSession(raw)
  }

  /**
   * Cancel and delete a wizard session.
   * DELETE /wizard-sessions/{sessionId}
   */
  async cancelSession(sessionId: string, reason?: string): Promise<void> {
    const params = reason ? `?reason=${encodeURIComponent(reason)}` : ''
    await this.request<Record<string, never>>(`/${sessionId}${params}`, {
      method: 'DELETE',
    })
  }

  // ==========================================================================
  // DOCUMENT OPERATIONS
  // ==========================================================================

  /**
   * Upload and preview document extraction.
   * POST /wizard-sessions/{sessionId}/documents/preview?document_code=xxx
   */
  async previewDocument(
    sessionId: string,
    documentCode: string,
    file: File
  ): Promise<DocumentPreview> {
    const formData = new FormData()
    formData.append('file', file)

    const raw = await this.uploadRequest<BackendDocumentPreviewResponse>(
      `/${sessionId}/documents/preview?document_code=${encodeURIComponent(documentCode)}`,
      formData
    )
    return transformDocumentPreview(raw)
  }

  /**
   * Confirm document extraction with optional corrections.
   * POST /wizard-sessions/{sessionId}/documents/confirm
   */
  async confirmDocument(
    sessionId: string,
    data: DocumentConfirmRequest
  ): Promise<WizardSession> {
    const raw = await this.request<BackendWizardSessionResponse>(
      `/${sessionId}/documents/confirm`,
      {
        method: 'POST',
        body: JSON.stringify(data),
      }
    )
    return transformSession(raw)
  }

  /**
   * Delete a document from wizard session.
   * DELETE /wizard-sessions/{sessionId}/documents/{documentCode}
   */
  async deleteDocument(
    sessionId: string,
    documentCode: string
  ): Promise<WizardSession> {
    const raw = await this.request<BackendWizardSessionResponse>(
      `/${sessionId}/documents/${encodeURIComponent(documentCode)}`,
      { method: 'DELETE' }
    )
    return transformSession(raw)
  }

  // ==========================================================================
  // VAULT DOCUMENT (Phase 2 — auto-fill from vault)
  // ==========================================================================

  /**
   * Use a vault document in the wizard session (no file upload needed).
   * POST /wizard-sessions/{sessionId}/documents/use-vault
   *
   * @param sessionId - Session ID
   * @param documentCode - Document code to fill (e.g. 'dip')
   * @param vaultDocumentId - UUID of the vault document
   */
  async useVaultDocument(
    sessionId: string,
    documentCode: string,
    vaultDocumentId: string
  ): Promise<WizardSession> {
    const raw = await this.request<BackendWizardSessionResponse>(
      `/${sessionId}/documents/use-vault`,
      {
        method: 'POST',
        body: JSON.stringify({
          document_code: documentCode,
          vault_document_id: vaultDocumentId,
        }),
      }
    )
    return transformSession(raw)
  }

  // ==========================================================================
  // FORM DATA
  // ==========================================================================

  /**
   * Save form data to session.
   * PUT /wizard-sessions/{sessionId}/form-data
   */
  async saveFormData(
    sessionId: string,
    data: FormDataSaveRequest
  ): Promise<WizardSession> {
    const raw = await this.request<BackendWizardSessionResponse>(
      `/${sessionId}/form-data`,
      {
        method: 'PUT',
        body: JSON.stringify(data),
      }
    )
    return transformSession(raw)
  }

  // ==========================================================================
  // FORM CONFIG (Dynamic rendering)
  // ==========================================================================

  /**
   * Get dynamic form configuration for a session step.
   * GET /wizard-sessions/{sessionId}/form-config/{stepId}
   */
  async getFormConfig(
    sessionId: string,
    stepId: string
  ): Promise<FormConfigResponse> {
    return this.request<FormConfigResponse>(
      `/${sessionId}/form-config/${encodeURIComponent(stepId)}`
    )
  }

  // ==========================================================================
  // PAYMENT FLOW
  // ==========================================================================

  /**
   * Validate session and calculate tariff for payment.
   * POST /wizard-sessions/{sessionId}/prepare-payment
   */
  async preparePayment(
    sessionId: string
  ): Promise<PreparePaymentResult> {
    const raw = await this.request<BackendPreparePaymentResponse>(
      `/${sessionId}/prepare-payment`,
      { method: 'POST' }
    )
    return transformPreparePayment(raw)
  }

  /**
   * Persist session to database (atomic transaction).
   * POST /wizard-sessions/{sessionId}/persist
   */
  async persistSession(
    sessionId: string,
    paymentId?: string
  ): Promise<PersistResult> {
    const params = paymentId
      ? `?payment_id=${encodeURIComponent(paymentId)}`
      : ''
    const raw = await this.request<BackendPersistResult>(
      `/${sessionId}/persist${params}`,
      { method: 'POST' }
    )
    return transformPersistResult(raw)
  }

  /**
   * Atomically persist session + initiate payment (single endpoint).
   * POST /wizard-sessions/{sessionId}/initiate-payment
   *
   * Replaces the two-call pattern (persist + initiate-payment) with
   * a single atomic operation. On failure, session stays in cache for retry.
   */
  async initiatePayment(
    sessionId: string,
    paymentMethod: string,
    phoneNumber?: string,
    treasuryLocationId?: string,
  ): Promise<InitiatePaymentResult> {
    const raw = await this.request<BackendInitiatePaymentResponse>(
      `/${sessionId}/initiate-payment`,
      {
        method: 'POST',
        body: JSON.stringify({
          payment_method: paymentMethod,
          phone_number: phoneNumber || null,
          treasury_location_id: treasuryLocationId || null,
        }),
      }
    )
    return transformInitiatePayment(raw)
  }

  // ==========================================================================
  // SITE SELECTION (for ALL workflows, before payment)
  // ==========================================================================

  /**
   * Get available processing sites for a workflow.
   * GET /wizard-sessions/{sessionId}/available-sites
   */
  async getAvailableSites(sessionId: string): Promise<{
    workflowCode: string
    sites: Array<{
      id: string
      entityCode: string
      city: string
      locationName: string
      locationAddress: string | null
      isMainOffice: boolean
    }>
    cities: Record<string, Array<{
      id: string
      entityCode: string
      city: string
      locationName: string
      locationAddress: string | null
      isMainOffice: boolean
    }>>
    count: number
  }> {
    const raw = await this.request<{
      workflow_code: string
      sites: Array<{
        id: string
        entity_code: string
        city: string
        location_name: string
        location_address: string | null
        is_main_office: boolean
      }>
      cities: Record<string, Array<{
        id: string
        entity_code: string
        city: string
        location_name: string
        location_address: string | null
        is_main_office: boolean
      }>>
      count: number
    }>(`/${sessionId}/available-sites`)

    // Transform snake_case → camelCase
    const transformSite = (s: { id: string; entity_code: string; city: string; location_name: string; location_address: string | null; is_main_office: boolean }) => ({
      id: s.id,
      entityCode: s.entity_code,
      city: s.city,
      locationName: s.location_name,
      locationAddress: s.location_address,
      isMainOffice: s.is_main_office,
    })

    const transformedCities: Record<string, Array<ReturnType<typeof transformSite>>> = {}
    for (const [city, sites] of Object.entries(raw.cities)) {
      transformedCities[city] = sites.map(transformSite)
    }

    return {
      workflowCode: raw.workflow_code,
      sites: raw.sites.map(transformSite),
      cities: transformedCities,
      count: raw.count,
    }
  }

  /**
   * Save site selection to session cache.
   * POST /wizard-sessions/{sessionId}/select-site
   */
  async saveSiteSelection(
    sessionId: string,
    data: {
      entityLocationId: string
      locationName: string
      city: string
      entityCode?: string | null
    },
  ): Promise<{ success: boolean }> {
    const raw = await this.request<{ success: boolean }>(
      `/${sessionId}/select-site`,
      {
        method: 'POST',
        body: JSON.stringify({
          entity_location_id: data.entityLocationId,
          location_name: data.locationName,
          city: data.city,
          entity_code: data.entityCode || null,
        }),
      }
    )
    return raw
  }

  // ==========================================================================
  // APPOINTMENT SELECTION (session-based, before payment)
  // ==========================================================================

  /**
   * Get appointment locations for a wizard session.
   * GET /wizard-sessions/{sessionId}/appointments/locations
   */
  async getAppointmentLocations(sessionId: string): Promise<{
    entityCode: string
    locations: Array<{
      id: string
      entityCode: string
      locationCode: string
      locationName: string
      city: string
      province: string | null
      region: string | null
      address: string | null
      phone: string | null
      email: string | null
      isMainOffice: boolean
    }>
    count: number
  }> {
    const raw = await this.request<{
      entity_code: string
      locations: Array<{
        id: string
        entity_code: string
        location_code: string
        location_name: string
        city: string
        province: string | null
        region: string | null
        address: string | null
        phone: string | null
        email: string | null
        is_main_office: boolean
      }>
      count: number
    }>(`/${sessionId}/appointments/locations`)

    return {
      entityCode: raw.entity_code,
      locations: raw.locations.map((l) => ({
        id: l.id,
        entityCode: l.entity_code,
        locationCode: l.location_code,
        locationName: l.location_name,
        city: l.city,
        province: l.province,
        region: l.region,
        address: l.address,
        phone: l.phone,
        email: l.email,
        isMainOffice: l.is_main_office,
      })),
      count: raw.count,
    }
  }

  /**
   * Get available days for calendar rendering (session-based).
   * GET /wizard-sessions/{sessionId}/appointments/available-days
   */
  async getAvailableDays(
    sessionId: string,
    entityLocationId: string,
    fromDate?: string,
    toDate?: string,
  ): Promise<{
    days: Array<{ date: string; timeSlotCount: number; totalSlotsRemaining: number }>
    minDate?: string
  }> {
    const params = new URLSearchParams({ entity_location_id: entityLocationId })
    if (fromDate) params.append('from_date', fromDate)
    if (toDate) params.append('to_date', toDate)

    const raw = await this.request<{
      days: Array<{ slot_date: string; time_slot_count: number; total_slots_remaining: number }>
      min_date?: string
    }>(`/${sessionId}/appointments/available-days?${params.toString()}`)

    return {
      days: raw.days.map((d) => ({
        date: d.slot_date,
        timeSlotCount: d.time_slot_count,
        totalSlotsRemaining: d.total_slots_remaining,
      })),
      minDate: raw.min_date,
    }
  }

  /**
   * Get available time slots for a location (session-based).
   * GET /wizard-sessions/{sessionId}/appointments/available-slots
   */
  async getAvailableSlots(
    sessionId: string,
    entityLocationId: string,
    fromDate?: string,
    limit?: number,
  ): Promise<{
    entityCode: string
    locationName: string
    fromDate: string
    slots: Array<{
      slotDate: string
      slotTime: string
      locationName: string
      locationAddress: string | null
      slotsRemaining: number
      city: string | null
    }>
    count: number
    hasAvailability: boolean
  }> {
    const params = new URLSearchParams({ entity_location_id: entityLocationId })
    if (fromDate) params.append('from_date', fromDate)
    if (limit) params.append('limit', String(limit))

    const raw = await this.request<{
      entity_code: string
      location_name: string
      from_date: string
      slots: Array<{
        slot_date: string
        slot_time: string
        location_name: string
        location_address: string | null
        slots_remaining: number
        city: string | null
      }>
      count: number
      has_availability: boolean
    }>(`/${sessionId}/appointments/available-slots?${params.toString()}`)

    return {
      entityCode: raw.entity_code,
      locationName: raw.location_name,
      fromDate: raw.from_date,
      slots: raw.slots.map((s) => ({
        slotDate: s.slot_date,
        slotTime: s.slot_time,
        locationName: s.location_name,
        locationAddress: s.location_address,
        slotsRemaining: s.slots_remaining,
        city: s.city,
      })),
      count: raw.count,
      hasAvailability: raw.has_availability,
    }
  }

  /**
   * Save appointment selection to session cache (not a real hold).
   * POST /wizard-sessions/{sessionId}/appointments/select
   */
  async saveAppointmentSelection(
    sessionId: string,
    data: {
      entityLocationId: string
      locationName: string
      city: string
      appointmentDate: string
      appointmentTime: string
      slotConfigId?: string | null
    },
  ): Promise<{ success: boolean }> {
    const raw = await this.request<{ success: boolean }>(
      `/${sessionId}/appointments/select`,
      {
        method: 'POST',
        body: JSON.stringify({
          entity_location_id: data.entityLocationId,
          location_name: data.locationName,
          city: data.city,
          appointment_date: data.appointmentDate,
          appointment_time: data.appointmentTime,
          slot_config_id: data.slotConfigId || null,
        }),
      }
    )
    return raw
  }
}

// ============================================================================
// SINGLETON EXPORT
// ============================================================================

export const wizardSessionApi = new WizardSessionApiClient()
