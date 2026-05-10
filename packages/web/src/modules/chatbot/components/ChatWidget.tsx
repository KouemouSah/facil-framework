/**
 * ChatWidget Component - Refactored with Hooks
 * Floating AI assistant widget with full RAG support
 *
 * @module chatbot/components
 * @author Claude Code
 * @date 2025-11-26
 *
 * Features:
 * - useChat hook integration
 * - Streaming support (optional)
 * - Suggestions and related services
 * - Error handling with retry
 * - i18n support
 * - Persistent settings
 * - Floating widget pattern
 * - WCAG 2.1 AA Accessibility
 *   - ARIA labels and live regions
 *   - Keyboard navigation (Escape to close)
 *   - Focus management
 *   - Screen reader announcements
 */

'use client'

import React, { useState, useRef, useEffect, useCallback } from 'react'
import { useLocale, useTranslations } from 'next-intl'
import Image from 'next/image'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  MessageCircle,
  Send,
  X,
  Loader2,
  AlertCircle,
  RefreshCw,
  Trash2,
  Settings,
  User,
  FileText,
} from 'lucide-react'
import { useChat, useChatSettings } from '../hooks'
import { formatTimestamp } from '../types'
import type { ChatWidgetProps, ServiceReference } from '../types'
import {
  announceToScreenReader,
  announceNewMessage,
  announceError,
  storeFocus,
  restoreFocus,
  KEYS,
} from '../utils/accessibility'

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export const ChatWidget = ({
  initialLanguage,
  position = 'bottom-right',
  theme: _theme = 'light',
  enableHistory = true,
  enableStreaming = false,
  maxHeight = '600px',
  onClose,
}: ChatWidgetProps = {}) => {
  const locale = useLocale()
  const t = useTranslations('chatbot')

  // State
  const [isOpen, setIsOpen] = useState(false)
  const [message, setMessage] = useState('')
  const [showSettings, setShowSettings] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const widgetRef = useRef<HTMLDivElement>(null)

  // Hooks
  const { settings, setLanguage } = useChatSettings({
    persistToStorage: enableHistory,
  })

  const {
    messages,
    isLoading,
    isStreaming,
    streamedText,
    error,
    suggestions,
    relatedServices,
    confidence: _confidence,
    sendMessage: sendChatMessage,
    clearChat,
    retry,
    stopStreaming,
  } = useChat({
    language: (initialLanguage || settings.language) as any,
    persistToStorage: enableHistory,
    enableStreaming: enableStreaming,
  })

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamedText])

  // Sync language with locale
  useEffect(() => {
    if (locale && locale !== settings.language) {
      setLanguage(locale as any)
    }
  }, [locale, settings.language, setLanguage])

  // Focus management - focus input when widget opens
  useEffect(() => {
    if (isOpen) {
      storeFocus()
      // Delay to allow animation
      setTimeout(() => {
        inputRef.current?.focus()
      }, 100)
      announceToScreenReader(t('welcomeMessage') || 'Chat assistant opened')
    } else {
      restoreFocus()
    }
  }, [isOpen, t])

  // Announce new messages to screen readers
  useEffect(() => {
    if (messages.length > 0) {
      const lastMessage = messages[messages.length - 1]
      announceNewMessage(lastMessage.role as 'user' | 'assistant', lastMessage.content)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- Only trigger when messages count changes
  }, [messages.length])

  // Announce errors
  useEffect(() => {
    if (error) {
      announceError(error)
    }
  }, [error])

  // Keyboard navigation - Escape to close
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.key === KEYS.ESCAPE && isOpen) {
      handleClose()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- handleClose is stable
  }, [isOpen])

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [handleKeyDown])

  // Listen for external openChatbot event (e.g., from CTA buttons)
  useEffect(() => {
    const handleOpenChatbot = () => {
      setIsOpen(true)
    }
    window.addEventListener('openChatbot', handleOpenChatbot)
    return () => window.removeEventListener('openChatbot', handleOpenChatbot)
  }, [])

  // =============================================================================
  // HANDLERS
  // =============================================================================

  const handleSend = async () => {
    if (!message.trim() || isLoading) return

    await sendChatMessage(message)
    setMessage('')
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleSuggestionClick = (suggestion: string) => {
    setMessage(suggestion)
  }

  const handleClose = () => {
    setIsOpen(false)
    if (onClose) {
      onClose()
    }
  }

  // =============================================================================
  // POSITION STYLES
  // =============================================================================

  const positionClasses = {
    'bottom-right': 'bottom-4 right-4',
    'bottom-left': 'bottom-4 left-4',
    'top-right': 'top-4 right-4',
    'top-left': 'top-4 left-4',
  }

  // =============================================================================
  // FLOATING BUTTON (CLOSED STATE)
  // =============================================================================

  if (!isOpen) {
    return (
      <Button
        onClick={() => setIsOpen(true)}
        className={`fixed ${positionClasses[position]} rounded-full h-14 w-14 shadow-lg z-50 hover:scale-110 transition-transform`}
        aria-label={t('openChat') || 'Open chat'}
      >
        <MessageCircle className="h-6 w-6" />
      </Button>
    )
  }

  // =============================================================================
  // CHAT WIDGET (OPEN STATE)
  // =============================================================================

  return (
    <Card
      ref={widgetRef}
      className={`fixed ${positionClasses[position]} w-96 shadow-2xl flex flex-col z-50 animate-in slide-in-from-bottom-4`}
      style={{ maxHeight, height: maxHeight }}
      role="dialog"
      aria-modal="true"
      aria-labelledby="chat-widget-title"
      aria-describedby="chat-widget-description"
    >
      {/* Hidden description for screen readers */}
      <span id="chat-widget-description" className="sr-only">
        AI assistant for Facil digital services. Use arrow keys to navigate messages, Enter to send.
      </span>

      {/* Header */}
      <div className="p-4 border-b flex items-center justify-between bg-primary text-white rounded-t-lg">
        <div className="flex items-center gap-2">
          <div className="flex-shrink-0 h-10 w-10 rounded-full bg-white flex items-center justify-center p-1">
            <Image
              src="/icon_facil.png"
              alt="Facil"
              width={32}
              height={32}
              className="object-contain"
            />
          </div>
          <div>
            <h3 id="chat-widget-title" className="font-semibold text-sm">{t('title') || 'Asistente Facil'}</h3>
            <div className="flex items-center gap-1">
              <div className="h-2 w-2 rounded-full bg-green-400 animate-pulse" />
              <p className="text-xs opacity-80">{t('online') || 'Online'}</p>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setShowSettings(!showSettings)}
            className="text-white hover:bg-white/20 h-8 w-8"
            aria-label={t('settings') || 'Settings'}
            aria-expanded={showSettings}
            aria-controls="chat-settings-panel"
          >
            <Settings className="h-4 w-4" aria-hidden="true" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={clearChat}
            className="text-white hover:bg-white/20 h-8 w-8"
            aria-label={t('clearChat') || 'Clear chat'}
          >
            <Trash2 className="h-4 w-4" aria-hidden="true" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={handleClose}
            className="text-white hover:bg-white/20 h-8 w-8"
            aria-label={t('closeChat') || 'Close chat'}
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </Button>
        </div>
      </div>

      {/* Settings Panel */}
      {showSettings && (
        <div className="p-3 border-b bg-muted/50 space-y-2">
          <div className="text-xs font-medium">{t('settings') || 'Settings'}</div>
          <div className="flex gap-2">
            {(['es', 'fr', 'en'] as const).map((lang) => (
              <Button
                key={lang}
                size="sm"
                variant={settings.language === lang ? 'default' : 'outline'}
                onClick={() => setLanguage(lang)}
                className="text-xs"
              >
                {lang.toUpperCase()}
              </Button>
            ))}
          </div>
        </div>
      )}

      {/* Messages Area */}
      <ScrollArea className="flex-1 p-4">
        <div
          className="space-y-4"
          role="log"
          aria-label="Chat messages"
          aria-live="polite"
          aria-relevant="additions"
        >
          {messages.length === 0 && (
            <div className="text-center text-muted-foreground text-sm py-8">
              <div className="h-16 w-16 rounded-full bg-primary/10 flex items-center justify-center mx-auto mb-2">
                <Image
                  src="/icon_facil.png"
                  alt="Facil"
                  width={40}
                  height={40}
                  className="object-contain opacity-50"
                />
              </div>
              <p>{t('welcomeMessage') || '¡Hola! ¿En qué puedo ayudarte hoy?'}</p>
            </div>
          )}

          {messages.map((msg, i) => (
            <div
              key={i}
              className={`flex gap-2 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              {msg.role === 'assistant' && (
                <div className="flex-shrink-0 h-8 w-8 rounded-full bg-white flex items-center justify-center border border-primary/20">
                  <Image
                    src="/icon_facil.png"
                    alt="Facil"
                    width={24}
                    height={24}
                    className="object-contain"
                  />
                </div>
              )}
              <div
                className={`max-w-[75%] rounded-lg p-3 ${
                  msg.role === 'user'
                    ? 'bg-primary text-white'
                    : 'bg-muted text-foreground'
                }`}
              >
                <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                <p className="text-xs opacity-70 mt-1">
                  {formatTimestamp(msg.timestamp, locale)}
                </p>
              </div>
              {msg.role === 'user' && (
                <div className="flex-shrink-0 h-8 w-8 rounded-full bg-primary flex items-center justify-center">
                  <User className="h-4 w-4 text-white" />
                </div>
              )}
            </div>
          ))}

          {/* Streaming Text Display */}
          {isStreaming && streamedText && (
            <div className="flex gap-2 justify-start">
              <div className="flex-shrink-0 h-8 w-8 rounded-full bg-white flex items-center justify-center border border-primary/20">
                <Image
                  src="/icon_facil.png"
                  alt="Facil"
                  width={24}
                  height={24}
                  className="object-contain"
                />
              </div>
              <div className="max-w-[75%] rounded-lg p-3 bg-muted text-foreground">
                <p className="text-sm whitespace-pre-wrap">{streamedText}</p>
                <span className="inline-block w-2 h-4 bg-primary/60 animate-pulse ml-1" />
              </div>
            </div>
          )}

          {/* Loading Indicator (non-streaming) */}
          {isLoading && !isStreaming && (
            <div className="flex gap-2 justify-start">
              <div className="flex-shrink-0 h-8 w-8 rounded-full bg-white flex items-center justify-center border border-primary/20">
                <Image
                  src="/icon_facil.png"
                  alt="Facil"
                  width={24}
                  height={24}
                  className="object-contain"
                />
              </div>
              <div className="bg-muted rounded-lg p-3">
                <Loader2 className="h-4 w-4 animate-spin" />
              </div>
            </div>
          )}

          {/* Streaming Indicator (before text arrives) */}
          {isStreaming && !streamedText && (
            <div className="flex gap-2 justify-start">
              <div className="flex-shrink-0 h-8 w-8 rounded-full bg-white flex items-center justify-center border border-primary/20">
                <Image
                  src="/icon_facil.png"
                  alt="Facil"
                  width={24}
                  height={24}
                  className="object-contain"
                />
              </div>
              <div className="bg-muted rounded-lg p-3 flex items-center gap-1">
                <span className="h-2 w-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                <span className="h-2 w-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                <span className="h-2 w-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </div>
          )}

          {/* Error Message */}
          {error && (
            <div className="flex items-start gap-2 p-3 bg-destructive/10 border border-destructive/20 rounded-lg">
              <AlertCircle className="h-4 w-4 text-destructive flex-shrink-0 mt-0.5" />
              <div className="flex-1">
                <p className="text-sm text-destructive">{error}</p>
                <p className="text-xs text-muted-foreground mt-1">{t('errorMessage')}</p>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={retry}
                  className="mt-2 h-7 text-xs"
                >
                  <RefreshCw className="h-3 w-3 mr-1" />
                  {t('retry') || 'Retry'}
                </Button>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </ScrollArea>

      {/* Suggestions */}
      {settings.enableSuggestions && suggestions.length > 0 && (
        <div className="px-4 py-2 border-t bg-muted/30">
          <div className="text-xs font-medium mb-2 text-muted-foreground">
            {t('suggestions') || 'Suggestions'}
          </div>
          <div className="flex flex-wrap gap-1">
            {suggestions.slice(0, 3).map((suggestion, i) => (
              <Badge
                key={i}
                variant="secondary"
                className="cursor-pointer hover:bg-secondary/80 text-xs"
                onClick={() => handleSuggestionClick(suggestion)}
              >
                {suggestion}
              </Badge>
            ))}
          </div>
        </div>
      )}

      {/* Related Services */}
      {settings.enableRelatedServices && relatedServices.length > 0 && (
        <div className="px-4 py-2 border-t bg-muted/30">
          <div className="text-xs font-medium mb-2 text-muted-foreground flex items-center gap-1">
            <FileText className="h-3 w-3" />
            {t('relatedServices') || 'Related Services'}
          </div>
          <div className="space-y-1">
            {relatedServices.slice(0, 3).map((service: ServiceReference, i) => (
              <div
                key={i}
                className="text-xs p-2 rounded bg-white border hover:border-primary/50 cursor-pointer transition-colors"
              >
                <div className="font-medium">{service.name}</div>
                {service.similarity && (
                  <div className="text-muted-foreground">
                    {Math.round(service.similarity * 100)}% {t('match') || 'match'}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Input Area */}
      <div className="p-4 border-t flex gap-2 bg-background">
        <Input
          ref={inputRef}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder={t('inputPlaceholder') || 'Posez votre question...'}
          disabled={isLoading || isStreaming}
          className="flex-1"
          aria-label={t('inputPlaceholder') || 'Type your message'}
          aria-describedby="chat-input-hint"
          aria-busy={isLoading || isStreaming}
        />
        <span id="chat-input-hint" className="sr-only">
          Press Enter to send, Escape to close chat
        </span>
        {isStreaming ? (
          <Button
            onClick={stopStreaming}
            variant="destructive"
            aria-label="Stop streaming"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </Button>
        ) : (
          <Button
            onClick={handleSend}
            disabled={isLoading || !message.trim()}
            aria-label={isLoading ? t('sending') : 'Send message'}
            aria-busy={isLoading}
          >
            {isLoading ? (
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            ) : (
              <Send className="h-4 w-4" aria-hidden="true" />
            )}
          </Button>
        )}
      </div>
    </Card>
  )
}

export default ChatWidget
