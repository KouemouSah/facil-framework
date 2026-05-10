'use client'

/**
 * Passport Workflow Wizard Page - IMPROVED VERSION
 *
 * Improvements implemented:
 * 1. Two-step document preview/validate flow (recommended)
 * 2. ExtractionPreview component for confidence/risk display
 * 3. getFormData() integration for pre-filled forms
 * 4. Cross-document validation during extraction (Gemini processor)
 * 5. checkPaymentStatus() polling
 * 6. SMS/Email notifications for appointments
 *
 * Steps:
 * 0. is_minor - Minor/Adult selection
 * 1. select_type - EXPEDICION or RENOVACION
 * 1b. select_motivo - If RENOVACION: VENCIMIENTO, PERDIDA, ROBO, DETERIORO
 * 2. upload_documents - All documents with preview/validate flow
 * 3. form_review_1 - Datos Personales + Domicilio (pre-filled)
 * 4. form_review_2 - Filiacion + Pasaporte Anterior (pre-filled)
 * 5. validation - Cross-document validation results
 * 6. payment - Mobile Money payment with status polling
 * 7. appointment - Select appointment with notifications
 * 8. confirmation - Final summary with PDF download
 */

import { useState, useEffect, useCallback, useRef, useMemo } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { useTranslations } from 'next-intl'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import {
  ArrowLeft,
  ArrowRight,
  UserCheck,
  Loader2,
  AlertCircle,
  CheckCircle,
  Baby,
  CreditCard,
  Smartphone,
  Banknote,
  Download,
  Eye,
  AlertTriangle,
  FileCheck,
  RefreshCw,
  Bell,
  Building2,
  Clock,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react'
import {
  useServiceRequests,
  DocumentUploader,
  AppointmentSelection,
  CitizenSummaryForm,
  notificationService,
  IdentityMismatchBlocker,
  DynamicFormRenderer,
  useFormConfig,
  usePrefetchFormConfig,
  useInvalidateFormConfig,
  validateFormConfig,
} from '@/modules/service-requests'
import { FEATURE_DYNAMIC_FORM_RENDERER } from '@/core/config/features'
import type { IdentityMismatch } from '@/modules/service-requests'
import type {
  DocumentRequirement,
  ServiceRequestDocument,
  CitizenSummaryResponse,
  EntityLocation,
  AvailableSlot,
  AppointmentHoldStatus,
  FormDataResponse,
  PassportSolicitudType,
  PassportRenovacionMotivo,
  DocumentExtractionPreview,
  PaymentMethodInfo,
} from '@/modules/service-requests'
import {
  DocumentConditionType,
  PASSPORT_WIZARD_STEPS,
  PASSPORT_TARIFFS,
  getVisiblePassportSteps,
} from '@/modules/service-requests'
import { PaymentMethod } from '@/types/payment'

// Use shared constants from types/index.ts
// NOTE: WIZARD_STEPS is now computed dynamically based on isMinor and solicitudType
// See the useMemo hook below for the actual visible steps
const _ALL_STEPS = PASSPORT_WIZARD_STEPS
const TARIFFS = PASSPORT_TARIFFS

// Solicitud types - Use shared types
type SolicitudType = PassportSolicitudType
type RenovacionMotivo = PassportRenovacionMotivo

interface WizardState {
  isMinor: boolean | null
  solicitudType: SolicitudType | null
  motivo: RenovacionMotivo | null
  representanteUnico: boolean | null // For minors: true = single parent, false = both parents
  motivoRepresentanteUnico: string | null // Reason for single representative
}

export default function PassportWizardPage() {
  const params = useParams()
  const router = useRouter()
  const locale = (params.locale as string) || 'es'
  const requestId = params.id as string
  const t = useTranslations('service_requests')

  // Local wizard state
  const [currentStepIndex, setCurrentStepIndex] = useState(0)
  const [wizardState, setWizardState] = useState<WizardState>({
    isMinor: null,
    solicitudType: null,
    motivo: null,
    representanteUnico: null,
    motivoRepresentanteUnico: null,
  })
  // isSaving is kept for UI components but no longer set during step transitions
  // Step transitions are now synchronous (data stored locally, saved at final validation)
  const [isSaving] = useState(false)

  // Compute visible steps based on wizard state (isMinor and solicitudType)
  // This filters out minor-only steps for adults and vice versa
  const visibleSteps = useMemo(() => {
    return getVisiblePassportSteps(wizardState.solicitudType ?? undefined, wizardState.isMinor)
  }, [wizardState.solicitudType, wizardState.isMinor])

  // Dynamically compute the LAST form_review step (not hardcoded to form_review_2)
  // This handles cases where form_review_2 sections are all filtered out
  const lastFormReviewStepId = useMemo(() => {
    const formReviewSteps = visibleSteps.filter(s => s.id.startsWith('form_review_'))
    if (formReviewSteps.length === 0) return null
    return formReviewSteps[formReviewSteps.length - 1].id
  }, [visibleSteps])

  // Service requests hook
  const {
    currentRequest,
    documents,
    isLoading: _isLoading,
    error,
    loadRequest,
    saveStepData,
    clearError,
    // Document methods - using 2-step preview/validate flow
    previewDocument,
    validateDocument,
    deleteDocument,
    // Form methods
    getFormData,
    // Summary & PDF
    getCitizenSummary,
    downloadSummaryPDF,
    // Payment methods
    prepareForPayment,
    getPaymentMethods,
    initiatePayment,
    checkPaymentStatus,
    // Appointment methods
    getAppointmentLocations,
    getAvailableDays,
    getAppointmentSlots,
    holdAppointmentSlot,
    getAppointmentHoldStatus,
    releaseAppointmentHold,
  } = useServiceRequests()

  // Payment state
  const [selectedPaymentMethod, setSelectedPaymentMethod] = useState<PaymentMethod | null>(null)
  const [phoneNumber, setPhoneNumber] = useState('')
  const [isProcessingPayment, setIsProcessingPayment] = useState(false)
  const [paymentComplete, setPaymentComplete] = useState(false)
  const [availablePaymentMethods, setAvailablePaymentMethods] = useState<PaymentMethodInfo[]>([])
  const [isLoadingPaymentMethods, setIsLoadingPaymentMethods] = useState(false)
  const [paymentMethodsError, setPaymentMethodsError] = useState<string | null>(null)
  // Store payment result for cash payments (reference number, instructions)
  const [pendingPaymentResult, setPendingPaymentResult] = useState<{
    paymentReference?: string
    messageEs?: string
    actionType?: string
    isManualPayment: boolean
  } | null>(null)
  const paymentPollRef = useRef<NodeJS.Timeout | null>(null)

  // Document preview state - stores extraction data from 2-step flow
  // Key: documentCode, Value: preview data from previewDocument API
  const [documentPreviews, setDocumentPreviews] = useState<Record<string, DocumentExtractionPreview>>({})
  const [isUploadingDocument, setIsUploadingDocument] = useState<string | null>(null)

  // Ref to access latest documentPreviews (avoids stale closures in callbacks)
  const documentPreviewsRef = useRef<Record<string, DocumentExtractionPreview>>(documentPreviews)
  useEffect(() => {
    documentPreviewsRef.current = documentPreviews
    console.log('[Wizard] documentPreviews updated:', Object.keys(documentPreviews))
  }, [documentPreviews])

  // Form review state - edited data during review steps
  const [editedFormData, setEditedFormData] = useState<Record<string, unknown>>({})
  const [isSavingFormData, setIsSavingFormData] = useState(false)
  const [formSaveError, setFormSaveError] = useState<string | null>(null)

  // Form data state
  const [formData, setFormData] = useState<FormDataResponse | null>(null)
  const [isLoadingFormData, setIsLoadingFormData] = useState(false)

  // Confirmation state
  const [citizenSummary, setCitizenSummary] = useState<CitizenSummaryResponse | null>(null)

  // Notification state
  const [notificationsSent, setNotificationsSent] = useState(false)

  // Identity mismatch state - for blocking when documents don't match
  const [identityMismatches, setIdentityMismatches] = useState<IdentityMismatch[]>([])
  const [showMismatchBlocker, setShowMismatchBlocker] = useState(false)

  // Form config cache invalidation (for dynamic form feature)
  const { invalidateRequest: invalidateFormConfigCache } = useInvalidateFormConfig()

  // Load request on mount
  useEffect(() => {
    if (requestId) {
      loadRequest(requestId)
    }
  }, [requestId, loadRequest])

  // Cleanup payment polling on unmount
  useEffect(() => {
    return () => {
      if (paymentPollRef.current) {
        clearInterval(paymentPollRef.current)
      }
    }
  }, [])

  // Track if initial step determination has been done
  const hasInitializedStep = useRef(false)

  // Initialize wizard state from request form_data (runs on every request update)
  useEffect(() => {
    if (currentRequest) {
      const data = currentRequest.formData as Record<string, unknown> | undefined

      // Always update wizard state from form data
      if (data) {
        setWizardState({
          isMinor: data.is_minor as boolean | null ?? null,
          solicitudType: data.solicitud_type as SolicitudType | null ?? null,
          motivo: data.motivo as RenovacionMotivo | null ?? null,
          representanteUnico: data.representante_unico as boolean | null ?? null,
          motivoRepresentanteUnico: data.motivo_representante_unico as string | null ?? null,
        })
      }
    }
  }, [currentRequest])

  // Determine initial step ONLY ONCE when request first loads
  useEffect(() => {
    if (currentRequest && !hasInitializedStep.current) {
      hasInitializedStep.current = true
      const data = currentRequest.formData as Record<string, unknown> | undefined

      // Determine step based on status FIRST, then form data
      const stepFromStatus = getStepFromStatus(currentRequest.status)
      if (stepFromStatus !== null) {
        setCurrentStepIndex(stepFromStatus)
        return
      }

      // For DRAFT status, determine step from form data and documents
      // Note: Step indices correspond to visibleSteps array which changes based on isMinor/solicitudType
      if (data) {
        const isMinor = data.is_minor as boolean | null
        const solicitudType = data.solicitud_type as string | null
        const motivo = data.motivo as string | null
        const representanteUnico = data.representante_unico as boolean | null

        if (isMinor === undefined || isMinor === null) {
          setCurrentStepIndex(0) // is_minor step
        } else if (!solicitudType) {
          setCurrentStepIndex(1) // select_type step
        } else if (solicitudType === 'RENOVACION' && !motivo) {
          setCurrentStepIndex(2) // select_motivo step
        } else if (isMinor && representanteUnico === null) {
          // For minors: must complete representantes_legales before upload_documents
          // Index depends on whether motivo step is visible
          const repIndex = solicitudType === 'RENOVACION' ? 3 : 2
          setCurrentStepIndex(repIndex) // representantes_legales step
        } else if (documents.length === 0) {
          // upload_documents step - index depends on visible steps
          const uploadIndex = isMinor
            ? (solicitudType === 'RENOVACION' ? 4 : 3)
            : (solicitudType === 'RENOVACION' ? 3 : 2)
          setCurrentStepIndex(uploadIndex)
        } else {
          // form_review_1 step - index depends on visible steps
          const formIndex = isMinor
            ? (solicitudType === 'RENOVACION' ? 5 : 4)
            : (solicitudType === 'RENOVACION' ? 4 : 3)
          setCurrentStepIndex(formIndex)
        }
      } else {
        setCurrentStepIndex(0)
      }
    }
  }, [currentRequest, documents.length])

  // Map status to step index
  function getStepFromStatus(status: string): number | null {
    const statusToStep: Record<string, number> = {
      'SUBMITTED': 6, // validation done, waiting
      'DOCUMENTS_REQUIRED': 3, // back to documents
      'UNDER_REVIEW': 6, // validation
      'DOSSIER_VALIDE': 7, // payment
      'PAYMENT_PENDING': 7, // payment
      'PAID': 8, // appointment
      'CITA_SCHEDULED': 9, // confirmation
      'IN_PROGRESS': 9, // confirmation
      'COMPLETED': 9, // confirmation
    }
    return statusToStep[status] ?? null // null means use form data logic
  }

  // Get current step
  const currentStep = visibleSteps[currentStepIndex]

  // Calculate progress percentage
  const progressPercent = ((currentStepIndex + 1) / visibleSteps.length) * 100

  // Calculate tariff based on selection
  const getTariff = (): number => {
    if (wizardState.solicitudType === 'EXPEDICION') {
      return TARIFFS.EXPEDICION
    }
    if (wizardState.solicitudType === 'RENOVACION' && wizardState.motivo) {
      return TARIFFS[wizardState.motivo] || 0
    }
    return 0
  }

  // Handle minor selection
  // Data kept in memory until form_review validation (as per user requirement)
  const handleMinorSelect = (isMinor: boolean) => {
    clearError()
    setWizardState(prev => ({ ...prev, isMinor }))
    setCurrentStepIndex(1)
  }

  // Handle type selection
  // Data kept in memory until form_review validation (as per user requirement)
  const handleTypeSelect = (type: SolicitudType) => {
    clearError()
    setWizardState(prev => ({ ...prev, solicitudType: type, motivo: null }))

    if (type === 'RENOVACION') {
      setCurrentStepIndex(2)
    } else {
      setCurrentStepIndex(3)
    }
  }

  // Handle motivo selection
  // Data kept in memory until form_review validation (as per user requirement)
  const handleMotivoSelect = (motivo: RenovacionMotivo) => {
    clearError()
    setWizardState(prev => ({ ...prev, motivo }))
    setCurrentStepIndex(3)
  }

  // Navigate back
  const handleBack = () => {
    // Clear any error state before navigation to prevent UI flicker
    setFormSaveError(null)
    clearError()

    if (currentStepIndex === 0) {
      // At step 0, go back to service requests list (not detail page)
      router.push(`/${locale}/dashboard/service-requests`)
      return
    }

    // Special case: if on documents and type is EXPEDICION, skip motivo
    if (currentStepIndex === 3 && wizardState.solicitudType === 'EXPEDICION') {
      setCurrentStepIndex(1)
      return
    }

    setCurrentStepIndex(prev => Math.max(0, prev - 1))
  }

  // ==========================================================================
  // DOCUMENT UPLOAD HANDLERS (2-step preview/validate flow)
  // ==========================================================================

  // Upload document using 2-step flow: preview (OCR extraction) → validate (save to DB)
  // This mirrors the dialog flow but stores preview in wizard state for form_review
  const handleDocumentUpload = async (documentCode: string, file: File) => {
    try {
      setIsUploadingDocument(documentCode)

      // Build existing extractions from preview cache for cross-document risk analysis
      // This enables DIP vs Passport comparison even before documents are saved to DB
      const existingExtractions: Record<string, Record<string, unknown>> = {}
      for (const [code, prev] of Object.entries(documentPreviewsRef.current)) {
        if (code !== documentCode && prev.extraction) {
          existingExtractions[code] = prev.extraction as Record<string, unknown>
        }
      }

      // Step 1: Preview - OCR extraction without saving to DB
      // Pass existing extractions for cross-document risk analysis
      const preview = await previewDocument(documentCode, file, existingExtractions)
      if (preview) {
        // Store preview data in state AND ref synchronously
        // The ref is updated immediately to avoid stale closure issues
        const newPreviews = {
          ...documentPreviewsRef.current,
          [documentCode]: preview
        }
        documentPreviewsRef.current = newPreviews  // Update ref synchronously
        setDocumentPreviews(newPreviews)           // Update state for UI re-render
        console.log(`[Wizard] Preview stored for ${documentCode}:`, preview.extraction)
        console.log('[Wizard] All previews now:', Object.keys(newPreviews))

        // Log risk analysis results if present
        if (preview.riskAnalysis) {
          console.log(`[Wizard] Risk analysis for ${documentCode}:`, preview.riskAnalysis)
          if (preview.riskAnalysis.riskFactors?.length > 0) {
            console.warn(`[Wizard] Risk factors detected:`, preview.riskAnalysis.riskFactors)
          }
        }
      }
    } catch (err) {
      console.error('Failed to preview document:', err)
    } finally {
      setIsUploadingDocument(null)
    }
  }

  // Continue to form review after all documents have been previewed
  // CHECKS FOR BLOCKING IDENTITY MISMATCHES BEFORE PROCEEDING
  const handleDocumentsContinue = () => {
    clearError()  // Clear any existing error before transition

    // Collect all identity mismatches from document previews
    const allMismatches: IdentityMismatch[] = []
    let hasBlockingMismatches = false

    const previews = documentPreviewsRef.current
    console.log('[Wizard] Checking identity mismatches in previews:', Object.keys(previews))

    for (const [docCode, preview] of Object.entries(previews)) {
      const riskAnalysis = preview.riskAnalysis
      if (riskAnalysis) {
        // Check for identity mismatches in risk analysis
        const mismatches = riskAnalysis.identityMismatches as IdentityMismatch[] | undefined
        if (mismatches && mismatches.length > 0) {
          console.log(`[Wizard] Found ${mismatches.length} identity mismatches in ${docCode}:`, mismatches)
          allMismatches.push(...mismatches)
        }

        // Check blocking flag
        if (riskAnalysis.hasBlockingMismatches) {
          hasBlockingMismatches = true
          console.warn(`[Wizard] BLOCKING mismatch detected in ${docCode}`)
        }
      }
    }

    // If we have blocking mismatches, show the blocker instead of proceeding
    if (hasBlockingMismatches && allMismatches.length > 0) {
      console.warn(`[Wizard] BLOCKING: ${allMismatches.length} identity mismatches detected`)
      setIdentityMismatches(allMismatches)
      setShowMismatchBlocker(true)
      return  // Don't proceed to form_review
    }

    // Clear any previous mismatch state
    setIdentityMismatches([])
    setShowMismatchBlocker(false)

    // Build form data BEFORE navigating (avoid timing issues with effects/refs)
    // This is the key difference with dialog - dialog receives data as prop directly,
    // wizard needs to prepare data synchronously before step change
    const previewFormData = buildFormDataFromPreviews()
    if (previewFormData) {
      console.log('[Wizard] Form data prepared before navigation:', previewFormData)
      setFormData(previewFormData)
    } else {
      console.warn('[Wizard] No preview data available when navigating to form_review')
    }

    // Proceed to form review
    setCurrentStepIndex(4)
  }

  // Handle going back from mismatch blocker to documents step
  const handleMismatchBlockerBack = () => {
    setShowMismatchBlocker(false)
    setIdentityMismatches([])
    // Stay on documents step (currentStepIndex is already 3)
  }

  // Handle re-uploading a specific document from mismatch blocker
  const handleReuploadFromBlocker = (documentCode: string) => {
    setShowMismatchBlocker(false)
    setIdentityMismatches([])
    // Clear the preview for this document so user can re-upload
    const newPreviews = { ...documentPreviewsRef.current }
    delete newPreviews[documentCode]
    documentPreviewsRef.current = newPreviews
    setDocumentPreviews(newPreviews)
  }

  // ==========================================================================
  // FORM REVIEW HANDLERS (Validate & Edit extracted data)
  // ==========================================================================

  // Handle field edit in form review
  const handleFormFieldEdit = (field: string, value: unknown) => {
    setEditedFormData(prev => ({ ...prev, [field]: value }))
  }

  // Save form data from review step
  // This calls validateDocument for each preview to save documents to DB (Step 2 of 2-step flow)
  const handleSaveFormReview = async (stepId: string) => {
    if (!formData) return false

    setIsSavingFormData(true)
    setFormSaveError(null) // Clear previous errors
    try {
      // Merge extracted data with user edits
      // IMPORTANT: Include wizardState values (solicitud_type, motivo, is_minor, representante_unico)
      // These are needed for tariff calculation and workflow processing in backend
      const dataToSave = {
        ...formData.extractedData,
        ...formData.formData,
        ...editedFormData,
        // Add wizard selections for tariff calculation and workflow
        solicitud_type: wizardState.solicitudType,
        motivo: wizardState.motivo,
        is_minor: wizardState.isMinor,
        // Minor-specific: representative info (null for adults)
        representante_unico: wizardState.representanteUnico,
        motivo_representante_unico: wizardState.motivoRepresentanteUnico,
      }

      // Step 2 of 2-step flow: Validate and save each document preview to DB
      // Only do this on the LAST form_review step (dynamically detected, not hardcoded)
      // CRITICAL: If any document fails to save, the entire operation fails
      if (stepId === lastFormReviewStepId && Object.keys(documentPreviews).length > 0) {
        console.log('[Wizard] Validating and saving documents to DB...')
        const failedDocuments: { code: string; error?: string }[] = []

        for (const [docCode, preview] of Object.entries(documentPreviews)) {
          if (preview.previewId) {
            // Build confirmed data for this document
            // For DIP, include user corrections
            let confirmedData = preview.extraction as Record<string, unknown>
            if (docCode === 'dip') {
              // Apply user edits to the extraction data
              confirmedData = {
                ...confirmedData,
                titular: {
                  ...(confirmedData.titular as Record<string, unknown> || {}),
                  apellidos: editedFormData.apellidos || (confirmedData.titular as Record<string, unknown>)?.apellidos,
                  nombres: editedFormData.nombres || (confirmedData.titular as Record<string, unknown>)?.nombres,
                  sexo: editedFormData.sexo || (confirmedData.titular as Record<string, unknown>)?.sexo,
                  fecha_nacimiento: editedFormData.fecha_nacimiento || (confirmedData.titular as Record<string, unknown>)?.fecha_nacimiento,
                  lugar_nacimiento: editedFormData.lugar_nacimiento || (confirmedData.titular as Record<string, unknown>)?.lugar_nacimiento,
                  nacionalidad: editedFormData.nacionalidad || (confirmedData.titular as Record<string, unknown>)?.nacionalidad,
                  estado_civil: editedFormData.estado_civil || (confirmedData.titular as Record<string, unknown>)?.estado_civil,
                  profesion: editedFormData.profesion || (confirmedData.titular as Record<string, unknown>)?.profesion,
                  grupo_sanguineo: editedFormData.grupo_sanguineo || (confirmedData.titular as Record<string, unknown>)?.grupo_sanguineo,
                },
                domicilio: {
                  ...(confirmedData.domicilio as Record<string, unknown> || {}),
                  domicilio: editedFormData.domicilio || (confirmedData.domicilio as Record<string, unknown>)?.domicilio,
                  ciudad: editedFormData.ciudad || (confirmedData.domicilio as Record<string, unknown>)?.ciudad,
                },
                filiacion: {
                  ...(confirmedData.filiacion as Record<string, unknown> || {}),
                  nombre_padre: editedFormData.nombre_padre || (confirmedData.filiacion as Record<string, unknown>)?.nombre_padre,
                  profesion_padre: editedFormData.profesion_padre || (confirmedData.filiacion as Record<string, unknown>)?.profesion_padre,
                  nombre_madre: editedFormData.nombre_madre || (confirmedData.filiacion as Record<string, unknown>)?.nombre_madre,
                  profesion_madre: editedFormData.profesion_madre || (confirmedData.filiacion as Record<string, unknown>)?.profesion_madre,
                }
              }
            }

            // Call validateDocument to save to Firebase + DB
            // This will throw an error if Firebase upload fails (fail-fast)
            try {
              const result = await validateDocument(preview.previewId, confirmedData)
              if (result) {
                console.log(`[Wizard] Document ${docCode} saved to DB:`, result)
              } else {
                // validateDocument returned null - something went wrong
                console.error(`[Wizard] Failed to save document ${docCode} - null response`)
                failedDocuments.push({ code: docCode })
              }
            } catch (docErr) {
              console.error(`[Wizard] Failed to save document ${docCode}:`, docErr)
              // Extract localized error message if available from API response
              const apiError = docErr as { response?: { data?: { detail?: { code?: string; message_es?: string; message_fr?: string; message_en?: string } | string } } }
              const detail = apiError?.response?.data?.detail
              let errorMsg = ''
              if (detail && typeof detail === 'object') {
                // Backend returned localized error (e.g., PREVIEW_EXPIRED)
                errorMsg = locale === 'es' ? detail.message_es || '' :
                           locale === 'fr' ? detail.message_fr || '' :
                           detail.message_en || ''
              }
              failedDocuments.push({ code: docCode, error: errorMsg })
            }
          }
        }

        // If any documents failed to save, abort the entire operation
        if (failedDocuments.length > 0) {
          // Check if we have a specific error message (e.g., preview expired)
          const firstError = failedDocuments[0]
          if (firstError.error) {
            throw new Error(firstError.error)
          }
          // Fallback to generic message
          const docNames = failedDocuments.map((d) => d.code).join(', ')
          throw new Error(
            locale === 'es' ? `Error al guardar documentos: ${docNames}. Por favor reintente.` :
            locale === 'fr' ? `Erreur lors de la sauvegarde des documents: ${docNames}. Veuillez réessayer.` :
            `Failed to save documents: ${docNames}. Please try again.`
          )
        }

        // Clear previews only after ALL documents saved successfully
        setDocumentPreviews({})
      }

      // Save form data to service request
      await saveStepData(stepId, dataToSave)

      // Invalidate form config cache after successful save
      // This ensures the next step gets fresh data with updated values
      if (FEATURE_DYNAMIC_FORM_RENDERER && requestId) {
        invalidateFormConfigCache(requestId)
      }

      return true
    } catch (err) {
      console.error('Failed to save form data:', err)
      // Set error message for display to user
      const errorMessage = err instanceof Error ? err.message : (
        locale === 'es' ? 'Error al guardar los datos. Por favor reintente.' :
        locale === 'fr' ? 'Erreur lors de la sauvegarde. Veuillez réessayer.' :
        'Failed to save data. Please try again.'
      )
      setFormSaveError(errorMessage)
      return false
    } finally {
      setIsSavingFormData(false)
    }
  }

  // ==========================================================================
  // FORM DATA LOADING (from preview state, NOT from DB)
  // ==========================================================================

  // Build form data from document previews (2-step flow)
  // Uses SAME approach as DocumentPreviewDialog: dynamic flattening
  const buildFormDataFromPreviews = useCallback((): FormDataResponse | null => {
    // Use ref to get latest previews (avoids stale closure)
    const previews = documentPreviewsRef.current
    console.log('[Wizard] buildFormDataFromPreviews called, previews:', Object.keys(previews))

    if (Object.keys(previews).length === 0) {
      console.log('[Wizard] No previews available to build form data')
      return null
    }

    // Helper: Flatten nested object recursively (SAME as dialog)
    const flattenObject = (
      obj: Record<string, unknown>,
      prefix = ''
    ): Record<string, unknown> => {
      const result: Record<string, unknown> = {}
      for (const [key, value] of Object.entries(obj)) {
        const fullKey = prefix ? `${prefix}.${key}` : key
        if (value && typeof value === 'object' && !Array.isArray(value)) {
          Object.assign(result, flattenObject(value as Record<string, unknown>, fullKey))
        } else {
          result[fullKey] = value
        }
      }
      return result
    }

    // Collect all extraction data from previews
    const extractedData: Record<string, Record<string, unknown>> = {}
    const allFlattenedData: Record<string, unknown> = {}

    for (const [docCode, preview] of Object.entries(previews)) {
      console.log(`[Wizard] Processing preview for ${docCode}:`, preview.extraction)
      if (preview.extraction) {
        extractedData[docCode] = preview.extraction as Record<string, unknown>

        // Flatten ALL extraction data dynamically (like dialog does)
        const flattened = flattenObject(preview.extraction as Record<string, unknown>)
        console.log(`[Wizard] Flattened ${docCode} data:`, flattened)
        Object.assign(allFlattenedData, flattened)
      }
    }

    console.log('[Wizard] All flattened extraction data:', allFlattenedData)

    // Map flattened keys to form field names
    // This handles both nested keys (documento.numero_dip) and flat keys (numero_dip)
    const formDataFlat: Record<string, unknown> = {}

    // Field mapping: flattened key patterns -> form field name
    const fieldMappings: Array<{ formField: string; possibleKeys: string[] }> = [
      { formField: 'numero_dip', possibleKeys: ['documento.numero_dip', 'numero_dip'] },
      { formField: 'apellidos', possibleKeys: ['titular.apellidos', 'apellidos'] },
      { formField: 'nombres', possibleKeys: ['titular.nombres', 'nombres'] },
      { formField: 'sexo', possibleKeys: ['titular.sexo', 'sexo'] },
      { formField: 'fecha_nacimiento', possibleKeys: ['titular.fecha_nacimiento', 'fecha_nacimiento'] },
      { formField: 'lugar_nacimiento', possibleKeys: ['titular.lugar_nacimiento', 'lugar_nacimiento'] },
      { formField: 'natural_de', possibleKeys: ['titular.natural_de', 'natural_de'] },
      { formField: 'distrito_provincia', possibleKeys: ['titular.distrito_provincia', 'distrito_provincia'] },
      { formField: 'nacionalidad', possibleKeys: ['titular.nacionalidad', 'nacionalidad'] },
      { formField: 'estado_civil', possibleKeys: ['titular.estado_civil', 'estado_civil'] },
      { formField: 'profesion', possibleKeys: ['titular.profesion', 'profesion'] },
      { formField: 'grupo_sanguineo', possibleKeys: ['titular.grupo_sanguineo', 'grupo_sanguineo'] },
      // Address fields - prefer new separated fields from backend post-processing
      { formField: 'domicilio', possibleKeys: ['domiciliacion_barrio', 'titular.domiciliacion', 'domicilio.domicilio', 'domicilio.direccion', 'domicilio', 'domiciliacion'] },
      { formField: 'ciudad', possibleKeys: ['domiciliacion_ciudad', 'domicilio.ciudad', 'ciudad'] },
      { formField: 'departamento', possibleKeys: ['domiciliacion_departamento', 'domicilio.departamento', 'departamento'] },
      { formField: 'nombre_padre', possibleKeys: ['filiacion.nombre_padre', 'nombre_padre'] },
      { formField: 'profesion_padre', possibleKeys: ['filiacion.profesion_padre', 'profesion_padre'] },
      { formField: 'nombre_madre', possibleKeys: ['filiacion.nombre_madre', 'nombre_madre'] },
      { formField: 'profesion_madre', possibleKeys: ['filiacion.profesion_madre', 'profesion_madre'] },
      { formField: 'numero_pasaporte_antiguo', possibleKeys: ['numero', 'numero_pasaporte', 'numero_pasaporte_antiguo'] },
      { formField: 'fecha_expedicion_antiguo', possibleKeys: ['fecha_expedicion', 'fecha_expedicion_antiguo'] },
      { formField: 'fecha_expiracion_antiguo', possibleKeys: ['fecha_expiracion', 'fecha_expiracion_antiguo'] },
    ]

    // Apply mappings - first match wins
    for (const { formField, possibleKeys } of fieldMappings) {
      for (const key of possibleKeys) {
        if (allFlattenedData[key] !== undefined && allFlattenedData[key] !== null && allFlattenedData[key] !== '') {
          formDataFlat[formField] = allFlattenedData[key]
          console.log(`[Wizard] Mapped ${key} -> ${formField}:`, allFlattenedData[key])
          break
        }
      }
    }

    console.log('[Wizard] Final formDataFlat:', formDataFlat)

    // Calculate completion percentage
    const requiredFields = ['numero_dip', 'apellidos', 'nombres', 'sexo', 'fecha_nacimiento', 'lugar_nacimiento', 'domicilio']
    const filledFields = requiredFields.filter(f => formDataFlat[f])
    const completionPercentage = Math.round((filledFields.length / requiredFields.length) * 100)
    const missingFields = requiredFields.filter(f => !formDataFlat[f])

    console.log('[Wizard] Completion:', completionPercentage, '%, missing:', missingFields)

    return {
      formData: formDataFlat,
      extractedData,
      requiresReview: true,
      completionPercentage,
      missingFields
    }
  }, []) // No dependencies - uses ref

  const loadFormDataForReview = useCallback(async () => {
    console.log('[Wizard] loadFormDataForReview called')
    setIsLoadingFormData(true)
    try {
      // First, try to build form data from preview state (2-step flow)
      // Check ref directly to avoid stale closure
      const previews = documentPreviewsRef.current
      console.log('[Wizard] Current previews in ref:', Object.keys(previews))

      if (Object.keys(previews).length > 0) {
        const previewFormData = buildFormDataFromPreviews()
        if (previewFormData) {
          setFormData(previewFormData)
          console.log('[Wizard] Form data built from previews successfully')
          return
        }
      }

      // Fallback: load from DB (for existing requests with documents already saved)
      console.log('[Wizard] No previews available, loading from DB...')
      const data = await getFormData()
      if (data) {
        setFormData(data)
        console.log('[Wizard] Form data loaded from DB:', data)
      } else {
        console.log('[Wizard] No form data returned from DB')
      }
    } catch (err) {
      console.error('[Wizard] Failed to load form data:', err)
      // Set empty form data on error to show the form fields anyway
      setFormData({
        formData: {},
        extractedData: {},
        requiresReview: true,
        completionPercentage: 0,
        missingFields: ['numero_dip', 'apellidos', 'nombres', 'sexo', 'fecha_nacimiento', 'lugar_nacimiento', 'domicilio']
      })
    } finally {
      setIsLoadingFormData(false)
    }
  }, [buildFormDataFromPreviews, getFormData]) // Removed documentPreviews - uses ref

  // Load form data when entering form review steps
  useEffect(() => {
    const isFormReviewStep = currentStep.id.startsWith('form_review')
    console.log('[Wizard] Form review effect:', { stepId: currentStep.id, isFormReviewStep, hasFormData: !!formData })

    if (isFormReviewStep && !formData) {
      loadFormDataForReview()
    }
  }, [currentStep.id, formData, loadFormDataForReview])

  // ==========================================================================
  // PAYMENT WITH STATUS POLLING
  // ==========================================================================

  // Load payment methods when step becomes payment
  // Payment methods must come from the API - no hardcoded fallback
  const loadPaymentMethods = useCallback(async () => {
    setIsLoadingPaymentMethods(true)
    setPaymentMethodsError(null)
    try {
      const response = await getPaymentMethods()
      if (response && response.methods && response.methods.length > 0) {
        setAvailablePaymentMethods(response.methods)
        setPaymentMethodsError(null)
        // Set default if specified
        if (response.defaultMethod) {
          setSelectedPaymentMethod(response.defaultMethod as PaymentMethod)
        }
      } else {
        // Response is null or empty - show error
        console.error('No payment methods returned from API')
        setAvailablePaymentMethods([])
        setPaymentMethodsError(
          locale === 'es' ? 'No se encontraron métodos de pago disponibles.' :
          locale === 'fr' ? 'Aucune méthode de paiement disponible.' :
          'No payment methods available.'
        )
      }
    } catch (err) {
      console.error('Failed to load payment methods:', err)
      setAvailablePaymentMethods([])
      setPaymentMethodsError(
        locale === 'es' ? 'Error al cargar los métodos de pago. Por favor, reintente.' :
        locale === 'fr' ? 'Erreur lors du chargement des méthodes de paiement. Veuillez réessayer.' :
        'Failed to load payment methods. Please try again.'
      )
    } finally {
      setIsLoadingPaymentMethods(false)
    }
  }, [getPaymentMethods, locale])

  // Load payment methods when reaching payment step
  useEffect(() => {
    const step = visibleSteps[currentStepIndex]
    if (step?.id === 'payment' && availablePaymentMethods.length === 0 && !isLoadingPaymentMethods) {
      loadPaymentMethods()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- visibleSteps is stable and derived from request data
  }, [currentStepIndex, availablePaymentMethods.length, isLoadingPaymentMethods, loadPaymentMethods])

  const handlePayment = async () => {
    if (!selectedPaymentMethod) return

    setIsProcessingPayment(true)
    setPendingPaymentResult(null)
    setPaymentMethodsError(null) // Clear any previous errors
    try {
      const result = await initiatePayment(selectedPaymentMethod, phoneNumber)
      if (!result) {
        // Payment initiation failed (returned null)
        setIsProcessingPayment(false)
        setPaymentMethodsError(
          locale === 'es'
            ? 'Error al iniciar el pago. Intente nuevamente.'
            : locale === 'fr'
              ? 'Erreur lors de l\'initiation du paiement. Réessayez.'
              : 'Error initiating payment. Please try again.'
        )
        return
      }
      if (result) {
        // Check if this is a manual payment (cash/check) requiring agent validation
        const isManualPayment = result.actionType?.startsWith('agent_validation') || false

        // Store payment result for display (especially for cash payments)
        if (isManualPayment) {
          setPendingPaymentResult({
            paymentReference: result.paymentReference,
            messageEs: result.messageEs,
            actionType: result.actionType,
            isManualPayment: true,
          })
          // Stop the "processing" spinner but keep showing waiting state
          setIsProcessingPayment(false)
          console.log('[Payment] Manual payment registered, reference:', result.paymentReference)
          // Continue polling to check when agent validates the payment
          // User cannot proceed to appointment until payment is validated (status=PAID)
        }

        // For BANGE electronic payments, redirect to payment page
        if (result.redirectUrl) {
          // Open BANGE payment page in new window/tab
          // User will complete payment there and return
          window.open(result.redirectUrl, '_blank')
        }

        // Start polling for payment status (for ALL payments - electronic and manual)
        // Manual payments need polling to detect when agent validates
        paymentPollRef.current = setInterval(async () => {
          try {
            const status = await checkPaymentStatus()
            if (status?.paid) {
              if (paymentPollRef.current) {
                clearInterval(paymentPollRef.current)
              }
              setPaymentComplete(true)
              setIsProcessingPayment(false)
              // Don't auto-advance for manual payments - let user click continue
              if (!isManualPayment) {
                setCurrentStepIndex(7) // Go to appointment (index 7 after validation step removal)
              }
            }
          } catch (err) {
            console.error('Payment status check failed:', err)
          }
        }, 5000) // Poll every 5 seconds (less aggressive for manual payments)

        // Stop polling after 30 minutes for manual payments (agent may take time)
        const pollTimeout = isManualPayment ? 1800000 : 600000 // 30 min vs 10 min
        setTimeout(() => {
          if (paymentPollRef.current) {
            clearInterval(paymentPollRef.current)
            if (!isManualPayment) {
              setIsProcessingPayment(false)
            }
          }
        }, pollTimeout)
      }
    } catch (err) {
      console.error('Payment failed:', err)
      setIsProcessingPayment(false)
    }
  }

  // ==========================================================================
  // APPOINTMENT WITH NOTIFICATIONS
  // ==========================================================================

  const handleAppointmentComplete = async (appointmentData: {
    hasAppointment: boolean
    locationName?: string
    appointmentDate?: string
    appointmentTime?: string
    isFallback: boolean
  }) => {
    // Load citizen summary for confirmation
    const summary = await getCitizenSummary()
    setCitizenSummary(summary)

    // Send notifications if appointment was booked
    if (appointmentData.hasAppointment && appointmentData.locationName && currentRequest) {
      try {
        const userEmail = currentRequest.formData?.email as string || ''
        const userPhone = currentRequest.formData?.phone as string
        const userName = currentRequest.formData?.nombres as string || 'Usuario'

        await notificationService.sendAppointmentConfirmation({
          userEmail,
          userPhone,
          userName,
          requestReference: currentRequest.requestNumber || requestId,
          locationName: appointmentData.locationName,
          appointmentDate: appointmentData.appointmentDate || '',
          appointmentTime: appointmentData.appointmentTime || '',
          language: locale as 'es' | 'fr' | 'en',
        })

        setNotificationsSent(true)
      } catch (err) {
        console.error('Failed to send notifications:', err)
      }
    }

    setCurrentStepIndex(9) // Go to confirmation
  }

  // Loading state - show loading when we don't have a request yet and no error
  // This prevents page flash on initial load (before loadRequest sets isLoading=true)
  if (!currentRequest && !error) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin mx-auto mb-4 text-primary" />
          <p className="text-muted-foreground">{t('loading')}</p>
        </div>
      </div>
    )
  }

  // Error state with improved retry functionality
  if (error) {
    const isNetworkError = error.toLowerCase().includes('failed to fetch') || error.toLowerCase().includes('network')
    return (
      <div className="max-w-md mx-auto space-y-4">
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            {isNetworkError ? (
              locale === 'es'
                ? 'Error de conexión. Verifique su conexión a internet e intente de nuevo.'
                : locale === 'fr'
                  ? 'Erreur de connexion. Vérifiez votre connexion internet et réessayez.'
                  : 'Connection error. Check your internet connection and try again.'
            ) : error}
          </AlertDescription>
        </Alert>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => { clearError(); loadRequest(requestId); }} className="flex-1">
            <RefreshCw className="mr-2 h-4 w-4" />
            {locale === 'es' ? 'Reintentar' : locale === 'fr' ? 'Réessayer' : 'Retry'}
          </Button>
          <Button variant="ghost" onClick={() => router.push(`/${locale}/dashboard/service-requests/${requestId}`)}>
            {locale === 'es' ? 'Volver' : locale === 'fr' ? 'Retour' : 'Back'}
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Back Button */}
      <Button
        variant="ghost"
        size="sm"
        onClick={handleBack}
        className="text-muted-foreground hover:text-foreground -ml-2"
      >
        <ArrowLeft className="mr-2 h-4 w-4" />
        {t('back')}
      </Button>

      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight">
          {locale === 'es' ? 'Solicitud de Pasaporte' : locale === 'fr' ? 'Demande de Passeport' : 'Passport Request'}
        </h1>
        <p className="text-muted-foreground">
          {currentRequest?.requestNumber && `Ref: ${currentRequest.requestNumber}`}
        </p>
      </div>

      {/* Progress Bar */}
      <div className="space-y-2">
        <div className="flex justify-between text-sm text-muted-foreground">
          <span>
            {locale === 'es'
              ? `Paso ${Math.ceil(currentStep.number + 1)} de 9`
              : locale === 'fr'
                ? `Etape ${Math.ceil(currentStep.number + 1)} sur 9`
                : `Step ${Math.ceil(currentStep.number + 1)} of 9`}
          </span>
          <span>{Math.round(progressPercent)}%</span>
        </div>
        <Progress value={progressPercent} className="h-2" />
      </div>

      {/* Step Content */}
      {currentStep.id === 'is_minor' && (
        <MinorSelectionStep
          locale={locale}
          selectedValue={wizardState.isMinor}
          onSelect={handleMinorSelect}
          isSaving={isSaving}
        />
      )}

      {currentStep.id === 'select_type' && (
        <TypeSelectionStep
          locale={locale}
          isMinor={wizardState.isMinor}
          selectedValue={wizardState.solicitudType}
          onSelect={handleTypeSelect}
          isSaving={isSaving}
        />
      )}

      {currentStep.id === 'select_motivo' && (
        <MotivoSelectionStep
          locale={locale}
          selectedValue={wizardState.motivo}
          onSelect={handleMotivoSelect}
          isSaving={isSaving}
        />
      )}

      {/* Step for minors: Legal representatives info (representante_unico checkbox) */}
      {currentStep.id === 'representantes_legales' && (
        <RepresentantesLegalesStep
          locale={locale}
          representanteUnico={wizardState.representanteUnico}
          motivoRepresentanteUnico={wizardState.motivoRepresentanteUnico}
          onSave={(representanteUnico, motivoRepresentanteUnico) => {
            console.log('[Wizard] RepresentantesLegales onSave:', { representanteUnico, motivoRepresentanteUnico })
            // Store in wizardState for immediate use
            setWizardState(prev => ({
              ...prev,
              representanteUnico,
              motivoRepresentanteUnico,
            }))
            // Also store in formData for later DB persistence
            setFormData(prev => {
              const newFormData = prev ? {
                ...prev,
                formData: {
                  ...prev.formData,
                  representante_unico: representanteUnico,
                  motivo_representante_unico: motivoRepresentanteUnico,
                }
              } : {
                formData: {
                  representante_unico: representanteUnico,
                  motivo_representante_unico: motivoRepresentanteUnico,
                },
                extractedData: {},
                requiresReview: true,
                completionPercentage: 0,
                missingFields: []
              }
              console.log('[Wizard] New formData after representantes:', newFormData)
              return newFormData
            })
            setCurrentStepIndex(prev => prev + 1)
          }}
          onBack={handleBack}
          isSaving={isSaving}
        />
      )}

      {currentStep.id === 'upload_documents' && !showMismatchBlocker && (
        <DocumentsStepImproved
          locale={locale}
          isMinor={wizardState.isMinor || false}
          solicitudType={wizardState.solicitudType}
          motivo={wizardState.motivo}
          representanteUnico={wizardState.representanteUnico}
          documents={documents}
          documentPreviews={documentPreviews}
          isUploadingDocument={isUploadingDocument}
          onUpload={handleDocumentUpload}
          onDelete={async (docId) => { await deleteDocument(docId) }}
          onNext={handleDocumentsContinue}
          onBack={handleBack}
          isLocked={currentRequest?.status !== 'DRAFT'}
        />
      )}

      {/* Identity Mismatch Blocker - shown when documents have conflicting identity data */}
      {currentStep.id === 'upload_documents' && showMismatchBlocker && (
        <IdentityMismatchBlocker
          mismatches={identityMismatches}
          hasBlockingMismatches={identityMismatches.some(m => m.is_blocking)}
          onGoBack={handleMismatchBlockerBack}
          onReuploadDocument={handleReuploadFromBlocker}
        />
      )}

      {currentStep.id.startsWith('form_review') && (
        <FormReviewStepEditable
          locale={locale}
          step={currentStep.id}
          requestId={requestId}
          formData={formData}
          editedData={editedFormData}
          isLoading={isLoadingFormData}
          isSaving={isSavingFormData}
          saveError={formSaveError}
          isMinor={wizardState.isMinor || false}
          solicitudType={wizardState.solicitudType}
          onFieldEdit={handleFormFieldEdit}
          onSave={() => handleSaveFormReview(currentStep.id)}
          onNext={async () => {
            const success = await handleSaveFormReview(currentStep.id)
            if (success) {
              // Check if this is the LAST form_review step (dynamically detected)
              // Minors go through form_review_representantes BEFORE this step
              if (currentStep.id === lastFormReviewStepId) {
                console.log(`[Wizard] Last form review step (${lastFormReviewStepId}) complete, preparing for payment...`)
                const result = await prepareForPayment()
                if (!result.success) {
                  console.error('[Wizard] Failed to prepare for payment:', result.errorMessage)
                  // Use the actual error message from the backend (contains list of missing docs)
                  // Fallback to generic message only if no specific error
                  setFormSaveError(
                    result.errorMessage || (
                      locale === 'es'
                        ? 'Error al preparar el pago. Verifique que todos los documentos estén validados.'
                        : locale === 'fr'
                          ? 'Erreur lors de la préparation du paiement. Vérifiez que tous les documents sont validés.'
                          : 'Error preparing payment. Verify all documents are validated.'
                    )
                  )
                  return
                }
                console.log('[Wizard] Request validated for payment, navigating to payment step')
              }
              setCurrentStepIndex(prev => prev + 1)
            }
          }}
          onBack={handleBack}
          onRetry={loadFormDataForReview}
        />
      )}

      {/* Step for minors: Review legal representatives data + cross-validation results */}
      {/* This is BEFORE the last form_review step - no persistence here, just validation display */}
      {currentStep.id === 'form_review_representantes' && (
        <FormReviewRepresentantesStep
          locale={locale}
          formData={formData?.formData ?? null}
          documentPreviews={documentPreviews}
          isSaving={false}
          saveError={null}
          onNext={() => {
            console.log('[Wizard] Form review representantes complete, advancing to next step...')
            setCurrentStepIndex(prev => prev + 1)
          }}
          onBack={handleBack}
        />
      )}

      {/* NOTE: Validation step removed - cross-document validation is now done during extraction
          by Gemini processor with identity mismatch blocking (Step 3: upload_documents) */}

      {currentStep.id === 'payment' && (
        <PaymentStepImproved
          locale={locale}
          tariff={getTariff()}
          availableMethods={availablePaymentMethods}
          isLoadingMethods={isLoadingPaymentMethods}
          methodsError={paymentMethodsError}
          onRetryLoadMethods={loadPaymentMethods}
          selectedMethod={selectedPaymentMethod}
          phoneNumber={phoneNumber}
          isProcessing={isProcessingPayment}
          paymentComplete={paymentComplete}
          pendingPaymentResult={pendingPaymentResult}
          onMethodSelect={setSelectedPaymentMethod}
          onPhoneChange={setPhoneNumber}
          onPay={handlePayment}
          onNext={() => setCurrentStepIndex(7)} // Appointment is now index 7 after validation step removal
          onBack={handleBack}
        />
      )}

      {currentStep.id === 'appointment' && (
        <AppointmentStepImproved
          locale={locale}
          requestId={requestId}
          tariff={getTariff()}
          paymentComplete={paymentComplete}
          pendingPaymentReference={pendingPaymentResult?.paymentReference}
          getLocations={getAppointmentLocations}
          getAvailableDays={getAvailableDays}
          getSlots={getAppointmentSlots}
          holdSlot={holdAppointmentSlot}
          getHoldStatus={getAppointmentHoldStatus}
          releaseHold={releaseAppointmentHold}
          onComplete={handleAppointmentComplete}
          onBack={handleBack}
        />
      )}

      {currentStep.id === 'confirmation' && (
        <ConfirmationStepImproved
          locale={locale}
          requestId={requestId}
          tariff={getTariff()}
          summary={citizenSummary}
          notificationsSent={notificationsSent}
          onDownloadPDF={async () => {
            await downloadSummaryPDF(locale)
          }}
        />
      )}

    </div>
  )
}

