/**
 * TypingIndicator Component
 * Animated "Bot is typing..." indicator with contextual status messages
 */

'use client'

import React from 'react'
import { useTranslations } from 'next-intl'
import { Bot, Search, Brain, Sparkles } from 'lucide-react'

interface TypingIndicatorProps {
  statusText?: string
  statusStep?: string
}

const STEP_ICONS: Record<string, React.ElementType> = {
  searching: Search,
  analyzing: Brain,
  generating: Sparkles,
}

export const TypingIndicator: React.FC<TypingIndicatorProps> = ({
  statusText,
  statusStep,
}) => {
  const t = useTranslations('chatbot')
  const StepIcon = (statusStep && STEP_ICONS[statusStep]) || null

  return (
    <div className="flex gap-2 justify-start">
      <div className="flex-shrink-0 h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center">
        <Bot className="h-4 w-4 text-primary" />
      </div>
      <div className="bg-muted rounded-lg p-3 flex items-center gap-2">
        <div className="flex gap-1">
          <span className="h-2 w-2 bg-primary/60 rounded-full animate-bounce [animation-delay:-0.3s]" />
          <span className="h-2 w-2 bg-primary/60 rounded-full animate-bounce [animation-delay:-0.15s]" />
          <span className="h-2 w-2 bg-primary/60 rounded-full animate-bounce" />
        </div>
        {statusText ? (
          <span className="text-xs text-muted-foreground ml-1 flex items-center gap-1.5 animate-in fade-in duration-300">
            {StepIcon && <StepIcon className="h-3 w-3" />}
            {statusText}
          </span>
        ) : (
          <span className="text-xs text-muted-foreground ml-1">{t('typing') || 'Typing...'}</span>
        )}
      </div>
    </div>
  )
}

export default TypingIndicator
