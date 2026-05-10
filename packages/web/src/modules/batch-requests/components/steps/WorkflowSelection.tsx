'use client'

import { useState, useEffect, useMemo } from 'react'
import { useTranslations } from 'next-intl'
import { FileStack, ArrowRight, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import type { UseBatchSessionReturn } from '../../hooks/useBatchSession'
import type { BatchWorkflowOption } from '../../types'
import { batchApi } from '../../services/batch-api'
import { useWorkflowTranslations, workflowNameKey } from '@/hooks/use-workflow-translations'

interface WorkflowSelectionProps {
  hook: UseBatchSessionReturn
  onSessionCreated: (sessionId: string) => void
}

export function WorkflowSelection({ hook, onSessionCreated }: WorkflowSelectionProps) {
  const { isLoading, createSession } = hook
  const t = useTranslations('batch')
  const { tw } = useWorkflowTranslations()
  const [workflowCode, setWorkflowCode] = useState('')
  const [solicitudType, setSolicitudType] = useState('')
  const [notes, setNotes] = useState('')

  // F-005: Fetch workflows dynamically from backend
  const [workflows, setWorkflows] = useState<BatchWorkflowOption[]>([])
  const [loadingWorkflows, setLoadingWorkflows] = useState(true)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const resp = await batchApi.getAvailableWorkflows()
        if (!cancelled) {
          setWorkflows(resp.workflows)
        }
      } catch (e) {
        console.error('[WorkflowSelection] Failed to load workflows:', e)
      } finally {
        if (!cancelled) setLoadingWorkflows(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [])

  // F-006: Derive solicitud types from selected workflow
  const selectedWorkflow = workflows.find((w) => w.code === workflowCode)
  const solicitudTypes = useMemo(
    () => selectedWorkflow?.allowed_solicitud_types || [],
    [selectedWorkflow?.allowed_solicitud_types]
  )

  // Auto-select first solicitud type when workflow changes
  useEffect(() => {
    if (solicitudTypes.length > 0 && !solicitudTypes.includes(solicitudType)) {
      setSolicitudType(solicitudTypes[0])
    }
  }, [workflowCode, solicitudTypes, solicitudType])

  const handleStart = async () => {
    if (!workflowCode) return

    const session = await createSession({
      workflowCode,
      solicitudType: solicitudType || 'expedicion',
      notes: notes || undefined,
    })

    if (session) {
      onSessionCreated(session.sessionId)
    }
  }

  // Group workflows by category for display
  const categories = Array.from(new Set(workflows.map((w) => w.category)))

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3 mb-4">
        <div className="p-2 bg-blue-100 rounded-lg">
          <FileStack className="h-6 w-6 text-blue-600" />
        </div>
        <div>
          <h2 className="text-lg font-semibold">{t('workflowSelection.title')}</h2>
          <p className="text-sm text-gray-500">
            {t('workflowSelection.description')}
          </p>
        </div>
      </div>

      <div className="space-y-2">
        <Label htmlFor="workflow">{t('workflowSelection.selectWorkflow')} *</Label>
        <Select
          value={workflowCode}
          onValueChange={(v) => {
            setWorkflowCode(v)
            setSolicitudType('')
          }}
          disabled={loadingWorkflows}
        >
          <SelectTrigger id="workflow">
            <SelectValue
              placeholder={
                loadingWorkflows
                  ? t('workflowSelection.loadingWorkflows')
                  : t('workflowSelection.selectWorkflow')
              }
            />
          </SelectTrigger>
          <SelectContent>
            {categories.map((cat) => {
              const catWorkflows = workflows.filter((w) => w.category === cat)
              // Category labels: use i18n if available, otherwise use raw category
              const CATEGORY_LABELS: Record<string, string> = {
                IDENTIDAD: 'Identidad',
                CONDUCCION: 'Conducción',
                CONTRATOS: 'Contratos',
                EXTRANJERIA: 'Extranjería',
                FUNCION_PUBLICA: 'Función Pública',
                VEHICULOS: 'Vehículos',
                OTROS: 'Otros',
              }
              const catLabel = CATEGORY_LABELS[cat] || cat

              return catWorkflows.map((wf) => (
                <SelectItem key={wf.code} value={wf.code}>
                  <span className="flex items-center gap-2">
                    <span className="text-xs text-gray-400">{catLabel}</span>
                    <span>{tw(workflowNameKey(wf.code), wf.service_name_es)}</span>
                  </span>
                </SelectItem>
              ))
            })}
          </SelectContent>
        </Select>
      </div>

      {solicitudTypes.length > 0 && (
        <div className="space-y-2">
          <Label htmlFor="solicitud-type">{t('workflowSelection.solicitudType')}</Label>
          <Select value={solicitudType} onValueChange={setSolicitudType}>
            <SelectTrigger id="solicitud-type">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {solicitudTypes.map((type) => {
                const SOLICITUD_LABELS: Record<string, string> = {
                  expedicion: 'Expedición',
                  renovacion: 'Renovación',
                  duplicado: 'Duplicado',
                  prorroga: 'Prórroga',
                  primera_matriculacion: 'Primera Matriculación',
                  renovacion_itv: 'Renovación ITV',
                  duplicado_permiso: 'Duplicado Permiso',
                }
                return (
                  <SelectItem key={type} value={type}>
                    {SOLICITUD_LABELS[type] || type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                  </SelectItem>
                )
              })}
            </SelectContent>
          </Select>
        </div>
      )}

      <div className="space-y-2">
        <Label htmlFor="notes">{t('workflowSelection.notes')}</Label>
        <Textarea
          id="notes"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={3}
        />
      </div>

      <div className="flex justify-end pt-4">
        <Button
          onClick={handleStart}
          disabled={!workflowCode || isLoading || loadingWorkflows}
          size="lg"
        >
          {isLoading ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin mr-2" />
              {t('workflowSelection.creatingSession')}
            </>
          ) : (
            <>
              {t('workflowSelection.start')}
              <ArrowRight className="h-4 w-4 ml-2" />
            </>
          )}
        </Button>
      </div>
    </div>
  )
}
