'use client'

import { useQuery } from '@tanstack/react-query'
import { auditLogsApi, geminiStatsApi } from '../services/api'
import type { PaginatedAuditLogsResponse, AuditLogStats, GeminiUsageStats } from '../types'

export const auditLogsKeys = {
  all: ['audit-logs'] as const,
  lists: () => [...auditLogsKeys.all, 'list'] as const,
  list: (filters: Record<string, string | number | boolean | undefined>) =>
    [...auditLogsKeys.lists(), filters] as const,
  details: () => [...auditLogsKeys.all, 'detail'] as const,
  detail: (id: string) => [...auditLogsKeys.details(), id] as const,
  user: (userId: string) => [...auditLogsKeys.all, 'user', userId] as const,
  stats: () => [...auditLogsKeys.all, 'stats'] as const,
  gemini: (days: number) => [...auditLogsKeys.all, 'gemini', days] as const,
}

export function useAuditLogs(params?: {
  action?: string
  user_id?: string
  entity_type?: string
  search?: string
  start_date?: string
  end_date?: string
  page?: number
  page_size?: number
}) {
  return useQuery<PaginatedAuditLogsResponse>({
    queryKey: auditLogsKeys.list(params || {}),
    queryFn: () => auditLogsApi.getAll(params),
  })
}

export function useAuditLog(id: string) {
  return useQuery({
    queryKey: auditLogsKeys.detail(id),
    queryFn: () => auditLogsApi.getById(id),
    enabled: !!id,
  })
}

export function useUserAuditLogs(
  userId: string,
  params?: {
    action?: string
    page?: number
    page_size?: number
  }
) {
  return useQuery({
    queryKey: [...auditLogsKeys.user(userId), params],
    queryFn: () => auditLogsApi.getByUser(userId, params),
    enabled: !!userId,
  })
}

export function useAuditLogStats(params?: {
  start_date?: string
  end_date?: string
}) {
  return useQuery<AuditLogStats>({
    queryKey: [...auditLogsKeys.stats(), params],
    queryFn: () => auditLogsApi.getStats(params),
    staleTime: 30_000,
  })
}

export function useGeminiStats(days: number = 30) {
  return useQuery<GeminiUsageStats>({
    queryKey: auditLogsKeys.gemini(days),
    queryFn: () => geminiStatsApi.getStats(days),
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  })
}
