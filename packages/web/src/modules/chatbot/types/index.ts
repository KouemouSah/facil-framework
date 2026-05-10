/**
 * Chatbot Types - 100% Aligned with Backend Pydantic Models
 *
 * Backend Reference: packages/backend/app/modules/chatbot/models/chatbot.py
 *
 * @module types/chatbot
 * @author Claude Code
 * @date 2025-11-26
 *
 * BACKEND ALIGNMENT: Complete RAG-powered AI chatbot
 * - Gemini AI + pgvector semantic search
 * - Real-time streaming (SSE)
 * - Multilingual support (ES/FR/EN)
 * - Service recommendations with citations
 */

// =============================================================================
// ENUMS - Aligned with Backend Exact Values
// =============================================================================

export type LanguageCode = 'es' | 'fr' | 'en'

// Legacy enum values for backward compatibility
export const LanguageCodeValues = {
  SPANISH: 'es' as const,
  FRENCH: 'fr' as const,
  ENGLISH: 'en' as const,
}

export enum MessageRole {
  USER = 'user',
  ASSISTANT = 'assistant',
  SYSTEM = 'system',
}

export enum AnalysisType {
  GENERAL = 'general',
  FISCAL = 'fiscal',
  LEGAL = 'legal',
  IDENTITY = 'identity',
}

export enum ConversationStatus {
  ACTIVE = 'active',
  ARCHIVED = 'archived',
  DELETED = 'deleted',
}

// =============================================================================
// CHAT TYPES - Core Messaging
// =============================================================================

export interface ChatMessage {
  role: MessageRole
  content: string
  timestamp: string
  actions?: ChatAction[]
}

export interface ConversationContext {
  userId?: string
  userRole?: string
  language: LanguageCode
  conversationId?: string
  additionalContext?: Record<string, any>
}

export interface ChatHistoryMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface ChatRequest {
  message: string
  conversationId?: string
  language: LanguageCode
  context?: Record<string, any>
  history?: ChatHistoryMessage[]
}

export interface ServiceReference {
  serviceCode: string
  name: string
  category?: string
  similarity?: number
  ministryCode?: string
  sectorCode?: string
}

export interface ChatResponse {
  response: string
  conversationId: string
  suggestions: string[]
  relatedServices: ServiceReference[]
  followUpActions: string[]
  confidence: number
  responseTime: number
  language: LanguageCode
  timestamp: string
  sources?: string[]  // Service codes cited in response
  model?: string      // Model used (e.g., "gemini-1.5-flash")
}

// =============================================================================
// CONVERSATION HISTORY - Persistence
// =============================================================================

export interface Conversation {
  id: string
  userId?: string
  title: string
  language: LanguageCode
  status: ConversationStatus
  messages: ChatMessage[]
  createdAt: string
  updatedAt: string
  metadata?: Record<string, any>
}

export interface ConversationCreate {
  title: string
  language: LanguageCode
  initialMessage?: string
}

export interface ConversationUpdate {
  title?: string
  status?: ConversationStatus
  metadata?: Record<string, any>
}

export interface ConversationListResponse {
  conversations: Conversation[]
  total: number
  page: number
  pageSize: number
}

// =============================================================================
// SEARCH TYPES - AI-Powered Semantic Search
// =============================================================================

export interface AISearchRequest {
  query: string
  language: LanguageCode
  filters?: {
    ministryId?: number
    sectorId?: number
    categoryId?: number
    serviceType?: string
  }
  limit?: number
}

export interface SemanticMatch {
  serviceCode: string
  serviceName: string
  similarity: number
  category?: string
  description?: string
}

export interface AISearchResponse {
  results: any[]
  total: number
  queryUnderstanding: string
  searchIntent?: string
  suggestions: string[]
  relatedTopics: string[]
  semanticMatches: SemanticMatch[]
  language: LanguageCode
  responseTime: number
}

// =============================================================================
// RECOMMENDATION TYPES - Intelligent Suggestions
// =============================================================================

export interface RecommendationRequest {
  userIntent: string
  context?: Record<string, any>
  language: LanguageCode
}

export interface RecommendationResponse {
  recommendations: any[]
  explanation: string
  confidenceScores: Record<string, number>
  alternativeOptions: any[]
  estimatedCost?: Record<string, any>
  estimatedTime?: Record<string, any>
  requiredDocuments: string[]
  nextSteps: string[]
  language: LanguageCode
}

// =============================================================================
// DOCUMENT ANALYSIS TYPES - AI Document Processing
// =============================================================================

export interface DocumentAnalysisRequest {
  documentType: string
  documentData: string | File
  analysisType: AnalysisType
  language: LanguageCode
}

export interface DocumentAnalysisResponse {
  analysisType: AnalysisType
  extractedData: Record<string, any>
  identifiedServices: any[]
  recommendations: string[]
  warnings: string[]
  confidence: number
  language: LanguageCode
}

// =============================================================================
// TRANSLATION TYPES - Multilingual Support
// =============================================================================

export interface TranslationRequest {
  text: string
  sourceLang: LanguageCode
  targetLang: LanguageCode
}

export interface TranslationResponse {
  originalText: string
  translatedText: string
  sourceLang: LanguageCode
  targetLang: LanguageCode
  confidence: number
}

// =============================================================================
// GUIDANCE TYPES - Step-by-Step Assistance
// =============================================================================

export interface GuidanceRequest {
  serviceId?: string
  processType: string
  language: LanguageCode
  currentStep?: number
}

