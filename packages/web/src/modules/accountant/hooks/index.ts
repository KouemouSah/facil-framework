/**
 * Accountant Hooks
 * React Query hooks for accountant multi-client dashboard
 *
 * @module accountant/hooks
 * @author Claude Code
 * @date 2025-12-03
 */

'use client'

import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  accountantClientsApi,
  accountantDeadlinesApi,
  accountantTasksApi,
  accountantDashboardApi,
} from '../services/api'
import type {
  ClientFilters,
  GetDeadlinesParams,
  GetTasksParams,
} from '../types'
// import { toast } from 'sonner'  // Reserved for future mutations

// =============================================================================
// QUERY KEYS
// =============================================================================

export const accountantKeys = {
  all: ['accountant'] as const,

  // Clients
  clients: () => [...accountantKeys.all, 'clients'] as const,
  clientsList: (filters?: ClientFilters) =>
    [...accountantKeys.clients(), 'list', filters] as const,
  clientStats: (companyId: string) =>
    [...accountantKeys.clients(), 'stats', companyId] as const,
  managedCompanies: () => [...accountantKeys.clients(), 'managed'] as const,

  // Deadlines
  deadlines: () => [...accountantKeys.all, 'deadlines'] as const,
  deadlinesList: (params?: GetDeadlinesParams) =>
    [...accountantKeys.deadlines(), 'list', params] as const,
  deadlinesOverdue: () => [...accountantKeys.deadlines(), 'overdue'] as const,
  deadlinesByCompany: (companyId: string, params?: GetDeadlinesParams) =>
    [...accountantKeys.deadlines(), 'by-company', companyId, params] as const,

  // Tasks
  tasks: () => [...accountantKeys.all, 'tasks'] as const,
  tasksList: (params?: GetTasksParams) =>
    [...accountantKeys.tasks(), 'list', params] as const,
  tasksHighPriority: () => [...accountantKeys.tasks(), 'high-priority'] as const,
  tasksRequiresAction: () => [...accountantKeys.tasks(), 'requires-action'] as const,

  // Dashboard
  dashboard: () => [...accountantKeys.all, 'dashboard'] as const,
  dashboardSummary: () => [...accountantKeys.dashboard(), 'summary'] as const,
}

// =============================================================================
// CLIENT HOOKS
// =============================================================================

/**
 * Fetch all clients managed by accountant with stats
 * Use for main client list view
 */
export function useAccountantClients(filters?: ClientFilters) {
  return useQuery({
    queryKey: accountantKeys.clientsList(filters),
    queryFn: () => accountantClientsApi.getAll(filters),
    staleTime: 1000 * 60 * 2, // 2 minutes
  })
}

/**
 * Fetch quick stats for a specific client
 * Use for client detail views
 */
export function useClientStats(companyId: string) {
  return useQuery({
    queryKey: accountantKeys.clientStats(companyId),
    queryFn: () => accountantClientsApi.getClientStats(companyId),
    enabled: !!companyId,
    staleTime: 1000 * 60 * 5, // 5 minutes
  })
}

/**
 * Fetch all companies where user is accountant
 * Use for client switcher dropdown
 */
export function useManagedCompanies() {
  return useQuery({
    queryKey: accountantKeys.managedCompanies(),
    queryFn: () => accountantClientsApi.getManagedCompanies(),
    staleTime: 1000 * 60 * 10, // 10 minutes
  })
}

// =============================================================================
// DEADLINE HOOKS
// =============================================================================

/**
 * Fetch upcoming deadlines across all clients
 * Use for deadline calendar view
 */
export function useUpcomingDeadlines(params?: GetDeadlinesParams) {
  return useQuery({
    queryKey: accountantKeys.deadlinesList(params),
    queryFn: () => accountantDeadlinesApi.getUpcoming(params),
    staleTime: 1000 * 60 * 5, // 5 minutes
  })
}

/**
 * Fetch overdue deadlines
 * Use for alerts/notifications
 */
export function useOverdueDeadlines() {
  return useQuery({
    queryKey: accountantKeys.deadlinesOverdue(),
    queryFn: () => accountantDeadlinesApi.getOverdue(),
    staleTime: 1000 * 60 * 2, // 2 minutes
    refetchInterval: 1000 * 60 * 5, // Refetch every 5 minutes
  })
}

/**
 * Fetch deadlines for a specific company
 * Use when viewing single client
 */
export function useClientDeadlines(
  companyId: string,
  params?: GetDeadlinesParams
) {
  return useQuery({
    queryKey: accountantKeys.deadlinesByCompany(companyId, params),
    queryFn: () => accountantDeadlinesApi.getByCompany(companyId, params),
    enabled: !!companyId,
    staleTime: 1000 * 60 * 5, // 5 minutes
  })
}

// =============================================================================
// TASK HOOKS
// =============================================================================

/**
 * Fetch pending tasks/declarations requiring action
 * Use for task queue view
 */
export function usePendingTasks(params?: GetTasksParams) {
  return useQuery({
    queryKey: accountantKeys.tasksList(params),
    queryFn: () => accountantTasksApi.getAll(params),
    staleTime: 1000 * 60 * 2, // 2 minutes
  })
}

/**
 * Fetch high priority tasks only
 * Use for priority task list
 */
export function useHighPriorityTasks() {
  return useQuery({
    queryKey: accountantKeys.tasksHighPriority(),
    queryFn: () => accountantTasksApi.getHighPriority(),
    staleTime: 1000 * 60 * 2, // 2 minutes
    refetchInterval: 1000 * 60 * 5, // Refetch every 5 minutes
  })
}

/**
 * Fetch tasks requiring immediate action
 * Use for action required badge/alert
 */
export function useTasksRequiringAction() {
  return useQuery({
    queryKey: accountantKeys.tasksRequiresAction(),
    queryFn: () => accountantTasksApi.getRequiresAction(),
    staleTime: 1000 * 60 * 2, // 2 minutes
    refetchInterval: 1000 * 60 * 5, // Refetch every 5 minutes
  })
}

// =============================================================================
// DASHBOARD HOOKS
// =============================================================================

/**
 * Fetch dashboard summary with all aggregated stats
 * Use for dashboard overview
 */
export function useDashboardSummary() {
  return useQuery({
    queryKey: accountantKeys.dashboardSummary(),
    queryFn: () => accountantDashboardApi.getSummary(),
    staleTime: 1000 * 60 * 5, // 5 minutes
    refetchInterval: 1000 * 60 * 10, // Refetch every 10 minutes
  })
}

// =============================================================================
// UTILITY HOOKS
// =============================================================================

/**
 * Invalidate all accountant queries
 * Use after major data changes (e.g., declaration submission)
 */
export function useInvalidateAccountantQueries() {
  const queryClient = useQueryClient()

  return () => {
    queryClient.invalidateQueries({ queryKey: accountantKeys.all })
  }
}

/**
 * Prefetch client data
 * Use for optimistic navigation
 */
export function usePrefetchClient() {
  const queryClient = useQueryClient()

  return (companyId: string) => {
    queryClient.prefetchQuery({
      queryKey: accountantKeys.clientStats(companyId),
      queryFn: () => accountantClientsApi.getClientStats(companyId),
      staleTime: 1000 * 60 * 5,
    })

    queryClient.prefetchQuery({
      queryKey: accountantKeys.deadlinesByCompany(companyId),
      queryFn: () => accountantDeadlinesApi.getByCompany(companyId),
      staleTime: 1000 * 60 * 5,
    })
  }
}
