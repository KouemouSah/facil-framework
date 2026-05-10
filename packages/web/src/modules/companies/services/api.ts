/**
 * Companies API Service
 * Uses shared apiClient (Axios) for automatic token refresh, Accept-Language, etc.
 */

import apiClient from '@/core/api/client'
import { toSnakeCase } from '@/core/utils/api-transform'

import type {
  Company,
  CompanyCreate,
  CompanyUpdate,
  PaginatedCompaniesResponse,
  CompanyMember,
  CompanyMemberRole,
  CompanyAdminListResponse,
  CompanyStats,
  CompanySearchResult,
  CompanyClassifyResult,
  ZoneStats,
  MinistryStatsResponse,
  GlobalStats,
  CompanyDebtResponse,
  PublicDirectoryResponse,
  PublicZone,
  LookupResult,
  CompanyAnalytics,
} from '../types'

const BASE = '/companies'

// NOTE: No transformKeys — Company types use snake_case matching backend/DB.
// Other modules (accountant) extend Company and depend on snake_case fields.
async function get<T>(path: string): Promise<T> {
  const { data } = await apiClient.get(`${BASE}${path}`)
  return data as T
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const { data } = await apiClient.post(`${BASE}${path}`, body ? toSnakeCase(body) : undefined)
  return data as T
}

async function put<T>(path: string, body: unknown): Promise<T> {
  const { data } = await apiClient.put(`${BASE}${path}`, toSnakeCase(body))
  return data as T
}

async function del<T>(path: string): Promise<T> {
  const { data } = await apiClient.delete(`${BASE}${path}`)
  return data as T
}

// ========== User-Scoped API ==========

export const companiesApi = {
  getAll: (params?: { page?: number; pageSize?: number }) => {
    const sp = new URLSearchParams()
    if (params?.page) sp.set('page', String(params.page))
    if (params?.pageSize) sp.set('page_size', String(params.pageSize))
    const q = sp.toString()
    return get<PaginatedCompaniesResponse>(`${q ? `?${q}` : ''}`)
  },

  getById: (id: string) => get<Company>(`/${id}`),

  create: (data: CompanyCreate) => post<Company>('', data),

  update: (id: string, data: CompanyUpdate) => put<Company>(`/${id}`, data),

  /**
   * @deprecated The citizen surface no longer offers a direct delete CTA. The
   * backend route still exists but is now gated behind `company.hard_delete`
   * permission AND requires the company to have been archived first
   * (migration 314). Use {@link archive} from the citizen surface and
   * {@link hardDelete} from admin tooling.
   */
  delete: (id: string) => del<{ message: string }>(`/${id}`),

  /**
   * Soft-delete (archive) a company — citizen surface, owner-only.
   *
   * Backend may return 409 Conflict with body
   * `{ detail: { message, blockers: { active_licenses, pending_payments,
   *   open_requests, active_inspections } } }` if the company still has
   * active dependencies. Callers should surface the per-bucket counts to
   * the user instead of treating it as a generic error.
   */
  archive: (id: string) =>
    post<{ message: string; archived_at: string | null }>(`/${id}/archive`),

  /** Restore an archived company. Admin only — requires `company.unarchive`. */
  unarchive: (id: string) => post<{ message: string }>(`/${id}/unarchive`),

  /**
   * Permanently delete an archived company. Admin only — requires
   * `company.hard_delete`. Backend enforces `archived_at IS NOT NULL` AND
   * re-checks blockers; the previous "owner can hard-delete" path is gone.
   */
  hardDelete: (id: string) => del<{ message: string }>(`/${id}`),
}

// ========== Members API ==========

export const companyMembersApi = {
  getAll: (companyId: string) => get<CompanyMember[]>(`/${companyId}/members`),

  add: (companyId: string, memberUserId: string, role: CompanyMemberRole) =>
    post<CompanyMember>(`/${companyId}/members`, { memberUserId, role }),

  remove: async (companyId: string, userId: string) => {
    await apiClient.delete(`${BASE}/${companyId}/members/${userId}`)
  },

  updateRole: (companyId: string, userId: string, role: CompanyMemberRole) =>
    put<CompanyMember>(`/${companyId}/members/${userId}/role`, { role }),
}

