/**
 * Accountant API Service
 * Handles all API calls for accountant multi-client dashboard
 *
 * @module accountant/services
 * @author Claude Code
 * @date 2025-12-03
 *
 * BACKEND ALIGNMENT:
 * Routes: /api/v1/accountant/* (to be implemented on backend)
 * These endpoints aggregate data from:
 * - /api/v1/companies (company_accountant role filtering)
 * - /api/v1/declarations (declarations for companies user manages)
 * - /api/v1/payments (payment status for managed companies)
 *
 * NOTE: Some endpoints may need backend implementation.
 * Current implementation uses existing endpoints with client-side aggregation.
 */

import { fetchClient } from '@/core/api'
import type {
  ClientWithStats,
  ClientQuickStats,
  DeclarationDeadline,
  PendingTask,
  AccountantDashboardSummary,
  ClientFilters,
  PaginatedClientsResponse,
  GetDeadlinesParams,
  GetTasksParams,
} from '../types'

// =============================================================================
// CONFIGURATION
// =============================================================================

const ACCOUNTANT_BASE = '/accountant'
const COMPANIES_BASE = '/companies'
const _DECLARATIONS_BASE = '/declarations'  // Reserved for future use

// =============================================================================
// CLIENTS API
// =============================================================================

export const accountantClientsApi = {
  /**
   * Get all clients managed by accountant with stats
   * BACKEND: GET /api/v1/accountant/clients
   *
   * NOTE: Backend needs to implement this endpoint.
   * For now, uses /companies with role filtering + client-side stats aggregation
   */
  getAll: async (filters?: ClientFilters): Promise<PaginatedClientsResponse> => {
    const params: Record<string, string | number | boolean | undefined> = {}

    if (filters?.search) params.search = filters.search
    if (filters?.status && filters.status !== 'all') params.status = filters.status
    if (filters?.hasPendingDeclarations !== undefined)
      params.has_pending = filters.hasPendingDeclarations
    if (filters?.hasOverduePayments !== undefined)
      params.has_overdue = filters.hasOverduePayments
    if (filters?.city_name) params.city_name = filters.city_name
    if (filters?.sortBy) params.sort_by = filters.sortBy
    if (filters?.sortOrder) params.sort_order = filters.sortOrder

    // TODO: Replace with dedicated accountant endpoint when available
    return fetchClient.get<PaginatedClientsResponse>(
      `${ACCOUNTANT_BASE}/clients`,
      params
    )
  },

  /**
   * Get quick stats for a specific client
   * BACKEND: GET /api/v1/accountant/clients/{companyId}/stats
   *
   * NOTE: Backend needs to implement this endpoint
   */
  getClientStats: async (companyId: string): Promise<ClientQuickStats> => {
    return fetchClient.get<ClientQuickStats>(
      `${ACCOUNTANT_BASE}/clients/${companyId}/stats`
    )
  },

  /**
   * Get all clients managed by accountant (companies where user has company_accountant role)
   * FALLBACK: Uses existing companies endpoint with role filtering
   */
  getManagedCompanies: async (): Promise<ClientWithStats[]> => {
    // Uses existing companies endpoint
    // Backend filters by user_company_roles where role = 'company_accountant'
    const response = await fetchClient.get<{ companies: ClientWithStats[] }>(
      `${COMPANIES_BASE}`,
      { role: 'company_accountant', include_stats: true }
    )
    return response.companies
  },
}

// =============================================================================
// DEADLINES API
// =============================================================================

