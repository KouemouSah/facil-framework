/**
 * useBundleWizard — State orchestration for the Bundle Payment wizard.
 *
 * Combines two concerns:
 * 1. Wizard session lifecycle (TTL, document upload) via useWizardSession
 * 2. Bundle business logic (company search, initiation, payment) via bundleWorkflowApi
 */

'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { useWizardSession } from '@/modules/service-requests/hooks'
import { extractApiError, type StructuredApiError } from '@/core/api/errors'
import { bundleWorkflowApi } from '../services/bundle-workflow-api'
import { getBundleErrorEntry } from '../constants/error-catalog'
import type {
  CompanySummary,
  CompanySearchResult,
  MyCompanyWithStatus,
  BundleInitiateResponse,
  BundlePaymentResult,
  ObligationItem,
  ClassifyPreviewResponse,
} from '../types'
import { BundleStep } from '../types'
import type { ProcessingMode } from '@/types/service-bundle'
import type { DocumentPreview } from '@/modules/service-requests/types/wizard-session'

function readBrowserLocale(): 'es' | 'fr' | 'en' {
  if (typeof window === 'undefined') return 'es'
  const seg = window.location.pathname.split('/')[1]
  return seg === 'fr' ? 'fr' : seg === 'en' ? 'en' : 'es'
}

// ── Editable company fields (form_review pattern) ──────────────

export interface EditableCompanyFields {
  legalName: string | null
  registrationNumber: string | null
  nif: string | null
  formaJuridica: string | null
  localidad: string | null
  provincia: string | null
  sector: string | null
  objetoSocial: string | null
}

const EMPTY_FIELDS: EditableCompanyFields = {
  legalName: null, registrationNumber: null, nif: null, formaJuridica: null,
  localidad: null, provincia: null, sector: null, objetoSocial: null,
}

// ── Return Interface ────────────────────────────────────────────

export interface UseBundleWizardReturn {
  // Step navigation
  currentStep: number
  totalSteps: number
  goNext: () => void
  goBack: () => void
  canGoNext: boolean
  canGoBack: boolean

  // Session (from useWizardSession)
  sessionId: string | null
  timeRemaining: number
  isExpiring: boolean
  isExpired: boolean
  createSession: () => Promise<string | null>
  loadSession: (sessionId: string) => Promise<boolean>

  // Step 0: Company identification
  myCompanies: MyCompanyWithStatus[]
  searchResults: CompanySearchResult[]
  selectedCompany: CompanySummary | null
  companyExists: boolean
  isLoadingCompanies: boolean
  isSearching: boolean
  searchCompany: (q: string) => void
  selectCompany: (company: CompanySummary) => void
  clearCompanySelection: () => void
  requestNewCompany: () => void

  // Step 1: Document upload (delegates to useWizardSession)
  documentPreview: DocumentPreview | null
  isUploading: boolean
  uploadDocument: (file: File) => Promise<DocumentPreview | null>
  deleteDocument: () => Promise<void>

  // Step 2: Classification form_review (all fields editable)
  classificationPreview: ClassifyPreviewResponse | null
  selectedZoneId: string | null
  selectedCommerceType: string | null
  editedFields: EditableCompanyFields
  setEditedField: (key: keyof EditableCompanyFields, value: string | null) => void
  setSelectedZoneId: (id: string | null) => void
  setSelectedCommerceType: (type: string | null) => void
  licenseData: BundleInitiateResponse | null
  isInitiating: boolean
  selectedMode: ProcessingMode
  selectedObligationIds: Set<string>
  setSelectedMode: (mode: ProcessingMode) => void
  toggleObligation: (id: string) => void
  selectAllObligations: () => void
  deselectAllObligations: () => void
  loadClassification: () => Promise<void>
  loadObligations: () => Promise<void>

  // Step 3: Payment
  paymentMethod: string | null
  phoneNumber: string
  isPaymentProcessing: boolean
  setPaymentMethod: (method: string) => void
  setPhoneNumber: (phone: string) => void
  submitPayment: () => Promise<BundlePaymentResult | null>

  // Step 4: Confirmation
  paymentResult: BundlePaymentResult | null

  // Global
  isLoading: boolean
  error: string | null
  /** Structured API error with metier code + localized message + CTA hint */
  apiError: StructuredApiError | null
  clearError: () => void
  /** Re-runs the last payment attempt; respects the catalog retry cooldown. */
  retryPayment: () => Promise<BundlePaymentResult | null>
}

// ── Hook ────────────────────────────────────────────────────────

