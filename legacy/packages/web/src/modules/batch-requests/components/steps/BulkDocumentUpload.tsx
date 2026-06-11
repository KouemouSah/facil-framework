'use client'

import { useState, useRef, useCallback } from 'react'
import { useTranslations } from 'next-intl'
import {
  Upload,
  FileText,
  Loader2,
  AlertCircle,
  CheckCircle,
  Info,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription } from '@/components/ui/alert'
import type { UseBatchSessionReturn } from '../../hooks/useBatchSession'
import type { ClassifyResponse } from '../../types'

interface BulkDocumentUploadProps {
  hook: UseBatchSessionReturn
}

export function BulkDocumentUpload({ hook }: BulkDocumentUploadProps) {
  const { isLoading, classifyDocuments } = hook
  const t = useTranslations('batch')

  const [selectedFiles, setSelectedFiles] = useState<File[]>([])
  const [classifyResult, setClassifyResult] = useState<ClassifyResponse | null>(null)
  const [isClassifying, setIsClassifying] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleFilesSelected = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || [])
    setSelectedFiles(files)
    setClassifyResult(null)
  }

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    const files = Array.from(e.dataTransfer.files)
    setSelectedFiles(files)
    setClassifyResult(null)
  }, [])

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
  }, [])

  const handleClassify = async () => {
    if (selectedFiles.length === 0) return
    setIsClassifying(true)
    const result = await classifyDocuments(selectedFiles)
    if (result) {
      setClassifyResult(result)
    }
    setIsClassifying(false)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <Upload className="h-5 w-5 text-blue-600" />
        <h2 className="text-lg font-semibold">{t('bulkUpload.title')}</h2>
      </div>

      <Alert>
        <Info className="h-4 w-4" />
        <AlertDescription>
          {t('bulkUpload.description')}
        </AlertDescription>
      </Alert>

      {/* Drop zone */}
      <div
        className="border-2 border-dashed rounded-lg p-8 text-center hover:border-blue-300 transition-colors cursor-pointer"
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onClick={() => fileInputRef.current?.click()}
      >
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".pdf,.jpg,.jpeg,.png"
          className="hidden"
          onChange={handleFilesSelected}
        />
        <Upload className="h-10 w-10 mx-auto text-gray-300 mb-3" />
        <p className="text-gray-500">
          {t('bulkUpload.dropzone')}
        </p>
        <p className="text-sm text-gray-400 mt-1">
          {t('bulkUpload.dropzoneHint')}
        </p>
      </div>

      {/* Selected files summary */}
      {selectedFiles.length > 0 && !classifyResult && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium">
              {selectedFiles.length} {t('bulkUpload.filesSelected')}
            </p>
            <Button
              onClick={handleClassify}
              disabled={isClassifying || isLoading}
            >
              {isClassifying ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  {t('bulkUpload.classifying')}
                </>
              ) : (
                <>
                  <FileText className="h-4 w-4 mr-2" />
                  {t('bulkUpload.classify')}
                </>
              )}
            </Button>
          </div>

          {isClassifying && (
            <div className="flex items-center justify-center gap-3 py-4">
              <Loader2 className="h-5 w-5 animate-spin text-blue-500" />
              <p className="text-sm text-gray-500">
                {t('bulkUpload.classifying')}
              </p>
            </div>
          )}

          <div className="max-h-48 overflow-y-auto space-y-1">
            {selectedFiles.map((file, idx) => (
              <div
                key={idx}
                className="flex items-center gap-2 text-sm text-gray-600 px-2 py-1"
              >
                <FileText className="h-3.5 w-3.5 text-gray-400" />
                <span className="truncate">{file.name}</span>
                <span className="text-gray-300 text-xs ml-auto">
                  {(file.size / 1024).toFixed(0)} KB
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Classification results */}
      {classifyResult && (
        <div className="space-y-4">
          <h3 className="text-sm font-semibold flex items-center gap-2">
            <CheckCircle className="h-4 w-4 text-green-500" />
            {t('bulkUpload.classificationDone')}
          </h3>

          {/* Stats */}
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
            <div className="bg-gray-50 rounded-lg p-3 text-center">
              <p className="text-2xl font-bold">{classifyResult.stats.totalFiles}</p>
              <p className="text-xs text-gray-500">{t('bulkUpload.total')}</p>
            </div>
            <div className="bg-green-50 rounded-lg p-3 text-center">
              <p className="text-2xl font-bold text-green-600">
                {classifyResult.stats.classified}
              </p>
              <p className="text-xs text-gray-500">{t('bulkUpload.classified')}</p>
            </div>
            <div className="bg-blue-50 rounded-lg p-3 text-center">
              <p className="text-2xl font-bold text-blue-600">
                {classifyResult.stats.matched}
              </p>
              <p className="text-xs text-gray-500">{t('bulkUpload.matched')}</p>
            </div>
            <div className="bg-amber-50 rounded-lg p-3 text-center">
              <p className="text-2xl font-bold text-amber-600">
                {classifyResult.stats.unmatched}
              </p>
              <p className="text-xs text-gray-500">{t('bulkUpload.unmatched')}</p>
            </div>
            <div className="bg-purple-50 rounded-lg p-3 text-center">
              <p className="text-2xl font-bold text-purple-600">
                {classifyResult.stats.shared}
              </p>
              <p className="text-xs text-gray-500">{t('bulkUpload.shared')}</p>
            </div>
          </div>

          {classifyResult.stats.unmatched > 0 && (
            <Alert className="border-amber-200 bg-amber-50">
              <AlertCircle className="h-4 w-4 text-amber-600" />
              <AlertDescription className="text-amber-700">
                {classifyResult.stats.unmatched} {t('bulkUpload.unmatchedWarning')}
              </AlertDescription>
            </Alert>
          )}

          {/* Classification list */}
          <div className="max-h-64 overflow-y-auto border rounded-lg divide-y">
            {classifyResult.classifications.map((c, idx) => (
              <div
                key={idx}
                className="flex items-center justify-between px-3 py-2 text-sm"
              >
                <div className="flex items-center gap-2 min-w-0">
                  <FileText className="h-4 w-4 text-gray-400 flex-shrink-0" />
                  <span className="truncate">{c.fileName}</span>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <Badge variant="outline" className="text-xs">
                    {c.documentType}
                  </Badge>
                  {c.matchedBeneficiaryId ? (
                    <Badge className="bg-green-100 text-green-700 text-xs">
                      {t('bulkUpload.matched')}
                    </Badge>
                  ) : (
                    <Badge className="bg-amber-100 text-amber-700 text-xs">
                      {t('bulkUpload.unmatched')}
                    </Badge>
                  )}
                  <span className="text-xs text-gray-400">
                    {Math.round(c.confidence * 100)}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
