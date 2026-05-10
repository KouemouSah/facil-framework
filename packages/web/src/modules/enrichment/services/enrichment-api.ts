/**
 * Enrichment Admin API Client
 */

import apiClient from '@/core/api/client'
import type {
  EnrichmentStats,
  EnrichmentTask,
  EnrichmentProgress,
  PendingDraft,
  EnrichmentSeedResult,
  ReviewResponse,
  BulkVisibilityResult,
  MinistryOption,
} from '../types/enrichment'

const BASE = '/enrichment'

function snakeToCamel(str: string): string {
  return str.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase())
}

function transformKeys<T>(obj: unknown): T {
  if (obj === null || obj === undefined) return obj as T
  if (Array.isArray(obj)) return obj.map(item => transformKeys(item)) as T
  if (typeof obj !== 'object') return obj as T
  const transformed: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(obj as Record<string, unknown>)) {
    transformed[snakeToCamel(key)] = transformKeys(value)
  }
  return transformed as T
}

async function get<T>(path: string): Promise<T> {
  const { data } = await apiClient.get(`${BASE}${path}`)
  return transformKeys<T>(data)
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const { data } = await apiClient.post(`${BASE}${path}`, body)
  return transformKeys<T>(data)
}

async function put<T>(path: string, body?: unknown): Promise<T> {
  const { data } = await apiClient.put(`${BASE}${path}`, body)
  return transformKeys<T>(data)
}

async function patch<T>(path: string, body?: unknown): Promise<T> {
  const { data } = await apiClient.patch(`${BASE}${path}`, body)
  return transformKeys<T>(data)
}

export const enrichmentApi = {
  // Stats & monitoring
  getStats: () => get<EnrichmentStats>('/admin/stats'),
  getRecent: (limit = 20, statusFilter = 'all') =>
    get<EnrichmentTask[]>(`/admin/recent?limit=${limit}&status_filter=${statusFilter}`),

  // Pending drafts for approval
  getPendingDrafts: () => get<PendingDraft[]>('/admin/pending-drafts'),
  getPendingMinistryDrafts: () => get<PendingDraft[]>('/admin/pending-ministry-drafts'),

  // Approval workflow
  reviewService: (serviceId: number, action: 'approve' | 'reject', editedText?: string) =>
    put<ReviewResponse>(`/admin/review/${serviceId}`, {
      action,
      ...(editedText ? { edited_text: editedText } : {}),
    }),

  reviewMinistry: (ministryId: number, action: 'approve' | 'reject', editedText?: string) =>
    put<Record<string, unknown>>(`/admin/review-ministry/${ministryId}`, {
      action,
      ...(editedText ? { edited_text: editedText } : {}),
    }),

  approveAll: () => post<{ approvedServices: number; approvedMinistries: number }>('/admin/approve-all'),

  // Seed operations (Option B: auto-triggers concurrent processing)
  seedBatch: () => post<EnrichmentSeedResult>('/admin/seed-batch'),
  seedMinistries: () => post<{ enqueuedMinistryDescriptions: number; autoProcessing: boolean }>('/admin/seed-ministries'),

  // Bulk visibility
  bulkVisibility: (visible: boolean, descriptionSource?: string, ministryId?: number) =>
    patch<BulkVisibilityResult>('/admin/bulk-visibility', {
      visible,
      ...(descriptionSource ? { description_source: descriptionSource } : {}),
      ...(ministryId ? { ministry_id: ministryId } : {}),
    }),

  // Ministries for filter dropdown
  getMinistries: () => get<MinistryOption[]>('/admin/ministries'),

  // Manual processing trigger (Option A)
  processNow: () => post<EnrichmentProgress>('/admin/process-now'),

  // Progress polling (during background processing)
  getProgress: () => get<EnrichmentProgress>('/admin/progress'),

  // Retry
  retryTask: (taskId: string) => post<{ taskId: string; newStatus: string }>(`/admin/retry/${taskId}`),
}
