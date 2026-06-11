/**
 * useServiceRequests Hook
 * State management for service requests following useSupport pattern
 */

import { useState, useCallback, useRef } from 'react'
import { serviceRequestsApi } from '../services/api'
import type { FilterOptions } from '../services/api'
import type {
  ServiceRequest,
  ServiceRequestCreate,
  ServiceRequestUpdate,
  ServiceRequestDocument,
  ServiceRequestFilters,
  WorkflowConfig,
  WorkflowStep,
  StepSubmitRequest,
  ValidationResult,
  TariffCalculation,
  DocumentExtractionPreview,
  DocumentValidationResponse,
  FormDataResponse,
  CitizenSummaryResponse,
  EntityLocation,
  AvailableSlot,
  AppointmentHoldStatus,
  PaymentMethodsResponse,
  PaymentInitiateResult,
} from '../types'

// ============================================================================
// RETURN TYPE INTERFACE
// ============================================================================

export interface UseServiceRequestsReturn {
  // State
  requests: ServiceRequest[]
  currentRequest: ServiceRequest | null
  workflow: WorkflowConfig | null
  currentStep: WorkflowStep | null
  documents: ServiceRequestDocument[]
  validationResults: ValidationResult[]
  tariff: TariffCalculation | null
  isLoading: boolean
  isSaving: boolean
  error: string | null
  pagination: {
    page: number
    pageSize: number
    total: number
    totalPages: number
  }
  filters: ServiceRequestFilters
  filterOptions: FilterOptions | null
  loadFilterOptions: () => Promise<void>

  // Workflow actions
  loadWorkflows: (category?: string) => Promise<WorkflowConfig[]>
  startWorkflow: (data: ServiceRequestCreate) => Promise<ServiceRequest | null>
  loadRequest: (requestId: string) => Promise<void>

  // Step actions
  submitStep: (stepData: StepSubmitRequest) => Promise<boolean>
  previousStep: () => Promise<boolean>
  saveStepData: (stepId: string, data: Record<string, unknown>) => Promise<boolean>
  validateStep: (stepId: string, data: Record<string, unknown>) => Promise<ValidationResult[]>

  // Document actions (legacy - direct upload)
  uploadDocument: (documentCode: string, file: File, face?: string) => Promise<ServiceRequestDocument | null>
  deleteDocument: (documentId: string) => Promise<boolean>
  retryExtraction: (documentId: string) => Promise<boolean>
  updateExtractedData: (documentId: string, data: Record<string, unknown>) => Promise<boolean>
  loadDocuments: () => Promise<void>

  // Document actions (NEW - preview/validate two-step flow)
  previewDocument: (documentCode: string, file: File, existingExtractions?: Record<string, Record<string, unknown>>) => Promise<DocumentExtractionPreview | null>
  validateDocument: (previewId: string, confirmedData: Record<string, unknown>, userNotes?: string) => Promise<DocumentValidationResponse | null>
  currentPreview: DocumentExtractionPreview | null
  clearPreview: () => void

  // Form data and summary
  getFormData: () => Promise<FormDataResponse | null>
  getCitizenSummary: () => Promise<CitizenSummaryResponse | null>
  downloadSummaryPDF: (language?: string) => Promise<void>

  // Validation & Tariff
  validateDocuments: () => Promise<ValidationResult[]>
  calculateTariff: (formData?: Record<string, unknown>) => Promise<TariffCalculation | null>

  // Submission
  submitRequest: () => Promise<boolean>
  prepareForPayment: () => Promise<{ success: boolean; errorMessage?: string }>
  getPaymentMethods: () => Promise<PaymentMethodsResponse | null>
  initiatePayment: (method: string, phone?: string) => Promise<PaymentInitiateResult | null>
  checkPaymentStatus: () => Promise<{ status: string; paid: boolean } | null>

