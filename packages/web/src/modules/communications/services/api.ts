/**
 * Communications API Service
 * Handles all API calls to communications and email templates backend endpoints
 *
 * @module communications/services
 *
 * BACKEND ALIGNMENT:
 * Base URL: /api/v1/email-templates
 * Routes: From app/modules/communications/api/email_templates_routes.py
 *
 * ENDPOINTS:
 * - GET    /email-templates - List all templates
 * - GET    /email-templates/search?q={query} - Search templates
 * - GET    /email-templates/{id} - Get single template
 * - GET    /email-templates/{id}/preview - Get HTML content
 * - POST   /email-templates - Create template (requires communications.manage)
 * - PUT    /email-templates/{id} - Update template (requires communications.manage)
 * - DELETE /email-templates/{id} - Delete template (requires communications.manage)
 */

import type {
  EmailTemplateCreate,
  EmailTemplateUpdate,
  EmailTemplateResponse,
  EmailTemplateListResponse,
  EmailTemplatePreview,
  EmailTemplateListParams,
  EmailTemplateSearchParams,
  WebhookCreate,
  WebhookUpdate,
  WebhookResponse,
  WebhookListResponse,
  WebhookListParams,
  WebhookTestRequest,
  WebhookTestResponse,
  WebhookLogsResponse,
  WebhookLogParams,
} from '@/modules/communications/types'
import { getAuthData, setAuthData, clearAuthData } from '@/core/auth/storage'
import { appConfig } from '@/core/config/app'

// =============================================================================
// CONFIGURATION
// =============================================================================

const API_BASE_URL = appConfig.api.baseUrl
const API_VERSION = `/api/${appConfig.api.version}`
const EMAIL_TEMPLATES_BASE = '/communications/email-templates'
const WEBHOOKS_BASE = '/communications/webhooks'

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

// =============================================================================
// HTTP CLIENT
// =============================================================================

class ApiClient {
  private baseUrl: string
  private isRefreshing: boolean = false
  private refreshPromise: Promise<string | null> | null = null

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl
  }

  private async refreshToken(): Promise<string | null> {
    const authData = getAuthData()
    if (!authData?.refresh_token) {
      return null
    }

    try {
      const response = await fetch(`${API_BASE_URL}${API_VERSION}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: authData.refresh_token }),
      })

      if (!response.ok) {
        throw new Error('Token refresh failed')
      }

      const data = await response.json()
      const { access_token, refresh_token } = data

      setAuthData({
        ...authData,
        access_token,
        refresh_token,
      })

      return access_token
    } catch {
      clearAuthData()
      if (typeof window !== 'undefined') {
        const pathParts = window.location.pathname.split('/')
        const locale = pathParts[1] && ['es', 'fr', 'en'].includes(pathParts[1]) ? pathParts[1] : 'es'
        window.location.href = `/${locale}/auth`
      }
      return null
    }
  }

  private async getFreshToken(): Promise<string | null> {
    if (this.isRefreshing && this.refreshPromise) {
      return this.refreshPromise
    }

    this.isRefreshing = true
    this.refreshPromise = this.refreshToken()

    try {
      const token = await this.refreshPromise
      return token
    } finally {
      this.isRefreshing = false
      this.refreshPromise = null
    }
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {},
    isRetry: boolean = false
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`

    const authData = typeof window !== 'undefined' ? getAuthData() : null

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    }

    if (authData?.access_token) {
      headers['Authorization'] = `Bearer ${authData.access_token}`
    }

    if (options.headers) {
      const headersToMerge = options.headers instanceof Headers
        ? Object.fromEntries(options.headers.entries())
        : Array.isArray(options.headers)
        ? Object.fromEntries(options.headers)
        : options.headers
      Object.assign(headers, headersToMerge)
    }

    const response = await fetch(url, {
      ...options,
      headers,
    })

    if (response.status === 401 && !isRetry) {
      const newToken = await this.getFreshToken()
      if (newToken) {
        return this.request<T>(endpoint, options, true)
      }
      throw new Error('Invalid or expired access token')
    }

    if (!response.ok) {
      const error = await response.json().catch(() => ({
        detail: `HTTP ${response.status}: ${response.statusText}`,
      }))
      throw new Error(error.detail || 'API request failed')
    }

    if (response.status === 204) {
      return {} as T
    }

    return response.json()
  }

  async get<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: 'GET' })
  }

  async post<T>(endpoint: string, data: unknown): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async put<T>(endpoint: string, data: unknown): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'PUT',
      body: JSON.stringify(data),
    })
  }

  async delete<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: 'DELETE' })
  }
}

