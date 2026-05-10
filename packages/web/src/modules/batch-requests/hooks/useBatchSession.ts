/**
 * useBatchSession - React hook for Batch Request Sessions
 *
 * Manages batch session lifecycle:
 * - Session creation and retrieval
 * - Beneficiary management (add/edit/remove/import CSV)
 * - Shared document uploads
 * - Bulk document classification and extraction
 * - Form data management (DataGrid)
 * - Payment preparation and submission
 * - TTL countdown (2h session)
 *
 * @see packages/backend/app/modules/batch_requests/services/batch_session_service.py
 */

'use client'

import { useState, useCallback, useEffect, useRef } from 'react'
import { batchApi } from '../services/batch-api'
import type {
  BatchSession,
  SessionBeneficiary,
  SharedDocument,
  ClassifyResponse,
  ExtractResponse,
  BatchFormConfig,
  PreparePaymentResult,
  SubmitResult,
  BatchCreateRequest,
  BeneficiaryCreateRequest,
  BeneficiaryUpdateRequest,
  SubmitRequest,
} from '../types'
import { BatchWizardStep } from '../types'

// ============================================================================
// CONSTANTS
// ============================================================================

const WARNING_THRESHOLD_SECONDS = 600 // 10 minutes for batch (2h total)
const COUNTDOWN_INTERVAL_MS = 1000

// ============================================================================
// RETURN TYPE
// ============================================================================

export interface UseBatchSessionReturn {
  // State
  session: BatchSession | null
  isLoading: boolean
  isSaving: boolean
  error: string | null
  currentStep: BatchWizardStep

  // TTL
  timeRemaining: number | null
  isExpiring: boolean
  isExpired: boolean

  // Session lifecycle
  createSession: (data: BatchCreateRequest) => Promise<BatchSession | null>
  loadSession: (sessionId: string) => Promise<BatchSession | null>
  cancelSession: () => Promise<boolean>

  // Navigation
  canGoNext: () => boolean
  goToStep: (step: BatchWizardStep) => void
  goNext: () => void
  goBack: () => void

  // Beneficiary management
  addBeneficiary: (data: BeneficiaryCreateRequest) => Promise<SessionBeneficiary | null>
  importCsv: (file: File) => Promise<number>
  updateBeneficiary: (id: string, data: BeneficiaryUpdateRequest) => Promise<SessionBeneficiary | null>
  removeBeneficiary: (id: string) => Promise<boolean>
  reorderBeneficiary: (id: string, direction: 'up' | 'down') => Promise<boolean>

  // Shared documents
  uploadSharedDocument: (file: File, documentCode: string) => Promise<SharedDocument | null>
  removeSharedDocument: (documentCode: string) => Promise<boolean>

  // Classification + Extraction
  classifyDocuments: (files: File[]) => Promise<ClassifyResponse | null>
  confirmAssignments: (assignments: Array<{
    file_path: string
    document_type: string
    beneficiary_id: string | null
  }>) => Promise<boolean>
  extractDocuments: () => Promise<ExtractResponse | null>

  // Form config + data
  formConfig: BatchFormConfig | null
  loadFormConfig: () => Promise<BatchFormConfig | null>
  saveFormData: (data: Record<string, Record<string, unknown>>) => Promise<boolean>

  // Payment
  preparePaymentResult: PreparePaymentResult | null
  preparePayment: () => Promise<PreparePaymentResult | null>
  submitBatch: (data: SubmitRequest) => Promise<SubmitResult | null>

  // Utility
  clearError: () => void
  refreshSession: () => Promise<void>
}

// ============================================================================
// STEP INFERENCE (restore step from session state on reload)
// ============================================================================

