'use client'

/**
 * DocumentUploader Component
 * Drag & drop file upload with preview and extraction status
 */

import { useState, useCallback, useRef } from 'react'
import { useTranslations } from 'next-intl'
import {
  Upload,
  FileText,
  AlertCircle,
  CheckCircle,
  Loader2,
  Eye,
  RefreshCw,
  Trash2,
  FolderOpen,
} from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { VaultDocumentPicker } from '@/modules/user-documents/components'

import type { DocumentRequirement, ServiceRequestDocument, ExtractionStatus } from '../types'

// ============================================================================
// PROPS
// ============================================================================

interface DocumentUploaderProps {
  requirement: DocumentRequirement
  uploadedDocument?: ServiceRequestDocument
  locale?: 'es' | 'fr' | 'en'
  onUpload: (file: File, face?: string) => Promise<void>
  onDelete?: () => Promise<void>
  onRetryExtraction?: () => Promise<void>
  onSelectFromVault?: (documentId: string, documentName: string) => void
  workflowCode?: string
  disabled?: boolean
  maxSizeMB?: number
}

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 Bytes'
  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

function getExtractionStatusConfig(status: ExtractionStatus | string) {
  const configs: Record<string, { color: string; icon: React.ComponentType<{ className?: string }>; label: string }> = {
    pending: { color: 'bg-gray-100 text-gray-800', icon: Loader2, label: 'Pendiente' },
    processing: { color: 'bg-blue-100 text-blue-800', icon: Loader2, label: 'Procesando' },
    completed: { color: 'bg-green-100 text-green-800', icon: CheckCircle, label: 'Completado' },
    failed: { color: 'bg-red-100 text-red-800', icon: AlertCircle, label: 'Fallido' },
    manual_review: { color: 'bg-yellow-100 text-yellow-800', icon: Eye, label: 'Revisión Manual' },
  }
  return configs[status] || configs.pending
}

function isImageFile(mimeType: string): boolean {
  return mimeType.startsWith('image/')
}

// ============================================================================
// MAIN COMPONENT
// ============================================================================