const client = new ApiClient(API_BASE_URL + API_VERSION)

// =============================================================================
// EMAIL TEMPLATES API
// =============================================================================

export const emailTemplatesApi = {
  /**
   * GET /api/v1/email-templates
   * List all email templates with pagination and filters
   */
  list: async (params?: EmailTemplateListParams): Promise<EmailTemplateListResponse> => {
    const queryParams = new URLSearchParams()
    if (params?.page) queryParams.append('page', String(params.page))
    if (params?.pageSize) queryParams.append('page_size', String(params.pageSize))
    if (params?.category) queryParams.append('category', params.category)
    if (params?.isActive !== undefined) queryParams.append('is_active', String(params.isActive))

    const query = queryParams.toString()
    const response = await client.get<EmailTemplateListResponse>(
      `${EMAIL_TEMPLATES_BASE}${query ? `?${query}` : ''}`
    )
    return transformKeys<EmailTemplateListResponse>(response)
  },

  /**
   * GET /api/v1/email-templates/search?q={query}
   * Search email templates by name or code
   */
  search: async (params: EmailTemplateSearchParams): Promise<EmailTemplateListResponse> => {
    const queryParams = new URLSearchParams()
    queryParams.append('q', params.q)
    if (params.page) queryParams.append('page', String(params.page))
    if (params.pageSize) queryParams.append('page_size', String(params.pageSize))

    const response = await client.get<EmailTemplateListResponse>(
      `${EMAIL_TEMPLATES_BASE}/search?${queryParams.toString()}`
    )
    return transformKeys<EmailTemplateListResponse>(response)
  },

  /**
   * GET /api/v1/email-templates/{template_id}
   * Get single email template by ID
   */
  get: async (templateId: number): Promise<EmailTemplateResponse> => {
    const response = await client.get<EmailTemplateResponse>(
      `${EMAIL_TEMPLATES_BASE}/${templateId}`
    )
    return transformKeys<EmailTemplateResponse>(response)
  },

  /**
   * GET /api/v1/email-templates/{template_id}/preview
   * Get HTML content preview for an email template
   */
  preview: async (templateId: number): Promise<EmailTemplatePreview> => {
    const response = await client.get<EmailTemplatePreview>(
      `${EMAIL_TEMPLATES_BASE}/${templateId}/preview`
    )
    return transformKeys<EmailTemplatePreview>(response)
  },

  /**
   * POST /api/v1/email-templates
   * Create new email template
   * Auth: Required + Permission "communications.manage"
   */
  create: async (data: EmailTemplateCreate): Promise<EmailTemplateResponse> => {
    const response = await client.post<EmailTemplateResponse>(
      EMAIL_TEMPLATES_BASE,
      toSnakeCase(data)
    )
    return transformKeys<EmailTemplateResponse>(response)
  },

  /**
   * PUT /api/v1/email-templates/{template_id}
   * Update email template
   * Auth: Required + Permission "communications.manage"
   */
  update: async (
    templateId: number,
    data: EmailTemplateUpdate
  ): Promise<EmailTemplateResponse> => {
    const response = await client.put<EmailTemplateResponse>(
      `${EMAIL_TEMPLATES_BASE}/${templateId}`,
      toSnakeCase(data)
    )
    return transformKeys<EmailTemplateResponse>(response)
  },

  /**
   * DELETE /api/v1/email-templates/{template_id}
   * Delete email template
   * Auth: Required + Permission "communications.manage"
   */
  delete: async (templateId: number): Promise<void> => {
    await client.delete<void>(`${EMAIL_TEMPLATES_BASE}/${templateId}`)
  },
}