// ========== Admin API ==========

export interface CompanyAdminListParams {
  page?: number
  pageSize?: number
  search?: string
  isActive?: boolean
  isVerified?: boolean
  regimenFiscal?: string
  zoneId?: string
  cityId?: string
  /**
   * Archive scope. Defaults to "active" (legacy behaviour). Use "archived" on
   * the dedicated /admin/companies/archived view, "all" for cross-state audits.
   */
  archived?: 'active' | 'archived' | 'all'
  sortBy?: string
  sortOrder?: string
}

export const companiesAdminApi = {
  listAll: (params?: CompanyAdminListParams) => {
    const sp = new URLSearchParams()
    if (params?.page) sp.set('page', String(params.page))
    if (params?.pageSize) sp.set('page_size', String(params.pageSize))
    if (params?.search) sp.set('search', params.search)
    if (params?.isActive !== undefined) sp.set('is_active', String(params.isActive))
    if (params?.isVerified !== undefined) sp.set('is_verified', String(params.isVerified))
    if (params?.regimenFiscal) sp.set('regimen_fiscal', params.regimenFiscal)
    if (params?.zoneId) sp.set('zone_id', params.zoneId)
    if (params?.cityId) sp.set('city_id', params.cityId)
    if (params?.archived) sp.set('archived', params.archived)
    if (params?.sortBy) sp.set('sort_by', params.sortBy)
    if (params?.sortOrder) sp.set('sort_order', params.sortOrder)
    const q = sp.toString()
    return get<CompanyAdminListResponse>(`/admin/all${q ? `?${q}` : ''}`)
  },

  getStats: () => get<CompanyStats>('/admin/stats'),

  search: (q: string, limit: number = 10) =>
    get<CompanySearchResult[]>(`/admin/search?q=${encodeURIComponent(q)}&limit=${limit}`),

  verify: (id: string, isVerified: boolean) =>
    put<Company>(`/admin/${id}/verify`, { is_verified: isVerified }),

  delete: (id: string) => del<{ message: string }>(`/${id}`),

  classify: (id: string) =>
    post<CompanyClassifyResult>(`/admin/${id}/classify`),

  createWithLicense: (data: {
    legalName: string
    commerceType: string
    zoneCode: string
    representanteLegal: string
    nif?: string
    registrationNumber?: string
    formaJuridica?: string
    sectorActividad?: string
    subsectorActividad?: string
    objetoSocial?: string
    address?: string
    phone?: string
    email?: string
    employeeCount?: number
    cityName?: string
  }) => post<{
    company_id: string
    company_name: string
    license_id: string
    license_status: string
    obligations_count: number
    total_amount: number
    zone_code: string
    fiscal_year: number
    source: string
  }>('/admin/create-with-license', data),
}

// ========== Supervisor API (entity-scoped) ==========

export interface CompanySupervisorListParams {
  page?: number
  pageSize?: number
  search?: string
  isActive?: boolean
  isVerified?: boolean
  regimenFiscal?: string
  sortBy?: string
  sortOrder?: string
}

export const companiesSupervisorApi = {
  listMyCompanies: (params?: CompanySupervisorListParams) => {
    const sp = new URLSearchParams()
    if (params?.page) sp.set('page', String(params.page))
    if (params?.pageSize) sp.set('page_size', String(params.pageSize))
    if (params?.search) sp.set('search', params.search)
    if (params?.isActive !== undefined) sp.set('is_active', String(params.isActive))
    if (params?.isVerified !== undefined) sp.set('is_verified', String(params.isVerified))
    if (params?.regimenFiscal) sp.set('regimen_fiscal', params.regimenFiscal)
    if (params?.sortBy) sp.set('sort_by', params.sortBy)
    if (params?.sortOrder) sp.set('sort_order', params.sortOrder)
    const q = sp.toString()
    return get<CompanyAdminListResponse>(`/supervisor/my-companies${q ? `?${q}` : ''}`)
  },

  getStats: () => get<CompanyStats>('/supervisor/stats'),
}

