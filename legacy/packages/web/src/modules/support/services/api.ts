/**
 * Support API Service
 * Handles all API calls for support ticketing system
 *
 * @module support/services
 * @author Claude Code
 * @date 2025-12-17
 *
 * BACKEND ALIGNMENT: Phase Support
 * Base URL: /api/v1/support
 * Backend: packages/backend/app/modules/support/api/support_routes.py
 *
 * Features:
 * - Category management (CRUD)
 * - Ticket management (CRUD + lifecycle)
 * - Message threads
 * - Statistics for admin
 */

import type {
  SupportCategory,
  SupportCategoryCreate,
  SupportCategoryUpdate,
  SupportTicket,
  SupportTicketCreate,
  SupportTicketUpdate,
  SupportTicketListResponse,
  SupportMessage,
  SupportMessageCreate,
  SupportStats,
  SupportFilters,
} from '../types'
import { getAuthData } from '@/core/auth/storage'

// =============================================================================
// CONFIGURATION
// =============================================================================

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const API_VERSION = '/api/v1'
const SUPPORT_BASE = '/support'

// =============================================================================
// HTTP CLIENT
// =============================================================================

class SupportApiClient {
  private baseUrl: string

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl
  }

  private getToken(): string | null {
    if (typeof window === 'undefined') return null
    const authData = getAuthData()
    return authData?.access_token || null
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`
    const token = this.getToken()

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    }

    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }

    if (options.headers) {
      const headersToMerge =
        options.headers instanceof Headers
          ? Object.fromEntries(options.headers.entries())
          : Array.isArray(options.headers)
          ? Object.fromEntries(options.headers)
          : options.headers
      Object.assign(headers, headersToMerge)
    }

    try {
      const response = await fetch(url, {
        ...options,
        headers,
      })

      if (!response.ok) {
        const error = await response.json().catch(() => ({
          message: `HTTP error! status: ${response.status}`,
        }))
        throw new Error(
          error.message || error.detail || `HTTP error! status: ${response.status}`
        )
      }

      // Handle 204 No Content
      if (response.status === 204) {
        return null as T
      }

      return response.json()
    } catch (error) {
      if (error instanceof Error) {
        throw error
      }
      throw new Error('Unknown error occurred')
    }
  }

  async get<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: 'GET' })
  }

  async post<T>(endpoint: string, data?: unknown): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
    })
  }

  async put<T>(endpoint: string, data?: unknown): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'PUT',
      body: data ? JSON.stringify(data) : undefined,
    })
  }

  async delete<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: 'DELETE' })
  }
}

const client = new SupportApiClient(`${API_BASE_URL}${API_VERSION}${SUPPORT_BASE}`)

// =============================================================================
// SNAKE_CASE TO CAMELCASE CONVERTERS
// =============================================================================

function categoryToCamelCase(data: Record<string, unknown>): SupportCategory {
  return {
    id: data.id as number,
    code: data.code as string,
    nameEs: data.name_es as string,
    nameFr: data.name_fr as string | null,
    nameEn: data.name_en as string | null,
    descriptionEs: data.description_es as string | null,
    descriptionFr: data.description_fr as string | null,
    descriptionEn: data.description_en as string | null,
    targetRole: data.target_role as string,
    icon: data.icon as string | null,
    isActive: data.is_active as boolean,
    sortOrder: data.sort_order as number,
    createdAt: data.created_at as string,
  }
}

function categoryToSnakeCase(
  data: SupportCategoryCreate | SupportCategoryUpdate
): Record<string, unknown> {
  const result: Record<string, unknown> = {}
  if ('code' in data && data.code !== undefined) result.code = data.code
  if ('nameEs' in data && data.nameEs !== undefined) result.name_es = data.nameEs
  if ('nameFr' in data && data.nameFr !== undefined) result.name_fr = data.nameFr
  if ('nameEn' in data && data.nameEn !== undefined) result.name_en = data.nameEn
  if ('descriptionEs' in data && data.descriptionEs !== undefined)
    result.description_es = data.descriptionEs
  if ('descriptionFr' in data && data.descriptionFr !== undefined)
    result.description_fr = data.descriptionFr
  if ('descriptionEn' in data && data.descriptionEn !== undefined)
    result.description_en = data.descriptionEn
  if ('targetRole' in data && data.targetRole !== undefined)
    result.target_role = data.targetRole
  if ('icon' in data && data.icon !== undefined) result.icon = data.icon
  if ('isActive' in data && data.isActive !== undefined)
    result.is_active = data.isActive
  if ('sortOrder' in data && data.sortOrder !== undefined)
    result.sort_order = data.sortOrder
  return result
}

function ticketToCamelCase(data: Record<string, unknown>): SupportTicket {
  return {
    id: data.id as number,
    ticketNumber: data.ticket_number as string,
    categoryId: data.category_id as number | null,
    subject: data.subject as string,
    description: data.description as string,
    priority: data.priority as string,
    status: data.status as string,
    createdBy: data.created_by as string,
    assignedTo: data.assigned_to as string | null,
    resolvedAt: data.resolved_at as string | null,
    closedAt: data.closed_at as string | null,
    createdAt: data.created_at as string,
    updatedAt: data.updated_at as string,
    categoryCode: data.category_code as string | undefined,
    categoryName: data.category_name as string | undefined,
    createdByName: data.created_by_name as string | undefined,
    createdByEmail: data.created_by_email as string | undefined,
    assignedToName: data.assigned_to_name as string | undefined,
    assignedToEmail: data.assigned_to_email as string | undefined,
    messageCount: data.message_count as number | undefined,
  }
}

function ticketToSnakeCase(
  data: SupportTicketCreate | SupportTicketUpdate
): Record<string, unknown> {
  const result: Record<string, unknown> = {}
  if ('categoryId' in data && data.categoryId !== undefined)
    result.category_id = data.categoryId
  if ('subject' in data && data.subject !== undefined) result.subject = data.subject
  if ('description' in data && data.description !== undefined)
    result.description = data.description
  if ('priority' in data && data.priority !== undefined)
    result.priority = data.priority
  if ('status' in data && data.status !== undefined) result.status = data.status
  if ('assignedTo' in data && data.assignedTo !== undefined)
    result.assigned_to = data.assignedTo
  return result
}

function messageToCamelCase(data: Record<string, unknown>): SupportMessage {
  return {
    id: data.id as number,
    ticketId: data.ticket_id as number,
    senderId: data.sender_id as string,
    content: data.content as string,
    isInternal: data.is_internal as boolean,
    createdAt: data.created_at as string,
    senderName: data.sender_name as string | undefined,
    senderEmail: data.sender_email as string | undefined,
    senderRole: data.sender_role as string | undefined,
  }
}

function statsToCamelCase(data: Record<string, unknown>): SupportStats {
  return {
    totalTickets: data.total_tickets as number,
    openTickets: data.open_tickets as number,
    inProgressTickets: data.in_progress_tickets as number,
    resolvedTickets: data.resolved_tickets as number,
    closedTickets: data.closed_tickets as number,
    averageResolutionTimeHours: data.average_resolution_time_hours as number | null,
    statusBreakdown: (data.status_breakdown as Array<Record<string, unknown>>)?.map(
      (item) => ({
        status: item.status as string,
        count: item.count as number,
      })
    ) || [],
    priorityBreakdown: (data.priority_breakdown as Array<Record<string, unknown>>)?.map(
      (item) => ({
        priority: item.priority as string,
        count: item.count as number,
      })
    ) || [],
    categoryBreakdown: (data.category_breakdown as Array<Record<string, unknown>>)?.map(
      (item) => ({
        categoryId: item.category_id as number,
        categoryCode: item.category_code as string,
        count: item.count as number,
      })
    ) || [],
  }
}

// =============================================================================
// SUPPORT API
// =============================================================================

export const supportApi = {
  // ===========================================================================
  // CATEGORIES
  // ===========================================================================

  /**
   * GET /api/v1/support/categories
   * List support categories
   */
  listCategories: async (
    isActive?: boolean,
    targetRole?: string
  ): Promise<SupportCategory[]> => {
    const params = new URLSearchParams()
    if (isActive !== undefined) params.append('is_active', String(isActive))
    if (targetRole) params.append('target_role', targetRole)
    const queryString = params.toString()
    const endpoint = queryString ? `/categories?${queryString}` : '/categories'
    const response = await client.get<Array<Record<string, unknown>>>(endpoint)
    return response.map(categoryToCamelCase)
  },

  /**
   * GET /api/v1/support/categories/{id}
   * Get a category by ID
   */
  getCategory: async (categoryId: number): Promise<SupportCategory> => {
    const response = await client.get<Record<string, unknown>>(
      `/categories/${categoryId}`
    )
    return categoryToCamelCase(response)
  },

  /**
   * POST /api/v1/support/categories
   * Create a new category (admin only)
   */
  createCategory: async (
    data: SupportCategoryCreate
  ): Promise<SupportCategory> => {
    const response = await client.post<Record<string, unknown>>(
      '/categories',
      categoryToSnakeCase(data)
    )
    return categoryToCamelCase(response)
  },

  /**
   * PUT /api/v1/support/categories/{id}
   * Update a category (admin only)
   */
  updateCategory: async (
    categoryId: number,
    data: SupportCategoryUpdate
  ): Promise<SupportCategory> => {
    const response = await client.put<Record<string, unknown>>(
      `/categories/${categoryId}`,
      categoryToSnakeCase(data)
    )
    return categoryToCamelCase(response)
  },

  /**
   * DELETE /api/v1/support/categories/{id}
   * Delete a category (admin only)
   */
  deleteCategory: async (categoryId: number): Promise<void> => {
    await client.delete(`/categories/${categoryId}`)
  },

  // ===========================================================================
  // TICKETS
  // ===========================================================================

  /**
   * GET /api/v1/support/tickets
   * List all tickets (admin only)
   */
  listAllTickets: async (
    page: number = 1,
    pageSize: number = 20,
    filters?: SupportFilters
  ): Promise<SupportTicketListResponse> => {
    const params = new URLSearchParams()
    params.append('page', String(page))
    params.append('page_size', String(pageSize))
    if (filters?.status) params.append('status', filters.status)
    if (filters?.priority) params.append('priority', filters.priority)
    if (filters?.categoryId) params.append('category_id', String(filters.categoryId))
    if (filters?.assignedTo) params.append('assigned_to', String(filters.assignedTo))
    if (filters?.search) params.append('search', filters.search)

    const response = await client.get<Record<string, unknown>>(
      `/tickets?${params.toString()}`
    )
    return {
      tickets: (response.tickets as Array<Record<string, unknown>>).map(
        ticketToCamelCase
      ),
      total: response.total as number,
      page: response.page as number,
      pageSize: response.page_size as number,
      totalPages: response.total_pages as number,
    }
  },

  /**
   * GET /api/v1/support/tickets/my
   * List current user's tickets
   */
  listMyTickets: async (
    page: number = 1,
    pageSize: number = 20,
    status?: string
  ): Promise<SupportTicketListResponse> => {
    const params = new URLSearchParams()
    params.append('page', String(page))
    params.append('page_size', String(pageSize))
    if (status) params.append('status', status)

    const response = await client.get<Record<string, unknown>>(
      `/tickets/my?${params.toString()}`
    )
    return {
      tickets: (response.tickets as Array<Record<string, unknown>>).map(
        ticketToCamelCase
      ),
      total: response.total as number,
      page: response.page as number,
      pageSize: response.page_size as number,
      totalPages: response.total_pages as number,
    }
  },

  /**
   * GET /api/v1/support/tickets/{id}
   * Get a ticket by ID
   */
  getTicket: async (ticketId: number): Promise<SupportTicket> => {
    const response = await client.get<Record<string, unknown>>(
      `/tickets/${ticketId}`
    )
    return ticketToCamelCase(response)
  },

  /**
   * GET /api/v1/support/tickets/by-number/{ticket_number}
   * Get a ticket by ticket number
   */
  getTicketByNumber: async (ticketNumber: string): Promise<SupportTicket> => {
    const response = await client.get<Record<string, unknown>>(
      `/tickets/by-number/${ticketNumber}`
    )
    return ticketToCamelCase(response)
  },

  /**
   * POST /api/v1/support/tickets
   * Create a new ticket
   */
  createTicket: async (data: SupportTicketCreate): Promise<SupportTicket> => {
    const response = await client.post<Record<string, unknown>>(
      '/tickets',
      ticketToSnakeCase(data)
    )
    return ticketToCamelCase(response)
  },

  /**
   * PUT /api/v1/support/tickets/{id}
   * Update a ticket
   */
  updateTicket: async (
    ticketId: number,
    data: SupportTicketUpdate
  ): Promise<SupportTicket> => {
    const response = await client.put<Record<string, unknown>>(
      `/tickets/${ticketId}`,
      ticketToSnakeCase(data)
    )
    return ticketToCamelCase(response)
  },

  /**
   * POST /api/v1/support/tickets/{id}/close
   * Close a ticket
   */
  closeTicket: async (ticketId: number): Promise<SupportTicket> => {
    const response = await client.post<Record<string, unknown>>(
      `/tickets/${ticketId}/close`
    )
    return ticketToCamelCase(response)
  },

  // ===========================================================================
  // MESSAGES
  // ===========================================================================

  /**
   * GET /api/v1/support/tickets/{id}/messages
   * List messages for a ticket
   */
  listMessages: async (ticketId: number): Promise<SupportMessage[]> => {
    const response = await client.get<Array<Record<string, unknown>>>(
      `/tickets/${ticketId}/messages`
    )
    return response.map(messageToCamelCase)
  },

  /**
   * POST /api/v1/support/tickets/{id}/messages
   * Add a message to a ticket
   */
  addMessage: async (
    ticketId: number,
    data: SupportMessageCreate
  ): Promise<SupportMessage> => {
    const response = await client.post<Record<string, unknown>>(
      `/tickets/${ticketId}/messages`,
      {
        content: data.content,
        is_internal: data.isInternal || false,
      }
    )
    return messageToCamelCase(response)
  },

  // ===========================================================================
  // STATISTICS
  // ===========================================================================

  /**
   * GET /api/v1/support/stats
   * Get support statistics (admin only)
   */
  getStats: async (): Promise<SupportStats> => {
    const response = await client.get<Record<string, unknown>>('/stats')
    return statsToCamelCase(response)
  },
}

// =============================================================================
// EXPORTS
// =============================================================================

export default supportApi