function inferStepFromSession(session: BatchSession): BatchWizardStep {
  // Payment-ready sessions → payment step
  if (session.status === 'PAYMENT_PENDING' || session.perItemTariffs) {
    return BatchWizardStep.PAYMENT
  }
  // Has form data for any beneficiary → data grid
  const hasFormData = Object.values(session.formDataGrid || {}).some(
    (fd) => fd && Object.keys(fd).length > 0
  )
  if (hasFormData) {
    return BatchWizardStep.DATA_GRID
  }
  // Has document assignments → assignment review
  const hasAssignments = session.beneficiaries.some(
    (b) => b.assignedDocuments && b.assignedDocuments.length > 0
  )
  if (hasAssignments) {
    return BatchWizardStep.ASSIGNMENT_REVIEW
  }
  // Has classification results → bulk upload
  if (session.classificationResults && session.classificationResults.length > 0) {
    return BatchWizardStep.BULK_UPLOAD
  }
  // Has shared documents → shared documents (but advance to bulk upload)
  if (session.sharedDocuments && session.sharedDocuments.length > 0) {
    return BatchWizardStep.BULK_UPLOAD
  }
  // Has beneficiaries → beneficiary roster
  if (session.beneficiaries.length > 0) {
    return BatchWizardStep.BENEFICIARY_ROSTER
  }
  // Session exists with workflow selected but no beneficiaries yet
  // → freshly created session, skip to beneficiary roster
  if (session.workflowCode) {
    return BatchWizardStep.BENEFICIARY_ROSTER
  }
  return BatchWizardStep.WORKFLOW_SELECTION
}

// ============================================================================
// HOOK
// ============================================================================