export function useBundleWizard(): UseBundleWizardReturn {
  // -- Wizard session (for docs + TTL) --
  const wizardSession = useWizardSession()

  // -- Step state --
  const [currentStep, setCurrentStep] = useState(BundleStep.COMPANY_IDENTIFICATION)

  // -- Step 0: Company --
  const [myCompanies, setMyCompanies] = useState<MyCompanyWithStatus[]>([])
  const [searchResults, setSearchResults] = useState<CompanySearchResult[]>([])
  const [selectedCompany, setSelectedCompany] = useState<CompanySummary | null>(null)
  const [companyExists, setCompanyExists] = useState(true)
  const [isLoadingCompanies, setIsLoadingCompanies] = useState(false)
  const [isSearching, setIsSearching] = useState(false)
  const searchDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const searchSeqRef = useRef(0)
  const paymentLockRef = useRef(false) // Prevents double-click on payment

  // -- Step 1: Document --
  const [documentPreview, setDocumentPreview] = useState<DocumentPreview | null>(null)

  // -- Step 2: Obligations --
  const [licenseData, setLicenseData] = useState<BundleInitiateResponse | null>(null)
  const [isInitiating, setIsInitiating] = useState(false)
  const [selectedMode, setSelectedMode] = useState<ProcessingMode>('per_line')
  const [selectedObligationIds, setSelectedObligationIds] = useState<Set<string>>(new Set())

  // -- Step 3: Payment --
  const [paymentMethod, setPaymentMethod] = useState<string | null>(null)
  const [phoneNumber, setPhoneNumber] = useState('')
  const [isPaymentProcessing, setIsPaymentProcessing] = useState(false)

  // -- Step 4: Confirmation --
  const [paymentResult, setPaymentResult] = useState<BundlePaymentResult | null>(null)

  // -- Classification preview --
  const [classificationPreview, setClassificationPreview] = useState<ClassifyPreviewResponse | null>(null)
  const [selectedZoneId, setSelectedZoneId] = useState<string | null>(null)
  const [selectedCommerceType, setSelectedCommerceType] = useState<string | null>(null)
  const [editedFields, setEditedFields] = useState<EditableCompanyFields>({ ...EMPTY_FIELDS })

  const setEditedField = useCallback((key: keyof EditableCompanyFields, value: string | null) => {
    setEditedFields(prev => ({ ...prev, [key]: value }))
  }, [])

  // -- Global --
  const [error, setError] = useState<string | null>(null)
  const [apiError, setApiError] = useState<StructuredApiError | null>(null)
  const lastRetryAtRef = useRef<number>(0)

  // Convert any caught error into a StructuredApiError and populate both
  // the legacy `error: string` state (backwards compat) and the new
  // `apiError` state (structured, used by BundleErrorAlert).
  const reportError = useCallback((e: unknown) => {
    const structured = extractApiError(e, readBrowserLocale())
    setApiError(structured)
    setError(structured.message)
  }, [])

  // ── Session lifecycle ───────────────────────────────────────

  const createSession = useCallback(async (): Promise<string | null> => {
    try {
      const session = await wizardSession.createSession({
        workflow_code: 'BUNDLE_PAYMENT',
        solicitud_type: 'expedicion',
      })
      return session?.sessionId ?? null
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error creating session')
      return null
    }
  }, [wizardSession])

  const loadSession = useCallback(async (sessionId: string): Promise<boolean> => {
    try {
      const session = await wizardSession.loadSession(sessionId)
      return session !== null
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error loading session')
      return false
    }
  }, [wizardSession])

  // ── Step 0: Load my companies on mount ──────────────────────

  const loadMyCompanies = useCallback(async () => {
    setIsLoadingCompanies(true)
    try {
      const resp = await bundleWorkflowApi.getMyCompanies()
      setMyCompanies(resp.companies)
    } catch (e) {
      console.error('[BundleWizard] Failed to load my companies:', e)
    } finally {
      setIsLoadingCompanies(false)
    }
  }, [])

  useEffect(() => {
    loadMyCompanies()
    // Cleanup debounce timer on unmount
    return () => {
      if (searchDebounceRef.current) clearTimeout(searchDebounceRef.current)
    }
  }, [loadMyCompanies])

  // ── Step 0: Search ──────────────────────────────────────────

  const searchCompany = useCallback((q: string) => {
    if (searchDebounceRef.current) clearTimeout(searchDebounceRef.current)

    if (!q || q.length < 2) {
      setSearchResults([])
      setIsSearching(false)
      return
    }

    setIsSearching(true)
    const seq = ++searchSeqRef.current

    searchDebounceRef.current = setTimeout(async () => {
      try {
        const resp = await bundleWorkflowApi.searchCompany(q)
        // Discard stale responses
        if (seq === searchSeqRef.current) {
          setSearchResults(resp.companies)
        }
      } catch (e) {
        console.error('[BundleWizard] Search error:', e)
      } finally {
        if (seq === searchSeqRef.current) setIsSearching(false)
      }
    }, 300)
  }, [])

  const selectCompany = useCallback((company: CompanySummary) => {
    setSelectedCompany(company)
    setCompanyExists(true)
    setSearchResults([])
    setError(null)
  }, [])

  const clearCompanySelection = useCallback(() => {
    setSelectedCompany(null)
    setCompanyExists(true)
    setLicenseData(null)
    setSelectedObligationIds(new Set())
  }, [])

  const requestNewCompany = useCallback(() => {
    setCompanyExists(false)
    setSelectedCompany(null)
    setCurrentStep(BundleStep.DOCUMENT_UPLOAD)
  }, [])

  // ── Step 1: Document upload ─────────────────────────────────

  const uploadDocument = useCallback(async (file: File): Promise<DocumentPreview | null> => {
    if (!wizardSession.session) return null
    try {
      const preview = await wizardSession.previewDocument('certificado_padron', file)
      setDocumentPreview(preview)
      return preview
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error uploading document')
      return null
    }
  }, [wizardSession])

  const deleteDocument = useCallback(async () => {
    if (!wizardSession.session) return
    try {
      await wizardSession.deleteDocument('certificado_padron')
      setDocumentPreview(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error deleting document')
    }
  }, [wizardSession])

  // ── Step 2: Load obligations ────────────────────────────────

  // ── Step: Classification (zone + category preview) ─────────────
  const loadClassification = useCallback(async () => {
    if (!documentPreview) return
    setIsInitiating(true)
    setError(null)
    try {
      setApiError(null)
      const extraction = documentPreview.extraction || {}
      const preview = await bundleWorkflowApi.classifyPreview(
        extraction, selectedZoneId || undefined,
      )
      setClassificationPreview(preview)

      // Auto-set zone if resolved and user hasn't manually selected
      if (preview.zoneResolved && preview.zone && !selectedZoneId) {
        setSelectedZoneId(preview.zone.id)
      }
      // Auto-set commerce_type if classified with high confidence
      if (preview.classification?.commerceType && !selectedCommerceType) {
        setSelectedCommerceType(preview.classification.commerceType)
      }
      // Auto-fill ALL editable fields from extraction (user can correct)
      const ed = preview.extractedData
      if (ed) {
        setEditedFields(prev => ({
          legalName: prev.legalName || ed.legalName || null,
          registrationNumber: prev.registrationNumber || ed.registrationNumber || null,
          nif: prev.nif || ed.nif || null,
          formaJuridica: prev.formaJuridica || ed.formaJuridica || null,
          localidad: prev.localidad || ed.localidad || null,
          provincia: prev.provincia || ed.provincia || null,
          sector: prev.sector || ed.sector || null,
          objetoSocial: prev.objetoSocial || ed.objetoSocial || null,
        }))
      }
    } catch (e) {
      reportError(e)
    } finally {
      setIsInitiating(false)
    }
  }, [documentPreview, selectedZoneId, selectedCommerceType, reportError])

  // Re-fetch classification when user changes zone (to get categories for that zone)
  useEffect(() => {
    if (currentStep === BundleStep.CLASSIFICATION && selectedZoneId && documentPreview) {
      loadClassification()
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedZoneId])

  // ── Step: Load obligations (initiate workflow) ────────────────
  const loadObligations = useCallback(async () => {
    setIsInitiating(true)
    setError(null)
    setApiError(null)
    try {
      let result: BundleInitiateResponse

      if (companyExists && selectedCompany) {
        // Existing company → initiate directly
        result = await bundleWorkflowApi.initiate(selectedCompany.id)
      } else if (documentPreview) {
        const extraction = { ...(documentPreview.extraction || {}) }
        // Inject ALL user-edited fields into extraction
        // (overrides OCR values with user corrections)
        const ef = editedFields
        const empresaObj = (extraction.empresa || extraction) as Record<string, unknown>
        const ubicacionObj = (extraction.ubicacion || extraction) as Record<string, unknown>
        const actividadObj = (extraction.actividad || extraction) as Record<string, unknown>
        if (ef.legalName) empresaObj.denominacion_social = ef.legalName
        if (ef.registrationNumber) empresaObj.numero_registro = ef.registrationNumber
        if (ef.nif) empresaObj.nif = ef.nif
        if (ef.formaJuridica) empresaObj.forma_juridica = ef.formaJuridica
        if (ef.localidad) ubicacionObj.localidad = ef.localidad
        if (ef.provincia) ubicacionObj.provincia = ef.provincia
        if (ef.sector) actividadObj.sector = ef.sector
        if (ef.objetoSocial) actividadObj.objeto_social = ef.objetoSocial

        // Zone and category must be selected (from CLASSIFICATION step)
        const zoneOverride = selectedZoneId || classificationPreview?.zone?.id || undefined
        const categoryOverride = selectedCommerceType || classificationPreview?.classification?.commerceType || undefined

        result = await bundleWorkflowApi.initiateFromUpload(
          extraction, undefined, zoneOverride, categoryOverride,
        )
      } else {
        throw new Error('No company selected and no document uploaded')
      }

      setLicenseData(result)

      // Auto-select all payable obligations
      const payableIds = result.obligations
        .filter((o: ObligationItem) => o.isPayable)
        .map((o: ObligationItem) => o.id)
      setSelectedObligationIds(new Set(payableIds))

      // If company was created from upload, update selectedCompany
      if (result.company) {
        setSelectedCompany(result.company)
        setCompanyExists(true)
      }
    } catch (e) {
      reportError(e)
    } finally {
      setIsInitiating(false)
    }
  }, [companyExists, selectedCompany, documentPreview, classificationPreview, selectedZoneId, selectedCommerceType, editedFields, reportError])

  // ── Step 2: Obligation selection ────────────────────────────

  const toggleObligation = useCallback((id: string) => {
    setSelectedObligationIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }, [])

  const selectAllObligations = useCallback(() => {
    if (!licenseData) return
    const payableIds = licenseData.obligations
      .filter(o => o.isPayable)
      .map(o => o.id)
    setSelectedObligationIds(new Set(payableIds))
  }, [licenseData])

  const deselectAllObligations = useCallback(() => {
    setSelectedObligationIds(new Set())
  }, [])

  const handleSetSelectedMode = useCallback((mode: ProcessingMode) => {
    setSelectedMode(mode)
    if (mode === 'consolidated' && licenseData) {
      // Auto-select all payable in consolidated mode
      const payableIds = licenseData.obligations
        .filter(o => o.isPayable)
        .map(o => o.id)
      setSelectedObligationIds(new Set(payableIds))
    }
  }, [licenseData])

  // ── Step 3: Payment ─────────────────────────────────────────

  const submitPayment = useCallback(async (): Promise<BundlePaymentResult | null> => {
    if (!licenseData || !paymentMethod) return null
    // Prevent double-click (useState is async, ref is sync)
    if (paymentLockRef.current) return null
    paymentLockRef.current = true

    setIsPaymentProcessing(true)
    setError(null)
    setApiError(null)

    try {
      const result = await bundleWorkflowApi.initiatePayment({
        licenseId: licenseData.licenseId,
        processingMode: selectedMode,
        paymentMethod,
        selectedObligationIds: Array.from(selectedObligationIds),
        phoneNumber: paymentMethod === 'mobile_money' ? phoneNumber : undefined,
        wizardSessionId: wizardSession.session?.sessionId,
      })

      setPaymentResult(result)

      if (result.redirectUrl) {
        // BANGE redirect
        window.location.href = result.redirectUrl
        return result
      }

      // Cash/check → advance to confirmation
      setCurrentStep(BundleStep.CONFIRMATION)
      return result
    } catch (e) {
      reportError(e)
      return null
    } finally {
      setIsPaymentProcessing(false)
      paymentLockRef.current = false
    }
  }, [
    licenseData, paymentMethod, selectedMode,
    selectedObligationIds, phoneNumber, wizardSession.session,
    reportError,
  ])

  const retryPayment = useCallback(async (): Promise<BundlePaymentResult | null> => {
    // Enforce the catalog cooldown — catalogs like PAYMENT_ALREADY_IN_PROGRESS
    // have 5s cooldowns so users don't hammer the server.
    if (apiError) {
      const entry = getBundleErrorEntry(apiError.code)
      const cooldown = entry.retryCooldownMs ?? 0
      const elapsed = Date.now() - lastRetryAtRef.current
      if (cooldown > 0 && elapsed < cooldown) {
        // Silently no-op until the cooldown expires — the UI button stays
        // enabled and the catalog hint already communicates the wait.
        return null
      }
    }
    lastRetryAtRef.current = Date.now()
    return submitPayment()
  }, [apiError, submitPayment])

  // ── Navigation ──────────────────────────────────────────────

  const canGoNext = (() => {
    switch (currentStep) {
      case BundleStep.COMPANY_IDENTIFICATION:
        return selectedCompany !== null
      case BundleStep.DOCUMENT_UPLOAD:
        return documentPreview !== null || companyExists
      case BundleStep.CLASSIFICATION:
        // Classification step: registration_number + zone + category required
        return !!editedFields.registrationNumber
          && !!editedFields.legalName
          && !!editedFields.localidad
          && !!selectedZoneId && !!selectedCommerceType
      case BundleStep.OBLIGATIONS_REVIEW:
        return licenseData !== null &&
          !licenseData.alreadyComplete &&
          selectedObligationIds.size > 0
      case BundleStep.PAYMENT:
        return paymentMethod !== null &&
          (paymentMethod !== 'mobile_money' || phoneNumber.length >= 9)
      default:
        return false
    }
  })()

  const canGoBack = currentStep > BundleStep.COMPANY_IDENTIFICATION &&
    currentStep < BundleStep.CONFIRMATION

  const goNext = useCallback(() => {
    if (currentStep === BundleStep.COMPANY_IDENTIFICATION && companyExists) {
      // Existing company: skip document upload + classification → obligations
      loadObligations()
      setCurrentStep(BundleStep.OBLIGATIONS_REVIEW)
    } else if (currentStep === BundleStep.DOCUMENT_UPLOAD) {
      // After document upload → load classification preview
      loadClassification()
      setCurrentStep(BundleStep.CLASSIFICATION)
    } else if (currentStep === BundleStep.CLASSIFICATION) {
      // After zone + category confirmed → load obligations
      loadObligations()
      setCurrentStep(BundleStep.OBLIGATIONS_REVIEW)
    } else if (currentStep === BundleStep.PAYMENT) {
      // Payment handles its own navigation via submitPayment
      return
    } else {
      setCurrentStep(prev => Math.min(prev + 1, BundleStep.CONFIRMATION))
    }
  }, [currentStep, companyExists, loadObligations, loadClassification])

  const goBack = useCallback(() => {
    if (currentStep === BundleStep.OBLIGATIONS_REVIEW && companyExists) {
      // Existing company: skip back to identification
      setCurrentStep(BundleStep.COMPANY_IDENTIFICATION)
    } else if (currentStep === BundleStep.OBLIGATIONS_REVIEW && !companyExists) {
      // New company: go back to classification (not document upload)
      setCurrentStep(BundleStep.CLASSIFICATION)
    } else {
      setCurrentStep(prev => Math.max(prev - 1, BundleStep.COMPANY_IDENTIFICATION))
    }
  }, [currentStep, companyExists])

  const clearError = useCallback(() => {
    setError(null)
    setApiError(null)
  }, [])

  // ── Return ──────────────────────────────────────────────────

  return {
    currentStep,
    totalSteps: 5,
    goNext,
    goBack,
    canGoNext,
    canGoBack,

    sessionId: wizardSession.session?.sessionId ?? null,
    timeRemaining: wizardSession.timeRemaining,
    isExpiring: wizardSession.isExpiring,
    isExpired: wizardSession.isExpired,
    createSession,
    loadSession,

    myCompanies,
    searchResults,
    selectedCompany,
    companyExists,
    isLoadingCompanies,
    isSearching,
    searchCompany,
    selectCompany,
    clearCompanySelection,
    requestNewCompany,

    documentPreview,
    isUploading: wizardSession.isDocumentUploading('certificado_padron'),
    uploadDocument,
    deleteDocument,

    classificationPreview,
    selectedZoneId,
    selectedCommerceType,
    editedFields,
    setEditedField,
    setSelectedZoneId,
    setSelectedCommerceType,
    licenseData,
    isInitiating,
    selectedMode,
    selectedObligationIds,
    setSelectedMode: handleSetSelectedMode,
    toggleObligation,
    selectAllObligations,
    deselectAllObligations,
    loadClassification,
    loadObligations,

    paymentMethod,
    phoneNumber,
    isPaymentProcessing,
    setPaymentMethod,
    setPhoneNumber,
    submitPayment,

    paymentResult,

    isLoading: wizardSession.isLoading || isLoadingCompanies || isInitiating || isPaymentProcessing,
    error: error || wizardSession.error,
    apiError,
    clearError,
    retryPayment,
  }
}
