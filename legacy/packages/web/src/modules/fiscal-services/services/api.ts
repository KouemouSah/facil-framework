/**
 * Fiscal Services API Service
 * Handles all API calls to fiscal services backend endpoints
 *
 * @module fiscal-services/services
 * @author Claude Code
 * @date 2025-11-25
 *
 * BACKEND ALIGNMENT: Phase 7
 * Base URL: /api/v1/fiscal-services
 * Routes: From app/modules/fiscal_services/api/fiscal_service_routes.py
 *
 * PUBLIC ENDPOINTS (12):
 * - GET    /ministries
 * - GET    /sectors?ministry_id={id}
 * - GET    /categories?sector_id={id}
 * - GET    /?page={n}&page_size={n}&category_id={id}&is_active={bool}
 * - GET    /{service_id}
 * - POST   /search
 * - GET    /popular/list?limit={n}
 * - GET    /recent/list?limit={n}
 * - POST   /calculate
 *
 * ADMIN ENDPOINTS (5):
 * - POST   /admin/services
 * - PUT    /admin/services/{service_id}
 * - DELETE /admin/services/{service_id}
 * - GET    /admin/stats
 * - POST   /admin/bulk/import
 * - POST   /admin/bulk/update-status
 */

import type {
  Ministry,
  Sector,
  Category,
  FiscalServiceResponse,
  FiscalServiceCreate,
  FiscalServiceUpdate,
  FiscalServiceListResponse,
  FiscalServiceFilter,
  FiscalServiceStats,
  CalculationInput,
  CalculationResult,
  ServiceStatusEnum,
  DocumentTemplate,
  ServiceDocumentAssignment,
  ProcedureTemplate,
  ProcedureStep,
  ServiceProcedureAssignment,
  ServiceKeyword,
  EntityTranslation,
} from '@/types/fiscal-service'
import { getAuthData, setAuthData, clearAuthData } from '@/core/auth/storage'
import { appConfig } from '@/core/config/app'

// =============================================================================
// CONFIGURATION
// =============================================================================

const API_BASE_URL = appConfig.api.baseUrl
const API_VERSION = `/api/${appConfig.api.version}`
const FISCAL_SERVICES_BASE = '/fiscal-services'

// =============================================================================
// UTILITY FUNCTIONS - snake_case to camelCase transformation
// =============================================================================

/**
 * Convert snake_case string to camelCase
 */
function snakeToCamel(str: string): string {
  return str.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase())
}

/**
 * Convert camelCase string to snake_case
 */
function camelToSnake(str: string): string {
  return str.replace(/[A-Z]/g, letter => `_${letter.toLowerCase()}`)
}

/**
 * Transform object keys from snake_case to camelCase (recursive)
 */
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

/**
 * Transform object keys from camelCase to snake_case (recursive)
 * Used for sending data to backend
 */
