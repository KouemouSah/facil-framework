/**
 * MessageItem Component
 * Individual chat message with rich formatting
 *
 * @module chatbot/components
 * @author Claude Code
 * @date 2025-11-26
 *
 * Features:
 * - User vs Bot message styling
 * - Markdown rendering with code highlighting
 * - Service code highlighting (PAT-001, etc.)
 * - Timestamp display
 * - Copy button
 */

'use client'

import React, { useState } from 'react'
import Image from 'next/image'
import { useTranslations } from 'next-intl'
import createDOMPurify from 'dompurify'
import { User, Copy, Check, Download, FileText, ThumbsUp, ThumbsDown, ExternalLink, Settings, AlertTriangle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { formatTimestamp } from '../types'
import type { ChatMessage, ChatAction } from '../types'

/**
 * Sanitize HTML output from renderMarkdown to prevent XSS.
 * Whitelists only safe tags/attributes for chatbot markdown rendering.
 */
const sanitizeHtml = (html: string): string => {
  if (typeof window === 'undefined') return html // SSR: skip sanitization (rendered client-side)
  const DOMPurify = createDOMPurify(window)
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: [
      'strong', 'em', 'li', 'ul', 'ol', 'code', 'pre',
      'table', 'tr', 'td', 'th', 'thead', 'tbody',
      'a', 'h3', 'h4', 'h5', 'blockquote', 'hr', 'br', 'p',
      'span', 'div',
    ],
    ALLOWED_ATTR: ['class', 'href', 'target', 'rel'],
    ALLOWED_URI_REGEXP: /^(?:(?:https?|mailto):|[^a-z]|[a-z+.-]+(?:[^a-z+.\-:]|$))/i,
    FORBID_ATTR: ['onerror', 'onload', 'onclick', 'onmouseover'],
  })
}

// =============================================================================
// TYPES
// =============================================================================

export interface MessageItemProps {
  message: ChatMessage
  locale?: string
  className?: string
  /**
   * When provided (authenticated chat only), clicking an `open_settings`
   * action opens the AgentSettingsPanel in place via this callback
   * instead of navigating to the DocumentVault page. The public chat
   * omits this prop and falls back to the legacy `<a href>` behavior.
   */
  onOpenAgentPanel?: (permissionType?: string) => void
  /**
   * Phase 5 — clicking a `confirm_executive` action opens the
   * ExecutiveConfirmModal via this callback. Only wired in the
   * authenticated chat page. Without it, the action is skipped silently
   * (no fallback — executive tools require the confirmation flow).
   */
  onConfirmExecutive?: (action: ChatAction) => void
}

// =============================================================================
// HELPERS
// =============================================================================

/**
 * Highlight service codes (e.g., PAT-001, IVA-002)
 */
const highlightServiceCodes = (text: string): string => {
  return text.replace(
    /\b([A-Z]{2,5}-\d{3,4})\b/g,
    '<span class="inline-block px-1.5 py-0.5 rounded bg-primary/20 text-primary font-mono text-xs font-semibold">$1</span>'
  )
}

/**
 * Markdown rendering optimized for LLM fiscal assistant responses.
 * Handles bold, italic, code, lists, tables, and auto-detects price line items.
 */
