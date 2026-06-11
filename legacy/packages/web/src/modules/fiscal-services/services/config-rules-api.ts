/**
 * Fiscal Config Rules API Client
 * Uses shared apiClient (Axios) for automatic token refresh, Accept-Language, etc.
 */

import apiClient from '@/core/api/client'
import { transformKeys, toSnakeCase } from '@/core/utils/api-transform'

import type {
  ConfigRuleResponse,
  ConfigRuleListResponse,
  ConfigRuleCreateInput,
  ConfigRuleUpdateInput,
  RecomputeResult,
} from '@/types/config-rule'

const BASE = '/config-rules'

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

async function del(path: string): Promise<void> {
  await apiClient.delete(`${BASE}${path}`)
}

// ========== Read API ==========

export const configRulesApi = {
  listRules: (params?: {
    configType?: string
    bundleId?: string
    isEnabled?: boolean
    page?: number
    pageSize?: number
  }) => {
    const sp = new URLSearchParams()
    if (params?.configType) sp.set('config_type', params.configType)
    if (params?.bundleId) sp.set('bundle_id', params.bundleId)
    if (params?.isEnabled !== undefined) sp.set('is_enabled', String(params.isEnabled))
    if (params?.page) sp.set('page', String(params.page))
    if (params?.pageSize) sp.set('page_size', String(params.pageSize))
    const q = sp.toString()
    return get<ConfigRuleListResponse>(`/${q ? `?${q}` : ''}`)
  },

  getRule: (id: string) => get<ConfigRuleResponse>(`/${id}`),

  resolve: (params: {
    bundleId: string
    feeType: string
    itemId: string
    ministryId?: number
  }) => {
    const sp = new URLSearchParams()
    sp.set('bundle_id', params.bundleId)
    sp.set('fee_type', params.feeType)
    sp.set('item_id', params.itemId)
    if (params.ministryId) sp.set('ministry_id', String(params.ministryId))
    return get<Record<string, unknown>>(`/resolve?${sp.toString()}`)
  },
}

// ========== Admin API ==========

export const configRulesAdminApi = {
  createRule: (data: ConfigRuleCreateInput) =>
    post<ConfigRuleResponse>('/', data),

  updateRule: (id: string, data: ConfigRuleUpdateInput) =>
    put<ConfigRuleResponse>(`/${id}`, data),

  deleteRule: (id: string) => del(`/${id}`),

  recompute: (bundleId?: string) => {
    const sp = new URLSearchParams()
    if (bundleId) sp.set('bundle_id', bundleId)
    const q = sp.toString()
    return post<RecomputeResult>(`/recompute${q ? `?${q}` : ''}`)
  },
}
