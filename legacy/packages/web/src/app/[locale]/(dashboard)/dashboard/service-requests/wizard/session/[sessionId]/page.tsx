'use client'

/**
 * Session-Based Wizard Page - Cache-First Architecture
 *
 * This wizard stores ALL data in Redis cache (30 min TTL).
 * No database writes occur until the user initiates payment.
 *
 * Steps:
 * 1. Upload documents (preview + confirm)
 * 2. Form review (N pages, dynamic)
 * 3. Payment preparation (validate + tariff)
 * 4. Confirmation (persist to DB)
 *
 * @since v2.0 - Cache-first wizard migration
 * @see .claude/plans/CACHE_FIRST_WIZARD_MIGRATION_PLAN.md
 */

import { useState, useEffect, useCallback, useMemo } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { useTranslations } from 'next-intl'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import {
  ArrowLeft,
  ArrowRight,
  Loader2,
  AlertCircle,
  CheckCircle,
  Upload,
  FileText,
  CreditCard,
  Calendar,
  RefreshCw,
  ListChecks,
  Stamp,
  Smartphone,
  Banknote,
  Clock,
  Download,
  Printer,
  ChevronDown,
  MapPin,
} from 'lucide-react'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Checkbox } from '@/components/ui/checkbox'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Label } from '@/components/ui/label'
import {
  useWizardSession,
  useWorkflow,
  SessionTimer,
  IdentityMismatchBlocker,
  DocumentUploader,
  AppointmentSelection,
  SiteSelection,
  DynamicFormRenderer,
  useSessionFormConfig,
  usePrefetchSessionFormConfig,
  validateFormConfig,
  ExtractionStatus,
} from '@/modules/service-requests'
import type {
  DocumentRequirement,
  ServiceRequestDocument,
} from '@/modules/service-requests'
import type { IdentityMismatch } from '@/modules/service-requests/components/IdentityMismatchBlocker'
import type {
  DocumentPreview,
  PreparePaymentResult,
  RequiredDocument,
  InitiatePaymentResult,
} from '@/modules/service-requests/types/wizard-session'
import { wizardSessionApi } from '@/modules/service-requests/services/wizard-session-api'
import { serviceRequestsApi } from '@/modules/service-requests/services/api'
import { getLocalizedField } from '@/core/utils/i18n-helpers'
import { useWorkflowTranslations, stepTitleKey, optionLabelKey, optionDescKey, workflowNameKey } from '@/hooks/use-workflow-translations'
import type { CitizenSummaryResponse } from '@/modules/service-requests/types'
import { useLocationsByEntity } from '@/modules/entity-locations/hooks'

// ============================================================================
// WIZARD STEPS (computed from session state)
// ============================================================================

interface WizardStepDef {
  id: string
  type: string
  titleEs: string
  titleFr: string
  titleEn: string
  icon: React.ElementType
}

// Step type → icon mapping
const STEP_TYPE_ICONS: Record<string, React.ElementType> = {
  selection: ListChecks,
  document_upload: Upload,
  form_review: FileText,
  payment: CreditCard,
  appointment: Calendar,
  site_selection: MapPin,
  confirmation: CheckCircle,
  validation: FileText,
  custom: Stamp,
}

/**
 * Step types that the wizard can render.
 * Steps with types not in this set are skipped (e.g., stamp_payment
 * is type "payment" but step_id starts with "stamp" — its cost is
 * shown in the tariff breakdown of the main payment step).
 */
const RENDERABLE_STEP_TYPES = new Set([
  'selection', 'document_upload', 'form_review', 'payment', 'appointment', 'site_selection', 'confirmation', 'custom',
])

// ============================================================================
// ADAPTER FUNCTIONS: Session types → Legacy types (for DocumentUploader)
// ============================================================================

function toDocumentRequirement(doc: RequiredDocument): DocumentRequirement {
  return {
    documentCode: doc.code,
    documentNameEs: doc.nameEs,
    isRequired: doc.isRequired,
    displayOrder: 0,
    conditionType: 'always' as DocumentRequirement['conditionType'],
    acceptedFormats: ['pdf', 'jpg', 'jpeg', 'png', 'webp'],
  }
}

function toServiceRequestDocument(
  doc: RequiredDocument,
  preview: DocumentPreview
): ServiceRequestDocument {
  const ext = preview.fileName.split('.').pop()?.toLowerCase() || ''
  const mimeMap: Record<string, string> = {
    pdf: 'application/pdf',
    jpg: 'image/jpeg',
    jpeg: 'image/jpeg',
    png: 'image/png',
    webp: 'image/webp',
  }
  return {
    id: `cache-${preview.documentCode}`,
    requestId: preview.sessionId,
    documentCode: preview.documentCode,
    documentNameEs: doc.nameEs,
    fileName: preview.fileName,
    fileUrl: '', // Not available in cache-first mode
    fileSize: preview.fileSize,
    mimeType: mimeMap[ext] || 'application/octet-stream',
    extractionStatus: ExtractionStatus.COMPLETED,
    extractedData: preview.extraction,
    extractionConfidence: preview.confidence,
    uploadedAt: new Date().toISOString(),
  }
}

// ============================================================================
// PAGE COMPONENT
// ============================================================================

