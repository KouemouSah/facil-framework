/**
 * Support Module Types - 100% Aligned with Backend Pydantic Models
 *
 * Backend Reference: packages/backend/app/modules/support/models/support.py
 *
 * @module support/types
 * @author Claude Code
 * @date 2025-12-17
 *
 * BACKEND ALIGNMENT: Complete support ticketing system
 * - Categories management
 * - Tickets with full lifecycle
 * - Messages/conversation threads
 * - Statistics for admin dashboard
 */

// =============================================================================
// ENUMS - Aligned with Backend Exact Values
// =============================================================================

export enum TicketPriority {
  LOW = 'low',
  NORMAL = 'normal',
  HIGH = 'high',
  URGENT = 'urgent',
}

export enum TicketStatus {
  OPEN = 'open',
  IN_PROGRESS = 'in_progress',
  PENDING_USER = 'pending_user',
  RESOLVED = 'resolved',
  CLOSED = 'closed',
}

export enum TargetRole {
  ADMIN = 'admin',
  AGENT = 'agent',
  ALL = 'all',
}

// =============================================================================
// CATEGORY TYPES
// =============================================================================

export interface SupportCategory {
  id: number
  code: string
  nameEs: string
  nameFr: string | null
  nameEn: string | null
  descriptionEs: string | null
  descriptionFr: string | null
  descriptionEn: string | null
  targetRole: TargetRole | string
  icon: string | null
  isActive: boolean
  sortOrder: number
  createdAt: string
}

export interface SupportCategoryCreate {
  code: string
  nameEs: string
  nameFr?: string
  nameEn?: string
  descriptionEs?: string
  descriptionFr?: string
  descriptionEn?: string
  targetRole?: TargetRole | string
  icon?: string
  isActive?: boolean
  sortOrder?: number
}

export interface SupportCategoryUpdate {
  nameEs?: string
  nameFr?: string
  nameEn?: string
  descriptionEs?: string
  descriptionFr?: string
  descriptionEn?: string
  targetRole?: TargetRole | string
  icon?: string
  isActive?: boolean
  sortOrder?: number
}

// =============================================================================
// TICKET TYPES
// =============================================================================

export interface SupportTicket {
  id: number
  ticketNumber: string
  categoryId: number | null
  subject: string
  description: string
  priority: TicketPriority | string
  status: TicketStatus | string
  createdBy: string
  assignedTo: string | null
  resolvedAt: string | null
  closedAt: string | null
  createdAt: string
  updatedAt: string | null
  // Populated fields
  categoryCode?: string
  categoryName?: string
  createdByName?: string
  createdByEmail?: string
  assignedToName?: string
  assignedToEmail?: string
  messageCount?: number
}

export interface SupportTicketCreate {
  categoryId?: number
  subject: string
  description: string
  priority?: TicketPriority | string
}

export interface SupportTicketUpdate {
  subject?: string
  description?: string
  priority?: TicketPriority | string
  status?: TicketStatus | string
  assignedTo?: string | null
  categoryId?: number
}

export interface SupportTicketListResponse {
  tickets: SupportTicket[]
  total: number
  page: number
  pageSize: number
  totalPages: number
}

// =============================================================================
// MESSAGE TYPES
// =============================================================================

export interface SupportMessage {
  id: number
  ticketId: number
  senderId: string
  content: string
  isInternal: boolean
  createdAt: string
  // Populated fields
  senderName?: string
  senderEmail?: string
  senderRole?: string
}

export interface SupportMessageCreate {
  content: string
  isInternal?: boolean
}

// =============================================================================
// STATISTICS TYPES
// =============================================================================

export interface StatusCount {
  status: string
  count: number
}

export interface PriorityCount {
  priority: string
  count: number
}

export interface CategoryCount {
  categoryId: number
  categoryCode: string
  count: number
}

export interface SupportStats {
  totalTickets: number
  openTickets: number
  inProgressTickets: number
  resolvedTickets: number
  closedTickets: number
  averageResolutionTimeHours: number | null
  statusBreakdown: StatusCount[]
  priorityBreakdown: PriorityCount[]
  categoryBreakdown: CategoryCount[]
}

// =============================================================================
// UI STATE TYPES
// =============================================================================

export interface SupportFilters {
  status?: TicketStatus | string
  priority?: TicketPriority | string
  categoryId?: number
  assignedTo?: string
  search?: string
}

export interface SupportState {
  tickets: SupportTicket[]
  currentTicket: SupportTicket | null
  messages: SupportMessage[]
  categories: SupportCategory[]
  stats: SupportStats | null
  isLoading: boolean
  error: string | null
  filters: SupportFilters
  pagination: {
    page: number
    pageSize: number
    total: number
    totalPages: number
  }
}

// =============================================================================
// HELPER FUNCTIONS
// =============================================================================

/**
 * Get localized category name
 */
export function getCategoryName(
  category: SupportCategory,
  locale: string = 'es'
): string {
  switch (locale) {
    case 'fr':
      return category.nameFr || category.nameEs
    case 'en':
      return category.nameEn || category.nameEs
    default:
      return category.nameEs
  }
}

/**
 * Get localized category description
 */
export function getCategoryDescription(
  category: SupportCategory,
  locale: string = 'es'
): string | null {
  switch (locale) {
    case 'fr':
      return category.descriptionFr || category.descriptionEs
    case 'en':
      return category.descriptionEn || category.descriptionEs
    default:
      return category.descriptionEs
  }
}

/**
 * Get priority color for UI
 */
export function getPriorityColor(priority: string): string {
  switch (priority) {
    case TicketPriority.URGENT:
      return 'destructive'
    case TicketPriority.HIGH:
      return 'warning'
    case TicketPriority.NORMAL:
      return 'default'
    case TicketPriority.LOW:
      return 'secondary'
    default:
      return 'default'
  }
}

/**
 * Get status color for UI
 */
export function getStatusColor(status: string): string {
  switch (status) {
    case TicketStatus.OPEN:
      return 'info'
    case TicketStatus.IN_PROGRESS:
      return 'warning'
    case TicketStatus.PENDING_USER:
      return 'secondary'
    case TicketStatus.RESOLVED:
      return 'success'
    case TicketStatus.CLOSED:
      return 'muted'
    default:
      return 'default'
  }
}

/**
 * Format ticket number for display
 */
export function formatTicketNumber(ticketNumber: string): string {
  return ticketNumber
}

/**
 * Check if ticket can be closed by user
 */
export function canUserCloseTicket(ticket: SupportTicket): boolean {
  return [TicketStatus.RESOLVED, TicketStatus.PENDING_USER].includes(
    ticket.status as TicketStatus
  )
}

/**
 * Check if ticket is editable
 */
export function isTicketEditable(ticket: SupportTicket): boolean {
  return ![TicketStatus.CLOSED, TicketStatus.RESOLVED].includes(
    ticket.status as TicketStatus
  )
}
