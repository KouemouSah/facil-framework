'use client'

/**
 * Documents Upload Page
 * Full page for uploading required documents based on workflow configuration
 */

import { useEffect, useState, useCallback, useRef } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { useTranslations } from 'next-intl'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Progress } from '@/components/ui/progress'
// Input component removed - not used
import {
  ArrowLeft,
  FileText,
  CheckCircle,
  AlertCircle,
  Upload,
  Loader2,
  ExternalLink,
  ArrowRight,
} from 'lucide-react'
import { useServiceRequests } from '@/modules/service-requests'
import { DocumentPreviewDialog } from '@/modules/service-requests/components'
// WorkflowConfig import removed - not needed with simplified logic

// Document requirement interface matching workflow
interface DocumentRequirement {
  documentCode: string
  documentNameKey: string  // Translation key
  isRequired: boolean
  instructionsKey?: string  // Translation key
  acceptedFormats?: string[]
  conditionType?: 'ALWAYS' | 'IS_MINOR' | 'IS_NEW' | 'CUSTOM'
}

// Check if user is minor (age < 18)
const isUserMinor = (birthDate?: string): boolean => {
  if (!birthDate) return false
  const birth = new Date(birthDate)
  const today = new Date()
  const age = today.getFullYear() - birth.getFullYear()
  const monthDiff = today.getMonth() - birth.getMonth()
  if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < birth.getDate())) {
    return age - 1 < 18
  }
  return age < 18
}