// =============================================================================
// PUSH TEMPLATES API
// =============================================================================

import type {
  PushTemplateCreate,
  PushTemplateUpdate,
  PushTemplateResponse,
  PushTemplateListResponse,
  PushNotificationPreview,
  PushTemplateListParams,
  PushTemplateStats,
} from '@/modules/communications/types'

const PUSH_TEMPLATES_BASE = '/communications/push-templates'

export const pushTemplatesApi = {
  /**
   * GET /api/v1/push-templates
   * List all push templates with pagination and filters
   */
  list: async (params?: PushTemplateListParams): Promise<PushTemplateListResponse> => {
    const queryParams = new URLSearchParams()
    if (params?.page) queryParams.append('page', String(params.page))
    if (params?.pageSize) queryParams.append('page_size', String(params.pageSize))
    if (params?.isActive !== undefined) queryParams.append('is_active', String(params.isActive))
    if (params?.platform) queryParams.append('platform', params.platform)
    if (params?.search) queryParams.append('search', params.search)

    const query = queryParams.toString()
    const response = await client.get<PushTemplateListResponse>(
      `${PUSH_TEMPLATES_BASE}${query ? `?${query}` : ''}`
    )
    return transformKeys<PushTemplateListResponse>(response)
  },

  /**
   * GET /api/v1/push-templates/stats
   * Get push template statistics
   */
  stats: async (): Promise<PushTemplateStats> => {
    const response = await client.get<PushTemplateStats>(
      `${PUSH_TEMPLATES_BASE}/stats`
    )
    return transformKeys<PushTemplateStats>(response)
  },

  /**
   * GET /api/v1/push-templates/{template_id}
   * Get single push template by ID
   */
  get: async (templateId: number): Promise<PushTemplateResponse> => {
    const response = await client.get<PushTemplateResponse>(
      `${PUSH_TEMPLATES_BASE}/${templateId}`
    )
    return transformKeys<PushTemplateResponse>(response)
  },

  /**
   * GET /api/v1/push-templates/code/{code}
   * Get push template by code
   */
  getByCode: async (code: string): Promise<PushTemplateResponse> => {
    const response = await client.get<PushTemplateResponse>(
      `${PUSH_TEMPLATES_BASE}/code/${code}`
    )
    return transformKeys<PushTemplateResponse>(response)
  },

  /**
   * POST /api/v1/push-templates/{template_id}/preview
   * Preview push notification with sample data
   */
  preview: async (
    templateId: number,
    language: string = 'es',
    variables?: Record<string, string>
  ): Promise<PushNotificationPreview> => {
    const queryParams = new URLSearchParams()
    queryParams.append('language', language)

    const response = await client.post<PushNotificationPreview>(
      `${PUSH_TEMPLATES_BASE}/${templateId}/preview?${queryParams.toString()}`,
      variables || null
    )
    return transformKeys<PushNotificationPreview>(response)
  },

  /**
   * POST /api/v1/push-templates
   * Create new push template
   * Auth: Required + Admin permission
   */
  create: async (data: PushTemplateCreate): Promise<PushTemplateResponse> => {
    const response = await client.post<PushTemplateResponse>(
      PUSH_TEMPLATES_BASE,
      toSnakeCase(data)
    )
    return transformKeys<PushTemplateResponse>(response)
  },

  /**
   * PUT /api/v1/push-templates/{template_id}
   * Update push template
   * Auth: Required + Admin permission
   */
  update: async (
    templateId: number,
    data: PushTemplateUpdate
  ): Promise<PushTemplateResponse> => {
    const response = await client.put<PushTemplateResponse>(
      `${PUSH_TEMPLATES_BASE}/${templateId}`,
      toSnakeCase(data)
    )
    return transformKeys<PushTemplateResponse>(response)
  },

  /**
   * DELETE /api/v1/push-templates/{template_id}
   * Delete push template
   * Auth: Required + Admin permission
   */
  delete: async (templateId: number): Promise<void> => {
    await client.delete<void>(`${PUSH_TEMPLATES_BASE}/${templateId}`)
  },
}

// =============================================================================
// WEBHOOKS API
// =============================================================================

