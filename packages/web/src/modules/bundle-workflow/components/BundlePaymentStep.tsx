'use client'

import { Loader2, Smartphone, Landmark, CreditCard } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'
import { CompanyInfoCard } from './CompanyInfoCard'
import { BundleErrorAlert } from './BundleErrorAlert'
import type { UseBundleWizardReturn } from '../hooks/useBundleWizard'

interface BundlePaymentStepProps {
  wizard: UseBundleWizardReturn
  locale: string
}

const labels = {
  title: {
    es: 'Pago de Obligaciones',
    fr: 'Paiement des Obligations',
    en: 'Obligations Payment',
  },
  summary: {
    es: 'Resumen',
    fr: 'Resume',
    en: 'Summary',
  },
  obligations: {
    es: 'obligaciones seleccionadas',
    fr: 'obligations selectionnees',
    en: 'selected obligations',
  },
  totalToPay: {
    es: 'Total a pagar',
    fr: 'Total a payer',
    en: 'Total to pay',
  },
  paymentMethod: {
    es: 'Metodo de pago',
    fr: 'Methode de paiement',
    en: 'Payment method',
  },
  mobileMoney: {
    es: 'Mobile Money (BANGE)',
    fr: 'Mobile Money (BANGE)',
    en: 'Mobile Money (BANGE)',
  },
  mobileMoneyDesc: {
    es: 'Pago instantaneo con su wallet BANGE',
    fr: 'Paiement instantane avec votre portefeuille BANGE',
    en: 'Instant payment with your BANGE wallet',
  },
  cash: {
    es: 'Pago en agencia (efectivo)',
    fr: 'Paiement en agence (especes)',
    en: 'Agency payment (cash)',
  },
  cashDesc: {
    es: 'Presente el recibo en una agencia del Tesoro',
    fr: 'Presentez le recu dans une agence du Tresor',
    en: 'Present the receipt at a Treasury agency',
  },
  phone: {
    es: 'Numero de telefono',
    fr: 'Numero de telephone',
    en: 'Phone number',
  },
  phonePlaceholder: {
    es: '+240 XXX XXX XXX',
    fr: '+240 XXX XXX XXX',
    en: '+240 XXX XXX XXX',
  },
  pay: {
    es: 'Pagar',
    fr: 'Payer',
    en: 'Pay',
  },
  processing: {
    es: 'Procesando pago...',
    fr: 'Traitement du paiement...',
    en: 'Processing payment...',
  },
  mode: {
    per_line: { es: 'Por linea', fr: 'Par ligne', en: 'Per line' },
    consolidated: { es: 'Consolidado', fr: 'Consolide', en: 'Consolidated' },
  },
} as const

function formatXAF(amount: number): string {
  return new Intl.NumberFormat('es-GQ', {
    style: 'decimal',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount)
}

const paymentMethods = [
  {
    id: 'mobile_money',
    icon: Smartphone,
    label: labels.mobileMoney,
    description: labels.mobileMoneyDesc,
  },
  {
    id: 'cash',
    icon: Landmark,
    label: labels.cash,
    description: labels.cashDesc,
  },
]

export function BundlePaymentStep({ wizard, locale }: BundlePaymentStepProps) {
  const lang = (locale === 'fr' ? 'fr' : locale === 'en' ? 'en' : 'es') as 'es' | 'fr' | 'en'

  if (!wizard.licenseData) return null

  const selectedObligations = wizard.licenseData.obligations.filter(
    o => wizard.selectedObligationIds.has(o.id)
  )
  const totalAmount = selectedObligations.reduce((sum, o) => sum + o.total, 0)

  // Processing state
  if (wizard.isPaymentProcessing) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary mb-4" />
        <p className="text-sm text-muted-foreground">{labels.processing[lang]}</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {wizard.selectedCompany && (
        <CompanyInfoCard company={wizard.selectedCompany} locale={locale} compact />
      )}

      <h2 className="text-lg font-semibold">{labels.title[lang]}</h2>

      {/* Summary */}
      <div className="rounded-lg border p-4 space-y-3">
        <h3 className="text-sm font-medium">{labels.summary[lang]}</h3>
        <div className="text-sm text-muted-foreground">
          {labels.mode[wizard.selectedMode][lang]} · {selectedObligations.length}{' '}
          {labels.obligations[lang]}
        </div>
        <Separator />
        <div className="space-y-1">
          {selectedObligations.map(obl => (
            <div key={obl.id} className="flex justify-between text-sm">
              <span className="truncate mr-4">{obl.fiscalServiceName}</span>
              <span className="tabular-nums shrink-0">{formatXAF(obl.total)} XAF</span>
            </div>
          ))}
        </div>
        <Separator />
        <div className="flex justify-between font-semibold">
          <span>{labels.totalToPay[lang]}</span>
          <span className="tabular-nums">{formatXAF(totalAmount)} XAF</span>
        </div>
      </div>

      {/* Payment method selection */}
      <div>
        <h3 className="text-sm font-medium mb-3">{labels.paymentMethod[lang]}</h3>
        <div className="grid gap-3">
          {paymentMethods.map(method => {
            const Icon = method.icon
            const isSelected = wizard.paymentMethod === method.id
            return (
              <div
                key={method.id}
                className={`flex items-start gap-3 p-4 rounded-lg border cursor-pointer transition-colors ${
                  isSelected
                    ? 'border-primary bg-primary/5'
                    : 'border-border hover:border-primary/30'
                }`}
                onClick={() => wizard.setPaymentMethod(method.id)}
              >
                <div className={`h-10 w-10 rounded-lg flex items-center justify-center shrink-0 ${
                  isSelected ? 'bg-primary/10' : 'bg-muted'
                }`}>
                  <Icon className={`h-5 w-5 ${isSelected ? 'text-primary' : 'text-muted-foreground'}`} />
                </div>
                <div>
                  <p className="font-medium text-sm">{method.label[lang]}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {method.description[lang]}
                  </p>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Phone input (mobile_money) */}
      {wizard.paymentMethod === 'mobile_money' && (
        <div className="space-y-2">
          <Label htmlFor="phone">{labels.phone[lang]}</Label>
          <Input
            id="phone"
            type="tel"
            value={wizard.phoneNumber}
            onChange={(e) => wizard.setPhoneNumber(e.target.value)}
            placeholder={labels.phonePlaceholder[lang]}
          />
        </div>
      )}

      {/* Error — structured actionable alert (retry / back / support) */}
      <BundleErrorAlert
        error={wizard.apiError}
        locale={locale}
        onRetry={wizard.retryPayment}
        onBack={wizard.goBack}
        onClear={wizard.clearError}
      />

      {/* Pay button */}
      <Button
        className="w-full h-12 text-base"
        disabled={!wizard.canGoNext || wizard.isPaymentProcessing}
        onClick={wizard.submitPayment}
      >
        <CreditCard className="h-5 w-5 mr-2" />
        {labels.pay[lang]} {formatXAF(totalAmount)} XAF
      </Button>
    </div>
  )
}
