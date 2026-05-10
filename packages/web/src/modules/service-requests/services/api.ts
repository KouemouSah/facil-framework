/**
 * Service Requests API Client
 * Follows the supportApi pattern for consistency
 */

import { getAuthData } from '@/core/auth/storage'
import type {
  ServiceRequest,
  ServiceRequestCreate,
  ServiceRequestUpdate,
  ServiceRequestDocument,
  ServiceRequestListResponse,
  ServiceRequestFilters,
  WorkflowConfig,
  WorkflowStep,
  WorkflowStartResponse,
  StepSubmitRequest,
  StepSubmitResponse,
  DocumentUploadResponse,
  TariffCalculation,
  ValidationResult,
  // Two-step preview/validate types (camelCase for frontend)
  DocumentExtractionPreview,
  DocumentValidationResponse,
  FormDataResponse,
  CitizenSummaryResponse,
  FieldIndicator,
  RiskAnalysisResult,
  // Payment types
  PaymentMethodsResponse,
  PaymentInitiateResult,
  // History types
  HistoryFilters,
  HistoryListResponse,
  HistoryListSummaryResponse,
  HistoryStatistics,
  // Detail view types
  DetailViewResponse,
} from '../types'
import { HistoryActionType, HistoryEntrySource } from '../types'
import { ExtractionStatus } from '../types'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const API_VERSION = '/api/v1'
const ENDPOINT_BASE = '/service-requests'
const AGENT_ENDPOINT_BASE = '/agent/service-requests'


// ============================================================================
// BACKEND RESPONSE TYPES (snake_case from Python)
// ============================================================================

interface BackendWorkflowStep {
  number: number
  id: string
  type: string
  title_es: string
  description_es?: string
  is_inherited: boolean
  is_optional?: boolean
  config?: Record<string, unknown>
}

interface BackendWorkflow {
  code: string
  all_workflow_codes?: string[]
  category: string
  entity_code: string
  service_name_es: string
  requires_nota_ingreso: boolean
  requires_appointment: boolean
  requires_agent_review: boolean
  allowed_solicitud_types?: string[]
  allowed_sub_types: string[]
  total_steps?: number
  steps?: BackendWorkflowStep[]
  tariff_type?: string
}

interface BackendServiceRequest {
  id: string
  reference: string
  user_id: string
  workflow_code: string
  solicitud_type: string
  status: string
  priority: string
  form_data?: Record<string, unknown>
  extracted_data?: Record<string, unknown>
  created_at: string
  updated_at?: string
  submitted_at?: string
  completed_at?: string
  assigned_to?: string
  current_step?: number
  tariff?: Record<string, unknown>
  // Notes & Rejection
  notes?: string
  rejection_reason?: string
  // Verification fields (from migration 040)
  verification_status?: string
  verification_details?: Record<string, {
    verified: boolean
    verified_at?: string
    source?: string
    reason?: string
    document_code?: string
    is_required?: boolean
  }>
}