export interface GuidanceResponse {
  steps: Array<{
    stepNumber?: number
    title?: string
    description?: string
    estimatedTime?: string
    requiredDocuments?: string[]
    tips?: string[]
    [key: string]: any
  }>
  currentStep: number
  totalSteps: number
  estimatedTime?: Record<string, any>
  requiredDocuments: string[]
  tips: string[]
  commonIssues: string[]
  nextActions: string[]
  helpResources: Array<Record<string, any>>
  language: LanguageCode
}

// =============================================================================
// VALIDATION TYPES - Form Validation
// =============================================================================

export interface ValidationRequest {
  formType: string
  formData: Record<string, any>
  language: LanguageCode
}

export interface ValidationResponse {
  isValid: boolean
  errors: Array<{
    field: string
    message: string
    severity: 'error' | 'warning' | 'info'
  }>
  suggestions: string[]
  correctedData?: Record<string, any>
  language: LanguageCode
}

// =============================================================================
// STREAMING TYPES - Real-Time Responses
// =============================================================================

export interface StreamChunk {
  type: 'chunk' | 'done' | 'error' | 'status'
  text?: string
  sources?: string[]
  totalLength?: number
  message?: string
  step?: string  // 'searching' | 'analyzing' | 'generating'
}

export interface ChatAction {
  type:
    | 'start_workflow'
    | 'open_wizard'
    | 'open_settings'
    | 'view_pricing'
    | 'view_documents'
    | 'appointment_booked'
    | 'confirm_executive'
  /** Legacy Spanish label kept as fallback when label_key is absent. */
  label: string
  /**
   * i18n key resolved by the frontend (e.g. "chatbot.actions.activatePermission").
   * When present, the frontend translates it using `label_params`; otherwise
   * it falls back to the literal `label` string above.
   */
  label_key?: string
  /** Parameters injected into the translated string (ICU placeholders). */
  label_params?: Record<string, string | number>
  url?: string
  workflow_code?: string
  permission_type?: string
  /** Phase 5 — executive tool confirmation payload. */
  confirmation_code?: string
  summary?: string
  tool_name?: string
}

// =============================================================================
// FEEDBACK TYPES - User Feedback
// =============================================================================

export interface FeedbackSubmission {
  conversationId: string
  rating: number  // 1-5
  feedback?: string
  timestamp?: string
}

export interface FeedbackResponse {
  status: string
  message: string
}

// =============================================================================
// STATISTICS TYPES - Admin Analytics
// =============================================================================

export interface ChatbotStats {
  totalConversations: number
  totalMessages: number
  averageResponseTime: number
  satisfactionRating: number
  topQueries: Array<{ query: string; count: number }>
  languageDistribution: Record<LanguageCode, number>
  servicesRecommended: Array<{ serviceCode: string; count: number }>
}

// =============================================================================
// UI STATE TYPES - Frontend State Management
// =============================================================================

export interface ChatState {
  messages: ChatMessage[]
  conversationId: string | null
  isLoading: boolean
  isStreaming: boolean
  error: string | null
  suggestions: string[]
  relatedServices: ServiceReference[]
  currentChunk: string
}

export interface ChatSettings {
  language: SupportedLanguage
  enableSuggestions: boolean
  enableRelatedServices: boolean
  enableSources: boolean
  theme: 'light' | 'dark'
  enableSound: boolean
  enableNotifications: boolean
}

/**
 * Supported language codes
 */
export type SupportedLanguage = 'es' | 'fr' | 'en'

export interface ChatWidgetProps {
  initialLanguage?: LanguageCode
  position?: 'bottom-right' | 'bottom-left' | 'top-right' | 'top-left'
  theme?: 'light' | 'dark'
  enableHistory?: boolean
  enableStreaming?: boolean
  maxHeight?: string
  onClose?: () => void
}

// =============================================================================
// HELPER FUNCTIONS
// =============================================================================

/**
 * Convert snake_case to camelCase
 */
export function toCamelCase(obj: unknown): unknown {
  if (Array.isArray(obj)) {
    return obj.map(v => toCamelCase(v))
  } else if (obj !== null && typeof obj === 'object' && (obj as object).constructor === Object) {
    return Object.keys(obj as Record<string, unknown>).reduce((result, key) => {
      const camelKey = key.replace(/_([a-z])/g, (g) => g[1].toUpperCase())
      result[camelKey] = toCamelCase((obj as Record<string, unknown>)[key])
      return result
    }, {} as Record<string, unknown>)
  }
  return obj
}

/**
 * Convert camelCase to snake_case
 */
export function toSnakeCase(obj: unknown): unknown {
  if (Array.isArray(obj)) {
    return obj.map(v => toSnakeCase(v))
  } else if (obj !== null && typeof obj === 'object' && (obj as object).constructor === Object) {
    return Object.keys(obj as Record<string, unknown>).reduce((result, key) => {
      const snakeKey = key.replace(/([A-Z])/g, '_$1').toLowerCase()
      result[snakeKey] = toSnakeCase((obj as Record<string, unknown>)[key])
      return result
    }, {} as Record<string, unknown>)
  }
  return obj
}

/**
 * Type guard: Check if message is from user
 */
export function isUserMessage(message: ChatMessage): boolean {
  return message.role === MessageRole.USER
}

/**
 * Type guard: Check if message is from assistant
 */
export function isAssistantMessage(message: ChatMessage): boolean {
  return message.role === MessageRole.ASSISTANT
}

/**
 * Generate conversation ID
 */
export function generateConversationId(): string {
  return `conv_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
}

/**
 * Format timestamp for display
 */
export function formatTimestamp(timestamp: string, locale: string = 'es'): string {
  const date = new Date(timestamp)
  return new Intl.DateTimeFormat(locale, {
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}
