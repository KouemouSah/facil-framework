/**
 * useSupport Hook
 * State management for support ticketing system
 *
 * @module support/hooks
 * @author Claude Code
 * @date 2025-12-17
 *
 * Features:
 * - Category management
 * - Ticket CRUD operations
 * - Message management
 * - Pagination and filtering
 * - Loading and error states
 */

'use client'

import { useState, useCallback, useEffect } from 'react'
import { supportApi } from '../services/api'
import type {
  SupportCategory,
  SupportCategoryCreate,
  SupportCategoryUpdate,
  SupportTicket,
  SupportTicketCreate,
  SupportTicketUpdate,
  SupportMessage,
  SupportMessageCreate,
  SupportStats,
  SupportFilters,
} from '../types'

// =============================================================================
// TYPES
// =============================================================================

export interface UseSupportOptions {
  autoLoadCategories?: boolean
  onError?: (error: Error) => void
}

export interface UseSupportReturn {
  // State
  categories: SupportCategory[]
  tickets: SupportTicket[]
  currentTicket: SupportTicket | null
  messages: SupportMessage[]
  stats: SupportStats | null
  isLoading: boolean
  error: string | null
  pagination: {
    page: number
    pageSize: number
    total: number
    totalPages: number
  }

  // Category actions
  loadCategories: (isActive?: boolean, targetRole?: string) => Promise<void>
  createCategory: (data: SupportCategoryCreate) => Promise<SupportCategory | null>
  updateCategory: (
    categoryId: number,
    data: SupportCategoryUpdate
  ) => Promise<SupportCategory | null>
  deleteCategory: (categoryId: number) => Promise<boolean>

  // Ticket actions - User
  loadMyTickets: (page?: number, pageSize?: number, status?: string) => Promise<void>
  createTicket: (data: SupportTicketCreate) => Promise<SupportTicket | null>
  closeTicket: (ticketId: number) => Promise<void>

  // Ticket actions - Admin
  loadAllTickets: (
    page?: number,
    pageSize?: number,
    filters?: SupportFilters
  ) => Promise<void>
  updateTicket: (
    ticketId: number,
    data: SupportTicketUpdate
  ) => Promise<SupportTicket | null>

  // Ticket detail
  loadTicket: (ticketId: number) => Promise<void>
  loadTicketByNumber: (ticketNumber: string) => Promise<void>

  // Message actions
  loadMessages: (ticketId: number) => Promise<void>
  addMessage: (
    ticketId: number,
    data: SupportMessageCreate
  ) => Promise<SupportMessage | null>

  // Stats actions
  loadStats: () => Promise<void>

  // Utility
  clearError: () => void
  setPage: (page: number) => void
}

// =============================================================================
// HOOK
// =============================================================================