  // List actions
  loadMyRequests: (page?: number, pageSize?: number, filtersOverride?: ServiceRequestFilters) => Promise<void>
  loadAllRequests: (page?: number, pageSize?: number) => Promise<void>
  updateRequest: (data: ServiceRequestUpdate) => Promise<ServiceRequest | null>
  deleteRequest: () => Promise<boolean>
  deleteRequestById: (requestId: string) => Promise<boolean>

  // Agent actions
  approveRequest: (notes?: string) => Promise<boolean>
  rejectRequest: (reason: string, notes?: string) => Promise<boolean>
  requestAdditionalInfo: (message: string, requiredDocs?: string[]) => Promise<boolean>
  scheduleAppointment: (date: string, time: string, location: string) => Promise<boolean>
  addAgentNote: (note: string) => Promise<boolean>

  // Appointment actions (citizen-first flow)
  // Migration 030: Uses entityLocationId FK instead of locationName
  getAppointmentLocations: (requestId: string) => Promise<{ entityCode: string; locations: EntityLocation[]; count: number }>
  getAvailableDays: (requestId: string, entityLocationId: string, fromDate?: string, toDate?: string) => Promise<{ days: Array<{ date: string; timeSlotCount: number; totalSlotsRemaining: number }>; count: number; minDate?: string }>
  getAppointmentSlots: (requestId: string, entityLocationId: string, fromDate?: string, limit?: number) => Promise<{ entityCode: string; locationName: string; fromDate: string; slots: AvailableSlot[]; count: number; hasAvailability: boolean }>
  holdAppointmentSlot: (requestId: string, data: { entityLocationId: string; slotConfigId?: string; appointmentDate: string; appointmentTime: string }) => Promise<{ success: boolean; holdId?: string; expiresInSeconds: number; expiresAt?: string; error?: string }>
  getAppointmentHoldStatus: (requestId: string) => Promise<AppointmentHoldStatus>
  releaseAppointmentHold: (requestId: string) => Promise<{ success: boolean; message: string }>
  submitWithoutAppointment: (requestId: string, entityLocationId: string) => Promise<{ success: boolean; locationName?: string; message: string; error?: string }>
  confirmAppointmentHold: (requestId: string) => Promise<{ success: boolean; appointmentDate?: string; appointmentTime?: string; locationName?: string; error?: string }>

  // Utility
  clearError: () => void
  setFilters: (filters: ServiceRequestFilters) => void
  setPage: (page: number) => void
  reset: () => void
}

// ============================================================================
// HOOK IMPLEMENTATION
// ============================================================================

