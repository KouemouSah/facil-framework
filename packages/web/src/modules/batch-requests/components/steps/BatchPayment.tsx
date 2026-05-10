'use client'

import { useState, useEffect } from 'react'
import { useLocale, useTranslations } from 'next-intl'
import {
  CreditCard,
  Banknote,
  Smartphone,
  Loader2,
  AlertCircle,
  CheckCircle,
  Users,
  UserX,
  ArrowRight,
  RefreshCw,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription } from '@/components/ui/alert'
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import type { UseBatchSessionReturn } from '../../hooks/useBatchSession'

const PAYMENT_METHOD_ICONS: Record<string, typeof CreditCard> = {
  mobile_money: Smartphone,
  card: CreditCard,
  bank_transfer: Banknote,
  cash: Banknote,
}

interface BatchPaymentProps {
  hook: UseBatchSessionReturn
  onSuccess: (batchId: string, redirectUrl?: string) => void
}

export function BatchPayment({ hook, onSuccess }: BatchPaymentProps) {
  const {
    isLoading,
    isSaving,
    isExpired,
    preparePaymentResult,
    preparePayment,
    submitBatch,
    goBack,
  } = hook
  const t = useTranslations('batch')
  const locale = useLocale()

  const [selectedMethod, setSelectedMethod] = useState<string | null>(null)
  const [phoneNumber, setPhoneNumber] = useState('')
  const [isPreparing, setIsPreparing] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [retryCount, setRetryCount] = useState(0)

  // Reset retry count when payment method changes
  useEffect(() => {
    setRetryCount(0)
    setSubmitError(null)
  }, [selectedMethod])

  // Auto-prepare on mount
  useEffect(() => {
    if (!preparePaymentResult) {
      setIsPreparing(true)
      preparePayment().finally(() => setIsPreparing(false))
    }
  }, [preparePaymentResult, preparePayment])

  const handleSubmit = async () => {
    if (!selectedMethod) return
    if (isExpired) {
      setSubmitError(t('payment.sessionExpired'))
      return
    }

    const needsPhone =
      selectedMethod === 'mobile_money' && !phoneNumber.trim()
    if (needsPhone) return

    setSubmitError(null)

    const result = await submitBatch({
      paymentMethod: selectedMethod,
      phoneNumber: phoneNumber || undefined,
    })

    if (result) {
      onSuccess(result.batchId, result.redirectUrl)
    } else if (hook.error) {
      setSubmitError(hook.error)
      setRetryCount((c) => c + 1)
    }
  }

  const handleRetry = () => {
    setSubmitError(null)
    handleSubmit()
  }

  const handleSwitchToCash = () => {
    setSubmitError(null)
    setSelectedMethod('cash')
  }

  // Loading state
  if (isPreparing || (isLoading && !preparePaymentResult)) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-blue-500" />
        <span className="ml-2 text-gray-500">{t('payment.calculatingTariff')}</span>
      </div>
    )
  }

  if (!preparePaymentResult) {
    return (
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>
          {t('payment.tariffError')}
        </AlertDescription>
      </Alert>
    )
  }

  const {
    readyCount,
    excludedCount,
    excludedBeneficiaries,
    totalAmount,
    perItemAmount,
    currency,
    paymentMethods,
  } = preparePaymentResult

  const formatAmount = (amount: number) =>
    new Intl.NumberFormat(locale === 'fr' ? 'fr-FR' : locale === 'en' ? 'en-US' : 'es-GQ', {
      style: 'currency',
      currency: currency,
      minimumFractionDigits: 0,
    }).format(amount)

  // Payment method labels from i18n (keys exist in all 3 languages)
  const PAYMENT_METHOD_LABELS: Record<string, string> = {
    mobile_money: 'BANGE Mobile Money',
    card: 'Tarjeta bancaria',
    bank_transfer: 'Transferencia bancaria',
    cash: 'Efectivo',
  }
  const PAYMENT_METHOD_DESCS: Record<string, string> = {
    mobile_money: 'Pago mediante BANGE Mobile Money',
    card: 'Pago con tarjeta de crédito o débito',
    bank_transfer: 'Transferencia bancaria directa',
    cash: 'Pago en efectivo en oficina',
  }
  const getMethodLabel = (method: string): string =>
    PAYMENT_METHOD_LABELS[method] || method
  const getMethodDescription = (method: string): string =>
    PAYMENT_METHOD_DESCS[method] || ''

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <CreditCard className="h-5 w-5 text-blue-600" />
        <h2 className="text-lg font-semibold">{t('payment.title')}</h2>
      </div>

      {/* Summary */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">{t('payment.summary')}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Users className="h-4 w-4 text-green-600" />
              <span className="text-sm">{t('payment.readyBeneficiaries')}</span>
            </div>
            <Badge className="bg-green-100 text-green-700">
              {readyCount}
            </Badge>
          </div>

          {excludedCount > 0 && (
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <UserX className="h-4 w-4 text-red-500" />
                <span className="text-sm">{t('payment.excluded')}</span>
              </div>
              <Badge className="bg-red-100 text-red-700">
                {excludedCount}
              </Badge>
            </div>
          )}

          {perItemAmount !== null && (
            <div className="flex items-center justify-between text-sm text-gray-500">
              <span>{t('payment.perItem')}</span>
              <span>{formatAmount(perItemAmount)}</span>
            </div>
          )}

          <div className="border-t pt-3 flex items-center justify-between">
            <span className="font-semibold">{t('payment.totalToPay')}</span>
            <span className="text-xl font-bold text-blue-600">
              {formatAmount(totalAmount)}
            </span>
          </div>
        </CardContent>
      </Card>

      {/* Excluded beneficiaries warning */}
      {excludedCount > 0 && (
        <Alert className="border-amber-200 bg-amber-50">
          <AlertCircle className="h-4 w-4 text-amber-600" />
          <AlertDescription className="text-amber-700">
            <p className="font-medium mb-1">
              {excludedCount} {t('payment.excludedWarning')}:
            </p>
            <ul className="text-xs space-y-0.5">
              {excludedBeneficiaries.slice(0, 5).map((b) => (
                <li key={b.id}>
                  {b.name} {'\u2014'} {b.reason}
                </li>
              ))}
              {excludedBeneficiaries.length > 5 && (
                <li>
                  ... +{excludedBeneficiaries.length - 5}
                </li>
              )}
            </ul>
          </AlertDescription>
        </Alert>
      )}

      {/* Payment method selection */}
      {totalAmount > 0 && (
        <div className="space-y-3">
          <Label>{t('payment.selectMethod')}</Label>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {paymentMethods.map((method) => {
              const Icon = PAYMENT_METHOD_ICONS[method] || CreditCard
              const isSelected = selectedMethod === method

              return (
                <button
                  key={method}
                  className={`flex items-center gap-3 p-4 border rounded-lg text-left transition-all ${
                    isSelected
                      ? 'border-blue-500 bg-blue-50 ring-2 ring-blue-200'
                      : 'hover:border-gray-300'
                  }`}
                  onClick={() => setSelectedMethod(method)}
                >
                  <Icon
                    className={`h-5 w-5 ${
                      isSelected ? 'text-blue-600' : 'text-gray-400'
                    }`}
                  />
                  <div>
                    <p className="text-sm font-medium">{getMethodLabel(method)}</p>
                    <p className="text-xs text-gray-400">
                      {getMethodDescription(method)}
                    </p>
                  </div>
                  {isSelected && (
                    <CheckCircle className="h-4 w-4 text-blue-500 ml-auto" />
                  )}
                </button>
              )
            })}
          </div>
        </div>
      )}

      {/* Phone number for mobile money */}
      {selectedMethod === 'mobile_money' && (
        <div className="space-y-2">
          <Label>{t('payment.phoneNumber')}</Label>
          <Input
            type="tel"
            value={phoneNumber}
            onChange={(e) => setPhoneNumber(e.target.value)}
            placeholder="+240..."
          />
        </div>
      )}

      {/* Error with retry + switch-to-cash */}
      {submitError && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            <p className="font-medium mb-2">{submitError}</p>
            <div className="flex gap-2 mt-2">
              {retryCount < 3 && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={handleRetry}
                  disabled={isSaving}
                  className="text-xs"
                >
                  <RefreshCw className="h-3 w-3 mr-1" />
                  {t('payment.retry')}
                </Button>
              )}
              {selectedMethod !== 'cash' &&
                paymentMethods.includes('cash') && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={handleSwitchToCash}
                  disabled={isSaving}
                  className="text-xs"
                >
                  <Banknote className="h-3 w-3 mr-1" />
                  {t('payment.switchToCash')}
                </Button>
              )}
            </div>
          </AlertDescription>
        </Alert>
      )}

      {/* Actions */}
      <div className="flex justify-between pt-4">
        <Button variant="outline" onClick={goBack}>
          {t('wizard.previous')}
        </Button>
        <Button
          onClick={handleSubmit}
          disabled={
            isSaving ||
            (totalAmount > 0 && !selectedMethod) ||
            (selectedMethod === 'mobile_money' && !phoneNumber.trim())
          }
          size="lg"
        >
          {isSaving ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin mr-2" />
              {t('payment.processing')}
            </>
          ) : totalAmount === 0 ? (
            <>
              {t('payment.sendRequests')}
              <ArrowRight className="h-4 w-4 ml-2" />
            </>
          ) : (
            <>
              {t('payment.pay')} {formatAmount(totalAmount)}
              <ArrowRight className="h-4 w-4 ml-2" />
            </>
          )}
        </Button>
      </div>
    </div>
  )
}