function toSnakeCase<T>(obj: unknown): T {
  if (obj === null || obj === undefined) return obj as T
  if (Array.isArray(obj)) return obj.map(item => toSnakeCase(item)) as T
  if (obj instanceof Date) return obj.toISOString().split('T')[0] as unknown as T
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

  /**
   * Refresh the access token using the refresh token
   */
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

      // Update stored tokens
      setAuthData({
        ...authData,
        access_token,
        refresh_token,
      })

      return access_token
    } catch {
      // Clear auth data and redirect to login with locale
      clearAuthData()
      if (typeof window !== 'undefined') {
        // Extract locale from current URL path (e.g., /es/dashboard -> es)
        const pathParts = window.location.pathname.split('/')
        const locale = pathParts[1] && ['es', 'fr', 'en'].includes(pathParts[1]) ? pathParts[1] : 'es'
        window.location.href = `/${locale}/auth`
      }
      return null
    }
  }

  /**
   * Get a fresh token, refreshing if necessary
   */
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

    const authData = typeof window !== 'undefined'
      ? getAuthData()
      : null

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

    // Handle 401 Unauthorized - attempt token refresh
    if (response.status === 401 && !isRetry) {
      const newToken = await this.getFreshToken()
      if (newToken) {
        // Retry the request with the new token
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
// HIERARCHY API
// =============================================================================

export const hierarchyApi = {
  /**
   * GET /api/v1/fiscal-services/ministries
   * List all ministries with i18n support
   */
  ministries: {
    list: async (language: string = 'es'): Promise<Ministry[]> => {
      const response = await client.get<Ministry[]>(`${FISCAL_SERVICES_BASE}/ministries?language=${language}`)
      return transformKeys<Ministry[]>(response)
    },
    get: async (ministryId: number): Promise<Ministry> => {
      const response = await client.get<Ministry>(`${FISCAL_SERVICES_BASE}/admin/ministries/${ministryId}`)
      return transformKeys<Ministry>(response)
    },
    create: async (data: Omit<Ministry, 'id' | 'created_at' | 'updated_at'>): Promise<Ministry> => {
      const response = await client.post<Ministry>(`${FISCAL_SERVICES_BASE}/admin/ministries`, toSnakeCase(data))
      return transformKeys<Ministry>(response)
    },
    update: async (ministryId: number, data: Partial<Ministry>): Promise<Ministry> => {
      const response = await client.put<Ministry>(`${FISCAL_SERVICES_BASE}/admin/ministries/${ministryId}`, toSnakeCase(data))
      return transformKeys<Ministry>(response)
    },
    delete: async (ministryId: number): Promise<void> => {
      return client.delete<void>(`${FISCAL_SERVICES_BASE}/admin/ministries/${ministryId}`)
    },
  },

  /**
   * GET /api/v1/fiscal-services/sectors?ministry_id={id}&language={lang}
   * List sectors, optionally filtered by ministry, with i18n support
   */
  sectors: {
    list: async (ministryId?: number, language: string = 'es'): Promise<Sector[]> => {
      const params = new URLSearchParams()
      params.append('language', language)
      if (ministryId) params.append('ministry_id', String(ministryId))
      const response = await client.get<Sector[]>(`${FISCAL_SERVICES_BASE}/sectors?${params.toString()}`)
      return transformKeys<Sector[]>(response)
    },
    get: async (sectorId: number): Promise<Sector> => {
      const response = await client.get<Sector>(`${FISCAL_SERVICES_BASE}/admin/sectors/${sectorId}`)
      return transformKeys<Sector>(response)
    },
    create: async (data: Omit<Sector, 'id' | 'created_at' | 'updated_at'>): Promise<Sector> => {
      const response = await client.post<Sector>(`${FISCAL_SERVICES_BASE}/admin/sectors`, toSnakeCase(data))
      return transformKeys<Sector>(response)
    },
    update: async (sectorId: number, data: Partial<Sector>): Promise<Sector> => {
      const response = await client.put<Sector>(`${FISCAL_SERVICES_BASE}/admin/sectors/${sectorId}`, toSnakeCase(data))
      return transformKeys<Sector>(response)
    },
    delete: async (sectorId: number): Promise<void> => {
      return client.delete<void>(`${FISCAL_SERVICES_BASE}/admin/sectors/${sectorId}`)
    },
  },

  /**
   * GET /api/v1/fiscal-services/categories?sector_id={id}&language={lang}
   * List categories, optionally filtered by sector, with i18n support
   */
  categories: {
    list: async (sectorId?: number, language: string = 'es'): Promise<Category[]> => {
      const params = new URLSearchParams()
      params.append('language', language)
      if (sectorId) params.append('sector_id', String(sectorId))
      const response = await client.get<Category[]>(`${FISCAL_SERVICES_BASE}/categories?${params.toString()}`)
      return transformKeys<Category[]>(response)
    },
    get: async (categoryId: number): Promise<Category> => {
      const response = await client.get<Category>(`${FISCAL_SERVICES_BASE}/admin/categories/${categoryId}`)
      return transformKeys<Category>(response)
    },
    create: async (data: Omit<Category, 'id' | 'created_at' | 'updated_at'>): Promise<Category> => {
      const response = await client.post<Category>(`${FISCAL_SERVICES_BASE}/admin/categories`, toSnakeCase(data))
      return transformKeys<Category>(response)
    },
    update: async (categoryId: number, data: Partial<Category>): Promise<Category> => {
      const response = await client.put<Category>(`${FISCAL_SERVICES_BASE}/admin/categories/${categoryId}`, toSnakeCase(data))
      return transformKeys<Category>(response)
    },
    delete: async (categoryId: number): Promise<void> => {
      return client.delete<void>(`${FISCAL_SERVICES_BASE}/admin/categories/${categoryId}`)
    },
  },
}

// =============================================================================
// FISCAL SERVICES API (PUBLIC)
// =============================================================================

export const fiscalServicesApi = {
  /**
   * GET /api/v1/fiscal-services
   * List fiscal services with pagination and filters
   */
  list: async (params?: {
    page?: number
    pageSize?: number
    categoryId?: number
    status?: string
    ministryId?: number
    sectorId?: number
    search?: string
    sortBy?: string
    sortOrder?: string
    language?: string
  }): Promise<FiscalServiceListResponse> => {
    const queryParams = new URLSearchParams()
    if (params?.page) queryParams.append('page', String(params.page))
    if (params?.pageSize) queryParams.append('page_size', String(params.pageSize))
    if (params?.categoryId) queryParams.append('category_id', String(params.categoryId))
    if (params?.status) queryParams.append('status', params.status)
    if (params?.ministryId) queryParams.append('ministry_id', String(params.ministryId))
    if (params?.sectorId) queryParams.append('sector_id', String(params.sectorId))
    if (params?.search) queryParams.append('search', params.search)
    if (params?.sortBy) queryParams.append('sort_by', params.sortBy)
    if (params?.sortOrder) queryParams.append('sort_order', params.sortOrder)
    if (params?.language) queryParams.append('language', params.language)

    const query = queryParams.toString()
    const response = await client.get<FiscalServiceListResponse>(
      `${FISCAL_SERVICES_BASE}${query ? `?${query}` : ''}`
    )
    return transformKeys<FiscalServiceListResponse>(response)
  },

  /**
   * GET /api/v1/fiscal-services/{service_id}
   * Get single fiscal service by ID
   */
  get: async (serviceId: number | string): Promise<FiscalServiceResponse> => {
    const response = await client.get<FiscalServiceResponse>(`${FISCAL_SERVICES_BASE}/${serviceId}`)
    return transformKeys<FiscalServiceResponse>(response)
  },

  /**
   * POST /api/v1/fiscal-services/search
   * Advanced search for fiscal services
   */
  search: async (
    filters: FiscalServiceFilter,
    page: number = 1,
    pageSize: number = 50
  ): Promise<FiscalServiceListResponse> => {
    const query = `?page=${page}&page_size=${pageSize}`
    const response = await client.post<FiscalServiceListResponse>(
      `${FISCAL_SERVICES_BASE}/search${query}`,
      filters
    )
    return transformKeys<FiscalServiceListResponse>(response)
  },

  /**
   * GET /api/v1/fiscal-services/popular/list?limit={n}
   * Get most used fiscal services
   */
  popular: async (limit: number = 10): Promise<FiscalServiceResponse[]> => {
    const response = await client.get<FiscalServiceResponse[]>(
      `${FISCAL_SERVICES_BASE}/popular/list?limit=${limit}`
    )
    return transformKeys<FiscalServiceResponse[]>(response)
  },

  /**
   * GET /api/v1/fiscal-services/recent/list?limit={n}
   * Get recently used fiscal services
   */
  recent: async (limit: number = 10): Promise<FiscalServiceResponse[]> => {
    const response = await client.get<FiscalServiceResponse[]>(
      `${FISCAL_SERVICES_BASE}/recent/list?limit=${limit}`
    )
    return transformKeys<FiscalServiceResponse[]>(response)
  },

  /**
   * POST /api/v1/fiscal-services/calculate
   * Calculate amount for a fiscal service
   * Auth: Required (JWT Bearer token)
   */
  calculate: async (input: CalculationInput): Promise<CalculationResult> => {
    return client.post<CalculationResult>(`${FISCAL_SERVICES_BASE}/calculate`, input)
  },
}

// =============================================================================
// FISCAL SERVICES ADMIN API
// =============================================================================

export const fiscalServicesAdminApi = {
  /**
   * POST /api/v1/fiscal-services/admin/services
   * Create new fiscal service
   * Auth: Required + Permission "fiscal_services.create"
   */
  create: async (data: FiscalServiceCreate): Promise<FiscalServiceResponse> => {
    const response = await client.post<FiscalServiceResponse>(`${FISCAL_SERVICES_BASE}/admin/services`, toSnakeCase(data))
    return transformKeys<FiscalServiceResponse>(response)
  },

  /**
   * PUT /api/v1/fiscal-services/admin/services/{service_id}
   * Update fiscal service
   * Auth: Required + Permission "fiscal_services.update"
   */
  update: async (serviceId: number | string, data: FiscalServiceUpdate): Promise<FiscalServiceResponse> => {
    const response = await client.put<FiscalServiceResponse>(
      `${FISCAL_SERVICES_BASE}/admin/services/${serviceId}`,
      toSnakeCase(data)
    )
    return transformKeys<FiscalServiceResponse>(response)
  },

  /**
   * DELETE /api/v1/fiscal-services/admin/services/{service_id}
   * Delete fiscal service
   * Auth: Required + Permission "fiscal_services.delete"
   */
  delete: async (serviceId: number | string): Promise<{ message: string }> => {
    return client.delete<{ message: string }>(
      `${FISCAL_SERVICES_BASE}/admin/services/${serviceId}`
    )
  },

  /**
   * GET /api/v1/fiscal-services/admin/stats
   * Get comprehensive statistics
   * Auth: Required + Permission "fiscal_services.view_stats"
   */
  stats: async (): Promise<FiscalServiceStats> => {
    const response = await client.get<FiscalServiceStats>(`${FISCAL_SERVICES_BASE}/admin/stats`)
    return transformKeys<FiscalServiceStats>(response)
  },

  /**
   * POST /api/v1/fiscal-services/admin/bulk/import
   * Bulk import fiscal services (max 100 per request)
   * Auth: Required + Permission "fiscal_services.bulk_import"
   */
  bulkImport: async (services: FiscalServiceCreate[]): Promise<{
    success: boolean
    totalProcessed: number
    successfulImports: number
    failedImports: number
    failedServices: Array<{ code: string; error: string }>
  }> => {
    return client.post(`${FISCAL_SERVICES_BASE}/admin/bulk/import`, services)
  },

  /**
   * POST /api/v1/fiscal-services/admin/bulk/update-status
   * Bulk update service status (max 50 per request)
   * Auth: Required + Permission "fiscal_services.bulk_update"
   */
  /**
   * GET /api/v1/fiscal-services/admin/export/csv
   * Export filtered services as CSV
   */
  exportCsv: async (params?: {
    categoryId?: number
    status?: string
    ministryId?: number
    sectorId?: number
    search?: string
  }): Promise<Blob> => {
    const queryParams = new URLSearchParams()
    if (params?.categoryId) queryParams.append('category_id', String(params.categoryId))
    if (params?.status) queryParams.append('status', params.status)
    if (params?.ministryId) queryParams.append('ministry_id', String(params.ministryId))
    if (params?.sectorId) queryParams.append('sector_id', String(params.sectorId))
    if (params?.search) queryParams.append('search', params.search)
    const query = queryParams.toString()
    const response = await fetch(
      `${typeof window !== 'undefined' ? (process.env.NEXT_PUBLIC_API_URL || '') : ''}/api/v1/fiscal-services/admin/export/csv${query ? `?${query}` : ''}`,
      {
        headers: {
          Authorization: `Bearer ${typeof window !== 'undefined' ? localStorage.getItem('access_token') || '' : ''}`,
        },
      }
    )
    if (!response.ok) throw new Error('Export failed')
    return response.blob()
  },

  bulkUpdateStatus: async (serviceIds: string[], newStatus: ServiceStatusEnum): Promise<{
    success: boolean
    totalRequested: number
    updatedCount: number
    failedUpdates: number
    newStatus: string
  }> => {
    return client.post(`${FISCAL_SERVICES_BASE}/admin/bulk/update-status`, {
      service_ids: serviceIds,
      new_status: newStatus,
    })
  },
}

// =============================================================================
// DOCUMENTS API
// =============================================================================

export const documentsApi = {
  /**
   * GET /api/v1/fiscal-services/{service_id}/documents
   * Get all document assignments for a service
   */
  list: async (serviceId: number | string): Promise<ServiceDocumentAssignment[]> => {
    const response = await client.get<ServiceDocumentAssignment[]>(
      `${FISCAL_SERVICES_BASE}/${serviceId}/documents`
    )
    return transformKeys<ServiceDocumentAssignment[]>(response)
  },

  /**
   * POST /api/v1/fiscal-services/{service_id}/documents
   * Assign a document to a service
   */
  assign: async (
    serviceId: number | string,
    data: {
      documentTemplateId: number
      isRequiredExpedition: boolean
      isRequiredRenewal: boolean
      displayOrder?: number
      customNotes?: string
    }
  ): Promise<ServiceDocumentAssignment> => {
    const response = await client.post<ServiceDocumentAssignment>(
      `${FISCAL_SERVICES_BASE}/${serviceId}/documents`,
      toSnakeCase(data)
    )
    return transformKeys<ServiceDocumentAssignment>(response)
  },

  /**
   * DELETE /api/v1/fiscal-services/{service_id}/documents/{assignment_id}
   * Remove a document assignment
   */
  unassign: async (
    serviceId: number | string,
    assignmentId: number
  ): Promise<{ message: string }> => {
    return client.delete<{ message: string }>(
      `${FISCAL_SERVICES_BASE}/${serviceId}/documents/${assignmentId}`
    )
  },

  /**
   * GET /api/v1/document-templates
   * Get all available document templates with i18n support
   * Note: Backend returns paginated response, extract templates array
   * pageSize=1000 to fetch all templates (792 documents in database)
   */
  templates: {
    list: async (language: string = 'es'): Promise<DocumentTemplate[]> => {
      const response = await client.get<{ templates: DocumentTemplate[]; total: number }>(`/document-templates?language=${language}&page_size=1000`)
      const transformed = transformKeys<{ templates: DocumentTemplate[] }>(response)
      return transformed.templates || []
    },
  },
}

// =============================================================================
// PROCEDURES API
// =============================================================================

export const proceduresApi = {
  /**
   * GET /api/v1/fiscal-services/{service_id}/procedures
   * Get all procedure assignments for a service
   */
  list: async (serviceId: number | string): Promise<ServiceProcedureAssignment[]> => {
    const response = await client.get<ServiceProcedureAssignment[]>(
      `${FISCAL_SERVICES_BASE}/${serviceId}/procedures`
    )
    return transformKeys<ServiceProcedureAssignment[]>(response)
  },

  /**
   * POST /api/v1/fiscal-services/{service_id}/procedures
   * Assign a procedure to a service
   */
  assign: async (
    serviceId: number | string,
    data: {
      templateId: number
      appliesTo?: string
      displayOrder?: number
      customNotes?: string
      overrideSteps?: Record<string, unknown>
    }
  ): Promise<ServiceProcedureAssignment> => {
    const response = await client.post<ServiceProcedureAssignment>(
      `${FISCAL_SERVICES_BASE}/${serviceId}/procedures`,
      toSnakeCase(data)
    )
    return transformKeys<ServiceProcedureAssignment>(response)
  },

  /**
   * DELETE /api/v1/fiscal-services/{service_id}/procedures/{assignment_id}
   * Remove a procedure assignment
   */
  unassign: async (
    serviceId: number | string,
    assignmentId: number
  ): Promise<{ message: string }> => {
    return client.delete<{ message: string }>(
      `${FISCAL_SERVICES_BASE}/${serviceId}/procedures/${assignmentId}`
    )
  },

  /**
   * GET /api/v1/procedure-templates
   * Get all available procedure templates with i18n support
   * Note: Backend returns paginated response, extract templates array
   * pageSize=1000 to fetch all templates (703 procedures in database)
   */
  templates: {
    list: async (language: string = 'es'): Promise<ProcedureTemplate[]> => {
      const response = await client.get<{ templates: ProcedureTemplate[]; total: number }>(`/procedure-templates?language=${language}&page_size=1000`)
      const transformed = transformKeys<{ templates: ProcedureTemplate[] }>(response)
      return transformed.templates || []
    },

    /**
     * GET /api/v1/procedure-templates/{template_id}/steps
     * Get steps for a procedure template
     */
    steps: async (templateId: number): Promise<ProcedureStep[]> => {
      const response = await client.get<ProcedureStep[]>(`/procedure-templates/${templateId}/steps`)
      return transformKeys<ProcedureStep[]>(response)
    },
  },
}

// =============================================================================
// KEYWORDS API
// =============================================================================

export const keywordsApi = {
  /**
   * GET /api/v1/fiscal-services/{service_id}/keywords
   * Get all keywords for a service
   */
  list: async (serviceId: number | string): Promise<ServiceKeyword[]> => {
    const response = await client.get<ServiceKeyword[]>(`${FISCAL_SERVICES_BASE}/${serviceId}/keywords`)
    return transformKeys<ServiceKeyword[]>(response)
  },

  /**
   * POST /api/v1/fiscal-services/{service_id}/keywords
   * Add a keyword to a service
   */
  create: async (
    serviceId: number | string,
    data: {
      keyword: string
      languageCode: string
      weight: number
    }
  ): Promise<ServiceKeyword> => {
    const response = await client.post<ServiceKeyword>(
      `${FISCAL_SERVICES_BASE}/${serviceId}/keywords`,
      toSnakeCase(data)
    )
    return transformKeys<ServiceKeyword>(response)
  },

  /**
   * DELETE /api/v1/fiscal-services/{service_id}/keywords/{keyword_id}
   * Remove a keyword
   */
  delete: async (
    serviceId: number | string,
    keywordId: number
  ): Promise<{ message: string }> => {
    return client.delete<{ message: string }>(
      `${FISCAL_SERVICES_BASE}/${serviceId}/keywords/${keywordId}`
    )
  },
}

// =============================================================================
// TRANSLATIONS API
// =============================================================================

export const translationsApi = {
  /**
   * GET /api/v1/fiscal-services/{service_id}/translations
   * Get all translations for a service
   */
  list: async (serviceId: number | string): Promise<EntityTranslation[]> => {
    const response = await client.get<EntityTranslation[]>(
      `${FISCAL_SERVICES_BASE}/${serviceId}/translations`
    )
    return transformKeys<EntityTranslation[]>(response)
  },

  /**
   * POST /api/v1/fiscal-services/{service_id}/translations
   * Add or update a translation
   */
  upsert: async (
    serviceId: number | string,
    data: {
      languageCode: string
      fieldName: string
      translationText: string
      translationSource?: string
    }
  ): Promise<EntityTranslation> => {
    const response = await client.post<EntityTranslation>(
      `${FISCAL_SERVICES_BASE}/${serviceId}/translations`,
      toSnakeCase(data)
    )
    return transformKeys<EntityTranslation>(response)
  },

  /**
   * DELETE /api/v1/fiscal-services/{service_id}/translations/{language_code}/{field_name}
   * Remove a translation
   */
  delete: async (
    serviceId: number | string,
    languageCode: string,
    fieldName: string
  ): Promise<{ message: string }> => {
    return client.delete<{ message: string }>(
      `${FISCAL_SERVICES_BASE}/${serviceId}/translations/${languageCode}/${fieldName}`
    )
  },
}

// =============================================================================
// EXPORTS
// =============================================================================

export default {
  hierarchy: hierarchyApi,
  services: fiscalServicesApi,
  admin: fiscalServicesAdminApi,
  documents: documentsApi,
  procedures: proceduresApi,
  keywords: keywordsApi,
  translations: translationsApi,
}
