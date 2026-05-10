/**
 * useChat Hook
 * Core state management for chatbot conversations
 *
 * @module chatbot/hooks
 * @author Claude Code
 * @date 2025-11-26
 *
 * Features:
 * - Message history management
 * - Conversation persistence
 * - API integration with error handling
 * - Suggestions and related services
 * - localStorage persistence
 * - Auto-retry on failure
 */

'use client'

import { useState, useEffect, useCallback, useRef, useMemo } from 'react'
import { chatbotApi } from '../services/api'
import { getAuthData } from '@/core/auth/storage'
import { MessageRole } from '../types'
import type {
  ChatAction,
  ChatMessage,
  ChatRequest,
  ChatResponse,
  ServiceReference,
  LanguageCode,
} from '../types'

// =============================================================================
// TYPES
// =============================================================================

export interface UseChatOptions {
  conversationId?: string
  language?: LanguageCode | 'es' | 'fr' | 'en'
  persistToStorage?: boolean
  autoLoadHistory?: boolean
  enableStreaming?: boolean
  onError?: (error: Error) => void
  onSuccess?: (response: ChatResponse) => void
  onStreamChunk?: (chunk: string) => void
}

export interface UseChatReturn {
  // State
  messages: ChatMessage[]
  conversationId: string | null
  isLoading: boolean
  isStreaming: boolean
  streamedText: string
  error: string | null
  suggestions: string[]
  relatedServices: ServiceReference[]
  confidence: number | null
  statusText: string | null
  statusStep: string | null

  // Actions
  sendMessage: (message: string, context?: Record<string, any>) => Promise<void>
  /**
   * Push an assistant message directly into the conversation without
   * round-tripping through Gemini. Used by out-of-band flows like the
   * Level 3 executive confirmation modal, where the tool result comes
   * from a dedicated endpoint and the user should see it in the chat
   * without paying for another LLM call.
   */
  pushAssistantMessage: (content: string, actions?: ChatAction[]) => void
  clearChat: () => void
  retry: () => Promise<void>
  loadHistory: (conversationId: string) => Promise<void>
  setLanguage: (language: LanguageCode) => void
  stopStreaming: () => void
}

// =============================================================================
// STORAGE KEYS - User-specific to prevent conversation sharing
// =============================================================================

/**
 * Generate user-specific storage keys to isolate conversations
 * @param userId - User ID or 'guest' for anonymous users
 */
const getStorageKeys = (userId: string) => ({
  MESSAGES: `chatbot_messages_${userId}`,
  CONVERSATION_ID: `chatbot_conversation_id_${userId}`,
  LANGUAGE: `chatbot_language_${userId}`,
} as const)

// =============================================================================
// HOOK
// =============================================================================