export default function SessionWizardPage() {
  const params = useParams()
  const router = useRouter()
  const locale = (params.locale as string) || 'es'
  const sessionId = params.sessionId as string
  const t = useTranslations('service_requests')

  // Wizard session hook
  const {
    session,
    isLoading,
    isSaving,
    error,
    isDocumentUploading,
    timeRemaining,
    isExpiring,
    isExpired,
    loadSession,
    cancelSession,
    previewDocument,
    confirmDocument,
    deleteDocument,
    linkVaultDocument,
    saveFormData,
    preparePayment,
    initiatePayment,
    clearError,
  } = useWizardSession()

  // Local state
  const [currentStepIndex, setCurrentStepIndex] = useState(0)
  const [documentPreviews, setDocumentPreviews] = useState<
    Record<string, DocumentPreview>
  >({})
  const [formValues, setFormValues] = useState<Record<string, unknown>>({})
  const [paymentResult, setPaymentResult] =
    useState<PreparePaymentResult | null>(null)
  const [persistedRequestId, setPersistedRequestId] = useState<string | null>(null)

  // Manual payment confirmation (cash/check) — shown before appointment
  const [manualPaymentResult, setManualPaymentResult] = useState<InitiatePaymentResult | null>(null)

  // Payment method selection state
  const [selectedPaymentMethod, setSelectedPaymentMethod] = useState<string | null>(null)
  const [paymentPhone, setPaymentPhone] = useState('')
  const [isPaymentProcessing, setIsPaymentProcessing] = useState(false)
  const [paymentError, setPaymentError] = useState<string | null>(null)
  const [treasuryLocationId, setTreasuryLocationId] = useState<string | null>(null)

  // Treasury location selector for cash/check payments
  const isManualPayment = selectedPaymentMethod === 'cash' || selectedPaymentMethod === 'check'
  const { data: treasuryLocations } = useLocationsByEntity('TESORO', isManualPayment)

  // Auto-select treasury location matching citizen's city
  useEffect(() => {
    if (!treasuryLocations?.length || treasuryLocationId) return
    const citizenCity = session?.appointmentData?.city || session?.siteSelection?.city
    if (citizenCity) {
      const match = treasuryLocations.find(loc => loc.city === citizenCity)
      if (match) setTreasuryLocationId(match.id)
    }
    // If no city match, default to first location
    if (!treasuryLocationId && treasuryLocations.length === 1) {
      setTreasuryLocationId(treasuryLocations[0].id)
    }
  }, [treasuryLocations, treasuryLocationId, session?.appointmentData?.city, session?.siteSelection?.city])

  // Identity mismatch blocker state
  const [identityMismatches, setIdentityMismatches] = useState<IdentityMismatch[]>([])
  const [showMismatchBlocker, setShowMismatchBlocker] = useState(false)
  const [hasBlockingMismatches, setHasBlockingMismatches] = useState(false)

  // Form validation state
  const [formErrors, setFormErrors] = useState<Record<string, string>>({})
  const [currentFormConfig, setCurrentFormConfig] = useState<import('@/modules/service-requests').FormConfig | null>(null)

  // Fetch workflow config to get step definitions dynamically
  const { data: workflowConfig, isLoading: isLoadingWorkflow } = useWorkflow(session?.workflowCode || '', {
    enabled: !!session?.workflowCode,
  })

  // Workflow translations (step titles, option labels from translations table)
  const { tw } = useWorkflowTranslations()

  // Load session on mount
  useEffect(() => {
    if (sessionId) {
      loadSession(sessionId)
    }
  }, [sessionId, loadSession])

  // Redirect BUNDLE_PAYMENT to its dedicated wizard page
  useEffect(() => {
    if (session?.workflowCode === 'BUNDLE_PAYMENT') {
      router.replace(`/${locale}/dashboard/bundle-payment/${sessionId}`)
    }
  }, [session?.workflowCode, sessionId, locale, router])

  // Restore form data from session when loaded
  useEffect(() => {
    if (session?.formData) {
      setFormValues((prev) => ({ ...prev, ...session.formData }))
    }
  }, [session?.formData])

  // Auto-select default payment method when payment result arrives
  useEffect(() => {
    if (paymentResult?.defaultPaymentMethod && !selectedPaymentMethod) {
      setSelectedPaymentMethod(paymentResult.defaultPaymentMethod)
    }
  }, [paymentResult?.defaultPaymentMethod, selectedPaymentMethod])

  // Build wizard steps dynamically from backend workflow config.
  // Filter to renderable types, skip stamp_payment, and evaluate step-level conditions.
  const steps = useMemo((): WizardStepDef[] => {
    if (!workflowConfig?.steps || workflowConfig.steps.length === 0) {
      // Loading guard shows spinner until workflowConfig is available,
      // so this only triggers if the backend returns 0 steps (bug).
      return []
    }

    const filtered: WizardStepDef[] = workflowConfig.steps
      .filter((s) => {
        // Only keep steps with renderable types
        if (!RENDERABLE_STEP_TYPES.has(s.stepType)) return false
        // Skip stamp_payment — its cost appears in the tariff breakdown
        if (s.stepId.startsWith('stamp')) return false

        // Evaluate step-level condition (config.condition)
        // If condition is set, ALL condition keys must match current formValues
        const cfg = s.config as Record<string, unknown> | undefined
        const condition = cfg?.condition as Record<string, unknown> | undefined
        if (condition) {
          for (const [key, expected] of Object.entries(condition)) {
            const actual = formValues[key]
            // Compare with type coercion (backend may send boolean, form stores string)
            if (String(actual ?? '') !== String(expected)) {
              return false
            }
          }
        }

        return true
      })
      .map((s) => {
        // Translate step title via workflow translations table (workflow.step.{normalized_key})
        const rawTitle = s.titleEs || s.stepId
        const title = tw(stepTitleKey(rawTitle), rawTitle)
        return {
          id: s.stepId,
          type: s.stepType as string,
          titleEs: title,
          titleFr: title,
          titleEn: title,
          icon: STEP_TYPE_ICONS[s.stepType] || FileText,
        }
      })

    // Inject site_selection step for non-appointment workflows.
    // Appointment workflows already handle site selection inside AppointmentSelection.
    const hasAppointmentStep = filtered.some(s => s.type === 'appointment')
    const hasSiteSelectionStep = filtered.some(s => s.type === 'site_selection')

    if (!hasAppointmentStep && !hasSiteSelectionStep) {
      // Insert before payment step
      const paymentIdx = filtered.findIndex(s => s.type === 'payment')
      const insertIdx = paymentIdx >= 0 ? paymentIdx : filtered.length
      filtered.splice(insertIdx, 0, {
        id: 'site_selection',
        type: 'site_selection',
        titleEs: 'Sitio de tramitacion',
        titleFr: 'Site de traitement',
        titleEn: 'Processing site',
        icon: STEP_TYPE_ICONS['site_selection'] || MapPin,
      })
    }

    return filtered
  }, [workflowConfig, formValues, tw, locale])

  // Clamp step index if steps list shrinks (e.g., condition no longer met)
  const safeStepIndex = Math.min(currentStepIndex, Math.max(0, steps.length - 1))
  useEffect(() => {
    if (safeStepIndex !== currentStepIndex) {
      setCurrentStepIndex(safeStepIndex)
    }
  }, [safeStepIndex, currentStepIndex])

  const currentStep = steps[safeStepIndex]
  const progressPercent =
    steps.length > 0
      ? Math.round(((safeStepIndex + 1) / steps.length) * 100)
      : 0

  const getStepTitle = (step: WizardStepDef): string =>
    locale === 'es'
      ? step.titleEs
      : locale === 'fr'
        ? step.titleFr
        : step.titleEn

  // ========================================================================
  // NAVIGATION
  // ========================================================================

  const canGoNext = useCallback((): boolean => {
    if (!session || !currentStep) return false

    const stepType = currentStep.type

    if (stepType === 'selection') {
      const stepConfig = workflowConfig?.steps?.find(s => s.stepId === currentStep.id)
      const cfg = stepConfig?.config as Record<string, unknown> | undefined
      if (!cfg) return true

      // Format A (Residencia/TramitesVisado): config.sections[].fields[].key
      // Filter by show_when conditions: only visible sections require their fields
      const sections = cfg.sections as Array<{
        fields: Array<{ key: string; required?: boolean }>
        show_when?: Record<string, string>
      }> | undefined
      if (sections) {
        const visibleSections = sections.filter(s => {
          if (!s.show_when) return true
          return Object.entries(s.show_when).every(
            ([k, v]) => String(formValues[k] ?? '') === String(v)
          )
        })
        const requiredKeys = visibleSections.flatMap(s => s.fields.filter(f => f.required !== false).map(f => f.key))
        return requiredKeys.every(key => formValues[key] !== undefined && formValues[key] !== '')
      }

      // Format B (all other workflows): config.selection_type + config.options
      const selectionType = cfg.selection_type as string | undefined
      if (selectionType && cfg.options) {
        const val = formValues[selectionType]
        return val !== undefined && val !== '' && val !== null
      }

      return true
    }

    if (stepType === 'custom') {
      // multi_selection: at least one option must be selected
      const stepConfig = workflowConfig?.steps?.find(s => s.stepId === currentStep.id)
      const cfg = stepConfig?.config as Record<string, unknown> | undefined
      if (cfg?.type === 'multi_selection') {
        const selected = formValues[currentStep.id] as string[] | undefined
        return Array.isArray(selected) && selected.length > 0
      }
      return true
    }

    if (stepType === 'document_upload') {
      // Block if identity mismatches are blocking
      if (hasBlockingMismatches) return false
      // Block if minor cross-validation failed
      if (session.isMinor) {
        const crossValFailed = Object.values(documentPreviews).some((p) => {
          const ra = p.riskAnalysis as Record<string, unknown> | null
          const crossVal = (ra?.parental_authorization_validation || ra?.parentalAuthorizationValidation) as Record<string, unknown> | undefined
          return crossVal && (crossVal.cross_validation_passed === false || crossVal.crossValidationPassed === false)
        })
        if (crossValFailed) return false
      }
      // All required documents must be uploaded
      const required = session.requiredDocuments.filter((d) => d.isRequired)
      return required.every((d) => d.uploaded)
    }

    if (stepType === 'form_review') {
      return true // Form can always proceed (validation on payment step)
    }

    if (stepType === 'payment') {
      return paymentResult?.readyForPayment === true
    }

    return true
  }, [session, currentStep, paymentResult, hasBlockingMismatches, formValues, workflowConfig, documentPreviews])

  // ========================================================================
  // INITIATE PAYMENT (atomic: persist + pay in one call)
  // ========================================================================

  const handleInitiatePayment = useCallback(async () => {
    if (!selectedPaymentMethod || !paymentResult?.readyForPayment) return
    // Mobile money requires phone number
    if (selectedPaymentMethod === 'mobile_money' && !paymentPhone.trim()) return

    setIsPaymentProcessing(true)
    setPaymentError(null)

    try {
      // Single atomic call: persist session + initiate payment
      const result = await initiatePayment(
        selectedPaymentMethod,
        selectedPaymentMethod === 'mobile_money' ? paymentPhone.trim() : undefined,
        isManualPayment ? (treasuryLocationId ?? undefined) : undefined
      )

      if (!result?.success) {
        const errorMsg = result?.error ||
          (locale === 'es'
            ? 'Error al procesar el pago. Intente de nuevo.'
            : locale === 'fr'
              ? 'Erreur lors du traitement du paiement. Reessayez.'
              : 'Error processing payment. Please try again.')

        // Appointment slot taken → go back to appointment step
        if (errorMsg.includes('ya no está disponible') || errorMsg.includes('APPOINTMENT_SLOT_TAKEN')) {
          setPaymentError(locale === 'es'
            ? 'El horario seleccionado ya no está disponible. Seleccione otro horario.'
            : locale === 'fr'
              ? 'Le créneau sélectionné n\'est plus disponible. Veuillez en choisir un autre.'
              : 'The selected time slot is no longer available. Please select another.')
          const apptStepIdx = steps.findIndex(s => s.type === 'appointment')
          if (apptStepIdx >= 0) setCurrentStepIndex(apptStepIdx)
          return
        }

        // Site selection missing → go back to site_selection step
        if (errorMsg.includes('sitio de tramitacion') || errorMsg.includes('MISSING_SITE_SELECTION') || errorMsg.includes('INVALID_SITE_SELECTION')) {
          setPaymentError(locale === 'es'
            ? 'Debe seleccionar un sitio de tramitación antes de continuar.'
            : locale === 'fr'
              ? 'Vous devez sélectionner un site de traitement avant de continuer.'
              : 'You must select a processing site before continuing.')
          const siteStepIdx = steps.findIndex(s => s.type === 'site_selection')
          if (siteStepIdx >= 0) setCurrentStepIndex(siteStepIdx)
          return
        }

        setPaymentError(errorMsg)
        return
      }

      // Store the persisted request ID and payment result for confirmation step
      if (result.serviceRequestId) {
        setPersistedRequestId(result.serviceRequestId)
        setManualPaymentResult(result)
      }

      // 1. BANGE electronic payment - redirect to gateway
      if (result.redirectUrl) {
        window.location.href = result.redirectUrl
        return
      }

      // 2. ALL other flows (manual + completed) → advance to confirmation step
      const confirmIdx = steps.findIndex(s => s.type === 'confirmation')
      if (confirmIdx >= 0) {
        setCurrentStepIndex(confirmIdx)
      } else {
        // Fallback: no confirmation step → redirect to detail
        if (result.serviceRequestId) {
          router.push(`/${locale}/dashboard/service-requests/${result.serviceRequestId}`)
        }
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Unknown error'
      // Slot was taken between selection and payment → go back to appointment step
      if (msg.includes('ya no está disponible') || msg.includes('APPOINTMENT_SLOT_TAKEN')) {
        setPaymentError(locale === 'es'
          ? 'El horario seleccionado ya no está disponible. Seleccione otro horario.'
          : locale === 'fr'
            ? 'Le créneau sélectionné n\'est plus disponible. Veuillez en choisir un autre.'
            : 'The selected time slot is no longer available. Please select another.')
        const apptStepIdx = steps.findIndex(s => s.type === 'appointment')
        if (apptStepIdx >= 0) setCurrentStepIndex(apptStepIdx)
        return
      }
      // Site selection missing → go back to site_selection step
      if (msg.includes('sitio de tramitacion') || msg.includes('MISSING_SITE_SELECTION') || msg.includes('INVALID_SITE_SELECTION')) {
        setPaymentError(locale === 'es'
          ? 'Debe seleccionar un sitio de tramitación antes de continuar.'
          : locale === 'fr'
            ? 'Vous devez sélectionner un site de traitement avant de continuer.'
            : 'You must select a processing site before continuing.')
        const siteStepIdx = steps.findIndex(s => s.type === 'site_selection')
        if (siteStepIdx >= 0) setCurrentStepIndex(siteStepIdx)
        return
      }
      setPaymentError(msg)
      console.error('[WizardSession] Payment error:', msg)
    } finally {
      setIsPaymentProcessing(false)
    }
  }, [
    selectedPaymentMethod,
    paymentPhone,
    paymentResult,
    initiatePayment,
    router,
    locale,
    steps,
    isManualPayment,
    treasuryLocationId,
  ])

  const handleNext = useCallback(async () => {
    if (!session || !currentStep) return

    // Save selection/custom data before advancing
    if (currentStep.type === 'selection' || currentStep.type === 'custom') {
      const success = await saveFormData({
        form_data: formValues,
        step_id: currentStep.id,
      })
      if (!success) return
    }

    // Validate and save form data before advancing from form review steps
    if (currentStep.type === 'form_review') {
      // Validate required fields if form config is loaded
      if (currentFormConfig) {
        const errors = validateFormConfig(
          currentFormConfig,
          formValues,
          locale as 'es' | 'fr' | 'en'
        )
        if (Object.keys(errors).length > 0) {
          setFormErrors(errors)
          return
        }
        setFormErrors({})
      }

      const success = await saveFormData({
        form_data: formValues,
        step_id: currentStep.id,
      })
      if (!success) return
    }

    // Auto-prepare payment when entering payment step
    if (
      currentStepIndex + 1 < steps.length &&
      steps[currentStepIndex + 1].type === 'payment'
    ) {
      const result = await preparePayment()
      setPaymentResult(result)
    }

    if (currentStepIndex < steps.length - 1) {
      setCurrentStepIndex((prev) => prev + 1)
    }
  }, [
    session,
    currentStep,
    currentStepIndex,
    steps,
    formValues,
    saveFormData,
    preparePayment,
    currentFormConfig,
    locale,
  ])

  const handleBack = useCallback(() => {
    if (currentStepIndex > 0) {
      setCurrentStepIndex((prev) => prev - 1)
    }
  }, [currentStepIndex])

  const handleCancel = useCallback(async () => {
    if (
      window.confirm(
        locale === 'es'
          ? 'Esta seguro de cancelar? Se perderan todos los datos.'
          : locale === 'fr'
            ? 'Etes-vous sur de vouloir annuler ? Toutes les donnees seront perdues.'
            : 'Are you sure you want to cancel? All data will be lost.'
      )
    ) {
      await cancelSession('User cancelled')
      router.push(`/${locale}/dashboard/service-requests`)
    }
  }, [locale, cancelSession, router])

  // ========================================================================
  // DOCUMENT UPLOAD HANDLERS
  // ========================================================================

  const handleDocumentUpload = useCallback(
    async (documentCode: string, file: File) => {
      const preview = await previewDocument(documentCode, file)
      if (preview) {
        // Store raw preview
        setDocumentPreviews((prev) => ({
          ...prev,
          [documentCode]: preview,
        }))

        // Check for identity mismatches in risk analysis
        const ra = preview.riskAnalysis as Record<string, unknown> | null
        if (ra) {
          const mismatches = (ra.identity_mismatches || ra.identityMismatches) as IdentityMismatch[] | undefined
          if (mismatches && mismatches.length > 0) {
            setIdentityMismatches(mismatches)
            const blocking = (ra.has_blocking_mismatches as boolean) ||
              (ra.hasBlockingMismatches as boolean) ||
              mismatches.some(m => m.is_blocking)
            setHasBlockingMismatches(blocking)
            if (blocking) {
              setShowMismatchBlocker(true)
              return // Show blocker instead of auto-confirming
            }
          }
        }

        // Auto-confirm: store extraction data as-is (user edits in form_review step)
        await confirmDocument({
          document_code: documentCode,
          confirmed_data: (preview.extraction || {}) as Record<string, unknown>,
          user_notes: null,
        })
      }
    },
    [previewDocument, confirmDocument]
  )

  // Handle delete document
  const handleDeleteDocument = useCallback(
    async (documentCode: string) => {
      const success = await deleteDocument(documentCode)
      if (success) {
        // Clear local preview state
        setDocumentPreviews((prev) => {
          const next = { ...prev }
          delete next[documentCode]
          return next
        })
      }
    },
    [deleteDocument]
  )

  // Handle select from vault (Phase 2)
  const handleSelectFromVault = useCallback(
    async (documentCode: string, vaultDocumentId: string, _documentName: string) => {
      const success = await linkVaultDocument(documentCode, vaultDocumentId)
      if (success) {
        // Mark as uploaded in local previews
        setDocumentPreviews((prev) => ({
          ...prev,
          [documentCode]: {
            fileName: _documentName,
            fileSize: 0,
            extraction: {},
            confidence: 1.0,
            processor: 'vault_reuse',
            extractionStatus: 'completed',
            needsCorrection: false,
            riskAnalysis: null,
            crossValidation: null,
            expiresAt: '',
            ttlSeconds: 0,
          } as DocumentPreview,
        }))
      }
    },
    [linkVaultDocument]
  )

  // Handle go back from mismatch blocker
  const handleMismatchBlockerBack = useCallback(() => {
    setShowMismatchBlocker(false)
    setIdentityMismatches([])
    setHasBlockingMismatches(false)
  }, [])

  // Handle re-upload from mismatch blocker
  const handleReuploadFromBlocker = useCallback((_documentCode: string) => {
    setShowMismatchBlocker(false)
    setIdentityMismatches([])
    setHasBlockingMismatches(false)
    // User will re-upload via DocumentUploader card (drag-drop or click)
  }, [])

  // ========================================================================
  // FORM CHANGE HANDLER
  // ========================================================================

  const handleFormChange = useCallback((key: string, value: unknown) => {
    setFormValues((prev) => ({ ...prev, [key]: value }))
  }, [])

  // ========================================================================
  // RENDER HELPERS
  // ========================================================================

  // Loading state — wait for both session AND workflow config before rendering steps.
  if ((isLoading && !session) || (session && isLoadingWorkflow)) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin mx-auto mb-4 text-primary" />
          <p className="text-muted-foreground">{t('loading')}</p>
        </div>
      </div>
    )
  }

  // Expired session
  if (isExpired) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Card className="max-w-md w-full">
          <CardHeader className="text-center">
            <AlertCircle className="h-12 w-12 mx-auto mb-4 text-destructive" />
            <CardTitle>
              {locale === 'es'
                ? 'Sesion expirada'
                : locale === 'fr'
                  ? 'Session expiree'
                  : 'Session expired'}
            </CardTitle>
            <CardDescription>
              {locale === 'es'
                ? 'Tu sesion ha expirado. Por favor, inicia una nueva solicitud.'
                : locale === 'fr'
                  ? 'Votre session a expire. Veuillez recommencer.'
                  : 'Your session has expired. Please start a new request.'}
            </CardDescription>
          </CardHeader>
          <CardContent className="flex justify-center">
            <Button
              onClick={() =>
                router.push(`/${locale}/dashboard/service-requests/new`)
              }
            >
              {locale === 'es'
                ? 'Nueva solicitud'
                : locale === 'fr'
                  ? 'Nouvelle demande'
                  : 'New request'}
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  // Error state (no session loaded)
  if (error && !session) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Card className="max-w-md w-full">
          <CardHeader className="text-center">
            <AlertCircle className="h-12 w-12 mx-auto mb-4 text-destructive" />
            <CardTitle>{t('error')}</CardTitle>
            <CardDescription>{error}</CardDescription>
          </CardHeader>
          <CardContent className="flex gap-2 justify-center">
            <Button
              variant="outline"
              onClick={() => {
                clearError()
                loadSession(sessionId)
              }}
            >
              <RefreshCw className="mr-2 h-4 w-4" />
              {t('retry')}
            </Button>
            <Button
              variant="ghost"
              onClick={() =>
                router.push(`/${locale}/dashboard/service-requests/new`)
              }
            >
              {locale === 'es'
                ? 'Volver'
                : locale === 'fr'
                  ? 'Retour'
                  : 'Back'}
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (!session) return null

  // No renderable steps — backend returned empty config or all steps filtered out
  if (steps.length === 0 || !currentStep) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Card className="max-w-md w-full">
          <CardHeader className="text-center">
            <AlertCircle className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
            <CardTitle>
              {locale === 'es'
                ? 'Configuracion no disponible'
                : locale === 'fr'
                  ? 'Configuration indisponible'
                  : 'Configuration unavailable'}
            </CardTitle>
            <CardDescription>
              {locale === 'es'
                ? 'No se pudo cargar la configuracion del tramite. Intenta de nuevo.'
                : locale === 'fr'
                  ? 'Impossible de charger la configuration. Veuillez reessayer.'
                  : 'Could not load the workflow configuration. Please try again.'}
            </CardDescription>
          </CardHeader>
          <CardContent className="flex gap-2 justify-center">
            <Button
              variant="outline"
              onClick={() => loadSession(sessionId)}
            >
              <RefreshCw className="mr-2 h-4 w-4" />
              {locale === 'es' ? 'Reintentar' : locale === 'fr' ? 'Reessayer' : 'Retry'}
            </Button>
            <Button
              variant="ghost"
              onClick={() => router.push(`/${locale}/dashboard/service-requests/new`)}
            >
              {locale === 'es' ? 'Volver' : locale === 'fr' ? 'Retour' : 'Back'}
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      {/* Header with timer */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={handleCancel}
            className="text-muted-foreground"
          >
            <ArrowLeft className="mr-2 h-4 w-4" />
            {t('cancel')}
          </Button>
          <div>
            <h1 className="text-xl font-bold">
              {tw(workflowNameKey(session.workflowCode), session.workflowCode.replace(/_/g, ' '))}
            </h1>
            <p className="text-sm text-muted-foreground">
              {session.subType || session.solicitudType}
              {session.motivo && ` - ${session.motivo}`}
            </p>
          </div>
        </div>

        <SessionTimer
          timeRemaining={timeRemaining}
          isExpiring={isExpiring}
          isExpired={isExpired}
          locale={locale as 'es' | 'fr' | 'en'}
        />
      </div>

      {/* Progress bar */}
      <div className="space-y-2">
        <div className="flex items-center justify-between text-sm">
          <span className="font-medium">{getStepTitle(currentStep)}</span>
          <span className="text-muted-foreground">
            {currentStepIndex + 1} / {steps.length}
          </span>
        </div>
        <Progress value={progressPercent} className="h-2" />

        {/* Step indicators */}
        <div className="flex gap-1">
          {steps.map((step, idx) => {
            const StepIcon = step.icon
            return (
              <div
                key={step.id}
                className={`flex items-center gap-1 px-2 py-1 rounded-full text-xs ${
                  idx === currentStepIndex
                    ? 'bg-primary text-primary-foreground'
                    : idx < currentStepIndex
                      ? 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300'
                      : 'bg-muted text-muted-foreground'
                }`}
              >
                <StepIcon className="h-3 w-3" />
                <span className="hidden sm:inline">
                  {getStepTitle(step)}
                </span>
              </div>
            )
          })}
        </div>
      </div>

      {/* Error banner with retry */}
      {error && (
        <Alert variant="destructive" className="flex items-start justify-between">
          <div className="flex items-start gap-2">
            <AlertCircle className="h-4 w-4 mt-0.5" />
            <AlertDescription>
              <p>{error}</p>
              <div className="flex gap-2 mt-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    clearError()
                    loadSession(sessionId)
                  }}
                  className="h-7 text-xs"
                >
                  <RefreshCw className="mr-1 h-3 w-3" />
                  {locale === 'es' ? 'Reintentar' : locale === 'fr' ? 'Reessayer' : 'Retry'}
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={clearError}
                  className="h-7 text-xs"
                >
                  {locale === 'es' ? 'Cerrar' : locale === 'fr' ? 'Fermer' : 'Close'}
                </Button>
              </div>
            </AlertDescription>
          </div>
        </Alert>
      )}

      {/* Step content */}
      <Card>
        <CardContent className="pt-6">
          {/* ============================================================ */}
          {/* STEP: Selection (persona type, sub_type, etc.)               */}
          {/* ============================================================ */}
          {(currentStep.type === 'selection' || currentStep.type === 'custom') && (
            <SelectionStepRenderer
              currentStep={currentStep}
              workflowConfig={workflowConfig}
              formValues={formValues}
              onFormChange={handleFormChange}
              locale={locale}
              tw={tw}
              workflowCode={session?.workflowCode || ''}
            />
          )}

          {/* ============================================================ */}
          {/* STEP: Upload Documents                                       */}
          {/* ============================================================ */}
          {currentStep.type === 'document_upload' && !showMismatchBlocker && (
            <div className="space-y-4">
              <h2 className="text-lg font-semibold">
                {locale === 'es'
                  ? 'Documentos requeridos'
                  : locale === 'fr'
                    ? 'Documents requis'
                    : 'Required documents'}
              </h2>
              <p className="text-sm text-muted-foreground">
                {locale === 'es'
                  ? 'Sube los documentos necesarios para tu tramite.'
                  : locale === 'fr'
                    ? 'Telechargez les documents necessaires pour votre demarche.'
                    : 'Upload the required documents for your application.'}
              </p>

              {/* Minor flow: parental authorization notice */}
              {session.isMinor && (
                <Alert>
                  <AlertCircle className="h-4 w-4" />
                  <AlertDescription>
                    {locale === 'es'
                      ? 'Tramite para menor de edad. Se requiere autorizacion parental o tutela legal.'
                      : locale === 'fr'
                        ? 'Demarche pour mineur. Une autorisation parentale ou tutelle legale est requise.'
                        : 'Minor application. Parental authorization or legal guardianship is required.'}
                  </AlertDescription>
                </Alert>
              )}

              {/* Minor flow: cross-validation results from parental authorization */}
              {session.isMinor && (() => {
                // Find cross-validation results from uploaded representative document
                const crossValDoc = Object.values(documentPreviews).find((p) => {
                  const ra = p.riskAnalysis as Record<string, unknown> | null
                  return ra?.parental_authorization_validation || ra?.parentalAuthorizationValidation
                })
                if (!crossValDoc) return null
                const ra = crossValDoc.riskAnalysis as Record<string, unknown>
                const crossVal = (ra.parental_authorization_validation || ra.parentalAuthorizationValidation) as Record<string, unknown> | undefined
                if (!crossVal) return null
                const passed = crossVal.cross_validation_passed ?? crossVal.crossValidationPassed
                if (passed === true) {
                  return (
                    <Alert>
                      <CheckCircle className="h-4 w-4 text-green-500" />
                      <AlertDescription className="text-green-700">
                        {locale === 'es'
                          ? 'Validacion de autorizacion parental exitosa.'
                          : locale === 'fr'
                            ? 'Validation de l\'autorisation parentale reussie.'
                            : 'Parental authorization validation successful.'}
                      </AlertDescription>
                    </Alert>
                  )
                }
                if (passed === false) {
                  return (
                    <Alert variant="destructive">
                      <AlertCircle className="h-4 w-4" />
                      <AlertDescription>
                        {locale === 'es'
                          ? 'Error en validacion de autorizacion parental. Verifique los documentos del representante.'
                          : locale === 'fr'
                            ? 'Erreur de validation de l\'autorisation parentale. Verifiez les documents du representant.'
                            : 'Parental authorization validation failed. Check representative documents.'}
                        {Array.isArray(crossVal.errors) && crossVal.errors.length > 0 && (
                          <ul className="list-disc pl-4 mt-1">
                            {(crossVal.errors as string[]).map((err: string, i: number) => (
                              <li key={i}>{String(err)}</li>
                            ))}
                          </ul>
                        )}
                      </AlertDescription>
                    </Alert>
                  )
                }
                return null
              })()}

              {/* Non-blocking identity warnings */}
              {identityMismatches.length > 0 && !hasBlockingMismatches && (
                <Alert>
                  <AlertCircle className="h-4 w-4" />
                  <AlertDescription>
                    {locale === 'es'
                      ? 'Se detectaron diferencias menores entre documentos. Puede continuar, pero verifique los datos.'
                      : locale === 'fr'
                        ? 'Des differences mineures ont ete detectees entre les documents. Vous pouvez continuer, mais verifiez les donnees.'
                        : 'Minor differences were detected between documents. You can continue, but verify the data.'}
                  </AlertDescription>
                </Alert>
              )}

              {session.requiredDocuments.map((doc: RequiredDocument) => {
                const docPreview = documentPreviews[doc.code]
                const uploadedDoc =
                  doc.uploaded && docPreview
                    ? toServiceRequestDocument(doc, docPreview)
                    : undefined

                return (
                  <div key={doc.code} className="space-y-1">
                    <DocumentUploader
                      requirement={toDocumentRequirement(doc)}
                      uploadedDocument={uploadedDoc}
                      locale={locale as 'es' | 'fr' | 'en'}
                      onUpload={(file) => handleDocumentUpload(doc.code, file)}
                      onDelete={doc.uploaded ? () => handleDeleteDocument(doc.code) : undefined}
                      onSelectFromVault={(vaultId, vaultName) =>
                        handleSelectFromVault(doc.code, vaultId, vaultName)
                      }
                      workflowCode={session?.workflowCode}
                      maxSizeMB={doc.code === 'photo_carnet' ? 2 : 5}
                      disabled={isDocumentUploading(doc.code)}
                    />
                    {/* Processor badge for AI-extracted documents */}
                    {doc.uploaded && docPreview && (
                      <div className="flex justify-end gap-2">
                        {docPreview.processor === 'gemini' && (
                          <Badge variant="outline" className="text-xs text-blue-600 border-blue-200">
                            {locale === 'es'
                              ? 'Extraido con IA'
                              : locale === 'fr'
                                ? 'Extrait par IA'
                                : 'AI Extracted'}
                          </Badge>
                        )}
                        {typeof docPreview.confidence === 'number' && docPreview.confidence > 0 && (
                          <Badge variant="outline" className={`text-xs ${docPreview.confidence >= 0.8 ? 'text-green-600 border-green-200' : docPreview.confidence >= 0.6 ? 'text-yellow-600 border-yellow-200' : 'text-red-600 border-red-200'}`}>
                            {Math.round(docPreview.confidence * 100)}%
                          </Badge>
                        )}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}

          {/* Identity Mismatch Blocker - shown when documents have conflicting identity data */}
          {currentStep.type === 'document_upload' && showMismatchBlocker && (
            <IdentityMismatchBlocker
              mismatches={identityMismatches}
              hasBlockingMismatches={hasBlockingMismatches}
              onGoBack={handleMismatchBlockerBack}
              onReuploadDocument={handleReuploadFromBlocker}
            />
          )}

          {/* ============================================================ */}
          {/* STEP: Form Review (Dynamic via DynamicFormRenderer)          */}
          {/* ============================================================ */}
          {currentStep.type === 'form_review' && (
            <SessionDynamicFormReview
              sessionId={sessionId}
              stepId={currentStep.id}
              values={formValues}
              onChange={(key, value) => {
                handleFormChange(key, value)
                // Clear error for the field being edited
                if (formErrors[key]) {
                  setFormErrors((prev) => {
                    const next = { ...prev }
                    delete next[key]
                    return next
                  })
                }
              }}
              locale={locale as 'es' | 'fr' | 'en'}
              errors={formErrors}
              onConfigLoaded={setCurrentFormConfig}
            />
          )}

          {/* ============================================================ */}
          {/* STEP: Payment Preparation                                    */}
          {/* ============================================================ */}
          {currentStep.type === 'payment' && (
            <div className="space-y-4">
              <h2 className="text-lg font-semibold">
                {locale === 'es'
                  ? 'Resumen de pago'
                  : locale === 'fr'
                    ? 'Resume du paiement'
                    : 'Payment Summary'}
              </h2>

              {isLoading && !paymentResult && (
                <div className="flex items-center gap-2 p-4">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span className="text-muted-foreground">
                    {locale === 'es'
                      ? 'Calculando tarifa...'
                      : locale === 'fr'
                        ? 'Calcul du tarif...'
                        : 'Calculating tariff...'}
                  </span>
                </div>
              )}

              {paymentResult && (
                <div className="space-y-4">
                  {/* Tariff breakdown */}
                  <div className="border rounded-lg p-4 space-y-3">
                    <div className="flex justify-between text-sm">
                      <span>
                        {locale === 'es'
                          ? 'Monto base'
                          : locale === 'fr'
                            ? 'Montant de base'
                            : 'Base amount'}
                      </span>
                      <span>
                        {paymentResult.tariff.base_amount.toLocaleString()}{' '}
                        {paymentResult.currency}
                      </span>
                    </div>
                    {paymentResult.tariff.supplements?.map((s, i) => (
                      <div
                        key={i}
                        className="flex justify-between text-sm text-muted-foreground"
                      >
                        <span>{getLocalizedField(s as unknown as Record<string, unknown>, 'label', locale)}</span>
                        <span>
                          {s.amount.toLocaleString()} {paymentResult.currency}
                        </span>
                      </div>
                    ))}
                    <hr />
                    <div className="flex justify-between font-bold text-lg">
                      <span>Total</span>
                      <span>
                        {paymentResult.totalAmount.toLocaleString()}{' '}
                        {paymentResult.currency}
                      </span>
                    </div>
                  </div>

                  {/* Validation errors */}
                  {paymentResult.errors.length > 0 && (
                    <Alert variant="destructive">
                      <AlertCircle className="h-4 w-4" />
                      <AlertDescription>
                        <ul className="list-disc pl-4">
                          {paymentResult.errors.map((e, i) => (
                            <li key={i}>{e.message_es}</li>
                          ))}
                        </ul>
                      </AlertDescription>
                    </Alert>
                  )}

                  {/* Missing documents */}
                  {paymentResult.missingDocuments.length > 0 && (
                    <Alert variant="destructive">
                      <AlertCircle className="h-4 w-4" />
                      <AlertDescription>
                        {locale === 'es'
                          ? 'Documentos faltantes: '
                          : locale === 'fr'
                            ? 'Documents manquants : '
                            : 'Missing documents: '}
                        {paymentResult.missingDocuments.join(', ')}
                      </AlertDescription>
                    </Alert>
                  )}

                  {/* Warnings */}
                  {paymentResult.warnings.length > 0 && (
                    <Alert>
                      <AlertCircle className="h-4 w-4" />
                      <AlertDescription>
                        <ul className="list-disc pl-4">
                          {paymentResult.warnings.map((w, i) => (
                            <li key={i}>{w.message_es}</li>
                          ))}
                        </ul>
                      </AlertDescription>
                    </Alert>
                  )}

                  {/* Payment method selection */}
                  {paymentResult.readyForPayment && (
                    <div className="space-y-4">
                      <h3 className="text-sm font-semibold">
                        {locale === 'es'
                          ? 'Seleccione un metodo de pago'
                          : locale === 'fr'
                            ? 'Choisissez un mode de paiement'
                            : 'Select a payment method'}
                      </h3>

                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        {paymentResult.paymentMethods.map((method) => {
                          const isSelected = selectedPaymentMethod === method.code
                          const label =
                            locale === 'fr'
                              ? method.labelFr
                              : locale === 'en'
                                ? method.labelEn
                                : method.labelEs
                          const Icon =
                            method.code === 'mobile_money'
                              ? Smartphone
                              : method.code === 'cash'
                                ? Banknote
                                : CreditCard

                          return (
                            <button
                              key={method.code}
                              type="button"
                              onClick={() => {
                                setSelectedPaymentMethod(method.code)
                                setPaymentError(null)
                              }}
                              className={`flex items-center gap-3 p-4 rounded-lg border-2 text-left transition-colors ${
                                isSelected
                                  ? 'border-primary bg-primary/5'
                                  : 'border-muted hover:border-primary/50'
                              }`}
                            >
                              <Icon className={`h-6 w-6 ${isSelected ? 'text-primary' : 'text-muted-foreground'}`} />
                              <div>
                                <p className={`font-medium ${isSelected ? 'text-primary' : ''}`}>
                                  {label}
                                </p>
                                {method.requiresAgentValidation && (
                                  <p className="text-xs text-muted-foreground">
                                    {locale === 'es'
                                      ? 'Requiere validacion del agente'
                                      : locale === 'fr'
                                        ? 'Necessite la validation de l\'agent'
                                        : 'Requires agent validation'}
                                  </p>
                                )}
                              </div>
                            </button>
                          )
                        })}
                      </div>

                      {/* Treasury office selector for cash/check */}
                      {isManualPayment && treasuryLocations && treasuryLocations.length > 0 && (
                        <div className="space-y-2">
                          <Label htmlFor="treasury-location">
                            <MapPin className="inline-block mr-1 h-4 w-4" />
                            {locale === 'es'
                              ? 'Oficina de pago'
                              : locale === 'fr'
                                ? 'Bureau de paiement'
                                : 'Payment office'}
                          </Label>
                          <select
                            id="treasury-location"
                            value={treasuryLocationId || ''}
                            onChange={(e) => setTreasuryLocationId(e.target.value || null)}
                            className="flex h-10 w-full max-w-[400px] rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                          >
                            <option value="">
                              {locale === 'es' ? 'Seleccione una oficina' : locale === 'fr' ? 'Sélectionnez un bureau' : 'Select an office'}
                            </option>
                            {treasuryLocations.map((loc) => (
                              <option key={loc.id} value={loc.id}>
                                {loc.location_name} — {loc.city}
                              </option>
                            ))}
                          </select>
                          <p className="text-xs text-muted-foreground">
                            {locale === 'es'
                              ? 'Oficina del Tesoro donde realizará el pago'
                              : locale === 'fr'
                                ? 'Bureau du Trésor où vous effectuerez le paiement'
                                : 'Treasury office where you will make the payment'}
                          </p>
                        </div>
                      )}

                      {/* Phone number for mobile money */}
                      {selectedPaymentMethod === 'mobile_money' && (
                        <div className="space-y-2">
                          <Label htmlFor="payment-phone">
                            {locale === 'es'
                              ? 'Numero de telefono'
                              : locale === 'fr'
                                ? 'Numero de telephone'
                                : 'Phone number'}
                          </Label>
                          <Input
                            id="payment-phone"
                            type="tel"
                            value={paymentPhone}
                            onChange={(e) => setPaymentPhone(e.target.value)}
                            placeholder="+240 222 123 456"
                            className="max-w-[300px]"
                          />
                        </div>
                      )}

                      {/* Payment error */}
                      {paymentError && (
                        <Alert variant="destructive">
                          <AlertCircle className="h-4 w-4" />
                          <AlertDescription>{paymentError}</AlertDescription>
                        </Alert>
                      )}

                      {/* Pay button */}
                      <Button
                        size="lg"
                        onClick={handleInitiatePayment}
                        disabled={
                          isPaymentProcessing ||
                          !selectedPaymentMethod ||
                          (selectedPaymentMethod === 'mobile_money' && !paymentPhone.trim())
                        }
                        className="w-full sm:w-auto min-w-[200px]"
                      >
                        {isPaymentProcessing ? (
                          <>
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            {locale === 'es'
                              ? 'Procesando...'
                              : locale === 'fr'
                                ? 'Traitement...'
                                : 'Processing...'}
                          </>
                        ) : (
                          <>
                            <CreditCard className="mr-2 h-4 w-4" />
                            {locale === 'es'
                              ? 'Pagar'
                              : locale === 'fr'
                                ? 'Payer'
                                : 'Pay'}{' '}
                            {paymentResult.totalAmount.toLocaleString()}{' '}
                            {paymentResult.currency}
                          </>
                        )}
                      </Button>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* ============================================================ */}
          {/* STEP: Confirmation (rich summary + PDF download)             */}
          {/* ============================================================ */}
          {currentStep.type === 'confirmation' && (
            <ConfirmationStepContent
              persistedRequestId={persistedRequestId}
              paymentResult={manualPaymentResult}
              tariffResult={paymentResult}
              locale={locale as 'es' | 'fr' | 'en'}
              onNavigateToRequest={() =>
                router.push(`/${locale}/dashboard/service-requests/${persistedRequestId}`)
              }
              onNavigateToList={() =>
                router.push(`/${locale}/dashboard/service-requests`)
              }
            />
          )}

          {/* ============================================================ */}
          {/* STEP: Site Selection (non-appointment workflows)            */}
          {/* ============================================================ */}
          {currentStep.type === 'site_selection' && (
            <SiteSelection
              sessionId={session.sessionId}
              onComplete={() => handleNext()}
              onBack={() => setCurrentStepIndex((prev) => prev - 1)}
              locale={locale as 'es' | 'fr' | 'en'}
              getAvailableSites={(sid) =>
                wizardSessionApi.getAvailableSites(sid)
              }
              saveSiteSelection={(sid, data) =>
                wizardSessionApi.saveSiteSelection(sid, data)
              }
              initialSiteId={session.siteSelection?.entityLocationId ?? null}
            />
          )}

          {/* ============================================================ */}
          {/* STEP: Appointment (session-based, BEFORE payment)           */}
          {/* ============================================================ */}
          {currentStep.type === 'appointment' && (
            <AppointmentSelection
              sessionId={session.sessionId}
              onComplete={() => {
                // Advance to next step (payment) — handleNext auto-prepares payment
                handleNext()
              }}
              onBack={() => setCurrentStepIndex((prev) => prev - 1)}
              locale={locale as 'es' | 'fr' | 'en'}
              getSessionLocations={(sid) =>
                wizardSessionApi.getAppointmentLocations(sid)
              }
              getSessionAvailableDays={(sid, entityLocationId, fromDate, toDate) =>
                wizardSessionApi.getAvailableDays(sid, entityLocationId, fromDate, toDate)
              }
              getSessionSlots={(sid, entityLocationId, fromDate, limit) =>
                wizardSessionApi.getAvailableSlots(sid, entityLocationId, fromDate, limit)
              }
              saveSelection={(sid, data) =>
                wizardSessionApi.saveAppointmentSelection(sid, data)
              }
            />
          )}
        </CardContent>
      </Card>

      {/* Navigation buttons (hidden on appointment, site_selection + confirmation steps — they have their own nav) */}
      {currentStep.type !== 'appointment' && currentStep.type !== 'site_selection' && currentStep.type !== 'confirmation' && (
      <div className="flex justify-between">
        <Button
          variant="outline"
          onClick={handleBack}
          disabled={currentStepIndex === 0 || isSaving}
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          {locale === 'es'
            ? 'Anterior'
            : locale === 'fr'
              ? 'Precedent'
              : 'Previous'}
        </Button>

        {currentStep.type !== 'confirmation' && currentStep.type !== 'payment' && (
          <Button
            onClick={handleNext}
            disabled={!canGoNext() || isSaving || isLoading}
          >
            {isSaving || isLoading ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : null}
            {locale === 'es'
              ? 'Siguiente'
              : locale === 'fr'
                ? 'Suivant'
                : 'Next'}
            <ArrowRight className="ml-2 h-4 w-4" />
          </Button>
        )}
      </div>
      )}

    </div>
  )
}

// ============================================================================
// SUB-COMPONENT: Selection Step Renderer (supports Format A & B)
// ============================================================================

/**
 * Renders a SELECTION step. Supports two config formats:
 *
 * Format A (Residencia): config.sections[].fields[] — sections with structured fields
 * Format B (all others): config.selection_type + config.options[] — flat option list
 */
function SelectionStepRenderer({
  currentStep,
  workflowConfig,
  formValues,
  onFormChange,
  locale,
  tw,
  workflowCode,
}: {
  currentStep: WizardStepDef
  workflowConfig: import('@/modules/service-requests').WorkflowConfig | undefined
  formValues: Record<string, unknown>
  onFormChange: (key: string, value: unknown) => void
  locale: string
  tw: (keyCode: string, fallbackEs?: string) => string
  workflowCode: string
}) {
  const stepConfig = workflowConfig?.steps?.find(s => s.stepId === currentStep.id)
  const cfg = stepConfig?.config as Record<string, unknown> | undefined

  // Derive workflow family for translation lookups (mirrors mobile step-selection.tsx)
  const wfFamily = (() => {
    const lower = workflowCode.toLowerCase()
    if (lower.startsWith('pasaporte')) return 'pasaporte'
    if (lower.startsWith('conducir')) return 'conducir'
    if (lower.startsWith('contrato')) return 'contrato'
    if (lower.startsWith('residencia')) return 'residencia'
    if (lower.startsWith('vehiculo')) return 'vehiculo'
    if (lower.startsWith('prorroga') || lower.startsWith('visado') || lower.startsWith('permanencia') || lower.startsWith('salida_visado')) return 'visado'
    if (lower.startsWith('fp_carnet')) return 'carnet'
    if (lower.startsWith('fp_promocion')) return 'promocion'
    if (lower.startsWith('fp_permiso')) return 'permiso'
    if (lower.startsWith('fp_certificado')) return 'certificado'
    if (lower.startsWith('fp_verificacion')) return 'verificacion'
    if (lower === 'bundle_payment') return 'bundle'
    return lower
  })()

  // Translate option label — tries workflow key → motivo key → applicant key → fallback ES
  const translateLabel = (labelEs: string | undefined, optionValue?: string): string => {
    if (!labelEs) return optionValue || ''
    if (!wfFamily || !optionValue) return tw(stepTitleKey(labelEs), labelEs)

    const optKey = optionLabelKey(wfFamily, optionValue)
    const result = tw(optKey, '')
    if (result && result !== optKey) return result

    // Try with clase_ prefix (for license classes: A → clase_A)
    const claseKey = optionLabelKey(wfFamily, `clase_${optionValue}`)
    const claseResult = tw(claseKey, '')
    if (claseResult && claseResult !== claseKey) return claseResult

    // Try motivo key (shared across workflows)
    const mKey = `workflow.motivo.${optionValue}`
    const mResult = tw(mKey, '')
    if (mResult && mResult !== mKey) return mResult

    // Try applicant type key (shared)
    const appKey = `workflow.option.applicant.${optionValue.toLowerCase()}`
    const appResult = tw(appKey, '')
    if (appResult && appResult !== appKey) return appResult

    return labelEs
  }

  // Translate option description — same fallback chain
  const translateDesc = (descEs: string | undefined, optionValue?: string): string | undefined => {
    if (!descEs) return undefined
    if (!wfFamily || !optionValue) return descEs

    const descKey = optionDescKey(wfFamily, optionValue)
    const result = tw(descKey, '')
    if (result && result !== descKey) return result

    const mDescKey = `workflow.motivo.${optionValue}.desc`
    const mResult = tw(mDescKey, '')
    if (mResult && mResult !== mDescKey) return mResult

    const appDescKey = `workflow.option.applicant.${optionValue.toLowerCase()}.desc`
    const appResult = tw(appDescKey, '')
    if (appResult && appResult !== appDescKey) return appResult

    return descEs
  }

  // Translate step title via translations table, fallback to Spanish from backend
  const rawTitle = stepConfig?.titleEs || currentStep.titleEs || ''
  const title = tw(stepTitleKey(rawTitle), rawTitle)

  // Format A: config.sections[].fields[] with optional show_when conditions
  const allSections = cfg?.sections as Array<{
    id: string
    title_es?: string
    show_when?: Record<string, string>
    fields: Array<{
      key: string
      type: string
      label_es?: string
      help_text_es?: string
      options?: Array<{ value: string; label_es?: string; description_es?: string }>
      required?: boolean
      min?: number
      max?: number
    }>
  }> | undefined

  // Filter sections by show_when conditions (e.g., duration only when ALTERNATIVO selected)
  const sections = allSections?.filter(s => {
    if (!s.show_when) return true
    return Object.entries(s.show_when).every(
      ([k, v]) => String(formValues[k] ?? '') === String(v)
    )
  })

  // Format B: config.selection_type + config.options[]
  const selectionType = cfg?.selection_type as string | undefined
  const options = cfg?.options as Array<{
    value: string | boolean
    label_es?: string
    description_es?: string
    icon?: string
    tariff?: number
  }> | undefined

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold">{title}</h2>
      {rawTitle && (
        <p className="text-sm text-muted-foreground">
          {tw(stepTitleKey(rawTitle) + '.desc', getLocalizedField(stepConfig as unknown as Record<string, unknown>, 'description', locale) || '')}
        </p>
      )}

      {/* Format A: sections with fields */}
      {sections && sections.map((section) => (
        <div key={section.id} className="space-y-3">
          {getLocalizedField(section as unknown as Record<string, unknown>, 'title', locale) && (
            <h3 className="text-sm font-medium text-muted-foreground">
              {getLocalizedField(section as unknown as Record<string, unknown>, 'title', locale)}
            </h3>
          )}
          {section.fields.map((field) => (
            <div key={field.key} className="space-y-2">
              {getLocalizedField(field as unknown as Record<string, unknown>, 'label', locale) && (
                <Label className="text-sm font-medium">{getLocalizedField(field as unknown as Record<string, unknown>, 'label', locale)}</Label>
              )}
              {getLocalizedField(field as unknown as Record<string, unknown>, 'help_text', locale) && (
                <p className="text-xs text-muted-foreground">{getLocalizedField(field as unknown as Record<string, unknown>, 'help_text', locale)}</p>
              )}
              {field.type === 'select' && field.options ? (
                <RadioGroup
                  value={String(formValues[field.key] ?? '')}
                  onValueChange={(val) => onFormChange(field.key, val)}
                  className="space-y-2"
                >
                  {field.options.map((opt) => (
                    <div key={opt.value} className="flex items-center space-x-2 p-3 border rounded-lg hover:bg-muted/50 cursor-pointer">
                      <RadioGroupItem value={opt.value} id={`${field.key}-${opt.value}`} />
                      <Label htmlFor={`${field.key}-${opt.value}`} className="cursor-pointer flex-1">
                        <span>{translateLabel(opt.label_es, opt.value)}</span>
                        {opt.description_es && (
                          <span className="block text-xs text-muted-foreground font-normal mt-0.5">
                            {translateDesc(opt.description_es, opt.value)}
                          </span>
                        )}
                      </Label>
                    </div>
                  ))}
                </RadioGroup>
              ) : field.type === 'number' ? (
                <Input
                  type="number"
                  value={String(formValues[field.key] ?? '')}
                  onChange={(e) => onFormChange(field.key, e.target.value)}
                  min={field.min}
                  max={field.max}
                  className="max-w-[200px]"
                />
              ) : null}
            </div>
          ))}
        </div>
      ))}

      {/* Format B: flat options list with selection_type key */}
      {!sections && selectionType && options && (
        <RadioGroup
          value={String(formValues[selectionType] ?? '')}
          onValueChange={(val) => onFormChange(selectionType, val)}
          className="space-y-2"
        >
          {options.map((opt) => {
            const optValue = String(opt.value)
            return (
              <div key={optValue} className="flex items-center space-x-2 p-4 border rounded-lg hover:bg-muted/50 cursor-pointer">
                <RadioGroupItem value={optValue} id={`${selectionType}-${optValue}`} />
                <Label htmlFor={`${selectionType}-${optValue}`} className="cursor-pointer flex-1">
                  <span className="font-medium">{translateLabel(opt.label_es, optValue)}</span>
                  {opt.description_es && (
                    <span className="block text-xs text-muted-foreground font-normal mt-0.5">
                      {translateDesc(opt.description_es, optValue)}
                    </span>
                  )}
                  {opt.tariff !== undefined && opt.tariff > 0 && (
                    <span className="block text-xs text-primary font-normal mt-0.5">
                      {opt.tariff.toLocaleString()} XAF
                    </span>
                  )}
                </Label>
              </div>
            )
          })}
        </RadioGroup>
      )}

      {/* Format C: multi_selection (checkboxes, e.g. license classes) */}
      {!sections && !selectionType && cfg?.type === 'multi_selection' && (
        (() => {
          const multiOptions = cfg.options as Array<{ id: string; label_es?: string; min_age?: number }> | undefined
          const stepId = currentStep.id
          const selected = (formValues[stepId] as string[] | undefined) || []
          const maxSelection = (cfg.max_selection as number) || 10
          if (!multiOptions) return null
          return (
            <div className="space-y-2">
              <p className="text-xs text-muted-foreground">
                {locale === 'es'
                  ? `Seleccione hasta ${maxSelection} opciones`
                  : locale === 'fr'
                    ? `Selectionnez jusqu'a ${maxSelection} options`
                    : `Select up to ${maxSelection} options`}
              </p>
              {multiOptions.map((opt) => {
                const isChecked = selected.includes(opt.id)
                return (
                  <div
                    key={opt.id}
                    className={`flex items-center space-x-3 p-3 border rounded-lg cursor-pointer hover:bg-muted/50 ${isChecked ? 'border-primary bg-primary/5' : ''}`}
                    onClick={() => {
                      const next = isChecked
                        ? selected.filter(v => v !== opt.id)
                        : selected.length < maxSelection
                          ? [...selected, opt.id]
                          : selected
                      onFormChange(stepId, next)
                    }}
                  >
                    <Checkbox
                      checked={isChecked}
                      onCheckedChange={(checked) => {
                        const next = checked
                          ? [...selected, opt.id]
                          : selected.filter(v => v !== opt.id)
                        onFormChange(stepId, next)
                      }}
                      disabled={!isChecked && selected.length >= maxSelection}
                    />
                    <Label className="cursor-pointer flex-1">
                      <span className="font-medium">{translateLabel(opt.label_es, opt.id)}</span>
                      {opt.min_age && (
                        <span className="text-xs text-muted-foreground ml-2">
                          (min. {opt.min_age} {locale === 'es' ? 'anos' : locale === 'fr' ? 'ans' : 'years'})
                        </span>
                      )}
                    </Label>
                  </div>
                )
              })}
            </div>
          )
        })()
      )}

      {/* No config loaded yet */}
      {!cfg && (
        <div className="flex items-center gap-2 p-4">
          <Loader2 className="h-4 w-4 animate-spin" />
          <span className="text-muted-foreground">
            {locale === 'es' ? 'Cargando opciones...' : locale === 'fr' ? 'Chargement...' : 'Loading...'}
          </span>
        </div>
      )}
    </div>
  )
}

// ============================================================================
// SUB-COMPONENT: Dynamic Form Review Step (uses DynamicFormRenderer)
// ============================================================================

function SessionDynamicFormReview({
  sessionId,
  stepId,
  values,
  onChange,
  locale,
  errors,
  onConfigLoaded,
}: {
  sessionId: string
  stepId: string
  values: Record<string, unknown>
  onChange: (key: string, value: unknown) => void
  locale: 'es' | 'fr' | 'en'
  errors?: Record<string, string>
  onConfigLoaded?: (config: import('@/modules/service-requests').FormConfig) => void
}) {
  const { data: formConfig, isLoading, error } = useSessionFormConfig(sessionId, stepId)

  // Initialize form values from config's current_value when config loads
  useEffect(() => {
    if (formConfig) {
      // Notify parent of loaded config for validation
      onConfigLoaded?.(formConfig)

      for (const section of formConfig.sections) {
        for (const field of section.fields) {
          if (
            field.current_value !== undefined &&
            field.current_value !== null &&
            values[field.key] === undefined
          ) {
            onChange(field.key, field.current_value)
          }
        }
      }
    }
    // Only run when formConfig changes, not values
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [formConfig])

  // Prefetch next form_review step
  const { prefetch } = usePrefetchSessionFormConfig()
  useEffect(() => {
    const stepNum = parseInt(stepId.replace('form_review_', ''), 10)
    if (!isNaN(stepNum)) {
      prefetch(sessionId, `form_review_${stepNum + 1}`).catch(() => {
        // Next form_review step doesn't exist or context incomplete - that's fine
      })
    }
  }, [sessionId, stepId, prefetch])

  if (isLoading) {
    return <DynamicFormRenderer.Skeleton />
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>
          {locale === 'es'
            ? 'Error al cargar la configuracion del formulario.'
            : locale === 'fr'
              ? 'Erreur lors du chargement de la configuration du formulaire.'
              : 'Error loading form configuration.'}
          <br />
          <span className="text-xs">{(error as Error).message}</span>
        </AlertDescription>
      </Alert>
    )
  }

  if (!formConfig) return null

  return (
    <DynamicFormRenderer
      config={formConfig}
      values={values}
      onChange={onChange}
      locale={locale}
      errors={errors}
    />
  )
}

// ============================================================================
// SUB-COMPONENT: Confirmation Step (rich summary + PDF download + print)
// ============================================================================

function ConfirmationStepContent({
  persistedRequestId,
  paymentResult,
  tariffResult,
  locale,
  onNavigateToRequest,
  onNavigateToList,
}: {
  persistedRequestId: string | null
  paymentResult: InitiatePaymentResult | null
  tariffResult: PreparePaymentResult | null
  locale: 'es' | 'fr' | 'en'
  onNavigateToRequest: () => void
  onNavigateToList: () => void
}) {
  const [summary, setSummary] = useState<CitizenSummaryResponse | null>(null)
  const [summaryLoading, setSummaryLoading] = useState(false)
  const [summaryError, setSummaryError] = useState<string | null>(null)
  const [isDownloading, setIsDownloading] = useState(false)
  const [downloadError, setDownloadError] = useState<string | null>(null)
  const [detailsOpen, setDetailsOpen] = useState(false)

  // Determine payment status
  const isPendingValidation = paymentResult?.requiresAction &&
    paymentResult?.actionType?.startsWith('agent_validation')

  // Fetch summary on mount
  useEffect(() => {
    if (!persistedRequestId) return
    let cancelled = false
    setSummaryLoading(true)
    setSummaryError(null)
    serviceRequestsApi.getCitizenSummary(persistedRequestId)
      .then((data) => {
        if (!cancelled) setSummary(data)
      })
      .catch((err) => {
        if (!cancelled) setSummaryError(err instanceof Error ? err.message : 'Error')
      })
      .finally(() => {
        if (!cancelled) setSummaryLoading(false)
      })
    return () => { cancelled = true }
  }, [persistedRequestId])

  // Fetch PDF blob (shared between download and print)
  const fetchPDFBlob = useCallback(async (): Promise<Blob | null> => {
    if (!persistedRequestId) return null
    setDownloadError(null)
    try {
      return await serviceRequestsApi.downloadSummaryPDF(persistedRequestId, locale)
    } catch (err) {
      console.error('[ConfirmationStep] PDF error:', err)
      setDownloadError(err instanceof Error ? err.message : 'Error al descargar PDF')
      return null
    }
  }, [persistedRequestId, locale])

  // PDF download handler
  const handleDownloadPDF = useCallback(async () => {
    setIsDownloading(true)
    try {
      const blob = await fetchPDFBlob()
      if (!blob) return
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `solicitud_${paymentResult?.reference || persistedRequestId}.pdf`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      setTimeout(() => URL.revokeObjectURL(url), 5000)
    } finally {
      setIsDownloading(false)
    }
  }, [fetchPDFBlob, paymentResult?.reference, persistedRequestId])

  // Print handler — opens PDF in new tab for native print
  const [isPrinting, setIsPrinting] = useState(false)
  const handlePrint = useCallback(async () => {
    setIsPrinting(true)
    try {
      const blob = await fetchPDFBlob()
      if (!blob) return
      const url = URL.createObjectURL(blob)
      window.open(url, '_blank')
      setTimeout(() => URL.revokeObjectURL(url), 30000)
    } finally {
      setIsPrinting(false)
    }
  }, [fetchPDFBlob])

  const texts = {
    es: {
      title: 'Solicitud completada',
      subtitle: 'Su solicitud ha sido registrada correctamente.',
      pendingTitle: 'Solicitud registrada - Pago pendiente de validacion',
      pendingSubtitle: 'Presente este comprobante en la oficina del Tesoro para la validacion de su pago.',
      reference: 'Referencia',
      paymentRef: 'Ref. pago',
      amount: 'Monto total',
      status: 'Estado pago',
      statusPending: 'Pendiente validacion',
      statusConfirmed: 'Confirmado',
      personalData: 'Datos personales',
      documents: 'Documentos presentados',
      tariff: 'Desglose de pago',
      baseTariff: 'Tarifa base',
      total: 'Total',
      appointment: 'Cita programada',
      downloadPdf: 'Descargar PDF',
      print: 'Imprimir',
      viewRequest: 'Ver mi solicitud',
      goToList: 'Ir a mis solicitudes',
      nextSteps: 'Proximos pasos',
      nextStepsPending: 'Acuda a la oficina del Tesoro con este comprobante para validar su pago. Una vez validado, su solicitud sera procesada.',
      nextStepsConfirmed: 'Su solicitud sera procesada por el agente correspondiente. Recibira una notificacion por email con los avances.',
      loading: 'Cargando resumen...',
      showDetails: 'Ver detalle de la solicitud',
      hideDetails: 'Ocultar detalle',
    },
    fr: {
      title: 'Demande completee',
      subtitle: 'Votre demande a ete enregistree avec succes.',
      pendingTitle: 'Demande enregistree - Paiement en attente de validation',
      pendingSubtitle: 'Presentez ce justificatif au bureau du Tresor pour la validation de votre paiement.',
      reference: 'Reference',
      paymentRef: 'Ref. paiement',
      amount: 'Montant total',
      status: 'Statut paiement',
      statusPending: 'En attente de validation',
      statusConfirmed: 'Confirme',
      personalData: 'Donnees personnelles',
      documents: 'Documents presentes',
      tariff: 'Detail du paiement',
      baseTariff: 'Tarif de base',
      total: 'Total',
      appointment: 'Rendez-vous programme',
      downloadPdf: 'Telecharger PDF',
      print: 'Imprimer',
      viewRequest: 'Voir ma demande',
      goToList: 'Aller a mes demandes',
      nextSteps: 'Prochaines etapes',
      nextStepsPending: 'Rendez-vous au bureau du Tresor avec ce justificatif pour valider votre paiement. Une fois valide, votre demande sera traitee.',
      nextStepsConfirmed: 'Votre demande sera traitee par l\'agent competent. Vous recevrez une notification par email.',
      loading: 'Chargement du resume...',
      showDetails: 'Voir le detail de la demande',
      hideDetails: 'Masquer le detail',
    },
    en: {
      title: 'Request completed',
      subtitle: 'Your request has been successfully registered.',
      pendingTitle: 'Request registered - Payment pending validation',
      pendingSubtitle: 'Present this receipt at the Treasury office for payment validation by an agent.',
      reference: 'Reference',
      paymentRef: 'Payment ref.',
      amount: 'Total amount',
      status: 'Payment status',
      statusPending: 'Pending validation',
      statusConfirmed: 'Confirmed',
      personalData: 'Personal data',
      documents: 'Documents submitted',
      tariff: 'Payment breakdown',
      baseTariff: 'Base tariff',
      total: 'Total',
      appointment: 'Scheduled appointment',
      downloadPdf: 'Download PDF',
      print: 'Print',
      viewRequest: 'View my request',
      goToList: 'Go to my requests',
      nextSteps: 'Next steps',
      nextStepsPending: 'Go to the Treasury office with this receipt to validate your payment. Once validated, your request will be processed.',
      nextStepsConfirmed: 'Your request will be processed by the corresponding agent. You will receive an email notification with updates.',
      loading: 'Loading summary...',
      showDetails: 'View request details',
      hideDetails: 'Hide details',
    },
  }
  const t = texts[locale]

  return (
    <div className="space-y-6">
      {/* ============================================================
          HERO SECTION — Payment status + reference + actions
          ============================================================ */}
      <div className="text-center space-y-3">
        <div className={`mx-auto w-16 h-16 rounded-full flex items-center justify-center ${
          isPendingValidation ? 'bg-amber-100' : 'bg-green-100'
        }`}>
          {isPendingValidation
            ? <Clock className="h-8 w-8 text-amber-600" />
            : <CheckCircle className="h-8 w-8 text-green-600" />
          }
        </div>
        <h2 className="text-lg font-semibold">
          {isPendingValidation ? t.pendingTitle : t.title}
        </h2>
        <p className="text-muted-foreground max-w-md mx-auto text-sm">
          {isPendingValidation ? t.pendingSubtitle : t.subtitle}
        </p>
      </div>

      {/* Reference + payment info card */}
      <div className="border rounded-lg p-4 max-w-md mx-auto space-y-3">
        {paymentResult?.reference && (
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">{t.reference}</span>
            <span className="font-mono font-bold">{paymentResult.reference}</span>
          </div>
        )}
        {paymentResult?.paymentReference && (
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">{t.paymentRef}</span>
            <span className="font-mono font-bold">{paymentResult.paymentReference}</span>
          </div>
        )}
        {tariffResult && (
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">{t.amount}</span>
            <span className="font-bold">
              {tariffResult.totalAmount.toLocaleString()} {tariffResult.currency}
            </span>
          </div>
        )}
        <hr />
        <div className="flex justify-between text-sm">
          <span className="text-muted-foreground">{t.status}</span>
          <Badge variant="outline" className={
            isPendingValidation
              ? 'text-amber-600 border-amber-300'
              : 'text-green-600 border-green-300'
          }>
            {isPendingValidation ? t.statusPending : t.statusConfirmed}
          </Badge>
        </div>
      </div>

      {/* Appointment (always visible when present — important info) */}
      {paymentResult?.appointmentConfirmed && (
        <div className="border-2 border-primary rounded-lg p-4 bg-primary/5 max-w-md mx-auto">
          <h4 className="font-semibold text-sm mb-2">{t.appointment}</h4>
          <div className="flex gap-4 text-sm">
            <div className="flex items-center gap-1">
              <Calendar className="h-4 w-4 text-primary" />
              <span>{paymentResult.appointmentDate}</span>
            </div>
            <div className="flex items-center gap-1">
              <Clock className="h-4 w-4 text-primary" />
              <span>{paymentResult.appointmentTime}</span>
            </div>
          </div>
          {paymentResult.appointmentLocation && (
            <p className="text-sm text-muted-foreground mt-1">{paymentResult.appointmentLocation}</p>
          )}
        </div>
      )}

      {/* Action buttons — prominent position */}
      <div className="flex flex-col items-center gap-3">
        <div className="flex gap-3">
          <Button
            variant="outline"
            size="sm"
            onClick={handleDownloadPDF}
            disabled={isDownloading || !persistedRequestId}
          >
            {isDownloading
              ? <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              : <Download className="mr-2 h-4 w-4" />
            }
            {t.downloadPdf}
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handlePrint}
            disabled={isPrinting || !persistedRequestId}
          >
            {isPrinting
              ? <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              : <Printer className="mr-2 h-4 w-4" />
            }
            {t.print}
          </Button>
        </div>
        {downloadError && (
          <p className="text-xs text-red-600">{downloadError}</p>
        )}
      </div>

      {/* Next steps */}
      <div className="bg-muted/50 rounded-lg p-4 max-w-md mx-auto">
        <h4 className="font-semibold text-sm mb-1">{t.nextSteps}</h4>
        <p className="text-sm text-muted-foreground">
          {isPendingValidation ? t.nextStepsPending : t.nextStepsConfirmed}
        </p>
      </div>

      {/* ============================================================
          COLLAPSIBLE — Summary details (closed by default)
          ============================================================ */}
      {summaryLoading && (
        <div className="flex items-center justify-center gap-2 py-4">
          <Loader2 className="h-4 w-4 animate-spin" />
          <span className="text-sm text-muted-foreground">{t.loading}</span>
        </div>
      )}

      {summary && (
        <Collapsible open={detailsOpen} onOpenChange={setDetailsOpen} className="max-w-lg mx-auto">
          <CollapsibleTrigger asChild>
            <Button variant="ghost" className="w-full justify-between px-4 py-3 h-auto">
              <span className="text-sm font-medium">
                {detailsOpen ? t.hideDetails : t.showDetails}
              </span>
              <ChevronDown className={`h-4 w-4 transition-transform ${detailsOpen ? 'rotate-180' : ''}`} />
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent className="space-y-4 mt-2">
            {/* Personal Data */}
            <div className="border rounded-lg overflow-hidden">
              <div className="bg-primary/10 px-4 py-2 font-semibold text-sm">
                {t.personalData}
              </div>
              <div className="p-4 grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
                {Object.entries(summary.personalData).map(([key, value]) => {
                  if (!value) return null
                  const label = key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
                  return (
                    <div key={key}>
                      <span className="text-muted-foreground text-xs">{label}</span>
                      <div className="font-medium">{String(value)}</div>
                    </div>
                  )
                })}
              </div>
            </div>

            {/* Documents */}
            <div className="border rounded-lg overflow-hidden">
              <div className="bg-primary/10 px-4 py-2 font-semibold text-sm">
                {t.documents} ({summary.documentsUploaded.length})
              </div>
              <div className="divide-y">
                {summary.documentsUploaded.map((doc) => (
                  <div key={doc.documentCode} className="flex items-center justify-between px-4 py-2 text-sm">
                    <span>{doc.documentName}</span>
                    <Badge variant="outline" className={
                      doc.isValidated
                        ? 'text-green-600 border-green-300'
                        : 'text-amber-600 border-amber-300'
                    }>
                      {doc.isValidated
                        ? (locale === 'es' ? 'Verificado' : locale === 'fr' ? 'Verifie' : 'Verified')
                        : (locale === 'es' ? 'Pendiente' : locale === 'fr' ? 'En attente' : 'Pending')
                      }
                    </Badge>
                  </div>
                ))}
              </div>
            </div>

            {/* Tariff breakdown */}
            {summary.tariffSummary && (
              <div className="border rounded-lg overflow-hidden">
                <div className="bg-primary/10 px-4 py-2 font-semibold text-sm">
                  {t.tariff}
                </div>
                <div className="p-4 space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span>{t.baseTariff}</span>
                    <span>{summary.tariffSummary.baseAmount.toLocaleString()} {summary.tariffSummary.currency}</span>
                  </div>
                  {summary.tariffSummary.supplements.map((s, i) => (
                    <div key={i} className="flex justify-between text-muted-foreground">
                      <span>{s.name}</span>
                      <span>{s.amount.toLocaleString()} {summary.tariffSummary!.currency}</span>
                    </div>
                  ))}
                  <hr />
                  <div className="flex justify-between font-bold">
                    <span>{t.total}</span>
                    <span>{summary.tariffSummary.total.toLocaleString()} {summary.tariffSummary.currency}</span>
                  </div>
                </div>
              </div>
            )}

            {/* Appointment */}
            {paymentResult?.appointmentConfirmed && (
              <div className="border rounded-lg overflow-hidden">
                <div className="bg-primary/10 px-4 py-2 font-semibold text-sm">
                  {t.appointment}
                </div>
                <div className="p-4 space-y-1 text-sm">
                  <div className="flex items-center gap-2">
                    <Calendar className="h-4 w-4 text-muted-foreground" />
                    <span className="font-medium">{paymentResult.appointmentDate}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Clock className="h-4 w-4 text-muted-foreground" />
                    <span className="font-medium">{paymentResult.appointmentTime}</span>
                  </div>
                  {paymentResult.appointmentLocation && (
                    <div className="flex items-center gap-2">
                      <MapPin className="h-4 w-4 text-muted-foreground" />
                      <span className="font-medium">{paymentResult.appointmentLocation}</span>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Reference footer */}
            <div className="border-t pt-3 text-xs text-muted-foreground space-y-1">
              <div><strong>{t.reference}:</strong> {summary.reference}</div>
              <div className="text-primary">
                {locale === 'es' ? 'Verificar en' : locale === 'fr' ? 'Verifier sur' : 'Verify at'}:{' '}
                taxasge.emacsah.com/verify/{summary.reference}
              </div>
            </div>
          </CollapsibleContent>
        </Collapsible>
      )}

      {/* Summary fetch error */}
      {summaryError && !summary && (
        <Alert variant="default" className="max-w-md mx-auto">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription className="text-xs">
            {summaryError}
          </AlertDescription>
        </Alert>
      )}

      {/* Navigation buttons */}
      <div className="flex flex-col items-center gap-3">
        <Button
          size="lg"
          onClick={onNavigateToRequest}
          disabled={!persistedRequestId}
          className="min-w-[200px]"
        >
          {t.viewRequest}
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={onNavigateToList}
        >
          {t.goToList}
        </Button>
      </div>
    </div>
  )
}
