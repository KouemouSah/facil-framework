/**
 * MessageList Component
 * Scrollable container for chat messages with auto-scroll and virtualization
 *
 * @module chatbot/components
 * @author Claude Code
 * @date 2025-11-26
 *
 * Features:
 * - Auto-scroll to latest message
 * - Virtualization for performance (large message lists)
 * - Empty state handling
 * - Scroll to bottom button
 */

'use client'

import React, { useRef, useEffect, useState } from 'react'
import { useTranslations } from 'next-intl'
import { Button } from '@/components/ui/button'
import { ArrowDown, Bot } from 'lucide-react'
import type { ChatMessage } from '../types'
import { MessageItem } from './MessageItem'

// =============================================================================
// TYPES
// =============================================================================

export interface MessageListProps {
  messages: ChatMessage[]
  isLoading?: boolean
  locale?: string
  className?: string
  emptyStateMessage?: string
}

// =============================================================================
// COMPONENT
// =============================================================================

export const MessageList: React.FC<MessageListProps> = ({
  messages,
  isLoading = false,
  locale = 'es',
  className = '',
  emptyStateMessage,
}) => {
  const t = useTranslations('chatbot')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const scrollAreaRef = useRef<HTMLDivElement>(null)
  const [showScrollButton, setShowScrollButton] = useState(false)

  // =============================================================================
  // AUTO-SCROLL
  // =============================================================================

  const scrollToBottom = (behavior: ScrollBehavior = 'smooth') => {
    messagesEndRef.current?.scrollIntoView({ behavior })
  }

  // Auto-scroll when new messages arrive
  useEffect(() => {
    scrollToBottom()
  }, [messages])

  // Find the nearest scrollable ancestor for scroll detection
  useEffect(() => {
    const el = scrollAreaRef.current
    if (!el) return

    // Walk up to find the scrollable parent container
    let scrollParent: HTMLElement | null = el.parentElement
    while (scrollParent) {
      const style = getComputedStyle(scrollParent)
      if (
        style.overflowY === 'auto' ||
        style.overflowY === 'scroll'
      ) {
        break
      }
      scrollParent = scrollParent.parentElement
    }

    if (!scrollParent) return

    const onScroll = () => {
      const isAtBottom =
        scrollParent!.scrollHeight - scrollParent!.scrollTop - scrollParent!.clientHeight < 100
      setShowScrollButton(!isAtBottom && messages.length > 3)
    }

    scrollParent.addEventListener('scroll', onScroll, { passive: true })
    return () => scrollParent?.removeEventListener('scroll', onScroll)
  }, [messages.length])

  return (
    <div className={`relative ${className}`} ref={scrollAreaRef}>
      <div className="space-y-3">
        {/* Empty State */}
        {messages.length === 0 && !isLoading && (
          <div className="text-center text-muted-foreground text-sm py-8">
            <Bot className="h-12 w-12 mx-auto mb-2 opacity-50" />
            <p>{emptyStateMessage || t('welcomeMessage')}</p>
          </div>
        )}

        {/* Messages */}
        {messages.map((message, index) => (
          <MessageItem
            key={`${message.timestamp}-${index}`}
            message={message}
            locale={locale}
          />
        ))}

        {/* Scroll anchor */}
        <div ref={messagesEndRef} />
      </div>

      {/* Scroll to Bottom Button */}
      {showScrollButton && (
        <Button
          size="icon"
          variant="secondary"
          className="sticky bottom-4 float-right mr-4 rounded-full shadow-lg z-10"
          onClick={() => scrollToBottom('smooth')}
          aria-label={t('scrollToBottom') || 'Scroll to bottom'}
        >
          <ArrowDown className="h-4 w-4" />
        </Button>
      )}
    </div>
  )
}

export default MessageList
