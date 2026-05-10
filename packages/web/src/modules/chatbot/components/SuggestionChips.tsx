/**
 * SuggestionChips Component
 * Quick action chips from AI suggestions
 */

'use client'

import React from 'react'
import { useTranslations } from 'next-intl'
import { Badge } from '@/components/ui/badge'
import { Lightbulb } from 'lucide-react'

export interface SuggestionChipsProps {
  suggestions: string[]
  onSelect: (suggestion: string) => void
  maxVisible?: number
  className?: string
}

export const SuggestionChips: React.FC<SuggestionChipsProps> = ({
  suggestions,
  onSelect,
  maxVisible = 3,
  className = '',
}) => {
  const t = useTranslations('chatbot')

  if (suggestions.length === 0) return null

  return (
    <div className={`px-4 py-2 border-t bg-muted/30 ${className}`}>
      <div className="text-xs font-medium mb-2 text-muted-foreground flex items-center gap-1">
        <Lightbulb className="h-3 w-3" />
        {t('suggestions') || 'Suggestions'}
      </div>
      <div className="flex flex-wrap gap-1">
        {suggestions.slice(0, maxVisible).map((suggestion, i) => (
          <Badge
            key={i}
            variant="secondary"
            className="cursor-pointer hover:bg-secondary/80 text-xs transition-colors"
            onClick={() => onSelect(suggestion)}
          >
            {suggestion}
          </Badge>
        ))}
      </div>
    </div>
  )
}

export default SuggestionChips
