/**
 * Wizard Session Types - Cache-First Architecture
 *
 * Matches backend models in:
 *   packages/backend/app/modules/service_requests/models/wizard_session.py
 *
 * Backend responses use snake_case. These types use camelCase for frontend.
 *
 * @since v2.0 - Cache-first wizard migration
 * @see .claude/plans/CACHE_FIRST_WIZARD_MIGRATION_PLAN.md
 */

// ============================================================================
// ENUMS
// ============================================================================

export enum WizardSessionStatus {
  ACTIVE = 'active',
  DOCUMENTS_UPLOADED = 'documents_uploaded',
  READY_FOR_PAYMENT = 'ready_for_payment',
  PAYMENT_INITIATED = 'payment_initiated',
  PERSISTED = 'persisted',
  EXPIRED = 'expired',
  CANCELLED = 'cancelled',
}

// ============================================================================
// BACKEND RESPONSE TYPES (snake_case - direct from API)
// ============================================================================

/** Matches WizardSessionResponse in wizard_session.py */
export interface BackendWizardSessionResponse {
  session_id: string
  workflow_code: string
  solicitud_type: string
  sub_type: string | null
  motivo: string | null
  is_minor: boolean

  status: WizardSessionStatus
  current_step: number
  current_step_id: string | null

  documents_count: number
  documents_uploaded: string[]

  form_data: Record<string, unknown>
  extracted_data: Record<string, unknown>

  tariff: TariffBreakdown | null

  created_at: string
  updated_at: string
  expires_at: string
  ttl_seconds: number

  required_documents: BackendRequiredDocument[]

  // Workflow capabilities
  requires_appointment: boolean
  entity_code: string | null

  // Appointment selection (cached in session, not a real hold)
  appointment_data: {
    entity_location_id: string
    location_name: string
    city: string
    appointment_date: string
    appointment_time: string
    slot_config_id: string | null
  } | null

  // Site selection (for non-appointment workflows)
  site_selection: {
    entity_location_id: string
    location_name: string
    city: string
    entity_code: string | null
  } | null
}

export interface BackendRequiredDocument {
  code: string
  name_es: string
  is_required: boolean
  uploaded: boolean
}

/** Matches WizardDocumentPreviewResponse */
export interface BackendDocumentPreviewResponse {
  session_id: string
  document_code: string
  document_name: string | null
  file_name: string
  file_size: number

  extraction: Record<string, unknown>
  confidence: number
  processor: string
  extraction_status: string
  needs_correction: boolean

  risk_analysis: Record<string, unknown> | null
  cross_validation: Record<string, unknown> | null

  expires_at: string
  ttl_seconds: number
}

/** Payment method info from backend */
export interface BackendPaymentMethodInfo {
  code: string
  label_es: string
  label_en: string
  label_fr: string
  processor_type: string
  requires_phone: boolean
  requires_redirect: boolean
  requires_agent_validation: boolean
}

/** Matches WizardPreparePaymentResponse */
export interface BackendPreparePaymentResponse {
  session_id: string
  ready_for_payment: boolean

  tariff: TariffBreakdown
  total_amount: number
  currency: string

  validation_passed: boolean
  errors: ValidationItem[]
  warnings: ValidationItem[]

  all_documents_uploaded: boolean
  missing_documents: string[]

  payment_methods: BackendPaymentMethodInfo[]
  default_payment_method: string | null
}

/** Matches WizardPersistResult */
export interface BackendPersistResult {
  success: boolean
  service_request_id: string | null
  reference: string | null
  payment_id: string | null
  error: string | null
  error_code: string | null
}

/** Matches WizardInitiatePaymentResponse (atomic persist + pay) */
export interface BackendInitiatePaymentResponse {
  success: boolean
  service_request_id: string | null
  reference: string | null
  payment_id: string | null
  payment_reference: string | null
  payment_status: string | null
  redirect_url: string | null
  requires_action: boolean
  action_type: string | null
  message_es: string | null
  expires_at: string | null
  requires_appointment: boolean
  appointment_confirmed: boolean
  appointment_date: string | null
  appointment_time: string | null
  appointment_location: string | null
  error: string | null
  error_code: string | null
}

// ============================================================================
// FRONTEND TYPES (camelCase - used in components)
// ============================================================================

export interface WizardSession {
  sessionId: string
  workflowCode: string
  solicitudType: string
  subType: string | null
  motivo: string | null
  isMinor: boolean

  status: WizardSessionStatus
  currentStep: number
  currentStepId: string | null

  documentsCount: number
  documentsUploaded: string[]

  formData: Record<string, unknown>
  extractedData: Record<string, unknown>

  tariff: TariffBreakdown | null

  createdAt: string
  updatedAt: string
  expiresAt: string
  ttlSeconds: number

  requiredDocuments: RequiredDocument[]

