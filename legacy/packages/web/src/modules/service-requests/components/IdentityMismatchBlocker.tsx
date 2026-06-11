'use client'

/**
 * IdentityMismatchBlocker Component
 *
 * Blocks user from proceeding when critical identity mismatches are detected
 * between documents (e.g., DIP vs Passport have different names/dates).
 *
 * Shows a clear message with:
 * - List of mismatches with source values
 * - Document sources for each field
 * - Action to re-upload correct documents
 */

import { useTranslations } from 'next-intl'
import { useParams } from 'next/navigation'
import {
  AlertOctagon,
  FileWarning,
  ArrowLeft,
  RefreshCw,
  Info,
} from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'

// ============================================================================
// TYPES
// ============================================================================

export interface IdentityMismatch {
  field_name: string
  field_label: {
    es: string
    fr: string
    en: string
  }
  is_blocking: boolean
  source_document: {
    code: string
    value: string
  }
  compared_document: {
    code: string
    value: string
  }
  risk_code: string
  severity: string
}

export interface IdentityMismatchBlockerProps {
  mismatches: IdentityMismatch[]
  hasBlockingMismatches: boolean
  onGoBack: () => void
  onReuploadDocument?: (documentCode: string) => void
  documentLabels?: Record<string, string>
}

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

const getDocumentLabel = (
  code: string,
  labels?: Record<string, string>,
  locale?: string
): string => {
  if (labels && labels[code]) {
    return labels[code]
  }

  // Default labels
  const defaultLabels: Record<string, Record<string, string>> = {
    dip: { es: 'DIP', fr: 'DIP', en: 'DIP (ID Card)' },
    pasaporte: { es: 'Pasaporte', fr: 'Passeport', en: 'Passport' },
    pasaporte_antiguo: { es: 'Pasaporte Antiguo', fr: 'Ancien Passeport', en: 'Old Passport' },
    pasaporte_danado: { es: 'Pasaporte Dañado', fr: 'Passeport Endommagé', en: 'Damaged Passport' },
    certificado_nacimiento: { es: 'Certificado de Nacimiento', fr: 'Acte de Naissance', en: 'Birth Certificate' },
    licencia_conducir: { es: 'Licencia de Conducir', fr: 'Permis de Conduire', en: 'Driver\'s License' },
  }

  const loc = locale || 'es'
  return defaultLabels[code]?.[loc] || code.toUpperCase()
}

const getSeverityColor = (severity: string): string => {
  switch (severity) {
    case 'critical': return 'destructive'
    case 'high': return 'destructive'
    case 'medium': return 'warning'
    case 'low': return 'secondary'
    default: return 'outline'
  }
}

// ============================================================================
// COMPONENT
// ============================================================================