/** Backend paginated list response (snake_case) */
interface BackendListResponse {
  requests: BackendServiceRequest[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

/** Filter options from /filter-options endpoint */
export interface FilterOptions {
  statuses: Array<{ value: string; phase: string }>
  categories: Array<{ value: string; label_es: string }>
}

/** Backend dashboard summary response (snake_case) */
interface BackendDashboardSummary {
  stats: { active: number; completed: number; pending_action: number; total_paid: number }
  recent_requests: Array<{
    id: string; reference: string; workflow_code: string; workflow_label: string
    status: string; solicitud_type: string; created_at: string
    updated_at?: string | null; total_amount?: number | null
  }>
  recent_payments: Array<{
    id: string; service_request_id: string; request_reference: string
    workflow_code: string; workflow_label: string; amount: number
    currency: string; status: string; payment_method?: string | null
    created_at: string
  }>
  notifications: Array<{
    id: string; action: string; title: string; message?: string | null
    performed_at: string; performer_role?: string | null; is_new: boolean
    new_status?: string | null
  }>
  unread_count: number
  upcoming_appointment?: {
    request_id: string; request_reference: string; workflow_code: string
    workflow_label: string; appointment_date: string; time?: string | null
    location?: string | null
  } | null
  action_required: Array<{
    request_id: string; reference: string; workflow_code: string
    workflow_label: string; status: string; message: string
  }>
}

/** Frontend dashboard summary (camelCase) */
export interface DashboardSummary {
  stats: { active: number; completed: number; pendingAction: number; totalPaid: number }
  recentRequests: Array<{
    id: string; reference: string; workflowCode: string; workflowLabel: string
    status: string; solicitudType: string; createdAt: string
    updatedAt?: string | null; totalAmount?: number | null
  }>
  recentPayments: Array<{
    id: string; serviceRequestId: string; requestReference: string
    workflowCode: string; workflowLabel: string; amount: number
    currency: string; status: string; paymentMethod?: string | null
    createdAt: string
  }>
  notifications: Array<{
    id: string; action: string; title: string; message?: string | null
    performedAt: string; performerRole?: string | null; isNew: boolean
    newStatus?: string | null
  }>
  unreadCount: number
  upcomingAppointment: {
    requestId: string; requestReference: string; workflowCode: string
    workflowLabel: string; appointmentDate: string; time?: string | null
    location?: string | null
  } | null
  actionRequired: Array<{
    requestId: string; reference: string; workflowCode: string
    workflowLabel: string; status: string; message: string
  }>
}


// Backend types for two-step preview/validate flow (snake_case from Python)
interface BackendFieldIndicator {
  field_name: string
  value?: unknown
  confidence: number
  status: 'ok' | 'warning' | 'error' | 'missing'
  risk_level?: string
  risk_message?: string
  requires_attention: boolean
  suggestion?: string
}

interface BackendRiskAnalysis {
  risk_level: string
  risk_score: number
  risk_factors: Array<Record<string, unknown>>
  recommendations: string[]
  requires_rejection: boolean
  requires_review: boolean
  factors_count: Record<string, number>
  // Identity mismatch fields for cross-document validation
  identity_mismatches?: Array<{
    field_name: string
    field_label: { es: string; fr: string; en: string }
    is_blocking: boolean
    source_document: { code: string; value: string }
    compared_document: { code: string; value: string }
    risk_code: string
    severity: string
  }>
  has_blocking_mismatches?: boolean
}

interface BackendDocumentExtractionPreview {
  preview_id: string
  document_code: string
  document_name: string
  file_name: string
  file_size: number
  mime_type: string
  extraction: Record<string, unknown>
  confidence: number
  processor: string
  field_indicators: BackendFieldIndicator[]
  risk_analysis?: BackendRiskAnalysis
  extraction_status: string
  needs_correction: boolean
  detected_document_type?: string
  document_type_match: boolean
  expected_fields: Array<Record<string, unknown>>
  expires_at: string
  processing_time_ms?: number
}

interface BackendDocumentValidationResponse {
  document_id: string
  document_code: string
  document_name: string
  file_path: string
  extraction_data: Record<string, unknown>
  extraction_confidence: number
  is_validated: boolean
  validated_at: string
}

interface BackendFormDataResponse {
  form_data: Record<string, unknown>
  extracted_data: Record<string, unknown>
  form_schema?: Record<string, unknown>
  requires_review: boolean
  completion_percentage: number
  missing_fields: string[]
}

interface BackendCitizenSummaryResponse {
  request_id: string
  reference: string
  workflow_code: string
  workflow_name_es: string
  solicitud_type: string
  sub_type?: string
  personal_data: Record<string, unknown>
  documents_uploaded: Array<{
    document_code: string
    document_name: string
    file_name: string
    extraction_confidence: number
    is_validated: boolean
  }>
  documents_complete: boolean
  tariff_summary?: {
    base_amount: number
    supplements_total: number
    total_amount: number
    currency: string
  }
  validation_passed: boolean
  validation_warnings: string[]
  can_submit: boolean
  blockers: string[]
}

// Backend ValidationResult (snake_case from Python)
interface BackendValidationResult {
  rule_id: string
  is_valid: boolean
  severity: string
  message_es: string
  field?: string
  document_code?: string
}

// ============================================================================
// TRANSFORMATION FUNCTIONS (snake_case -> camelCase)
// ============================================================================

function transformStep(backend: BackendWorkflowStep): WorkflowStep {
  return {
    stepNumber: backend.number,
    stepId: backend.id,
    stepType: backend.type as WorkflowStep['stepType'],
    titleEs: backend.title_es,
    descriptionEs: backend.description_es,
    isInherited: backend.is_inherited,
    isOptional: backend.is_optional,
    config: backend.config,
  }
}

function transformWorkflow(backend: BackendWorkflow): WorkflowConfig {
  return {
    workflowCode: backend.code,
    allWorkflowCodes: backend.all_workflow_codes || [backend.code],
    category: backend.category as WorkflowConfig['category'],
    entityCode: backend.entity_code,
    serviceNameEs: backend.service_name_es,
    requiresNotaIngreso: backend.requires_nota_ingreso,
    requiresAppointment: backend.requires_appointment,
    requiresAgentReview: backend.requires_agent_review,
    allowedSubTypes: backend.allowed_sub_types || [],
    steps: (backend.steps || []).map(transformStep),
    tariffType: (backend.tariff_type as WorkflowConfig['tariffType']) || 'fixed',
  }
}

function transformServiceRequest(backend: BackendServiceRequest): ServiceRequest {
  // CRITICAL: sub_type comes from form_data (NUEVO/PERDIDA/ROBO/DETERIORO)
  // solicitud_type is the enum (expedicion/renovacion/duplicado)
  // Workflow-specific logic (like document requirements) needs the original sub_type
  const subType = (backend.form_data?.sub_type as string) || backend.solicitud_type

  // Transform verification details from snake_case to camelCase
  let verificationDetails: ServiceRequest['verificationDetails'] = undefined
  if (backend.verification_details) {
    verificationDetails = {}
    for (const [key, val] of Object.entries(backend.verification_details)) {
      verificationDetails[key] = {
        verified: val.verified,
        verifiedAt: val.verified_at,
        source: val.source,
        reason: val.reason,
        documentCode: val.document_code,
        isRequired: val.is_required,
      }
    }
  }

  // Transform tariff from backend (snake_case) to frontend (camelCase)
  let tariff: ServiceRequest['tariff'] = undefined
  if (backend.tariff) {
    const backendTariff = backend.tariff as {
      base_amount?: number
      supplements?: Array<{ code: string; name_es?: string; amount: number }>
      supplements_total?: number
      total_amount?: number
      currency?: string
    }
    tariff = {
      baseAmount: backendTariff.base_amount || 0,
      supplements: (backendTariff.supplements || []).map(s => ({
        code: s.code,
        nameEs: s.name_es || s.code,
        amount: s.amount,
      })),
      supplementsTotal: backendTariff.supplements_total || 0,
      totalAmount: backendTariff.total_amount || 0,
      currency: backendTariff.currency || 'XAF',
    }
  }

  return {
    id: backend.id,
    requestNumber: backend.reference,
    userId: backend.user_id,
    workflowCode: backend.workflow_code,
    subType,
    status: backend.status as ServiceRequest['status'],
    currentStep: backend.current_step || 1,
    formData: backend.form_data || {},
    extractedData: backend.extracted_data,
    tariffAmount: backend.tariff?.total_amount as number | undefined,
    tariff,
    assignedAgentId: backend.assigned_to,
    createdAt: backend.created_at,
    updatedAt: backend.updated_at,
    submittedAt: backend.submitted_at,
    completedAt: backend.completed_at,
    // Notes & Rejection
    notes: backend.notes,
    rejectionReason: backend.rejection_reason,
    // Verification fields
    verificationStatus: backend.verification_status as ServiceRequest['verificationStatus'],
    verificationDetails,
  }
}


// Transform functions for two-step preview/validate types
function transformFieldIndicator(backend: BackendFieldIndicator): FieldIndicator {
  return {
    fieldName: backend.field_name,
    value: backend.value,
    confidence: backend.confidence,
    status: backend.status,
    riskLevel: backend.risk_level as FieldIndicator['riskLevel'],
    riskMessage: backend.risk_message,
    requiresAttention: backend.requires_attention,
    suggestion: backend.suggestion,
  }
}

function transformRiskAnalysis(backend: BackendRiskAnalysis): RiskAnalysisResult {
  return {
    riskLevel: backend.risk_level as RiskAnalysisResult['riskLevel'],
    riskScore: backend.risk_score,
    riskFactors: backend.risk_factors.map((f) => ({
      type: (f as Record<string, unknown>).type as string,
      severity: (f as Record<string, unknown>).severity as string,
      description: (f as Record<string, unknown>).description as string,
    })),
    recommendations: backend.recommendations,
    requiresRejection: backend.requires_rejection,
    requiresReview: backend.requires_review,
    factorsCount: backend.factors_count,
    // Transform identity mismatch fields (snake_case -> camelCase)
    identityMismatches: backend.identity_mismatches?.map((m) => ({
      field_name: m.field_name,
      field_label: m.field_label,
      is_blocking: m.is_blocking,
      source_document: m.source_document,
      compared_document: m.compared_document,
      risk_code: m.risk_code,
      severity: m.severity,
    })),
    hasBlockingMismatches: backend.has_blocking_mismatches ?? false,
  }
}

function transformDocumentExtractionPreview(backend: BackendDocumentExtractionPreview): DocumentExtractionPreview {
  return {
    previewId: backend.preview_id,
    documentCode: backend.document_code,
    documentName: backend.document_name,
    fileName: backend.file_name,
    fileSize: backend.file_size,
    mimeType: backend.mime_type,
    extraction: backend.extraction,
    confidence: backend.confidence,
    processor: backend.processor as DocumentExtractionPreview['processor'],
    fieldIndicators: backend.field_indicators.map(transformFieldIndicator),
    riskAnalysis: backend.risk_analysis ? transformRiskAnalysis(backend.risk_analysis) : undefined,
    extractionStatus: backend.extraction_status as DocumentExtractionPreview['extractionStatus'],
    needsCorrection: backend.needs_correction,
    detectedDocumentType: backend.detected_document_type,
    documentTypeMatch: backend.document_type_match,
    expectedFields: backend.expected_fields.map(f => ({
      key: (f as Record<string, unknown>).key as string,
      label: (f as Record<string, unknown>).label as string,
      type: (f as Record<string, unknown>).type as string,
      required: (f as Record<string, unknown>).required as boolean,
    })),
    expiresAt: backend.expires_at,
    processingTimeMs: backend.processing_time_ms,
  }
}

function transformDocumentValidationResponse(backend: BackendDocumentValidationResponse): DocumentValidationResponse {
  return {
    documentId: backend.document_id,
    documentCode: backend.document_code,
    documentName: backend.document_name,
    filePath: backend.file_path,
    extractionData: backend.extraction_data,
    extractionConfidence: backend.extraction_confidence,
    isValidated: backend.is_validated,
    validatedAt: backend.validated_at,
  }
}

function transformFormDataResponse(backend: BackendFormDataResponse): FormDataResponse {
  return {
    formData: backend.form_data,
    extractedData: backend.extracted_data,
    formSchema: backend.form_schema,
    requiresReview: backend.requires_review,
    completionPercentage: backend.completion_percentage,
    missingFields: backend.missing_fields,
  }
}

function transformCitizenSummaryResponse(backend: BackendCitizenSummaryResponse): CitizenSummaryResponse {
  return {
    requestId: backend.request_id,
    reference: backend.reference,
    workflowCode: backend.workflow_code,
    workflowNameEs: backend.workflow_name_es,
    solicitudType: backend.solicitud_type,
    subType: backend.sub_type,
    personalData: backend.personal_data,
    documentsUploaded: backend.documents_uploaded.map(d => ({
      documentCode: d.document_code,
      documentName: d.document_name,
      fileName: d.file_name,
      extractionConfidence: d.extraction_confidence,
      isValidated: d.is_validated,
    })),
    documentsComplete: backend.documents_complete,
    tariffSummary: backend.tariff_summary ? {
      baseAmount: backend.tariff_summary.base_amount,
      // Convert supplements_total (number) to supplements array for frontend compatibility
      supplements: backend.tariff_summary.supplements_total > 0
        ? [{ name: 'Suplementos', amount: backend.tariff_summary.supplements_total }]
        : [],
      total: backend.tariff_summary.total_amount,
      currency: backend.tariff_summary.currency,
    } : undefined,
    validationPassed: backend.validation_passed,
    validationWarnings: backend.validation_warnings,
    canSubmit: backend.can_submit,
    blockers: backend.blockers,
  }
}

/**
 * Transform ValidationResult from backend snake_case to frontend camelCase
 */
function transformValidationResult(backend: BackendValidationResult): ValidationResult {
  return {
    ruleId: backend.rule_id,
    isValid: backend.is_valid,
    severity: backend.severity as 'error' | 'warning' | 'info',
    messageEs: backend.message_es,
    field: backend.field,
    documentCode: backend.document_code,
  }
}

class ServiceRequestsApiClient {
  private baseUrl: string

  constructor() {
    this.baseUrl = `${API_BASE_URL}${API_VERSION}${ENDPOINT_BASE}`
  }

  private getToken(): string | null {
    if (typeof window === 'undefined') return null
    const authData = getAuthData()
    return authData?.access_token || null
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const token = this.getToken()
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    }

    const url = `${this.baseUrl}${endpoint}`
    console.log(`[ServiceRequests] ${options.method || 'GET'} ${url}`)

    try {
      const response = await fetch(url, {
        ...options,
        headers,
      })

      console.log(`[ServiceRequests] Response status: ${response.status}`)

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        // Handle error.detail that could be string or object
        let errorMessage = `API Error: ${response.status}`
        if (errorData.detail) {
          if (typeof errorData.detail === 'string') {
            errorMessage = errorData.detail
          } else if (typeof errorData.detail === 'object') {
            // FastAPI can return detail as object with localized messages
            // Priority: message_es/message_fr/message_en > message > msg > JSON
            const locale = typeof window !== 'undefined' ? (document.documentElement.lang || 'es') : 'es'
            errorMessage =
              (locale === 'es' ? errorData.detail.message_es :
               locale === 'fr' ? errorData.detail.message_fr :
               errorData.detail.message_en) ||
              errorData.detail.message ||
              errorData.detail.msg ||
              JSON.stringify(errorData.detail)
          }
        }
        console.error(`[ServiceRequests] Error: ${errorMessage}`)
        throw new Error(errorMessage)
      }

      // Handle 204 No Content
      if (response.status === 204) {
        return {} as T
      }

      const data = await response.json()
      console.log(`[ServiceRequests] Success`)
      return data
    } catch (error) {
      console.error(`[ServiceRequests] Fetch error:`, error)
      throw error
    }
  }

