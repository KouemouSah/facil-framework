'use client'

/**
 * SessionTimer - Displays countdown for cache-first wizard session TTL.
 *
 * Shows time remaining, turns orange at 5 minutes, red when expired.
 * Can be placed in the wizard header bar.
 *
 * @since v2.0 - Cache-first wizard migration
 */

import { Clock, AlertTriangle } from 'lucide-react'
import { cn } from '@/lib/utils'

export interface SessionTimerProps {
  /** Seconds remaining on the session */
  timeRemaining: number
  /** Whether session is in the expiring warning zone (< 5 min) */
  isExpiring: boolean
  /** Whether session has expired */
  isExpired: boolean
  /** Optional callback when expired */
  onExpired?: () => void
  /** Optional locale for labels */
  locale?: 'es' | 'fr' | 'en'
}

const LABELS = {
  es: {
    sessionExpires: 'La sesion expira pronto',
    sessionExpired: 'Sesion expirada',
    remaining: 'restante',
  },
  fr: {
    sessionExpires: 'La session expire bientot',
    sessionExpired: 'Session expiree',
    remaining: 'restant',
  },
  en: {
    sessionExpires: 'Session expires soon',
    sessionExpired: 'Session expired',
    remaining: 'remaining',
  },
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}:${s.toString().padStart(2, '0')}`
}

export function SessionTimer({
  timeRemaining,
  isExpiring,
  isExpired,
  locale = 'es',
}: SessionTimerProps) {
  const l = LABELS[locale] || LABELS.es

  if (isExpired) {
    return (
      <div className="flex items-center gap-2 text-sm font-medium text-destructive">
        <AlertTriangle className="h-4 w-4" />
        <span>{l.sessionExpired}</span>
      </div>
    )
  }

  return (
    <div
      className={cn(
        'flex items-center gap-2 text-sm',
        isExpiring
          ? 'text-orange-600 dark:text-orange-400 font-medium animate-pulse'
          : 'text-muted-foreground'
      )}
    >
      <Clock className="h-4 w-4" />
      <span className="tabular-nums">{formatTime(timeRemaining)}</span>
      {isExpiring && (
        <span className="text-xs">({l.sessionExpires})</span>
      )}
    </div>
  )
}