export const webhooksApi = {
  /**
   * GET /api/v1/webhooks
   * List all webhook configurations with pagination and filters
   */
  list: async (params?: WebhookListParams): Promise<WebhookListResponse> => {
    const queryParams = new URLSearchParams()
    if (params?.page) queryParams.append('page', String(params.page))
    if (params?.pageSize) queryParams.append('page_size', String(params.pageSize))
    if (params?.webhookType) queryParams.append('webhook_type', params.webhookType)
    if (params?.isActive !== undefined) queryParams.append('is_active', String(params.isActive))

    const query = queryParams.toString()
    const response = await client.get<WebhookListResponse>(
      `${WEBHOOKS_BASE}${query ? `?${query}` : ''}`
    )
    return transformKeys<WebhookListResponse>(response)
  },

  /**
   * GET /api/v1/webhooks/{webhook_id}
   * Get single webhook configuration by ID
   */
  get: async (webhookId: number): Promise<WebhookResponse> => {
    const response = await client.get<WebhookResponse>(
      `${WEBHOOKS_BASE}/${webhookId}`
    )
    return transformKeys<WebhookResponse>(response)
  },

  /**
   * POST /api/v1/webhooks
   * Create new webhook configuration
   * Auth: Required + Permission "manage:communications"
   */
  create: async (data: WebhookCreate): Promise<WebhookResponse> => {
    const response = await client.post<WebhookResponse>(
      WEBHOOKS_BASE,
      toSnakeCase(data)
    )
    return transformKeys<WebhookResponse>(response)
  },

  /**
   * PUT /api/v1/webhooks/{webhook_id}
   * Update webhook configuration
   * Auth: Required + Permission "manage:communications"
   */
  update: async (
    webhookId: number,
    data: WebhookUpdate
  ): Promise<WebhookResponse> => {
    const response = await client.put<WebhookResponse>(
      `${WEBHOOKS_BASE}/${webhookId}`,
      toSnakeCase(data)
    )
    return transformKeys<WebhookResponse>(response)
  },

  /**
   * DELETE /api/v1/webhooks/{webhook_id}
   * Delete webhook configuration
   * Auth: Required + Permission "manage:communications"
   */
  delete: async (webhookId: number): Promise<void> => {
    await client.delete<void>(`${WEBHOOKS_BASE}/${webhookId}`)
  },

  /**
   * POST /api/v1/webhooks/{webhook_id}/test
   * Test webhook by sending a test request
   * Auth: Required + Permission "manage:communications"
   */
  test: async (
    webhookId: number,
    data: WebhookTestRequest
  ): Promise<WebhookTestResponse> => {
    const response = await client.post<WebhookTestResponse>(
      `${WEBHOOKS_BASE}/${webhookId}/test`,
      toSnakeCase(data)
    )
    return transformKeys<WebhookTestResponse>(response)
  },

  /**
   * GET /api/v1/webhooks/{webhook_id}/logs
   * Get execution logs for webhook
   * Auth: Required + Permission "read:communications"
   */
  logs: async (
    webhookId: number,
    params?: WebhookLogParams
  ): Promise<WebhookLogsResponse> => {
    const queryParams = new URLSearchParams()
    if (params?.page) queryParams.append('page', String(params.page))
    if (params?.pageSize) queryParams.append('page_size', String(params.pageSize))

    const query = queryParams.toString()
    const response = await client.get<WebhookLogsResponse>(
      `${WEBHOOKS_BASE}/${webhookId}/logs${query ? `?${query}` : ''}`
    )
    return transformKeys<WebhookLogsResponse>(response)
  },
}

// =============================================================================
// SMS TEMPLATES API
// =============================================================================

import type {
  SmsTemplateCreate,
  SmsTemplateUpdate,
  SmsTemplateResponse,
  SmsTemplateListResponse,
  SmsTemplateListParams,
  SmsCharacterCount,
  SmsTemplateRenderRequest,
  SmsTemplateRenderResponse,
  SmsCategoryStats,
} from '@/modules/communications/types'

const SMS_TEMPLATES_BASE = '/communications/sms-templates'

