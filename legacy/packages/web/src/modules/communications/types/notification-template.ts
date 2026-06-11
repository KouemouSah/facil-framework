/**
 * Notification Template Types
 * TypeScript interfaces for notification template management
 */

// =============================================================================
// NOTIFICATION TEMPLATE
// =============================================================================

export type NotificationType = 'info' | 'success' | 'warning' | 'error'
export type NotificationPriority = 'low' | 'normal' | 'high' | 'urgent'

export interface NotificationTemplateBase {
  templateCode: string
  nameEs: string
  nameFr?: string
  nameEn?: string
  titleEs: string
  titleFr?: string
  titleEn?: string
  bodyEs: string
  bodyFr?: string
  bodyEn?: string
  icon?: string
  actionUrl?: string
  variables: string[]
  notificationType: NotificationType
  priority: NotificationPriority
  isActive: boolean
}

export interface NotificationTemplateCreate extends NotificationTemplateBase {}

export interface NotificationTemplateUpdate {
  nameEs?: string
  nameFr?: string
  nameEn?: string
  titleEs?: string
  titleFr?: string
  titleEn?: string
  bodyEs?: string
  bodyFr?: string
  bodyEn?: string
  icon?: string
  actionUrl?: string
  variables?: string[]
  notificationType?: NotificationType
  priority?: NotificationPriority
  isActive?: boolean
}

export interface NotificationTemplateResponse extends NotificationTemplateBase {
  id: number
  createdAt: string
  updatedAt?: string
  createdBy?: number
}

export interface NotificationTemplateListResponse {
  templates: NotificationTemplateResponse[]
  total: number
  page: number
  pageSize: number
  totalPages: number
}

export interface NotificationPreviewRequest {
  templateId: number
  language: 'es' | 'fr' | 'en'
  variables: Record<string, string | number>
}

export interface NotificationPreviewResponse {
  title: string
  body: string
  icon?: string
  actionUrl?: string
  notificationType: NotificationType
  priority: NotificationPriority
}

export interface NotificationTemplateListParams {
  page?: number
  pageSize?: number
  isActive?: boolean
  notificationType?: NotificationType
  search?: string
}

// Helper type for notification colors
export type NotificationColor = 'blue' | 'green' | 'yellow' | 'red'

export const NOTIFICATION_TYPE_COLORS: Record<NotificationType, NotificationColor> = {
  info: 'blue',
  success: 'green',
  warning: 'yellow',
  error: 'red',
}

export const NOTIFICATION_TYPE_LABELS: Record<NotificationType, string> = {
  info: 'Information',
  success: 'Success',
  warning: 'Warning',
  error: 'Error',
}

export const NOTIFICATION_PRIORITY_LABELS: Record<NotificationPriority, string> = {
  low: 'Low',
  normal: 'Normal',
  high: 'High',
  urgent: 'Urgent',
}
