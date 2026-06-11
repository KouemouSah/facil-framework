'use client'

/**
 * BANGE Payment Result Page
 *
 * After electronic payment (BANGE mobile_money/card/bank_transfer),
 * the payment gateway redirects the user back to this page.
 *
 * Flow:
 * 1. User pays on BANGE gateway
 * 2. BANGE redirects to: /dashboard/service-requests/{id}/payment/result?status=...
 * 3. This page polls GET /service-requests/{id}/payment/status
 * 4. Shows success/failure/pending state
 * 5. Navigates to service request detail
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import { useParams, useRouter, useSearchParams } from 'next/navigation'
import { useTranslations } from 'next-intl'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import {
  Loader2,
  CheckCircle,
  XCircle,
  Clock,
  ArrowRight,
  RefreshCw,
} from 'lucide-react'
import { serviceRequestsApi } from '@/modules/service-requests/services/api'

// ============================================================================
// CONSTANTS
// ============================================================================

const POLL_INTERVAL_MS = 3000
const MAX_POLL_ATTEMPTS = 20 // 60 seconds max polling
const INITIAL_DELAY_MS = 2000 // Wait for webhook to process

type PaymentState = 'loading' | 'success' | 'pending' | 'failed' | 'error'

// Translations now loaded from messages/{locale}.json via useTranslations('paymentResult')

// ============================================================================
// PAGE COMPONENT
// ============================================================================

export default function PaymentResultPage() {
  const params = useParams()
  const router = useRouter()
  const searchParams = useSearchParams()
  const requestId = params.id as string
  const locale = (params.locale as string) || 'es'

  const [state, setState] = useState<PaymentState>('loading')
  const [paymentInfo, setPaymentInfo] = useState<{
    amount?: number
    currency?: string
    reference?: string
  }>({})
  const pollCountRef = useRef(0)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const t = useTranslations('paymentResult')

  // Read BANGE query params (if any)
  const bangeStatus = searchParams.get('status')

  // If BANGE explicitly says failed/cancelled, skip polling
  const isBangeFailure = bangeStatus === 'failed' || bangeStatus === 'cancelled' || bangeStatus === 'error'

  const checkStatus = useCallback(async () => {
    try {
      const result = await serviceRequestsApi.checkPaymentStatus(requestId)

      if (result.paid || result.status === 'completed') {
        setState('success')
        setPaymentInfo({
          amount: (result as Record<string, unknown>).amount as number | undefined,
          currency: ((result as Record<string, unknown>).currency as string) || 'XAF',
        })
        return true // Stop polling
      }

      if (result.status === 'failed') {
        setState('failed')
        return true // Stop polling
      }

      // Still processing — continue polling
      return false
    } catch {
      // API error — don't stop polling yet, might be transient
      return false
    }
  }, [requestId])

  const startPolling = useCallback(() => {
    pollCountRef.current = 0

    const poll = async () => {
      pollCountRef.current++

      const done = await checkStatus()
      if (done) return

      if (pollCountRef.current >= MAX_POLL_ATTEMPTS) {
        // Max attempts reached — payment might still be processing via webhook
        setState('pending')
        return
      }

      timerRef.current = setTimeout(poll, POLL_INTERVAL_MS)
    }

    // Wait a bit for webhook to process before first check
    timerRef.current = setTimeout(poll, INITIAL_DELAY_MS)
  }, [checkStatus])

  useEffect(() => {
    if (isBangeFailure) {
      setState('failed')
      return
    }

    startPolling()

    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current)
      }
    }
  }, [isBangeFailure, startPolling])

  const handleRetry = useCallback(() => {
    setState('loading')
    if (timerRef.current) {
      clearTimeout(timerRef.current)
    }
    startPolling()
  }, [startPolling])

  const navigateToRequest = () => {
    router.push(`/${locale}/dashboard/service-requests/${requestId}`)
  }

  const navigateToList = () => {
    router.push(`/${locale}/dashboard/service-requests`)
  }

  // ============================================================================
  // RENDER
  // ============================================================================

  const stateConfig: Record<PaymentState, {
    icon: React.ReactNode
    bgColor: string
    title: string
    subtitle: string
  }> = {
    loading: {
      icon: <Loader2 className="h-10 w-10 text-primary animate-spin" />,
      bgColor: 'bg-primary/10',
      title: t('loading'),
      subtitle: t('loadingSubtitle'),
    },
    success: {
      icon: <CheckCircle className="h-10 w-10 text-green-600" />,
      bgColor: 'bg-green-100',
      title: t('success'),
      subtitle: t('successSubtitle'),
    },
    pending: {
      icon: <Clock className="h-10 w-10 text-amber-600" />,
      bgColor: 'bg-amber-100',
      title: t('pending'),
      subtitle: t('pendingSubtitle'),
    },
    failed: {
      icon: <XCircle className="h-10 w-10 text-red-600" />,
      bgColor: 'bg-red-100',
      title: t('failed'),
      subtitle: t('failedSubtitle'),
    },
    error: {
      icon: <XCircle className="h-10 w-10 text-gray-600" />,
      bgColor: 'bg-gray-100',
      title: t('error'),
      subtitle: t('errorSubtitle'),
    },
  }

  const config = stateConfig[state]

  return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <Card className="w-full max-w-md">
        <CardContent className="pt-8 pb-6 px-6">
          <div className="text-center space-y-4">
            {/* Status icon */}
            <div className={`mx-auto w-20 h-20 rounded-full flex items-center justify-center ${config.bgColor}`}>
              {config.icon}
            </div>

            {/* Title + subtitle */}
            <div className="space-y-2">
              <h2 className="text-xl font-semibold">{config.title}</h2>
              <p className="text-sm text-muted-foreground">{config.subtitle}</p>
            </div>

            {/* Payment info (when available) */}
            {state === 'success' && paymentInfo.amount && (
              <div className="border rounded-lg p-3 space-y-1 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">{t('amount')}</span>
                  <span className="font-bold">
                    {paymentInfo.amount.toLocaleString()} {paymentInfo.currency}
                  </span>
                </div>
              </div>
            )}

            {/* Loading progress indicator */}
            {state === 'loading' && (
              <div className="text-xs text-muted-foreground">
                {pollCountRef.current > 0 && `${pollCountRef.current}/${MAX_POLL_ATTEMPTS}`}
              </div>
            )}

            {/* Action buttons */}
            <div className="flex flex-col gap-3 pt-4">
              {(state === 'success' || state === 'pending') && (
                <Button onClick={navigateToRequest} className="w-full">
                  {t('viewRequest')}
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Button>
              )}

              {state === 'failed' && (
                <Button onClick={navigateToRequest} className="w-full">
                  {t('viewRequest')}
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Button>
              )}

              {(state === 'error' || state === 'pending') && (
                <Button variant="outline" onClick={handleRetry} className="w-full">
                  <RefreshCw className="mr-2 h-4 w-4" />
                  {t('retry')}
                </Button>
              )}

              <Button variant="ghost" size="sm" onClick={navigateToList}>
                {t('goToList')}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
