'use client'

/**
 * CitizenSummaryForm Component
 * Shows a summary of the service request for citizen review before submission
 * This is the "formulaire récapitulatif" that citizens see before final submission
 */

import { useState, useMemo, useCallback } from 'react'
import {
  CheckCircle,
  AlertCircle,
  AlertTriangle,
  Send,
  ArrowLeft,
  FileText,
  User,
  CreditCard,
  Clock,
  Shield,
  Edit2,
  Loader2,
  Download,
} from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Separator } from '@/components/ui/separator'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion'

import type { CitizenSummaryResponse } from '../types'

// ============================================================================
// PROPS
// ============================================================================

interface CitizenSummaryFormProps {
  summary: CitizenSummaryResponse
  onSubmit: () => Promise<void>
  onBack: () => void
  onEditDocuments: () => void
  onEditPersonalData: () => void
  onDownloadPDF?: () => Promise<void>
  isSubmitting?: boolean
  locale?: 'es' | 'fr' | 'en'
}

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

function formatCurrency(amount: number, currency: string = 'XAF'): string {
  return new Intl.NumberFormat('es-GQ', {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount)
}

function formatFieldLabel(key: string): string {
  return key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (l) => l.toUpperCase())
}

function formatFieldValue(value: unknown): string {
  if (value === null || value === undefined) return '-'
  if (typeof value === 'boolean') return value ? 'Sí' : 'No'
  if (Array.isArray(value)) return value.join(', ')
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

// ============================================================================
// MAIN COMPONENT
// ============================================================================

export function CitizenSummaryForm({
  summary,
  onSubmit,
  onBack,
  onEditDocuments,
  onEditPersonalData,
  onDownloadPDF,
  isSubmitting = false,
  locale = 'es',
}: CitizenSummaryFormProps) {
  // Confirmation checkbox state
  const [isConfirmed, setIsConfirmed] = useState(false)
  // PDF download state
  const [isDownloading, setIsDownloading] = useState(false)

  // Get personal data fields to display
  const personalDataFields = useMemo(() => {
    const fields: Array<{ key: string; value: unknown }> = []
    const data = summary.personalData || {}

    // Priority fields first
    const priorityKeys = [
      'nombres', 'apellidos', 'numero_dip', 'fecha_nacimiento',
      'lugar_nacimiento', 'nacionalidad', 'sexo', 'estado_civil',
      'profesion', 'domicilio'
    ]

    for (const key of priorityKeys) {
      if (data[key] !== undefined && data[key] !== null && data[key] !== '') {
        fields.push({ key, value: data[key] })
      }
    }

    // Then other fields
    for (const [key, value] of Object.entries(data)) {
      if (!priorityKeys.includes(key) && value !== null && value !== '' && value !== undefined) {
        fields.push({ key, value })
      }
    }

    return fields
  }, [summary.personalData])

  // Handle submit
  const handleSubmit = useCallback(async () => {
    if (!isConfirmed || !summary.canSubmit) return
    await onSubmit()
  }, [isConfirmed, summary.canSubmit, onSubmit])

  // Handle PDF download
  const handleDownloadPDF = useCallback(async () => {
    if (!onDownloadPDF || isDownloading) return
    setIsDownloading(true)
    try {
      await onDownloadPDF()
    } finally {
      setIsDownloading(false)
    }
  }, [onDownloadPDF, isDownloading])

  // Texts by locale
  const texts = {
    title: locale === 'es' ? 'Resumen de Solicitud' : locale === 'fr' ? 'Résumé de la Demande' : 'Request Summary',
    subtitle: locale === 'es' ? 'Revise los datos antes de enviar' : locale === 'fr' ? 'Vérifiez les données avant de soumettre' : 'Review data before submitting',
    personalData: locale === 'es' ? 'Datos Personales' : locale === 'fr' ? 'Données Personnelles' : 'Personal Data',
    documents: locale === 'es' ? 'Documentos Cargados' : locale === 'fr' ? 'Documents Téléchargés' : 'Uploaded Documents',
    tariff: locale === 'es' ? 'Desglose de Pago' : locale === 'fr' ? 'Détail du Paiement' : 'Payment Breakdown',
    warnings: locale === 'es' ? 'Advertencias' : locale === 'fr' ? 'Avertissements' : 'Warnings',
    blockers: locale === 'es' ? 'Problemas que Bloquean el Envío' : locale === 'fr' ? 'Problèmes Bloquants' : 'Blocking Issues',
    confirmLabel: locale === 'es'
      ? 'Confirmo que todos los datos son correctos y verdaderos'
      : locale === 'fr'
        ? 'Je confirme que toutes les données sont exactes et véridiques'
        : 'I confirm all data is correct and true',
    submit: locale === 'es' ? 'Enviar Solicitud' : locale === 'fr' ? 'Soumettre la Demande' : 'Submit Request',
    submitting: locale === 'es' ? 'Enviando...' : locale === 'fr' ? 'Envoi en cours...' : 'Submitting...',
    back: locale === 'es' ? 'Volver' : locale === 'fr' ? 'Retour' : 'Back',
    downloadPDF: locale === 'es' ? 'Descargar PDF' : locale === 'fr' ? 'Telecharger PDF' : 'Download PDF',
    downloading: locale === 'es' ? 'Descargando...' : locale === 'fr' ? 'Telechargement...' : 'Downloading...',
    edit: locale === 'es' ? 'Editar' : locale === 'fr' ? 'Modifier' : 'Edit',
    baseTariff: locale === 'es' ? 'Tarifa Base' : locale === 'fr' ? 'Tarif de Base' : 'Base Tariff',
    supplements: locale === 'es' ? 'Suplementos' : locale === 'fr' ? 'Suppléments' : 'Supplements',
    total: locale === 'es' ? 'Total a Pagar' : locale === 'fr' ? 'Total à Payer' : 'Total to Pay',
    validated: locale === 'es' ? 'Validado' : locale === 'fr' ? 'Validé' : 'Validated',
    pending: locale === 'es' ? 'Pendiente' : locale === 'fr' ? 'En attente' : 'Pending',
    documentsComplete: locale === 'es' ? 'Todos los documentos cargados' : locale === 'fr' ? 'Tous les documents téléchargés' : 'All documents uploaded',
    documentsMissing: locale === 'es' ? 'Faltan documentos requeridos' : locale === 'fr' ? 'Documents requis manquants' : 'Required documents missing',
    validationPassed: locale === 'es' ? 'Validación completada' : locale === 'fr' ? 'Validation terminée' : 'Validation complete',
    validationFailed: locale === 'es' ? 'Hay errores de validación' : locale === 'fr' ? 'Erreurs de validation' : 'Validation errors',
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold tracking-tight">{texts.title}</h2>
        <p className="text-muted-foreground">{texts.subtitle}</p>
      </div>

      {/* Request Info */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-lg">{summary.workflowNameEs}</CardTitle>
              <CardDescription>
                {summary.reference} · {summary.solicitudType}
                {summary.subType && ` · ${summary.subType}`}
              </CardDescription>
            </div>
            <Badge variant={summary.canSubmit ? 'default' : 'secondary'}>
              {summary.canSubmit ? (
                <><CheckCircle className="mr-1 h-3 w-3" /> Listo</>
              ) : (
                <><AlertCircle className="mr-1 h-3 w-3" /> Pendiente</>
              )}
            </Badge>
          </div>
        </CardHeader>
      </Card>

      {/* Blockers Alert */}
      {summary.blockers && summary.blockers.length > 0 && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>{texts.blockers}</AlertTitle>
          <AlertDescription>
            <ul className="list-disc list-inside mt-2 space-y-1">
              {summary.blockers.map((blocker, i) => (
                <li key={i} className="text-sm">{blocker}</li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      )}

      {/* Warnings Alert */}
      {summary.validationWarnings && summary.validationWarnings.length > 0 && (
        <Alert>
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>{texts.warnings}</AlertTitle>
          <AlertDescription>
            <ul className="list-disc list-inside mt-2 space-y-1">
              {summary.validationWarnings.map((warning, i) => (
                <li key={i} className="text-sm">{warning}</li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      )}

      {/* Main Content - Accordion */}
      <Accordion type="multiple" defaultValue={['personal', 'documents', 'tariff']} className="space-y-4">
        {/* Personal Data Section */}
        <AccordionItem value="personal" className="border rounded-lg">
          <AccordionTrigger className="px-4 hover:no-underline">
            <div className="flex items-center gap-2">
              <User className="h-5 w-5 text-muted-foreground" />
              <span className="font-semibold">{texts.personalData}</span>
              <Badge variant="outline" className="ml-2">
                {personalDataFields.length} campos
              </Badge>
            </div>
          </AccordionTrigger>
          <AccordionContent className="px-4 pb-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-2">
              {personalDataFields.map(({ key, value }) => (
                <div key={key} className="flex justify-between py-1.5 border-b border-dashed">
                  <span className="text-sm text-muted-foreground">
                    {formatFieldLabel(key)}
                  </span>
                  <span className="text-sm font-medium text-right">
                    {formatFieldValue(value)}
                  </span>
                </div>
              ))}
            </div>
            {personalDataFields.length === 0 && (
              <p className="text-sm text-muted-foreground italic">
                {locale === 'es' ? 'No hay datos personales extraídos'
                  : locale === 'fr' ? 'Aucune donnée personnelle extraite'
                  : 'No personal data extracted'}
              </p>
            )}
            <Button
              variant="outline"
              size="sm"
              className="mt-4"
              onClick={onEditPersonalData}
            >
              <Edit2 className="mr-2 h-3 w-3" />
              {texts.edit}
            </Button>
          </AccordionContent>
        </AccordionItem>

        {/* Documents Section */}
        <AccordionItem value="documents" className="border rounded-lg">
          <AccordionTrigger className="px-4 hover:no-underline">
            <div className="flex items-center gap-2">
              <FileText className="h-5 w-5 text-muted-foreground" />
              <span className="font-semibold">{texts.documents}</span>
              <Badge
                variant={summary.documentsComplete ? 'default' : 'secondary'}
                className="ml-2"
              >
                {summary.documentsUploaded?.length || 0}
              </Badge>
            </div>
          </AccordionTrigger>
          <AccordionContent className="px-4 pb-4">
            {/* Documents Status */}
            <div className={`flex items-center gap-2 mb-4 p-3 rounded-lg ${
              summary.documentsComplete ? 'bg-green-50 text-green-700' : 'bg-yellow-50 text-yellow-700'
            }`}>
              {summary.documentsComplete ? (
                <CheckCircle className="h-4 w-4" />
              ) : (
                <AlertTriangle className="h-4 w-4" />
              )}
              <span className="text-sm font-medium">
                {summary.documentsComplete ? texts.documentsComplete : texts.documentsMissing}
              </span>
            </div>

            {/* Documents List */}
            <div className="space-y-2">
              {summary.documentsUploaded?.map((doc, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between p-3 bg-muted/50 rounded-lg"
                >
                  <div className="flex items-center gap-3">
                    <FileText className="h-4 w-4 text-muted-foreground" />
                    <div>
                      <p className="text-sm font-medium">{doc.documentName}</p>
                      <p className="text-xs text-muted-foreground">{doc.fileName}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {doc.isValidated ? (
                      <Badge variant="default" className="text-xs">
                        <CheckCircle className="mr-1 h-3 w-3" />
                        {texts.validated}
                      </Badge>
                    ) : (
                      <Badge variant="secondary" className="text-xs">
                        <Clock className="mr-1 h-3 w-3" />
                        {texts.pending}
                      </Badge>
                    )}
                    <span className={`text-xs ${
                      doc.extractionConfidence >= 0.9 ? 'text-green-600' :
                      doc.extractionConfidence >= 0.7 ? 'text-yellow-600' : 'text-red-600'
                    }`}>
                      {Math.round(doc.extractionConfidence * 100)}%
                    </span>
                  </div>
                </div>
              ))}
            </div>

            <Button
              variant="outline"
              size="sm"
              className="mt-4"
              onClick={onEditDocuments}
            >
              <Edit2 className="mr-2 h-3 w-3" />
              {texts.edit}
            </Button>
          </AccordionContent>
        </AccordionItem>

        {/* Tariff Section */}
        {summary.tariffSummary && (
          <AccordionItem value="tariff" className="border rounded-lg">
            <AccordionTrigger className="px-4 hover:no-underline">
              <div className="flex items-center gap-2">
                <CreditCard className="h-5 w-5 text-muted-foreground" />
                <span className="font-semibold">{texts.tariff}</span>
                <Badge variant="outline" className="ml-2">
                  {formatCurrency(summary.tariffSummary.total, summary.tariffSummary.currency)}
                </Badge>
              </div>
            </AccordionTrigger>
            <AccordionContent className="px-4 pb-4">
              <div className="space-y-3">
                {/* Base Tariff */}
                <div className="flex justify-between items-center py-2 border-b">
                  <span className="text-sm">{texts.baseTariff}</span>
                  <span className="text-sm font-medium">
                    {formatCurrency(summary.tariffSummary.baseAmount, summary.tariffSummary.currency)}
                  </span>
                </div>

                {/* Supplements */}
                {summary.tariffSummary.supplements && summary.tariffSummary.supplements.length > 0 && (
                  <div className="space-y-1">
                    <p className="text-xs text-muted-foreground uppercase tracking-wide">
                      {texts.supplements}
                    </p>
                    {summary.tariffSummary.supplements.map((sup, i) => (
                      <div key={i} className="flex justify-between items-center py-1 pl-4">
                        <span className="text-sm text-muted-foreground">{sup.name}</span>
                        <span className="text-sm">
                          {formatCurrency(sup.amount, summary.tariffSummary?.currency)}
                        </span>
                      </div>
                    ))}
                  </div>
                )}

                <Separator />

                {/* Total */}
                <div className="flex justify-between items-center pt-2">
                  <span className="font-semibold">{texts.total}</span>
                  <span className="text-lg font-bold text-primary">
                    {formatCurrency(summary.tariffSummary.total, summary.tariffSummary.currency)}
                  </span>
                </div>
              </div>
            </AccordionContent>
          </AccordionItem>
        )}
      </Accordion>

      {/* Validation Status */}
      <Card className={summary.validationPassed ? 'border-green-200' : 'border-yellow-200'}>
        <CardContent className="pt-6">
          <div className="flex items-center gap-3">
            <div className={`p-2 rounded-full ${
              summary.validationPassed ? 'bg-green-100' : 'bg-yellow-100'
            }`}>
              {summary.validationPassed ? (
                <Shield className="h-5 w-5 text-green-600" />
              ) : (
                <AlertTriangle className="h-5 w-5 text-yellow-600" />
              )}
            </div>
            <div>
              <p className={`font-medium ${
                summary.validationPassed ? 'text-green-700' : 'text-yellow-700'
              }`}>
                {summary.validationPassed ? texts.validationPassed : texts.validationFailed}
              </p>
              <p className="text-sm text-muted-foreground">
                {summary.validationWarnings?.length || 0} advertencias
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Confirmation Checkbox */}
      <div className="flex items-start gap-3 p-4 bg-muted/50 rounded-lg">
        <Checkbox
          id="confirm"
          checked={isConfirmed}
          onCheckedChange={(checked) => setIsConfirmed(checked === true)}
          disabled={!summary.canSubmit}
        />
        <Label
          htmlFor="confirm"
          className="text-sm leading-relaxed cursor-pointer"
        >
          {texts.confirmLabel}
        </Label>
      </div>

      {/* Actions */}
      <div className="flex justify-between pt-4 border-t">
        <Button variant="outline" onClick={onBack} disabled={isSubmitting}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          {texts.back}
        </Button>

        <div className="flex gap-2">
          {onDownloadPDF && (
            <Button
              variant="outline"
              onClick={handleDownloadPDF}
              disabled={isDownloading}
            >
              {isDownloading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  {texts.downloading}
                </>
              ) : (
                <>
                  <Download className="mr-2 h-4 w-4" />
                  {texts.downloadPDF}
                </>
              )}
            </Button>
          )}

          <Button
            onClick={handleSubmit}
            disabled={!isConfirmed || !summary.canSubmit || isSubmitting}
          >
            {isSubmitting ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                {texts.submitting}
              </>
            ) : (
              <>
                <Send className="mr-2 h-4 w-4" />
                {texts.submit}
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  )
}

export default CitizenSummaryForm
