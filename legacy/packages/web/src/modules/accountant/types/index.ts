/**
 * Accountant Module Types
 * Type definitions for accountant multi-client dashboard
 *
 * @module accountant/types
 * @author Claude Code
 * @date 2025-12-03
 *
 * ALIGNED WITH BACKEND:
 * - packages/backend/app/modules/companies/models/company.py
 * - packages/backend/app/modules/declarations/models/declaration.py
 */

import type { Company } from '@/modules/companies/types'

// =============================================================================
// CLIENT TYPES
// =============================================================================

/**
 * Client quick stats for accountant dashboard
 * Aggregated data from various tables
 */
export interface ClientQuickStats {
  companyId: string
  companyName: string
  taxId: string
  city_name?: string | null

  // Declaration stats
  pendingDeclarations: number
  draftDeclarations: number
  inReviewDeclarations: number
  approvedThisMonth: number

  // Financial stats
  totalAmountDue: number
  overdueAmount: number

  // Deadline info
  nextDeadline?: {
    declarationId: string
    declarationType: string
    dueDate: string
    daysUntilDue: number
  } | null

  // Activity
  lastActivityDate: string
  status: 'active' | 'inactive' | 'suspended'
}

/**
 * Client with stats for list view
 */
export interface ClientWithStats extends Company {
  stats: ClientQuickStats
}

// =============================================================================
// DEADLINE TYPES
// =============================================================================

/**
 * Declaration deadline across all clients
 */
export interface DeclarationDeadline {
  id: string
  companyId: string
  companyName: string
  declarationType: string
  dueDate: string
  status: 'draft' | 'pending' | 'in_review' | 'approved' | 'rejected'
  amount?: number | null
  priority: 'low' | 'medium' | 'high' | 'urgent'
  daysUntilDue: number
  assignedAgentName?: string | null
}

/**
 * Calendar view for deadlines
 */
export interface DeadlineCalendarEvent {
  id: string
  title: string
  date: string
  companyName: string
  declarationType: string
  amount?: number | null
  priority: 'low' | 'medium' | 'high' | 'urgent'
  status: string
}

// =============================================================================
// TASK QUEUE TYPES
// =============================================================================

/**
 * Task/declaration pending review
 */
export interface PendingTask {
  id: string
  companyId: string
  companyName: string
  declarationType: string
  status: 'draft' | 'pending' | 'in_review'
  createdAt: string
  updatedAt: string
  dueDate?: string | null
  amount?: number | null
  priority: 'low' | 'medium' | 'high' | 'urgent'
  requiresAction: boolean
  actionType?: 'review' | 'approve' | 'fix_errors' | 'add_documents' | null
  daysUntilDue?: number | null
}

/**
 * Task queue filters
 */
export interface TaskQueueFilters {
  status?: 'draft' | 'pending' | 'in_review' | 'all'
  priority?: 'low' | 'medium' | 'high' | 'urgent' | 'all'
  companyId?: string
  declarationType?: string
  sortBy?: 'dueDate' | 'priority' | 'createdAt' | 'amount'
  sortOrder?: 'asc' | 'desc'
}

// =============================================================================
// DASHBOARD SUMMARY TYPES
// =============================================================================

/**
 * Accountant dashboard summary
 * Overview of all clients and tasks
 */
export interface AccountantDashboardSummary {
  // Client totals
  totalClients: number
  activeClients: number
  inactiveClients: number

  // Declaration totals
  totalPendingDeclarations: number
  totalDraftDeclarations: number
  totalInReviewDeclarations: number
  totalApprovedThisMonth: number

  // Financial totals
  totalAmountDue: number
  totalOverdueAmount: number

  // Deadline summary
  upcomingDeadlines: number
  overdueDeadlines: number
  dueTodayCount: number
  dueThisWeekCount: number

  // Task summary
  requiresActionCount: number
  highPriorityCount: number
  urgentCount: number
}

// =============================================================================
// SEARCH & FILTER TYPES
// =============================================================================

/**
 * Client search and filter options
 */
export interface ClientFilters {
  search?: string
  status?: 'active' | 'inactive' | 'suspended' | 'all'
  hasPendingDeclarations?: boolean
  hasOverduePayments?: boolean
  city_name?: string
  sortBy?: 'name' | 'lastActivity' | 'pendingCount' | 'totalDue'
  sortOrder?: 'asc' | 'desc'
}

/**
 * Paginated client list response
 */
export interface PaginatedClientsResponse {
  clients: ClientWithStats[]
  total: number
  page: number
  pageSize: number
}

// =============================================================================
// API PARAMS TYPES
// =============================================================================

/**
 * Get deadlines query params
 */
export interface GetDeadlinesParams {
  startDate?: string
  endDate?: string
  companyId?: string
  status?: string
  priority?: string
}

/**
 * Get tasks query params
 */
export interface GetTasksParams extends TaskQueueFilters {
  page?: number
  pageSize?: number
}