export const smsTemplatesApi = {
  /**
   * GET /api/v1/communications/sms-templates
   * List all SMS templates with pagination and filters
   */
  list: async (params?: SmsTemplateListParams): Promise<SmsTemplateListResponse> => {
    const queryParams = new URLSearchParams()
    if (params?.page) queryParams.append('page', String(params.page))
    if (params?.pageSize) queryParams.append('page_size', String(params.pageSize))
    if (params?.category) queryParams.append('category', params.category)
    if (params?.isActive !== undefined) queryParams.append('is_active', String(params.isActive))
    if (params?.search) queryParams.append('search', params.search)

    const query = queryParams.toString()
    const response = await client.get<SmsTemplateListResponse>(
      `${SMS_TEMPLATES_BASE}${query ? `?${query}` : ''}`
    )
    return transformKeys<SmsTemplateListResponse>(response)
  },

  /**
   * GET /api/v1/communications/sms-templates/{template_id}
   * Get single SMS template by ID
   */
  get: async (templateId: number): Promise<SmsTemplateResponse> => {
    const response = await client.get<SmsTemplateResponse>(
      `${SMS_TEMPLATES_BASE}/${templateId}`
    )
    return transformKeys<SmsTemplateResponse>(response)
  },

  /**
   * GET /api/v1/communications/sms-templates/code/{code}
   * Get SMS template by code
   */
  getByCode: async (code: string): Promise<SmsTemplateResponse> => {
    const response = await client.get<SmsTemplateResponse>(
      `${SMS_TEMPLATES_BASE}/code/${code}`
    )
    return transformKeys<SmsTemplateResponse>(response)
  },

  /**
   * GET /api/v1/communications/sms-templates/categories/list
   * Get SMS template categories with counts
   */
  getCategories: async (): Promise<{ categories: SmsCategoryStats[]; total: number }> => {
    const response = await client.get<{ categories: SmsCategoryStats[]; total: number }>(
      `${SMS_TEMPLATES_BASE}/categories/list`
    )
    return transformKeys<{ categories: SmsCategoryStats[]; total: number }>(response)
  },

  /**
   * POST /api/v1/communications/sms-templates
   * Create new SMS template
   * Auth: Required + Admin permission
   */
  create: async (data: SmsTemplateCreate): Promise<SmsTemplateResponse> => {
    const response = await client.post<SmsTemplateResponse>(
      SMS_TEMPLATES_BASE,
      toSnakeCase(data)
    )
    return transformKeys<SmsTemplateResponse>(response)
  },

  /**
   * PUT /api/v1/communications/sms-templates/{template_id}
   * Update SMS template
   * Auth: Required + Admin permission
   */
  update: async (
    templateId: number,
    data: SmsTemplateUpdate
  ): Promise<SmsTemplateResponse> => {
    const response = await client.put<SmsTemplateResponse>(
      `${SMS_TEMPLATES_BASE}/${templateId}`,
      toSnakeCase(data)
    )
    return transformKeys<SmsTemplateResponse>(response)
  },

  /**
   * DELETE /api/v1/communications/sms-templates/{template_id}
   * Delete SMS template
   * Auth: Required + Admin permission
   */
  delete: async (templateId: number): Promise<void> => {
    await client.delete<void>(`${SMS_TEMPLATES_BASE}/${templateId}`)
  },

  /**
   * POST /api/v1/communications/sms-templates/render
   * Render SMS template with variables
   */
  render: async (request: SmsTemplateRenderRequest): Promise<SmsTemplateRenderResponse> => {
    const response = await client.post<SmsTemplateRenderResponse>(
      `${SMS_TEMPLATES_BASE}/render`,
      toSnakeCase(request)
    )
    return transformKeys<SmsTemplateRenderResponse>(response)
  },

  /**
   * POST /api/v1/communications/sms-templates/calculate-chars
   * Calculate character count for SMS content
   */
  calculateChars: async (content: string): Promise<SmsCharacterCount> => {
    const queryParams = new URLSearchParams()
    queryParams.append('content', content)

    const response = await client.post<SmsCharacterCount>(
      `${SMS_TEMPLATES_BASE}/calculate-chars?${queryParams.toString()}`,
      {}
    )
    return transformKeys<SmsCharacterCount>(response)
  },
}

