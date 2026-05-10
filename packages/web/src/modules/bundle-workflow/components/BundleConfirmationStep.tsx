'use client'

import { CheckCircle2, Home, FileText } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { Badge } from '@/components/ui/badge'
import Link from 'next/link'
import type { UseBundleWizardReturn } from '../hooks/useBundleWizard'

interface BundleConfirmationStepProps {
  wizard: UseBundleWizardReturn
  locale: string
}

const labels = {
  success: {
    es: 'Pago registrado exitosamente',
    fr: 'Paiement enregistre avec succes',
    en: 'Payment registered successfully',
  },
  reference: {
    es: 'Referencia de pago',
    fr: 'Reference de paiement',
    en: 'Payment reference',
  },
  amount: {
    es: 'Monto total',
    fr: 'Montant total',
    en: 'Total amount',
  },
  obligations: {
    es: 'Obligaciones',
    fr: 'Obligations',
    en: 'Obligations',
  },
  mode: {
    es: 'Modo',
    fr: 'Mode',
    en: 'Mode',
  },
  nextSteps: {
    es: 'Proximos pasos',
    fr: 'Prochaines etapes',
    en: 'Next steps',
  },
  step1: {
    es: 'Un agente validara su pago (1-3 dias habiles).',
    fr: 'Un agent validera votre paiement (1-3 jours ouvrables).',
    en: 'An agent will validate your payment (1-3 business days).',
  },
  step2: {
    es: 'Cada entidad procesara su obligacion correspondiente.',
    fr: 'Chaque entite traitera son obligation correspondante.',
    en: 'Each entity will process its corresponding obligation.',
  },
  step3: {
    es: 'Recibira su licencia comercial por email cuando todo este completo.',
    fr: 'Vous recevrez votre licence commerciale par email une fois tout termine.',
    en: 'You will receive your commercial license by email when everything is complete.',
  },
  pendingWarning: {
    es: 'Si tiene obligaciones pendientes, puede pagarlas iniciando un nuevo flujo.',
    fr: 'Si vous avez des obligations en attente, vous pouvez les payer en initiant un nouveau flux.',
    en: 'If you have pending obligations, you can pay them by starting a new flow.',
  },
  viewRequests: {
    es: 'Ver mis solicitudes',
    fr: 'Voir mes demandes',
    en: 'View my requests',
  },
  backToDashboard: {
    es: 'Volver al Dashboard',
    fr: 'Retour au tableau de bord',
    en: 'Back to Dashboard',
  },
  modeLabels: {
    per_line: { es: 'Por linea', fr: 'Par ligne', en: 'Per line' },
    consolidated: { es: 'Consolide', fr: 'Consolide', en: 'Consolidated' },
  },
} as const

function formatXAF(amount: number): string {
  return new Intl.NumberFormat('es-GQ', {
    style: 'decimal',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount)
}

export function BundleConfirmationStep({ wizard, locale }: BundleConfirmationStepProps) {
  const lang = (locale === 'fr' ? 'fr' : locale === 'en' ? 'en' : 'es') as 'es' | 'fr' | 'en'
  const result = wizard.paymentResult

  if (!result) return null

  // Get the message in the right language
  const message = lang === 'fr' ? result.messageFr
    : lang === 'en' ? result.messageEn
    : result.messageEs

  return (
    <div className="space-y-6 max-w-lg mx-auto text-center">
      {/* Success icon */}
      <div className="flex justify-center">
        <div className="h-16 w-16 rounded-full bg-green-100 dark:bg-green-900 flex items-center justify-center">
          <CheckCircle2 className="h-8 w-8 text-green-600" />
        </div>
      </div>

      <h2 className="text-xl font-semibold">{labels.success[lang]}</h2>

      {message && (
        <p className="text-sm text-muted-foreground">{message}</p>
      )}

      {/* Payment details */}
      <div className="rounded-lg border p-4 text-left space-y-3">
        <div className="flex justify-between text-sm">
          <span className="text-muted-foreground">{labels.reference[lang]}</span>
          <Badge variant="outline" className="font-mono">
            {result.paymentReference}
          </Badge>
        </div>
        <Separator />
        <div className="flex justify-between text-sm">
          <span className="text-muted-foreground">{labels.amount[lang]}</span>
          <span className="font-semibold tabular-nums">{formatXAF(result.totalAmount)} XAF</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-muted-foreground">{labels.obligations[lang]}</span>
          <span>{result.obligationsCount}</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-muted-foreground">{labels.mode[lang]}</span>
          <span>
            {labels.modeLabels[result.processingMode as keyof typeof labels.modeLabels]?.[lang]
              || result.processingMode}
          </span>
        </div>
      </div>

      {/* Next steps */}
      <div className="rounded-lg border p-4 text-left space-y-2">
        <h3 className="text-sm font-medium">{labels.nextSteps[lang]}</h3>
        <ol className="list-decimal list-inside text-sm text-muted-foreground space-y-1.5">
          <li>{labels.step1[lang]}</li>
          <li>{labels.step2[lang]}</li>
          <li>{labels.step3[lang]}</li>
        </ol>
        <p className="text-xs text-muted-foreground mt-3 italic">
          {labels.pendingWarning[lang]}
        </p>
      </div>

      {/* Actions */}
      <div className="flex flex-col sm:flex-row gap-3 justify-center">
        <Button variant="outline" asChild>
          <Link href={`/${locale}/dashboard/service-requests`}>
            <FileText className="h-4 w-4 mr-2" />
            {labels.viewRequests[lang]}
          </Link>
        </Button>
        <Button asChild>
          <Link href={`/${locale}/dashboard`}>
            <Home className="h-4 w-4 mr-2" />
            {labels.backToDashboard[lang]}
          </Link>
        </Button>
      </div>
    </div>
  )
}