// =============================================================================
// STEP 0: Minor Selection (unchanged)
// =============================================================================

interface MinorSelectionStepProps {
  locale: string
  selectedValue: boolean | null
  onSelect: (value: boolean) => void
  isSaving: boolean
}

function MinorSelectionStep({ locale, selectedValue, onSelect, isSaving }: MinorSelectionStepProps) {
  const options = [
    {
      value: false,
      icon: UserCheck,
      labelEs: 'Mayor de Edad',
      labelFr: 'Majeur',
      labelEn: 'Adult',
      descEs: 'Persona de 18 anos o mas',
      descFr: 'Personne de 18 ans ou plus',
      descEn: 'Person 18 years or older',
    },
    {
      value: true,
      icon: Baby,
      labelEs: 'Menor de Edad',
      labelFr: 'Mineur',
      labelEn: 'Minor',
      descEs: 'Menor de 18 anos (requiere autorizacion parental)',
      descFr: 'Moins de 18 ans (autorisation parentale requise)',
      descEn: 'Under 18 years (parental authorization required)',
    },
  ]

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          {locale === 'es' ? 'Tipo de Solicitante' : locale === 'fr' ? 'Type de Demandeur' : 'Applicant Type'}
        </CardTitle>
        <CardDescription>
          {locale === 'es'
            ? 'Indique si la solicitud es para un adulto o un menor de edad'
            : locale === 'fr'
              ? 'Indiquez si la demande concerne un adulte ou un mineur'
              : 'Indicate if the request is for an adult or a minor'}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {options.map((option) => {
          const Icon = option.icon
          const isSelected = selectedValue === option.value

          return (
            <button
              key={String(option.value)}
              onClick={() => !isSaving && onSelect(option.value)}
              disabled={isSaving}
              className={`w-full p-4 rounded-lg border-2 text-left transition-all ${
                isSelected
                  ? 'border-primary bg-primary/5'
                  : 'border-muted hover:border-primary/50 hover:bg-muted/50'
              } ${isSaving ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
            >
              <div className="flex items-start gap-4">
                <div className={`p-2 rounded-lg ${isSelected ? 'bg-primary text-primary-foreground' : 'bg-muted'}`}>
                  <Icon className="h-6 w-6" />
                </div>
                <div className="flex-1">
                  <p className="font-semibold">
                    {locale === 'es' ? option.labelEs : locale === 'fr' ? option.labelFr : option.labelEn}
                  </p>
                  <p className="text-sm text-muted-foreground">
                    {locale === 'es' ? option.descEs : locale === 'fr' ? option.descFr : option.descEn}
                  </p>
                </div>
                {isSelected && <CheckCircle className="h-5 w-5 text-primary" />}
              </div>
            </button>
          )
        })}

        {isSaving && (
          <div className="flex items-center justify-center gap-2 text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            <span>{locale === 'es' ? 'Guardando...' : locale === 'fr' ? 'Enregistrement...' : 'Saving...'}</span>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

// =============================================================================
// STEP 1: Type Selection (unchanged)
// =============================================================================

interface TypeSelectionStepProps {
  locale: string
  isMinor: boolean | null
  selectedValue: SolicitudType | null
  onSelect: (value: SolicitudType) => void
  isSaving: boolean
}

function TypeSelectionStep({ locale, isMinor, selectedValue, onSelect, isSaving }: TypeSelectionStepProps) {
  const options: Array<{
    value: SolicitudType
    labelEs: string
    labelFr: string
    labelEn: string
    descEs: string
    descFr: string
    descEn: string
    tariff: number
  }> = [
    {
      value: 'EXPEDICION',
      labelEs: 'Primera Expedicion',
      labelFr: 'Premiere Emission',
      labelEn: 'First Issuance',
      descEs: 'Solicito mi primer pasaporte',
      descFr: 'Je demande mon premier passeport',
      descEn: 'I am requesting my first passport',
      tariff: 7500,
    },
    {
      value: 'RENOVACION',
      labelEs: 'Renovacion',
      labelFr: 'Renouvellement',
      labelEn: 'Renewal',
      descEs: 'Ya tengo un pasaporte (vencido, perdido, robado o danado)',
      descFr: "J'ai deja un passeport (expire, perdu, vole ou endommage)",
      descEn: 'I already have a passport (expired, lost, stolen or damaged)',
      tariff: 0,
    },
  ]

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          {locale === 'es' ? 'Tipo de Solicitud' : locale === 'fr' ? 'Type de Demande' : 'Request Type'}
        </CardTitle>
        <CardDescription>
          {locale === 'es'
            ? `Solicitud para: ${isMinor ? 'Menor de edad' : 'Mayor de edad'}`
            : locale === 'fr'
              ? `Demande pour: ${isMinor ? 'Mineur' : 'Majeur'}`
              : `Request for: ${isMinor ? 'Minor' : 'Adult'}`}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {options.map((option) => {
          const isSelected = selectedValue === option.value

          return (
            <button
              key={option.value}
              onClick={() => !isSaving && onSelect(option.value)}
              disabled={isSaving}
              className={`w-full p-4 rounded-lg border-2 text-left transition-all ${
                isSelected
                  ? 'border-primary bg-primary/5'
                  : 'border-muted hover:border-primary/50 hover:bg-muted/50'
              } ${isSaving ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1">
                  <p className="font-semibold">
                    {locale === 'es' ? option.labelEs : locale === 'fr' ? option.labelFr : option.labelEn}
                  </p>
                  <p className="text-sm text-muted-foreground">
                    {locale === 'es' ? option.descEs : locale === 'fr' ? option.descFr : option.descEn}
                  </p>
                </div>
                <div className="text-right">
                  {option.tariff > 0 ? (
                    <p className="font-semibold text-primary">{option.tariff.toLocaleString()} XAF</p>
                  ) : (
                    <p className="text-sm text-muted-foreground">
                      {locale === 'es' ? 'Segun motivo' : locale === 'fr' ? 'Selon motif' : 'Varies'}
                    </p>
                  )}
                  {isSelected && <CheckCircle className="h-5 w-5 text-primary mt-1 ml-auto" />}
                </div>
              </div>
            </button>
          )
        })}
      </CardContent>
    </Card>
  )
}

// =============================================================================
// STEP 1b: Motivo Selection (unchanged)
// =============================================================================

interface MotivoSelectionStepProps {
  locale: string
  selectedValue: RenovacionMotivo | null
  onSelect: (value: RenovacionMotivo) => void
  isSaving: boolean
}

function MotivoSelectionStep({ locale, selectedValue, onSelect, isSaving }: MotivoSelectionStepProps) {
  const options: Array<{
    value: RenovacionMotivo
    labelEs: string
    labelFr: string
    labelEn: string
    descEs: string
    descFr: string
    descEn: string
    tariff: number
  }> = [
    {
      value: 'VENCIMIENTO',
      labelEs: 'Vencimiento',
      labelFr: 'Expiration',
      labelEn: 'Expiration',
      descEs: 'Mi pasaporte esta vencido o por vencer',
      descFr: 'Mon passeport est expire ou va expirer',
      descEn: 'My passport is expired or expiring',
      tariff: 5000,
    },
    {
      value: 'PERDIDA',
      labelEs: 'Perdida',
      labelFr: 'Perte',
      labelEn: 'Loss',
      descEs: 'Perdi mi pasaporte (requiere denuncia policial)',
      descFr: "J'ai perdu mon passeport (declaration de perte requise)",
      descEn: 'I lost my passport (police report required)',
      tariff: 10000,
    },
    {
      value: 'ROBO',
      labelEs: 'Robo',
      labelFr: 'Vol',
      labelEn: 'Theft',
      descEs: 'Me robaron mi pasaporte (requiere denuncia policial)',
      descFr: 'Mon passeport a ete vole (declaration de vol requise)',
      descEn: 'My passport was stolen (police report required)',
      tariff: 10000,
    },
    {
      value: 'DETERIORO',
      labelEs: 'Deterioro',
      labelFr: 'Deterioration',
      labelEn: 'Damage',
      descEs: 'Mi pasaporte esta danado',
      descFr: 'Mon passeport est endommage',
      descEn: 'My passport is damaged',
      tariff: 7500,
    },
  ]

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          {locale === 'es' ? 'Motivo de Renovacion' : locale === 'fr' ? 'Motif de Renouvellement' : 'Renewal Reason'}
        </CardTitle>
        <CardDescription>
          {locale === 'es'
            ? 'Seleccione el motivo de la renovacion'
            : locale === 'fr'
              ? 'Selectionnez le motif du renouvellement'
              : 'Select the reason for renewal'}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {options.map((option) => {
          const isSelected = selectedValue === option.value

          return (
            <button
              key={option.value}
              onClick={() => !isSaving && onSelect(option.value)}
              disabled={isSaving}
              className={`w-full p-4 rounded-lg border-2 text-left transition-all ${
                isSelected
                  ? 'border-primary bg-primary/5'
                  : 'border-muted hover:border-primary/50 hover:bg-muted/50'
              } ${isSaving ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1">
                  <p className="font-semibold">
                    {locale === 'es' ? option.labelEs : locale === 'fr' ? option.labelFr : option.labelEn}
                  </p>
                  <p className="text-sm text-muted-foreground">
                    {locale === 'es' ? option.descEs : locale === 'fr' ? option.descFr : option.descEn}
                  </p>
                </div>
                <div className="text-right">
                  <p className="font-semibold text-primary">{option.tariff.toLocaleString()} XAF</p>
                  {isSelected && <CheckCircle className="h-5 w-5 text-primary mt-1 ml-auto" />}
                </div>
              </div>
            </button>
          )
        })}
      </CardContent>
    </Card>
  )
}

// =============================================================================
// STEP 2: Documents Step - IMPROVED with Two-Step Flow
// =============================================================================

interface DocumentsStepImprovedProps {
  locale: string
  isMinor: boolean
  solicitudType: SolicitudType | null
  motivo: RenovacionMotivo | null
  representanteUnico: boolean | null // For minors: true = single parent/guardian, false = both parents
  documents: ServiceRequestDocument[]
  documentPreviews: Record<string, DocumentExtractionPreview>
  isUploadingDocument: string | null
  onUpload: (documentCode: string, file: File) => Promise<void>
  onDelete: (documentId: string) => Promise<void>
  onNext: () => void
  onBack: () => void
  isLocked?: boolean // True when documents cannot be modified (status != DRAFT)
}

function DocumentsStepImproved({
  locale,
  isMinor,
  solicitudType,
  motivo,
  representanteUnico,
  documents,
  documentPreviews,
  isUploadingDocument,
  onUpload,
  onDelete,
  onNext,
  onBack,
  isLocked = false,
}: DocumentsStepImprovedProps) {
  // Debug log to trace representanteUnico value
  console.log('[Wizard] DocumentsStepImproved props:', { isMinor, solicitudType, motivo, representanteUnico })

  const getDocumentRequirements = (): DocumentRequirement[] => {
    const requirements: DocumentRequirement[] = []
    console.log('[Wizard] getDocumentRequirements called with representanteUnico:', representanteUnico)

    // Identity document: DIP for adults, Certificado de Nacimiento for minors
    if (isMinor) {
      // Minors don't have DIP - they use birth certificate as identity document
      requirements.push({
        documentCode: 'certificado_nacimiento',
        documentNameEs: 'Certificado de Nacimiento',
        isRequired: true,
        displayOrder: 1,
        conditionType: DocumentConditionType.CUSTOM,
        conditionValue: { is_minor: true },
        instructionsEs: 'Certificación literal de inscripción de nacimiento del menor',
        acceptedFormats: ['pdf', 'jpg', 'jpeg', 'png'],
      })
    } else {
      // Adults use DIP
      requirements.push({
        documentCode: 'dip',
        documentNameEs: 'Documento de Identidad Personal (DIP)',
        schemaKey: 'DIP_GQ_V2',
        isRequired: true,
        displayOrder: 1,
        conditionType: DocumentConditionType.ALWAYS,
        instructionsEs: 'Escanee ambas caras de su DIP vigente',
        acceptedFormats: ['pdf', 'jpg', 'jpeg', 'png'],
      })
    }

    // Type-specific documents (adults only for EXPEDICION birth certificate)
    if (solicitudType === 'EXPEDICION' && !isMinor) {
      // Adults doing first-time passport also need birth certificate
      requirements.push({
        documentCode: 'certificado_nacimiento',
        documentNameEs: 'Certificado de Nacimiento',
        isRequired: true,
        displayOrder: 2,
        conditionType: DocumentConditionType.IS_NEW,
        instructionsEs: 'Certificación literal de inscripción de nacimiento',
        acceptedFormats: ['pdf', 'jpg', 'jpeg', 'png'],
      })
    } else if (solicitudType === 'RENOVACION' && motivo) {
      if (motivo === 'VENCIMIENTO' || motivo === 'DETERIORO') {
        requirements.push({
          documentCode: 'pasaporte_antiguo',
          documentNameEs: motivo === 'DETERIORO' ? 'Pasaporte Danado' : 'Pasaporte Antiguo',
          isRequired: true,
          displayOrder: 2,
          conditionType: DocumentConditionType.CUSTOM,
          instructionsEs: motivo === 'DETERIORO'
            ? 'Presente el pasaporte danado para verificacion'
            : 'Escanee la pagina de datos de su pasaporte vencido',
          acceptedFormats: ['pdf', 'jpg', 'jpeg', 'png'],
        })
      } else if (motivo === 'PERDIDA' || motivo === 'ROBO') {
        requirements.push({
          documentCode: 'denuncia_policial',
          documentNameEs: 'Denuncia Policial',
          isRequired: true,
          displayOrder: 2,
          conditionType: DocumentConditionType.CUSTOM,
          instructionsEs: `Denuncia de ${motivo === 'ROBO' ? 'robo' : 'perdida'} emitida por la Policia Nacional`,
          acceptedFormats: ['pdf', 'jpg', 'jpeg', 'png'],
        })
      }
    }

    // Photo - Always required (images only)
    requirements.push({
      documentCode: 'photo_carnet',
      documentNameEs: 'Fotografia tipo pasaporte',
      isRequired: true,
      displayOrder: 10,
      conditionType: DocumentConditionType.ALWAYS,
      instructionsEs: '1 foto de 35x45mm, fondo blanco, rostro visible',
      acceptedFormats: ['jpg', 'jpeg', 'png'],
    })

    // Minor-specific documents
    if (isMinor) {
      // Parental authorization
      requirements.push({
        documentCode: 'autorizacion_parental',
        documentNameEs: 'Autorización Parental',
        isRequired: true,
        displayOrder: 5,
        conditionType: DocumentConditionType.CUSTOM,
        conditionValue: { is_minor: true },
        instructionsEs: representanteUnico
          ? 'Autorización firmada por el representante único (padre, madre o tutor legal)'
          : 'Autorización firmada por AMBOS padres o tutores legales',
        acceptedFormats: ['pdf', 'jpg', 'jpeg', 'png'],
      })

      // Representative 1 identity document (always required for minors)
      requirements.push({
        documentCode: 'documento_representante_1',
        documentNameEs: representanteUnico
          ? 'Documento de Identidad del Representante'
          : 'Documento de Identidad - Representante 1 (Padre/Madre/Tutor)',
        isRequired: true,
        displayOrder: 6,
        conditionType: DocumentConditionType.CUSTOM,
        conditionValue: { is_minor: true },
        instructionsEs: 'DIP, NIE o Pasaporte vigente del representante legal',
        acceptedFormats: ['pdf', 'jpg', 'jpeg', 'png'],
      })

      // Representative 2 identity document (only when both parents required)
      if (representanteUnico === false) {
        requirements.push({
          documentCode: 'documento_representante_2',
          documentNameEs: 'Documento de Identidad - Representante 2 (Padre/Madre/Tutor)',
          isRequired: true,
          displayOrder: 7,
          conditionType: DocumentConditionType.CUSTOM,
          conditionValue: { is_minor: true, representante_unico: false },
          instructionsEs: 'DIP, NIE o Pasaporte vigente del segundo representante legal',
          acceptedFormats: ['pdf', 'jpg', 'jpeg', 'png'],
        })
      }
    }

    return requirements.sort((a, b) => a.displayOrder - b.displayOrder)
  }

  const requirements = getDocumentRequirements()

  // Check if all required documents have previews (2-step flow)
  // OR are already saved in DB (for existing requests)
  const allRequiredUploaded = requirements.every(req => {
    if (!req.isRequired) return true
    // Check preview state first (new 2-step flow)
    if (documentPreviews[req.documentCode]) return true
    // Fallback: check if already saved in DB
    return documents.some(doc => doc.documentCode === req.documentCode)
  })

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          {locale === 'es' ? 'Documentos Requeridos' : locale === 'fr' ? 'Documents Requis' : 'Required Documents'}
        </CardTitle>
        <CardDescription>
          {locale === 'es'
            ? `Tipo: ${solicitudType === 'EXPEDICION' ? 'Primera Expedicion' : `Renovacion - ${motivo}`}${isMinor ? ' (Menor de edad)' : ''}`
            : locale === 'fr'
              ? `Type: ${solicitudType === 'EXPEDICION' ? 'Premiere Emission' : `Renouvellement - ${motivo}`}${isMinor ? ' (Mineur)' : ''}`
              : `Type: ${solicitudType === 'EXPEDICION' ? 'First Issuance' : `Renewal - ${motivo}`}${isMinor ? ' (Minor)' : ''}`}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Warning when documents are locked */}
        {isLocked && (
          <Alert className="border-orange-200 bg-orange-50">
            <AlertTriangle className="h-4 w-4 text-orange-600" />
            <AlertDescription className="text-orange-700">
              {locale === 'es'
                ? 'Los documentos estan bloqueados porque la solicitud ya ha avanzado al pago. No puede modificar los documentos.'
                : locale === 'fr'
                  ? 'Les documents sont bloques car la demande est deja en cours de paiement. Vous ne pouvez pas modifier les documents.'
                  : 'Documents are locked because the request has progressed to payment. You cannot modify documents.'}
            </AlertDescription>
          </Alert>
        )}

        {/* Info about two-step flow */}
        {!isLocked && (
          <Alert className="border-blue-200 bg-blue-50">
            <Eye className="h-4 w-4 text-blue-600" />
            <AlertDescription className="text-blue-700">
              {locale === 'es'
                ? 'Los documentos seran procesados automaticamente. Podra revisar y corregir los datos extraidos antes de guardar.'
                : locale === 'fr'
                  ? 'Les documents seront traites automatiquement. Vous pourrez verifier et corriger les donnees extraites avant de sauvegarder.'
                  : 'Documents will be processed automatically. You can review and correct extracted data before saving.'}
            </AlertDescription>
          </Alert>
        )}

        {requirements.map((req) => {
          const uploadedDoc = documents.find(d => d.documentCode === req.documentCode)
          const preview = documentPreviews[req.documentCode]
          const isUploading = isUploadingDocument === req.documentCode
          const hasPreview = !!preview

          return (
            <div key={req.documentCode} className="space-y-2">
              <DocumentUploader
                requirement={req}
                uploadedDocument={uploadedDoc}
                locale={locale as 'es' | 'fr' | 'en'}
                onUpload={(file) => onUpload(req.documentCode, file)}
                onDelete={uploadedDoc ? async () => { await onDelete(uploadedDoc.id) } : undefined}
                maxSizeMB={req.documentCode === 'photo_carnet' ? 2 : 5}
                disabled={isLocked}
              />

              {/* Loading state during OCR extraction */}
              {isUploading && (
                <div className="flex items-center gap-2 text-sm text-blue-600 bg-blue-50 p-2 rounded">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  {locale === 'es' ? 'Extrayendo datos...' : locale === 'fr' ? 'Extraction en cours...' : 'Extracting data...'}
                </div>
              )}

              {/* Preview success indicator */}
              {hasPreview && !isUploading && (
                <div className="flex items-center gap-2 text-sm text-green-600 bg-green-50 p-2 rounded">
                  <CheckCircle className="h-4 w-4" />
                  {locale === 'es'
                    ? `Datos extraídos (confianza: ${Math.round((preview.confidence || 0) * 100)}%)`
                    : locale === 'fr'
                      ? `Données extraites (confiance: ${Math.round((preview.confidence || 0) * 100)}%)`
                      : `Data extracted (confidence: ${Math.round((preview.confidence || 0) * 100)}%)`}
                </div>
              )}
            </div>
          )
        })}

        <div className="flex justify-between pt-4">
          <Button variant="outline" onClick={onBack}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            {locale === 'es' ? 'Anterior' : locale === 'fr' ? 'Precedent' : 'Back'}
          </Button>
          <Button onClick={onNext} disabled={!allRequiredUploaded}>
            {locale === 'es' ? 'Continuar' : locale === 'fr' ? 'Continuer' : 'Continue'}
            <ArrowRight className="ml-2 h-4 w-4" />
          </Button>
        </div>

        {!allRequiredUploaded && (
          <p className="text-sm text-muted-foreground text-center">
            {locale === 'es'
              ? 'Suba todos los documentos requeridos para continuar'
              : locale === 'fr'
                ? 'Telechargez tous les documents requis pour continuer'
                : 'Upload all required documents to continue'}
          </p>
        )}
      </CardContent>
    </Card>
  )
}

// =============================================================================
// STEP 3-4: Form Review - EDITABLE with confidence indicators
// =============================================================================

interface FormReviewStepEditableProps {
  locale: string
  step: string
  requestId: string
  formData: FormDataResponse | null
  editedData: Record<string, unknown>
  isLoading: boolean
  isSaving: boolean
  saveError: string | null
  isMinor?: boolean
  solicitudType?: PassportSolicitudType | null
  onFieldEdit: (field: string, value: unknown) => void
  onSave: () => Promise<boolean>
  onNext: () => Promise<void>
  onBack: () => void
  onRetry?: () => void
}

function FormReviewStepEditable({
  locale,
  step,
  requestId,
  formData,
  editedData,
  isLoading,
  isSaving,
  saveError,
  isMinor = false,
  solicitudType,
  onFieldEdit,
  onNext,
  onBack,
  onRetry,
}: FormReviewStepEditableProps) {
  const isStep1 = step === 'form_review_1'

  // === DYNAMIC FORM RENDERING (Feature Flag) ===
  // When enabled, fetch form config from backend and use DynamicFormRenderer
  const {
    data: dynamicFormConfig,
    isLoading: isLoadingDynamicConfig,
    error: dynamicConfigError,
  } = useFormConfig(
    FEATURE_DYNAMIC_FORM_RENDERER ? requestId : null,
    FEATURE_DYNAMIC_FORM_RENDERER ? step : null
  )

  // Prefetch next form_review step's config (dynamic)
  const { prefetch } = usePrefetchFormConfig()
  useEffect(() => {
    if (FEATURE_DYNAMIC_FORM_RENDERER && requestId && step.startsWith('form_review_')) {
      // Extract current step number and prefetch next one
      // e.g., form_review_1 → form_review_2, form_review_2 → form_review_3
      const match = step.match(/form_review_(\d+)/)
      if (match) {
        const currentNum = parseInt(match[1], 10)
        const nextStepId = `form_review_${currentNum + 1}`
        // Prefetch silently - if step doesn't exist, it will just fail gracefully
        prefetch(requestId, nextStepId).catch(() => {
          // Next form_review step doesn't exist - that's fine
        })
      }
    }
  }, [step, requestId, prefetch])

  // Validation state for dynamic form
  const [validationErrors, setValidationErrors] = useState<Record<string, string>>({})

  // Handle next with validation
  const handleNextWithValidation = useCallback(() => {
    if (FEATURE_DYNAMIC_FORM_RENDERER && dynamicFormConfig) {
      const loc = locale as 'es' | 'fr' | 'en'
      // Merge extracted data with user edits for validation
      const mergedValues = { ...formData?.formData, ...editedData }
      const errors = validateFormConfig(dynamicFormConfig, mergedValues, loc)

      if (Object.keys(errors).length > 0) {
        setValidationErrors(errors)
        // Scroll to first error
        const firstErrorKey = Object.keys(errors)[0]
        const errorElement = document.getElementById(`field-${firstErrorKey}`)
        if (errorElement) {
          errorElement.scrollIntoView({ behavior: 'smooth', block: 'center' })
        }
        return
      }

      // Clear validation errors and proceed
      setValidationErrors({})
    }
    onNext()
  }, [dynamicFormConfig, editedData, formData, locale, onNext])

  // Clear validation errors when field is edited
  const handleFieldEditWithClear = useCallback((key: string, value: unknown) => {
    if (validationErrors[key]) {
      setValidationErrors(prev => {
        const next = { ...prev }
        delete next[key]
        return next
      })
    }
    onFieldEdit(key, value)
  }, [validationErrors, onFieldEdit])

  // If feature flag is ON and we have config, use DynamicFormRenderer
  if (FEATURE_DYNAMIC_FORM_RENDERER) {
    // Loading state for dynamic form
    if (isLoadingDynamicConfig || isLoading) {
      return (
        <Card>
          <CardContent className="py-12">
            <DynamicFormRenderer.Skeleton />
          </CardContent>
        </Card>
      )
    }

    // Error state for dynamic form - i18n messages
    const errorMessages = {
      title: { es: 'Error al cargar formulario', fr: 'Erreur de chargement', en: 'Error loading form' },
      description: { es: 'No se pudo cargar la configuración del formulario.', fr: 'Impossible de charger la configuration du formulaire.', en: 'Could not load form configuration.' },
      retry: { es: 'Reintentar', fr: 'Réessayer', en: 'Retry' },
      back: { es: 'Volver', fr: 'Retour', en: 'Back' },
    }
    const loc = locale as 'es' | 'fr' | 'en'

    if (dynamicConfigError || !dynamicFormConfig) {
      return (
        <Card>
          <CardHeader>
            <CardTitle>
              {errorMessages.title[loc] || errorMessages.title.es}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>
                {dynamicConfigError?.message || errorMessages.description[loc] || errorMessages.description.es}
              </AlertDescription>
            </Alert>
            {onRetry && (
              <Button variant="outline" onClick={onRetry} className="w-full">
                <RefreshCw className="mr-2 h-4 w-4" />
                {errorMessages.retry[loc] || errorMessages.retry.es}
              </Button>
            )}
            <Button variant="outline" onClick={onBack} className="w-full">
              <ArrowLeft className="mr-2 h-4 w-4" />
              {errorMessages.back[loc] || errorMessages.back.es}
            </Button>
          </CardContent>
        </Card>
      )
    }

    // Form titles - i18n messages (dynamic step number)
    const stepMatch = step.match(/form_review_(\d+)/)
    const stepNum = stepMatch ? parseInt(stepMatch[1], 10) : 1
    const formTitles = {
      title: {
        es: `Verificar y Editar Datos (${stepNum})`,
        fr: `Vérifier et modifier (${stepNum})`,
        en: `Verify & Edit Data (${stepNum})`,
      },
      description: {
        es: 'Los datos fueron extraídos automáticamente. Verifique y corrija si es necesario.',
        fr: 'Les données ont été extraites automatiquement. Vérifiez et corrigez si nécessaire.',
        en: 'Data was extracted automatically. Verify and correct if needed.',
      },
      completed: { es: 'Datos completados', fr: 'Données complétées', en: 'Data completed' },
    }

    // Render dynamic form
    return (
      <Card>
        <CardHeader>
          <CardTitle>
            {formTitles.title[loc] || formTitles.title.es}
          </CardTitle>
          <CardDescription>
            {formTitles.description[loc] || formTitles.description.es}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Completion Progress */}
          {formData && (
            <div className="flex items-center gap-3 p-3 bg-muted rounded-lg">
              <FileCheck className="h-5 w-5 text-primary" />
              <div className="flex-1">
                <p className="text-sm font-medium">
                  {formTitles.completed[loc] || formTitles.completed.es}
                </p>
                <Progress value={formData.completionPercentage} className="h-2 mt-1" />
              </div>
              <span className="text-sm font-semibold">{formData.completionPercentage}%</span>
            </div>
          )}

          {/* Dynamic Form */}
          <DynamicFormRenderer
            config={dynamicFormConfig}
            values={{ ...formData?.formData, ...editedData }}
            onChange={handleFieldEditWithClear}
            locale={locale as 'es' | 'fr' | 'en'}
            disabled={isSaving}
            errors={validationErrors}
          />

          {/* Save Error Display */}
          {saveError && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{saveError}</AlertDescription>
            </Alert>
          )}

          <div className="flex justify-between pt-4">
            <Button variant="outline" onClick={onBack} disabled={isSaving}>
              <ArrowLeft className="mr-2 h-4 w-4" />
              {loc === 'es' ? 'Anterior' : loc === 'fr' ? 'Précédent' : 'Back'}
            </Button>
            <Button onClick={handleNextWithValidation} disabled={isSaving}>
              {isSaving ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  {loc === 'es' ? 'Guardando...' : loc === 'fr' ? 'Enregistrement...' : 'Saving...'}
                </>
              ) : (
                <>
                  <CheckCircle className="mr-2 h-4 w-4" />
                  {loc === 'es' ? 'Guardar y Continuar' : loc === 'fr' ? 'Enregistrer et continuer' : 'Save & Continue'}
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>
    )
  }

  // === LEGACY FORM RENDERING (Feature Flag OFF) ===
  // Fields for each step with their types
  // Note: For minors, numero_dip is not shown (they use certificado_nacimiento instead)
  const step1Fields = [
    // DIP field only for adults
    ...(!isMinor ? [{ key: 'numero_dip', type: 'text', required: true }] : []),
    { key: 'apellidos', type: 'text', required: true },
    { key: 'nombres', type: 'text', required: true },
    { key: 'sexo', type: 'select', options: ['M', 'F'], required: true },
    { key: 'fecha_nacimiento', type: 'date', required: true },
    { key: 'lugar_nacimiento', type: 'text', required: true },
    { key: 'nacionalidad', type: 'text', required: false },
    { key: 'estado_civil', type: 'text', required: false },
    { key: 'profesion', type: 'text', required: false },
    { key: 'grupo_sanguineo', type: 'text', required: false },
    { key: 'domicilio', type: 'text', required: true },
    { key: 'ciudad', type: 'text', required: false },
  ]

  // Step 2 fields - CONDITIONAL based on solicitudType and isMinor
  // Filiation (nombre_padre, nombre_madre, profesion_*):
  //   - Show for EXPEDICION (first passport needs full filiation from certificado)
  //   - Show for minors (always have certificado_nacimiento with filiation)
  //   - For RENOVACION adults: these come from DIP which has nombre_padre and nombre_madre
  // Pasaporte Anterior (numero, fechas):
  //   - Show ONLY for RENOVACION (all motivos require old passport info)
  const showFiliationFields = solicitudType === 'EXPEDICION' || isMinor
  const showPasaporteAnteriorFields = solicitudType === 'RENOVACION'

  const step2Fields = [
    // Filiation section - conditional
    ...(showFiliationFields ? [
      { key: 'nombre_padre', type: 'text', required: false },
      { key: 'profesion_padre', type: 'text', required: false },
      { key: 'nombre_madre', type: 'text', required: false },
      { key: 'profesion_madre', type: 'text', required: false },
    ] : []),
    // Pasaporte anterior section - conditional (RENOVACION only)
    ...(showPasaporteAnteriorFields ? [
      { key: 'numero_pasaporte_antiguo', type: 'text', required: true },
      { key: 'fecha_expedicion_antiguo', type: 'date', required: true },
      { key: 'fecha_expiracion_antiguo', type: 'date', required: true },
    ] : []),
  ]

  const fieldsToShow = isStep1 ? step1Fields : step2Fields

  const getFieldLabel = (field: string): string => {
    const labels: Record<string, Record<string, string>> = {
      numero_dip: { es: 'Número DIP', fr: 'Numéro DIP', en: 'DIP Number' },
      apellidos: { es: 'Apellidos', fr: 'Nom de famille', en: 'Last Name' },
      nombres: { es: 'Nombres', fr: 'Prénoms', en: 'First Name' },
      sexo: { es: 'Sexo', fr: 'Sexe', en: 'Gender' },
      fecha_nacimiento: { es: 'Fecha de Nacimiento', fr: 'Date de Naissance', en: 'Birth Date' },
      lugar_nacimiento: { es: 'Lugar de Nacimiento', fr: 'Lieu de Naissance', en: 'Birth Place' },
      nacionalidad: { es: 'Nacionalidad', fr: 'Nationalité', en: 'Nationality' },
      estado_civil: { es: 'Estado Civil', fr: 'État Civil', en: 'Marital Status' },
      profesion: { es: 'Profesión', fr: 'Profession', en: 'Profession' },
      grupo_sanguineo: { es: 'Grupo Sanguíneo', fr: 'Groupe Sanguin', en: 'Blood Type' },
      domicilio: { es: 'Domicilio', fr: 'Adresse', en: 'Address' },
      ciudad: { es: 'Ciudad', fr: 'Ville', en: 'City' },
      nombre_padre: { es: 'Nombre del Padre', fr: 'Nom du Père', en: 'Father Name' },
      profesion_padre: { es: 'Profesión del Padre', fr: 'Profession du Père', en: 'Father Profession' },
      nombre_madre: { es: 'Nombre de la Madre', fr: 'Nom de la Mère', en: 'Mother Name' },
      profesion_madre: { es: 'Profesión de la Madre', fr: 'Profession de la Mère', en: 'Mother Profession' },
      numero_pasaporte_antiguo: { es: 'Número Pasaporte Antiguo', fr: 'Numéro Ancien Passeport', en: 'Old Passport Number' },
      fecha_expedicion_antiguo: { es: 'Fecha Expedición Antiguo', fr: 'Date Émission Ancien', en: 'Old Issue Date' },
      fecha_expiracion_antiguo: { es: 'Fecha Expiración Antiguo', fr: 'Date Expiration Ancien', en: 'Old Expiry Date' },
    }
    return labels[field]?.[locale] || field.replace(/_/g, ' ')
  }

  // Get current value (edited or extracted)
  const getFieldValue = (field: string): string => {
    if (editedData[field] !== undefined) {
      return String(editedData[field])
    }
    if (formData?.formData?.[field] !== undefined) {
      return String(formData.formData[field])
    }
    if (formData?.extractedData?.[field] !== undefined) {
      return String(formData.extractedData[field])
    }
    return ''
  }

  // Check if field was extracted (to show confidence indicator)
  const isExtractedField = (field: string): boolean => {
    return formData?.extractedData?.[field] !== undefined
  }

  // Check if field was modified by user
  const isModifiedField = (field: string): boolean => {
    return editedData[field] !== undefined
  }

  if (isLoading) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <Loader2 className="h-8 w-8 animate-spin mx-auto mb-4 text-primary" />
          <p className="text-muted-foreground">
            {locale === 'es' ? 'Cargando datos extraídos...' : locale === 'fr' ? 'Chargement des données...' : 'Loading extracted data...'}
          </p>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          {isStep1
            ? (locale === 'es' ? 'Verificar y Editar Datos (1/2)' : locale === 'fr' ? 'Vérifier et Éditer (1/2)' : 'Verify & Edit Data (1/2)')
            : (locale === 'es' ? 'Verificar y Editar Datos (2/2)' : locale === 'fr' ? 'Vérifier et Éditer (2/2)' : 'Verify & Edit Data (2/2)')}
        </CardTitle>
        <CardDescription>
          {locale === 'es'
            ? 'Los datos fueron extraídos automáticamente. Verifique y corrija si es necesario.'
            : locale === 'fr'
              ? 'Les données ont été extraites automatiquement. Vérifiez et corrigez si nécessaire.'
              : 'Data was extracted automatically. Verify and correct if needed.'}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {formData ? (
          <>
            {/* Completion Progress */}
            <div className="flex items-center gap-3 p-3 bg-muted rounded-lg">
              <FileCheck className="h-5 w-5 text-primary" />
              <div className="flex-1">
                <p className="text-sm font-medium">
                  {locale === 'es' ? 'Datos completados' : locale === 'fr' ? 'Données complétées' : 'Data completed'}
                </p>
                <Progress value={formData.completionPercentage} className="h-2 mt-1" />
              </div>
              <span className="text-sm font-semibold">{formData.completionPercentage}%</span>
            </div>

            {/* Legend */}
            <div className="flex gap-4 text-xs text-muted-foreground">
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 bg-blue-500 rounded-full"></span>
                {locale === 'es' ? 'Extraído automáticamente' : 'Auto-extracted'}
              </span>
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 bg-green-500 rounded-full"></span>
                {locale === 'es' ? 'Modificado por usted' : 'Modified by you'}
              </span>
            </div>

            {/* Editable Form Fields */}
            <div className="space-y-4">
              {fieldsToShow.map(({ key: field, type, required }) => {
                const value = getFieldValue(field)
                const isExtracted = isExtractedField(field)
                const isModified = isModifiedField(field)
                const isMissing = required && !value

                return (
                  <div key={field} className="space-y-1">
                    <div className="flex items-center gap-2">
                      <Label htmlFor={field} className="text-sm font-medium">
                        {getFieldLabel(field)}
                        {required && <span className="text-red-500 ml-1">*</span>}
                      </Label>
                      {isExtracted && !isModified && (
                        <Badge variant="outline" className="text-xs bg-blue-50 text-blue-700 border-blue-200">
                          {locale === 'es' ? 'OCR' : 'OCR'}
                        </Badge>
                      )}
                      {isModified && (
                        <Badge variant="outline" className="text-xs bg-green-50 text-green-700 border-green-200">
                          {locale === 'es' ? 'Editado' : 'Edited'}
                        </Badge>
                      )}
                    </div>
                    {type === 'select' ? (
                      <RadioGroup
                        value={value}
                        onValueChange={(v) => onFieldEdit(field, v)}
                        className="flex gap-4"
                      >
                        <div className="flex items-center space-x-2">
                          <RadioGroupItem value="M" id={`${field}-m`} />
                          <Label htmlFor={`${field}-m`}>{locale === 'es' ? 'Masculino' : 'Male'}</Label>
                        </div>
                        <div className="flex items-center space-x-2">
                          <RadioGroupItem value="F" id={`${field}-f`} />
                          <Label htmlFor={`${field}-f`}>{locale === 'es' ? 'Femenino' : 'Female'}</Label>
                        </div>
                      </RadioGroup>
                    ) : (
                      <Input
                        id={field}
                        type={type}
                        value={value}
                        onChange={(e) => onFieldEdit(field, e.target.value)}
                        className={`${isMissing ? 'border-red-300 bg-red-50' : ''} ${isExtracted && !isModified ? 'border-blue-200 bg-blue-50/30' : ''}`}
                        placeholder={isMissing ? (locale === 'es' ? 'Campo requerido' : 'Required field') : ''}
                      />
                    )}
                  </div>
                )
              })}
            </div>

            {/* Missing Fields Warning */}
            {formData.missingFields && formData.missingFields.filter(f => fieldsToShow.some(fs => fs.key === f && fs.required)).length > 0 && (
              <Alert className="border-yellow-200 bg-yellow-50">
                <AlertTriangle className="h-4 w-4 text-yellow-600" />
                <AlertDescription className="text-yellow-700">
                  {locale === 'es'
                    ? 'Complete los campos requeridos marcados en rojo para continuar.'
                    : 'Fill in required fields marked in red to continue.'}
                </AlertDescription>
              </Alert>
            )}
          </>
        ) : (
          <div className="space-y-4">
            <Alert>
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>
                {locale === 'es'
                  ? 'No se pudieron cargar los datos extraídos. Verifique su conexión e intente de nuevo.'
                  : locale === 'fr'
                    ? 'Impossible de charger les données extraites. Vérifiez votre connexion et réessayez.'
                    : 'Could not load extracted data. Check your connection and try again.'}
              </AlertDescription>
            </Alert>
            {onRetry && (
              <Button variant="outline" onClick={onRetry} className="w-full">
                <RefreshCw className="mr-2 h-4 w-4" />
                {locale === 'es' ? 'Reintentar' : locale === 'fr' ? 'Réessayer' : 'Retry'}
              </Button>
            )}
          </div>
        )}

        {/* Save Error Display */}
        {saveError && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{saveError}</AlertDescription>
          </Alert>
        )}

        <div className="flex justify-between pt-4">
          <Button variant="outline" onClick={onBack} disabled={isSaving}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            {locale === 'es' ? 'Anterior' : locale === 'fr' ? 'Précédent' : 'Back'}
          </Button>
          <Button onClick={onNext} disabled={isSaving}>
            {isSaving ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                {locale === 'es' ? 'Guardando...' : 'Saving...'}
              </>
            ) : (
              <>
                <CheckCircle className="mr-2 h-4 w-4" />
                {locale === 'es' ? 'Guardar y Continuar' : locale === 'fr' ? 'Enregistrer et Continuer' : 'Save & Continue'}
              </>
            )}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

// =============================================================================
// NOTE: ValidationStepImproved component REMOVED
// Cross-document validation is now done during extraction (Step 3: upload_documents)
// by Gemini processor with identity mismatch blocking. No separate validation step needed.
// =============================================================================

// =============================================================================
// STEP 5: Payment - IMPROVED with status polling (was Step 6 before validation removal)
// =============================================================================

interface PaymentStepImprovedProps {
  locale: string
  tariff: number
  availableMethods: PaymentMethodInfo[]
  isLoadingMethods: boolean
  methodsError: string | null
  onRetryLoadMethods: () => void
  selectedMethod: PaymentMethod | null
  phoneNumber: string
  isProcessing: boolean
  paymentComplete: boolean
  // Cash payment result with reference and instructions
  pendingPaymentResult: {
    paymentReference?: string
    messageEs?: string
    actionType?: string
    isManualPayment: boolean
  } | null
  onMethodSelect: (method: PaymentMethod) => void
  onPhoneChange: (phone: string) => void
  onPay: () => Promise<void>
  onNext: () => void
  onBack: () => void
}

function PaymentStepImproved({
  locale,
  tariff,
  availableMethods,
  isLoadingMethods,
  methodsError,
  onRetryLoadMethods,
  selectedMethod,
  phoneNumber,
  isProcessing,
  paymentComplete,
  pendingPaymentResult,
  onMethodSelect,
  onPhoneChange,
  onPay,
  onNext,
  onBack,
}: PaymentStepImprovedProps) {
  // Get icon for method code
  const getMethodIcon = (code: string) => {
    const icons: Record<string, React.ComponentType<{ className?: string }>> = {
      mobile_money: Smartphone,
      cash: Banknote,
      check: Banknote,
      card: CreditCard,
      bank_transfer: Banknote,
    }
    return icons[code] || Banknote
  }

  const texts = {
    es: {
      title: 'Pago de Tasas',
      subtitle: 'Seleccione un metodo de pago',
      amount: 'Monto a pagar',
      selectMethod: 'Metodo de pago',
      phoneLabel: 'Numero de telefono',
      phonePlaceholder: '+240 XXX XXX XXX',
      payButton: 'Pagar ahora',
      processing: 'Procesando pago...',
      waitingConfirmation: 'Esperando confirmacion...',
      paymentComplete: 'Pago confirmado',
      back: 'Anterior',
    },
    fr: {
      title: 'Paiement des Frais',
      subtitle: 'Selectionnez un mode de paiement',
      amount: 'Montant a payer',
      selectMethod: 'Mode de paiement',
      phoneLabel: 'Numero de telephone',
      phonePlaceholder: '+240 XXX XXX XXX',
      payButton: 'Payer maintenant',
      processing: 'Traitement en cours...',
      waitingConfirmation: 'En attente de confirmation...',
      paymentComplete: 'Paiement confirme',
      back: 'Precedent',
    },
    en: {
      title: 'Fee Payment',
      subtitle: 'Select a payment method',
      amount: 'Amount to pay',
      selectMethod: 'Payment method',
      phoneLabel: 'Phone number',
      phonePlaceholder: '+240 XXX XXX XXX',
      payButton: 'Pay now',
      processing: 'Processing payment...',
      waitingConfirmation: 'Waiting for confirmation...',
      paymentComplete: 'Payment confirmed',
      back: 'Back',
    },
  }

  const t = texts[locale as keyof typeof texts] || texts.es

  const selectedMethodInfo = availableMethods.find(m => m.code === selectedMethod)
  const canPay = selectedMethod !== null &&
    (!selectedMethodInfo?.requiresPhone || phoneNumber.length >= 9)

  if (paymentComplete) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <CheckCircle className="h-10 w-10 text-green-600" />
          </div>
          <h3 className="text-lg font-semibold text-green-600 mb-2">{t.paymentComplete}</h3>
          <p className="text-muted-foreground mb-4">{tariff.toLocaleString()} XAF</p>
          <Button onClick={onNext}>
            {locale === 'es' ? 'Continuar a la Cita' : locale === 'fr' ? 'Continuer au Rendez-vous' : 'Continue to Appointment'}
            <ArrowRight className="ml-2 h-4 w-4" />
          </Button>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t.title}</CardTitle>
        <CardDescription>{t.subtitle}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Amount Display */}
        <div className="p-4 bg-muted rounded-lg text-center">
          <p className="text-sm text-muted-foreground">{t.amount}</p>
          <p className="text-3xl font-bold text-primary">{tariff.toLocaleString()} XAF</p>
        </div>

        {/* Payment Method Selection */}
        <div className="space-y-3">
          <Label>{t.selectMethod}</Label>
          {isLoadingMethods ? (
            <div className="flex items-center gap-2 text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>{locale === 'es' ? 'Cargando metodos...' : locale === 'fr' ? 'Chargement...' : 'Loading methods...'}</span>
            </div>
          ) : methodsError ? (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription className="flex items-center justify-between">
                <span>{methodsError}</span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={onRetryLoadMethods}
                  className="ml-4"
                >
                  <RefreshCw className="mr-2 h-4 w-4" />
                  {locale === 'es' ? 'Reintentar' : locale === 'fr' ? 'Réessayer' : 'Retry'}
                </Button>
              </AlertDescription>
            </Alert>
          ) : availableMethods.length === 0 ? (
            <Alert>
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>
                {locale === 'es' ? 'No hay métodos de pago disponibles.' :
                 locale === 'fr' ? 'Aucune méthode de paiement disponible.' :
                 'No payment methods available.'}
              </AlertDescription>
            </Alert>
          ) : (
            <RadioGroup
              value={selectedMethod || ''}
              onValueChange={(value) => onMethodSelect(value as PaymentMethod)}
              disabled={isProcessing}
            >
              {availableMethods.map((method) => {
                const Icon = getMethodIcon(method.code)
                const label = locale === 'es' ? method.labelEs : locale === 'fr' ? method.labelFr : method.labelEn
                return (
                  <div key={method.code} className="flex items-center space-x-3">
                    <RadioGroupItem value={method.code} id={method.code} />
                    <Label htmlFor={method.code} className="flex items-center gap-2 cursor-pointer">
                      <Icon className="h-5 w-5" />
                      {label}
                      {method.requiresAgentValidation && (
                        <span className="text-xs text-muted-foreground">
                          ({locale === 'es' ? 'validacion manual' : locale === 'fr' ? 'validation manuelle' : 'manual validation'})
                        </span>
                      )}
                    </Label>
                  </div>
                )
              })}
            </RadioGroup>
          )}
        </div>

        {/* Phone Number (for methods requiring phone) */}
        {selectedMethodInfo?.requiresPhone && (
          <div className="space-y-2">
            <Label htmlFor="phone">{t.phoneLabel}</Label>
            <Input
              id="phone"
              type="tel"
              value={phoneNumber}
              onChange={(e) => onPhoneChange(e.target.value)}
              placeholder={t.phonePlaceholder}
              disabled={isProcessing}
            />
          </div>
        )}

        {/* Cash/Check Payment Result - Show when manual payment initiated */}
        {pendingPaymentResult?.isManualPayment && !isProcessing && (
          <div className="space-y-4">
            {/* Status Alert - Changes based on paymentComplete */}
            {paymentComplete ? (
              <Alert className="border-green-200 bg-green-50">
                <CheckCircle className="h-4 w-4 text-green-600" />
                <AlertDescription className="text-green-700 font-medium">
                  {locale === 'es' ? 'Pago validado! Puede continuar a reservar su cita.' :
                   locale === 'fr' ? 'Paiement valide! Vous pouvez continuer a reserver votre rendez-vous.' :
                   'Payment validated! You can now book your appointment.'}
                </AlertDescription>
              </Alert>
            ) : (
              <Alert className="border-amber-200 bg-amber-50">
                <Clock className="h-4 w-4 text-amber-600 animate-pulse" />
                <AlertDescription className="text-amber-700 font-medium">
                  {locale === 'es' ? 'Pago en espera de validacion...' :
                   locale === 'fr' ? 'Paiement en attente de validation...' :
                   'Payment awaiting validation...'}
                </AlertDescription>
              </Alert>
            )}

            {/* Reference Number Display */}
            <Alert className="border-gray-200 bg-gray-50">
              <Building2 className="h-4 w-4 text-gray-600" />
              <AlertDescription className="text-gray-800 space-y-2">
                <p className="font-medium">
                  {locale === 'es' ? 'Referencia de Pago:' :
                   locale === 'fr' ? 'Reference de paiement:' :
                   'Payment Reference:'}
                </p>
                <p className="text-xl font-bold font-mono">
                  {pendingPaymentResult.paymentReference}
                </p>
              </AlertDescription>
            </Alert>

            {/* Instructions - Only show when NOT yet validated */}
            {!paymentComplete && (
              <Alert className="border-blue-200 bg-blue-50">
                <AlertCircle className="h-4 w-4 text-blue-600" />
                <AlertDescription className="text-blue-700">
                  {locale === 'es' ? (
                    <>
                      <p className="font-medium mb-1">Instrucciones:</p>
                      <p>Presente este comprobante en la oficina del Tesoro junto con el monto de <strong>{tariff.toLocaleString()} XAF</strong>.</p>
                      <p className="mt-2 text-sm font-medium">Un agente del Tesoro validara su pago. Solo entonces podra reservar su cita.</p>
                    </>
                  ) : locale === 'fr' ? (
                    <>
                      <p className="font-medium mb-1">Instructions:</p>
                      <p>Presentez ce recu au bureau du Tresor avec le montant de <strong>{tariff.toLocaleString()} XAF</strong>.</p>
                      <p className="mt-2 text-sm font-medium">Un agent du Tresor validera votre paiement. Vous pourrez prendre rendez-vous uniquement apres validation.</p>
                    </>
                  ) : (
                    <>
                      <p className="font-medium mb-1">Instructions:</p>
                      <p>Present this receipt at the Treasury office with the amount of <strong>{tariff.toLocaleString()} XAF</strong>.</p>
                      <p className="mt-2 text-sm font-medium">A Treasury agent will validate your payment. Only then can you book your appointment.</p>
                    </>
                  )}
                </AlertDescription>
              </Alert>
            )}
          </div>
        )}

        {/* Electronic Payment Processing State */}
        {isProcessing && !pendingPaymentResult?.isManualPayment && (
          <Alert className="border-blue-200 bg-blue-50">
            <Loader2 className="h-4 w-4 text-blue-600 animate-spin" />
            <AlertDescription className="text-blue-700">
              {t.waitingConfirmation}
            </AlertDescription>
          </Alert>
        )}

        {/* Action Buttons */}
        <div className="flex justify-between pt-4">
          <Button variant="outline" onClick={onBack} disabled={isProcessing || (pendingPaymentResult?.isManualPayment && !paymentComplete)}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            {t.back}
          </Button>
          {pendingPaymentResult?.isManualPayment ? (
            // Manual payment (cash/check): Show continue button - DISABLED until payment validated
            <Button
              onClick={onNext}
              disabled={!paymentComplete}
              className={!paymentComplete ? 'opacity-50 cursor-not-allowed' : ''}
            >
              {!paymentComplete ? (
                <>
                  <Clock className="mr-2 h-4 w-4 animate-pulse" />
                  {locale === 'es' ? 'Esperando validacion...' :
                   locale === 'fr' ? 'En attente de validation...' :
                   'Waiting for validation...'}
                </>
              ) : (
                <>
                  <CheckCircle className="mr-2 h-4 w-4" />
                  {locale === 'es' ? 'Continuar a la Cita' : locale === 'fr' ? 'Continuer au Rendez-vous' : 'Continue to Appointment'}
                  <ArrowRight className="ml-2 h-4 w-4" />
                </>
              )}
            </Button>
          ) : (
            // Electronic payment: Normal pay button
            <Button onClick={onPay} disabled={!canPay || isProcessing}>
              {isProcessing ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  {t.processing}
                </>
              ) : (
                <>
                  <CreditCard className="mr-2 h-4 w-4" />
                  {t.payButton}
                </>
              )}
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

// =============================================================================
// STEP 7: Appointment - IMPROVED with notifications
// =============================================================================

interface AppointmentStepImprovedProps {
  locale: string
  requestId: string
  tariff: number
  paymentComplete: boolean
  pendingPaymentReference?: string
  getLocations: (requestId: string) => Promise<{ entityCode: string; locations: EntityLocation[]; count: number }>
  getAvailableDays: (requestId: string, entityLocationId: string, fromDate?: string, toDate?: string) => Promise<{ days: Array<{ date: string; timeSlotCount: number; totalSlotsRemaining: number }>; minDate?: string }>
  // Migration 030: Uses entityLocationId FK instead of locationName
  getSlots: (requestId: string, entityLocationId: string, fromDate?: string, limit?: number) => Promise<{ entityCode: string; locationName: string; fromDate: string; slots: AvailableSlot[]; count: number; hasAvailability: boolean }>
  holdSlot: (requestId: string, data: { entityLocationId: string; slotConfigId?: string; appointmentDate: string; appointmentTime: string }) => Promise<{ success: boolean; holdId?: string; expiresInSeconds: number; expiresAt?: string; error?: string }>
  getHoldStatus: (requestId: string) => Promise<AppointmentHoldStatus>
  releaseHold: (requestId: string) => Promise<{ success: boolean; message: string }>
  onComplete: (data: { hasAppointment: boolean; locationName?: string; appointmentDate?: string; appointmentTime?: string; isFallback: boolean }) => void
  onBack: () => void
}

function AppointmentStepImproved({
  locale,
  requestId,
  tariff,
  paymentComplete,
  pendingPaymentReference,
  getLocations,
  getAvailableDays,
  getSlots,
  holdSlot,
  getHoldStatus,
  releaseHold,
  onComplete,
  onBack,
}: AppointmentStepImprovedProps) {
  return (
    <div className="space-y-4">
      {/* Payment Status Banner - Conditional based on actual payment status */}
      {paymentComplete ? (
        <Alert className="border-green-200 bg-green-50">
          <CheckCircle className="h-4 w-4 text-green-600" />
          <AlertDescription className="text-green-700">
            {locale === 'es'
              ? `Pago de ${tariff.toLocaleString()} XAF confirmado. Seleccione su cita.`
              : locale === 'fr'
                ? `Paiement de ${tariff.toLocaleString()} XAF confirme. Selectionnez votre rendez-vous.`
                : `Payment of ${tariff.toLocaleString()} XAF confirmed. Select your appointment.`}
          </AlertDescription>
        </Alert>
      ) : (
        <Alert className="border-amber-200 bg-amber-50">
          <Clock className="h-4 w-4 text-amber-600" />
          <AlertDescription className="text-amber-700">
            {locale === 'es'
              ? `Pago de ${tariff.toLocaleString()} XAF en espera de validacion.${pendingPaymentReference ? ` Referencia: ${pendingPaymentReference}` : ''} Puede reservar su cita mientras se procesa.`
              : locale === 'fr'
                ? `Paiement de ${tariff.toLocaleString()} XAF en attente de validation.${pendingPaymentReference ? ` Reference: ${pendingPaymentReference}` : ''} Vous pouvez reserver votre rendez-vous pendant le traitement.`
                : `Payment of ${tariff.toLocaleString()} XAF pending validation.${pendingPaymentReference ? ` Reference: ${pendingPaymentReference}` : ''} You can book your appointment while it processes.`}
          </AlertDescription>
        </Alert>
      )}

      {/* Notification Info */}
      <Alert className="border-blue-200 bg-blue-50">
        <Bell className="h-4 w-4 text-blue-600" />
        <AlertDescription className="text-blue-700">
          {locale === 'es'
            ? 'Recibira una confirmacion por SMS y correo electronico al reservar su cita.'
            : locale === 'fr'
              ? 'Vous recevrez une confirmation par SMS et email lors de la reservation.'
              : 'You will receive SMS and email confirmation when booking your appointment.'}
        </AlertDescription>
      </Alert>

      {/* AppointmentSelection Component */}
      <AppointmentSelection
        requestId={requestId}
        locale={locale as 'es' | 'fr' | 'en'}
        onComplete={onComplete}
        onBack={onBack}
        getLocations={getLocations}
        getAvailableDays={getAvailableDays}
        getSlots={getSlots}
        holdSlot={holdSlot}
        getHoldStatus={getHoldStatus}
        releaseHold={releaseHold}
        submitWithoutAppointment={async (reqId, preferredLocation) => ({
          success: true,
          locationName: preferredLocation,
          message: 'Submitted without appointment',
        })}
      />
    </div>
  )
}

// =============================================================================
// STEP 8: Confirmation - IMPROVED with notification status
// =============================================================================

interface ConfirmationStepImprovedProps {
  locale: string
  requestId: string
  tariff: number
  summary: CitizenSummaryResponse | null
  notificationsSent: boolean
  onDownloadPDF: () => Promise<void>
}

function ConfirmationStepImproved({ locale, requestId, tariff, summary, notificationsSent, onDownloadPDF }: ConfirmationStepImprovedProps) {
  const router = useRouter()
  const [isDownloading, setIsDownloading] = useState(false)

  const handleDownload = async () => {
    setIsDownloading(true)
    try {
      await onDownloadPDF()
    } finally {
      setIsDownloading(false)
    }
  }

  if (summary) {
    return (
      <div className="space-y-4">
        {/* Success Banner */}
        <Alert className="border-green-200 bg-green-50">
          <CheckCircle className="h-4 w-4 text-green-600" />
          <AlertDescription className="text-green-700 font-semibold">
            {locale === 'es'
              ? 'Solicitud completada exitosamente'
              : locale === 'fr'
                ? 'Demande completee avec succes'
                : 'Request completed successfully'}
          </AlertDescription>
        </Alert>

        {/* Notification Status */}
        {notificationsSent && (
          <Alert className="border-blue-200 bg-blue-50">
            <Bell className="h-4 w-4 text-blue-600" />
            <AlertDescription className="text-blue-700">
              {locale === 'es'
                ? 'Se ha enviado una confirmacion a su telefono y correo electronico.'
                : locale === 'fr'
                  ? 'Une confirmation a ete envoyee sur votre telephone et email.'
                  : 'A confirmation has been sent to your phone and email.'}
            </AlertDescription>
          </Alert>
        )}

        {/* Summary Display using CitizenSummaryForm */}
        <CitizenSummaryForm
          summary={summary}
          locale={locale as 'es' | 'fr' | 'en'}
          isSubmitting={false}
          onSubmit={async () => {}}
          onBack={() => {}}
          onEditDocuments={() => {}}
          onEditPersonalData={() => {}}
          onDownloadPDF={handleDownload}
        />

        {/* Navigation */}
        <div className="flex justify-center gap-2 pt-4">
          <Button
            variant="outline"
            onClick={() => router.push(`/${locale}/dashboard/service-requests/${requestId}`)}
          >
            {locale === 'es' ? 'Ver Detalles' : locale === 'fr' ? 'Voir les Details' : 'View Details'}
          </Button>
          <Button onClick={() => router.push(`/${locale}/dashboard/service-requests`)}>
            {locale === 'es' ? 'Volver a Solicitudes' : locale === 'fr' ? 'Retour aux Demandes' : 'Back to Requests'}
          </Button>
        </div>
      </div>
    )
  }

  // Fallback simple display
  return (
    <Card>
      <CardHeader className="text-center">
        <div className="mx-auto w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mb-4">
          <CheckCircle className="h-10 w-10 text-green-600" />
        </div>
        <CardTitle className="text-green-600">
          {locale === 'es' ? 'Solicitud Completada' : locale === 'fr' ? 'Demande Terminee' : 'Request Completed'}
        </CardTitle>
        <CardDescription>
          {locale === 'es'
            ? 'Su solicitud de pasaporte ha sido registrada exitosamente'
            : locale === 'fr'
              ? 'Votre demande de passeport a ete enregistree avec succes'
              : 'Your passport request has been successfully registered'}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="p-4 bg-muted rounded-lg space-y-2">
          <div className="flex justify-between">
            <span className="text-muted-foreground">{locale === 'es' ? 'Referencia' : 'Reference'}</span>
            <span className="font-mono font-semibold">{requestId.slice(0, 8).toUpperCase()}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">{locale === 'es' ? 'Tarifa pagada' : 'Fee paid'}</span>
            <span className="font-semibold">{tariff.toLocaleString()} XAF</span>
          </div>
        </div>

        <div className="flex justify-center gap-2">
          <Button variant="outline" onClick={handleDownload} disabled={isDownloading}>
            {isDownloading ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Download className="mr-2 h-4 w-4" />
            )}
            {locale === 'es' ? 'Descargar PDF' : locale === 'fr' ? 'Telecharger PDF' : 'Download PDF'}
          </Button>
          <Button onClick={() => router.push(`/${locale}/dashboard/service-requests`)}>
            {locale === 'es' ? 'Volver a Solicitudes' : locale === 'fr' ? 'Retour aux Demandes' : 'Back to Requests'}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

// =============================================================================
// STEP: Legal Representatives Info (for minors only)
// =============================================================================

interface RepresentantesLegalesStepProps {
  locale: string
  representanteUnico: boolean | null
  motivoRepresentanteUnico: string | null
  onSave: (representanteUnico: boolean, motivoRepresentanteUnico: string | null) => void
  onBack: () => void
  isSaving: boolean
}

function RepresentantesLegalesStep({
  locale,
  representanteUnico: initialRepresentanteUnico,
  motivoRepresentanteUnico: initialMotivoRepresentanteUnico,
  onSave,
  onBack,
  isSaving,
}: RepresentantesLegalesStepProps) {
  const [representanteUnico, setRepresentanteUnico] = useState<boolean>(
    initialRepresentanteUnico ?? false
  )
  const [motivoRepresentanteUnico, setMotivoRepresentanteUnico] = useState<string>(
    initialMotivoRepresentanteUnico ?? ''
  )

  const motivoOptions = [
    { value: 'custodia_exclusiva', labelEs: 'Custodia exclusiva', labelFr: 'Garde exclusive', labelEn: 'Sole custody' },
    { value: 'fallecimiento', labelEs: 'Fallecimiento de un padre', labelFr: 'Décès d\'un parent', labelEn: 'Parent deceased' },
    { value: 'desconocido', labelEs: 'Padre desconocido', labelFr: 'Parent inconnu', labelEn: 'Unknown parent' },
    { value: 'otro', labelEs: 'Otro motivo', labelFr: 'Autre motif', labelEn: 'Other reason' },
  ]

  const handleContinue = () => {
    onSave(
      representanteUnico,
      representanteUnico ? motivoRepresentanteUnico : null
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          {locale === 'es' ? 'Representantes Legales' : locale === 'fr' ? 'Représentants Légaux' : 'Legal Representatives'}
        </CardTitle>
        <CardDescription>
          {locale === 'es'
            ? 'Información sobre los padres/tutores del menor'
            : locale === 'fr'
              ? 'Informations sur les parents/tuteurs du mineur'
              : 'Information about the minor\'s parents/guardians'}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Representante Unico Checkbox */}
        <div className="flex items-start space-x-3 p-4 border rounded-lg">
          <input
            type="checkbox"
            id="representante_unico"
            checked={representanteUnico}
            onChange={(e) => setRepresentanteUnico(e.target.checked)}
            className="mt-1 h-4 w-4 rounded border-gray-300"
          />
          <div>
            <label htmlFor="representante_unico" className="font-medium cursor-pointer">
              {locale === 'es' ? 'Representante único' : locale === 'fr' ? 'Représentant unique' : 'Single representative'}
            </label>
            <p className="text-sm text-muted-foreground">
              {locale === 'es'
                ? 'Un solo padre o tutor realiza este trámite (custodia exclusiva, fallecimiento, etc.)'
                : locale === 'fr'
                  ? 'Un seul parent ou tuteur effectue cette démarche (garde exclusive, décès, etc.)'
                  : 'Only one parent or guardian is handling this request (sole custody, death, etc.)'}
            </p>
          </div>
        </div>

        {/* Motivo selection (only if representante_unico is true) */}
        {representanteUnico && (
          <div className="space-y-3">
            <label className="font-medium">
              {locale === 'es' ? 'Motivo del representante único' : locale === 'fr' ? 'Motif du représentant unique' : 'Reason for single representative'}
            </label>
            <div className="grid gap-2">
              {motivoOptions.map((option) => (
                <div
                  key={option.value}
                  className={`p-3 border rounded-lg cursor-pointer transition-colors ${
                    motivoRepresentanteUnico === option.value
                      ? 'border-primary bg-primary/5'
                      : 'hover:border-gray-400'
                  }`}
                  onClick={() => setMotivoRepresentanteUnico(option.value)}
                >
                  <div className="flex items-center gap-3">
                    <div className={`w-4 h-4 rounded-full border-2 ${
                      motivoRepresentanteUnico === option.value
                        ? 'border-primary bg-primary'
                        : 'border-gray-300'
                    }`}>
                      {motivoRepresentanteUnico === option.value && (
                        <div className="w-full h-full flex items-center justify-center">
                          <div className="w-1.5 h-1.5 bg-white rounded-full" />
                        </div>
                      )}
                    </div>
                    <span>
                      {locale === 'es' ? option.labelEs : locale === 'fr' ? option.labelFr : option.labelEn}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Info about documents required */}
        <div className="p-4 bg-blue-50 text-blue-800 rounded-lg">
          <p className="text-sm">
            {locale === 'es'
              ? representanteUnico
                ? 'Deberá subir: Autorización parental + Documento de identidad del representante (DIP, NIE o Pasaporte)'
                : 'Deberá subir: Autorización parental firmada por ambos + Documentos de identidad de ambos representantes'
              : locale === 'fr'
                ? representanteUnico
                  ? 'Vous devrez télécharger: Autorisation parentale + Document d\'identité du représentant (DIP, NIE ou Passeport)'
                  : 'Vous devrez télécharger: Autorisation parentale signée par les deux + Documents d\'identité des deux représentants'
                : representanteUnico
                  ? 'You will need to upload: Parental authorization + Representative\'s identity document (DIP, NIE or Passport)'
                  : 'You will need to upload: Parental authorization signed by both + Identity documents for both representatives'}
          </p>
        </div>

        {/* Navigation buttons */}
        <div className="flex justify-between pt-4">
          <Button variant="outline" onClick={onBack} disabled={isSaving}>
            <ChevronLeft className="h-4 w-4 mr-1" />
            {locale === 'es' ? 'Anterior' : locale === 'fr' ? 'Précédent' : 'Back'}
          </Button>
          <Button
            onClick={handleContinue}
            disabled={isSaving || (representanteUnico && !motivoRepresentanteUnico)}
          >
            {locale === 'es' ? 'Continuar' : locale === 'fr' ? 'Continuer' : 'Continue'}
            <ChevronRight className="h-4 w-4 ml-1" />
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

// =============================================================================
// STEP: Form Review Representantes (for minors only - shows cross-validation)
// =============================================================================

interface FormReviewRepresentantesStepProps {
  locale: string
  formData: Record<string, unknown> | null
  documentPreviews: Record<string, DocumentExtractionPreview>
  onNext: () => void
  onBack: () => void
  isSaving: boolean
  saveError: string | null
}

function FormReviewRepresentantesStep({
  locale,
  formData,
  documentPreviews,
  onNext,
  onBack,
  isSaving,
  saveError,
}: FormReviewRepresentantesStepProps) {
  // Get parental authorization validation results from formData
  const parentalValidation = formData?.parental_authorization_validation as {
    cross_validation_passed?: boolean
    blocking_errors?: Array<{
      code: string
      field: string
      message_es?: string
      message_fr?: string
      message_en?: string
    }>
    validation_details?: {
      representante_1?: { validated: boolean; match: boolean | null; auth_value?: string; doc_value?: string }
      representante_2?: { validated: boolean; match: boolean | null; auth_value?: string; doc_value?: string }
    }
  } | null

  const isRepresentanteUnico = formData?.representante_unico as boolean ?? false
  const crossValidationPassed = parentalValidation?.cross_validation_passed ?? true
  const blockingErrors = parentalValidation?.blocking_errors ?? []

  // Get representative data from authorization preview
  const authPreview = documentPreviews['autorizacion_parental']
  const rep1Preview = documentPreviews['documento_representante_1']
  const rep2Preview = documentPreviews['documento_representante_2']

  const rep1Data = authPreview?.extraction?.representante_1 as Record<string, unknown> | undefined
  const rep2Data = authPreview?.extraction?.representante_2 as Record<string, unknown> | undefined

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          {locale === 'es' ? 'Verificar Representantes Legales' : locale === 'fr' ? 'Vérifier les Représentants Légaux' : 'Verify Legal Representatives'}
        </CardTitle>
        <CardDescription>
          {locale === 'es'
            ? 'Revise los datos extraídos de la autorización parental y los documentos de identidad'
            : locale === 'fr'
              ? 'Vérifiez les données extraites de l\'autorisation parentale et des documents d\'identité'
              : 'Review the data extracted from parental authorization and identity documents'}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Cross-validation status */}
        <div className={`p-4 rounded-lg ${crossValidationPassed ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'}`}>
          <div className="flex items-center gap-2">
            {crossValidationPassed ? (
              <CheckCircle className="h-5 w-5 text-green-600" />
            ) : (
              <AlertCircle className="h-5 w-5 text-red-600" />
            )}
            <span className={`font-medium ${crossValidationPassed ? 'text-green-800' : 'text-red-800'}`}>
              {locale === 'es'
                ? crossValidationPassed ? 'Validación cruzada exitosa' : 'Error en validación cruzada'
                : locale === 'fr'
                  ? crossValidationPassed ? 'Validation croisée réussie' : 'Erreur de validation croisée'
                  : crossValidationPassed ? 'Cross-validation passed' : 'Cross-validation failed'}
            </span>
          </div>

          {/* Show blocking errors */}
          {blockingErrors.length > 0 && (
            <div className="mt-3 space-y-2">
              {blockingErrors.map((error, idx) => (
                <div key={idx} className="text-sm text-red-700">
                  • {locale === 'es' ? error.message_es : locale === 'fr' ? error.message_fr : error.message_en}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Representante 1 */}
        <div className="border rounded-lg p-4">
          <h4 className="font-medium mb-3">
            {locale === 'es' ? 'Representante 1' : locale === 'fr' ? 'Représentant 1' : 'Representative 1'}
          </h4>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-muted-foreground">{locale === 'es' ? 'Nombre' : 'Name'}:</span>
              <span className="ml-2 font-medium">{rep1Data?.nombre_completo as string || '-'}</span>
            </div>
            <div>
              <span className="text-muted-foreground">{locale === 'es' ? 'Tipo documento' : 'Doc type'}:</span>
              <span className="ml-2 font-medium">{rep1Data?.documento_tipo as string || '-'}</span>
            </div>
            <div className="col-span-2">
              <span className="text-muted-foreground">{locale === 'es' ? 'N° Documento (autorización)' : 'Doc # (authorization)'}:</span>
              <span className="ml-2 font-mono">{rep1Data?.documento_numero as string || '-'}</span>
            </div>
            {rep1Preview && (
              <div className="col-span-2">
                <span className="text-muted-foreground">{locale === 'es' ? 'N° Documento (subido)' : 'Doc # (uploaded)'}:</span>
                <span className="ml-2 font-mono">
                  {((rep1Preview.extraction?.documento as Record<string, unknown>)?.numero_dip ||
                    (rep1Preview.extraction?.documento as Record<string, unknown>)?.numero_nie ||
                    rep1Preview.extraction?.numero_documento) as string || '-'}
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Representante 2 (only if not representante_unico) */}
        {!isRepresentanteUnico && (
          <div className="border rounded-lg p-4">
            <h4 className="font-medium mb-3">
              {locale === 'es' ? 'Representante 2' : locale === 'fr' ? 'Représentant 2' : 'Representative 2'}
            </h4>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="text-muted-foreground">{locale === 'es' ? 'Nombre' : 'Name'}:</span>
                <span className="ml-2 font-medium">{rep2Data?.nombre_completo as string || '-'}</span>
              </div>
              <div>
                <span className="text-muted-foreground">{locale === 'es' ? 'Tipo documento' : 'Doc type'}:</span>
                <span className="ml-2 font-medium">{rep2Data?.documento_tipo as string || '-'}</span>
              </div>
              <div className="col-span-2">
                <span className="text-muted-foreground">{locale === 'es' ? 'N° Documento (autorización)' : 'Doc # (authorization)'}:</span>
                <span className="ml-2 font-mono">{rep2Data?.documento_numero as string || '-'}</span>
              </div>
              {rep2Preview && (
                <div className="col-span-2">
                  <span className="text-muted-foreground">{locale === 'es' ? 'N° Documento (subido)' : 'Doc # (uploaded)'}:</span>
                  <span className="ml-2 font-mono">
                    {((rep2Preview.extraction?.documento as Record<string, unknown>)?.numero_dip ||
                      (rep2Preview.extraction?.documento as Record<string, unknown>)?.numero_nie ||
                      rep2Preview.extraction?.numero_documento) as string || '-'}
                  </span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Save error display */}
        {saveError && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{saveError}</AlertDescription>
          </Alert>
        )}

        {/* Navigation buttons */}
        <div className="flex justify-between pt-4">
          <Button variant="outline" onClick={onBack} disabled={isSaving}>
            <ChevronLeft className="h-4 w-4 mr-1" />
            {locale === 'es' ? 'Anterior' : locale === 'fr' ? 'Précédent' : 'Back'}
          </Button>
          <Button
            onClick={onNext}
            disabled={isSaving || !crossValidationPassed}
          >
            {locale === 'es' ? 'Continuar' : locale === 'fr' ? 'Continuer' : 'Continue'}
            <ChevronRight className="h-4 w-4 ml-1" />
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

