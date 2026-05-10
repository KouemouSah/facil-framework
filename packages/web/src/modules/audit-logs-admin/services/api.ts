/**
 * Audit Logs Admin API Service
 * Aligned with backend audit_routes.py
 */

import { fetchClient } from '@/core/api'
import type {
  AuditLog,
  PaginatedAuditLogsResponse,
  AuditLogStats,
  GeminiUsageStats,
} from '../types'

export const auditLogsApi = {
  /**
   * GET /audit-logs — paginated list with filters
   */
  getAll: async (params?: {
    action?: string
    user_id?: string
    entity_type?: string
    search?: string
    start_date?: string
    end_date?: string
    page?: number
    page_size?: number
  }): Promise<PaginatedAuditLogsResponse> => {
    return fetchClient.get<PaginatedAuditLogsResponse>('/audit-logs', {
      action: params?.action,
      user_id: params?.user_id,
      entity_type: params?.entity_type,
      search: params?.search,
      start_date: params?.start_date,
      end_date: params?.end_date,
      page: params?.page || 1,
      page_size: params?.page_size || 25,
    })
  },

  /**
   * GET /audit-logs/{id}
   */
  getById: async (id: string): Promise<AuditLog> => {
    return fetchClient.get<AuditLog>(`/audit-logs/${id}`)
  },

  /**
   * GET /audit-logs/stats
   */
  getStats: async (params?: {
    start_date?: string
    end_date?: string
  }): Promise<AuditLogStats> => {
    return fetchClient.get<AuditLogStats>('/audit-logs/stats', {
      start_date: params?.start_date,
      end_date: params?.end_date,
    })
  },

  /**
   * GET /users/{user_id}/audit-logs
   */
  getByUser: async (userId: string, params?: {
    action?: string
    page?: number
    page_size?: number
  }): Promise<AuditLog[]> => {
    const response = await fetchClient.get<AuditLog[]>(
      `/users/${userId}/audit-logs`,
      {
        action: params?.action,
        page: params?.page,
        page_size: params?.page_size,
      }
    )
    return response || []
  },
}

export const geminiStatsApi = {
  /**
   * GET /audit-logs/gemini-stats
   */
  getStats: async (days: number = 30): Promise<GeminiUsageStats> => {
    return fetchClient.get<GeminiUsageStats>('/audit-logs/gemini-stats', { days })
  },
}

export default auditLogsApi