  // Workflow capabilities
  requiresAppointment: boolean
  entityCode: string | null

  // Appointment selection (cached in session)
  appointmentData: {
    entityLocationId: string
    locationName: string
    city: string
    appointmentDate: string
    appointmentTime: string
    slotConfigId: string | null
  } | null

  // Site selection (for non-appointment workflows)
  siteSelection: {
    entityLocationId: string
    locationName: string
    city: string
    entityCode: string | null
  } | null
}

export interface RequiredDocument {
  code: string
  nameEs: string
  isRequired: boolean
  uploaded: boolean
}

export interface DocumentPreview {
  sessionId: string
  documentCode: string
  documentName: string | null
  fileName: string
  fileSize: number

  extraction: Record<string, unknown>
  confidence: number
  processor: string
  extractionStatus: string
  needsCorrection: boolean

  riskAnalysis: Record<string, unknown> | null
  crossValidation: Record<string, unknown> | null

  expiresAt: string
  ttlSeconds: number
}

export interface PaymentMethodInfo {
  code: string
  labelEs: string
  labelEn: string
  labelFr: string
  processorType: string
  requiresPhone: boolean
  requiresRedirect: boolean
  requiresAgentValidation: boolean
}

export interface PreparePaymentResult {
  sessionId: string
  readyForPayment: boolean

  tariff: TariffBreakdown
  totalAmount: number
  currency: string

  validationPassed: boolean
  errors: ValidationItem[]
  warnings: ValidationItem[]

  allDocumentsUploaded: boolean
  missingDocuments: string[]

  paymentMethods: PaymentMethodInfo[]
  defaultPaymentMethod: string | null
}

export interface PersistResult {
  success: boolean
  serviceRequestId: string | null
  reference: string | null
  paymentId: string | null
  error: string | null
  errorCode: string | null
}

/** Frontend version of WizardInitiatePaymentResponse (camelCase) */
export interface InitiatePaymentResult {
  success: boolean
  serviceRequestId: string | null
  reference: string | null
  paymentId: string | null
  paymentReference: string | null
  paymentStatus: string | null
  redirectUrl: string | null
  requiresAction: boolean
  actionType: string | null
  messageEs: string | null
  expiresAt: string | null
  requiresAppointment: boolean
  appointmentConfirmed: boolean
  appointmentDate: string | null
  appointmentTime: string | null
  appointmentLocation: string | null
  error: string | null
  errorCode: string | null
}

// ============================================================================
// SHARED TYPES
// ============================================================================

export interface TariffBreakdown {
  base_amount: number
  supplements: TariffSupplement[]
  total_amount: number
  currency: string
  source?: string
}

export interface TariffSupplement {
  code: string
  label_es: string
  amount: number
}

export interface ValidationItem {
  rule_id: string
  message_es: string
  field: string | null
}

// ============================================================================
// REQUEST TYPES (sent to backend)
// ============================================================================

export interface WizardSessionCreateRequest {
  workflow_code: string
  solicitud_type?: string
  sub_type?: string | null
  motivo?: string | null
  is_minor?: boolean
}

export interface DocumentConfirmRequest {
  document_code: string
  confirmed_data: Record<string, unknown>
  user_notes?: string | null
}

export interface FormDataSaveRequest {
  form_data: Record<string, unknown>
  step_id?: string | null
}

// ============================================================================
// TRANSFORM FUNCTIONS (Backend snake_case → Frontend camelCase)
// ============================================================================

export function transformSession(
  backend: BackendWizardSessionResponse
): WizardSession {
  return {
    sessionId: backend.session_id,
    workflowCode: backend.workflow_code,
    solicitudType: backend.solicitud_type,
    subType: backend.sub_type,
    motivo: backend.motivo,
    isMinor: backend.is_minor,
    status: backend.status,
    currentStep: backend.current_step,
    currentStepId: backend.current_step_id,
    documentsCount: backend.documents_count,
    documentsUploaded: backend.documents_uploaded,
    formData: backend.form_data,
    extractedData: backend.extracted_data,
    tariff: backend.tariff,
    createdAt: backend.created_at,
    updatedAt: backend.updated_at,
    expiresAt: backend.expires_at,
    ttlSeconds: backend.ttl_seconds,
    requiredDocuments: (backend.required_documents || []).map(transformRequiredDocument),
    requiresAppointment: backend.requires_appointment ?? false,
    entityCode: backend.entity_code ?? null,
    appointmentData: backend.appointment_data
      ? {
          entityLocationId: backend.appointment_data.entity_location_id,
          locationName: backend.appointment_data.location_name,
          city: backend.appointment_data.city,
          appointmentDate: backend.appointment_data.appointment_date,
          appointmentTime: backend.appointment_data.appointment_time,
          slotConfigId: backend.appointment_data.slot_config_id ?? null,
        }
      : null,
    siteSelection: backend.site_selection
      ? {
          entityLocationId: backend.site_selection.entity_location_id,
          locationName: backend.site_selection.location_name,
          city: backend.site_selection.city,
          entityCode: backend.site_selection.entity_code ?? null,
        }
      : null,
  }
}