export function DocumentUploader({
  requirement,
  uploadedDocument,
  locale: _locale = 'es',  // TODO: Use for translations via translations module
  onUpload,
  onDelete,
  onRetryExtraction,
  onSelectFromVault,
  workflowCode,
  disabled = false,
  maxSizeMB = 5,
}: DocumentUploaderProps) {
  const t = useTranslations('service_requests')
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [showVaultPicker, setShowVaultPicker] = useState(false)

  // Get localized text - uses Spanish as base, translations via translations module
  const getDocumentName = useCallback(() => {
    // TODO: Integrate with translations module for fr/en
    return requirement.documentNameEs
  }, [requirement])

  const getInstructions = useCallback(() => {
    // TODO: Integrate with translations module for fr/en
    return requirement.instructionsEs
  }, [requirement])

  // Validate file
  const validateFile = useCallback((file: File): string | null => {
    // Check size
    const maxSize = maxSizeMB * 1024 * 1024
    if (file.size > maxSize) {
      return t('error_file_too_large', { max: maxSizeMB })
    }

    // Check format
    if (requirement.acceptedFormats && requirement.acceptedFormats.length > 0) {
      const ext = file.name.split('.').pop()?.toLowerCase()
      if (ext && !requirement.acceptedFormats.includes(ext)) {
        return t('error_invalid_format', { formats: requirement.acceptedFormats.join(', ') })
      }
    }

    return null
  }, [maxSizeMB, requirement.acceptedFormats, t])

  // Handle file selection
  const handleFileSelect = useCallback(async (file: File) => {
    const validationError = validateFile(file)
    if (validationError) {
      setError(validationError)
      return
    }

    setError(null)
    setIsUploading(true)
    setUploadProgress(0)

    // Create preview for images
    if (isImageFile(file.type)) {
      const url = URL.createObjectURL(file)
      setPreviewUrl(url)
    }

    // Simulate progress (real progress would come from API)
    const progressInterval = setInterval(() => {
      setUploadProgress(prev => {
        if (prev >= 90) {
          clearInterval(progressInterval)
          return prev
        }
        return prev + 10
      })
    }, 100)

    try {
      await onUpload(file)
      setUploadProgress(100)
    } catch (err) {
      setError(err instanceof Error ? err.message : t('error_upload_failed'))
    } finally {
      setIsUploading(false)
      clearInterval(progressInterval)
    }
  }, [validateFile, onUpload, t])

  // Drag and drop handlers
  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (!disabled) {
      setIsDragging(true)
    }
  }, [disabled])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)
  }, [])

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)

    if (disabled) return

    const file = e.dataTransfer.files[0]
    if (file) {
      handleFileSelect(file)
    }
  }, [disabled, handleFileSelect])

  // Handle delete
  const handleDelete = useCallback(async () => {
    if (onDelete) {
      try {
        await onDelete()
        setPreviewUrl(null)
      } catch (err) {
        setError(err instanceof Error ? err.message : t('error_delete_failed'))
      }
    }
  }, [onDelete, t])

  // Handle retry extraction
  const handleRetryExtraction = useCallback(async () => {
    if (onRetryExtraction) {
      try {
        await onRetryExtraction()
      } catch (err) {
        setError(err instanceof Error ? err.message : t('error_retry_failed'))
      }
    }
  }, [onRetryExtraction, t])

  // Render uploaded document state
  if (uploadedDocument) {
    const statusConfig = getExtractionStatusConfig(uploadedDocument.extractionStatus)
    const StatusIcon = statusConfig.icon
    const isImage = isImageFile(uploadedDocument.mimeType)

    return (
      <Card className="border-green-200 bg-green-50/50">
        <CardContent className="p-4">
          <div className="flex items-start gap-4">
            {/* Document Preview */}
            <div className="flex-shrink-0">
              {isImage && uploadedDocument.fileUrl ? (
                <Dialog>
                  <DialogTrigger asChild>
                    <button className="relative group cursor-pointer">
                      <img
                        src={uploadedDocument.fileUrl}
                        alt={uploadedDocument.fileName}
                        className="w-16 h-20 object-cover rounded border"
                      />
                      <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity rounded flex items-center justify-center">
                        <Eye className="h-5 w-5 text-white" />
                      </div>
                    </button>
                  </DialogTrigger>
                  <DialogContent className="max-w-3xl">
                    <DialogHeader>
                      <DialogTitle>{uploadedDocument.fileName}</DialogTitle>
                    </DialogHeader>
                    <img
                      src={uploadedDocument.fileUrl}
                      alt={uploadedDocument.fileName}
                      className="w-full h-auto"
                    />
                  </DialogContent>
                </Dialog>
              ) : (
                <div className="w-16 h-20 bg-gray-100 rounded border flex items-center justify-center">
                  <FileText className="h-8 w-8 text-gray-400" />
                </div>
              )}
            </div>

            {/* Document Info */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <h4 className="font-medium truncate">{getDocumentName()}</h4>
                {requirement.isRequired && (
                  <Badge variant="outline" className="text-xs">
                    {t('required')}
                  </Badge>
                )}
              </div>

              <p className="text-sm text-muted-foreground truncate">
                {uploadedDocument.fileName} • {formatFileSize(uploadedDocument.fileSize)}
              </p>

              {/* Extraction Status */}
              <div className="flex items-center gap-2 mt-2">
                <Badge className={statusConfig.color}>
                  <StatusIcon className={`h-3 w-3 mr-1 ${
                    uploadedDocument.extractionStatus === 'processing' ? 'animate-spin' : ''
                  }`} />
                  {statusConfig.label}
                </Badge>

                {uploadedDocument.extractionConfidence && (
                  <span className="text-xs text-muted-foreground">
                    {Math.round(uploadedDocument.extractionConfidence * 100)}% {t('confidence')}
                  </span>
                )}
              </div>

              {/* Validation Errors */}
              {uploadedDocument.validationErrors && uploadedDocument.validationErrors.length > 0 && (
                <div className="mt-2 p-2 bg-red-50 rounded text-sm text-red-700">
                  <ul className="list-disc list-inside">
                    {uploadedDocument.validationErrors.map((err, i) => (
                      <li key={i}>{err}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            {/* Actions */}
            <div className="flex flex-col gap-1">
              {uploadedDocument.extractionStatus === 'failed' && onRetryExtraction && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleRetryExtraction}
                  disabled={disabled}
                >
                  <RefreshCw className="h-4 w-4" />
                </Button>
              )}
              {onDelete && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleDelete}
                  disabled={disabled}
                  className="text-red-500 hover:text-red-700 hover:bg-red-50"
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              )}
            </div>
          </div>
        </CardContent>
      </Card>
    )
  }

  // Render upload state
  return (
    <Card className={`border-dashed ${isDragging ? 'border-primary bg-primary/5' : ''} ${disabled ? 'opacity-50' : ''}`}>
      <CardContent className="p-4">
        <div
          className="flex flex-col items-center justify-center py-6 cursor-pointer"
          onDragEnter={handleDragEnter}
          onDragLeave={handleDragLeave}
          onDragOver={handleDragOver}
          onDrop={handleDrop}
          onClick={() => !disabled && fileInputRef.current?.click()}
        >
          <input
            ref={fileInputRef}
            type="file"
            className="hidden"
            accept={requirement.acceptedFormats?.map(f => `.${f}`).join(',') || '*'}
            onChange={(e) => {
              const file = e.target.files?.[0]
              if (file) handleFileSelect(file)
            }}
            disabled={disabled || isUploading}
          />

          {isUploading ? (
            <>
              <Loader2 className="h-8 w-8 text-primary animate-spin mb-4" />
              <Progress value={uploadProgress} className="w-48 h-2 mb-2" />
              <p className="text-sm text-muted-foreground">{t('uploading')}...</p>
            </>
          ) : (
            <>
              <div className={`p-3 rounded-full mb-4 ${isDragging ? 'bg-primary/20' : 'bg-muted'}`}>
                <Upload className={`h-6 w-6 ${isDragging ? 'text-primary' : 'text-muted-foreground'}`} />
              </div>

              <div className="text-center">
                <h4 className="font-medium mb-1">
                  {getDocumentName()}
                  {requirement.isRequired && <span className="text-red-500 ml-1">*</span>}
                </h4>

                <p className="text-sm text-muted-foreground mb-2">
                  {t('drag_drop_or_click')}
                </p>

                {getInstructions() && (
                  <p className="text-xs text-muted-foreground mb-2">
                    {getInstructions()}
                  </p>
                )}

                <p className="text-xs text-muted-foreground">
                  {requirement.acceptedFormats
                    ? `${requirement.acceptedFormats.join(', ').toUpperCase()} • `
                    : ''}
                  Max {maxSizeMB}MB
                </p>

                {onSelectFromVault && (
                  <>
                    <div className="flex items-center gap-2 mt-3 w-full max-w-[200px]">
                      <div className="flex-1 h-px bg-border" />
                      <span className="text-xs text-muted-foreground">{t('or')}</span>
                      <div className="flex-1 h-px bg-border" />
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      className="mt-2"
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation()
                        setShowVaultPicker(true)
                      }}
                    >
                      <FolderOpen className="mr-2 h-4 w-4" strokeWidth={1.5} />
                      {t('fromVault')}
                    </Button>
                  </>
                )}
              </div>
            </>
          )}

          {/* Preview for new upload */}
          {previewUrl && !uploadedDocument && (
            <div className="mt-4">
              <img
                src={previewUrl}
                alt="Preview"
                className="max-h-32 rounded border"
              />
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="mt-4 flex items-center gap-2 text-red-600 text-sm">
              <AlertCircle className="h-4 w-4" />
              {error}
            </div>
          )}
        </div>
      </CardContent>

      {/* Vault Document Picker Dialog */}
      {onSelectFromVault && (
        <VaultDocumentPicker
          open={showVaultPicker}
          onOpenChange={setShowVaultPicker}
          workflowCode={workflowCode}
          onSelect={(documentId, documentName) => {
            onSelectFromVault(documentId, documentName)
            setShowVaultPicker(false)
          }}
        />
      )}
    </Card>
  )
}

export default DocumentUploader
