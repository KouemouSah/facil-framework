'use client'

/**
 * BundleErrorAlert — structured error surface for bundle-workflow steps.
 *
 * Renders title + localized backend message + optional hint + a single
 * actionable CTA (retry / back / support / inline-noop). The shape of
 * the error comes from core/api/errors::extractApiError and the
 * catalog entry from constants/error-catalog.
 *
 * Plan: .claude/plans/BUNDLE_DEBUG_PHASE3_PLAN.md §3.3
 */

import { AlertCircle, ArrowLeft, ExternalLink, LifeBuoy, RefreshCcw, X } from 'lucide-react'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import type { StructuredApiError } from '@/core/api/errors'
import {
  getBundleErrorEntry,
  type BundleErrorCtaType,
} from '../constants/error-catalog'

interface BundleErrorAlertProps {
  error: StructuredApiError | null
  locale: string
  onRetry?: () => void
  onBack?: () => void
  onClear?: () => void
  /** Optional support URL (defaults to /dashboard/support for the locale) */
  supportUrl?: string
}

const CTA_LABELS: Record<
  BundleErrorCtaType,
  { es: string; fr: string; en: string }
> = {
  retry: { es: 'Reintentar', fr: 'Réessayer', en: 'Retry' },
  back: { es: 'Volver', fr: 'Retour', en: 'Back' },
  support: {
    es: 'Contactar soporte',
    fr: 'Contacter le support',
    en: 'Contact support',
  },
  inline: { es: 'Corregir', fr: 'Corriger', en: 'Fix' },
  none: { es: 'OK', fr: 'OK', en: 'OK' },
  view_request: {
    es: 'Ver mi solicitud',
    fr: 'Voir ma demande',
    en: 'View my request',
  },
}

const DISMISS_LABEL = {
  es: 'Cerrar',
  fr: 'Fermer',
  en: 'Dismiss',
}

export function BundleErrorAlert({
  error,
  locale,
  onRetry,
  onBack,
  onClear,
  supportUrl,
}: BundleErrorAlertProps) {
  if (!error) return null

  const lang = (locale === 'fr' ? 'fr' : locale === 'en' ? 'en' : 'es') as
    | 'es'
    | 'fr'
    | 'en'

  const entry = getBundleErrorEntry(error.code)
  const title = entry.title[lang]
  const hint = entry.hint?.[lang] ?? null

  const handleCta = () => {
    switch (entry.cta) {
      case 'retry':
        onRetry?.()
        break
      case 'back':
        onBack?.()
        break
      case 'support': {
        const href = supportUrl ?? `/${lang}/dashboard/support`
        if (typeof window !== 'undefined') window.location.href = href
        break
      }
      case 'view_request': {
        // Redirect to existing SR detail page (id from backend 409 response)
        const srId = error.raw?.existing_request_id
        if (srId && typeof window !== 'undefined') {
          window.location.href = `/${lang}/dashboard/service-requests/${srId}`
        } else {
          // Fallback: go to service requests list
          if (typeof window !== 'undefined') {
            window.location.href = `/${lang}/dashboard/service-requests`
          }
        }
        break
      }
      case 'inline':
      case 'none':
        onClear?.()
        break
    }
  }

  // Hide CTA button entirely for 'inline' (user fixes input in place)
  const showCtaButton = entry.cta !== 'inline' && entry.cta !== 'none'
  const ctaLabel = CTA_LABELS[entry.cta][lang]

  const Icon =
    entry.cta === 'retry'
      ? RefreshCcw
      : entry.cta === 'back'
      ? ArrowLeft
      : entry.cta === 'support'
      ? LifeBuoy
      : entry.cta === 'view_request'
      ? ExternalLink
      : AlertCircle

  return (
    <Alert variant="destructive" className="relative pr-10">
      <AlertCircle className="h-4 w-4" />
      <AlertDescription className="space-y-2">
        <p className="font-medium">{title}</p>
        <p className="text-sm opacity-90">{error.message}</p>
        {hint && <p className="text-xs opacity-75">{hint}</p>}
        {showCtaButton && (
          <div className="pt-2">
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={handleCta}
              className="gap-2"
            >
              <Icon className="h-4 w-4" />
              {ctaLabel}
            </Button>
          </div>
        )}
      </AlertDescription>
      {onClear && (
        <button
          type="button"
          onClick={onClear}
          aria-label={DISMISS_LABEL[lang]}
          className="absolute right-2 top-2 rounded-sm opacity-70 transition-opacity hover:opacity-100"
        >
          <X className="h-4 w-4" />
        </button>
      )}
    </Alert>
  )
}