export default function DocumentsUploadPage() {
  const params = useParams()
  const router = useRouter()
  const locale = params.locale as string
  const requestId = params.id as string
  const t = useTranslations('service_requests')

  const {
    currentRequest,
    documents,
    isLoading,
    isSaving: _isSaving,
    error,
    loadRequest,
    loadDocuments,
    loadWorkflows,
    uploadDocument: _uploadDocument, // Legacy direct upload (kept as fallback)
    previewDocument, // NEW: Two-step preview flow
    validateDocument, // NEW: Validate and save after preview
    currentPreview,
    clearPreview,
    clearError,
  } = useServiceRequests()



  // Upload state
  const [uploadingDocCode, setUploadingDocCode] = useState<string | null>(null)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null)
  const fileInputRefs = useRef<Record<string, HTMLInputElement | null>>({})

  // Preview dialog state
  const [showPreviewDialog, setShowPreviewDialog] = useState(false)
  const [previewingDocCode, setPreviewingDocCode] = useState<string | null>(null)
  const [isConfirmingPreview, setIsConfirmingPreview] = useState(false)

  // Load request and documents on mount
  useEffect(() => {
    if (requestId) {
      loadRequest(requestId)
      loadDocuments()
      loadWorkflows()  // Keep for future use
    }
  }, [requestId, loadRequest, loadDocuments, loadWorkflows])

  // Get required documents based on workflow and sub_type
  // This logic MUST match pasaporte_workflow.py exactly
  const getRequiredDocuments = useCallback((): DocumentRequirement[] => {
    if (!currentRequest) return []

    const workflowCode = currentRequest.workflowCode?.toUpperCase() || ''
    const subType = currentRequest.subType?.toUpperCase() || 'NUEVO'

    // Check if user is minor (for conditional documents)
    const userIsMinor = isUserMinor(currentRequest.formData?.fecha_nacimiento as string | undefined)

    // Detect if this is a passport workflow (any variant)
    const isPasaporte = workflowCode.includes('PASAPORTE')

    let docs: DocumentRequirement[] = []

    if (isPasaporte) {
      // DIP is ALWAYS required for passport
      docs.push({
        documentCode: 'dip',
        documentNameKey: 'document_types.dip',
        isRequired: true,
        instructionsKey: 'document_instructions.dip',
        conditionType: 'ALWAYS'
      })

      // Type-specific documents based on sub_type
      if (subType === 'NUEVO') {
        docs.push({
          documentCode: 'certificado_nacimiento',
          documentNameKey: 'document_types.birth_certificate',
          isRequired: true,
          instructionsKey: 'document_instructions.birth_certificate',
          conditionType: 'IS_NEW'
        })
      } else if (subType === 'RENOVACION' || subType === 'DETERIORO') {
        docs.push({
          documentCode: 'pasaporte_antiguo',
          documentNameKey: subType === 'DETERIORO' ? 'document_types.damaged_passport' : 'document_types.old_passport',
          isRequired: true,
          instructionsKey: subType === 'DETERIORO' ? 'document_instructions.damaged_passport' : 'document_instructions.old_passport'
        })
      } else if (subType === 'PERDIDA' || subType === 'ROBO') {
        docs.push({
          documentCode: 'denuncia_policial',
          documentNameKey: 'document_types.police_report',
          isRequired: true,
          instructionsKey: subType === 'ROBO' ? 'document_instructions.police_report_theft' : 'document_instructions.police_report_loss'
        })
      }

      // Photos are ALWAYS required for passport
      docs.push({
        documentCode: 'photo_carnet',
        documentNameKey: 'document_types.passport_photos',
        isRequired: true,
        instructionsKey: 'document_instructions.passport_photos',
        conditionType: 'ALWAYS'
      })

      // Parental authorization for minors (IS_MINOR condition)
      if (userIsMinor) {
        docs.push({
          documentCode: 'autorizacion_parental',
          documentNameKey: 'document_types.parental_authorization',
          isRequired: true,
          instructionsKey: 'document_instructions.parental_authorization',
          conditionType: 'IS_MINOR'
        })
      }
    } else if (workflowCode.includes('RESIDENCIA')) {
      // Residencia workflow
      docs.push({
        documentCode: 'pasaporte',
        documentNameKey: 'document_types.valid_passport',
        isRequired: true
      })
      docs.push({
        documentCode: 'foto_carnet',
        documentNameKey: 'document_types.id_photo',
        isRequired: true
      })
      if (subType === 'RENOVACION') {
        docs.push({
          documentCode: 'carnet_residencia_antiguo',
          documentNameKey: 'document_types.current_residence_card',
          isRequired: true
        })
      }
    } else {
      // Default fallback for unknown workflows
      docs = [
        { documentCode: 'dip', documentNameKey: 'document_types.dip', isRequired: true },
        { documentCode: 'foto_carnet', documentNameKey: 'document_types.id_photo', isRequired: true },
      ]
    }

    return docs
  }, [currentRequest])

  // Check if document is already uploaded
  const isDocumentUploaded = (docCode: string): boolean => {
    return documents.some(d => d.documentCode === docCode || d.documentCode?.toLowerCase() === docCode.toLowerCase())
  }

  // Get uploaded document for a code
  const getUploadedDocument = (docCode: string) => {
    return documents.find(d => d.documentCode === docCode || d.documentCode?.toLowerCase() === docCode.toLowerCase())
  }

  // Handle file upload - TWO-STEP PREVIEW FLOW
  // Step 1: Preview extraction without saving
  const handleFileUpload = useCallback(async (docCode: string, event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    setUploadingDocCode(docCode)
    setPreviewingDocCode(docCode)
    setUploadError(null)
    setUploadSuccess(null)
    setUploadProgress(10)

    let progressInterval: ReturnType<typeof setInterval> | null = null

    try {
      progressInterval = setInterval(() => {
        setUploadProgress(prev => Math.min(prev + 15, 80))
      }, 200)

      // Call preview endpoint - document NOT saved yet
      const preview = await previewDocument(docCode, file)

      if (progressInterval) clearInterval(progressInterval)
      setUploadProgress(100)

      if (preview) {
        // Open preview dialog for user validation
        setShowPreviewDialog(true)
      }

      setUploadingDocCode(null)
      setUploadProgress(0)
    } catch (err) {
      if (progressInterval) clearInterval(progressInterval)
      setUploadError(err instanceof Error ? err.message : t('documents.upload_error'))
      setUploadProgress(0)
      setUploadingDocCode(null)
      setPreviewingDocCode(null)
    }
  }, [previewDocument, t])

  // Step 2: Confirm preview and save document
  const handleConfirmPreview = useCallback(async (
    confirmedData: Record<string, unknown>,
    userNotes?: string
  ) => {
    if (!currentPreview) return

    setIsConfirmingPreview(true)
    try {
      const result = await validateDocument(
        currentPreview.previewId,
        confirmedData,
        userNotes
      )

      if (result) {
        setUploadSuccess(previewingDocCode)
        setShowPreviewDialog(false)
        setPreviewingDocCode(null)
        // Refresh documents list
        await loadDocuments()
      }
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : t('documents.validation_error'))
    } finally {
      setIsConfirmingPreview(false)
    }
  }, [currentPreview, validateDocument, previewingDocCode, loadDocuments, t])

  // Cancel preview dialog
  const handleCancelPreview = useCallback(() => {
    setShowPreviewDialog(false)
    setPreviewingDocCode(null)
    clearPreview()
  }, [clearPreview])

  // Calculate progress
  const requiredDocs = getRequiredDocuments()
  const uploadedCount = requiredDocs.filter(doc => isDocumentUploaded(doc.documentCode)).length
  const totalRequired = requiredDocs.filter(doc => doc.isRequired).length
  const allRequiredUploaded = requiredDocs.every(doc => !doc.isRequired || isDocumentUploaded(doc.documentCode))

  // Loading state
  if (isLoading && !currentRequest) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin mx-auto mb-4 text-primary" />
          <p className="text-muted-foreground">{t('loading')}</p>
        </div>
      </div>
    )
  }

  // Error state
  if (error) {
    return (
      <div className="space-y-6">
        <Button variant="ghost" onClick={() => router.back()}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          {t('back')}
        </Button>
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
        <Button onClick={() => { clearError(); loadRequest(requestId); }}>
          {t('retry')}
        </Button>
      </div>
    )
  }

  if (!currentRequest) {
    return (
      <div className="space-y-6">
        <Button variant="ghost" onClick={() => router.back()}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          {t('back')}
        </Button>
        <Alert>
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>{t('no_requests_found')}</AlertTitle>
        </Alert>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="sm" onClick={() => router.push(`/${locale}/dashboard/service-requests/${requestId}`)}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            {t('back')}
          </Button>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">
              {t('upload_documents')}
            </h1>
            <p className="text-muted-foreground">
              {currentRequest.requestNumber} - {currentRequest.workflowCode}
            </p>
          </div>
        </div>
        <Badge variant={allRequiredUploaded ? 'default' : 'secondary'}>
          {uploadedCount} / {totalRequired} {t('documents.required')}
        </Badge>
      </div>

      {/* Progress */}
      <Card>
        <CardContent className="pt-6">
          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <span>{t('upload_progress')}</span>
              <span>{Math.round((uploadedCount / Math.max(totalRequired, 1)) * 100)}%</span>
            </div>
            <Progress value={(uploadedCount / Math.max(totalRequired, 1)) * 100} className="h-2" />
          </div>
        </CardContent>
      </Card>

      {/* Sub-type info */}
      {currentRequest.subType && (
        <Alert>
          <FileText className="h-4 w-4" />
          <AlertTitle>{t('sub_type')}: {t(`sub_types.${currentRequest.subType?.toLowerCase()}`) || currentRequest.subType}</AlertTitle>
          <AlertDescription>
            {t('documents_for_subtype')}
          </AlertDescription>
        </Alert>
      )}

      {/* Error message */}
      {uploadError && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{uploadError}</AlertDescription>
        </Alert>
      )}

      {/* Documents List */}
      <div className="space-y-4">
        {requiredDocs.map((doc) => {
          const isUploaded = isDocumentUploaded(doc.documentCode)
          const uploadedDoc = getUploadedDocument(doc.documentCode)
          const isCurrentlyUploading = uploadingDocCode === doc.documentCode
          const justUploaded = uploadSuccess === doc.documentCode

          return (
            <Card
              key={doc.documentCode}
              className={isUploaded ? 'border-green-200 bg-green-50/50' : doc.isRequired ? 'border-orange-200' : ''}
            >
              <CardContent className="p-6">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-start gap-4 flex-1">
                    <div className={`p-3 rounded-lg ${isUploaded ? 'bg-green-100' : 'bg-muted'}`}>
                      {isUploaded ? (
                        <CheckCircle className="h-6 w-6 text-green-600" />
                      ) : (
                        <FileText className="h-6 w-6 text-muted-foreground" />
                      )}
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <h3 className="font-medium">{t(doc.documentNameKey)}</h3>
                        {doc.isRequired && (
                          <Badge variant="outline" className="text-xs">
                            {t('documents.required')}
                          </Badge>
                        )}
                      </div>

                      {doc.instructionsKey && (
                        <p className="text-sm text-muted-foreground mb-2">{t(doc.instructionsKey)}</p>
                      )}

                      {isUploaded && uploadedDoc && (
                        <div className="flex items-center gap-2 text-sm text-green-700">
                          <CheckCircle className="h-4 w-4" />
                          <span>{uploadedDoc.fileName}</span>
                          {uploadedDoc.fileUrl && (
                            <a
                              href={uploadedDoc.fileUrl}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-blue-600 hover:underline flex items-center gap-1"
                            >
                              <ExternalLink className="h-3 w-3" />
                              {t('documents.preview')}
                            </a>
                          )}
                        </div>
                      )}

                      {isCurrentlyUploading && (
                        <div className="mt-2 space-y-2">
                          <Progress value={uploadProgress} className="h-2" />
                          <p className="text-sm text-muted-foreground">{t('documents.uploading')} {uploadProgress}%</p>
                        </div>
                      )}

                      {justUploaded && !isCurrentlyUploading && (
                        <div className="mt-2 flex items-center gap-2 text-green-600">
                          <CheckCircle className="h-4 w-4" />
                          <span className="text-sm">{t('documents.upload_success')}</span>
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="flex-shrink-0">
                    {!isUploaded ? (
                      <div>
                        <input
                          type="file"
                          accept=".pdf,.jpg,.jpeg,.png"
                          className="hidden"
                          ref={el => { fileInputRefs.current[doc.documentCode] = el }}
                          onChange={(e) => handleFileUpload(doc.documentCode, e)}
                          disabled={isCurrentlyUploading}
                        />
                        <Button
                          onClick={() => fileInputRefs.current[doc.documentCode]?.click()}
                          disabled={isCurrentlyUploading}
                          variant={doc.isRequired ? 'default' : 'outline'}
                        >
                          {isCurrentlyUploading ? (
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          ) : (
                            <Upload className="mr-2 h-4 w-4" />
                          )}
                          {t('upload') || 'Subir'}
                        </Button>
                      </div>
                    ) : (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => fileInputRefs.current[doc.documentCode]?.click()}
                      >
                        <input
                          type="file"
                          accept=".pdf,.jpg,.jpeg,.png"
                          className="hidden"
                          ref={el => { fileInputRefs.current[doc.documentCode] = el }}
                          onChange={(e) => handleFileUpload(doc.documentCode, e)}
                        />
                        {t('replace') || 'Reemplazar'}
                      </Button>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          )
        })}
      </div>

      {/* Bottom Actions */}
      <div className="flex justify-between pt-4 border-t">
        <Button
          variant="outline"
          onClick={() => router.push(`/${locale}/dashboard/service-requests/${requestId}`)}
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          {t('back_to_request') || 'Volver a la solicitud'}
        </Button>

        {allRequiredUploaded && (
          <Button onClick={() => router.push(`/${locale}/dashboard/service-requests/${requestId}`)}>
            {t('continue') || 'Continuar'}
            <ArrowRight className="ml-2 h-4 w-4" />
          </Button>
        )}
      </div>

      {/* Accepted formats info */}
      <p className="text-xs text-center text-muted-foreground">
        {t('accepted_formats') || 'Formatos aceptados'}: PDF, JPG, PNG. {t('max_size') || 'Tamaño máximo'}: 5MB
      </p>
      {/* Document Preview Dialog - Two-Step Validation */}
      <DocumentPreviewDialog
        preview={currentPreview}
        isOpen={showPreviewDialog}
        onClose={handleCancelPreview}
        onConfirm={handleConfirmPreview}
        isConfirming={isConfirmingPreview}
        locale={locale as 'es' | 'fr' | 'en'}
      />
    </div>
  )
}
