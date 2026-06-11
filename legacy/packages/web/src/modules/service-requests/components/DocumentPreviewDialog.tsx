'use client'

/**
 * DocumentPreviewDialog Component
 * Shows extraction preview for user validation before saving document
 * Part of the two-step preview/validate flow
 */

import { useState, useCallback, useMemo } from 'react'
import {
  CheckCircle,
  AlertCircle,
  AlertTriangle,
  Save,
  X,
  Clock,
  FileText,
  Shield,
  Edit2,
  Eye,
  Loader2,
} from 'lucide-react'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Separator } from '@/components/ui/separator'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'

import type { DocumentExtractionPreview, FieldIndicator } from '../types'

// ============================================================================
// PROPS
// ============================================================================

interface DocumentPreviewDialogProps {
  preview: DocumentExtractionPreview | null
  isOpen: boolean
  onClose: () => void
  onConfirm: (confirmedData: Record<string, unknown>, userNotes?: string) => Promise<void>
  isConfirming?: boolean
  locale?: 'es' | 'fr' | 'en'
}

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

function getConfidenceColor(confidence: number): string {
  if (confidence >= 0.9) return 'text-green-600'
  if (confidence >= 0.7) return 'text-yellow-600'
  return 'text-red-600'
}

function getConfidenceBg(confidence: number): string {
  if (confidence >= 0.9) return 'bg-green-100'
  if (confidence >= 0.7) return 'bg-yellow-100'
  return 'bg-red-100'
}

function getConfidenceIcon(confidence: number) {
  if (confidence >= 0.9) return CheckCircle
  if (confidence >= 0.7) return AlertTriangle
  return AlertCircle
}