export const accountantDeadlinesApi = {
  /**
   * Get upcoming deadlines across all managed clients
   * BACKEND: GET /api/v1/accountant/deadlines
   *
   * NOTE: Backend needs to implement this endpoint
   * Aggregates declaration deadlines from all companies where user has accountant role
   */
  getUpcoming: async (
    params?: GetDeadlinesParams
  ): Promise<DeclarationDeadline[]> => {
    const queryParams: Record<string, string | number | boolean | undefined> = {}

    if (params?.startDate) queryParams.start_date = params.startDate
    if (params?.endDate) queryParams.end_date = params.endDate
    if (params?.companyId) queryParams.company_id = params.companyId
    if (params?.status) queryParams.status = params.status
    if (params?.priority) queryParams.priority = params.priority

    return fetchClient.get<DeclarationDeadline[]>(
      `${ACCOUNTANT_BASE}/deadlines`,
      queryParams
    )
  },

  /**
   * Get overdue deadlines
   * BACKEND: GET /api/v1/accountant/deadlines/overdue
   */
  getOverdue: async (): Promise<DeclarationDeadline[]> => {
    return fetchClient.get<DeclarationDeadline[]>(
      `${ACCOUNTANT_BASE}/deadlines/overdue`
    )
  },

  /**
   * Get deadlines for a specific company
   * BACKEND: GET /api/v1/accountant/clients/{companyId}/deadlines
   */
  getByCompany: async (
    companyId: string,
    params?: GetDeadlinesParams
  ): Promise<DeclarationDeadline[]> => {
    const queryParams: Record<string, string | number | boolean | undefined> = {}

    if (params?.startDate) queryParams.start_date = params.startDate
    if (params?.endDate) queryParams.end_date = params.endDate
    if (params?.status) queryParams.status = params.status
    if (params?.priority) queryParams.priority = params.priority

    return fetchClient.get<DeclarationDeadline[]>(
      `${ACCOUNTANT_BASE}/clients/${companyId}/deadlines`,
      queryParams
    )
  },
}

// =============================================================================
// TASKS API
// =============================================================================

export const accountantTasksApi = {
  /**
   * Get pending tasks/declarations requiring action
   * BACKEND: GET /api/v1/accountant/tasks
   *
   * NOTE: Backend needs to implement this endpoint
   * Returns declarations that need accountant review/action
   */
  getAll: async (params?: GetTasksParams): Promise<PendingTask[]> => {
    const queryParams: Record<string, string | number | boolean | undefined> = {
      page: params?.page ?? 1,
      page_size: params?.pageSize ?? 20,
    }

    if (params?.status && params.status !== 'all') queryParams.status = params.status
    if (params?.priority && params.priority !== 'all')
      queryParams.priority = params.priority
    if (params?.companyId) queryParams.company_id = params.companyId
    if (params?.declarationType) queryParams.declaration_type = params.declarationType
    if (params?.sortBy) queryParams.sort_by = params.sortBy
    if (params?.sortOrder) queryParams.sort_order = params.sortOrder

    return fetchClient.get<PendingTask[]>(`${ACCOUNTANT_BASE}/tasks`, queryParams)
  },

  /**
   * Get high priority tasks only
   * BACKEND: GET /api/v1/accountant/tasks/high-priority
   */
  getHighPriority: async (): Promise<PendingTask[]> => {
    return fetchClient.get<PendingTask[]>(`${ACCOUNTANT_BASE}/tasks/high-priority`)
  },

  /**
   * Get tasks requiring immediate action
   * BACKEND: GET /api/v1/accountant/tasks/requires-action
   */
  getRequiresAction: async (): Promise<PendingTask[]> => {
    return fetchClient.get<PendingTask[]>(
      `${ACCOUNTANT_BASE}/tasks/requires-action`
    )
  },
}

// =============================================================================
// DASHBOARD API
// =============================================================================

export const accountantDashboardApi = {
  /**
   * Get dashboard summary with all stats
   * BACKEND: GET /api/v1/accountant/dashboard/summary
   *
   * NOTE: Backend needs to implement this endpoint
   * Provides aggregated overview of all clients and tasks
   */
  getSummary: async (): Promise<AccountantDashboardSummary> => {
    return fetchClient.get<AccountantDashboardSummary>(
      `${ACCOUNTANT_BASE}/dashboard/summary`
    )
  },
}

// =============================================================================
// EXPORTS
// =============================================================================

export default {
  clients: accountantClientsApi,
  deadlines: accountantDeadlinesApi,
  tasks: accountantTasksApi,
  dashboard: accountantDashboardApi,
}