// =============================================================================
// USSD CONFIGURATION API
// =============================================================================

import type {
  UssdConfigCreate,
  UssdConfigUpdate,
  UssdConfigResponse,
  UssdConfigListResponse,
  UssdConfigListParams,
  MenuValidationResult,
  MenuNode,
  UssdOperatorInfo,
} from '@/modules/communications/types'

const USSD_BASE = '/communications/ussd'

export const ussdApi = {
  /**
   * GET /api/v1/communications/ussd
   * List all USSD configurations with pagination and filters
   */
  list: async (params?: UssdConfigListParams): Promise<UssdConfigListResponse> => {
    const queryParams = new URLSearchParams()
    if (params?.page) queryParams.append('page', String(params.page))
    if (params?.pageSize) queryParams.append('page_size', String(params.pageSize))
    if (params?.isActive !== undefined) queryParams.append('is_active', String(params.isActive))

    const query = queryParams.toString()
    const response = await client.get<UssdConfigListResponse>(
      `${USSD_BASE}${query ? `?${query}` : ''}`
    )
    return transformKeys<UssdConfigListResponse>(response)
  },

  /**
   * GET /api/v1/communications/ussd/{config_id}
   * Get single USSD configuration by ID
   */
  get: async (configId: number): Promise<UssdConfigResponse> => {
    const response = await client.get<UssdConfigResponse>(
      `${USSD_BASE}/${configId}`
    )
    return transformKeys<UssdConfigResponse>(response)
  },

  /**
   * GET /api/v1/communications/ussd/operator/{operator}
   * Get USSD configuration by operator name
   */
  getByOperator: async (operator: string): Promise<UssdConfigResponse> => {
    const response = await client.get<UssdConfigResponse>(
      `${USSD_BASE}/operator/${operator}`
    )
    return transformKeys<UssdConfigResponse>(response)
  },

  /**
   * POST /api/v1/communications/ussd
   * Create new USSD configuration
   * Auth: Required + Permission "create:ussd_configs"
   */
  create: async (data: UssdConfigCreate): Promise<UssdConfigResponse> => {
    const response = await client.post<UssdConfigResponse>(
      USSD_BASE,
      toSnakeCase(data)
    )
    return transformKeys<UssdConfigResponse>(response)
  },

  /**
   * PUT /api/v1/communications/ussd/{config_id}
   * Update USSD configuration
   * Auth: Required + Permission "update:ussd_configs"
   */
  update: async (
    configId: number,
    data: UssdConfigUpdate
  ): Promise<UssdConfigResponse> => {
    const response = await client.put<UssdConfigResponse>(
      `${USSD_BASE}/${configId}`,
      toSnakeCase(data)
    )
    return transformKeys<UssdConfigResponse>(response)
  },

  /**
   * DELETE /api/v1/communications/ussd/{config_id}
   * Delete USSD configuration
   * Auth: Required + Permission "delete:ussd_configs"
   */
  delete: async (configId: number): Promise<void> => {
    await client.delete<void>(`${USSD_BASE}/${configId}`)
  },

  /**
   * POST /api/v1/communications/ussd/validate
   * Validate menu structure without saving
   * Auth: Required
   */
  validateMenu: async (menuStructure: MenuNode[]): Promise<MenuValidationResult> => {
    const response = await client.post<MenuValidationResult>(
      `${USSD_BASE}/validate`,
      { menu_structure: toSnakeCase(menuStructure) }
    )
    return transformKeys<MenuValidationResult>(response)
  },

  /**
   * GET /api/v1/communications/ussd/operators/list
   * List available mobile operators
   * Public endpoint - No authentication required
   */
  listOperators: async (): Promise<UssdOperatorInfo[]> => {
    const response = await client.get<UssdOperatorInfo[]>(
      `${USSD_BASE}/operators/list`
    )
    return transformKeys<UssdOperatorInfo[]>(response)
  },
}

// =============================================================================
// PROVIDER SETTINGS API
// =============================================================================