export function useChat(options: UseChatOptions = {}): UseChatReturn {
  const {
    conversationId: initialConversationId,
    language: initialLanguage = 'es',
    persistToStorage = true,
    autoLoadHistory = true,
    enableStreaming = false,
    onError,
    onSuccess,
    onStreamChunk,
  } = options

  // Get current user ID for storage isolation
  // Re-evaluate on every render to detect session expiry (token cleared)
  const userId = (() => {
    if (typeof window === 'undefined') return 'guest'
    const authData = getAuthData()
    // Only use authenticated ID if token is still present
    const token = authData?.access_token
    if (token && authData?.user?.id) return authData.user.id
    return 'guest'
  })()

  // User-specific storage keys
  const STORAGE_KEYS = useMemo(() => getStorageKeys(userId), [userId])

  // State
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [conversationId, setConversationId] = useState<string | null>(
    initialConversationId || null
  )
  const [language, setLanguage] = useState<LanguageCode>(initialLanguage)
  const [isLoading, setIsLoading] = useState(false)
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamedText, setStreamedText] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [suggestions, setSuggestions] = useState<string[]>([])
  const [relatedServices, setRelatedServices] = useState<ServiceReference[]>([])
  const [confidence, setConfidence] = useState<number | null>(null)
  const [lastRequest, setLastRequest] = useState<ChatRequest | null>(null)
  const [statusText, setStatusText] = useState<string | null>(null)
  const [statusStep, setStatusStep] = useState<string | null>(null)
  const statusTimersRef = useRef<ReturnType<typeof setTimeout>[]>([])

  // Refs for streaming control
  const abortControllerRef = useRef<AbortController | null>(null)

  // =============================================================================
  // STORAGE HELPERS
  // =============================================================================

  const saveToStorage = useCallback(() => {
    if (!persistToStorage || typeof window === 'undefined') return

    try {
      localStorage.setItem(STORAGE_KEYS.MESSAGES, JSON.stringify(messages))
      if (conversationId) {
        localStorage.setItem(STORAGE_KEYS.CONVERSATION_ID, conversationId)
      }
      localStorage.setItem(STORAGE_KEYS.LANGUAGE, language)
    } catch (err) {
      console.error('Failed to save to storage:', err)
    }
  }, [messages, conversationId, language, persistToStorage, STORAGE_KEYS])

  const loadFromStorage = useCallback(() => {
    if (!persistToStorage || typeof window === 'undefined') return

    try {
      const storedMessages = localStorage.getItem(STORAGE_KEYS.MESSAGES)
      const storedConversationId = localStorage.getItem(STORAGE_KEYS.CONVERSATION_ID)
      const storedLanguage = localStorage.getItem(STORAGE_KEYS.LANGUAGE)

      if (storedMessages) {
        setMessages(JSON.parse(storedMessages))
      }
      if (storedConversationId) {
        setConversationId(storedConversationId)
      }
      if (storedLanguage) {
        setLanguage(storedLanguage as LanguageCode)
      }
    } catch (err) {
      console.error('Failed to load from storage:', err)
    }
  }, [persistToStorage, STORAGE_KEYS])

  const clearStorage = useCallback(() => {
    if (typeof window === 'undefined') return

    try {
      localStorage.removeItem(STORAGE_KEYS.MESSAGES)
      localStorage.removeItem(STORAGE_KEYS.CONVERSATION_ID)
    } catch (err) {
      console.error('Failed to clear storage:', err)
    }
  }, [STORAGE_KEYS])

  // =============================================================================
  // EFFECTS
  // =============================================================================

  // Load history on mount
  useEffect(() => {
    if (autoLoadHistory) {
      loadFromStorage()
    }
  }, [autoLoadHistory, loadFromStorage])

  // Save to storage when messages change
  useEffect(() => {
    if (messages.length > 0) {
      saveToStorage()
    }
  }, [messages, saveToStorage])

  // =============================================================================
  // ACTIONS
  // =============================================================================

  /**
   * Stop streaming
   */
  const stopStreaming = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
    }
    setIsStreaming(false)
  }, [])

  /**
   * Send a message using streaming API
   */
  const sendMessageStreaming = useCallback(
    async (message: string) => {
      setIsStreaming(true)
      setStreamedText('')

      // Add user message
      const userMessage: ChatMessage = {
        role: 'user' as MessageRole,
        content: message,
        timestamp: new Date().toISOString(),
      }
      setMessages((prev) => [...prev, userMessage])

      abortControllerRef.current = new AbortController()

      try {
        let fullText = ''

        for await (const chunk of chatbotApi.chatStream(
          message,
          conversationId || undefined,
          language
        )) {
          if (chunk.type === 'chunk' && chunk.text) {
            fullText += chunk.text
            setStreamedText(fullText)
            if (onStreamChunk) {
              onStreamChunk(chunk.text)
            }
          }

          if (chunk.type === 'done') {
            // Add final assistant message
            const assistantMessage: ChatMessage = {
              role: 'assistant' as MessageRole,
              content: fullText,
              timestamp: new Date().toISOString(),
            }
            setMessages((prev) => [...prev, assistantMessage])
            break
          }

          if (chunk.type === 'error') {
            throw new Error(chunk.message || 'Stream error')
          }
        }
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Stream error'
        setError(errorMessage)
        if (onError) {
          onError(err instanceof Error ? err : new Error(errorMessage))
        }
      } finally {
        setIsStreaming(false)
        setStreamedText('')
        abortControllerRef.current = null
      }
    },
    [conversationId, language, onError, onStreamChunk]
  )

  /**
   * Send a message to the chatbot (standard API or streaming)
   */
  const sendMessage = useCallback(
    async (message: string, context?: Record<string, any>) => {
      if (!message.trim()) return

      // Use streaming if enabled
      if (enableStreaming) {
        await sendMessageStreaming(message)
        return
      }

      setIsLoading(true)
      setError(null)

      // Progressive status indicators (simulated for non-streaming)
      const statusMessages = language === 'fr'
        ? [
            { step: 'searching', text: 'Recherche dans les documents...' },
            { step: 'analyzing', text: 'Analyse des résultats...' },
            { step: 'generating', text: 'Préparation de la réponse...' },
          ]
        : language === 'en'
        ? [
            { step: 'searching', text: 'Searching documents...' },
            { step: 'analyzing', text: 'Analyzing results...' },
            { step: 'generating', text: 'Preparing response...' },
          ]
        : [
            { step: 'searching', text: 'Buscando en documentos...' },
            { step: 'analyzing', text: 'Analizando resultados...' },
            { step: 'generating', text: 'Preparando respuesta...' },
          ]

      // Clear previous timers
      statusTimersRef.current.forEach(clearTimeout)
      statusTimersRef.current = []

      // Set status messages progressively
      setStatusText(statusMessages[0].text)
      setStatusStep(statusMessages[0].step)
      statusTimersRef.current.push(
        setTimeout(() => { setStatusText(statusMessages[1].text); setStatusStep(statusMessages[1].step) }, 1500),
        setTimeout(() => { setStatusText(statusMessages[2].text); setStatusStep(statusMessages[2].step) }, 4000),
      )

      // Add user message immediately
      const userMessage: ChatMessage = {
        role: 'user' as MessageRole,
        content: message,
        timestamp: new Date().toISOString(),
      }

      setMessages((prev) => [...prev, userMessage])

      // Build history from current messages (excluding the just-added user message)
      const currentMessages = [...messages, userMessage]
      const history = currentMessages
        .filter(msg => msg.role === 'user' || msg.role === 'assistant')
        .slice(-10)  // Limit to last 10 messages for context
        .map(msg => ({
          role: msg.role as 'user' | 'assistant',
          content: msg.content,
        }))

      // Prepare request with conversation history
      const request: ChatRequest = {
        message,
        conversationId: conversationId || undefined,
        language,
        context,
        history: history.length > 1 ? history.slice(0, -1) : undefined,  // Exclude current message
      }

      setLastRequest(request)

      try {
        const response = await chatbotApi.chat(request)

        // Add assistant message with action buttons if available
        const assistantMessage: ChatMessage = {
          role: 'assistant' as MessageRole,
          content: response.response,
          timestamp: response.timestamp || new Date().toISOString(),
          actions: (response as unknown as Record<string, unknown>).actions as ChatMessage['actions'],
        }

        setMessages((prev) => [...prev, assistantMessage])
        setConversationId(response.conversationId)
        setSuggestions(response.suggestions || [])
        setRelatedServices(response.relatedServices || [])
        setConfidence(response.confidence)

        if (onSuccess) {
          onSuccess(response)
        }
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Unknown error occurred'
        setError(errorMessage)

        if (onError) {
          onError(err instanceof Error ? err : new Error(errorMessage))
        }

        // Add error message to chat
        const errorChatMessage: ChatMessage = {
          role: 'assistant' as MessageRole,
          content: `Error: ${errorMessage}`,
          timestamp: new Date().toISOString(),
        }

        setMessages((prev) => [...prev, errorChatMessage])
      } finally {
        setIsLoading(false)
        // Clear status indicators
        statusTimersRef.current.forEach(clearTimeout)
        statusTimersRef.current = []
        setStatusText(null)
        setStatusStep(null)
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps -- messages is intentionally omitted to prevent re-creating callback on every message
    [conversationId, language, onError, onSuccess, enableStreaming, sendMessageStreaming]
  )

  /**
   * Push an assistant message directly into the conversation. Used by the
   * Level 3 executive confirmation flow which calls a dedicated endpoint
   * (POST /chatbot/execute-confirmed) and wants to surface the result in
   * the chat without re-invoking Gemini.
   */
  const pushAssistantMessage = useCallback(
    (content: string, actions?: ChatAction[]) => {
      const assistantMessage: ChatMessage = {
        role: MessageRole.ASSISTANT,
        content,
        timestamp: new Date().toISOString(),
        ...(actions && actions.length > 0 ? { actions } : {}),
      }
      setMessages((prev) => [...prev, assistantMessage])
    },
    [],
  )

  /**
   * Clear the entire chat
   */
  const clearChat = useCallback(() => {
    stopStreaming()
    setMessages([])
    setConversationId(null)
    setSuggestions([])
    setRelatedServices([])
    setConfidence(null)
    setError(null)
    setLastRequest(null)
    setStreamedText('')
    clearStorage()
  }, [clearStorage, stopStreaming])

  /**
   * Retry the last failed request
   */
  const retry = useCallback(async () => {
    if (!lastRequest) {
      setError('No previous request to retry')
      return
    }

    // Remove the last error message
    setMessages((prev) => prev.slice(0, -1))

    // Retry with the same request
    await sendMessage(lastRequest.message, lastRequest.context)
  }, [lastRequest, sendMessage])

  /**
   * Load conversation history
   */
  const loadHistory = useCallback(async (newConversationId: string) => {
    setConversationId(newConversationId)

    // Try to load from backend first (persisted across devices)
    try {
      const { chatbotApi } = await import('../services/api')
      const result = await chatbotApi.getConversationHistory(newConversationId)
      if (result.found && result.messages.length > 0) {
        const chatMessages: ChatMessage[] = result.messages.map((msg) => ({
          role: msg.role as MessageRole,
          content: msg.content,
          timestamp: new Date().toISOString(),
        }))
        setMessages(chatMessages)
        console.info(`[useChat] Loaded ${result.messages.length} messages from backend`)
        return
      }
    } catch {
      // Backend unavailable — fall back to localStorage
      console.warn('[useChat] Failed to load from backend, falling back to localStorage')
    }

    // Fallback: load from localStorage
    loadFromStorage()
  }, [loadFromStorage])

  /**
   * Change language
   */
  const changeLanguage = useCallback((newLanguage: LanguageCode) => {
    setLanguage(newLanguage)
  }, [])

  // =============================================================================
  // RETURN
  // =============================================================================

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopStreaming()
      // Clean up status timers to prevent state updates on unmounted component
      statusTimersRef.current.forEach(clearTimeout)
      statusTimersRef.current = []
    }
  }, [stopStreaming])

  return {
    // State
    messages,
    conversationId,
    isLoading,
    isStreaming,
    streamedText,
    error,
    suggestions,
    relatedServices,
    confidence,
    statusText,
    statusStep,

    // Actions
    sendMessage,
    pushAssistantMessage,
    clearChat,
    retry,
    loadHistory,
    setLanguage: changeLanguage,
    stopStreaming,
  }
}

export default useChat
