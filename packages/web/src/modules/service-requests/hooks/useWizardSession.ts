/**
 * useWizardSession - React hook for Cache-First Wizard Sessions
 *
 * Manages wizard session lifecycle:
 * - Session creation and retrieval
 * - Document preview/confirm operations
 * - Form data saving
 * - TTL countdown with expiry warning
 * - Payment preparation and session persistence
 *
 * @since v2.0 - Cache-first wizard migration
 * @see .claude/plans/CACHE_FIRST_WIZARD_MIGRATION_PLAN.md
 */

'use client'

import { useState, useCallback, useEffect, useRef } from 'react'
import { wizardSessionApi } from '../services/wizard-session-api'
import type {
  WizardSession,
  DocumentPreview,
  PreparePaymentResult,
  PersistResult,
  InitiatePaymentResult,
  WizardSessionCreateRequest,
  DocumentConfirmRequest,
  FormDataSaveRequest,
} from '../types/wizard-session'
import { WizardSessionStatus } from '../types/wizard-session'

// ============================================================================
// CONSTANTS
// ============================================================================

const WARNING_THRESHOLD_SECONDS = 300 // 5 minutes
const COUNTDOWN_INTERVAL_MS = 1000

// ============================================================================
// RETURN TYPE
// ============================================================================

export interface UseWizardSessionReturn {
  // State
  session: WizardSession | null
  isLoading: boolean
  isSaving: boolean
  error: string | null

  // Per-document upload tracking
  uploadingDocs: Set<string>
  isDocumentUploading: (documentCode: string) => boolean

  // TTL
  timeRemaining: number // seconds
  isExpiring: boolean // < 5 min
  isExpired: boolean

  // Session lifecycle
  createSession: (data: WizardSessionCreateRequest) => Promise<WizardSession | null>
  loadSession: (sessionId: string) => Promise<WizardSession | null>
  cancelSession: (reason?: string) => Promise<boolean>

  // Document operations
  previewDocument: (documentCode: string, file: File) => Promise<DocumentPreview | null>
  confirmDocument: (data: DocumentConfirmRequest) => Promise<boolean>
  deleteDocument: (documentCode: string) => Promise<boolean>
  linkVaultDocument: (documentCode: string, vaultDocumentId: string) => Promise<boolean>

  // Form data
  saveFormData: (data: FormDataSaveRequest) => Promise<boolean>

  // Appointment (session-based, before payment)
  saveAppointmentData: (data: {
    entityLocationId: string
    locationName: string
    city: string
    appointmentDate: string
    appointmentTime: string
    slotConfigId?: string | null
  }) => Promise<boolean>

  saveSiteData: (data: {
    entityLocationId: string
    locationName: string
    city: string
    entityCode?: string | null
  }) => Promise<boolean>

  // Payment
  preparePayment: () => Promise<PreparePaymentResult | null>
  /** @deprecated Use initiatePayment() for atomic persist+pay. Kept for free services (amount=0). */
  persistAndPay: (paymentId?: string) => Promise<PersistResult | null>
  /** Atomically persist session + initiate payment in one call. */
  initiatePayment: (paymentMethod: string, phoneNumber?: string, treasuryLocationId?: string) => Promise<InitiatePaymentResult | null>

  // Utility
  clearError: () => void
  reset: () => void
}

// ============================================================================
// HOOK
// ============================================================================