function getRiskLevelColor(level?: string): string {
  switch (level) {
    case 'critical': return 'bg-red-500 text-white'
    case 'high': return 'bg-orange-500 text-white'
    case 'medium': return 'bg-yellow-500 text-black'
    case 'low': return 'bg-green-500 text-white'
    default: return 'bg-gray-200 text-gray-800'
  }
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return ''
  if (typeof value === 'boolean') return value ? 'Si' : 'No'
  if (Array.isArray(value)) return value.join(', ')
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function formatFieldLabel(key: string): string {
  return key
    .split('.')
    .pop()
    ?.replace(/_/g, ' ')
    .replace(/\b\w/g, (l) => l.toUpperCase()) || key
}

// ============================================================================
// FIELD ROW COMPONENT
// ============================================================================

interface FieldRowProps {
  fieldKey: string
  value: unknown
  indicator?: FieldIndicator
  isEditing: boolean
  editValue: string
  onStartEdit: () => void
  onEditChange: (value: string) => void
  onSave: () => void
  onCancel: () => void
}

function FieldRow({
  fieldKey,
  value,
  indicator,
  isEditing,
  editValue,
  onStartEdit,
  onEditChange,
  onSave,
  onCancel,
}: FieldRowProps) {
  const confidence = indicator?.confidence ?? 0.5
  const ConfidenceIcon = getConfidenceIcon(confidence)
  const needsAttention = indicator?.requiresAttention || confidence < 0.7

  return (
    <div className={`flex items-center py-2 px-3 -mx-3 rounded transition-colors ${
      needsAttention ? 'bg-yellow-50' : 'hover:bg-muted/50'
    }`}>
      {/* Label */}
      <div className="w-1/3 text-sm font-medium text-muted-foreground">
        {formatFieldLabel(fieldKey)}
      </div>

      {/* Value */}
      <div className="flex-1 flex items-center gap-2">
        {isEditing ? (
          <div className="flex items-center gap-2 flex-1">
            <Input
              value={editValue}
              onChange={(e) => onEditChange(e.target.value)}
              className="h-8 text-sm"
              autoFocus
            />
            <Button size="sm" variant="ghost" onClick={onSave}>
              <Save className="h-4 w-4" />
            </Button>
            <Button size="sm" variant="ghost" onClick={onCancel}>
              <X className="h-4 w-4" />
            </Button>
          </div>
        ) : (
          <>
            <span className={`text-sm ${needsAttention ? 'font-medium' : ''}`}>
              {formatValue(value) || '-'}
            </span>

            {/* Confidence Indicator */}
            {indicator && (
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <span className={`inline-flex items-center gap-1 ${getConfidenceBg(confidence)} px-2 py-0.5 rounded text-xs cursor-help`}>
                      <ConfidenceIcon className={`h-3 w-3 ${getConfidenceColor(confidence)}`} />
                      {Math.round(confidence * 100)}%
                    </span>
                  </TooltipTrigger>
                  <TooltipContent>
                    {indicator.riskMessage || (
                      confidence >= 0.9 ? 'Alta confianza' :
                      confidence >= 0.7 ? 'Confianza media - verifique' :
                      'Baja confianza - requiere correccion'
                    )}
                    {indicator.suggestion && (
                      <p className="text-xs mt-1">{indicator.suggestion}</p>
                    )}
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            )}

            {/* Edit Button */}
            <Button
              size="sm"
              variant="ghost"
              onClick={onStartEdit}
              className="opacity-50 hover:opacity-100"
            >
              <Edit2 className="h-3 w-3" />
            </Button>
          </>
        )}
      </div>
    </div>
  )
}

// ============================================================================
// MAIN COMPONENT
// ============================================================================

export function DocumentPreviewDialog({
  preview,
  isOpen,
  onClose,
  onConfirm,
  isConfirming = false,
  locale = 'es',
}: DocumentPreviewDialogProps) {
  // Editable data state
  const [editedData, setEditedData] = useState<Record<string, unknown>>({})
  const [editingField, setEditingField] = useState<string | null>(null)
  const [editValue, setEditValue] = useState('')
  const [userNotes, setUserNotes] = useState('')

  // Get combined data (original + edits)
  const combinedData = useMemo(() => {
    if (!preview) return {}
    return { ...preview.extraction, ...editedData }
  }, [preview, editedData])

  // Flatten nested objects for display
  const flattenedFields = useMemo(() => {
    const flatten = (obj: Record<string, unknown>, prefix = ''): Array<{ key: string; value: unknown }> => {
      const result: Array<{ key: string; value: unknown }> = []
      for (const [key, value] of Object.entries(obj)) {
        const fullKey = prefix ? `${prefix}.${key}` : key
        if (value && typeof value === 'object' && !Array.isArray(value)) {
          result.push(...flatten(value as Record<string, unknown>, fullKey))
        } else {
          result.push({ key: fullKey, value })
        }
      }
      return result
    }
    return flatten(combinedData)
  }, [combinedData])

  // Find indicator for a field
  const getFieldIndicator = useCallback((key: string): FieldIndicator | undefined => {
    return preview?.fieldIndicators?.find(i => i.fieldName === key)
  }, [preview])

  // Handle edit start
  const handleStartEdit = useCallback((key: string, value: unknown) => {
    setEditingField(key)
    setEditValue(formatValue(value))
  }, [])

  // Handle save edit
  const handleSaveEdit = useCallback((key: string) => {
    setEditedData(prev => ({ ...prev, [key]: editValue }))
    setEditingField(null)
    setEditValue('')
  }, [editValue])

  // Handle cancel edit
  const handleCancelEdit = useCallback(() => {
    setEditingField(null)
    setEditValue('')
  }, [])

  // Handle confirm
  const handleConfirm = useCallback(async () => {
    await onConfirm(combinedData, userNotes || undefined)
  }, [combinedData, userNotes, onConfirm])

  // Handle close (reset state)
  const handleClose = useCallback(() => {
    setEditedData({})
    setEditingField(null)
    setEditValue('')
    setUserNotes('')
    onClose()
  }, [onClose])

  // Time remaining until preview expires
  const timeRemaining = useMemo(() => {
    if (!preview) return null
    const expiresAt = new Date(preview.expiresAt)
    const now = new Date()
    const diffMs = expiresAt.getTime() - now.getTime()
    const diffMin = Math.max(0, Math.floor(diffMs / 60000))
    return diffMin
  }, [preview])

  if (!preview) return null

  const overallConfidence = preview.confidence
  const hasRiskIssues = preview.riskAnalysis?.requiresReview || preview.riskAnalysis?.requiresRejection
  const attentionFieldsCount = preview.fieldIndicators?.filter(f => f.requiresAttention).length || 0

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && handleClose()}>
      <DialogContent className="max-w-2xl max-h-[90vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Eye className="h-5 w-5" />
            {locale === 'es' ? 'Vista Previa de Extraccion' : locale === 'fr' ? 'Apercu d\'Extraction' : 'Extraction Preview'}
          </DialogTitle>
          <DialogDescription className="flex items-center gap-4">
            <span className="flex items-center gap-1">
              <FileText className="h-4 w-4" />
              {preview.documentName}
            </span>
            <span className="text-xs text-muted-foreground">
              {preview.fileName} ({Math.round(preview.fileSize / 1024)} KB)
            </span>
          </DialogDescription>
        </DialogHeader>

        <ScrollArea className="flex-1 pr-4">
          {/* Confidence Summary */}
          <div className="flex items-center gap-4 mb-4">
            <div className="flex items-center gap-2">
              <Badge className={getConfidenceBg(overallConfidence)}>
                {Math.round(overallConfidence * 100)}% {locale === 'es' ? 'confianza' : locale === 'fr' ? 'confiance' : 'confidence'}
              </Badge>
              <Badge variant="outline">
                {preview.processor === 'gemini' ? 'Gemini AI' : preview.processor === 'tesseract' ? 'OCR' : 'Hibrido'}
              </Badge>
            </div>
            {timeRemaining !== null && (
              <span className="flex items-center gap-1 text-xs text-muted-foreground">
                <Clock className="h-3 w-3" />
                {timeRemaining} min
              </span>
            )}
          </div>

          {/* Risk Analysis Alert */}
          {preview.riskAnalysis && hasRiskIssues && (
            <Alert variant={preview.riskAnalysis.requiresRejection ? 'destructive' : 'default'} className="mb-4">
              <Shield className="h-4 w-4" />
              <AlertTitle className="flex items-center gap-2">
                {locale === 'es' ? 'Analisis de Riesgo' : locale === 'fr' ? 'Analyse de Risque' : 'Risk Analysis'}
                <Badge className={getRiskLevelColor(preview.riskAnalysis.riskLevel)}>
                  {preview.riskAnalysis.riskLevel.toUpperCase()}
                </Badge>
              </AlertTitle>
              <AlertDescription>
                <ul className="list-disc list-inside mt-2 space-y-1 text-sm">
                  {preview.riskAnalysis.recommendations.map((rec, i) => (
                    <li key={i}>{rec}</li>
                  ))}
                </ul>
              </AlertDescription>
            </Alert>
          )}

          {/* Attention Fields Alert */}
          {attentionFieldsCount > 0 && (
            <Alert className="mb-4">
              <AlertTriangle className="h-4 w-4" />
              <AlertTitle>
                {attentionFieldsCount} {attentionFieldsCount === 1 ? 'campo requiere' : 'campos requieren'} atencion
              </AlertTitle>
              <AlertDescription>
                {locale === 'es' ? 'Por favor verifique los campos resaltados en amarillo.' :
                 locale === 'fr' ? 'Veuillez verifier les champs surlignés en jaune.' :
                 'Please verify the fields highlighted in yellow.'}
              </AlertDescription>
            </Alert>
          )}

          {/* Document Type Mismatch Warning */}
          {!preview.documentTypeMatch && preview.detectedDocumentType && (
            <Alert variant="destructive" className="mb-4">
              <AlertCircle className="h-4 w-4" />
              <AlertTitle>
                {locale === 'es' ? 'Tipo de Documento Incorrecto' :
                 locale === 'fr' ? 'Type de Document Incorrect' :
                 'Incorrect Document Type'}
              </AlertTitle>
              <AlertDescription>
                {locale === 'es' ? `Se esperaba otro documento. Detectado: ${preview.detectedDocumentType}` :
                 locale === 'fr' ? `Un autre document était attendu. Détecté: ${preview.detectedDocumentType}` :
                 `A different document was expected. Detected: ${preview.detectedDocumentType}`}
              </AlertDescription>
            </Alert>
          )}

          <Separator className="my-4" />

          {/* Extracted Fields */}
          <div className="space-y-1">
            <h4 className="font-medium mb-2">
              {locale === 'es' ? 'Datos Extraidos' : locale === 'fr' ? 'Donnees Extraites' : 'Extracted Data'}
            </h4>
            {flattenedFields.map(({ key, value }) => (
              <FieldRow
                key={key}
                fieldKey={key}
                value={value}
                indicator={getFieldIndicator(key)}
                isEditing={editingField === key}
                editValue={editValue}
                onStartEdit={() => handleStartEdit(key, value)}
                onEditChange={setEditValue}
                onSave={() => handleSaveEdit(key)}
                onCancel={handleCancelEdit}
              />
            ))}
          </div>

          <Separator className="my-4" />

          {/* User Notes */}
          <div className="space-y-2">
            <Label htmlFor="userNotes">
              {locale === 'es' ? 'Notas (opcional)' : locale === 'fr' ? 'Notes (facultatif)' : 'Notes (optional)'}
            </Label>
            <Textarea
              id="userNotes"
              value={userNotes}
              onChange={(e) => setUserNotes(e.target.value)}
              placeholder={
                locale === 'es' ? 'Agregue notas sobre este documento...' :
                locale === 'fr' ? 'Ajoutez des notes sur ce document...' :
                'Add notes about this document...'
              }
              className="resize-none h-20"
            />
          </div>

          {/* Progress indicator for changes */}
          {Object.keys(editedData).length > 0 && (
            <div className="mt-4 p-3 bg-blue-50 rounded-lg">
              <p className="text-sm text-blue-700">
                {Object.keys(editedData).length} {Object.keys(editedData).length === 1 ? 'campo modificado' : 'campos modificados'}
              </p>
            </div>
          )}
        </ScrollArea>

        <DialogFooter className="mt-4">
          <Button variant="outline" onClick={handleClose} disabled={isConfirming}>
            {locale === 'es' ? 'Cancelar' : locale === 'fr' ? 'Annuler' : 'Cancel'}
          </Button>
          <Button
            onClick={handleConfirm}
            disabled={isConfirming || preview.riskAnalysis?.requiresRejection}
          >
            {isConfirming ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                {locale === 'es' ? 'Guardando...' : locale === 'fr' ? 'Enregistrement...' : 'Saving...'}
              </>
            ) : (
              <>
                <CheckCircle className="mr-2 h-4 w-4" />
                {locale === 'es' ? 'Confirmar y Guardar' : locale === 'fr' ? 'Confirmer et Enregistrer' : 'Confirm & Save'}
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default DocumentPreviewDialog