const renderMarkdown = (text: string): string => {
  let html = text

  // Strip raw JSON blocks (e.g., `json{"briefing": "Normal"...}`)
  // These are internal tool responses that should not be displayed to users
  html = html.replace(/(?:^|\n)json\s*\{[\s\S]*?\}(?:\n|$)/g, '\n')
  html = html.replace(/```json\s*\{[\s\S]*?\}```/g, '')

  // Code blocks ```code```
  html = html.replace(/```([\s\S]*?)```/g, '<pre class="bg-stone-100 dark:bg-stone-800 p-3 rounded-lg text-sm overflow-x-auto my-3 font-mono"><code>$1</code></pre>')

  // Inline code `code`
  html = html.replace(/`([^`]+)`/g, '<code class="bg-stone-100 dark:bg-stone-800 px-1.5 py-0.5 rounded text-sm font-mono">$1</code>')

  // Headings (before bold to avoid conflicts)
  html = html.replace(/^#### (.+)$/gm, '<h5 class="font-semibold text-sm mt-3 mb-1.5 text-stone-800 dark:text-stone-200">$1</h5>')
  html = html.replace(/^### (.+)$/gm, '<h4 class="font-semibold text-base mt-4 mb-2 text-stone-800 dark:text-stone-200">$1</h4>')
  html = html.replace(/^## (.+)$/gm, '<h3 class="font-semibold text-lg mt-5 mb-2 text-stone-800 dark:text-stone-200">$1</h3>')

  // Tables (markdown table format) - BEFORE bold/italic to preserve pipes
  html = html.replace(/^\|(.+)\|\n\|[-| :]+\|\n((?:\|.+\|\n?)*)/gm, (_match, header, body) => {
    const headers = header.split('|').map((h: string) => h.trim()).filter(Boolean)
    const rows = body.trim().split('\n').map((row: string) =>
      row.split('|').map((c: string) => c.trim()).filter(Boolean)
    )
    return `<div class="overflow-x-auto my-3 rounded-md border border-stone-200 dark:border-stone-700"><table class="w-full text-sm border-collapse">
      <thead><tr>${headers.map((h: string) => `<th class="border-b border-stone-200 dark:border-stone-700 px-3 py-2 text-left font-semibold text-stone-700 dark:text-stone-300 bg-stone-50 dark:bg-stone-800/50">${h}</th>`).join('')}</tr></thead>
      <tbody>${rows.map((row: string[], ri: number) => `<tr class="${ri % 2 ? 'bg-stone-50/50 dark:bg-stone-800/20' : ''}">${row.map((c: string) => `<td class="border-b border-stone-100 dark:border-stone-800 px-3 py-1.5">${c}</td>`).join('')}</tr>`).join('')}</tbody>
    </table></div>`
  })

  // Bold **text**
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong class="font-semibold text-stone-800 dark:text-stone-100">$1</strong>')

  // Italic *text* (only if not already part of bold)
  html = html.replace(/(?<!\*)\*([^*\n]+)\*(?!\*)/g, '<em class="italic">$1</em>')

  // Blockquotes > text (attention notes, legal quotes) — BEFORE lists
  html = html.replace(/^>\s*(.+)$/gm, '<blockquote class="border-l-4 border-primary/40 bg-primary/5 dark:bg-primary/10 pl-3 pr-2 py-2 my-2 rounded-r text-sm">$1</blockquote>')
  // Merge consecutive blockquotes
  html = html.replace(/<\/blockquote>\n<blockquote/g, '<br><blockquote')

  // Horizontal rule --- (separators)
  html = html.replace(/^---+$/gm, '<hr class="my-3 border-stone-200 dark:border-stone-700">')

  // Unicode bullet markers (▸, •, ►, →) → standard bullets
  html = html.replace(/^[•▸►]\s*/gm, '- ')
  // Arrow → at line start as sub-item indicator
  html = html.replace(/^→\s*/gm, '- ')

  // Checkmark lines ✓ item → checklist style
  html = html.replace(/^[✓✔]\s+(.+)$/gm, '<li class="ml-4 py-0 list-none flex items-start gap-1.5"><span class="text-green-600 dark:text-green-400 mt-0.5 shrink-0">✓</span><span>$1</span></li>')

  // Auto-detect price lines: "ConceptName: 123.456 XAF" (requires XAF or 3+ digit number with dots)
  html = html.replace(/^([A-ZÁÉÍÓÚÑ][^:\n]{2,60}):\s*([\d.]+\s*XAF)\s*$/gm, '- **$1**: $2')

  // Remove extra blank lines between list items
  html = html.replace(/^(- .+)\n{2,4}(?=- )/gm, '$1\n')
  html = html.replace(/^(\d+\. .+)\n{2,4}(?=\d+\. )/gm, '$1\n')

  // Bullet lists - item (consecutive)
  html = html.replace(/^- (.+)$/gm, '<li class="ml-4 py-0 list-disc">$1</li>')
  // Wrap consecutive <li> in <ul>
  html = html.replace(/((?:<li class="ml-4 py-0[^"]*">[\s\S]*?<\/li>\n?)+)/g, (match) => {
    if (match.includes('list-none')) return `<ul class="my-1 space-y-0 pl-1">${match}</ul>`
    return `<ul class="list-disc my-1 space-y-0 pl-1">${match}</ul>`
  })

  // Numbered lists 1. item (consecutive)
  html = html.replace(/^\d+\.\s+(.+)$/gm, '<li class="ml-4 py-0">$1</li>')
  html = html.replace(/((?:<li class="ml-4 py-0">(?!.*list-disc)(?!.*list-none)[\s\S]*?<\/li>\n?)+)/g,
    (match) => `<ol class="list-decimal my-1 space-y-0 pl-1">${match}</ol>`)

  // Links [text](url)
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer" class="text-primary hover:underline">$1</a>')

  // Paragraphs (double newline → spacing)
  html = html.replace(/\n\n/g, '</p><p class="my-1">')

  // Single newlines → <br>
  html = html.replace(/\n/g, '<br>')

  // Highlight service codes
  html = highlightServiceCodes(html)

  return html
}

// =============================================================================
// COMPONENT
// =============================================================================

export const MessageItem: React.FC<MessageItemProps> = ({
  message,
  locale = 'es',
  className = '',
  onOpenAgentPanel,
  onConfirmExecutive,
}) => {
  const t = useTranslations('chatbot')
  // Separate namespaces so we can resolve action labels AND permission-type
  // human names independently (e.g. "prepare_request" → "Préparer les demandes").
  const tActions = useTranslations('chatbot.actions')
  const tPermTypes = useTranslations('userDocuments.agent.permissionTypes')
  const [copied, setCopied] = useState(false)
  const [feedback, setFeedback] = useState<'up' | 'down' | null>(null)

  const isUser = message.role === 'user'
  const isBot = message.role === 'assistant'

  /**
   * Resolve an action's label: prefer backend-supplied i18n key, otherwise
   * fall back to the legacy literal. When `permission_key` is present in
   * label_params, replace it with the localized permission type name.
   */
  const resolveActionLabel = (action: ChatAction): string => {
    if (!action.label_key) return action.label
    const params: Record<string, string | number> = { ...(action.label_params ?? {}) }
    if (typeof params.permission_key === 'string') {
      try {
        params.permission = tPermTypes(params.permission_key as string)
      } catch {
        params.permission = params.permission_key
      }
      delete params.permission_key
    }
    try {
      return tActions(action.label_key.replace(/^chatbot\.actions\./, ''), params)
    } catch {
      return action.label
    }
  }

  // =============================================================================
  // HANDLERS
  // =============================================================================

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.content)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (err) {
      console.error('Failed to copy:', err)
    }
  }

  const handleDownloadMd = () => {
    const blob = new Blob([message.content], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `facil-response-${Date.now()}.md`
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleDownloadTxt = () => {
    const blob = new Blob([message.content], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `facil-response-${Date.now()}.txt`
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleFeedback = async (type: 'up' | 'down') => {
    setFeedback(type)
    try {
      const { chatbotApi } = await import('../services/api')
      await chatbotApi.submitFeedback({
        conversationId: message.timestamp || new Date().toISOString(),
        rating: type === 'up' ? 5 : 1,
        feedback: type === 'up' ? 'helpful' : 'not_helpful',
      }).catch(() => { /* best-effort */ })
    } catch {
      // Non-blocking — feedback is best-effort
    }
  }

  // =============================================================================
  // RENDER
  // =============================================================================

  return (
    <div
      className={`flex gap-2 ${isUser ? 'justify-end' : 'justify-start'} ${className}`}
    >
      {/* Bot Avatar - App Logo */}
      {isBot && (
        <div className="flex-shrink-0 h-8 w-8 rounded-full bg-white flex items-center justify-center overflow-hidden border border-border">
          <Image
            src="/icon_facil.png"
            alt="Facil"
            width={24}
            height={24}
            className="h-6 w-6 object-contain"
          />
        </div>
      )}

      {/* Message Bubble */}
      <div className={`${isUser ? 'max-w-[75%]' : 'max-w-[90%]'} group relative`}>
        <div
          className={`rounded-lg p-3 ${
            isUser
              ? 'bg-primary text-white'
              : 'bg-muted text-foreground'
          }`}
        >
          {/* Message Content */}
          {isBot ? (
            <div
              className="text-sm prose prose-sm max-w-none prose-li:my-0 prose-ul:my-0.5 prose-ol:my-0.5 prose-p:my-0.5 prose-headings:my-1 [&_li]:leading-snug [&_p]:leading-snug [&_br+br]:hidden"
              dangerouslySetInnerHTML={{ __html: sanitizeHtml(renderMarkdown(message.content)) }}
            />
          ) : (
            <p className="text-sm whitespace-pre-wrap">{message.content}</p>
          )}

          {/* Action Buttons — inline CTAs from tool results */}
          {isBot && message.actions && message.actions.length > 0 && (
            <div className="flex flex-wrap gap-2 mt-3 pt-2 border-t border-stone-200/50 dark:border-stone-700/50">
              {message.actions.map((action: ChatAction, i: number) => {
                const labelText = resolveActionLabel(action)

                // `open_settings` with a live handler → in-place panel (authenticated chat)
                if (action.type === 'open_settings' && onOpenAgentPanel) {
                  return (
                    <Button
                      key={i}
                      type="button"
                      size="sm"
                      variant="default"
                      className="h-8 text-xs gap-1.5"
                      onClick={() => onOpenAgentPanel(action.permission_type)}
                    >
                      <Settings className="h-3 w-3" strokeWidth={1.5} />
                      {labelText}
                    </Button>
                  )
                }

                // `confirm_executive` → Level 3 per-action consent modal
                // (authenticated chat only; silently skipped if no handler)
                if (action.type === 'confirm_executive') {
                  if (!onConfirmExecutive || !action.confirmation_code) return null
                  return (
                    <Button
                      key={i}
                      type="button"
                      size="sm"
                      variant="destructive"
                      className="h-8 text-xs gap-1.5"
                      onClick={() => onConfirmExecutive(action)}
                    >
                      <AlertTriangle className="h-3 w-3" strokeWidth={1.5} />
                      {labelText}
                    </Button>
                  )
                }

                // Everything else → <a href> (skip actions without valid URL to
                // avoid dead links, e.g. the pure-informational `appointment_booked`)
                if (!action.url || !action.url.startsWith('/')) return null

                return (
                  <a
                    key={i}
                    href={action.url}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors no-underline"
                  >
                    {(action.type === 'start_workflow' || action.type === 'open_wizard') && (
                      <ExternalLink className="h-3 w-3" />
                    )}
                    {action.type === 'open_settings' && <Settings className="h-3 w-3" />}
                    {labelText}
                  </a>
                )
              })}
            </div>
          )}

          {/* Timestamp */}
          <p className={`text-xs mt-1 ${isUser ? 'opacity-80' : 'text-muted-foreground'}`}>
            {formatTimestamp(message.timestamp, locale)}
          </p>
        </div>

        {/* Action buttons — visible on hover */}
        {isBot && (
          <div className="flex items-center gap-0.5 mt-1 opacity-0 group-hover:opacity-100 transition-opacity">
            <Button
              size="icon"
              variant="ghost"
              className="h-7 w-7 text-stone-400 hover:text-stone-700"
              onClick={handleCopy}
              title={t('copyMessage') || 'Copy'}
            >
              {copied ? (
                <Check className="h-3.5 w-3.5 text-green-600" />
              ) : (
                <Copy className="h-3.5 w-3.5" strokeWidth={1.5} />
              )}
            </Button>
            <Button
              size="icon"
              variant="ghost"
              className="h-7 w-7 text-stone-400 hover:text-stone-700"
              onClick={handleDownloadMd}
              title="Download .md"
            >
              <FileText className="h-3.5 w-3.5" strokeWidth={1.5} />
            </Button>
            <Button
              size="icon"
              variant="ghost"
              className="h-7 w-7 text-stone-400 hover:text-stone-700"
              onClick={handleDownloadTxt}
              title="Download .txt"
            >
              <Download className="h-3.5 w-3.5" strokeWidth={1.5} />
            </Button>
            <div className="w-px h-4 bg-stone-200 dark:bg-stone-700 mx-0.5" />
            <Button
              size="icon"
              variant="ghost"
              className={`h-7 w-7 ${feedback === 'up' ? 'text-green-600' : 'text-stone-400 hover:text-stone-700'}`}
              onClick={() => handleFeedback('up')}
              disabled={feedback !== null}
              title="Helpful"
            >
              <ThumbsUp className="h-3.5 w-3.5" strokeWidth={1.5} />
            </Button>
            <Button
              size="icon"
              variant="ghost"
              className={`h-7 w-7 ${feedback === 'down' ? 'text-red-500' : 'text-stone-400 hover:text-stone-700'}`}
              onClick={() => handleFeedback('down')}
              disabled={feedback !== null}
              title="Not helpful"
            >
              <ThumbsDown className="h-3.5 w-3.5" strokeWidth={1.5} />
            </Button>
          </div>
        )}
      </div>

      {/* User Avatar */}
      {isUser && (
        <div className="flex-shrink-0 h-8 w-8 rounded-full bg-primary flex items-center justify-center">
          <User className="h-4 w-4 text-white" />
        </div>
      )}
    </div>
  )
}

export default MessageItem