export function useWizardSession(): UseWizardSessionReturn {
  const [session, setSession] = useState<WizardSession | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [timeRemaining, setTimeRemaining] = useState(0)
  const [uploadingDocs, setUploadingDocs] = useState<Set<string>>(new Set())
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // ==========================================================================
  // TTL COUNTDOWN TIMER
  // ==========================================================================

  const startTimer = useCallback((expiresAt: string) => {
    // Clear any existing timer
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }

    const updateRemaining = () => {
      const expMs = new Date(expiresAt).getTime()
      const remaining = Math.max(0, Math.floor((expMs - Date.now()) / 1000))
      setTimeRemaining(remaining)

      if (remaining <= 0) {
        if (timerRef.current) {
          clearInterval(timerRef.current)
          timerRef.current = null
        }
        setSession((prev) =>
          prev ? { ...prev, status: WizardSessionStatus.EXPIRED } : null
        )
      }
    }

    // Initial update
    updateRemaining()

    // Start interval
    timerRef.current = setInterval(updateRemaining, COUNTDOWN_INTERVAL_MS)
  }, [])

  // Cleanup timer on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current)
      }
    }
  }, [])

  // Restart timer when session changes
  useEffect(() => {
    if (session?.expiresAt) {
      startTimer(session.expiresAt)
    }
  }, [session?.expiresAt, startTimer])

  // ==========================================================================
  // ERROR HANDLING
  // ==========================================================================

  const handleError = useCallback((err: unknown): string => {
    const message = err instanceof Error ? err.message : 'Error desconocido'
    setError(message)
    console.error('[useWizardSession] Error:', message)
    return message
  }, [])

  // ==========================================================================
  // SESSION LIFECYCLE
  // ==========================================================================

  const createSession = useCallback(
    async (data: WizardSessionCreateRequest): Promise<WizardSession | null> => {
      try {
        setIsLoading(true)
        setError(null)
        const result = await wizardSessionApi.createSession(data)
        setSession(result)
        return result
      } catch (err) {
        handleError(err)
        return null
      } finally {
        setIsLoading(false)
      }
    },
    [handleError]
  )

  const loadSession = useCallback(
    async (sessionId: string): Promise<WizardSession | null> => {
      try {
        setIsLoading(true)
        setError(null)
        const result = await wizardSessionApi.getSession(sessionId)
        setSession(result)
        return result
      } catch (err) {
        handleError(err)
        return null
      } finally {
        setIsLoading(false)
      }
    },
    [handleError]
  )

  const cancelSession = useCallback(
    async (reason?: string): Promise<boolean> => {
      if (!session) return false
      try {
        setIsLoading(true)
        setError(null)
        await wizardSessionApi.cancelSession(session.sessionId, reason)
        setSession(null)
        setTimeRemaining(0)
        if (timerRef.current) {
          clearInterval(timerRef.current)
          timerRef.current = null
        }
        return true
      } catch (err) {
        handleError(err)
        return false
      } finally {
        setIsLoading(false)
      }
    },
    [session, handleError]
  )

  // ==========================================================================
  // DOCUMENT OPERATIONS
  // ==========================================================================

  const previewDocument = useCallback(
    async (
      documentCode: string,
      file: File
    ): Promise<DocumentPreview | null> => {
      if (!session) {
        setError('No hay sesión activa')
        return null
      }
      try {
        // Track per-document upload state (allows parallel uploads)
        setUploadingDocs((prev) => new Set(prev).add(documentCode))
        setError(null)
        const result = await wizardSessionApi.previewDocument(
          session.sessionId,
          documentCode,
          file
        )
        // Update session state with new TTL
        setSession((prev) =>
          prev
            ? {
                ...prev,
                documentsCount: prev.documentsCount + (prev.documentsUploaded.includes(documentCode) ? 0 : 1),
                documentsUploaded: prev.documentsUploaded.includes(documentCode)
                  ? prev.documentsUploaded
                  : [...prev.documentsUploaded, documentCode],
                expiresAt: result.expiresAt,
                ttlSeconds: result.ttlSeconds,
              }
            : null
        )
        return result
      } catch (err) {
        handleError(err)
        return null
      } finally {
        setUploadingDocs((prev) => {
          const next = new Set(prev)
          next.delete(documentCode)
          return next
        })
      }
    },
    [session, handleError]
  )

  const confirmDocument = useCallback(
    async (data: DocumentConfirmRequest): Promise<boolean> => {
      if (!session) {
        setError('No hay sesión activa')
        return false
      }
      try {
        setIsSaving(true)
        setError(null)
        const updated = await wizardSessionApi.confirmDocument(
          session.sessionId,
          data
        )
        setSession(updated)
        return true
      } catch (err) {
        handleError(err)
        return false
      } finally {
        setIsSaving(false)
      }
    },
    [session, handleError]
  )

  const deleteDocument = useCallback(
    async (documentCode: string): Promise<boolean> => {
      if (!session) {
        setError('No hay sesión activa')
        return false
      }
      try {
        setUploadingDocs((prev) => new Set(prev).add(documentCode))
        setError(null)
        const updated = await wizardSessionApi.deleteDocument(
          session.sessionId,
          documentCode
        )
        setSession(updated)
        return true
      } catch (err) {
        handleError(err)
        return false
      } finally {
        setUploadingDocs((prev) => {
          const next = new Set(prev)
          next.delete(documentCode)
          return next
        })
      }
    },
    [session, handleError]
  )

  // ==========================================================================
  // USE VAULT DOCUMENT (Phase 2 — auto-fill from vault)
  // ==========================================================================

  const linkVaultDocument = useCallback(
    async (documentCode: string, vaultDocumentId: string): Promise<boolean> => {
      if (!session) {
        setError('No hay sesion activa')
        return false
      }
      try {
        setUploadingDocs((prev) => new Set(prev).add(documentCode))
        setError(null)
        const updated = await wizardSessionApi.useVaultDocument(
          session.sessionId,
          documentCode,
          vaultDocumentId
        )
        setSession(updated)
        return true
      } catch (err) {
        handleError(err)
        return false
      } finally {
        setUploadingDocs((prev) => {
          const next = new Set(prev)
          next.delete(documentCode)
          return next
        })
      }
    },
    [session, handleError]
  )

  // ==========================================================================
  // FORM DATA
  // ==========================================================================

  const saveFormData = useCallback(
    async (data: FormDataSaveRequest): Promise<boolean> => {
      if (!session) {
        setError('No hay sesión activa')
        return false
      }
      try {
        setIsSaving(true)
        setError(null)
        const updated = await wizardSessionApi.saveFormData(
          session.sessionId,
          data
        )
        setSession(updated)
        return true
      } catch (err) {
        handleError(err)
        return false
      } finally {
        setIsSaving(false)
      }
    },
    [session, handleError]
  )

  // ==========================================================================
  // APPOINTMENT (session-based, before payment)
  // ==========================================================================

  const saveAppointmentData = useCallback(
    async (data: {
      entityLocationId: string
      locationName: string
      city: string
      appointmentDate: string
      appointmentTime: string
      slotConfigId?: string | null
    }): Promise<boolean> => {
      if (!session) {
        setError('No hay sesión activa')
        return false
      }
      try {
        setIsLoading(true)
        setError(null)
        const result = await wizardSessionApi.saveAppointmentSelection(
          session.sessionId,
          data,
        )
        if (result.success) {
          setSession((prev) =>
            prev
              ? {
                  ...prev,
                  appointmentData: {
                    entityLocationId: data.entityLocationId,
                    locationName: data.locationName,
                    city: data.city,
                    appointmentDate: data.appointmentDate,
                    appointmentTime: data.appointmentTime,
                    slotConfigId: data.slotConfigId ?? null,
                  },
                }
              : null
          )
        }
        return result.success
      } catch (err) {
        handleError(err)
        return false
      } finally {
        setIsLoading(false)
      }
    },
    [session, handleError]
  )

  const saveSiteData = useCallback(
    async (data: {
      entityLocationId: string
      locationName: string
      city: string
      entityCode?: string | null
    }): Promise<boolean> => {
      if (!session) {
        setError('No hay sesión activa')
        return false
      }
      try {
        setIsLoading(true)
        setError(null)
        const result = await wizardSessionApi.saveSiteSelection(
          session.sessionId,
          data,
        )
        if (result.success) {
          setSession((prev) =>
            prev
              ? {
                  ...prev,
                  siteSelection: {
                    entityLocationId: data.entityLocationId,
                    locationName: data.locationName,
                    city: data.city,
                    entityCode: data.entityCode ?? null,
                  },
                }
              : null
          )
        }
        return result.success
      } catch (err) {
        handleError(err)
        return false
      } finally {
        setIsLoading(false)
      }
    },
    [session, handleError]
  )

  // ==========================================================================
  // PAYMENT
  // ==========================================================================

  const preparePayment = useCallback(async (): Promise<PreparePaymentResult | null> => {
    if (!session) {
      setError('No hay sesión activa')
      return null
    }
    try {
      setIsLoading(true)
      setError(null)
      const result = await wizardSessionApi.preparePayment(session.sessionId)
      // Update session status if ready
      if (result.readyForPayment) {
        setSession((prev) =>
          prev
            ? {
                ...prev,
                status: WizardSessionStatus.READY_FOR_PAYMENT,
                tariff: result.tariff,
              }
            : null
        )
      }
      return result
    } catch (err) {
      handleError(err)
      return null
    } finally {
      setIsLoading(false)
    }
  }, [session, handleError])

  const persistAndPay = useCallback(
    async (paymentId?: string): Promise<PersistResult | null> => {
      if (!session) {
        setError('No hay sesión activa')
        return null
      }
      try {
        setIsLoading(true)
        setError(null)
        const result = await wizardSessionApi.persistSession(
          session.sessionId,
          paymentId
        )
        if (result.success) {
          setSession((prev) =>
            prev
              ? { ...prev, status: WizardSessionStatus.PERSISTED }
              : null
          )
          // Stop timer - session is done
          if (timerRef.current) {
            clearInterval(timerRef.current)
            timerRef.current = null
          }
        }
        return result
      } catch (err) {
        handleError(err)
        return null
      } finally {
        setIsLoading(false)
      }
    },
    [session, handleError]
  )

  const initiatePayment = useCallback(
    async (
      paymentMethod: string,
      phoneNumber?: string,
      treasuryLocationId?: string
    ): Promise<InitiatePaymentResult | null> => {
      if (!session) {
        setError('No hay sesión activa')
        return null
      }
      try {
        setIsLoading(true)
        setError(null)
        const result = await wizardSessionApi.initiatePayment(
          session.sessionId,
          paymentMethod,
          phoneNumber,
          treasuryLocationId,
        )
        if (result.success) {
          setSession((prev) =>
            prev
              ? { ...prev, status: WizardSessionStatus.PERSISTED }
              : null
          )
          // Stop timer - session is done
          if (timerRef.current) {
            clearInterval(timerRef.current)
            timerRef.current = null
          }
        }
        return result
      } catch (err) {
        const msg = handleError(err)
        return { success: false, error: msg } as InitiatePaymentResult
      } finally {
        setIsLoading(false)
      }
    },
    [session, handleError]
  )

  // ==========================================================================
  // UTILITY
  // ==========================================================================

  const clearError = useCallback(() => setError(null), [])

  const reset = useCallback(() => {
    setSession(null)
    setError(null)
    setTimeRemaining(0)
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
  }, [])

  // ==========================================================================
  // DERIVED STATE
  // ==========================================================================

  const isExpiring = timeRemaining > 0 && timeRemaining <= WARNING_THRESHOLD_SECONDS
  const isExpired =
    timeRemaining <= 0 && session?.status === WizardSessionStatus.EXPIRED

  const isDocumentUploading = useCallback(
    (documentCode: string) => uploadingDocs.has(documentCode),
    [uploadingDocs]
  )

  // ==========================================================================
  // RETURN
  // ==========================================================================

  return {
    // State
    session,
    isLoading,
    isSaving,
    error,

    // Per-document upload tracking
    uploadingDocs,
    isDocumentUploading,

    // TTL
    timeRemaining,
    isExpiring,
    isExpired,

    // Session lifecycle
    createSession,
    loadSession,
    cancelSession,

    // Document operations
    previewDocument,
    confirmDocument,
    deleteDocument,
    linkVaultDocument,

    // Form data
    saveFormData,

    // Appointment
    saveAppointmentData,

    // Site selection
    saveSiteData,

    // Payment
    preparePayment,
    persistAndPay,
    initiatePayment,

    // Utility
    clearError,
    reset,
  }
}