import type {
  ProviderSettingsCreate,
  ProviderSettingsUpdate,
  ProviderSettingsResponse,
  ProviderSettingsListResponse,
  ProviderSettingsListParams,
  ProviderTestRequest,
  ProviderTestResponse,
  CommunicationProviderType,
} from '@/modules/communications/types'

const PROVIDERS_BASE = '/communications/providers'

export const providerSettingsApi = {
  /**
   * GET /api/v1/communications/providers
   * List all provider configurations
   */
  list: async (params?: ProviderSettingsListParams): Promise<ProviderSettingsListResponse> => {
    const queryParams = new URLSearchParams()
    if (params?.providerType) queryParams.append('provider_type', params.providerType)
    if (params?.isActive !== undefined) queryParams.append('is_active', String(params.isActive))
    if (params?.limit) queryParams.append('limit', String(params.limit))
    if (params?.offset) queryParams.append('offset', String(params.offset))

    const query = queryParams.toString()
    const response = await client.get<ProviderSettingsListResponse>(
      `${PROVIDERS_BASE}${query ? `?${query}` : ''}`
    )
    return transformKeys<ProviderSettingsListResponse>(response)
  },

  /**
   * GET /api/v1/communications/providers/{provider_id}
   * Get provider by ID
   */
  get: async (providerId: number): Promise<ProviderSettingsResponse> => {
    const response = await client.get<ProviderSettingsResponse>(
      `${PROVIDERS_BASE}/${providerId}`
    )
    return transformKeys<ProviderSettingsResponse>(response)
  },

  /**
   * GET /api/v1/communications/providers/code/{provider_code}
   * Get provider by code
   */
  getByCode: async (providerCode: string): Promise<ProviderSettingsResponse> => {
    const response = await client.get<ProviderSettingsResponse>(
      `${PROVIDERS_BASE}/code/${providerCode}`
    )
    return transformKeys<ProviderSettingsResponse>(response)
  },

  /**
   * GET /api/v1/communications/providers/default/{provider_type}
   * Get default provider for type
   */
  getDefault: async (providerType: CommunicationProviderType): Promise<ProviderSettingsResponse | null> => {
    try {
      const response = await client.get<ProviderSettingsResponse>(
        `${PROVIDERS_BASE}/default/${providerType}`
      )
      return transformKeys<ProviderSettingsResponse>(response)
    } catch {
      return null
    }
  },

  /**
   * POST /api/v1/communications/providers
   * Create new provider configuration
   */
  create: async (data: ProviderSettingsCreate): Promise<ProviderSettingsResponse> => {
    const response = await client.post<ProviderSettingsResponse>(
      PROVIDERS_BASE,
      toSnakeCase(data)
    )
    return transformKeys<ProviderSettingsResponse>(response)
  },

  /**
   * PUT /api/v1/communications/providers/{provider_id}
   * Update provider configuration
   */
  update: async (
    providerId: number,
    data: ProviderSettingsUpdate
  ): Promise<ProviderSettingsResponse> => {
    const response = await client.put<ProviderSettingsResponse>(
      `${PROVIDERS_BASE}/${providerId}`,
      toSnakeCase(data)
    )
    return transformKeys<ProviderSettingsResponse>(response)
  },

  /**
   * DELETE /api/v1/communications/providers/{provider_id}
   * Delete provider configuration
   */
  delete: async (providerId: number): Promise<void> => {
    await client.delete<void>(`${PROVIDERS_BASE}/${providerId}`)
  },

  /**
   * POST /api/v1/communications/providers/test
   * Test provider connection
   */
  test: async (request: ProviderTestRequest): Promise<ProviderTestResponse> => {
    const response = await client.post<ProviderTestResponse>(
      `${PROVIDERS_BASE}/test`,
      toSnakeCase(request)
    )
    return transformKeys<ProviderTestResponse>(response)
  },
}

// =============================================================================
// EXPORTS
// =============================================================================

export default {
  emailTemplates: emailTemplatesApi,
  pushTemplates: pushTemplatesApi,
  webhooks: webhooksApi,
  smsTemplates: smsTemplatesApi,
  ussd: ussdApi,
  providers: providerSettingsApi,
}
