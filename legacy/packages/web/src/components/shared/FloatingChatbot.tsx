'use client'

import { useState, useRef, useEffect, useCallback } from "react"
import { MessageCircle, X, Send, Loader2, RefreshCw, User } from "lucide-react"
import { useLocale, useTranslations } from "next-intl"
import Image from "next/image"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import { chatbotApi } from "@/modules/chatbot/services/api"
import { renderMarkdown } from "@/core/utils/markdown"
import { useDocumentAlerts } from "@/modules/user-documents/hooks"
import type { LanguageCode } from "@/modules/chatbot/types"

interface Message {
  role: "user" | "assistant"
  content: string
  timestamp?: string
}

export const FloatingChatbot = () => {
  const locale = useLocale() as LanguageCode
  const t = useTranslations('chatbot')
  const { unreadCount } = useDocumentAlerts()

  const [isOpen, setIsOpen] = useState(false)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [conversationId, setConversationId] = useState<string | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Scroll to bottom when messages change
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages])

  // Focus input when chat opens
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 100)
    }
  }, [isOpen])

  // Listen for external openChatbot event (from CTA buttons)
  useEffect(() => {
    const handleOpenChatbot = () => {
      setIsOpen(true)
    }
    window.addEventListener('openChatbot', handleOpenChatbot)
    return () => window.removeEventListener('openChatbot', handleOpenChatbot)
  }, [])

  // Keyboard navigation - Escape to close
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        setIsOpen(false)
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [isOpen])

  const handleSend = useCallback(async () => {
    if (!input.trim() || isLoading) return

    const userMessage: Message = {
      role: "user",
      content: input,
      timestamp: new Date().toISOString()
    }
    setMessages((prev) => [...prev, userMessage])
    setInput("")
    setIsLoading(true)
    setError(null)

    try {
      // Call the real RAG API
      const response = await chatbotApi.chat({
        message: input,
        conversationId: conversationId || undefined,
        language: locale,
      })

      const assistantMessage: Message = {
        role: "assistant",
        content: response.response,
        timestamp: response.timestamp
      }

      setMessages((prev) => [...prev, assistantMessage])
      setConversationId(response.conversationId)
    } catch (err) {
      console.error("Error sending message:", err)
      const errorMessage = err instanceof Error ? err.message : "Unknown error"
      setError(errorMessage)
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: t('errorMessage') || "Désolé, une erreur s'est produite. Veuillez réessayer.",
          timestamp: new Date().toISOString()
        },
      ])
    } finally {
      setIsLoading(false)
    }
  }, [input, isLoading, conversationId, locale, t])

  const handleRetry = useCallback(async () => {
    // Remove the last error message and retry
    if (messages.length >= 2) {
      const lastUserMessage = messages[messages.length - 2]
      if (lastUserMessage.role === 'user') {
        setMessages((prev) => prev.slice(0, -1))
        setInput(lastUserMessage.content)
        setError(null)
      }
    }
  }, [messages])

  const handleClearChat = useCallback(() => {
    setMessages([])
    setConversationId(null)
    setError(null)
  }, [])

  return (
    <>
      {/* Floating Button — pinned bottom-RIGHT (same side as the footer
          "Contacto" block, so the help affordance lives in the user's
          natural support-seeking quadrant). Pill shape with persistent
          label, pulse halo to draw attention, larger touch target. */}
      {!isOpen && (
        <button
          onClick={() => setIsOpen(true)}
          className="fixed bottom-6 right-6 z-50 print:hidden group flex items-center gap-2 h-14 pl-4 pr-5 rounded-full shadow-2xl bg-primary text-primary-foreground hover:bg-primary/90 transition-all duration-300 hover:scale-105 hover:shadow-primary/40"
          aria-label={t('openChat') || 'Open chat'}
        >
          {/* Pulse halo (purely decorative, attracts attention without
              spamming the rest of the page) */}
          <span
            aria-hidden="true"
            className="absolute inset-0 rounded-full bg-primary/40 animate-ping opacity-60"
          />
          <span className="relative flex items-center justify-center h-9 w-9 rounded-full bg-white/15">
            <MessageCircle className="h-5 w-5" />
          </span>
          <span className="relative text-sm font-medium whitespace-nowrap">
            {t('title') || 'Asistente IA'}
          </span>
          {unreadCount > 0 && (
            <span className="absolute -top-1 -right-1 flex h-5 w-5 items-center justify-center rounded-full bg-destructive text-[10px] font-bold text-destructive-foreground">
              {unreadCount > 9 ? '9+' : unreadCount}
            </span>
          )}
        </button>
      )}

      {/* Chat Window — same side (right) as the trigger for spatial coherence */}
      {isOpen && (
        <div
          className="fixed bottom-6 right-6 w-96 h-[500px] bg-card border border-border rounded-lg shadow-2xl flex flex-col z-50 animate-in slide-in-from-bottom-4 print:hidden"
          role="dialog"
          aria-modal="true"
          aria-labelledby="chatbot-title"
        >
          {/* Header */}
          <div className="flex items-center justify-between p-4 border-b border-border bg-primary rounded-t-lg">
            <div className="flex items-center space-x-2">
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
                <h3 id="chatbot-title" className="font-semibold text-white text-sm">{t('title') || 'Asistente Facil'}</h3>
                <p className="text-xs text-white/80">{t('online') || 'En ligne'}</p>
              </div>
            </div>
            <div className="flex items-center gap-1">
              <Button
                onClick={handleClearChat}
                variant="ghost"
                size="icon"
                className="text-white hover:bg-white/20 h-8 w-8"
                aria-label={t('clearChat') || 'Clear chat'}
              >
                <RefreshCw className="h-4 w-4" />
              </Button>
              <Button
                onClick={() => setIsOpen(false)}
                variant="ghost"
                size="icon"
                className="text-white hover:bg-white/20 h-8 w-8"
                aria-label={t('closeChat') || 'Close chat'}
              >
                <X className="h-5 w-5" />
              </Button>
            </div>
          </div>

          {/* Messages */}
          <ScrollArea className="flex-1 p-4" ref={scrollRef}>
            <div className="space-y-4" role="log" aria-live="polite">
              {/* Welcome message if no messages */}
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

              {messages.map((message, index) => (
                <div
                  key={index}
                  className={`flex gap-2 ${
                    message.role === "user" ? "justify-end" : "justify-start"
                  }`}
                >
                  {message.role === "assistant" && (
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
                    className={`${message.role === "user" ? "max-w-[75%]" : "max-w-[90%]"} rounded-lg p-3 ${
                      message.role === "user"
                        ? "bg-primary text-primary-foreground"
                        : "bg-muted text-foreground"
                    }`}
                  >
                    {message.role === "assistant" ? (
                      <div
                        className="text-sm prose prose-sm max-w-none"
                        dangerouslySetInnerHTML={{ __html: renderMarkdown(message.content) }}
                      />
                    ) : (
                      <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                    )}
                  </div>
                  {message.role === "user" && (
                    <div className="flex-shrink-0 h-8 w-8 rounded-full bg-primary flex items-center justify-center">
                      <User className="h-4 w-4 text-white" />
                    </div>
                  )}
                </div>
              ))}

              {/* Loading indicator */}
              {isLoading && (
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

              {/* Error with retry */}
              {error && (
                <div className="flex items-center gap-2 text-xs text-destructive">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={handleRetry}
                    className="h-7 text-xs"
                  >
                    <RefreshCw className="h-3 w-3 mr-1" />
                    {t('retry') || 'Retry'}
                  </Button>
                </div>
              )}
            </div>
          </ScrollArea>

          {/* Input */}
          <div className="p-4 border-t border-border">
            <form
              onSubmit={(e) => {
                e.preventDefault()
                handleSend()
              }}
              className="flex space-x-2"
            >
              <Input
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder={t('inputPlaceholder') || 'Posez votre question...'}
                disabled={isLoading}
                className="flex-1"
                aria-label={t('inputPlaceholder') || 'Type your message'}
              />
              <Button
                type="submit"
                size="icon"
                disabled={isLoading || !input.trim()}
                aria-label={isLoading ? t('sending') : t('send') || 'Send'}
              >
                {isLoading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Send className="h-4 w-4" />
                )}
              </Button>
            </form>
          </div>
        </div>
      )}
    </>
  )
}

export default FloatingChatbot
