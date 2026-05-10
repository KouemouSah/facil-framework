'use client'

import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import { useTranslations } from 'next-intl'
import {
  Table2,
  Save,
  Loader2,
  Filter,
  ChevronDown,
  ChevronUp,
  Download,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import type { UseBatchSessionReturn } from '../../hooks/useBatchSession'
import type { BatchFormField } from '../../types'

interface BatchDataGridProps {
  hook: UseBatchSessionReturn
}

// Confidence thresholds for cell coloring
const HIGH_CONFIDENCE = 0.9
const MEDIUM_CONFIDENCE = 0.7

function getConfidenceColor(confidence?: number): string {
  if (confidence === undefined || confidence === null) return ''
  if (confidence >= HIGH_CONFIDENCE) return 'bg-green-50 dark:bg-green-950/30'
  if (confidence >= MEDIUM_CONFIDENCE) return 'bg-yellow-50 dark:bg-yellow-950/30'
  return 'bg-red-50 dark:bg-red-950/30'
}

// F-025 + F-008: Confidence tooltip label (localized)
function getConfidenceLabel(confidence: number, t: ReturnType<typeof useTranslations>): string {
  const pct = Math.round(confidence * 100)
  if (confidence >= HIGH_CONFIDENCE) return `${pct}% — ${t('dataGrid.confidenceHigh')}`
  if (confidence >= MEDIUM_CONFIDENCE) return `${pct}% — ${t('dataGrid.confidenceMedium')}`
  return `${pct}% — ${t('dataGrid.confidenceLow')}`
}

export function BatchDataGrid({ hook }: BatchDataGridProps) {
  const {
    session,
    isLoading,
    isSaving,
    formConfig,
    loadFormConfig,
    saveFormData,
  } = hook
  const t = useTranslations('batch')

  const [localData, setLocalData] = useState<
    Record<string, Record<string, unknown>>
  >({})
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false)
  const [filterText, setFilterText] = useState('')
  // Track explicitly collapsed sections (all open by default)
  const [collapsedSections, setCollapsedSections] = useState<Set<string>>(new Set())

  const beneficiaries = useMemo(
    () => session?.beneficiaries || [],
    [session?.beneficiaries]
  )

  // Load form config on mount (once only — guard prevents retry loop on failure)
  const formConfigLoadedRef = useRef(false)
  useEffect(() => {
    if (!formConfig && !formConfigLoadedRef.current) {
      formConfigLoadedRef.current = true
      loadFormConfig()
    }
  }, [formConfig, loadFormConfig])

  // Initialize local data from session
  useEffect(() => {
    if (session?.formDataGrid) {
      setLocalData(session.formDataGrid)
    } else {
      // Initialize from beneficiary form_data (extraction results)
      const initial: Record<string, Record<string, unknown>> = {}
      for (const ben of beneficiaries) {
        initial[ben.id] = {}
      }
      setLocalData(initial)
    }
  }, [session?.formDataGrid, beneficiaries])

  // Flatten all fields from all sections
  const allFields = useMemo(() => {
    if (!formConfig) return []
    return formConfig.sections.flatMap((s) =>
      s.fields.map((f) => ({ ...f, sectionId: s.id, sectionTitle: s.titleEs }))
    )
  }, [formConfig])

  // Filtered fields
  const filteredFields = useMemo(() => {
    if (!filterText) return allFields
    const lower = filterText.toLowerCase()
    return allFields.filter(
      (f) =>
        f.labelEs.toLowerCase().includes(lower) ||
        f.key.toLowerCase().includes(lower)
    )
  }, [allFields, filterText])

  // Filtered beneficiaries
  const filteredBeneficiaries = useMemo(() => {
    if (!filterText) return beneficiaries
    const lower = filterText.toLowerCase()
    return beneficiaries.filter(
      (b) =>
        b.name.toLowerCase().includes(lower) ||
        (b.identifier && b.identifier.toLowerCase().includes(lower))
    )
  }, [beneficiaries, filterText])

  const handleCellChange = useCallback(
    (beneficiaryId: string, fieldKey: string, value: unknown) => {
      setLocalData((prev) => ({
        ...prev,
        [beneficiaryId]: {
          ...(prev[beneficiaryId] || {}),
          [fieldKey]: value,
        },
      }))
      setHasUnsavedChanges(true)
    },
    []
  )

  const handleSave = async () => {
    const saved = await saveFormData(localData)
    if (saved) {
      setHasUnsavedChanges(false)
    }
  }

  // F-020: CSV export
  const handleExportCsv = useCallback(() => {
    if (!formConfig || beneficiaries.length === 0) return
    const fields = allFields
    const header = [t('beneficiaries'), ...fields.map((f) => f.labelEs)]
    const rows = beneficiaries.map((ben) => {
      const benData = localData[ben.id] || {}
      return [
        ben.name,
        ...fields.map((f) => {
          const cell = benData[f.key]
          if (typeof cell === 'object' && cell !== null && !Array.isArray(cell)) {
            return String((cell as Record<string, unknown>).value ?? '')
          }
          return String(cell ?? '')
        }),
      ]
    })
    const csvContent = [header, ...rows]
      .map((row) =>
        row.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(',')
      )
      .join('\n')
    const blob = new Blob(['\uFEFF' + csvContent], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `batch-data-${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }, [formConfig, beneficiaries, allFields, localData, t])

  const toggleSection = (sectionId: string) => {
    setCollapsedSections((prev) => {
      const next = new Set(prev)
      if (next.has(sectionId)) {
        next.delete(sectionId)
      } else {
        next.add(sectionId)
      }
      return next
    })
  }

  if (!formConfig && isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-blue-500" />
        <span className="ml-2 text-gray-500">{t('dataGrid.loadingConfig')}</span>
      </div>
    )
  }

  if (!formConfig || allFields.length === 0) {
    return (
      <div className="text-center py-12 text-gray-400">
        <Table2 className="h-10 w-10 mx-auto mb-3 opacity-30" />
        <p>{t('dataGrid.noConfig')}</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Table2 className="h-5 w-5 text-blue-600" />
          <h2 className="text-lg font-semibold">{t('dataGrid.title')}</h2>
          <Badge variant="secondary">
            {beneficiaries.length} {t('beneficiaries')} x {allFields.length} {t('dataGrid.fields')}
          </Badge>
        </div>
        <div className="flex items-center gap-2">
          {hasUnsavedChanges && (
            <Badge className="bg-amber-100 text-amber-700">
              {t('dataGrid.unsavedChanges')}
            </Badge>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={handleExportCsv}
            disabled={beneficiaries.length === 0}
          >
            <Download className="h-4 w-4 mr-1" />
            CSV
          </Button>
          <Button
            onClick={handleSave}
            disabled={!hasUnsavedChanges || isSaving}
            size="sm"
          >
            {isSaving ? (
              <Loader2 className="h-4 w-4 animate-spin mr-1" />
            ) : (
              <Save className="h-4 w-4 mr-1" />
            )}
            {t('dataGrid.save')}
          </Button>
        </div>
      </div>

      {/* Filter */}
      <div className="flex items-center gap-2">
        <Filter className="h-4 w-4 text-gray-400" />
        <Input
          value={filterText}
          onChange={(e) => setFilterText(e.target.value)}
          placeholder={t('dataGrid.filter')}
          className="max-w-sm h-8 text-sm"
        />
      </div>

      {/* Grid by sections */}
      <div className="space-y-4">
        {formConfig.sections.map((section) => {
          const sectionFields = filteredFields.filter(
            (f) => f.sectionId === section.id
          )
          if (sectionFields.length === 0) return null

          const isExpanded = !collapsedSections.has(section.id)

          return (
            <div key={section.id} className="border rounded-lg">
              {/* Section header */}
              <button
                className="w-full flex items-center justify-between px-4 py-2.5 bg-gray-50 hover:bg-gray-100 rounded-t-lg transition-colors"
                onClick={() => toggleSection(section.id)}
              >
                <span className="text-sm font-medium">{section.titleEs}</span>
                <div className="flex items-center gap-2">
                  <Badge variant="secondary" className="text-[10px]">
                    {sectionFields.length} {t('dataGrid.fields')}
                  </Badge>
                  {isExpanded ? (
                    <ChevronUp className="h-4 w-4 text-gray-400" />
                  ) : (
                    <ChevronDown className="h-4 w-4 text-gray-400" />
                  )}
                </div>
              </button>

              {/* Section data grid */}
              {isExpanded && (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b">
                        <th className="px-2 py-2 text-left text-xs font-medium text-gray-500 bg-gray-50 dark:bg-gray-900 sticky left-0 z-10 min-w-[120px] md:min-w-[180px]">
                          {t('beneficiaries')}
                        </th>
                        {sectionFields.map((field) => (
                          <th
                            key={field.key}
                            className="px-2 py-2 text-left text-xs font-medium text-gray-500 min-w-[120px] md:min-w-[150px]"
                          >
                            <span>{field.labelEs}</span>
                            {field.required && (
                              <span className="text-red-400 ml-0.5">*</span>
                            )}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y">
                      {filteredBeneficiaries.map((ben) => (
                        <tr key={ben.id} className="hover:bg-gray-50/50">
                          <td className="px-2 py-2 font-medium sticky left-0 bg-white dark:bg-gray-950 z-10 border-r min-w-[120px] md:min-w-[180px]">
                            <div className="truncate">
                              <p className="text-sm truncate">{ben.name}</p>
                              {ben.identifier && (
                                <p className="text-[10px] text-gray-400 truncate">
                                  {ben.identifier}
                                </p>
                              )}
                            </div>
                          </td>
                          {sectionFields.map((field) => {
                            const cellData = localData[ben.id]?.[field.key]
                            // Extract value + confidence from nested objects
                            // (extraction results may be {value: "...", confidence: 0.9})
                            let value: unknown
                            let confidence: number | undefined
                            if (typeof cellData === 'object' && cellData !== null && !Array.isArray(cellData)) {
                              const obj = cellData as Record<string, unknown>
                              confidence = obj.confidence as number | undefined
                              value = obj.value ?? ''
                            } else {
                              value = cellData ?? ''
                            }
                            return (
                              <td
                                key={field.key}
                                className={`px-1 py-1 ${getConfidenceColor(confidence)}`}
                              >
                                {confidence !== undefined ? (
                                  <TooltipProvider delayDuration={200}>
                                    <Tooltip>
                                      <TooltipTrigger asChild>
                                        <div>
                                          <CellInput
                                            field={field}
                                            value={value}
                                            onChange={(val) =>
                                              handleCellChange(ben.id, field.key, val)
                                            }
                                            readonly={field.readonly}
                                          />
                                        </div>
                                      </TooltipTrigger>
                                      <TooltipContent side="top" className="text-xs">
                                        {getConfidenceLabel(confidence, t)}
                                      </TooltipContent>
                                    </Tooltip>
                                  </TooltipProvider>
                                ) : (
                                  <CellInput
                                    field={field}
                                    value={value}
                                    onChange={(val) =>
                                      handleCellChange(ben.id, field.key, val)
                                    }
                                    readonly={field.readonly}
                                  />
                                )}
                              </td>
                            )
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ============================================================================
// CELL INPUT — renders appropriate input per field type
// ============================================================================

function CellInput({
  field,
  value,
  onChange,
  readonly,
}: {
  field: BatchFormField
  value: unknown
  onChange: (val: unknown) => void
  readonly: boolean
}) {
  const t = useTranslations('batch')
  const strValue = String(value ?? '')

  if (readonly) {
    return (
      <span className="px-2 py-1 text-sm text-gray-600 block truncate">
        {strValue || '\u2014'}
      </span>
    )
  }

  if (field.type === 'select' && field.options) {
    return (
      <select
        className="w-full border-0 bg-transparent text-sm px-2 py-1 focus:ring-1 focus:ring-blue-300 rounded"
        value={strValue}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value="">{'\u2014'}</option>
        {field.options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    )
  }

  if (field.type === 'boolean' || field.type === 'radio') {
    return (
      <select
        className="w-full border-0 bg-transparent text-sm px-2 py-1 focus:ring-1 focus:ring-blue-300 rounded"
        value={strValue}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value="">{'\u2014'}</option>
        {field.options ? (
          field.options.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))
        ) : (
          <>
            <option value="true">{t('dataGrid.yes') ?? 'Sí'}</option>
            <option value="false">{t('dataGrid.no') ?? 'No'}</option>
          </>
        )}
      </select>
    )
  }

  if (field.type === 'date') {
    return (
      <input
        type="date"
        className="w-full border-0 bg-transparent text-sm px-2 py-1 focus:ring-1 focus:ring-blue-300 rounded"
        value={strValue}
        onChange={(e) => onChange(e.target.value)}
      />
    )
  }

  if (field.type === 'number') {
    return (
      <input
        type="number"
        className="w-full border-0 bg-transparent text-sm px-2 py-1 focus:ring-1 focus:ring-blue-300 rounded"
        value={strValue}
        onChange={(e) => onChange(e.target.value)}
      />
    )
  }

  // Default: text input
  return (
    <input
      type="text"
      className="w-full border-0 bg-transparent text-sm px-2 py-1 focus:ring-1 focus:ring-blue-300 rounded"
      value={strValue}
      onChange={(e) => onChange(e.target.value)}
      placeholder={field.placeholderEs || ''}
    />
  )
}