export function IdentityMismatchBlocker({
  mismatches,
  hasBlockingMismatches: _hasBlockingMismatches,  // Prefixed with _ as it's used by parent
  onGoBack,
  onReuploadDocument,
  documentLabels,
}: IdentityMismatchBlockerProps) {
  const params = useParams()
  const locale = (params?.locale as string) || 'es'
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const _t = useTranslations('service_requests')  // Kept for future expansion

  // Get blocking mismatches (critical ones)
  const blockingMismatches = mismatches.filter(m => m.is_blocking)
  const warningMismatches = mismatches.filter(m => !m.is_blocking)

  // Get unique documents involved in mismatches
  const involvedDocuments = Array.from(new Set([
    ...mismatches.map(m => m.source_document.code),
    ...mismatches.map(m => m.compared_document.code)
  ]))

  // Get field label based on locale
  const getFieldLabel = (mismatch: IdentityMismatch): string => {
    return mismatch.field_label[locale as 'es' | 'fr' | 'en'] || mismatch.field_name
  }

  // Localized strings
  const strings = {
    es: {
      title: 'Datos de Identidad No Coinciden',
      subtitle: 'Se detectaron diferencias críticas entre los documentos cargados',
      blockingTitle: 'Discrepancias que Bloquean el Proceso',
      blockingDesc: 'Los siguientes campos no coinciden entre documentos y deben ser corregidos:',
      warningTitle: 'Discrepancias de Advertencia',
      warningDesc: 'Los siguientes campos tienen diferencias menores:',
      documentField: 'Campo',
      value: 'Valor',
      in: 'en',
      vs: 'vs',
      actionTitle: 'Acciones Requeridas',
      actionDesc: 'Debe volver y cargar documentos que pertenezcan a la misma persona.',
      actionReupload: 'Volver a cargar',
      goBack: 'Volver a Documentos',
      helpTitle: 'Ayuda',
      helpText: 'Asegúrese de que todos los documentos (DIP, Pasaporte, etc.) pertenezcan a la misma persona. Los nombres, fechas de nacimiento y números de documento deben coincidir.',
    },
    fr: {
      title: 'Données d\'Identité Non Correspondantes',
      subtitle: 'Des différences critiques ont été détectées entre les documents téléchargés',
      blockingTitle: 'Divergences Bloquantes',
      blockingDesc: 'Les champs suivants ne correspondent pas entre les documents et doivent être corrigés:',
      warningTitle: 'Avertissements',
      warningDesc: 'Les champs suivants présentent des différences mineures:',
      documentField: 'Champ',
      value: 'Valeur',
      in: 'dans',
      vs: 'vs',
      actionTitle: 'Actions Requises',
      actionDesc: 'Vous devez retourner et télécharger des documents appartenant à la même personne.',
      actionReupload: 'Re-télécharger',
      goBack: 'Retour aux Documents',
      helpTitle: 'Aide',
      helpText: 'Assurez-vous que tous les documents (DIP, Passeport, etc.) appartiennent à la même personne. Les noms, dates de naissance et numéros de document doivent correspondre.',
    },
    en: {
      title: 'Identity Data Mismatch',
      subtitle: 'Critical differences were detected between uploaded documents',
      blockingTitle: 'Blocking Discrepancies',
      blockingDesc: 'The following fields do not match between documents and must be corrected:',
      warningTitle: 'Warning Discrepancies',
      warningDesc: 'The following fields have minor differences:',
      documentField: 'Field',
      value: 'Value',
      in: 'in',
      vs: 'vs',
      actionTitle: 'Required Actions',
      actionDesc: 'You must go back and upload documents that belong to the same person.',
      actionReupload: 'Re-upload',
      goBack: 'Back to Documents',
      helpTitle: 'Help',
      helpText: 'Make sure all documents (DIP, Passport, etc.) belong to the same person. Names, dates of birth, and document numbers must match.',
    },
  }

  const s = strings[locale as 'es' | 'fr' | 'en'] || strings.es

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* Main Alert */}
      <Alert variant="destructive" className="border-red-300 bg-red-50">
        <AlertOctagon className="h-5 w-5" />
        <AlertTitle className="text-lg font-semibold">{s.title}</AlertTitle>
        <AlertDescription className="mt-1">
          {s.subtitle}
        </AlertDescription>
      </Alert>

      {/* Blocking Mismatches */}
      {blockingMismatches.length > 0 && (
        <Card className="border-red-200">
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2 text-red-700">
              <FileWarning className="h-5 w-5" />
              {s.blockingTitle}
            </CardTitle>
            <CardDescription>{s.blockingDesc}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {blockingMismatches.map((mismatch, index) => (
              <div key={`${mismatch.field_name}-${index}`} className="p-4 bg-red-50 rounded-lg border border-red-200">
                <div className="flex items-start justify-between">
                  <div className="space-y-2 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-red-800">{getFieldLabel(mismatch)}</span>
                      <Badge variant={getSeverityColor(mismatch.severity) as 'destructive' | 'secondary' | 'outline'}>
                        {mismatch.severity}
                      </Badge>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-2">
                      {/* Source Document */}
                      <div className="p-2 bg-white rounded border">
                        <span className="text-xs text-muted-foreground">
                          {s.in} {getDocumentLabel(mismatch.source_document.code, documentLabels, locale)}:
                        </span>
                        <p className="font-mono text-sm mt-1 text-red-900">
                          {mismatch.source_document.value}
                        </p>
                      </div>

                      {/* Compared Document */}
                      <div className="p-2 bg-white rounded border">
                        <span className="text-xs text-muted-foreground">
                          {s.in} {getDocumentLabel(mismatch.compared_document.code, documentLabels, locale)}:
                        </span>
                        <p className="font-mono text-sm mt-1 text-red-900">
                          {mismatch.compared_document.value}
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Warning Mismatches (non-blocking) */}
      {warningMismatches.length > 0 && (
        <Card className="border-yellow-200">
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2 text-yellow-700">
              <Info className="h-5 w-5" />
              {s.warningTitle}
            </CardTitle>
            <CardDescription>{s.warningDesc}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {warningMismatches.map((mismatch, index) => (
              <div key={`${mismatch.field_name}-${index}`} className="p-3 bg-yellow-50 rounded-lg border border-yellow-200">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-yellow-800">{getFieldLabel(mismatch)}</span>
                  <Badge variant="outline" className="text-yellow-700">
                    {mismatch.severity}
                  </Badge>
                </div>
                <p className="text-sm text-yellow-700 mt-1">
                  <span className="font-mono">{mismatch.source_document.value}</span>
                  <span className="mx-2">{s.vs}</span>
                  <span className="font-mono">{mismatch.compared_document.value}</span>
                </p>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Action Required Card */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">{s.actionTitle}</CardTitle>
          <CardDescription>{s.actionDesc}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Re-upload buttons per document */}
          {onReuploadDocument && involvedDocuments.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {involvedDocuments.map(docCode => (
                <Button
                  key={docCode}
                  variant="outline"
                  size="sm"
                  onClick={() => onReuploadDocument(docCode)}
                  className="flex items-center gap-2"
                >
                  <RefreshCw className="h-4 w-4" />
                  {s.actionReupload} {getDocumentLabel(docCode, documentLabels, locale)}
                </Button>
              ))}
            </div>
          )}

          <Separator />

          {/* Main back button */}
          <Button
            variant="default"
            onClick={onGoBack}
            className="w-full"
          >
            <ArrowLeft className="mr-2 h-4 w-4" />
            {s.goBack}
          </Button>
        </CardContent>
      </Card>

      {/* Help Card */}
      <Card className="bg-blue-50 border-blue-200">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center gap-2 text-blue-700">
            <Info className="h-4 w-4" />
            {s.helpTitle}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-blue-700">
            {s.helpText}
          </p>
        </CardContent>
      </Card>
    </div>
  )
}

export default IdentityMismatchBlocker