// ========== Dashboard API ==========

export const companyDashboardApi = {
  /** All zones stats — admin choropleth map */
  getZoneStats: () => get<{ zones: ZoneStats[] }>('/dashboard/zone-stats'),

  /** My zone stats — supervisor site */
  getMyZoneStats: () => get<{ zone: ZoneStats | null }>('/dashboard/zone-stats/mine'),

  /** Ministry stats — supervisor ministry (all zones, their items) */
  getMinistryStats: () => get<MinistryStatsResponse>('/dashboard/ministry-stats'),

  /** Global stats — admin overview KPIs */
  getGlobalStats: () => get<GlobalStats>('/dashboard/global-stats'),

  /** Refresh materialized views (cron) */
  refreshStats: () => post<{ refreshed: string[]; count: number }>('/dashboard/cron/refresh-company-stats'),

  /** Rich cross-tabulated analytics for pro dashboards */
  getAnalytics: () => get<CompanyAnalytics>('/dashboard/analytics'),
}

// ========== Ministry Debt API ==========

export const companyMinistryApi = {
  /** Company debt for agent's ministry — detail complet */
  getCompanyDebt: (companyId: string) =>
    get<CompanyDebtResponse>(`/ministry/company-debt/${companyId}`),

  /** National company lookup — ONRC agents */
  lookup: (q: string) =>
    get<{ results: LookupResult[]; count: number; query: string }>(
      `/ministry/lookup?q=${encodeURIComponent(q)}`
    ),
}

// ========== Public Directory API (no auth — uses plain axios, no interceptors) ==========

import axios from 'axios'
import { appConfig } from '@/core/config'

const publicClient = axios.create({
  baseURL: `${appConfig.api.baseUrl}/api/${appConfig.api.version}/public/companies`,
  timeout: 15000,
})

export const companyPublicApi = {
  /** Public directory search with advanced filters */
  search: (params: {
    q?: string
    zone_id?: string
    sector?: string
    forma_juridica?: string
    provincia?: string
    ciudad?: string
    sort_by?: string
    sort_order?: string
    page?: number
    page_size?: number
  }) => {
    const sp = new URLSearchParams()
    if (params.q) sp.set('q', params.q)
    if (params.zone_id) sp.set('zone_id', params.zone_id)
    if (params.sector) sp.set('sector', params.sector)
    if (params.forma_juridica) sp.set('forma_juridica', params.forma_juridica)
    if (params.provincia) sp.set('provincia', params.provincia)
    if (params.ciudad) sp.set('ciudad', params.ciudad)
    if (params.sort_by) sp.set('sort_by', params.sort_by)
    if (params.sort_order) sp.set('sort_order', params.sort_order)
    if (params.page) sp.set('page', String(params.page))
    if (params.page_size) sp.set('page_size', String(params.page_size))
    const q = sp.toString()
    return publicClient.get<PublicDirectoryResponse>(`/search${q ? `?${q}` : ''}`)
      .then(r => r.data)
  },

  getZones: () =>
    publicClient.get<PublicZone[]>('/zones').then(r => r.data),
  getSectors: () =>
    publicClient.get<string[]>('/sectors').then(r => r.data),
  getProvincias: () =>
    publicClient.get<string[]>('/provincias').then(r => r.data),
  getCiudades: (provincia?: string) => {
    const q = provincia ? `?provincia=${encodeURIComponent(provincia)}` : ''
    return publicClient.get<string[]>(`/ciudades${q}`).then(r => r.data)
  },
  getFormasJuridicas: () =>
    publicClient.get<{ value: string; count: number }[]>('/formas-juridicas').then(r => r.data),
}

export default {
  companies: companiesApi,
  members: companyMembersApi,
  admin: companiesAdminApi,
  supervisor: companiesSupervisorApi,
}