export function useSupport(options: UseSupportOptions = {}): UseSupportReturn {
  const { autoLoadCategories = true, onError } = options

  // State
  const [categories, setCategories] = useState<SupportCategory[]>([])
  const [tickets, setTickets] = useState<SupportTicket[]>([])
  const [currentTicket, setCurrentTicket] = useState<SupportTicket | null>(null)
  const [messages, setMessages] = useState<SupportMessage[]>([])
  const [stats, setStats] = useState<SupportStats | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [pagination, setPagination] = useState({
    page: 1,
    pageSize: 20,
    total: 0,
    totalPages: 0,
  })

  // =============================================================================
  // ERROR HANDLING
  // =============================================================================

  const handleError = useCallback(
    (err: unknown, context: string) => {
      const errorMessage =
        err instanceof Error ? err.message : `Error in ${context}`
      setError(errorMessage)
      if (onError) {
        onError(err instanceof Error ? err : new Error(errorMessage))
      }
      console.error(`[useSupport] ${context}:`, err)
    },
    [onError]
  )

  const clearError = useCallback(() => {
    setError(null)
  }, [])

  // =============================================================================
  // CATEGORY ACTIONS
  // =============================================================================

  const loadCategories = useCallback(
    async (isActive?: boolean, targetRole?: string) => {
      setIsLoading(true)
      setError(null)
      try {
        const data = await supportApi.listCategories(isActive, targetRole)
        setCategories(data)
      } catch (err) {
        handleError(err, 'loadCategories')
      } finally {
        setIsLoading(false)
      }
    },
    [handleError]
  )

  const createCategory = useCallback(
    async (data: SupportCategoryCreate): Promise<SupportCategory | null> => {
      setIsLoading(true)
      setError(null)
      try {
        const category = await supportApi.createCategory(data)
        setCategories((prev) => [...prev, category])
        return category
      } catch (err) {
        handleError(err, 'createCategory')
        return null
      } finally {
        setIsLoading(false)
      }
    },
    [handleError]
  )

  const updateCategory = useCallback(
    async (
      categoryId: number,
      data: SupportCategoryUpdate
    ): Promise<SupportCategory | null> => {
      setIsLoading(true)
      setError(null)
      try {
        const updatedCategory = await supportApi.updateCategory(categoryId, data)
        setCategories((prev) =>
          prev.map((c) => (c.id === categoryId ? updatedCategory : c))
        )
        return updatedCategory
      } catch (err) {
        handleError(err, 'updateCategory')
        return null
      } finally {
        setIsLoading(false)
      }
    },
    [handleError]
  )

  const deleteCategory = useCallback(
    async (categoryId: number): Promise<boolean> => {
      setIsLoading(true)
      setError(null)
      try {
        await supportApi.deleteCategory(categoryId)
        setCategories((prev) => prev.filter((c) => c.id !== categoryId))
        return true
      } catch (err) {
        handleError(err, 'deleteCategory')
        return false
      } finally {
        setIsLoading(false)
      }
    },
    [handleError]
  )

  // =============================================================================
  // TICKET ACTIONS - USER
  // =============================================================================

  const loadMyTickets = useCallback(
    async (page: number = 1, pageSize: number = 20, status?: string) => {
      setIsLoading(true)
      setError(null)
      try {
        const response = await supportApi.listMyTickets(page, pageSize, status)
        setTickets(response.tickets)
        setPagination({
          page: response.page,
          pageSize: response.pageSize,
          total: response.total,
          totalPages: response.totalPages,
        })
      } catch (err) {
        handleError(err, 'loadMyTickets')
      } finally {
        setIsLoading(false)
      }
    },
    [handleError]
  )

  const createTicket = useCallback(
    async (data: SupportTicketCreate): Promise<SupportTicket | null> => {
      setIsLoading(true)
      setError(null)
      try {
        const ticket = await supportApi.createTicket(data)
        setTickets((prev) => [ticket, ...prev])
        return ticket
      } catch (err) {
        handleError(err, 'createTicket')
        return null
      } finally {
        setIsLoading(false)
      }
    },
    [handleError]
  )

  const closeTicket = useCallback(
    async (ticketId: number) => {
      setIsLoading(true)
      setError(null)
      try {
        const updatedTicket = await supportApi.closeTicket(ticketId)
        setTickets((prev) =>
          prev.map((t) => (t.id === ticketId ? updatedTicket : t))
        )
        if (currentTicket?.id === ticketId) {
          setCurrentTicket(updatedTicket)
        }
      } catch (err) {
        handleError(err, 'closeTicket')
      } finally {
        setIsLoading(false)
      }
    },
    [handleError, currentTicket]
  )

  // =============================================================================
  // TICKET ACTIONS - ADMIN
  // =============================================================================

  const loadAllTickets = useCallback(
    async (
      page: number = 1,
      pageSize: number = 20,
      filters?: SupportFilters
    ) => {
      setIsLoading(true)
      setError(null)
      try {
        const response = await supportApi.listAllTickets(page, pageSize, filters)
        setTickets(response.tickets)
        setPagination({
          page: response.page,
          pageSize: response.pageSize,
          total: response.total,
          totalPages: response.totalPages,
        })
      } catch (err) {
        handleError(err, 'loadAllTickets')
      } finally {
        setIsLoading(false)
      }
    },
    [handleError]
  )

  const updateTicket = useCallback(
    async (
      ticketId: number,
      data: SupportTicketUpdate
    ): Promise<SupportTicket | null> => {
      setIsLoading(true)
      setError(null)
      try {
        const updatedTicket = await supportApi.updateTicket(ticketId, data)
        setTickets((prev) =>
          prev.map((t) => (t.id === ticketId ? updatedTicket : t))
        )
        if (currentTicket?.id === ticketId) {
          setCurrentTicket(updatedTicket)
        }
        return updatedTicket
      } catch (err) {
        handleError(err, 'updateTicket')
        return null
      } finally {
        setIsLoading(false)
      }
    },
    [handleError, currentTicket]
  )

  // =============================================================================
  // TICKET DETAIL
  // =============================================================================

  const loadTicket = useCallback(
    async (ticketId: number) => {
      setIsLoading(true)
      setError(null)
      try {
        const ticket = await supportApi.getTicket(ticketId)
        setCurrentTicket(ticket)
      } catch (err) {
        handleError(err, 'loadTicket')
      } finally {
        setIsLoading(false)
      }
    },
    [handleError]
  )

  const loadTicketByNumber = useCallback(
    async (ticketNumber: string) => {
      setIsLoading(true)
      setError(null)
      try {
        const ticket = await supportApi.getTicketByNumber(ticketNumber)
        setCurrentTicket(ticket)
      } catch (err) {
        handleError(err, 'loadTicketByNumber')
      } finally {
        setIsLoading(false)
      }
    },
    [handleError]
  )

  // =============================================================================
  // MESSAGE ACTIONS
  // =============================================================================

  const loadMessages = useCallback(
    async (ticketId: number) => {
      setIsLoading(true)
      setError(null)
      try {
        const data = await supportApi.listMessages(ticketId)
        setMessages(data)
      } catch (err) {
        handleError(err, 'loadMessages')
      } finally {
        setIsLoading(false)
      }
    },
    [handleError]
  )

  const addMessage = useCallback(
    async (
      ticketId: number,
      data: SupportMessageCreate
    ): Promise<SupportMessage | null> => {
      setIsLoading(true)
      setError(null)
      try {
        const message = await supportApi.addMessage(ticketId, data)
        setMessages((prev) => [...prev, message])
        return message
      } catch (err) {
        handleError(err, 'addMessage')
        return null
      } finally {
        setIsLoading(false)
      }
    },
    [handleError]
  )

  // =============================================================================
  // STATS ACTIONS
  // =============================================================================

  const loadStats = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const data = await supportApi.getStats()
      setStats(data)
    } catch (err) {
      handleError(err, 'loadStats')
    } finally {
      setIsLoading(false)
    }
  }, [handleError])

  // =============================================================================
  // UTILITY
  // =============================================================================

  const setPage = useCallback((page: number) => {
    setPagination((prev) => ({ ...prev, page }))
  }, [])

  // =============================================================================
  // EFFECTS
  // =============================================================================

  useEffect(() => {
    if (autoLoadCategories) {
      loadCategories(true)
    }
  }, [autoLoadCategories, loadCategories])

  // =============================================================================
  // RETURN
  // =============================================================================

  return {
    // State
    categories,
    tickets,
    currentTicket,
    messages,
    stats,
    isLoading,
    error,
    pagination,

    // Category actions
    loadCategories,
    createCategory,
    updateCategory,
    deleteCategory,

    // Ticket actions - User
    loadMyTickets,
    createTicket,
    closeTicket,

    // Ticket actions - Admin
    loadAllTickets,
    updateTicket,

    // Ticket detail
    loadTicket,
    loadTicketByNumber,

    // Message actions
    loadMessages,
    addMessage,

    // Stats actions
    loadStats,

    // Utility
    clearError,
    setPage,
  }
}

export default useSupport
