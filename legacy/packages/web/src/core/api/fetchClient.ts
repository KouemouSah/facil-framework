/**
 * Shared Fetch-based API Client
 * For modules that don't use axios
 *
 * @module core/api
 * @author Claude Code
 * @date 2025-11-26
 *
 * Features:
 * - Standardized auth token retrieval via getAuthData()
 * - Automatic Content-Type headers
 * - Error handling with proper messages
 * - Support for all HTTP methods
 * - Automatic token refresh on 401 errors
 */

import { getAuthData, setAuthData, clearAuthData } from '@/core/auth/storage'
import { appConfig } from '@/core/config/app'

// =============================================================================
// TYPES
// =============================================================================

export interface FetchClientOptions {
  baseUrl?: string
  defaultHeaders?: Record<string, string>
}

export interface RequestOptions extends Omit<RequestInit, 'body'> {
  params?: Record<string, string | number | boolean | undefined>
  body?: unknown
}

// =============================================================================
// FETCH CLIENT CLASS
// =============================================================================

export class FetchClient {
  private baseUrl: string
  private defaultHeaders: Record<string, string>
  private isRefreshing: boolean = false
  private refreshPromise: Promise<string | null> | null = null

  constructor(options: FetchClientOptions = {}) {
    this.baseUrl = options.baseUrl || `${appConfig.api.baseUrl}/api/v1`
    this.defaultHeaders = {
      'Content-Type': 'application/json',
      ...options.defaultHeaders,
    }
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
      const response = await fetch(`${this.baseUrl}/auth/refresh`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
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
    // If already refreshing, wait for the existing refresh to complete
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

  /**
   * Get auth token from storage
   */
  private getToken(): string | null {
    if (typeof window === 'undefined') return null
    const authData = getAuthData()
    return authData?.access_token || null
  }

  /**
   * Public getter for baseUrl (for multipart uploads)
   */
  public getBaseUrl(): string {
    return this.baseUrl
  }

  /**
   * Public getter for auth token (for multipart uploads)
   */
  public getAuthToken(): string | null {
    return this.getToken()
  }

  /**
   * Build URL with query parameters
   */
  private buildUrl(endpoint: string, params?: Record<string, string | number | boolean | undefined>): string {
    const url = new URL(`${this.baseUrl}${endpoint}`)

    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          url.searchParams.append(key, String(value))
        }
      })
    }

    return url.toString()
  }

  /**
   * Make a request with automatic token refresh on 401
   */
  private async request<T>(
    endpoint: string,
    options: RequestOptions = {},
    isRetry: boolean = false
  ): Promise<T> {
    const { params, body, headers: customHeaders, ...fetchOptions } = options

    const url = this.buildUrl(endpoint, params)
    const token = this.getToken()

    const headers: Record<string, string> = {
      ...this.defaultHeaders,
    }

    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }

    // Merge custom headers
    if (customHeaders) {
      const headersToMerge = customHeaders instanceof Headers
        ? Object.fromEntries(customHeaders.entries())
        : Array.isArray(customHeaders)
        ? Object.fromEntries(customHeaders)
        : customHeaders
      Object.assign(headers, headersToMerge)
    }

    try {
      const response = await fetch(url, {
        ...fetchOptions,
        headers,
        body: body ? JSON.stringify(body) : undefined,
      })

      // Handle 204 No Content
      if (response.status === 204) {
        return {} as T
      }

      // Handle 401 Unauthorized - attempt token refresh
      if (response.status === 401 && !isRetry) {
        const newToken = await this.getFreshToken()
        if (newToken) {
          // Retry the request with the new token
          return this.request<T>(endpoint, options, true)
        }
        // If refresh failed, throw the error
        throw new Error('Invalid or expired access token')
      }

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({
          detail: `HTTP ${response.status}: ${response.statusText}`,
        }))

        // Properly extract error message - handle various error formats
        let errorMessage: string
        if (typeof errorData.detail === 'string') {
          errorMessage = errorData.detail
        } else if (typeof errorData.message === 'string') {
          errorMessage = errorData.message
        } else if (Array.isArray(errorData.detail)) {
          // Handle FastAPI validation errors (array of objects)
          // Format: [{ loc: ["body", "field"], msg: "error message", type: "..." }]
          errorMessage = errorData.detail
            .map((err: { msg?: string; loc?: string[] }) => {
              const field = err.loc?.slice(1).join('.') || 'field'
              return `${field}: ${err.msg || 'validation error'}`
            })
            .join('; ')
        } else if (errorData.detail && typeof errorData.detail === 'object') {
          // Handle nested error objects
          errorMessage = errorData.detail.msg || errorData.detail.message || JSON.stringify(errorData.detail)
        } else if (errorData.error && typeof errorData.error === 'string') {
          errorMessage = errorData.error
        } else {
          errorMessage = `HTTP ${response.status}: ${response.statusText}`
        }

        throw new Error(errorMessage)
      }

      return response.json()
    } catch (error) {
      if (error instanceof Error) {
        throw error
      }
      throw new Error('Unknown error occurred')
    }
  }

  /**
   * GET request
   */
  async get<T>(endpoint: string, params?: Record<string, string | number | boolean | undefined>): Promise<T> {
    return this.request<T>(endpoint, { method: 'GET', params })
  }

  /**
   * POST request
   */
  async post<T>(endpoint: string, data?: unknown, params?: Record<string, string | number | boolean | undefined>): Promise<T> {
    return this.request<T>(endpoint, { method: 'POST', body: data, params })
  }

  /**
   * PUT request
   */
  async put<T>(endpoint: string, data?: unknown): Promise<T> {
    return this.request<T>(endpoint, { method: 'PUT', body: data })
  }

  /**
   * PATCH request
   */
  async patch<T>(endpoint: string, data?: unknown): Promise<T> {
    return this.request<T>(endpoint, { method: 'PATCH', body: data })
  }

  /**
   * DELETE request
   */
  async delete<T>(endpoint: string, params?: Record<string, string | number | boolean | undefined>): Promise<T> {
    return this.request<T>(endpoint, { method: 'DELETE', params })
  }
}

// =============================================================================
// SINGLETON INSTANCE
// =============================================================================

export const fetchClient = new FetchClient()

export default fetchClient
