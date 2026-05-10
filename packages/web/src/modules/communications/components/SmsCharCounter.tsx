/**
 * SmsCharCounter Component
 * Real-time character count and SMS segment calculator
 */

'use client'

import { useMemo } from 'react'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { MessageSquare, FileText, AlertCircle } from 'lucide-react'

interface SmsCharCounterProps {
  content: string
  maxSegments?: number
  className?: string
}

// GSM-7 character set for proper calculation
const GSM7_BASIC = new Set(
  "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?" +
  "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà".split('')
)

const GSM7_EXTENDED = new Set("^{}\\[~]|€".split(''))

function usesUnicode(text: string): boolean {
  for (const char of text) {
    if (!GSM7_BASIC.has(char) && !GSM7_EXTENDED.has(char)) {
      return true
    }
  }
  return false
}

function calculateSegments(content: string): {
  characterCount: number
  segmentCount: number
  charactersPerSegment: number
  charactersRemaining: number
  usesUnicode: boolean
} {
  const length = content.length
  const unicode = usesUnicode(content)

  const charsPerSegment = unicode ? 70 : 160
  const charsPerSegmentConcat = unicode ? 67 : 153

  let segmentCount: number
  let charactersRemaining: number

  if (length === 0) {
    segmentCount = 0
    charactersRemaining = charsPerSegment
  } else if (length <= charsPerSegment) {
    segmentCount = 1
    charactersRemaining = charsPerSegment - length
  } else {
    segmentCount = Math.ceil(length / charsPerSegmentConcat)
    const charsUsedInLast = length % charsPerSegmentConcat || charsPerSegmentConcat
    charactersRemaining = charsPerSegmentConcat - charsUsedInLast
  }

  return {
    characterCount: length,
    segmentCount,
    charactersPerSegment: segmentCount <= 1 ? charsPerSegment : charsPerSegmentConcat,
    charactersRemaining,
    usesUnicode: unicode,
  }
}

export function SmsCharCounter({ content, maxSegments = 10, className }: SmsCharCounterProps) {
  const stats = useMemo(() => calculateSegments(content), [content])

  const isOverLimit = maxSegments && stats.segmentCount > maxSegments
  const isWarning = maxSegments && stats.segmentCount >= maxSegments - 1

  return (
    <Card className={`p-4 ${className || ''}`}>
      <div className="space-y-3">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <MessageSquare className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm font-medium">SMS Character Count</span>
          </div>
          {stats.usesUnicode && (
            <Badge variant="secondary" className="text-xs">
              Unicode
            </Badge>
          )}
        </div>

        {/* Statistics Grid */}
        <div className="grid grid-cols-3 gap-4">
          {/* Character Count */}
          <div className="text-center">
            <div className="text-2xl font-bold">{stats.characterCount}</div>
            <div className="text-xs text-muted-foreground">Characters</div>
          </div>

          {/* Segment Count */}
          <div className="text-center">
            <div className={`text-2xl font-bold ${
              isOverLimit ? 'text-destructive' : isWarning ? 'text-yellow-600' : 'text-primary'
            }`}>
              {stats.segmentCount}
            </div>
            <div className="text-xs text-muted-foreground">
              Segments {maxSegments && `(max: ${maxSegments})`}
            </div>
          </div>

          {/* Remaining Characters */}
          <div className="text-center">
            <div className="text-2xl font-bold text-muted-foreground">
              {stats.charactersRemaining}
            </div>
            <div className="text-xs text-muted-foreground">Remaining</div>
          </div>
        </div>

        {/* Progress Bar */}
        <div className="space-y-1">
          <div className="h-2 bg-muted rounded-full overflow-hidden">
            <div
              className={`h-full transition-all duration-300 ${
                isOverLimit
                  ? 'bg-destructive'
                  : isWarning
                  ? 'bg-yellow-500'
                  : 'bg-primary'
              }`}
              style={{
                width: `${Math.min(
                  100,
                  ((stats.characterCount % stats.charactersPerSegment) /
                    stats.charactersPerSegment) *
                    100
                )}%`,
              }}
            />
          </div>
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>{stats.characterCount % stats.charactersPerSegment} / {stats.charactersPerSegment} in current segment</span>
            <span className="flex items-center gap-1">
              <FileText className="h-3 w-3" />
              {stats.charactersPerSegment} chars/segment
            </span>
          </div>
        </div>

        {/* Warning Messages */}
        {isOverLimit && (
          <div className="flex items-start gap-2 p-3 bg-destructive/10 rounded-lg">
            <AlertCircle className="h-4 w-4 text-destructive mt-0.5" />
            <div className="text-sm">
              <p className="font-medium text-destructive">Segment limit exceeded</p>
              <p className="text-muted-foreground">
                Content exceeds maximum of {maxSegments} segments. Please reduce the text length.
              </p>
            </div>
          </div>
        )}

        {isWarning && !isOverLimit && (
          <div className="flex items-start gap-2 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
            <AlertCircle className="h-4 w-4 text-yellow-600 mt-0.5" />
            <div className="text-sm">
              <p className="font-medium text-yellow-800">Approaching limit</p>
              <p className="text-yellow-700">
                You&apos;re close to the maximum segment limit. Consider shortening the message.
              </p>
            </div>
          </div>
        )}

        {/* Info Message */}
        {stats.usesUnicode && (
          <div className="text-xs text-muted-foreground bg-muted p-2 rounded">
            <strong>Unicode mode:</strong> Your message contains special characters, limiting
            segments to {stats.charactersPerSegment} characters each.
          </div>
        )}
      </div>
    </Card>
  )
}