  private async uploadRequest<T>(
    endpoint: string,
    formData: FormData
  ): Promise<T> {
    const token = this.getToken()
    const headers: HeadersInit = {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    }

    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      method: 'POST',
      headers,
      body: formData,
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      // Handle error.detail that could be string or object
      let errorMessage = `Upload Error: ${response.status}`
      if (errorData.detail) {
        if (typeof errorData.detail === 'string') {
          errorMessage = errorData.detail
        } else if (typeof errorData.detail === 'object') {
          // FastAPI can return detail as object with localized messages
          const locale = typeof window !== 'undefined' ? (document.documentElement.lang || 'es') : 'es'
          errorMessage =
            (locale === 'es' ? errorData.detail.message_es :
             locale === 'fr' ? errorData.detail.message_fr :
             errorData.detail.message_en) ||
            errorData.detail.message ||
            errorData.detail.msg ||
            JSON.stringify(errorData.detail)
        }
      }
      throw new Error(errorMessage)
    }

    return response.json()
  }

  /**
   * Make a request to agent-specific endpoints (/agent/service-requests/...)
   */
  private async agentRequest<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const token = this.getToken()
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    }

    const agentBaseUrl = `${API_BASE_URL}${API_VERSION}${AGENT_ENDPOINT_BASE}`
    const url = `${agentBaseUrl}${endpoint}`
    console.log(`[ServiceRequests:Agent] ${options.method || 'GET'} ${url}`)

    try {
      const response = await fetch(url, {
        ...options,
        headers,
      })

      console.log(`[ServiceRequests:Agent] Response status: ${response.status}`)

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        let errorMessage = `API Error: ${response.status}`
        if (errorData.detail) {
          if (typeof errorData.detail === 'string') {
            errorMessage = errorData.detail
          } else if (typeof errorData.detail === 'object') {
            errorMessage = errorData.detail.message || errorData.detail.msg || JSON.stringify(errorData.detail)
          }
        }
        console.error(`[ServiceRequests:Agent] Error: ${errorMessage}`)
        throw new Error(errorMessage)
      }

      if (response.status === 204) {
        return {} as T
      }

      const data = await response.json()
      console.log(`[ServiceRequests:Agent] Success`)
      return data
    } catch (error) {
      console.error(`[ServiceRequests:Agent] Fetch error:`, error)
      throw error
    }
  }

  // =========================================================================
  // WORKFLOW CONFIGURATION
  // =========================================================================

  /**
   * Get available workflows for a category
   */
  async getWorkflows(category?: string): Promise<WorkflowConfig[]> {
    const params = category ? `?category=${category}` : ''
    const workflows = await this.request<BackendWorkflow[]>(`/workflows${params}`)
    return workflows.map(transformWorkflow)
  }

  /**
   * Get workflow configuration by code
   */
  async getWorkflow(workflowCode: string): Promise<WorkflowConfig> {
    const workflow = await this.request<BackendWorkflow>(`/workflows/${workflowCode}`)
    return transformWorkflow(workflow)
  }

  /**
   * Get workflow steps configuration
   */
  async getWorkflowSteps(workflowCode: string, _subType?: string): Promise<WorkflowConfig> {
    // Backend doesn't have /steps endpoint, use the main workflow endpoint
    const workflow = await this.request<BackendWorkflow>(`/workflows/${workflowCode}`)
    return transformWorkflow(workflow)
  }

  // =========================================================================
  // SERVICE REQUEST CRUD
  // =========================================================================

  /**
   * Start a new service request workflow
   * Backend uses POST / to create, returns ServiceRequestResponse (snake_case)
   */
  async startWorkflow(data: ServiceRequestCreate): Promise<WorkflowStartResponse> {
    // Backend endpoint is POST / - convert to snake_case for backend
    // Map workflow sub_types (NUEVO, RENOVACION, PERDIDA, ROBO, DETERIORO)
    // to solicitud_type enum (expedicion, renovacion, duplicado)
    const mapSubTypeToSolicitudType = (subType?: string): string => {
      if (!subType) return 'expedicion'
      const upper = subType.toUpperCase()
      if (upper === 'NUEVO' || upper === 'EXPEDICION') return 'expedicion'
      if (upper === 'RENOVACION') return 'renovacion'
      if (['PERDIDA', 'ROBO', 'DETERIORO', 'DUPLICADO'].includes(upper)) return 'duplicado'
      return 'expedicion' // fallback
    }
    
    const backendData = {
      workflow_code: data.workflowCode,
      solicitud_type: mapSubTypeToSolicitudType(data.subType),
      form_data: {
        ...(data.formData || {}),
        // CRITICAL: Preserve original sub_type for workflow engine
        // workflow_engine.py reads form_data.sub_type or form_data.tipo
        // Required for pasaporte_workflow document requirements (NUEVO/PERDIDA/ROBO/etc.)
        sub_type: data.subType?.toUpperCase() || 'NUEVO',
      },
    }
    // Backend returns snake_case, transform to camelCase
    const backendRequest = await this.request<BackendServiceRequest>('/', {
      method: 'POST',
      body: JSON.stringify(backendData),
    })
    const request = transformServiceRequest(backendRequest)

    // Fetch workflow config to return complete response
    const workflow = await this.getWorkflow(request.workflowCode)
    const currentStepConfig = workflow.steps?.find(s => s.stepNumber === (request.currentStep || 1)) || null

    return {
      request,
      workflow,
      currentStepConfig,
    }
  }

  /**
   * Get service request by ID
   */
  async getRequest(requestId: string): Promise<ServiceRequest> {
    const backend = await this.request<BackendServiceRequest>(`/${requestId}`)
    return transformServiceRequest(backend)
  }

  /**
   * List user's service requests with server-side filters + pagination
   * Backend returns ServiceRequestListResponse with total count
   */
  async listMyRequests(
    page: number = 1,
    pageSize: number = 20,
    filters?: ServiceRequestFilters
  ): Promise<ServiceRequestListResponse> {
    const params = new URLSearchParams({
      page: page.toString(),
      page_size: pageSize.toString(),
    })

    if (filters?.status) params.append('status', filters.status)
    if (filters?.workflowCode) params.append('workflow_code', filters.workflowCode)
    if (filters?.category) params.append('category', filters.category as string)
    if (filters?.search) params.append('search', filters.search)
    if (filters?.dateFrom) params.append('date_from', filters.dateFrom)
    if (filters?.dateTo) params.append('date_to', filters.dateTo)

    const response = await this.request<BackendListResponse>(`/?${params.toString()}`)
    const requests = (response.requests || []).map(transformServiceRequest)

    return {
      requests,
      total: response.total,
      page: response.page,
      pageSize: response.page_size,
      totalPages: response.total_pages,
    }
  }

  /**
   * Get dynamic filter options (statuses + categories) from backend enums
   */
  async getFilterOptions(): Promise<FilterOptions> {
    return this.request<FilterOptions>('/filter-options')
  }

  /**
   * Get citizen dashboard summary — single call, all data
   */
  async getDashboardSummary(): Promise<DashboardSummary> {
    const b = await this.request<BackendDashboardSummary>('/dashboard-summary')
    return {
      stats: {
        active: b.stats.active,
        completed: b.stats.completed,
        pendingAction: b.stats.pending_action,
        totalPaid: b.stats.total_paid,
      },
      recentRequests: b.recent_requests.map(r => ({
        id: r.id, reference: r.reference, workflowCode: r.workflow_code,
        workflowLabel: r.workflow_label, status: r.status,
        solicitudType: r.solicitud_type, createdAt: r.created_at,
        updatedAt: r.updated_at, totalAmount: r.total_amount,
      })),
      recentPayments: b.recent_payments.map(p => ({
        id: p.id, serviceRequestId: p.service_request_id,
        requestReference: p.request_reference, workflowCode: p.workflow_code,
        workflowLabel: p.workflow_label, amount: p.amount,
        currency: p.currency, status: p.status,
        paymentMethod: p.payment_method, createdAt: p.created_at,
      })),
      notifications: b.notifications.map(n => ({
        id: n.id, action: n.action, title: n.title, message: n.message,
        performedAt: n.performed_at, performerRole: n.performer_role,
        isNew: n.is_new, newStatus: n.new_status,
      })),
      unreadCount: b.unread_count,
      upcomingAppointment: b.upcoming_appointment ? {
        requestId: b.upcoming_appointment.request_id,
        requestReference: b.upcoming_appointment.request_reference,
        workflowCode: b.upcoming_appointment.workflow_code,
        workflowLabel: b.upcoming_appointment.workflow_label,
        appointmentDate: b.upcoming_appointment.appointment_date,
        time: b.upcoming_appointment.time,
        location: b.upcoming_appointment.location,
      } : null,
      actionRequired: b.action_required.map(a => ({
        requestId: a.request_id, reference: a.reference,
        workflowCode: a.workflow_code, workflowLabel: a.workflow_label,
        status: a.status, message: a.message,
      })),
    }
  }

  /**
   * Update service request form data
   */
  async updateRequest(
    requestId: string,
    data: ServiceRequestUpdate
  ): Promise<ServiceRequest> {
    // Transform camelCase to snake_case for backend
    const backendData: Record<string, unknown> = {}
    if (data.formData !== undefined) {
      backendData.form_data = data.formData
    }
    if (data.currentStep !== undefined) {
      backendData.current_step = data.currentStep
    }

    const backend = await this.request<BackendServiceRequest>(`/${requestId}`, {
      method: 'PUT',
      body: JSON.stringify(backendData),
    })
    return transformServiceRequest(backend)
  }

  /**
   * Delete/cancel a draft request
   */
  async deleteRequest(requestId: string): Promise<void> {
    return this.request<void>(`/${requestId}`, {
      method: 'DELETE',
    })
  }

  // =========================================================================
  // WORKFLOW STEP OPERATIONS
  // =========================================================================

  /**
   * Submit current step and advance
   */
  async submitStep(
    requestId: string,
    stepData: StepSubmitRequest
  ): Promise<StepSubmitResponse> {
    return this.request<StepSubmitResponse>(`/${requestId}/step`, {
      method: 'POST',
      body: JSON.stringify(stepData),
    })
  }

  /**
   * Go back to previous step
   */
  async previousStep(requestId: string): Promise<StepSubmitResponse> {
    return this.request<StepSubmitResponse>(`/${requestId}/step/previous`, {
      method: 'POST',
    })
  }

  /**
   * Save step data by merging into formData
   * Uses PUT /{request_id} endpoint with formData
   * @param existingFormData - Optional existing formData to merge with (avoids extra API call)
   */
  async saveStepData(
    requestId: string,
    _stepId: string, // Kept for API compatibility, not used
    data: Record<string, unknown>,
    existingFormData?: Record<string, unknown>
  ): Promise<ServiceRequest> {
    // Merge new data with existing formData
    const mergedFormData = {
      ...(existingFormData || {}),
      ...data,
    }

    // Use the update endpoint with merged formData
    return this.updateRequest(requestId, {
      formData: mergedFormData,
    })
  }

  // =========================================================================
  // DOCUMENT OPERATIONS
  // =========================================================================

  /**
   * Upload a document for extraction
   * Backend returns flat response, we transform to expected frontend format
   */
  async uploadDocument(
    requestId: string,
    documentCode: string,
    file: File,
    face?: string
  ): Promise<DocumentUploadResponse> {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('document_code', documentCode)
    if (face) formData.append('face', face)

    // Backend returns: { document_id, document_code, extraction, confidence, processor, status, needs_review }
    interface BackendDocumentUploadResponse {
      document_id: string
      document_code: string
      extraction: Record<string, unknown>
      confidence: number
      processor: string
      status: string
      needs_review: boolean
    }

    const backendResponse = await this.uploadRequest<BackendDocumentUploadResponse>(
      `/${requestId}/documents`,
      formData
    )

    // Transform to frontend expected format
    // Create a ServiceRequestDocument from the backend response
    const document: ServiceRequestDocument = {
      id: backendResponse.document_id,
      requestId: requestId,
      documentCode: backendResponse.document_code,
      documentNameEs: backendResponse.document_code,
      fileName: file.name,
      fileUrl: '',
      fileSize: file.size,
      mimeType: file.type,
      extractionStatus: backendResponse.status === 'success' ? ExtractionStatus.COMPLETED :
                        backendResponse.status === 'failed' ? ExtractionStatus.FAILED : ExtractionStatus.MANUAL_REVIEW,
      extractedData: backendResponse.extraction,
      extractionConfidence: backendResponse.confidence,
      uploadedAt: new Date().toISOString(),
    }

    return {
      document,
      extractedData: backendResponse.extraction,
      validationErrors: backendResponse.needs_review ? ['Review required'] : undefined,
    }
  }

  /**
   * Get all documents for a request
   * Backend returns snake_case, we transform to camelCase
   */
  async getDocuments(requestId: string): Promise<ServiceRequestDocument[]> {
    interface BackendProvidedDocument {
      id: string
      document_code: string
      document_name: string
      file_path: string
      file_name: string
      file_size?: number
      mime_type?: string
      extraction_data: Record<string, unknown>
      extraction_confidence?: number
      extraction_status: string
      is_valid?: boolean
      validation_errors: string[]
    }

    const backendDocs = await this.request<BackendProvidedDocument[]>(`/${requestId}/documents`)

    return backendDocs.map((doc) => ({
      id: doc.id,
      requestId: requestId,
      documentCode: doc.document_code,
      documentNameEs: doc.document_name,
      fileName: doc.file_name,
      fileUrl: doc.file_path, // Firebase Storage path can be used as URL
      fileSize: doc.file_size || 0,
      mimeType: doc.mime_type || 'application/octet-stream',
      // Map backend status values to frontend enum
      // Backend returns: success, validated, failed, manual_review, low_confidence, pending
      extractionStatus: (['success', 'validated', 'completed'].includes(doc.extraction_status) ? ExtractionStatus.COMPLETED :
                         doc.extraction_status === 'failed' ? ExtractionStatus.FAILED :
                         ['manual_review', 'low_confidence'].includes(doc.extraction_status) ? ExtractionStatus.MANUAL_REVIEW :
                         ExtractionStatus.PENDING) as ExtractionStatus,
      extractedData: doc.extraction_data,
      extractionConfidence: doc.extraction_confidence,
      validationErrors: doc.validation_errors,
      uploadedAt: new Date().toISOString(),
    }))
  }

  /**
   * Delete an uploaded document
   */
  async deleteDocument(requestId: string, documentId: string): Promise<void> {
    return this.request<void>(`/${requestId}/documents/${documentId}`, {
      method: 'DELETE',
    })
  }

  /**
   * Retry extraction for a document
   */
  async retryExtraction(
    requestId: string,
    documentId: string
  ): Promise<ServiceRequestDocument> {
    return this.request<ServiceRequestDocument>(
      `/${requestId}/documents/${documentId}/retry-extraction`,
      { method: 'POST' }
    )
  }

  /**
   * Update extracted data manually
   */
  async updateExtractedData(
    requestId: string,
    documentId: string,
    data: Record<string, unknown>
  ): Promise<ServiceRequestDocument> {
    return this.request<ServiceRequestDocument>(
      `/${requestId}/documents/${documentId}/extracted-data`,
      {
        method: 'PATCH',
        body: JSON.stringify(data),
      }
    )
  }

  // =========================================================================
  // VALIDATION & TARIFF
  // =========================================================================

  /**
   * Validate current step data
   */
  async validateStep(
    requestId: string,
    stepId: string,
    data: Record<string, unknown>
  ): Promise<ValidationResult[]> {
    return this.request<ValidationResult[]>(`/${requestId}/validate/${stepId}`, {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  /**
   * Run cross-document validation
   */
  async validateDocuments(requestId: string): Promise<ValidationResult[]> {
    const backendResults = await this.request<BackendValidationResult[]>(`/${requestId}/validate-documents`, {
      method: 'POST',
    })
    return backendResults.map(transformValidationResult)
  }

  /**
   * Calculate tariff for request
   */
  async calculateTariff(
    _requestId: string,
    _formData?: Record<string, unknown>
  ): Promise<TariffCalculation> {
    // TODO: Implement when backend endpoint exists
    // For now return a placeholder to avoid 404 errors
    return {
      baseAmount: 0,
      additionalFees: [],
      totalAmount: 0,
      currency: 'XAF',
      breakdown: '',
    }
  }

  // =========================================================================
  // SUBMISSION & PAYMENT
  // =========================================================================

  /**
   * Submit request for processing
   */
  async submitRequest(requestId: string): Promise<ServiceRequest> {
    const backend = await this.request<BackendServiceRequest>(`/${requestId}/submit`, {
      method: 'POST',
    })
    return transformServiceRequest(backend)
  }

  /**
   * Prepare request for payment.
   * Transitions status from DRAFT to PAYMENT_PENDING.
   * Called after form review validation, before payment step.
   */
  async prepareForPayment(requestId: string): Promise<ServiceRequest> {
    const backend = await this.request<BackendServiceRequest>(`/${requestId}/prepare-payment`, {
      method: 'POST',
    })
    return transformServiceRequest(backend)
  }

  /**
   * Get available payment methods for request
   */
  async getPaymentMethods(requestId: string): Promise<PaymentMethodsResponse> {
    interface BackendPaymentMethod {
      code: string
      label_es: string
      label_en: string
      label_fr: string
      processor_type: string
      requires_phone: boolean
      requires_redirect: boolean
      requires_agent_validation: boolean
    }
    interface BackendResponse {
      methods: BackendPaymentMethod[]
      default_method: string | null
    }

    const backend = await this.request<BackendResponse>(`/${requestId}/payment/methods`)

    return {
      methods: backend.methods.map(m => ({
        code: m.code,
        labelEs: m.label_es,
        labelEn: m.label_en,
        labelFr: m.label_fr,
        processorType: m.processor_type as 'gateway_api' | 'bange_api' | 'manual',
        requiresPhone: m.requires_phone,
        requiresRedirect: m.requires_redirect,
        requiresAgentValidation: m.requires_agent_validation,
      })),
      defaultMethod: backend.default_method,
    }
  }

  /**
   * Initiate payment for request
   * Returns full payment info including reference number and instructions for cash payments
   */
  async initiatePayment(
    requestId: string,
    paymentMethod: string,
    phoneNumber?: string
  ): Promise<PaymentInitiateResult> {
    interface BackendResponse {
      success: boolean
      payment_id: string
      payment_reference?: string
      status: string
      redirect_url?: string
      requires_action: boolean
      action_type?: string
      message_es?: string
      expires_at?: string
      error?: string
    }

    const backend = await this.request<BackendResponse>(
      `/${requestId}/payment/initiate`,
      {
        method: 'POST',
        body: JSON.stringify({ payment_method: paymentMethod, phone_number: phoneNumber }),
      }
    )

    // Transform snake_case to camelCase
    return {
      success: backend.success,
      paymentId: backend.payment_id,
      paymentReference: backend.payment_reference,
      status: backend.status,
      redirectUrl: backend.redirect_url,
      requiresAction: backend.requires_action,
      actionType: backend.action_type,
      messageEs: backend.message_es,
      expiresAt: backend.expires_at,
      error: backend.error,
    }
  }

  /**
   * Check payment status
   */
  async checkPaymentStatus(
    requestId: string
  ): Promise<{ status: string; paid: boolean }> {
    return this.request<{ status: string; paid: boolean }>(
      `/${requestId}/payment/status`
    )
  }

  // =========================================================================
  // AGENT OPERATIONS (for agent dashboard)
  // =========================================================================

  /**
   * List all requests for agents (with filters)
   */
  async listAllRequests(
    page: number = 1,
    pageSize: number = 10,
    filters?: ServiceRequestFilters
  ): Promise<ServiceRequestListResponse> {
    const params = new URLSearchParams({
      page: page.toString(),
      page_size: pageSize.toString(),
    })

    if (filters?.status) params.append('status', filters.status)
    if (filters?.workflowCode) params.append('workflow_code', filters.workflowCode)
    if (filters?.category) params.append('category', filters.category)
    if (filters?.search) params.append('search', filters.search)
    if (filters?.dateFrom) params.append('date_from', filters.dateFrom)
    if (filters?.dateTo) params.append('date_to', filters.dateTo)
    if (filters?.assignedAgentId) params.append('assigned_agent_id', filters.assignedAgentId)

    return this.request<ServiceRequestListResponse>(`/all?${params.toString()}`)
  }

  /**
   * Approve request
   */
  async approveRequest(
    requestId: string,
    notes?: string
  ): Promise<ServiceRequest> {
    const backend = await this.request<BackendServiceRequest>(`/${requestId}/approve`, {
      method: 'POST',
      body: JSON.stringify({ notes }),
    })
    return transformServiceRequest(backend)
  }

  /**
   * Reject request
   */
  async rejectRequest(
    requestId: string,
    reason: string,
    notes?: string
  ): Promise<ServiceRequest> {
    const backend = await this.request<BackendServiceRequest>(`/${requestId}/reject`, {
      method: 'POST',
      body: JSON.stringify({ reason, notes }),
    })
    return transformServiceRequest(backend)
  }

  /**
   * Request additional information
   */
  async requestAdditionalInfo(
    requestId: string,
    message: string,
    requiredDocuments?: string[]
  ): Promise<ServiceRequest> {
    const backend = await this.request<BackendServiceRequest>(`/${requestId}/request-info`, {
      method: 'POST',
      body: JSON.stringify({ message, required_documents: requiredDocuments }),
    })
    return transformServiceRequest(backend)
  }

  /**
   * Schedule appointment
   */
  async scheduleAppointment(
    requestId: string,
    date: string,
    time: string,
    location: string
  ): Promise<ServiceRequest> {
    const backend = await this.request<BackendServiceRequest>(`/${requestId}/appointment`, {
      method: 'POST',
      body: JSON.stringify({ date, time, location }),
    })
    return transformServiceRequest(backend)
  }

  /**
   * Add agent note
   */
  async addAgentNote(requestId: string, note: string): Promise<ServiceRequest> {
    const backend = await this.request<BackendServiceRequest>(`/${requestId}/notes`, {
      method: 'POST',
      body: JSON.stringify({ note }),
    })
    return transformServiceRequest(backend)
  }

  // =========================================================================
  // WORKFLOW STEP EXECUTION (NEW v2 ENDPOINTS)
  // =========================================================================

  /**
   * Execute a workflow step
   * Call without stepData to get step requirements
   * Call with stepData to complete the step
   */
  async executeStep(
    requestId: string,
    stepNumber: number,
    stepData?: Record<string, unknown>
  ): Promise<StepExecutionResponse> {
    return this.request<StepExecutionResponse>(`/${requestId}/step/${stepNumber}`, {
      method: 'POST',
      body: JSON.stringify({ step_data: stepData || null }),
    })
  }

  /**
   * Get pre-filled form data from document extraction
   * Uses workflow's form_mapping to transform extracted_data to form fields
   */
  async getFormData(requestId: string): Promise<FormDataResponse> {
    const backend = await this.request<BackendFormDataResponse>(`/${requestId}/form-data`)
    return transformFormDataResponse(backend)
  }

  /**
   * Get citizen summary for confirmation before submission
   * This is the "formulaire recapitulatif"
   */
  async getCitizenSummary(requestId: string): Promise<CitizenSummaryResponse> {
    const backend = await this.request<BackendCitizenSummaryResponse>(`/${requestId}/summary`)
    return transformCitizenSummaryResponse(backend)
  }

  /**
   * Get complete detail view for citizen "Mi Solicitud" page.
   * Single endpoint combining request data, stepper, data sections, notifications.
   * Backend returns snake_case for the nested `request` — transform to camelCase.
   */
  async getDetailView(requestId: string): Promise<DetailViewResponse> {
    interface BackendDetailViewResponse {
      request: BackendServiceRequest
      stepper_phases: DetailViewResponse['stepper_phases']
      current_phase_index: number
      data_sections: DetailViewResponse['data_sections']
      citizen_notifications: DetailViewResponse['citizen_notifications']
      unread_notification_count: number
      photo_url?: string | null
      tariff?: Record<string, unknown> | null
      payment_status?: string | null
      payment_reference?: string | null
      receipt_number?: string | null
      appointment?: { date?: string | null; time?: string | null; location?: string | null } | null
      documents: DetailViewResponse['documents']
      workflow_name_es: string
      solicitud_type_display?: string | null
      bundle_details?: DetailViewResponse['bundle_details']
    }

    const backend = await this.request<BackendDetailViewResponse>(`/${requestId}/detail-view`)

    return {
      request: transformServiceRequest(backend.request),
      stepper_phases: backend.stepper_phases,
      current_phase_index: backend.current_phase_index,
      data_sections: backend.data_sections,
      citizen_notifications: backend.citizen_notifications,
      unread_notification_count: backend.unread_notification_count,
      photo_url: backend.photo_url,
      tariff: backend.tariff,
      payment_status: backend.payment_status,
      payment_reference: backend.payment_reference,
      receipt_number: backend.receipt_number,
      appointment: backend.appointment,
      documents: backend.documents || [],
      workflow_name_es: backend.workflow_name_es,
      solicitud_type_display: backend.solicitud_type_display,
      bundle_details: backend.bundle_details,
    }
  }

  /**
   * Download citizen summary as PDF
   * Backend generates PDF using xhtml2pdf + Jinja2 template
   */
  async downloadSummaryPDF(requestId: string, language: string = 'es'): Promise<Blob> {
    const token = this.getToken()
    const response = await fetch(`${this.baseUrl}/${requestId}/summary/pdf?language=${language}`, {
      method: 'GET',
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    })
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Failed to download PDF' }))
      throw new Error(typeof error.detail === 'string' ? error.detail : 'Failed to download PDF')
    }
    return response.blob()
  }

  // =========================================================================
  // DOCUMENT PREVIEW/VALIDATE FLOW (RECOMMENDED)
  // =========================================================================

  /**
   * Preview document extraction before upload (Step 1 of 2)
   * Document is NOT uploaded to storage yet - just extracted for user review
   *
   * @param requestId - The service request ID
   * @param documentCode - The document type code
   * @param file - The file to extract data from
   * @param existingExtractions - Optional: Previously extracted data from other documents
   *                              (from preview cache) for cross-document risk analysis.
   *                              This enables DIP vs Passport comparison even before
   *                              documents are saved to DB.
   */
  async previewDocumentExtraction(
    requestId: string,
    documentCode: string,
    file: File,
    existingExtractions?: Record<string, Record<string, unknown>>
  ): Promise<DocumentExtractionPreview> {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('document_code', documentCode)

    // Pass existing extractions for cross-document risk analysis
    if (existingExtractions && Object.keys(existingExtractions).length > 0) {
      formData.append('existing_extractions', JSON.stringify(existingExtractions))
    }

    const backend = await this.uploadRequest<BackendDocumentExtractionPreview>(
      `/${requestId}/documents/preview`,
      formData
    )
    return transformDocumentExtractionPreview(backend)
  }

  /**
   * Validate and finalize document upload (Step 2 of 2)
   * User confirms/corrects extraction, then document is uploaded to storage
   */
  async validateAndUploadDocument(
    requestId: string,
    previewId: string,
    confirmedData: Record<string, unknown>,
    userNotes?: string
  ): Promise<DocumentValidationResponse> {
    const backend = await this.request<BackendDocumentValidationResponse>(`/${requestId}/documents/validate`, {
      method: 'POST',
      body: JSON.stringify({
        preview_id: previewId,
        confirmed_data: confirmedData,
        user_notes: userNotes,
      }),
    })
    return transformDocumentValidationResponse(backend)
  }

  // =========================================================================
  // APPOINTMENT METHODS (Citizen-First Flow)
  // =========================================================================

  /**
   * Get available locations for appointment selection
   */
  async getAppointmentLocations(requestId: string): Promise<{
    entityCode: string
    locations: Array<{
      id: string
      entityCode: string
      locationCode: string
      locationName: string
      city: string
      province?: string
      region?: string
      address?: string
      phone?: string
      email?: string
      isMainOffice: boolean
    }>
    count: number
  }> {
    const response = await this.request<{
      entity_code: string
      locations: Array<{
        id: string
        entity_code: string
        location_code: string
        location_name: string
        city: string
        province?: string
        region?: string
        address?: string
        phone?: string
        email?: string
        is_main_office: boolean
      }>
      count: number
    }>(`/${requestId}/appointments/locations`)

    return {
      entityCode: response.entity_code,
      locations: response.locations.map(loc => ({
        id: loc.id,
        entityCode: loc.entity_code,
        locationCode: loc.location_code,
        locationName: loc.location_name,
        city: loc.city,
        province: loc.province,
        region: loc.region,
        address: loc.address,
        phone: loc.phone,
        email: loc.email,
        isMainOffice: loc.is_main_office,
      })),
      count: response.count,
    }
  }

  /**
   * Get available appointment slots for a location
   * Migration 030: Uses entity_location_id FK instead of location_name
   */
  async getAppointmentSlots(
    requestId: string,
    entityLocationId: string,
    fromDate?: string,
    limit: number = 6
  ): Promise<{
    entityCode: string
    locationName: string
    fromDate: string
    slots: Array<{
      slotDate: string
      slotTime: string
      locationName: string
      locationAddress?: string
      slotsRemaining: number
      city?: string
    }>
    count: number
    hasAvailability: boolean
  }> {
    const params = new URLSearchParams({
      entity_location_id: entityLocationId,
      limit: limit.toString(),
    })
    if (fromDate) params.append('from_date', fromDate)

    const response = await this.request<{
      entity_code: string
      location_name: string
      from_date: string
      slots: Array<{
        slot_date: string
        slot_time: string
        location_name: string
        location_address?: string
        slots_remaining: number
        city?: string
      }>
      count: number
      has_availability: boolean
    }>(`/${requestId}/appointments/slots?${params.toString()}`)

    return {
      entityCode: response.entity_code,
      locationName: response.location_name,
      fromDate: response.from_date,
      slots: response.slots.map(slot => ({
        slotDate: slot.slot_date,
        slotTime: slot.slot_time,
        locationName: slot.location_name,
        locationAddress: slot.location_address,
        slotsRemaining: slot.slots_remaining,
        city: slot.city,
      })),
      count: response.count,
      hasAvailability: response.has_availability,
    }
  }

  /**
   * Get available days for calendar view (grouped by date)
   */
  async getAvailableDays(
    requestId: string,
    entityLocationId: string,
    fromDate?: string,
    toDate?: string
  ): Promise<{
    entityCode: string
    locationName: string
    fromDate: string
    toDate: string
    days: Array<{ date: string; timeSlotCount: number; totalSlotsRemaining: number }>
    count: number
    minDate?: string
  }> {
    const params = new URLSearchParams({ entity_location_id: entityLocationId })
    if (fromDate) params.append('from_date', fromDate)
    if (toDate) params.append('to_date', toDate)

    const response = await this.request<{
      entity_code: string
      location_name: string
      from_date: string
      to_date: string
      days: Array<{ slot_date: string; time_slot_count: number; total_slots_remaining: number }>
      count: number
      min_date?: string
    }>(`/${requestId}/appointments/available-days?${params.toString()}`)

    return {
      entityCode: response.entity_code,
      locationName: response.location_name,
      fromDate: response.from_date,
      toDate: response.to_date,
      days: response.days.map(d => ({
        date: d.slot_date,
        timeSlotCount: d.time_slot_count,
        totalSlotsRemaining: d.total_slots_remaining,
      })),
      count: response.count,
      minDate: response.min_date,
    }
  }

  /**
   * Hold an appointment slot before payment
   * Migration 030: Now uses entity_location_id FK instead of location_name/address
   */
  async holdAppointmentSlot(
    requestId: string,
    data: {
      entityLocationId: string  // FK to entity_locations table
      slotConfigId?: string     // Optional slot config ID
      appointmentDate: string
      appointmentTime: string
    }
  ): Promise<{
    success: boolean
    holdId?: string
    locationName?: string
    city?: string
    appointmentDate?: string
    appointmentTime?: string
    expiresAt?: string
    expiresInSeconds: number
    error?: string
  }> {
    const response = await this.request<{
      success: boolean
      hold_id?: string
      location_name?: string
      city?: string
      appointment_date?: string
      appointment_time?: string
      expires_at?: string
      expires_in_seconds: number
      error?: string
    }>(`/${requestId}/appointments/hold`, {
      method: 'POST',
      body: JSON.stringify({
        entity_location_id: data.entityLocationId,
        slot_config_id: data.slotConfigId,
        appointment_date: data.appointmentDate,
        appointment_time: data.appointmentTime,
      }),
    })

    return {
      success: response.success,
      holdId: response.hold_id,
      locationName: response.location_name,
      city: response.city,
      appointmentDate: response.appointment_date,
      appointmentTime: response.appointment_time,
      expiresAt: response.expires_at,
      expiresInSeconds: response.expires_in_seconds,
      error: response.error,
    }
  }

  /**
   * Get current hold status for a request
   */
  async getHoldStatus(requestId: string): Promise<{
    hasHold: boolean
    status?: 'held' | 'confirmed' | 'expired' | 'released' | 'fallback'
    locationName?: string
    city?: string
    appointmentDate?: string
    appointmentTime?: string
    expiresAt?: string
    isExpired: boolean
  }> {
    const response = await this.request<{
      has_hold: boolean
      status?: string
      location_name?: string
      city?: string
      appointment_date?: string
      appointment_time?: string
      expires_at?: string
      is_expired: boolean
    }>(`/${requestId}/appointments/hold-status`)

    return {
      hasHold: response.has_hold,
      status: response.status as 'held' | 'confirmed' | 'expired' | 'released' | 'fallback' | undefined,
      locationName: response.location_name,
      city: response.city,
      appointmentDate: response.appointment_date,
      appointmentTime: response.appointment_time,
      expiresAt: response.expires_at,
      isExpired: response.is_expired,
    }
  }

  /**
   * Release an appointment hold
   */
  async releaseHold(requestId: string): Promise<{
    success: boolean
    message: string
  }> {
    return this.request<{ success: boolean; message: string }>(`/${requestId}/appointments/hold`, {
      method: 'DELETE',
    })
  }

  /**
   * Submit without appointment (fallback when no slots available)
   * Migration 030: Now uses entity_location_id FK instead of location name
   */
  async submitWithoutAppointment(
    requestId: string,
    entityLocationId: string  // FK to entity_locations table
  ): Promise<{
    success: boolean
    locationName?: string
    message: string
    error?: string
  }> {
    const response = await this.request<{
      success: boolean
      location_name?: string
      message: string
      error?: string
    }>(`/${requestId}/appointments/fallback`, {
      method: 'POST',
      body: JSON.stringify({
        entity_location_id: entityLocationId,
      }),
    })

    return {
      success: response.success,
      locationName: response.location_name,
      message: response.message,
      error: response.error,
    }
  }

  /**
   * Confirm appointment hold after payment (for webhook integration)
   */
  async confirmAppointmentHold(requestId: string): Promise<{
    success: boolean
    appointmentDate?: string
    appointmentTime?: string
    locationName?: string
    city?: string
    error?: string
  }> {
    const response = await this.request<{
      success: boolean
      appointment_date?: string
      appointment_time?: string
      location_name?: string
      city?: string
      error?: string
    }>(`/${requestId}/appointments/confirm`, {
      method: 'POST',
    })

    return {
      success: response.success,
      appointmentDate: response.appointment_date,
      appointmentTime: response.appointment_time,
      locationName: response.location_name,
      city: response.city,
      error: response.error,
    }
  }

  // =========================================================================
  // HISTORY / TIMELINE OPERATIONS
  // =========================================================================

  /**
   * Get history timeline for a specific service request
   * Uses AGENT_ENDPOINT_BASE because history endpoints are under /agent/service-requests
   */
  async getRequestHistory(
    requestId: string,
    filters?: HistoryFilters,
    page: number = 1,
    pageSize: number = 50
  ): Promise<HistoryListResponse> {
    const params = new URLSearchParams({
      page: page.toString(),
      page_size: pageSize.toString(),
    })

    if (filters?.actionTypes?.length) {
      filters.actionTypes.forEach((t) => params.append('action_types', t))
    }
    if (filters?.fromDate) params.append('from_date', filters.fromDate)
    if (filters?.toDate) params.append('to_date', filters.toDate)
    if (filters?.includeSystem !== undefined) {
      params.append('include_system', filters.includeSystem.toString())
    }

    interface BackendHistoryResponse {
      request_id: string
      reference: string
      workflow_code: string
      solicitud_type?: string
      citizen_name?: string
      current_status: string
      entries: Array<{
        id: string
        action: string
        previous_status?: string
        new_status?: string
        details: Record<string, unknown>
        comment?: string
        performed_by?: {
          user_id?: string
          full_name: string
          email?: string
          role?: string
          is_system: boolean
        }
        performed_at: string
        source?: string
      }>
      total: number
      page: number
      page_size: number
      total_status_changes?: number
      total_documents?: number
      total_assignments?: number
      first_action_at?: string
      last_action_at?: string
    }

    const response = await this.agentRequest<BackendHistoryResponse>(
      `/${requestId}/history?${params.toString()}`
    )

    return {
      requestId: response.request_id,
      reference: response.reference,
      workflowCode: response.workflow_code,
      solicitudType: response.solicitud_type,
      citizenName: response.citizen_name,
      currentStatus: response.current_status,
      entries: response.entries.map((e) => ({
        id: e.id,
        action: e.action as HistoryActionType,
        previousStatus: e.previous_status,
        newStatus: e.new_status,
        details: e.details,
        comment: e.comment,
        performedBy: e.performed_by
          ? {
              userId: e.performed_by.user_id,
              fullName: e.performed_by.full_name,
              email: e.performed_by.email,
              role: e.performed_by.role,
              isSystem: e.performed_by.is_system,
            }
          : undefined,
        performedAt: e.performed_at,
        source: e.source as HistoryEntrySource | undefined,
      })),
      total: response.total,
      page: response.page,
      pageSize: response.page_size,
      totalStatusChanges: response.total_status_changes,
      totalDocuments: response.total_documents,
      totalAssignments: response.total_assignments,
      firstActionAt: response.first_action_at,
      lastActionAt: response.last_action_at,
    }
  }

  /**
   * List service requests with history summary for timeline page
   * Uses AGENT_ENDPOINT_BASE because history endpoints are under /agent/service-requests
   */
  async listRequestsWithHistory(
    entityCode: string,
    workflowCodes?: string[],
    statusFilter?: string,
    page: number = 1,
    pageSize: number = 20
  ): Promise<HistoryListSummaryResponse> {
    const params = new URLSearchParams({
      entity_code: entityCode,
      page: page.toString(),
      page_size: pageSize.toString(),
    })

    if (workflowCodes?.length) {
      workflowCodes.forEach((c) => params.append('workflow_codes', c))
    }
    if (statusFilter) params.append('status', statusFilter)

    interface BackendHistorySummaryResponse {
      items: Array<{
        request_id: string
        reference: string
        workflow_code: string
        citizen_name?: string
        current_status: string
        last_action: string
        last_action_at: string
        last_performer?: string
        total_actions: number
        days_since_created?: number
        is_stale?: boolean
      }>
      total: number
      page: number
      page_size: number
      workflow_codes?: string[]
      status_filter?: string
    }

    const response = await this.agentRequest<BackendHistorySummaryResponse>(
      `/history?${params.toString()}`
    )

    return {
      items: response.items.map((item) => ({
        requestId: item.request_id,
        reference: item.reference,
        workflowCode: item.workflow_code,
        citizenName: item.citizen_name,
        currentStatus: item.current_status,
        lastAction: item.last_action as HistoryActionType,
        lastActionAt: item.last_action_at,
        lastPerformer: item.last_performer,
        totalActions: item.total_actions,
        daysSinceCreated: item.days_since_created,
        isStale: item.is_stale,
      })),
      total: response.total,
      page: response.page,
      pageSize: response.page_size,
      workflowCodes: response.workflow_codes,
      statusFilter: response.status_filter,
    }
  }

  /**
   * Export history timeline as CSV or PDF
   * Returns a blob URL for download
   * Uses AGENT_ENDPOINT_BASE because history endpoints are under /agent/service-requests
   */
  async exportHistory(
    requestId: string,
    format: 'csv' | 'pdf' = 'csv',
    includeOcr: boolean = true,
    includeAssignments: boolean = true
  ): Promise<Blob> {
    const params = new URLSearchParams({
      format,
      include_ocr: includeOcr.toString(),
      include_assignments: includeAssignments.toString(),
    })

    const response = await fetch(
      `${API_BASE_URL}${API_VERSION}${AGENT_ENDPOINT_BASE}/${requestId}/history/export?${params}`,
      {
        method: 'GET',
        headers: {
          Authorization: `Bearer ${getAuthData()?.access_token}`,
        },
      }
    )

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.detail || 'Export failed')
    }

    return response.blob()
  }

  /**
   * Get history statistics
   * Uses AGENT_ENDPOINT_BASE because history endpoints are under /agent/service-requests
   */
  async getHistoryStatistics(
    entityCode: string,
    days: number = 30,
    workflowCodes?: string[]
  ): Promise<HistoryStatistics> {
    const params = new URLSearchParams({
      entity_code: entityCode,
      days: days.toString(),
    })

    if (workflowCodes?.length) {
      workflowCodes.forEach((c) => params.append('workflow_codes', c))
    }

    interface BackendStatsResponse {
      period_days: number
      action_distribution: Array<{ action: string; count: number }>
      avg_time_by_status: Array<{ status: string; avg_hours: number; transitions: number }>
      daily_activity: Array<{ date: string; actions: number; requests: number }>
      total_actions: number
      total_requests: number
      busiest_day?: string
      most_common_action?: string
    }

    const response = await this.agentRequest<BackendStatsResponse>(
      `/history/statistics?${params}`
    )

    return {
      periodDays: response.period_days,
      actionDistribution: response.action_distribution,
      avgTimeByStatus: response.avg_time_by_status.map((s) => ({
        status: s.status,
        avgHours: s.avg_hours,
        transitions: s.transitions,
      })),
      dailyActivity: response.daily_activity,
      totalActions: response.total_actions,
      totalRequests: response.total_requests,
      busiestDay: response.busiest_day,
      mostCommonAction: response.most_common_action,
    }
  }
}

// =========================================================================
// RESPONSE TYPES FOR NEW ENDPOINTS
// =========================================================================

export interface StepExecutionResponse {
  step_number: number
  step_id: string
  step_type: string
  success: boolean
  options?: string[]
  selection?: string
  documents_required?: Array<{
    code: string
    name_es: string
    is_required: boolean
    uploaded?: boolean
    schema_key?: string
  }>
  missing_documents?: Array<{ code: string; name_es: string }>
  form_data?: Record<string, unknown>
  extracted_data?: Record<string, unknown>
  requires_review?: boolean
  validation_complete?: boolean
  has_errors?: boolean
  errors?: Array<{ rule_id: string; message_es: string; document_code?: string }>
  warnings?: Array<{ rule_id: string; message_es: string; document_code?: string }>
  amount?: number
  tariff_breakdown?: Record<string, unknown>
  payment_methods?: string[]
  next_step?: {
    number: number
    id: string
    type: string
    title_es: string
  }
  error?: string
}

// Export singleton instance
export const serviceRequestsApi = new ServiceRequestsApiClient()
