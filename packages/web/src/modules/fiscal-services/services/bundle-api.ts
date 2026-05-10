/**
 * Service Bundles API Client
 * Uses shared apiClient (Axios) for automatic token refresh, Accept-Language, etc.
 */

import apiClient from '@/core/api/client'
import { transformKeys, toSnakeCase } from '@/core/utils/api-transform'

import type {
  CommerceZone,
  ServiceBundle,
  BundleItem,
  BundleWithItems,
  PricingMatrix,
  BundleDocument,
  InstallmentPreview,
  BundleListResponse,
  BundleCreateInput,
  BundleUpdateInput,
  BundleItemCreateInput,
  CopyZonePricesInput,
  FiscalServiceOption,
  BundleStats,
  BulkImportItem,
  BulkImportResult,
  ParsePdfResult,
  SimulatorResponse,
  CommerceTypeOption,
  ServiceBundleBadge,
} from '@/types/service-bundle'

const BASE = '/service-bundles'

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

async function del<T>(path: string): Promise<T> {
  const { data } = await apiClient.delete(`${BASE}${path}`)
  return data as T
}

// ========== Public API ==========

export const bundleApi = {
  listZones: () => get<CommerceZone[]>('/zones'),

  listBundles: (params?: {
    page?: number
    pageSize?: number
    search?: string
    commerceType?: string
    isActive?: boolean
  }) => {
    const sp = new URLSearchParams()
    if (params?.page) sp.set('page', String(params.page))
    if (params?.pageSize) sp.set('page_size', String(params.pageSize))
    if (params?.search) sp.set('search', params.search)
    if (params?.commerceType) sp.set('commerce_type', params.commerceType)
    if (params?.isActive !== undefined) sp.set('is_active', String(params.isActive))
    const q = sp.toString()
    return get<BundleListResponse>(`/${q ? `?${q}` : ''}`)
  },

  getBundle: (id: string) => get<ServiceBundle>(`/${id}`),

  getBundlePricing: (id: string, zoneId: string) =>
    get<BundleWithItems>(`/${id}/pricing?zone_id=${zoneId}`),

  getPricingMatrix: (id: string) => get<PricingMatrix>(`/${id}/matrix`),

  getBundleDocuments: (id: string) => get<BundleDocument[]>(`/${id}/documents`),

  previewInstallments: (id: string, zoneId: string, installments: number) =>
    get<InstallmentPreview>(
      `/${id}/installment-preview?zone_id=${zoneId}&installments=${installments}`
    ),

  getBundlesForService: (fiscalServiceId: number) =>
    get<ServiceBundleBadge[]>(`/by-service/${fiscalServiceId}`),

  simulate: (commerceType: string, zoneCode: string) =>
    get<SimulatorResponse>(
      `/simulator?commerce_type=${encodeURIComponent(commerceType)}&zone_code=${encodeURIComponent(zoneCode)}`
    ),

  listCommerceTypes: () => get<CommerceTypeOption[]>('/commerce-types'),
}

// ========== Admin API ==========

export const bundleAdminApi = {
  getStats: () => get<BundleStats>('/admin/stats'),

  searchServices: (q: string, limit = 15) =>
    get<FiscalServiceOption[]>(`/admin/search-services?q=${encodeURIComponent(q)}&limit=${limit}`),

  createBundle: (data: BundleCreateInput) =>
    post<ServiceBundle>('/admin/bundles', data),

  updateBundle: (id: string, data: BundleUpdateInput) =>
    put<ServiceBundle>(`/admin/bundles/${id}`, data),

  deleteBundle: (id: string) => del<void>(`/admin/bundles/${id}`),

  upsertItem: (bundleId: string, data: BundleItemCreateInput) =>
    post<BundleItem>(`/admin/bundles/${bundleId}/items`, data),

  deleteItem: (itemId: string) => del<void>(`/admin/items/${itemId}`),

  copyZonePrices: (bundleId: string, data: CopyZonePricesInput) =>
    post<{ copiedItems: number }>(`/admin/bundles/${bundleId}/copy-zone-prices`, data),

  exportCsv: async (bundleId: string): Promise<Blob> => {
    const response = await apiClient.get(
      `${BASE}/admin/export/csv?bundle_id=${bundleId}`,
      { responseType: 'blob' }
    )
    return response.data
  },

  exportXlsx: async (bundleId: string): Promise<Blob> => {
    const response = await apiClient.get(
      `${BASE}/admin/export/xlsx?bundle_id=${bundleId}`,
      { responseType: 'blob' }
    )
    return response.data
  },

  reorderItems: (bundleId: string, itemIds: string[]) =>
    post<{ updated: number; total: number }>(
      `/admin/bundles/${bundleId}/reorder-items`,
      { itemIds }
    ),

  bulkImport: (bundleId: string, items: BulkImportItem[]) =>
    post<BulkImportResult>(
      `/admin/bundles/${bundleId}/bulk-import`,
      { items }
    ),

  parsePdf: async (bundleId: string, file: File): Promise<ParsePdfResult> => {
    const formData = new FormData()
    formData.append('file', file)
    const { data } = await apiClient.post(
      `${BASE}/admin/parse-pdf?bundle_id=${bundleId}`,
      formData,
      { headers: { 'Content-Type': 'multipart/form-data' } }
    )
    return transformKeys<ParsePdfResult>(data)
  },
}