// ============================================================================
// SITE SELECTION TYPES
// ============================================================================

export interface SiteInfo {
  id: string
  entityCode: string
  city: string
  locationName: string
  locationAddress: string | null
  isMainOffice: boolean
}

export interface AvailableSitesResponse {
  workflow_code: string
  sites: Array<{
    id: string
    entity_code: string
    city: string
    location_name: string
    location_address: string | null
    is_main_office: boolean
  }>
  cities: Record<string, Array<{
    id: string
    entity_code: string
    city: string
    location_name: string
    location_address: string | null
    is_main_office: boolean
  }>>
  count: number
}

export interface SiteSelectionData {
  entityLocationId: string
  locationName: string
  city: string
  entityCode: string | null
}

function transformRequiredDocument(
  backend: BackendRequiredDocument
): RequiredDocument {
  return {
    code: backend.code,
    nameEs: backend.name_es,
    isRequired: backend.is_required,
    uploaded: backend.uploaded,
  }
}

export function transformDocumentPreview(
  backend: BackendDocumentPreviewResponse
): DocumentPreview {
  return {
    sessionId: backend.session_id,
    documentCode: backend.document_code,
    documentName: backend.document_name,
    fileName: backend.file_name,
    fileSize: backend.file_size,
    extraction: backend.extraction,
    confidence: backend.confidence,
    processor: backend.processor,
    extractionStatus: backend.extraction_status,
    needsCorrection: backend.needs_correction,
    riskAnalysis: backend.risk_analysis,
    crossValidation: backend.cross_validation,
    expiresAt: backend.expires_at,
    ttlSeconds: backend.ttl_seconds,
  }
}

function transformPaymentMethod(
  backend: BackendPaymentMethodInfo
): PaymentMethodInfo {
  return {
    code: backend.code,
    labelEs: backend.label_es,
    labelEn: backend.label_en,
    labelFr: backend.label_fr,
    processorType: backend.processor_type,
    requiresPhone: backend.requires_phone,
    requiresRedirect: backend.requires_redirect,
    requiresAgentValidation: backend.requires_agent_validation,
  }
}

export function transformPreparePayment(
  backend: BackendPreparePaymentResponse
): PreparePaymentResult {
  return {
    sessionId: backend.session_id,
    readyForPayment: backend.ready_for_payment,
    tariff: backend.tariff,
    totalAmount: backend.total_amount,
    currency: backend.currency,
    validationPassed: backend.validation_passed,
    errors: backend.errors,
    warnings: backend.warnings,
    allDocumentsUploaded: backend.all_documents_uploaded,
    missingDocuments: backend.missing_documents,
    paymentMethods: (backend.payment_methods || []).map(transformPaymentMethod),
    defaultPaymentMethod: backend.default_payment_method ?? null,
  }
}

export function transformPersistResult(
  backend: BackendPersistResult
): PersistResult {
  return {
    success: backend.success,
    serviceRequestId: backend.service_request_id,
    reference: backend.reference,
    paymentId: backend.payment_id,
    error: backend.error,
    errorCode: backend.error_code,
  }
}

export function transformInitiatePayment(
  backend: BackendInitiatePaymentResponse
): InitiatePaymentResult {
  return {
    success: backend.success,
    serviceRequestId: backend.service_request_id,
    reference: backend.reference,
    paymentId: backend.payment_id,
    paymentReference: backend.payment_reference,
    paymentStatus: backend.payment_status,
    redirectUrl: backend.redirect_url,
    requiresAction: backend.requires_action,
    actionType: backend.action_type,
    messageEs: backend.message_es,
    expiresAt: backend.expires_at,
    requiresAppointment: backend.requires_appointment ?? false,
    appointmentConfirmed: backend.appointment_confirmed ?? false,
    appointmentDate: backend.appointment_date ?? null,
    appointmentTime: backend.appointment_time ?? null,
    appointmentLocation: backend.appointment_location ?? null,
    error: backend.error,
    errorCode: backend.error_code,
  }
}

// ============================================================================
// CROSS-TYPE TRANSFORMS (Session ↔ Legacy)
// ============================================================================

/**
 * Transform a session DocumentPreview to the legacy DocumentExtractionPreview
 * format used by DocumentPreviewDialog.
 *
 * This adapter allows reusing the existing DocumentPreviewDialog component
 * with the cache-first wizard's preview response.
 */
