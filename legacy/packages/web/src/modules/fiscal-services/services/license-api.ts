/**
 * Commercial Licenses API Client
 * Uses shared apiClient (Axios) for automatic token refresh, Accept-Language, etc.
 */

import apiClient from '@/core/api/client'
import { transformKeys, toSnakeCase } from '@/core/utils/api-transform'

import type {
  LicenseResponse,
  LicenseListResponse,
  LicenseCreateInput,
  LicenseUpdateInput,
  LicenseRenewInput,
  LicenseStats,
  ObligationResponse,
  ObligationListResponse,
  ObligationStatusUpdateInput,
  BatchObligationUpdateInput,
  ComplianceEventListResponse,
} from '@/types/commercial-license'

const BASE = '/licenses'

async function get<T>(path: string): Promise<T> {
  const { data } = await apiClient.get(`${BASE}${path}`)
  return transformKeys<T>(data)
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const { data } = await apiClient.post(`${BASE}${path}`, body ? toSnakeCase(body) : undefined)
  return transformKeys<T>(data)
}

async function put<T>(path: string, body: unknown): Promise<T> {
  const { data } = await apiClient.put(`${BASE}${path}`, toSnakeCase(body))
  return transformKeys<T>(data)
}

// ========== Read API ==========

export const licenseApi = {
  getStats: (fiscalYear?: number) => {
    const sp = new URLSearchParams()
    if (fiscalYear) sp.set('fiscal_year', String(fiscalYear))
    const q = sp.toString()
    return get<LicenseStats>(`/stats${q ? `?${q}` : ''}`)
  },

  listLicenses: (params?: {
    page?: number
    pageSize?: number
    companyId?: string
    bundleId?: string
    fiscalYear?: number
    status?: string
    search?: string
    sortBy?: string
    sortOrder?: string
  }) => {
    const sp = new URLSearchParams()
    if (params?.page) sp.set('page', String(params.page))
    if (params?.pageSize) sp.set('page_size', String(params.pageSize))
    if (params?.companyId) sp.set('company_id', params.companyId)
    if (params?.bundleId) sp.set('bundle_id', params.bundleId)
    if (params?.fiscalYear) sp.set('fiscal_year', String(params.fiscalYear))
    if (params?.status) sp.set('status', params.status)
    if (params?.search) sp.set('search', params.search)
    if (params?.sortBy) sp.set('sort_by', params.sortBy)
    if (params?.sortOrder) sp.set('sort_order', params.sortOrder)
    const q = sp.toString()
    return get<LicenseListResponse>(`/${q ? `?${q}` : ''}`)
  },

  getLicense: (id: string) => get<LicenseResponse>(`/${id}`),

  getObligations: (licenseId: string, params?: {
    feeType?: string
    status?: string
    page?: number
    pageSize?: number
  }) => {
    const sp = new URLSearchParams()
    if (params?.feeType) sp.set('fee_type', params.feeType)
    if (params?.status) sp.set('status', params.status)
    if (params?.page) sp.set('page', String(params.page))
    if (params?.pageSize) sp.set('page_size', String(params.pageSize))
    const q = sp.toString()
    return get<ObligationListResponse>(`/${licenseId}/obligations${q ? `?${q}` : ''}`)
  },

  getObligationsSummary: (licenseId: string) =>
    get<Record<string, unknown>>(`/${licenseId}/obligations/summary`),

  getObligation: (licenseId: string, obligationId: string) =>
    get<ObligationResponse>(`/${licenseId}/obligations/${obligationId}`),

  getEvents: (licenseId: string, params?: {
    eventType?: string
    obligationId?: string
    page?: number
    pageSize?: number
  }) => {
    const sp = new URLSearchParams()
    if (params?.eventType) sp.set('event_type', params.eventType)
    if (params?.obligationId) sp.set('obligation_id', params.obligationId)
    if (params?.page) sp.set('page', String(params.page))
    if (params?.pageSize) sp.set('page_size', String(params.pageSize))
    const q = sp.toString()
    return get<ComplianceEventListResponse>(`/${licenseId}/events${q ? `?${q}` : ''}`)
  },
}

// ========== Admin API ==========

export const licenseAdminApi = {
  openLicense: (data: LicenseCreateInput) =>
    post<LicenseResponse>('/', data),

  updateLicense: (id: string, data: LicenseUpdateInput) =>
    put<LicenseResponse>(`/${id}`, data),

  renewLicense: (id: string, data: LicenseRenewInput) =>
    post<LicenseResponse>(`/${id}/renew`, data),

  checkPreviousYear: (id: string) =>
    post<{ checked: number; licenseId: string }>(`/${id}/check-previous-year`),

  updateObligation: (licenseId: string, obligationId: string, data: ObligationStatusUpdateInput) =>
    put<ObligationResponse>(`/${licenseId}/obligations/${obligationId}`, data),

  batchUpdateObligations: (licenseId: string, data: BatchObligationUpdateInput) =>
    post<{ updated: number; items: ObligationResponse[] }>(
      `/${licenseId}/obligations/batch-update`, data
    ),

  cronFlagOverdue: () =>
    post<{ flagged: number }>('/cron/flag-overdue'),

  cronApplyPenalties: () =>
    post<{ updated: number }>('/cron/apply-penalties'),
}
