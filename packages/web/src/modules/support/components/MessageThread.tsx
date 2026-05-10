'use client'

import { useState, useRef, useEffect } from 'react'
import { useTranslations } from 'next-intl'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Checkbox } from '@/components/ui/checkbox'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Skeleton } from '@/components/ui/skeleton'
import { Send, Lock, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { SupportMessage, SupportMessageCreate } from '../types'

interface MessageThreadProps {
  messages: SupportMessage[]
  isLoading: boolean
  isAdmin?: boolean
  currentUserId: string
  onSendMessage: (data: SupportMessageCreate) => Promise<void>
  ticketClosed?: boolean
  locale: string
}

export function MessageThread({
  messages,
  isLoading,
  isAdmin = false,
  currentUserId,
  onSendMessage,
  ticketClosed = false,
  locale,
}: MessageThreadProps) {
  const t = useTranslations('support')
  const [newMessage, setNewMessage] = useState('')
  const [isInternal, setIsInternal] = useState(false)
  const [sending, setSending] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages])

  const handleSend = async () => {
    if (!newMessage.trim() || sending) return

    setSending(true)
    try {
      await onSendMessage({
        content: newMessage.trim(),
        isInternal: isAdmin && isInternal,
      })
      setNewMessage('')
      setIsInternal(false)
    } finally {
      setSending(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString(locale, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  const getInitials = (name?: string) => {
    if (!name) return '?'
    return name
      .split(' ')
      .map((n) => n[0])
      .join('')
      .toUpperCase()
      .slice(0, 2)
  }

  const isOwnMessage = (message: SupportMessage) => {
    return message.senderId === currentUserId
  }

  if (isLoading) {
    return (
      <div className="space-y-4">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="flex gap-3">
            <Skeleton className="h-10 w-10 rounded-full" />
            <div className="flex-1 space-y-2">
              <Skeleton className="h-4 w-32" />
              <Skeleton className="h-16 w-full" />
            </div>
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className="flex flex-col h-[500px]">
      {/* Messages */}
      <ScrollArea className="flex-1 pr-4" ref={scrollRef}>
        <div className="space-y-4 pb-4">
          {messages.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              {t('noMessages')}
            </div>
          ) : (
            messages.map((message) => {
              // Filter internal messages for non-admin users
              if (message.isInternal && !isAdmin) {
                return null
              }

              const own = isOwnMessage(message)

              return (
                <div
                  key={message.id}
                  className={cn(
                    'flex gap-3',
                    own && 'flex-row-reverse'
                  )}
                >
                  <Avatar className="h-10 w-10 shrink-0">
                    <AvatarFallback
                      className={cn(
                        message.senderRole === 'admin' && 'bg-primary text-primary-foreground',
                        own && 'bg-muted'
                      )}
                    >
                      {getInitials(message.senderName)}
                    </AvatarFallback>
                  </Avatar>

                  <div
                    className={cn(
                      'flex-1 max-w-[80%]',
                      own && 'text-right'
                    )}
                  >
                    <div
                      className={cn(
                        'flex items-center gap-2 mb-1',
                        own && 'flex-row-reverse'
                      )}
                    >
                      <span className="font-medium text-sm">
                        {message.senderName || t('unknownUser')}
                      </span>
                      {message.isInternal && (
                        <span className="inline-flex items-center gap-1 text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded">
                          <Lock className="h-3 w-3" />
                          {t('internalNote')}
                        </span>
                      )}
                      <span className="text-xs text-muted-foreground">
                        {formatDate(message.createdAt)}
                      </span>
                    </div>

                    <div
                      className={cn(
                        'rounded-lg p-3 inline-block',
                        own
                          ? 'bg-primary text-primary-foreground'
                          : 'bg-muted',
                        message.isInternal && 'border-2 border-dashed border-amber-500 bg-amber-50 dark:bg-amber-950'
                      )}
                    >
                      <p className="whitespace-pre-wrap text-sm">
                        {message.content}
                      </p>
                    </div>
                  </div>
                </div>
              )
            })
          )}
        </div>
      </ScrollArea>

      {/* Message Input */}
      {!ticketClosed ? (
        <div className="border-t pt-4 mt-4">
          {isAdmin && (
            <div className="flex items-center gap-2 mb-3">
              <Checkbox
                id="internal"
                checked={isInternal}
                onCheckedChange={(checked) => setIsInternal(checked === true)}
              />
              <label
                htmlFor="internal"
                className="text-sm font-medium flex items-center gap-1 cursor-pointer"
              >
                <Lock className="h-3 w-3" />
                {t('markAsInternal')}
              </label>
            </div>
          )}

          <div className="flex gap-2">
            <Textarea
              placeholder={t('typeMessage')}
              value={newMessage}
              onChange={(e) => setNewMessage(e.target.value)}
              onKeyDown={handleKeyDown}
              className="min-h-[80px] resize-none"
              disabled={sending}
            />
            <Button
              onClick={handleSend}
              disabled={!newMessage.trim() || sending}
              className="self-end"
            >
              {sending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Send className="h-4 w-4" />
              )}
            </Button>
          </div>
        </div>
      ) : (
        <div className="border-t pt-4 mt-4 text-center text-muted-foreground">
          {t('ticketClosedNoReply')}
        </div>
      )}
    </div>
  )
}

export default MessageThread
