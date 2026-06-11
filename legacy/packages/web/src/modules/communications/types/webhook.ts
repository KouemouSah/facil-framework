/**
 * Webhook Configuration Types
 */

// =============================================================================
// ENUMS
// =============================================================================

export enum WebhookType {
  WHATSAPP = 'whatsapp',
  CUSTOM = 'custom',
}

export enum HttpMethod {
  GET = 'GET',
  POST = 'POST',
  PUT = 'PUT',
  PATCH = 'PATCH',
  DELETE = 'DELETE',
}

export enum AuthType {
  NONE = 'none',
  API_KEY = 'api_key',
  BEARER = 'bearer',
  BASIC = 'basic',
}

// =============================================================================
// INTERFACES
// =============================================================================

export interface RetryConfig {
  maxRetries: number
  retryDelaySeconds: number
}

export interface AuthConfig {
  apiKey?: string
  apiKeyHeader?: string
  bearerToken?: string
  basicUsername?: string
  basicPassword?: string
}

export interface WebhookBase {
  name: string
  webhookType: WebhookType
  endpointUrl: string
  httpMethod: HttpMethod
  headers: Record<string, string>
  authType: AuthType
  authConfig: AuthConfig
  payloadTemplate?: Record<string, unknown>
  retryConfig: RetryConfig
  timeoutSeconds: number
  events: string[]
  isActive: boolean
}

export interface WebhookCreate extends WebhookBase {}

export interface WebhookUpdate {
  name?: string
  webhookType?: WebhookType
  endpointUrl?: string
  httpMethod?: HttpMethod
  headers?: Record<string, string>
  authType?: AuthType
  authConfig?: AuthConfig
  payloadTemplate?: Record<string, unknown>
  retryConfig?: RetryConfig
  timeoutSeconds?: number
  events?: string[]
  isActive?: boolean
}

export interface WebhookResponse extends WebhookBase {
  id: number
  lastTriggeredAt?: string
  lastStatus?: string
  createdAt: string
  updatedAt?: string
  createdBy?: string  // UUID as string
}

export interface WebhookListResponse {
  webhooks: WebhookResponse[]
  total: number
  page: number
  pageSize: number
  totalPages: number
}

// =============================================================================
// WEBHOOK LOGS
// =============================================================================

export interface WebhookLog {
  id: number
  webhookId: number
  eventType: string
  requestPayload: Record<string, unknown>
  responseStatus?: number
  responseBody?: string
  durationMs?: number
  errorMessage?: string
  createdAt: string
}

export interface WebhookLogsResponse {
  logs: WebhookLog[]
  total: number
  page: number
  pageSize: number
  totalPages: number
}

// =============================================================================
// WEBHOOK TESTING
// =============================================================================

export interface WebhookTestRequest {
  testPayload?: Record<string, unknown>
}

export interface WebhookTestResponse {
  success: boolean
  statusCode?: number
  responseBody?: string
  durationMs: number
  errorMessage?: string
  requestUrl: string
  requestMethod: string
  requestHeaders: Record<string, string>
  requestPayload: Record<string, unknown>
}

// =============================================================================
// API REQUEST PARAMS
// =============================================================================

export interface WebhookListParams {
  page?: number
  pageSize?: number
  webhookType?: WebhookType
  isActive?: boolean
}

export interface WebhookLogParams {
  page?: number
  pageSize?: number
}

// =============================================================================
// FORM DATA
// =============================================================================

export interface WebhookFormData {
  name: string
  webhookType: WebhookType
  endpointUrl: string
  httpMethod: HttpMethod
  headers: Array<{ key: string; value: string }>
  authType: AuthType
  authConfig: {
    apiKey?: string
    apiKeyHeader?: string
    bearerToken?: string
    basicUsername?: string
    basicPassword?: string
  }
  payloadTemplateJson?: string
  retryConfig: {
    maxRetries: number
    retryDelaySeconds: number
  }
  timeoutSeconds: number
  events: string[]
  isActive: boolean
}
