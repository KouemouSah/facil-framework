'use client'

import { useState, useRef, useEffect, useMemo } from 'react'
import { useTranslations, useLocale } from 'next-intl'
import { getLocalizedName } from '@/core/utils/i18n-helpers'
import { FileUp, Trash2, FileCheck, Loader2, Info } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

import { Alert, AlertDescription } from '@/components/ui/alert'
import type { UseBatchSessionReturn } from '../../hooks/useBatchSession'
import type { BatchWorkflowOption, WorkflowDocumentOption } from '../../types'
import { batchApi } from '../../services/batch-api'

interface SharedDocumentsProps {
  hook: UseBatchSessionReturn
}

export function SharedDocuments({ hook }: SharedDocumentsProps) {
  const {
    session,
    isSaving,
    uploadSharedDocument,
    removeSharedDocument,
  } = hook
  const t = useTranslations('batch')
  const locale = useLocale()

  const [selectedCode, setSelectedCode] = useState('')
  const [isUploading, setIsUploading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // F-007: Fetch document types from workflow configuration
  const [workflows, setWorkflows] = useState<BatchWorkflowOption[]>([])
  const [loadingDocs, setLoadingDocs] = useState(true)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const resp = await batchApi.getAvailableWorkflows()
        if (!cancelled) setWorkflows(resp.workflows)
      } catch (e) {
        console.error('[SharedDocuments] Failed to load workflows:', e)
      } finally {
        if (!cancelled) setLoadingDocs(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [])

  // Derive document options from workflow + solicitud type
  const documentOptions: WorkflowDocumentOption[] = useMemo(() => {
    if (!session || !workflows.length) return []

    const wf = workflows.find((w) =>
      w.code === session.workflowCode ||
      w.all_workflow_codes.includes(session.workflowCode)
    )
    if (!wf) return []

    const solType = session.solicitudType || wf.allowed_solicitud_types[0] || 'expedicion'
    const docs = wf.documents_by_solicitud_type[solType] || []

    // Sort by display_order
    return [...docs].sort((a, b) => a.display_order - b.display_order)
  }, [session, workflows])

  const sharedDocs = session?.sharedDocuments || []
  const uploadedCodes = new Set(sharedDocs.map((d) => d.documentCode))

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file || !selectedCode) return

    setIsUploading(true)
    const result = await uploadSharedDocument(file, selectedCode)
    setIsUploading(false)

    if (result) {
      setSelectedCode('')
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const handleRemove = async (documentCode: string) => {
    await removeSharedDocument(documentCode)
  }

  // Helper to get label for a document code
  const getDocLabel = (code: string): string => {
    const doc = documentOptions.find((d) => d.code === code)
    if (doc) return getLocalizedName(doc as unknown as Record<string, unknown>, locale) || code

    return code
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <FileUp className="h-5 w-5 text-blue-600" />
        <h2 className="text-lg font-semibold">{t('sharedDocs.title')}</h2>
      </div>

      <Alert>
        <Info className="h-4 w-4" />
        <AlertDescription>
          {t('sharedDocs.description')}
        </AlertDescription>
      </Alert>

      <div className="flex items-end gap-3">
        <div className="flex-1 space-y-1">
          <Label>{t('sharedDocs.selectType')}</Label>
          <select
            className="w-full border rounded-md px-3 py-2 text-sm"
            value={selectedCode}
            onChange={(e) => setSelectedCode(e.target.value)}
            disabled={loadingDocs}
          >
            <option value="">{loadingDocs ? '...' : '...'}</option>
            {documentOptions
              .filter((doc) => !uploadedCodes.has(doc.code))
              .map((doc) => (
                <option key={doc.code} value={doc.code}>
                  {getDocLabel(doc.code)}
                  {doc.is_required ? ' *' : ''}
                </option>
              ))}
          </select>
        </div>
        <div className="flex-1 space-y-1">
          <Label>{t('sharedDocs.file')}</Label>
          <Input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.jpg,.jpeg,.png"
            onChange={handleUpload}
            disabled={!selectedCode || isUploading}
          />
        </div>
        {isUploading && (
          <Loader2 className="h-5 w-5 animate-spin text-blue-500 mb-2" />
        )}
      </div>

      {sharedDocs.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-sm font-medium text-gray-500">
            {t('sharedDocs.uploaded')} ({sharedDocs.length})
          </h3>
          {sharedDocs.map((doc) => (
            <div
              key={doc.documentCode}
              className="flex items-center justify-between p-3 border rounded-lg"
            >
              <div className="flex items-center gap-3">
                <FileCheck className="h-5 w-5 text-green-500" />
                <div>
                  <p className="text-sm font-medium">{getDocLabel(doc.documentCode)}</p>
                  <p className="text-xs text-gray-400">{doc.fileName}</p>
                </div>
              </div>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 text-red-500 hover:text-red-700"
                onClick={() => handleRemove(doc.documentCode)}
                disabled={isSaving}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          ))}
        </div>
      )}

      {sharedDocs.length === 0 && (
        <div className="text-center py-8 text-gray-400 text-sm">
          {t('sharedDocs.noDocuments')}
        </div>
      )}
    </div>
  )
}
