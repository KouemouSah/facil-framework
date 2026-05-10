/**
 * Bundle Workflow API Client
 * Endpoints for BUNDLE_PAYMENT workflow (citizen-facing).
 * Uses shared apiClient (Axios) with automatic token refresh + Accept-Language.
 */

import apiClient from '@/core/api/client'
import { transformKeys, toSnakeCase } from '@/core/utils/api-transform'

import type {
  BundleInitiateResponse,
  BundleValidateSelectionResponse,
  BundlePaymentResult,
  MyCompaniesResponse,
  SearchCompanyResponse,
  ClassifyPreviewResponse,
} from '../types'

const BASE = '/bundle-workflow'

async function get<T>(path: string, params?: Record<string, unknown>): Promise<T> {
  const searchParams = new URLSearchParams()
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null) searchParams.set(k, String(v))
    }
  }
  const query = searchParams.toString()
  const url = query ? `${BASE}${path}?${query}` : `${BASE}${path}`
  const { data } = await apiClient.get(url)
  return transformKeys<T>(data)
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const { data } = await apiClient.post(
    `${BASE}${path}`,
    body ? toSnakeCase(body) : undefined,
  )
  return transformKeys<T>(data)
}

// ========== Bundle Workflow API ==========

export const bundleWorkflowApi = {
  /**
   * Get user's companies with pending obligation counts (max 5).
   * Sorted by urgency (pending obligations first).
   */
  getMyCompanies: (fiscalYear?: number): Promise<MyCompaniesResponse> =>
    get('/my-companies', { fiscal_year: fiscalYear }),

  /**
   * Search companies eligible for bundle payment.
   * Filters: regimen_fiscal='bundle', is_active=true.
   */
  searchCompany: (q: string, limit: number = 10): Promise<SearchCompanyResponse> =>
    get('/search-company', { q, limit }),

  /**
   * Verify company, find/create license, return obligations for review.
   * Main entry point after company identification.
   */
  initiate: (companyId: string, fiscalYear?: number): Promise<BundleInitiateResponse> =>
    post('/initiate', { companyId, fiscalYear }),

  /**
   * Preview classification WITHOUT creating company/license.
   * Returns extracted data, resolved zone, classification, available options.
   */
  classifyPreview: (
    extraction: Record<string, unknown>,
    zoneId?: string,
  ): Promise<ClassifyPreviewResponse> =>
    post('/classify-preview', { extraction, zone_id: zoneId || undefined }),

  /**
   * Create company from OCR extraction, classify, then initiate workflow.
   * Accepts optional zone_id/commerce_type overrides if auto-resolution failed.
   */
  initiateFromUpload: (
    extraction: Record<string, unknown>,
    fiscalYear?: number,
    zoneId?: string,
    commerceType?: string,
  ): Promise<BundleInitiateResponse> =>
    post('/initiate-from-upload', { extraction, fiscalYear, zoneId, commerceType }),

  /**
   * Validate mode + obligation selection before payment.
   */
  validateSelection: (
    licenseId: string,
    processingMode: string,
    selectedObligationIds?: string[],
  ): Promise<BundleValidateSelectionResponse> =>
    post('/validate-selection', {
      licenseId,
      processingMode,
      selectedObligationIds,
    }),

  /**
   * Create service_request + service_payment + link obligations (atomic).
   * For mobile_money: returns redirect_url (BANGE).
   * For cash: returns payment reference for agent validation.
   */
  initiatePayment: (params: {
    licenseId: string
    processingMode: string
    paymentMethod: string
    selectedObligationIds: string[]
    phoneNumber?: string
    wizardSessionId?: string
  }): Promise<BundlePaymentResult> =>
    post('/initiate-payment', params),

  // ========== Citizen Company Management ==========

  /** Company detail with license + obligations + inspections */
  getMyCompanyDetail: (companyId: string, fiscalYear?: number) =>
    get<CompanyDetailResponse>(`/my-companies/${companyId}`, { fiscal_year: fiscalYear }),

  /** Payment history for a company (paginated) */
  getMyCompanyPayments: (companyId: string, page = 1, pageSize = 20) =>
    get<CompanyPaymentsResponse>(`/my-companies/${companyId}/payments`, { page, page_size: pageSize }),

  /** Download license PDF for citizen's own company */
  downloadLicensePdf: async (companyId: string, language = 'es'): Promise<void> => {
    const { data } = await apiClient.get(
      `${BASE}/my-companies/${companyId}/license-pdf?language=${language}`,
      { responseType: 'blob' },
    )
    const blob = new Blob([data], { type: 'application/pdf' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `license-${companyId}.pdf`
    a.click()
    URL.revokeObjectURL(url)
  },
}

// ========== Citizen Company Types ==========

export interface CompanyDetailResponse {
  company: {
    id: string; legalName: string; nif: string | null; registrationNumber: string | null
    regimenFiscal: string | null; commerceType: string | null; objetoSocial: string | null
    formaJuridica: string | null; isActive: boolean; isVerified: boolean
    zoneCode: string | null; cityName: string | null
  }
  license: {
    id: string; status: string; fiscalYear: number; totalAmount: number
    amountPaid: number; amountRemaining: number; penaltyAmount: number
    obligationsTotal: number; obligationsPaid: number
    deadline: string | null; completedAt: string | null; expiryDate: string
    certificateNumber: string | null; certificateUrl: string | null
  } | null
  obligations: Array<{
    id: string; feeType: string; amount: number; penaltyAmount: number
    status: string; dueDate: string | null; paidAt: string | null
    serviceName: string | null; serviceCode: string | null; ministryName: string | null
  }>
  inspections: Array<{
    id: string; date: string | null; status: string; result: string | null
    conforme: boolean | null; activityDeclared: string | null; activityObserved: string | null
    miseEnDemeure: boolean; miseEnDemeureDeadline: string | null
    sealApplied: boolean; sealReason: string | null; sealApprovedAt: string | null
    paymentCollected: boolean; paymentReceipt: string | null; paymentAmount: number | null
    notes: string | null; createdAt: string | null
  }>
  fiscalYear: number
}

export interface CompanyPaymentsResponse {
  payments: Array<{
    id: string; reference: string; srReference: string | null
    amount: number; currency: string; method: string; status: string
    feeType: string | null; entityCode: string | null
    receiptNumber: string | null; receiptUrl: string | null
    createdAt: string | null; validatedAt: string | null
  }>
  total: number; page: number; pageSize: number
}
