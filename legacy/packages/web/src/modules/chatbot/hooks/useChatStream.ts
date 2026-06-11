/**
 * useChatStream Hook
 * Real-time streaming chat with Server-Sent Events (SSE)
 *
 * @module chatbot/hooks
 * @author Claude Code
 * @date 2025-11-26
 *
 * Features:
 * - Real-time streaming responses
 * - Server-Sent Events (SSE) support
 * - Chunk-by-chunk rendering
 * - Graceful error handling
 * - Abort capability
 * - Auto-retry on connection loss
 */

'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import { chatbotApi } from '../services/api'
import type {
  ChatMessage,

  LanguageCode,
  MessageRole,
} from '../types'

// =============================================================================
// TYPES
// =============================================================================

export interface UseChatStreamOptions {
  conversationId?: string
  language?: LanguageCode
  onChunk?: (chunk: string) => void
  onComplete?: (fullText: string, sources?: string[]) => void
  onError?: (error: Error) => void
  autoRetry?: boolean
  maxRetries?: number
}

export interface UseChatStreamReturn {
  // State
  messages: ChatMessage[]
  conversationId: string | null
  isStreaming: boolean
  error: string | null
  currentChunk: string
  streamedText: string
  sources: string[]
  statusText: string | null
  statusStep: string | null

  // Actions
  sendMessage: (message: string) => Promise<void>
  stopStreaming: () => void
  clearChat: () => void
  retry: () => Promise<void>
  setLanguage: (language: LanguageCode) => void
}

// =============================================================================
// HOOK
// =============================================================================

export function useChatStream(options: UseChatStreamOptions = {}): UseChatStreamReturn {
  const {
    conversationId: initialConversationId,
    language: initialLanguage = 'es',
    onChunk,
    onComplete,
    onError,
    autoRetry = false,
    maxRetries = 3,
  } = options

  // State
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [conversationId, setConversationId] = useState<string | null>(
    initialConversationId || null
  )
  const [language, setLanguage] = useState<LanguageCode>(initialLanguage)
  const [isStreaming, setIsStreaming] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [currentChunk, setCurrentChunk] = useState('')
  const [streamedText, setStreamedText] = useState('')
  const [sources, setSources] = useState<string[]>([])
  const [lastMessage, setLastMessage] = useState<string | null>(null)
  const [statusText, setStatusText] = useState<string | null>(null)
  const [statusStep, setStatusStep] = useState<string | null>(null)

  // Refs
  const abortControllerRef = useRef<AbortController | null>(null)
  const retryCountRef = useRef(0)

  // =============================================================================
  // ACTIONS
  // =============================================================================

  /**
   * Stop the current streaming
   */
  const stopStreaming = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
    }
    setIsStreaming(false)
  }, [])

  /**
   * Send a message and stream the response
   */
  const sendMessage = useCallback(
    async (message: string) => {
      if (!message.trim()) return

      // Stop any ongoing streaming
      stopStreaming()

      setIsStreaming(true)
      setError(null)
      setStreamedText('')
      setCurrentChunk('')
      setSources([])
      setLastMessage(message)

      // Add user message immediately
      const userMessage: ChatMessage = {
        role: 'user' as MessageRole,
        content: message,
        timestamp: new Date().toISOString(),
      }

      setMessages((prev) => [...prev, userMessage])

      // Create abort controller
      abortControllerRef.current = new AbortController()

      try {
        let fullText = ''
        let finalSources: string[] = []

        // Stream the response
        for await (const chunk of chatbotApi.chatStream(
          message,
          conversationId || undefined,
          language
        )) {
          // Handle status updates (searching, analyzing, generating)
          if (chunk.type === 'status') {
            setStatusText(chunk.text || null)
            setStatusStep(chunk.step || null)
            continue
          }

          // Handle chunk — clear status when text starts arriving
          if (chunk.type === 'chunk' && chunk.text) {
            if (statusText) {
              setStatusText(null)
              setStatusStep(null)
            }
            fullText += chunk.text
            setStreamedText(fullText)
            setCurrentChunk(chunk.text)

            if (onChunk) {
              onChunk(chunk.text)
            }
          }

          // Handle sources
          if (chunk.sources) {
            finalSources = chunk.sources
            setSources(chunk.sources)
          }

          // Handle completion
          if (chunk.type === 'done') {
            // Add assistant message
            const assistantMessage: ChatMessage = {
              role: 'assistant' as MessageRole,
              content: fullText,
              timestamp: new Date().toISOString(),
            }

            setMessages((prev) => [...prev, assistantMessage])

            if (onComplete) {
              onComplete(fullText, finalSources)
            }

            // Reset retry count on success
            retryCountRef.current = 0
            break
          }

          // Handle error
          if (chunk.type === 'error') {
            throw new Error(chunk.message || 'Stream error')
          }
        }
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Unknown error occurred'
        setError(errorMessage)

        if (onError) {
          onError(err instanceof Error ? err : new Error(errorMessage))
        }

        // Auto-retry logic
        if (autoRetry && retryCountRef.current < maxRetries) {
          retryCountRef.current++
          console.log(`Retrying... (${retryCountRef.current}/${maxRetries})`)

          // Wait before retrying (exponential backoff)
          const delay = Math.min(1000 * Math.pow(2, retryCountRef.current - 1), 10000)
          await new Promise(resolve => setTimeout(resolve, delay))

          // Retry
          await sendMessage(message)
          return
        }

        // Add error message to chat
        const errorChatMessage: ChatMessage = {
          role: 'assistant' as MessageRole,
          content: `Error: ${errorMessage}`,
          timestamp: new Date().toISOString(),
        }

        setMessages((prev) => [...prev, errorChatMessage])
      } finally {
        setIsStreaming(false)
        setCurrentChunk('')
        abortControllerRef.current = null
      }
    },
    [
      conversationId,
      language,
      onChunk,
      onComplete,
      onError,
      autoRetry,
      maxRetries,
      stopStreaming,
    ]
  )

  /**
   * Clear the entire chat
   */
  const clearChat = useCallback(() => {
    stopStreaming()
    setMessages([])
    setConversationId(null)
    setStreamedText('')
    setCurrentChunk('')
    setSources([])
    setError(null)
    setLastMessage(null)
    retryCountRef.current = 0
  }, [stopStreaming])

  /**
   * Retry the last failed message
   */
  const retry = useCallback(async () => {
    if (!lastMessage) {
      setError('No previous message to retry')
      return
    }

    // Remove the last error message
    setMessages((prev) => prev.slice(0, -1))

    // Reset retry count and try again
    retryCountRef.current = 0
    await sendMessage(lastMessage)
  }, [lastMessage, sendMessage])

  /**
   * Change language
   */
  const changeLanguage = useCallback((newLanguage: LanguageCode) => {
    setLanguage(newLanguage)
  }, [])

  // =============================================================================
  // EFFECTS
  // =============================================================================

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopStreaming()
    }
  }, [stopStreaming])

  // =============================================================================
  // RETURN
  // =============================================================================

  return {
    // State
    messages,
    conversationId,
    isStreaming,
    error,
    currentChunk,
    streamedText,
    sources,
    statusText,
    statusStep,

    // Actions
    sendMessage,
    stopStreaming,
    clearChat,
    retry,
    setLanguage: changeLanguage,
  }
}

export default useChatStream
