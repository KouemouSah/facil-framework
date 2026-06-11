/**
 * Chatbot API Service
 * Handles all API calls for RAG-powered AI chatbot
 *
 * @module chatbot/services
 * @author Claude Code
 * @date 2025-11-26
 *
 * BACKEND ALIGNMENT: Phase Chatbot
 * Base URL: /api/v1/chatbot
 * Backend: packages/backend/app/modules/chatbot/api/chatbot_routes.py
 *
 * Features:
 * - Interactive chat with Gemini AI
 * - Real-time streaming (SSE)
 * - Semantic search over fiscal services
 * - Service recommendations
 * - Feedback system
 */

import type {
  ChatRequest,
  ChatResponse,
  AISearchRequest,
  AISearchResponse,
  RecommendationRequest,
  RecommendationResponse,
  GuidanceRequest,
  GuidanceResponse,
  FeedbackSubmission,
  FeedbackResponse,
  ChatbotStats,
  StreamChunk,
  LanguageCode,
} from '../types'
import { getAuthData } from '@/core/auth/storage'

// =============================================================================
// CONFIGURATION
// =============================================================================

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const API_VERSION = '/api/v1'
const CHATBOT_BASE = '/chatbot'

// =============================================================================
// HTTP CLIENT
// =============================================================================

class ChatbotApiClient {
  private baseUrl: string

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl
  }

  /**
   * Get auth token from storage
   */
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
      const headersToMerge = options.headers instanceof Headers
        ? Object.fromEntries(options.headers.entries())
        : Array.isArray(options.headers)
        ? Object.fromEntries(options.headers)
        : options.headers
      Object.assign(headers, headersToMerge)
    }

    try {
      // Timeout: 60s for tool-heavy requests (auto_prepare_wizard can be slow)
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 60_000)

      const response = await fetch(url, {
        ...options,
        headers,
        signal: controller.signal,
      })

      clearTimeout(timeoutId)

      if (!response.ok) {
        const error = await response.json().catch(() => ({
          message: `HTTP error! status: ${response.status}`,
        }))
        throw new Error(error.message || error.detail || `HTTP error! status: ${response.status}`)
      }

      return response.json()
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') {
        throw new Error('La solicitud ha tardado demasiado. Intente de nuevo.')
      }
      if (error instanceof TypeError && error.message === 'Failed to fetch') {
        throw new Error('Error de conexión. Verifique su conexión a internet e intente de nuevo.')
      }
      if (error instanceof Error) {
        throw error
      }
      throw new Error('Unknown error occurred')
    }
  }

  async get<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: 'GET' })
  }

  async post<T>(endpoint: string, data?: any): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
    })
  }
}

const client = new ChatbotApiClient(`${API_BASE_URL}${API_VERSION}${CHATBOT_BASE}`)

// =============================================================================
// CHATBOT API
// =============================================================================

