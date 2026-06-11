'use client'

import { useEffect, useState } from 'react'
import { useRouter, useParams, useSearchParams } from 'next/navigation'
import { Loader2, Receipt } from 'lucide-react'
import { wizardSessionApi } from '@/modules/service-requests/services/wizard-session-api'

const labels = {
  loading: {
    es: 'Iniciando flujo de pago...',
    fr: 'Demarrage du flux de paiement...',
    en: 'Starting payment flow...',
  },
  error: {
    es: 'Error al iniciar el flujo. Intente de nuevo.',
    fr: 'Erreur lors du demarrage du flux. Reessayez.',
    en: 'Error starting the flow. Please try again.',
  },
  title: {
    es: 'Pago de Obligaciones Fiscales',
    fr: 'Paiement des Obligations Fiscales',
    en: 'Fiscal Obligations Payment',
  },
} as const

/**
 * Entry page: creates a wizard session and redirects to the wizard page.
 * URL: /dashboard/bundle-payment
 * Redirects to: /dashboard/bundle-payment/[sessionId]
 */
export default function BundlePaymentEntryPage() {
  const router = useRouter()
  const params = useParams()
  const searchParams = useSearchParams()
  const locale = (params?.locale as string) || 'es'
  const lang = (locale === 'fr' ? 'fr' : locale === 'en' ? 'en' : 'es') as 'es' | 'fr' | 'en'

  // Deep-link: ?companyId=xxx pre-selects the company in the wizard
  // ?mode=new skips to upload step (for "Registrar nueva empresa")
  const companyId = searchParams.get('companyId')
  const mode = searchParams.get('mode')

  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function init() {
      try {
        const session = await wizardSessionApi.createSession({
          workflow_code: 'BUNDLE_PAYMENT',
          solicitud_type: 'expedicion',
        })
        if (!cancelled && session?.sessionId) {
          // Pass companyId and mode as query params to the wizard
          const qs = new URLSearchParams()
          if (companyId) qs.set('companyId', companyId)
          if (mode) qs.set('mode', mode)
          const qsStr = qs.toString()
          router.replace(`/${locale}/dashboard/bundle-payment/${session.sessionId}${qsStr ? '?' + qsStr : ''}`)
        }
      } catch (e) {
        if (!cancelled) {
          console.error('[BundlePayment] Session creation failed:', e)
          setError(labels.error[lang])
        }
      }
    }

    init()
    return () => { cancelled = true }
  }, [locale, lang, router])

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] text-center p-4">
        <Receipt className="h-12 w-12 text-muted-foreground mb-4" />
        <p className="text-sm text-destructive">{error}</p>
        <button
          className="mt-4 text-sm text-primary underline"
          onClick={() => { setError(null); window.location.reload() }}
        >
          {lang === 'fr' ? 'Reessayer' : lang === 'en' ? 'Try again' : 'Reintentar'}
        </button>
      </div>
    )
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-[50vh] text-center">
      <Loader2 className="h-8 w-8 animate-spin text-primary mb-4" />
      <p className="text-sm text-muted-foreground">{labels.loading[lang]}</p>
      <p className="text-xs text-muted-foreground mt-1">{labels.title[lang]}</p>
    </div>
  )
}
