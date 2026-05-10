/**
 * Notification Template API Service
 * API calls for notification template management
 */

import apiClient from '@/core/api/client'
import type {
  NotificationTemplateCreate,
  NotificationTemplateUpdate,
  NotificationTemplateResponse,
  NotificationTemplateListResponse,
  NotificationTemplateListParams,
  NotificationPreviewRequest,
  NotificationPreviewResponse,
} from '../types/notification-template'

const BASE_URL = '/communications/notification-templates'

// =============================================================================
// UTILITY FUNCTIONS - snake_case to camelCase transformation
// =============================================================================

function snakeToCamel(str: string): string {
  return str.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase())
}

function camelToSnake(str: string): string {
  return str.replace(/[A-Z]/g, letter => `_${letter.toLowerCase()}`)
}

function transformKeys<T>(obj: unknown): T {
  if (obj === null || obj === undefined) return obj as T
  if (Array.isArray(obj)) return obj.map(item => transformKeys(item)) as T
  if (typeof obj !== 'object') return obj as T

  const transformed: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(obj as Record<string, unknown>)) {
    const camelKey = snakeToCamel(key)
    transformed[camelKey] = transformKeys(value)
  }
  return transformed as T
}

function toSnakeCase<T>(obj: unknown): T {
  if (obj === null || obj === undefined) return obj as T
  if (Array.isArray(obj)) return obj.map(item => toSnakeCase(item)) as T
  if (obj instanceof Date) return obj.toISOString() as unknown as T
  if (typeof obj !== 'object') return obj as T

  const transformed: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(obj as Record<string, unknown>)) {
    const snakeKey = camelToSnake(key)
    transformed[snakeKey] = toSnakeCase(value)
  }
  return transformed as T
}

export const notificationTemplateApi = {
  /**
   * Create a new notification template
   */
  async create(data: NotificationTemplateCreate): Promise<NotificationTemplateResponse> {
    const response = await apiClient.post(BASE_URL, toSnakeCase(data))
    return transformKeys<NotificationTemplateResponse>(response.data)
  },

  /**
   * Get notification template by ID
   */
  async getById(id: number): Promise<NotificationTemplateResponse> {
    const response = await apiClient.get(`${BASE_URL}/${id}`)
    return transformKeys<NotificationTemplateResponse>(response.data)
  },

  /**
   * Get notification template by code
   */
  async getByCode(code: string): Promise<NotificationTemplateResponse> {
    const response = await apiClient.get(`${BASE_URL}/code/${code}`)
    return transformKeys<NotificationTemplateResponse>(response.data)
  },

  /**
   * List notification templates with pagination and filters
   */
  async list(params?: NotificationTemplateListParams): Promise<NotificationTemplateListResponse> {
    // Convert params to snake_case for API
    const snakeParams = params ? toSnakeCase(params) : undefined
    const response = await apiClient.get(BASE_URL, {
      params: snakeParams,
    })
    return transformKeys<NotificationTemplateListResponse>(response.data)
  },

  /**
   * Update notification template
   */
  async update(id: number, data: NotificationTemplateUpdate): Promise<NotificationTemplateResponse> {
    const response = await apiClient.put(`${BASE_URL}/${id}`, toSnakeCase(data))
    return transformKeys<NotificationTemplateResponse>(response.data)
  },

  /**
   * Delete notification template
   */
  async delete(id: number): Promise<void> {
    await apiClient.delete(`${BASE_URL}/${id}`)
  },

  /**
   * Preview notification with variable substitution
   */
  async preview(request: NotificationPreviewRequest): Promise<NotificationPreviewResponse> {
    const response = await apiClient.post(
      `${BASE_URL}/preview`,
      toSnakeCase(request)
    )
    return transformKeys<NotificationPreviewResponse>(response.data)
  },

  /**
   * Get all active notification templates
   */
  async getActive(): Promise<NotificationTemplateResponse[]> {
    const response = await apiClient.get(`${BASE_URL}/active/list`)
    return transformKeys<NotificationTemplateResponse[]>(response.data)
  },
}