export function useServiceRequests(): UseServiceRequestsReturn {
  // State
  const [requests, setRequests] = useState<ServiceRequest[]>([])
  const [currentRequest, setCurrentRequest] = useState<ServiceRequest | null>(null)
  const [workflow, setWorkflow] = useState<WorkflowConfig | null>(null)
  const [currentStep, setCurrentStep] = useState<WorkflowStep | null>(null)
  const [documents, setDocuments] = useState<ServiceRequestDocument[]>([])
  const [validationResults, setValidationResults] = useState<ValidationResult[]>([])
  const [tariff, setTariff] = useState<TariffCalculation | null>(null)
  const [currentPreview, setCurrentPreview] = useState<DocumentExtractionPreview | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [filters, setFilters] = useState<ServiceRequestFilters>({})
  const [pagination, setPagination] = useState({
    page: 1,
    pageSize: 20,
    total: 0,
    totalPages: 0,
  })
  const [filterOptions, setFilterOptions] = useState<FilterOptions | null>(null)

  // Sequence counter to discard stale responses from rapid filter changes
  const listRequestSeqRef = useRef(0)

  // =========================================================================
  // HELPER FUNCTIONS
  // =========================================================================

  const handleError = useCallback((err: unknown) => {
    const message = err instanceof Error ? err.message : 'An error occurred'
    setError(message)
    // Log with stack trace to identify where the error is coming from
    console.error('[ServiceRequests] Error set:', message)
    console.error('[ServiceRequests] Stack:', new Error().stack)
  }, [])

  const updateCurrentStep = useCallback((request: ServiceRequest, wf: WorkflowConfig) => {
    const step = wf.steps.find(s => s.stepNumber === request.currentStep)
    setCurrentStep(step || null)
  }, [])

  // =========================================================================
  // FILTER OPTIONS
  // =========================================================================

  const loadFilterOptions = useCallback(async (): Promise<void> => {
    try {
      const options = await serviceRequestsApi.getFilterOptions()
      setFilterOptions(options)
    } catch (err) {
      console.error('[ServiceRequests] Failed to load filter options:', err)
    }
  }, [])

  // =========================================================================
  // WORKFLOW ACTIONS
  // =========================================================================

  const loadWorkflows = useCallback(async (category?: string): Promise<WorkflowConfig[]> => {
    try {
      setIsLoading(true)
      setError(null)
      return await serviceRequestsApi.getWorkflows(category)
    } catch (err) {
      handleError(err)
      return []
    } finally {
      setIsLoading(false)
    }
  }, [handleError])

  const startWorkflow = useCallback(async (data: ServiceRequestCreate): Promise<ServiceRequest | null> => {
    try {
      setIsLoading(true)
      setError(null)
      const response = await serviceRequestsApi.startWorkflow(data)
      setCurrentRequest(response.request)
      setWorkflow(response.workflow)
      setCurrentStep(response.currentStepConfig)
      setDocuments([])
      setValidationResults([])
      setTariff(null)
      return response.request
    } catch (err) {
      handleError(err)
      return null
    } finally {
      setIsLoading(false)
    }
  }, [handleError])

  const loadRequest = useCallback(async (requestId: string): Promise<void> => {
    console.log('[ServiceRequests] loadRequest called for:', requestId)
    try {
      setIsLoading(true)
      setError(null)

      const [request, docs] = await Promise.all([
        serviceRequestsApi.getRequest(requestId),
        serviceRequestsApi.getDocuments(requestId),
      ])

      setCurrentRequest(request)
      setDocuments(docs)

      // Load workflow config
      const wf = await serviceRequestsApi.getWorkflowSteps(request.workflowCode, request.subType)
      setWorkflow(wf)
      updateCurrentStep(request, wf)
      console.log('[ServiceRequests] loadRequest completed successfully')
    } catch (err) {
      console.error('[ServiceRequests] loadRequest failed:', err)
      handleError(err)
    } finally {
      setIsLoading(false)
    }
  }, [handleError, updateCurrentStep])

  // =========================================================================
  // STEP ACTIONS
  // =========================================================================

  const submitStep = useCallback(async (stepData: StepSubmitRequest): Promise<boolean> => {
    if (!currentRequest) return false

    try {
      setIsSaving(true)
      setError(null)
      const response = await serviceRequestsApi.submitStep(currentRequest.id, stepData)
      setCurrentRequest(response.request)
      setValidationResults(response.validationResults || [])

      if (response.nextStep) {
        setCurrentStep(response.nextStep)
      }

      return true
    } catch (err) {
      handleError(err)
      return false
    } finally {
      setIsSaving(false)
    }
  }, [currentRequest, handleError])

  const previousStep = useCallback(async (): Promise<boolean> => {
    if (!currentRequest) return false

    try {
      setIsSaving(true)
      setError(null)
      const response = await serviceRequestsApi.previousStep(currentRequest.id)
      setCurrentRequest(response.request)

      if (response.nextStep) {
        setCurrentStep(response.nextStep)
      }

      return true
    } catch (err) {
      handleError(err)
      return false
    } finally {
      setIsSaving(false)
    }
  }, [currentRequest, handleError])

  const saveStepData = useCallback(async (
    stepId: string,
    data: Record<string, unknown>
  ): Promise<boolean> => {
    console.log('[ServiceRequests] saveStepData called:', { stepId, data })
    if (!currentRequest) {
      console.warn('[ServiceRequests] saveStepData: no currentRequest')
      return false
    }

    try {
      setIsSaving(true)
      setError(null)
      // Pass existing formData to avoid extra API call
      const existingFormData = currentRequest.formData || {}
      console.log('[ServiceRequests] saveStepData: calling API...')
      const request = await serviceRequestsApi.saveStepData(
        currentRequest.id,
        stepId,
        data,
        existingFormData
      )
      console.log('[ServiceRequests] saveStepData: API success, updating state')
      setCurrentRequest(request)
      return true
    } catch (err) {
      console.error('[ServiceRequests] saveStepData failed:', err)
      handleError(err)
      return false
    } finally {
      setIsSaving(false)
    }
  }, [currentRequest, handleError])

  const validateStep = useCallback(async (
    stepId: string,
    data: Record<string, unknown>
  ): Promise<ValidationResult[]> => {
    if (!currentRequest) return []

    try {
      const results = await serviceRequestsApi.validateStep(currentRequest.id, stepId, data)
      setValidationResults(results)
      return results
    } catch (err) {
      handleError(err)
      return []
    }
  }, [currentRequest, handleError])

  // =========================================================================
  // DOCUMENT ACTIONS
  // =========================================================================

  const uploadDocument = useCallback(async (
    documentCode: string,
    file: File,
    face?: string
  ): Promise<ServiceRequestDocument | null> => {
    if (!currentRequest) return null

    try {
      setIsSaving(true)
      setError(null)
      const response = await serviceRequestsApi.uploadDocument(
        currentRequest.id,
        documentCode,
        file,
        face
      )
      setDocuments(prev => [...prev, response.document])
      return response.document
    } catch (err) {
      handleError(err)
      return null
    } finally {
      setIsSaving(false)
    }
  }, [currentRequest, handleError])

  const deleteDocument = useCallback(async (documentId: string): Promise<boolean> => {
    if (!currentRequest) return false

    try {
      setIsSaving(true)
      setError(null)
      await serviceRequestsApi.deleteDocument(currentRequest.id, documentId)
      setDocuments(prev => prev.filter(d => d.id !== documentId))
      return true
    } catch (err) {
      handleError(err)
      return false
    } finally {
      setIsSaving(false)
    }
  }, [currentRequest, handleError])

  const retryExtraction = useCallback(async (documentId: string): Promise<boolean> => {
    if (!currentRequest) return false

    try {
      setIsSaving(true)
      setError(null)
      const doc = await serviceRequestsApi.retryExtraction(currentRequest.id, documentId)
      setDocuments(prev => prev.map(d => d.id === documentId ? doc : d))
      return true
    } catch (err) {
      handleError(err)
      return false
    } finally {
      setIsSaving(false)
    }
  }, [currentRequest, handleError])

  const updateExtractedData = useCallback(async (
    documentId: string,
    data: Record<string, unknown>
  ): Promise<boolean> => {
    if (!currentRequest) return false

    try {
      setIsSaving(true)
      setError(null)
      const doc = await serviceRequestsApi.updateExtractedData(
        currentRequest.id,
        documentId,
        data
      )
      setDocuments(prev => prev.map(d => d.id === documentId ? doc : d))
      return true
    } catch (err) {
      handleError(err)
      return false
    } finally {
      setIsSaving(false)
    }
  }, [currentRequest, handleError])

  const loadDocuments = useCallback(async (): Promise<void> => {
    if (!currentRequest) return

    try {
      setIsLoading(true)
      const docs = await serviceRequestsApi.getDocuments(currentRequest.id)
      setDocuments(docs)
    } catch (err) {
      handleError(err)
    } finally {
      setIsLoading(false)
    }
  }, [currentRequest, handleError])

  // =========================================================================
  // DOCUMENT PREVIEW/VALIDATE (NEW TWO-STEP FLOW)
  // =========================================================================

  const previewDocument = useCallback(async (
    documentCode: string,
    file: File,
    existingExtractions?: Record<string, Record<string, unknown>>
  ): Promise<DocumentExtractionPreview | null> => {
    if (!currentRequest) return null

    try {
      setIsSaving(true)
      setError(null)
      const preview = await serviceRequestsApi.previewDocumentExtraction(
        currentRequest.id,
        documentCode,
        file,
        existingExtractions
      )
      setCurrentPreview(preview)
      return preview
    } catch (err) {
      handleError(err)
      return null
    } finally {
      setIsSaving(false)
    }
  }, [currentRequest, handleError, setCurrentPreview])

  const validateDocument = useCallback(async (
    previewId: string,
    confirmedData: Record<string, unknown>,
    userNotes?: string
  ): Promise<DocumentValidationResponse | null> => {
    if (!currentRequest) return null

    try {
      setIsSaving(true)
      setError(null)
      const response = await serviceRequestsApi.validateAndUploadDocument(
        currentRequest.id,
        previewId,
        confirmedData,
        userNotes
      )
      // Clear preview after successful validation
      setCurrentPreview(null)
      // Refresh documents list
      const docs = await serviceRequestsApi.getDocuments(currentRequest.id)
      setDocuments(docs)
      return response
    } catch (err) {
      handleError(err)
      return null
    } finally {
      setIsSaving(false)
    }
  }, [currentRequest, handleError, setCurrentPreview])

  const clearPreview = useCallback(() => {
    setCurrentPreview(null)
  }, [setCurrentPreview])

  // =========================================================================
  // FORM DATA AND CITIZEN SUMMARY
  // =========================================================================

  const getFormData = useCallback(async (): Promise<FormDataResponse | null> => {
    if (!currentRequest) return null

    try {
      setIsLoading(true)
      setError(null)
      return await serviceRequestsApi.getFormData(currentRequest.id)
    } catch (err) {
      handleError(err)
      return null
    } finally {
      setIsLoading(false)
    }
  }, [currentRequest, handleError])

  const getCitizenSummary = useCallback(async (): Promise<CitizenSummaryResponse | null> => {
    if (!currentRequest) return null

    try {
      setIsLoading(true)
      setError(null)
      return await serviceRequestsApi.getCitizenSummary(currentRequest.id)
    } catch (err) {
      handleError(err)
      return null
    } finally {
      setIsLoading(false)
    }
  }, [currentRequest, handleError])

  const downloadSummaryPDF = useCallback(async (language: string = 'es'): Promise<void> => {
    if (!currentRequest) return
    try {
      const blob = await serviceRequestsApi.downloadSummaryPDF(currentRequest.id, language)
      // Create download link
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `resumen_${currentRequest.requestNumber || currentRequest.id}.pdf`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      window.URL.revokeObjectURL(url)
    } catch (err) {
      handleError(err)
    }
  }, [currentRequest, handleError])


  // =========================================================================
  // VALIDATION & TARIFF
  // =========================================================================

  const validateDocuments = useCallback(async (): Promise<ValidationResult[]> => {
    if (!currentRequest) return []

    try {
      const results = await serviceRequestsApi.validateDocuments(currentRequest.id)
      setValidationResults(results)
      return results
    } catch (err) {
      handleError(err)
      return []
    }
  }, [currentRequest, handleError])

  const calculateTariff = useCallback(async (
    formData?: Record<string, unknown>
  ): Promise<TariffCalculation | null> => {
    if (!currentRequest) return null

    try {
      const calc = await serviceRequestsApi.calculateTariff(currentRequest.id, formData)
      setTariff(calc)
      return calc
    } catch (err) {
      handleError(err)
      return null
    }
  }, [currentRequest, handleError])

  // =========================================================================
  // SUBMISSION & PAYMENT
  // =========================================================================

  const submitRequest = useCallback(async (): Promise<boolean> => {
    if (!currentRequest) return false

    try {
      setIsSaving(true)
      setError(null)
      const request = await serviceRequestsApi.submitRequest(currentRequest.id)
      setCurrentRequest(request)
      return true
    } catch (err) {
      handleError(err)
      return false
    } finally {
      setIsSaving(false)
    }
  }, [currentRequest, handleError])

  const prepareForPayment = useCallback(async (): Promise<{ success: boolean; errorMessage?: string }> => {
    if (!currentRequest) return { success: false, errorMessage: 'No request loaded' }

    try {
      setIsSaving(true)
      setError(null)
      const request = await serviceRequestsApi.prepareForPayment(currentRequest.id)
      setCurrentRequest(request)
      return { success: true }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'An error occurred'
      handleError(err)
      return { success: false, errorMessage }
    } finally {
      setIsSaving(false)
    }
  }, [currentRequest, handleError])

  const getPaymentMethods = useCallback(async (): Promise<PaymentMethodsResponse | null> => {
    if (!currentRequest) return null

    try {
      setIsLoading(true)
      setError(null)
      return await serviceRequestsApi.getPaymentMethods(currentRequest.id)
    } catch (err) {
      handleError(err)
      return null
    } finally {
      setIsLoading(false)
    }
  }, [currentRequest, handleError])

  const initiatePayment = useCallback(async (
    method: string,
    phone?: string
  ): Promise<PaymentInitiateResult | null> => {
    if (!currentRequest) return null

    try {
      setIsSaving(true)
      setError(null)
      return await serviceRequestsApi.initiatePayment(currentRequest.id, method, phone)
    } catch (err) {
      handleError(err)
      return null
    } finally {
      setIsSaving(false)
    }
  }, [currentRequest, handleError])

  const checkPaymentStatus = useCallback(async (): Promise<{ status: string; paid: boolean } | null> => {
    if (!currentRequest) return null

    try {
      return await serviceRequestsApi.checkPaymentStatus(currentRequest.id)
    } catch (err) {
      handleError(err)
      return null
    }
  }, [currentRequest, handleError])

  // =========================================================================
  // LIST ACTIONS
  // =========================================================================

  const loadMyRequests = useCallback(async (
    page: number = 1,
    pageSize: number = 20,
    filtersOverride?: ServiceRequestFilters
  ): Promise<void> => {
    // Increment sequence to invalidate any in-flight requests
    const seq = ++listRequestSeqRef.current
    try {
      setIsLoading(true)
      setError(null)
      const response = await serviceRequestsApi.listMyRequests(page, pageSize, filtersOverride ?? filters)
      // Discard stale response if a newer request was initiated
      if (seq !== listRequestSeqRef.current) return
      setRequests(response.requests)
      setPagination({
        page: response.page,
        pageSize: response.pageSize,
        total: response.total,
        totalPages: response.totalPages,
      })
    } catch (err) {
      if (seq !== listRequestSeqRef.current) return
      handleError(err)
    } finally {
      if (seq === listRequestSeqRef.current) {
        setIsLoading(false)
      }
    }
  }, [filters, handleError])

  const loadAllRequests = useCallback(async (
    page: number = 1,
    pageSize: number = 10
  ): Promise<void> => {
    try {
      setIsLoading(true)
      setError(null)
      const response = await serviceRequestsApi.listAllRequests(page, pageSize, filters)
      setRequests(response.requests)
      setPagination({
        page: response.page,
        pageSize: response.pageSize,
        total: response.total,
        totalPages: response.totalPages,
      })
    } catch (err) {
      handleError(err)
    } finally {
      setIsLoading(false)
    }
  }, [filters, handleError])

  const updateRequest = useCallback(async (
    data: ServiceRequestUpdate
  ): Promise<ServiceRequest | null> => {
    if (!currentRequest) return null

    try {
      setIsSaving(true)
      setError(null)
      const request = await serviceRequestsApi.updateRequest(currentRequest.id, data)
      setCurrentRequest(request)
      return request
    } catch (err) {
      handleError(err)
      return null
    } finally {
      setIsSaving(false)
    }
  }, [currentRequest, handleError])

  const deleteRequest = useCallback(async (): Promise<boolean> => {
    if (!currentRequest) return false

    try {
      setIsSaving(true)
      setError(null)
      await serviceRequestsApi.deleteRequest(currentRequest.id)
      setCurrentRequest(null)
      setWorkflow(null)
      setCurrentStep(null)
      setDocuments([])
      return true
    } catch (err) {
      handleError(err)
      return false
    } finally {
      setIsSaving(false)
    }
  }, [currentRequest, handleError])

  const deleteRequestById = useCallback(async (requestId: string): Promise<boolean> => {
    try {
      setIsSaving(true)
      setError(null)
      await serviceRequestsApi.deleteRequest(requestId)
      // Remove from list if present
      setRequests(prev => prev.filter(r => r.id !== requestId))
      return true
    } catch (err) {
      handleError(err)
      return false
    } finally {
      setIsSaving(false)
    }
  }, [handleError])

  // =========================================================================
  // AGENT ACTIONS
  // =========================================================================

  const approveRequest = useCallback(async (notes?: string): Promise<boolean> => {
    if (!currentRequest) return false

    try {
      setIsSaving(true)
      setError(null)
      const request = await serviceRequestsApi.approveRequest(currentRequest.id, notes)
      setCurrentRequest(request)
      return true
    } catch (err) {
      handleError(err)
      return false
    } finally {
      setIsSaving(false)
    }
  }, [currentRequest, handleError])

  const rejectRequest = useCallback(async (reason: string, notes?: string): Promise<boolean> => {
    if (!currentRequest) return false

    try {
      setIsSaving(true)
      setError(null)
      const request = await serviceRequestsApi.rejectRequest(currentRequest.id, reason, notes)
      setCurrentRequest(request)
      return true
    } catch (err) {
      handleError(err)
      return false
    } finally {
      setIsSaving(false)
    }
  }, [currentRequest, handleError])

  const requestAdditionalInfo = useCallback(async (
    message: string,
    requiredDocs?: string[]
  ): Promise<boolean> => {
    if (!currentRequest) return false

    try {
      setIsSaving(true)
      setError(null)
      const request = await serviceRequestsApi.requestAdditionalInfo(
        currentRequest.id,
        message,
        requiredDocs
      )
      setCurrentRequest(request)
      return true
    } catch (err) {
      handleError(err)
      return false
    } finally {
      setIsSaving(false)
    }
  }, [currentRequest, handleError])

  const scheduleAppointment = useCallback(async (
    date: string,
    time: string,
    location: string
  ): Promise<boolean> => {
    if (!currentRequest) return false

    try {
      setIsSaving(true)
      setError(null)
      const request = await serviceRequestsApi.scheduleAppointment(
        currentRequest.id,
        date,
        time,
        location
      )
      setCurrentRequest(request)
      return true
    } catch (err) {
      handleError(err)
      return false
    } finally {
      setIsSaving(false)
    }
  }, [currentRequest, handleError])

  const addAgentNote = useCallback(async (note: string): Promise<boolean> => {
    if (!currentRequest) return false

    try {
      setIsSaving(true)
      setError(null)
      const request = await serviceRequestsApi.addAgentNote(currentRequest.id, note)
      setCurrentRequest(request)
      return true
    } catch (err) {
      handleError(err)
      return false
    } finally {
      setIsSaving(false)
    }
  }, [currentRequest, handleError])

  // =========================================================================
  // UTILITY
  // =========================================================================

  const clearError = useCallback(() => setError(null), [])

  const setPage = useCallback((page: number) => {
    setPagination(prev => ({ ...prev, page }))
  }, [])

  const reset = useCallback(() => {
    setCurrentRequest(null)
    setWorkflow(null)
    setCurrentStep(null)
    setDocuments([])
    setValidationResults([])
    setTariff(null)
    setError(null)
  }, [])

  // =========================================================================
  // APPOINTMENT ACTIONS (Citizen-First Flow)
  // =========================================================================

  const getAppointmentLocations = useCallback(async (requestId: string) => {
    return serviceRequestsApi.getAppointmentLocations(requestId)
  }, [])

  const getAvailableDays = useCallback(async (
    requestId: string,
    entityLocationId: string,
    fromDate?: string,
    toDate?: string
  ) => {
    return serviceRequestsApi.getAvailableDays(requestId, entityLocationId, fromDate, toDate)
  }, [])

  // Migration 030: Uses entityLocationId FK instead of locationName
  const getAppointmentSlots = useCallback(async (
    requestId: string,
    entityLocationId: string,
    fromDate?: string,
    limit: number = 6
  ) => {
    return serviceRequestsApi.getAppointmentSlots(requestId, entityLocationId, fromDate, limit)
  }, [])

  const holdAppointmentSlot = useCallback(async (
    requestId: string,
    data: {
      entityLocationId: string
      slotConfigId?: string
      appointmentDate: string
      appointmentTime: string
    }
  ) => {
    return serviceRequestsApi.holdAppointmentSlot(requestId, data)
  }, [])

  const getAppointmentHoldStatus = useCallback(async (requestId: string) => {
    return serviceRequestsApi.getHoldStatus(requestId)
  }, [])

  const releaseAppointmentHold = useCallback(async (requestId: string) => {
    return serviceRequestsApi.releaseHold(requestId)
  }, [])

  const submitWithoutAppointment = useCallback(async (requestId: string, entityLocationId: string) => {
    return serviceRequestsApi.submitWithoutAppointment(requestId, entityLocationId)
  }, [])

  const confirmAppointmentHold = useCallback(async (requestId: string) => {
    return serviceRequestsApi.confirmAppointmentHold(requestId)
  }, [])

  // =========================================================================
  // RETURN
  // =========================================================================

  return {
    // State
    requests,
    currentRequest,
    workflow,
    currentStep,
    documents,
    validationResults,
    tariff,
    isLoading,
    isSaving,
    error,
    pagination,
    filters,
    filterOptions,
    loadFilterOptions,

    // Workflow actions
    loadWorkflows,
    startWorkflow,
    loadRequest,

    // Step actions
    submitStep,
    previousStep,
    saveStepData,
    validateStep,

    // Document actions (legacy)
    uploadDocument,
    deleteDocument,
    retryExtraction,
    updateExtractedData,
    loadDocuments,

    // Document actions (new preview/validate flow)
    previewDocument,
    validateDocument,
    currentPreview,
    clearPreview,

    // Form data and summary
    getFormData,
    getCitizenSummary,
    downloadSummaryPDF,

    // Validation & Tariff
    validateDocuments,
    calculateTariff,

    // Submission
    submitRequest,
    prepareForPayment,
    getPaymentMethods,
    initiatePayment,
    checkPaymentStatus,

    // List actions
    loadMyRequests,
    loadAllRequests,
    updateRequest,
    deleteRequest,
    deleteRequestById,

    // Agent actions
    approveRequest,
    rejectRequest,
    requestAdditionalInfo,
    scheduleAppointment,
    addAgentNote,

    // Appointment actions (citizen-first flow)
    getAppointmentLocations,
    getAvailableDays,
    getAppointmentSlots,
    holdAppointmentSlot,
    getAppointmentHoldStatus,
    releaseAppointmentHold,
    submitWithoutAppointment,
    confirmAppointmentHold,

    // Utility
    clearError,
    setFilters,
    setPage,
    reset,
  }
}
