'use client'

/**
 * ExtractionPreview Component
 * Display extracted document data with confidence indicators
 */

import { useState, useCallback, useMemo } from 'react'
import { useTranslations } from 'next-intl'
import {
  CheckCircle,
  AlertCircle,
  AlertTriangle,
  Edit2,
  Save,
  X,
  ChevronDown,
  ChevronRight,
  Eye,
  FileText,
} from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'

import type { ServiceRequestDocument } from '../types'

// ============================================================================
// TYPES
// ============================================================================

interface FieldIndicator {
  confidence: number
  source: 'extracted' | 'manual' | 'default'
  originalValue?: string
}

interface ExtractedField {
  key: string
  label: string
  value: unknown
  indicator?: FieldIndicator
  editable?: boolean
  required?: boolean
}

interface ExtractionPreviewProps {
  document: ServiceRequestDocument
  locale?: 'es' | 'fr' | 'en'
  fieldLabels?: Record<string, { es: string; fr?: string; en?: string }>
  editableFields?: string[]
  requiredFields?: string[]
  onUpdateField?: (field: string, value: unknown) => Promise<void>
  onSaveAll?: (data: Record<string, unknown>) => Promise<void>
  showRawData?: boolean
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

function flattenObject(
  obj: Record<string, unknown>,
  prefix = ''
): Record<string, unknown> {
  const result: Record<string, unknown> = {}

  for (const [key, value] of Object.entries(obj)) {
    const newKey = prefix ? `${prefix}.${key}` : key

    if (value && typeof value === 'object' && !Array.isArray(value)) {
      Object.assign(result, flattenObject(value as Record<string, unknown>, newKey))
    } else {
      result[newKey] = value
    }
  }

  return result
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return '-'
  if (typeof value === 'boolean') return value ? 'Sí' : 'No'
  if (Array.isArray(value)) return value.join(', ')
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

// ============================================================================
// FIELD ROW COMPONENT
// ============================================================================

interface FieldRowProps {
  field: ExtractedField
  locale: 'es' | 'fr' | 'en'
  isEditing: boolean
  editValue: string
  onEditValueChange: (value: string) => void
  onSave: () => void
  onCancel: () => void
  onStartEdit: () => void
}

function FieldRow({
  field,
  locale: _locale,
  isEditing,
  editValue,
  onEditValueChange,
  onSave,
  onCancel,
  onStartEdit,
}: FieldRowProps) {
  const confidence = field.indicator?.confidence ?? 1
  const ConfidenceIcon = getConfidenceIcon(confidence)

  return (
    <div className="flex items-center py-2 border-b last:border-b-0 hover:bg-muted/50 px-2 -mx-2 rounded">
      {/* Label */}
      <div className="w-1/3 text-sm font-medium text-muted-foreground">
        {field.label}
        {field.required && <span className="text-red-500 ml-1">*</span>}
      </div>

      {/* Value */}
      <div className="flex-1 flex items-center gap-2">
        {isEditing ? (
          <div className="flex items-center gap-2 flex-1">
            <Input
              value={editValue}
              onChange={(e) => onEditValueChange(e.target.value)}
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
            <span className="text-sm">{formatValue(field.value)}</span>

            {/* Confidence Indicator */}
            {field.indicator && (
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <span className={`inline-flex items-center gap-1 ${getConfidenceBg(confidence)} px-2 py-0.5 rounded text-xs`}>
                      <ConfidenceIcon className={`h-3 w-3 ${getConfidenceColor(confidence)}`} />
                      {Math.round(confidence * 100)}%
                    </span>
                  </TooltipTrigger>
                  <TooltipContent>
                    <p>
                      {field.indicator.source === 'extracted' && 'Extraído automáticamente'}
                      {field.indicator.source === 'manual' && 'Editado manualmente'}
                      {field.indicator.source === 'default' && 'Valor por defecto'}
                    </p>
                    {field.indicator.originalValue && (
                      <p className="text-xs text-muted-foreground mt-1">
                        Original: {field.indicator.originalValue}
                      </p>
                    )}
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            )}

            {/* Edit Button */}
            {field.editable && (
              <Button
                size="sm"
                variant="ghost"
                onClick={onStartEdit}
                className="opacity-0 group-hover:opacity-100 transition-opacity"
              >
                <Edit2 className="h-3 w-3" />
              </Button>
            )}
          </>
        )}
      </div>
    </div>
  )
}

// ============================================================================
// SECTION COMPONENT
// ============================================================================

interface SectionProps {
  title: string
  fields: ExtractedField[]
  locale: 'es' | 'fr' | 'en'
  editingField: string | null
  editValue: string
  onEditValueChange: (value: string) => void
  onSave: (field: string) => void
  onCancel: () => void
  onStartEdit: (field: string, value: string) => void
}

function Section({
  title,
  fields,
  locale,
  editingField,
  editValue,
  onEditValueChange,
  onSave,
  onCancel,
  onStartEdit,
}: SectionProps) {
  const [isOpen, setIsOpen] = useState(true)

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <CollapsibleTrigger className="flex items-center gap-2 w-full p-2 hover:bg-muted rounded-lg">
        {isOpen ? (
          <ChevronDown className="h-4 w-4" />
        ) : (
          <ChevronRight className="h-4 w-4" />
        )}
        <span className="font-medium">{title}</span>
        <Badge variant="outline" className="ml-auto">
          {fields.length}
        </Badge>
      </CollapsibleTrigger>
      <CollapsibleContent className="pl-6 pt-2">
        {fields.map((field) => (
          <div key={field.key} className="group">
            <FieldRow
              field={field}
              locale={locale}
              isEditing={editingField === field.key}
              editValue={editValue}
              onEditValueChange={onEditValueChange}
              onSave={() => onSave(field.key)}
              onCancel={onCancel}
              onStartEdit={() => onStartEdit(field.key, formatValue(field.value))}
            />
          </div>
        ))}
      </CollapsibleContent>
    </Collapsible>
  )
}

// ============================================================================
// MAIN COMPONENT
// ============================================================================

export function ExtractionPreview({
  document,
  locale = 'es',
  fieldLabels = {},
  editableFields = [],
  requiredFields = [],
  onUpdateField,
  onSaveAll,
  showRawData = false,
}: ExtractionPreviewProps) {
  const t = useTranslations('service_requests')
  const [editingField, setEditingField] = useState<string | null>(null)
  const [editValue, setEditValue] = useState('')
  const [localData, setLocalData] = useState<Record<string, unknown>>(
    document.extractedData || {}
  )
  const [hasChanges, setHasChanges] = useState(false)
  const [showRaw, setShowRaw] = useState(false)

  // Get field label
  const getFieldLabel = useCallback((key: string): string => {
    const labels = fieldLabels[key]
    if (labels) {
      if (locale === 'fr' && labels.fr) return labels.fr
      if (locale === 'en' && labels.en) return labels.en
      return labels.es
    }
    // Fallback: format key as label
    return key
      .split('.')
      .pop()
      ?.replace(/_/g, ' ')
      .replace(/\b\w/g, (l) => l.toUpperCase()) || key
  }, [fieldLabels, locale])

  // Parse extracted data into fields
  const fields = useMemo((): ExtractedField[] => {
    if (!localData) return []

    const flattened = flattenObject(localData)
    return Object.entries(flattened).map(([key, value]) => ({
      key,
      label: getFieldLabel(key),
      value,
      indicator: {
        confidence: document.extractionConfidence || 0.5,
        source: 'extracted',
      },
      editable: editableFields.includes(key) || editableFields.includes('*'),
      required: requiredFields.includes(key),
    }))
  }, [localData, document.extractionConfidence, editableFields, requiredFields, getFieldLabel])

  // Group fields by section (based on first key segment)
  const sections = useMemo(() => {
    const grouped: Record<string, ExtractedField[]> = {}

    for (const field of fields) {
      const section = field.key.split('.')[0]
      if (!grouped[section]) {
        grouped[section] = []
      }
      grouped[section].push(field)
    }

    return Object.entries(grouped).map(([name, sectionFields]) => ({
      name,
      title: getFieldLabel(name),
      fields: sectionFields,
    }))
  }, [fields, getFieldLabel])

  // Overall confidence
  const overallConfidence = useMemo(() => {
    return document.extractionConfidence || 0.5
  }, [document.extractionConfidence])

  // Handle edit start
  const handleStartEdit = useCallback((field: string, value: string) => {
    setEditingField(field)
    setEditValue(value)
  }, [])

  // Handle save field
  const handleSaveField = useCallback(async (field: string) => {
    // Update local data
    const newData = { ...localData }
    const keys = field.split('.')
    let current: Record<string, unknown> = newData

    for (let i = 0; i < keys.length - 1; i++) {
      if (!current[keys[i]]) {
        current[keys[i]] = {}
      }
      current = current[keys[i]] as Record<string, unknown>
    }
    current[keys[keys.length - 1]] = editValue

    setLocalData(newData)
    setHasChanges(true)
    setEditingField(null)

    // Call update handler if provided
    if (onUpdateField) {
      await onUpdateField(field, editValue)
    }
  }, [localData, editValue, onUpdateField])

  // Handle cancel edit
  const handleCancelEdit = useCallback(() => {
    setEditingField(null)
    setEditValue('')
  }, [])

  // Handle save all changes
  const handleSaveAll = useCallback(async () => {
    if (onSaveAll) {
      await onSaveAll(localData)
      setHasChanges(false)
    }
  }, [localData, onSaveAll])

  // No data
  if (!document.extractedData || Object.keys(document.extractedData).length === 0) {
    return (
      <Card>
        <CardContent className="py-8 text-center">
          <FileText className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
          <p className="text-muted-foreground">{t('no_extracted_data')}</p>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg flex items-center gap-2">
            <Eye className="h-5 w-5" />
            {t('extracted_data')}
          </CardTitle>

          <div className="flex items-center gap-2">
            {/* Overall Confidence */}
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Badge className={getConfidenceBg(overallConfidence)}>
                    {Math.round(overallConfidence * 100)}% {t('confidence')}
                  </Badge>
                </TooltipTrigger>
                <TooltipContent>
                  <p>{t('overall_extraction_confidence')}</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>

            {/* Toggle Raw Data */}
            {showRawData && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowRaw(!showRaw)}
              >
                {showRaw ? t('show_formatted') : t('show_raw')}
              </Button>
            )}

            {/* Save All Button */}
            {hasChanges && onSaveAll && (
              <Button size="sm" onClick={handleSaveAll}>
                <Save className="h-4 w-4 mr-2" />
                {t('save_changes')}
              </Button>
            )}
          </div>
        </div>
      </CardHeader>

      <CardContent>
        {showRaw ? (
          <pre className="text-xs bg-muted p-4 rounded overflow-auto max-h-96">
            {JSON.stringify(localData, null, 2)}
          </pre>
        ) : (
          <div className="space-y-4">
            {sections.map((section) => (
              <Section
                key={section.name}
                title={section.title}
                fields={section.fields}
                locale={locale}
                editingField={editingField}
                editValue={editValue}
                onEditValueChange={setEditValue}
                onSave={handleSaveField}
                onCancel={handleCancelEdit}
                onStartEdit={handleStartEdit}
              />
            ))}
          </div>
        )}

        {/* Validation Errors */}
        {document.validationErrors && document.validationErrors.length > 0 && (
          <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg">
            <div className="flex items-center gap-2 text-red-700 mb-2">
              <AlertCircle className="h-4 w-4" />
              <span className="font-medium">{t('validation_errors')}</span>
            </div>
            <ul className="list-disc list-inside text-sm text-red-600">
              {document.validationErrors.map((err, i) => (
                <li key={i}>{err}</li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export default ExtractionPreview