export function transformPreviewToExtractionPreview(
  preview: DocumentPreview
): {
  previewId: string
  documentCode: string
  documentName: string
  fileName: string
  fileSize: number
  mimeType: string
  extraction: Record<string, unknown>
  confidence: number
  processor: 'gemini' | 'tesseract' | 'hybrid'
  fieldIndicators: Array<{
    fieldName: string
    value?: unknown
    confidence: number
    status: 'ok' | 'warning' | 'error' | 'missing'
    riskLevel?: 'low' | 'medium' | 'high' | 'critical'
    riskMessage?: string
    requiresAttention: boolean
    suggestion?: string
  }>
  riskAnalysis?: {
    riskLevel: string
    riskScore: number
    riskFactors: Array<{ type: string; severity: string; description: string }>
    recommendations: string[]
    requiresRejection: boolean
    requiresReview: boolean
    factorsCount: Record<string, number>
    identityMismatches?: Array<{
      field_name: string
      field_label: { es: string; fr: string; en: string }
      is_blocking: boolean
      source_document: { code: string; value: string }
      compared_document: { code: string; value: string }
      risk_code: string
      severity: string
    }>
    hasBlockingMismatches?: boolean
  }
  extractionStatus: string
  needsCorrection: boolean
  detectedDocumentType?: string
  documentTypeMatch: boolean
  expectedFields: Array<{ key: string; label: string; type: string; required: boolean }>
  expiresAt: string
  processingTimeMs?: number
} {
  // Parse risk analysis from generic Record to typed structure
  const ra = preview.riskAnalysis as Record<string, unknown> | null
  const riskAnalysis = ra ? {
    riskLevel: (ra.risk_level as string) || (ra.riskLevel as string) || 'low',
    riskScore: (ra.risk_score as number) || (ra.riskScore as number) || 0,
    riskFactors: (ra.risk_factors as Array<{ type: string; severity: string; description: string }>) ||
      (ra.riskFactors as Array<{ type: string; severity: string; description: string }>) || [],
    recommendations: (ra.recommendations as string[]) || [],
    requiresRejection: (ra.requires_rejection as boolean) || (ra.requiresRejection as boolean) || false,
    requiresReview: (ra.requires_review as boolean) || (ra.requiresReview as boolean) || false,
    factorsCount: (ra.factors_count as Record<string, number>) || (ra.factorsCount as Record<string, number>) || {},
    identityMismatches: (ra.identity_mismatches as Array<{
      field_name: string
      field_label: { es: string; fr: string; en: string }
      is_blocking: boolean
      source_document: { code: string; value: string }
      compared_document: { code: string; value: string }
      risk_code: string
      severity: string
    }>) || (ra.identityMismatches as unknown as Array<{
      field_name: string
      field_label: { es: string; fr: string; en: string }
      is_blocking: boolean
      source_document: { code: string; value: string }
      compared_document: { code: string; value: string }
      risk_code: string
      severity: string
    }>) || undefined,
    hasBlockingMismatches: (ra.has_blocking_mismatches as boolean) || (ra.hasBlockingMismatches as boolean) || false,
  } : undefined

  // Build field indicators from extraction data
  const fieldIndicators = Object.entries(preview.extraction).map(([key, value]) => ({
    fieldName: key,
    value,
    confidence: preview.confidence,
    status: (preview.confidence >= 0.7 ? 'ok' : 'warning') as 'ok' | 'warning' | 'error' | 'missing',
    requiresAttention: preview.confidence < 0.7,
  }))

  return {
    previewId: `${preview.sessionId}-${preview.documentCode}`,
    documentCode: preview.documentCode,
    documentName: preview.documentName || preview.documentCode,
    fileName: preview.fileName,
    fileSize: preview.fileSize,
    mimeType: 'application/octet-stream', // Not available from session preview
    extraction: preview.extraction,
    confidence: preview.confidence,
    processor: preview.processor as 'gemini' | 'tesseract' | 'hybrid',
    fieldIndicators,
    riskAnalysis,
    extractionStatus: preview.extractionStatus,
    needsCorrection: preview.needsCorrection,
    documentTypeMatch: true, // Default - session preview doesn't have this
    expectedFields: [], // Not available from session preview
    expiresAt: preview.expiresAt,
  }
}

// ============================================================================
// UI HELPERS
// ============================================================================

export function getSessionStatusColor(status: WizardSessionStatus): string {
  switch (status) {
    case WizardSessionStatus.ACTIVE:
      return 'blue'
    case WizardSessionStatus.DOCUMENTS_UPLOADED:
      return 'cyan'
    case WizardSessionStatus.READY_FOR_PAYMENT:
      return 'green'
    case WizardSessionStatus.PAYMENT_INITIATED:
      return 'orange'
    case WizardSessionStatus.PERSISTED:
      return 'green'
    case WizardSessionStatus.EXPIRED:
      return 'red'
    case WizardSessionStatus.CANCELLED:
      return 'gray'
    default:
      return 'gray'
  }
}