export function useBatchSession(): UseBatchSessionReturn {
  const [session, setSession] = useState<BatchSession | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [currentStep, setCurrentStep] = useState<BatchWizardStep>(BatchWizardStep.WORKFLOW_SELECTION)
  const [timeRemaining, setTimeRemaining] = useState<number | null>(null)
  const [formConfig, setFormConfig] = useState<BatchFormConfig | null>(null)
  const [preparePaymentResult, setPreparePaymentResult] = useState<PreparePaymentResult | null>(null)

  const countdownRef = useRef<ReturnType<typeof setInterval> | null>(null)
  // Ref for sessionId to avoid stale closures (F-002)
  const sessionIdRef = useRef<string | null>(null)

  // Helper: get current sessionId safely (never stale)
  const getSessionId = useCallback((): string | null => {
    return sessionIdRef.current
  }, [])

  // Helper: update session + ref atomically
  const updateSession = useCallback((s: BatchSession | null) => {
    setSession(s)
    sessionIdRef.current = s?.sessionId ?? null
  }, [])

  // =========================================================================
  // TTL COUNTDOWN
  // =========================================================================

  const startCountdown = useCallback((expiresAt: string) => {
    if (countdownRef.current) {
      clearInterval(countdownRef.current)
    }

    const expiresMs = new Date(expiresAt).getTime()

    const tick = () => {
      const remaining = Math.max(0, Math.floor((expiresMs - Date.now()) / 1000))
      setTimeRemaining(remaining)
      if (remaining <= 0 && countdownRef.current) {
        clearInterval(countdownRef.current)
      }
    }

    tick()
    countdownRef.current = setInterval(tick, COUNTDOWN_INTERVAL_MS)
  }, [])

  useEffect(() => {
    return () => {
      if (countdownRef.current) {
        clearInterval(countdownRef.current)
      }
    }
  }, [])

  useEffect(() => {
    if (session?.expiresAt) {
      startCountdown(session.expiresAt)
    }
  }, [session?.expiresAt, startCountdown])

  const isExpiring = timeRemaining !== null && timeRemaining > 0 && timeRemaining <= WARNING_THRESHOLD_SECONDS
  const isExpired = session !== null && timeRemaining !== null && timeRemaining <= 0

  // =========================================================================
  // SESSION LIFECYCLE
  // =========================================================================

  const createSession = useCallback(async (data: BatchCreateRequest): Promise<BatchSession | null> => {
    setIsLoading(true)
    setError(null)
    try {
      const result = await batchApi.startSession(data)
      updateSession(result)
      setCurrentStep(BatchWizardStep.BENEFICIARY_ROSTER)
      return result
    } catch (e) {
      setError((e as Error).message)
      return null
    } finally {
      setIsLoading(false)
    }
  }, [updateSession])

  const loadSession = useCallback(async (sessionId: string): Promise<BatchSession | null> => {
    setIsLoading(true)
    setError(null)
    try {
      const result = await batchApi.getSession(sessionId)
      updateSession(result)

      // Restore wizard step from session state (F-026)
      if (result) {
        const inferred = inferStepFromSession(result)
        setCurrentStep(inferred)
      }

      return result
    } catch (e) {
      setError((e as Error).message)
      return null
    } finally {
      setIsLoading(false)
    }
  }, [updateSession])

  const cancelSession = useCallback(async (): Promise<boolean> => {
    const sid = getSessionId()
    if (!sid) return false
    setIsLoading(true)
    setError(null)
    try {
      await batchApi.cancelSession(sid)
      updateSession(null)
      setCurrentStep(BatchWizardStep.WORKFLOW_SELECTION)
      return true
    } catch (e) {
      setError((e as Error).message)
      return false
    } finally {
      setIsLoading(false)
    }
  }, [getSessionId, updateSession])

  const refreshSession = useCallback(async () => {
    const sid = getSessionId()
    if (!sid) return
    try {
      const result = await batchApi.getSession(sid)
      updateSession(result)
    } catch {
      // silently fail on refresh
    }
  }, [getSessionId, updateSession])

  // =========================================================================
  // NAVIGATION + STEP VALIDATION
  // =========================================================================

  const canGoNext = useCallback((): boolean => {
    if (!session) return false
    switch (currentStep) {
      case BatchWizardStep.WORKFLOW_SELECTION:
        return !!session.workflowCode
      case BatchWizardStep.BENEFICIARY_ROSTER:
        return session.beneficiaries.length > 0
      case BatchWizardStep.SHARED_DOCUMENTS:
        return true // Optional step
      case BatchWizardStep.BULK_UPLOAD:
        return (session.classificationResults ?? []).length > 0
      case BatchWizardStep.ASSIGNMENT_REVIEW:
        // At least some documents must be assigned
        return session.beneficiaries.some((b) => b.assignedDocuments.length > 0)
      case BatchWizardStep.DATA_GRID:
        return true // Save is optional, user proceeds when ready
      case BatchWizardStep.PAYMENT:
        return false // Last step
      default:
        return false
    }
  }, [session, currentStep])

  const goToStep = useCallback((step: BatchWizardStep) => {
    setCurrentStep(step)
    setError(null)
  }, [])

  const goNext = useCallback(() => {
    if (!canGoNext()) return
    setCurrentStep((prev) => Math.min(prev + 1, BatchWizardStep.PAYMENT) as BatchWizardStep)
    setError(null)
  }, [canGoNext])

  const goBack = useCallback(() => {
    setCurrentStep((prev) => Math.max(prev - 1, BatchWizardStep.WORKFLOW_SELECTION) as BatchWizardStep)
    setError(null)
  }, [])

  // =========================================================================
  // BENEFICIARY MANAGEMENT
  // =========================================================================

  const addBeneficiary = useCallback(async (data: BeneficiaryCreateRequest): Promise<SessionBeneficiary | null> => {
    const sid = getSessionId()
    if (!sid) return null
    setIsSaving(true)
    setError(null)
    try {
      const result = await batchApi.sessionAddBeneficiary(sid, data)
      setSession((prev) => prev ? {
        ...prev,
        beneficiaries: [...prev.beneficiaries, result],
      } : prev)
      return result
    } catch (e) {
      setError((e as Error).message)
      return null
    } finally {
      setIsSaving(false)
    }
  }, [getSessionId])

  const importCsv = useCallback(async (file: File): Promise<number> => {
    const sid = getSessionId()
    if (!sid) return 0
    setIsSaving(true)
    setError(null)
    try {
      const result = await batchApi.sessionImportCsv(sid, file)
      await refreshSession()
      return result.imported
    } catch (e) {
      setError((e as Error).message)
      return 0
    } finally {
      setIsSaving(false)
    }
  }, [getSessionId, refreshSession])

  const updateBeneficiary = useCallback(async (
    id: string,
    data: BeneficiaryUpdateRequest
  ): Promise<SessionBeneficiary | null> => {
    const sid = getSessionId()
    if (!sid) return null
    setIsSaving(true)
    setError(null)
    try {
      const result = await batchApi.sessionUpdateBeneficiary(sid, id, data)
      setSession((prev) => prev ? {
        ...prev,
        beneficiaries: prev.beneficiaries.map((b) => b.id === id ? result : b),
      } : prev)
      return result
    } catch (e) {
      setError((e as Error).message)
      return null
    } finally {
      setIsSaving(false)
    }
  }, [getSessionId])

  const removeBeneficiary = useCallback(async (id: string): Promise<boolean> => {
    const sid = getSessionId()
    if (!sid) return false
    setIsSaving(true)
    setError(null)
    try {
      await batchApi.sessionRemoveBeneficiary(sid, id)
      setSession((prev) => prev ? {
        ...prev,
        beneficiaries: prev.beneficiaries.filter((b) => b.id !== id),
      } : prev)
      return true
    } catch (e) {
      setError((e as Error).message)
      return false
    } finally {
      setIsSaving(false)
    }
  }, [getSessionId])

  const reorderBeneficiary = useCallback(async (
    id: string,
    direction: 'up' | 'down'
  ): Promise<boolean> => {
    const sid = getSessionId()
    if (!sid) return false
    setIsSaving(true)
    try {
      await batchApi.sessionReorderBeneficiary(sid, id, direction)
      // Optimistic update
      setSession((prev) => {
        if (!prev) return prev
        const bens = [...prev.beneficiaries]
        const idx = bens.findIndex((b) => b.id === id)
        if (idx === -1) return prev
        if (direction === 'up' && idx > 0) {
          [bens[idx], bens[idx - 1]] = [bens[idx - 1], bens[idx]]
        } else if (direction === 'down' && idx < bens.length - 1) {
          [bens[idx], bens[idx + 1]] = [bens[idx + 1], bens[idx]]
        }
        return { ...prev, beneficiaries: bens }
      })
      return true
    } catch (e) {
      setError((e as Error).message)
      return false
    } finally {
      setIsSaving(false)
    }
  }, [getSessionId])

  // =========================================================================
  // SHARED DOCUMENTS
  // =========================================================================

  const uploadSharedDocument = useCallback(async (
    file: File,
    documentCode: string
  ): Promise<SharedDocument | null> => {
    const sid = getSessionId()
    if (!sid) return null
    setIsSaving(true)
    setError(null)
    try {
      const result = await batchApi.sessionUploadSharedDocument(sid, file, documentCode)
      setSession((prev) => prev ? {
        ...prev,
        sharedDocuments: [...prev.sharedDocuments, result],
      } : prev)
      return result
    } catch (e) {
      setError((e as Error).message)
      return null
    } finally {
      setIsSaving(false)
    }
  }, [getSessionId])

  const removeSharedDocument = useCallback(async (documentCode: string): Promise<boolean> => {
    const sid = getSessionId()
    if (!sid) return false
    setIsSaving(true)
    setError(null)
    try {
      await batchApi.sessionRemoveSharedDocument(sid, documentCode)
      setSession((prev) => prev ? {
        ...prev,
        sharedDocuments: prev.sharedDocuments.filter((d) => d.documentCode !== documentCode),
      } : prev)
      return true
    } catch (e) {
      setError((e as Error).message)
      return false
    } finally {
      setIsSaving(false)
    }
  }, [getSessionId])

  // =========================================================================
  // CLASSIFICATION + EXTRACTION
  // =========================================================================

  const classifyDocuments = useCallback(async (files: File[]): Promise<ClassifyResponse | null> => {
    const sid = getSessionId()
    if (!sid) return null
    setIsLoading(true)
    setError(null)
    try {
      const result = await batchApi.sessionClassifyDocuments(sid, files)
      await refreshSession()
      return result
    } catch (e) {
      setError((e as Error).message)
      return null
    } finally {
      setIsLoading(false)
    }
  }, [getSessionId, refreshSession])

  const confirmAssignments = useCallback(async (
    assignments: Array<{
      file_path: string
      document_type: string
      beneficiary_id: string | null
    }>
  ): Promise<boolean> => {
    const sid = getSessionId()
    if (!sid) return false
    setIsSaving(true)
    setError(null)
    try {
      await batchApi.sessionConfirmAssignments(sid, assignments)
      await refreshSession()
      return true
    } catch (e) {
      setError((e as Error).message)
      return false
    } finally {
      setIsSaving(false)
    }
  }, [getSessionId, refreshSession])

  const extractDocuments = useCallback(async (): Promise<ExtractResponse | null> => {
    const sid = getSessionId()
    if (!sid) return null
    setIsLoading(true)
    setError(null)
    try {
      const result = await batchApi.sessionExtractDocuments(sid)
      await refreshSession()
      return result
    } catch (e) {
      setError((e as Error).message)
      return null
    } finally {
      setIsLoading(false)
    }
  }, [getSessionId, refreshSession])

  // =========================================================================
  // FORM CONFIG + DATA
  // =========================================================================

  const loadFormConfig = useCallback(async (): Promise<BatchFormConfig | null> => {
    const sid = getSessionId()
    if (!sid) return null
    setIsLoading(true)
    setError(null)
    try {
      const result = await batchApi.sessionGetFormConfig(sid)
      setFormConfig(result)
      return result
    } catch (e) {
      setError((e as Error).message)
      return null
    } finally {
      setIsLoading(false)
    }
  }, [getSessionId])

  const saveFormData = useCallback(async (
    data: Record<string, Record<string, unknown>>
  ): Promise<boolean> => {
    const sid = getSessionId()
    if (!sid) return false
    setIsSaving(true)
    setError(null)
    try {
      await batchApi.sessionSaveFormData(sid, data)
      setSession((prev) => prev ? { ...prev, formDataGrid: data } : prev)
      return true
    } catch (e) {
      setError((e as Error).message)
      return false
    } finally {
      setIsSaving(false)
    }
  }, [getSessionId])

  // =========================================================================
  // PAYMENT + SUBMIT
  // =========================================================================

  const preparePayment = useCallback(async (): Promise<PreparePaymentResult | null> => {
    const sid = getSessionId()
    if (!sid) return null
    setIsLoading(true)
    setError(null)
    try {
      const result = await batchApi.sessionPreparePayment(sid)
      setPreparePaymentResult(result)
      return result
    } catch (e) {
      setError((e as Error).message)
      return null
    } finally {
      setIsLoading(false)
    }
  }, [getSessionId])

  const submitBatch = useCallback(async (data: SubmitRequest): Promise<SubmitResult | null> => {
    const sid = getSessionId()
    if (!sid) return null
    setIsSaving(true)
    setError(null)
    try {
      const result = await batchApi.sessionSubmit(sid, data)
      updateSession(null)
      return result
    } catch (e) {
      setError((e as Error).message)
      return null
    } finally {
      setIsSaving(false)
    }
  }, [getSessionId, updateSession])

  // =========================================================================
  // UTILITY
  // =========================================================================

  const clearError = useCallback(() => setError(null), [])

  return {
    // State
    session,
    isLoading,
    isSaving,
    error,
    currentStep,

    // TTL
    timeRemaining,
    isExpiring,
    isExpired,

    // Session lifecycle
    createSession,
    loadSession,
    cancelSession,

    // Navigation
    canGoNext,
    goToStep,
    goNext,
    goBack,

    // Beneficiaries
    addBeneficiary,
    importCsv,
    updateBeneficiary,
    removeBeneficiary,
    reorderBeneficiary,

    // Shared documents
    uploadSharedDocument,
    removeSharedDocument,

    // Classification + Extraction
    classifyDocuments,
    confirmAssignments,
    extractDocuments,

    // Form config + data
    formConfig,
    loadFormConfig,
    saveFormData,

    // Payment
    preparePaymentResult,
    preparePayment,
    submitBatch,

    // Utility
    clearError,
    refreshSession,
  }
}