export const chatbotApi = {
  /**
   * POST /api/v1/chatbot/execute-confirmed
   * Redeem a Level 3 executive confirmation code and run the tool
   * directly (bypasses Gemini). Returns the tool's result envelope.
   */
  executeConfirmed: async (
    confirmationCode: string,
    locale: string = 'es',
  ): Promise<{
    status: string
    tool_name: string
    result: Record<string, unknown>
  }> => {
    return client.post('/execute-confirmed', {
      confirmation_code: confirmationCode,
      locale,
    })
  },

  /**
   * GET /api/v1/chatbot/conversations/{conversationId}
   * Load conversation history from database (persisted across sessions)
   */
  getConversationHistory: async (conversationId: string): Promise<{
    messages: Array<{ role: string; content: string }>
    conversation_id: string
    language?: string
    message_count?: number
    found: boolean
  }> => {
    return client.get(`/conversations/${conversationId}`)
  },

  /**
   * POST /api/v1/chatbot/chat
   * Interactive chat with RAG support
   */
  chat: async (request: ChatRequest): Promise<ChatResponse> => {
    // Convert camelCase to snake_case for backend
    const backendRequest = {
      message: request.message,
      conversation_id: request.conversationId,
      language: request.language,
      context: request.context,
      // Include conversation history for context continuity
      history: request.history?.map(msg => ({
        role: msg.role,
        content: msg.content,
      })),
    }

    const response = await client.post<any>('/chat', backendRequest)

    // Convert snake_case response to camelCase
    return {
      response: response.response,
      conversationId: response.conversation_id,
      suggestions: response.suggestions || [],
      relatedServices: (response.related_services || []).map((service: any) => ({
        serviceCode: service.service_code,
        name: service.name,
        category: service.category,
        similarity: service.similarity,
        ministryCode: service.ministry_code,
        sectorCode: service.sector_code,
      })),
      followUpActions: response.follow_up_actions || [],
      confidence: response.confidence,
      responseTime: response.response_time,
      language: response.language,
      timestamp: response.timestamp,
      sources: response.sources,
      model: response.model,
    }
  },

  /**
   * POST /api/v1/chatbot/chat/stream
   * Streaming chat with Server-Sent Events (SSE)
   */
  chatStream: async function* (
    message: string,
    conversationId?: string,
    language: LanguageCode = 'es'
  ): AsyncGenerator<StreamChunk, void, unknown> {
    // Get token from auth storage
    const authData = typeof window !== 'undefined' ? getAuthData() : null
    const token = authData?.access_token || null

    const params = new URLSearchParams({
      message,
      language: language.toString(),
      ...(conversationId && { conversation_id: conversationId }),
    })

    const response = await fetch(
      `${API_BASE_URL}${API_VERSION}${CHATBOT_BASE}/chat/stream?${params}`,
      {
        method: 'POST',
        headers: {
          Accept: 'text/event-stream',
          ...(token && { Authorization: `Bearer ${token}` }),
        },
      }
    )

    if (!response.ok) {
      const errorText = await response.text().catch(() => response.statusText)
      throw new Error(`Stream error: ${errorText || response.statusText}`)
    }

    const reader = response.body?.getReader()
    const decoder = new TextDecoder()

    if (!reader) {
      throw new Error('No response body')
    }

    try {
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')

        // Keep the last incomplete line in buffer
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))
              yield data as StreamChunk
            } catch (e) {
              console.error('Failed to parse SSE data:', e)
            }
          }
        }
      }
    } finally {
      reader.releaseLock()
    }
  },

  /**
   * POST /api/v1/chatbot/search
   * AI-powered semantic search
   */
  search: async (request: AISearchRequest): Promise<AISearchResponse> => {
    const backendRequest = {
      query: request.query,
      language: request.language,
      filters: request.filters,
      limit: request.limit,
    }

    const response = await client.post<any>('/search', backendRequest)

    return {
      results: response.results || [],
      total: response.total,
      queryUnderstanding: response.query_understanding,
      searchIntent: response.search_intent,
      suggestions: response.suggestions || [],
      relatedTopics: response.related_topics || [],
      semanticMatches: (response.semantic_matches || []).map((match: any) => ({
        serviceCode: match.service_code,
        serviceName: match.service_name,
        similarity: match.similarity,
        category: match.category,
        description: match.description,
      })),
      language: response.language,
      responseTime: response.response_time,
    }
  },

  /**
   * POST /api/v1/chatbot/recommend
   * Get service recommendations
   */
  getRecommendations: async (
    request: RecommendationRequest
  ): Promise<RecommendationResponse> => {
    const backendRequest = {
      user_intent: request.userIntent,
      context: request.context,
      language: request.language,
    }

    const response = await client.post<any>('/recommend', backendRequest)

    return {
      recommendations: response.recommendations || [],
      explanation: response.explanation,
      confidenceScores: response.confidence_scores || {},
      alternativeOptions: response.alternative_options || [],
      estimatedCost: response.estimated_cost,
      estimatedTime: response.estimated_time,
      requiredDocuments: response.required_documents || [],
      nextSteps: response.next_steps || [],
      language: response.language,
    }
  },

  /**
   * POST /api/v1/chatbot/guide
   * Get step-by-step guidance
   */
  getGuidance: async (request: GuidanceRequest): Promise<GuidanceResponse> => {
    const backendRequest = {
      service_id: request.serviceId,
      process_type: request.processType,
      language: request.language,
      current_step: request.currentStep,
    }

    const response = await client.post<any>('/guide', backendRequest)

    return {
      steps: (response.steps || []).map((step: any) => ({
        stepNumber: step.step_number,
        title: step.title,
        description: step.description,
        estimatedTime: step.estimated_time,
        requiredDocuments: step.required_documents,
        tips: step.tips,
      })),
      currentStep: response.current_step || 1,
      totalSteps: response.total_steps || 0,
      estimatedTime: response.estimated_time,
      requiredDocuments: response.required_documents || [],
      tips: response.tips || [],
      commonIssues: response.common_issues || [],
      nextActions: response.next_actions || [],
      helpResources: response.help_resources || [],
      language: response.language,
    }
  },

  /**
   * POST /api/v1/chatbot/feedback
   * Submit user feedback
   * NOTE: Backend expects Query Parameters, not JSON body
   */
  submitFeedback: async (
    feedback: FeedbackSubmission
  ): Promise<FeedbackResponse> => {
    const params = new URLSearchParams({
      conversation_id: feedback.conversationId,
      rating: feedback.rating.toString(),
      ...(feedback.feedback && { feedback: feedback.feedback }),
    })

    const token = typeof window !== 'undefined' ? getAuthData()?.access_token : null

    const response = await fetch(
      `${API_BASE_URL}${API_VERSION}${CHATBOT_BASE}/feedback?${params}`,
      {
        method: 'POST',
        headers: {
          ...(token && { Authorization: `Bearer ${token}` }),
        },
      }
    )

    if (!response.ok) {
      throw new Error(`Feedback error: ${response.statusText}`)
    }

    return response.json()
  },

  /**
   * GET /api/v1/chatbot/stats
   * Get chatbot statistics (admin only)
   */
  getStats: async (): Promise<ChatbotStats> => {
    const response = await client.get<any>('/stats')

    return {
      totalConversations: response.total_conversations,
      totalMessages: response.total_messages,
      averageResponseTime: response.average_response_time,
      satisfactionRating: response.satisfaction_rating,
      topQueries: (response.top_queries || []).map((q: any) => ({
        query: q.query,
        count: q.count,
      })),
      languageDistribution: response.language_distribution || {},
      servicesRecommended: (response.services_recommended || []).map((s: any) => ({
        serviceCode: s.service_code,
        count: s.count,
      })),
    }
  },

  /**
   * GET /api/v1/chatbot/
   * Get API information
   */
  getInfo: async (): Promise<any> => {
    return client.get('/')
  },

  /**
   * POST /api/v1/chatbot/analyze-document
   * Analyze uploaded document using AI
   */
  analyzeDocument: async (
    file: File,
    analysisType: 'general' | 'fiscal' | 'legal' | 'identity' = 'general',
    language: LanguageCode = 'es'
  ): Promise<any> => {
    const formData = new FormData()
    formData.append('file', file)

    const params = new URLSearchParams({
      analysis_type: analysisType,
      language: language.toString(),
    })

    const token = typeof window !== 'undefined' ? getAuthData()?.access_token : null

    const response = await fetch(
      `${API_BASE_URL}${API_VERSION}${CHATBOT_BASE}/analyze-document?${params}`,
      {
        method: 'POST',
        headers: {
          ...(token && { Authorization: `Bearer ${token}` }),
        },
        body: formData,
      }
    )

    if (!response.ok) {
      throw new Error(`Document analysis error: ${response.statusText}`)
    }

    const data = await response.json()
    return {
      analysis: data.analysis,
      extractedData: data.extracted_data,
      documentType: data.document_type,
      confidence: data.confidence,
      suggestions: data.suggestions || [],
      requiredActions: data.required_actions || [],
      validationStatus: data.validation_status || {},
      language: data.language,
      fileInfo: data.file_info,
    }
  },

  /**
   * POST /api/v1/chatbot/translate
   * Translate text using AI
   */
  translate: async (
    text: string,
    sourceLanguage: LanguageCode,
    targetLanguage: LanguageCode,
    context?: string
  ): Promise<any> => {
    const backendRequest = {
      text,
      source_language: sourceLanguage,
      target_language: targetLanguage,
      context,
    }

    const response = await client.post<any>('/translate', backendRequest)

    return {
      translatedText: response.translated_text,
      sourceLanguage: response.source_language,
      targetLanguage: response.target_language,
      confidence: response.confidence,
      alternatives: response.alternatives || [],
      detectedLanguage: response.detected_language,
      translationTime: response.translation_time,
    }
  },

  /**
   * POST /api/v1/chatbot/validate
   * AI-powered form validation
   */
  validateForm: async (
    formData: Record<string, any>,
    formType: string,
    language: LanguageCode = 'es'
  ): Promise<any> => {
    const backendRequest = {
      form_data: formData,
      form_type: formType,
      language,
    }

    const response = await client.post<any>('/validate', backendRequest)

    return {
      isValid: response.is_valid,
      errors: response.errors || [],
      warnings: response.warnings || [],
      suggestions: response.suggestions || [],
      correctedData: response.corrected_data,
      completenessScore: response.completeness_score,
      requiredFields: response.required_fields || [],
      optionalImprovements: response.optional_improvements || [],
      language: response.language,
    }
  },
}

// =============================================================================
// EXPORTS
// =============================================================================

export default chatbotApi
