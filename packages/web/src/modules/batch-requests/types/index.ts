/**
 * Batch Requests Module - Type Definitions
 * Matches backend batch_request.py Pydantic models + batch_session_service.py
 */

// ============================================================================
// ENUMS
// ============================================================================

/**
 * BatchStatus - Matches backend BatchStatus enum
 * DRAFT → UPLOADING → CLASSIFYING → REVIEW → PAYMENT_PENDING → PAID → IN_PROGRESS → COMPLETED
 */
export enum BatchStatus {
  DRAFT = 'DRAFT',
  UPLOADING = 'UPLOADING',
  CLASSIFYING = 'CLASSIFYING',
  REVIEW = 'REVIEW',
  PAYMENT_PENDING = 'PAYMENT_PENDING',
  PAID = 'PAID',
  IN_PROGRESS = 'IN_PROGRESS',
  COMPLETED = 'COMPLETED',
}

/**
 * BatchItemStatus - Matches backend BatchItemStatus enum
 * PENDING → DOCUMENTS_ASSIGNED → REVIEW → READY → SUBMITTED → EXCLUDED
 */
export enum BatchItemStatus {
  PENDING = 'PENDING',
  DOCUMENTS_ASSIGNED = 'DOCUMENTS_ASSIGNED',
  REVIEW = 'REVIEW',
  READY = 'READY',
  SUBMITTED = 'SUBMITTED',
  EXCLUDED = 'EXCLUDED',
}

/**
 * Wizard step IDs for the batch wizard
 */
export enum BatchWizardStep {
  WORKFLOW_SELECTION = 0,
  BENEFICIARY_ROSTER = 1,
  SHARED_DOCUMENTS = 2,
  BULK_UPLOAD = 3,
  ASSIGNMENT_REVIEW = 4,
  DATA_GRID = 5,
  PAYMENT = 6,
}

/**
 * i18n keys for wizard step labels.
 * Use with useTranslations('batch'): t(BATCH_WIZARD_STEP_KEYS[step])
 */
export const BATCH_WIZARD_STEP_KEYS: Record<BatchWizardStep, string> = {
  [BatchWizardStep.WORKFLOW_SELECTION]: 'wizard.workflowSelection',
  [BatchWizardStep.BENEFICIARY_ROSTER]: 'wizard.beneficiaryRoster',
  [BatchWizardStep.SHARED_DOCUMENTS]: 'wizard.sharedDocuments',
  [BatchWizardStep.BULK_UPLOAD]: 'wizard.bulkUpload',
  [BatchWizardStep.ASSIGNMENT_REVIEW]: 'wizard.assignmentReview',
  [BatchWizardStep.DATA_GRID]: 'wizard.dataGrid',
  [BatchWizardStep.PAYMENT]: 'wizard.payment',
}

// ============================================================================
// BACKEND TYPES (snake_case — match API responses)
// ============================================================================

export interface BackendBatchItem {
  id: string
  batch_id: string
  beneficiary_name: string
  beneficiary_identifier: string | null
  beneficiary_identifier_type: string | null
  beneficiary_email: string | null
  beneficiary_phone: string | null
  status: string
  service_request_id: string | null
  assigned_documents: BackendAssignedDocument[]
  required_documents: string[]
  missing_documents: string[]
  conditions: Record<string, string>
  form_data: Record<string, unknown>
  item_amount: number | null
  validation_errors: BackendValidationError[]
  item_order: number
  created_at: string
  updated_at: string | null
}

export interface BackendAssignedDocument {
  document_code: string
  file_path: string
  file_name: string
  extraction_data?: Record<string, unknown>
  confidence?: number
  match_method?: string
  match_score?: number
}

export interface BackendValidationError {
  field?: string
  message: string
  severity?: 'error' | 'warning'
}

export interface BackendBatchRequest {
  id: string
  reference: string | null
  submitted_by: string
  company_id: string | null
  workflow_code: string
  solicitud_type: string
  entity_code: string | null
  total_items: number
  items_ready: number
  items_submitted: number
  items_completed: number
  status: string
  shared_documents: BackendSharedDocument[]
  per_item_amount: number | null
  total_amount: number | null
  currency: string
  created_at: string
  updated_at: string | null
  submitted_at: string | null
  completed_at: string | null
  notes: string | null
}

export interface BackendBatchDetailResponse extends BackendBatchRequest {
  items: BackendBatchItem[]
}

export interface BackendBatchListResponse {
  batches: BackendBatchRequest[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface BackendSharedDocument {
  document_code: string
  file_path: string
  file_name: string
  file_size?: number
  mime_type?: string
  uploaded_at?: string
}

// ============================================================================
// SESSION TYPES (from batch_session_service.py Redis session)
// ============================================================================

export interface BackendBatchSession {
  session_id: string
  user_id: string
  workflow_code: string
  solicitud_type: string
  company_id: string | null
  status: string
  beneficiaries: BackendSessionBeneficiary[]
  shared_documents: BackendSharedDocument[]
  form_data_grid: Record<string, Record<string, unknown>>
  classification_results: BackendClassificationResult[] | null
  per_item_tariffs: Record<string, BackendTariffBreakdown> | null
  total_amount: number | null
  created_at: string
  expires_at: string
}

export interface BackendSessionBeneficiary {
  id: string
  name: string
  identifier: string | null
  identifier_type: string | null
  email: string | null
  phone: string | null
  conditions: Record<string, string>
  assigned_documents: BackendAssignedDocument[]
  required_documents: string[]
  missing_documents: string[]
  status: string
}

export interface BackendTariffBreakdown {
  base_amount: number
  supplements: Array<{ code: string; label: string; amount: number }>
  supplements_total: number
  penalties_amount: number
  total_amount: number
  currency: string
}

// ============================================================================
// CLASSIFICATION + EXTRACTION RESULTS
// ============================================================================

export interface BackendClassificationResult {
  file_path: string
  file_name: string
  document_type: string
  confidence: number
  identity_extracted: {
    name?: string
    identifier?: string
    identifier_type?: string
  } | null
  matched_beneficiary_id: string | null
  match_method: string | null
  match_score: number | null
}

export interface BackendClassifyResponse {
  classifications: BackendClassificationResult[]
  assignments: BackendDocumentAssignment[]
  stats: {
    total_files: number
    classified: number
    matched: number
    unmatched: number
    shared: number
  }
}

export interface BackendDocumentAssignment {
  file_path: string
  file_name: string
  document_type: string
  beneficiary_id: string | null
  confidence: number
  match_method: string | null
  match_score: number | null
}

export interface BackendExtractResponse {
  extracted: number
  failed: number
  results: Array<{
    beneficiary_id: string
    document_code: string
    status: 'success' | 'failed'
    fields_extracted?: number
    error?: string
  }>
}

// ============================================================================
// FORM CONFIG (DataGrid columns)
// ============================================================================

export interface BackendBatchFormConfig {
  workflow_code: string
  solicitud_type: string
  sections: BackendBatchFormSection[]
  form_mapping: Record<string, string>
  total_fields: number
}

export interface BackendBatchFormSection {
  id: string
  title_es: string
  source_document: string | null
  fields: BackendBatchFormField[]
}

export interface BackendBatchFormField {
  key: string
  label_es: string
  type: string
  required: boolean
  readonly: boolean
  options?: Array<{ value: string; label: string }>
  placeholder_es?: string
  validation?: Record<string, unknown>
}

// ============================================================================
// PREPARE PAYMENT RESPONSE
// ============================================================================

export interface BackendPreparePaymentResponse {
  ready_count: number
  excluded_count: number
  ready_beneficiaries: Array<{
    id: string
    name: string
    amount: number
    currency: string
  }>
  excluded_beneficiaries: Array<{
    id: string
    name: string
    reason: string
  }>
  per_item_amount: number | null
  total_amount: number
  currency: string
  payment_methods: string[]
}

// ============================================================================
// SUBMIT RESPONSE
// ============================================================================

export interface BackendSubmitResponse {
  batch_id: string
  batch_reference: string
  status: string
  service_requests_created: number
  total_amount: number
  currency: string
  payment_type: string
  redirect_url?: string
  action_type?: string
  message?: string
}

// ============================================================================
// FRONTEND TYPES (camelCase)
// ============================================================================

export interface BatchRequest {
  id: string
  reference: string | null
  submittedBy: string
  companyId: string | null
  workflowCode: string
  solicitudType: string
  entityCode: string | null
  totalItems: number
  itemsReady: number
  itemsSubmitted: number
  itemsCompleted: number
  status: BatchStatus
  sharedDocuments: SharedDocument[]
  perItemAmount: number | null
  totalAmount: number | null
  currency: string
  createdAt: string
  updatedAt: string | null
  submittedAt: string | null
  completedAt: string | null
  notes: string | null
}

export interface BatchItem {
  id: string
  batchId: string
  beneficiaryName: string
  beneficiaryIdentifier: string | null
  beneficiaryIdentifierType: string | null
  beneficiaryEmail: string | null
  beneficiaryPhone: string | null
  status: BatchItemStatus
  serviceRequestId: string | null
  assignedDocuments: AssignedDocument[]
  requiredDocuments: string[]
  missingDocuments: string[]
  conditions: Record<string, string>
  formData: Record<string, unknown>
  itemAmount: number | null
  validationErrors: ValidationError[]
  itemOrder: number
  createdAt: string
  updatedAt: string | null
}

export interface AssignedDocument {
  documentCode: string
  filePath: string
  fileName: string
  extractionData?: Record<string, unknown>
  confidence?: number
  matchMethod?: string
  matchScore?: number
}

export interface SharedDocument {
  documentCode: string
  filePath: string
  fileName: string
  fileSize?: number
  mimeType?: string
  uploadedAt?: string
}

export interface ValidationError {
  field?: string
  message: string
  severity?: 'error' | 'warning'
}

export interface BatchDetail extends BatchRequest {
  items: BatchItem[]
}

export interface BatchListResponse {
  batches: BatchRequest[]
  total: number
  page: number
  pageSize: number
  totalPages: number
}

// ============================================================================
// SESSION (Frontend)
// ============================================================================

export interface BatchSession {
  sessionId: string
  userId: string
  workflowCode: string
  solicitudType: string
  companyId: string | null
  status: string
  beneficiaries: SessionBeneficiary[]
  sharedDocuments: SharedDocument[]
  formDataGrid: Record<string, Record<string, unknown>>
  classificationResults: ClassificationResult[] | null
  perItemTariffs: Record<string, TariffBreakdown> | null
  totalAmount: number | null
  createdAt: string
  expiresAt: string
}

export interface SessionBeneficiary {
  id: string
  name: string
  identifier: string | null
  identifierType: string | null
  email: string | null
  phone: string | null
  conditions: Record<string, string>
  assignedDocuments: AssignedDocument[]
  requiredDocuments: string[]
  missingDocuments: string[]
  status: string
}

export interface TariffBreakdown {
  baseAmount: number
  supplements: Array<{ code: string; label: string; amount: number }>
  supplementsTotal: number
  penaltiesAmount: number
  totalAmount: number
  currency: string
}

export interface ClassificationResult {
  filePath: string
  fileName: string
  documentType: string
  confidence: number
  identityExtracted: {
    name?: string
    identifier?: string
    identifierType?: string
  } | null
  matchedBeneficiaryId: string | null
  matchMethod: string | null
  matchScore: number | null
}

export interface ClassifyResponse {
  classifications: ClassificationResult[]
  assignments: DocumentAssignment[]
  stats: {
    totalFiles: number
    classified: number
    matched: number
    unmatched: number
    shared: number
  }
}

export interface DocumentAssignment {
  filePath: string
  fileName: string
  documentType: string
  beneficiaryId: string | null
  confidence: number
  matchMethod: string | null
  matchScore: number | null
}

export interface ExtractResponse {
  extracted: number
  failed: number
  results: Array<{
    beneficiaryId: string
    documentCode: string
    status: 'success' | 'failed'
    fieldsExtracted?: number
    error?: string
  }>
}

export interface BatchFormConfig {
  workflowCode: string
  solicitudType: string
  sections: BatchFormSection[]
  formMapping: Record<string, string>
  totalFields: number
}

export interface BatchFormSection {
  id: string
  titleEs: string
  sourceDocument: string | null
  fields: BatchFormField[]
}

export interface BatchFormField {
  key: string
  labelEs: string
  type: string
  required: boolean
  readonly: boolean
  options?: Array<{ value: string; label: string }>
  placeholderEs?: string
  validation?: Record<string, unknown>
}

export interface PreparePaymentResult {
  readyCount: number
  excludedCount: number
  readyBeneficiaries: Array<{
    id: string
    name: string
    amount: number
    currency: string
  }>
  excludedBeneficiaries: Array<{
    id: string
    name: string
    reason: string
  }>
  perItemAmount: number | null
  totalAmount: number
  currency: string
  paymentMethods: string[]
}

export interface SubmitResult {
  batchId: string
  batchReference: string
  status: string
  serviceRequestsCreated: number
  totalAmount: number
  currency: string
  paymentType: string
  redirectUrl?: string
  actionType?: string
  message?: string
}

// ============================================================================
// REQUEST TYPES (camelCase frontend — transformed to snake_case in API client)
// ============================================================================

export interface BatchCreateRequest {
  workflowCode: string
  solicitudType?: string
  companyId?: string
  entityCode?: string
  notes?: string
}

export interface BeneficiaryCreateRequest {
  beneficiaryName: string
  beneficiaryIdentifier?: string
  beneficiaryIdentifierType?: string
  beneficiaryEmail?: string
  beneficiaryPhone?: string
  conditions?: Record<string, string>
  itemOrder?: number
}

export interface BeneficiaryUpdateRequest {
  beneficiaryName?: string
  beneficiaryIdentifier?: string
  beneficiaryIdentifierType?: string
  beneficiaryEmail?: string
  beneficiaryPhone?: string
  conditions?: Record<string, string>
  formData?: Record<string, unknown>
  status?: string
}

export interface SubmitRequest {
  paymentMethod: string
  phoneNumber?: string
  userEmail?: string
  userPhone?: string
  userName?: string
}

// ============================================================================
// WORKFLOW METADATA (F-005/F-006/F-007)
// ============================================================================

export interface WorkflowDocumentOption {
  code: string
  name_es: string
  is_required: boolean
  display_order: number
  instructions_es: string | null
  accepted_formats: string[]
}

export interface WorkflowSelectionField {
  key: string
  label_es: string
  type: 'radio' | 'select'
  options: Array<{ value: string; label_es: string }>
  condition?: Record<string, unknown>
}

export interface BatchWorkflowOption {
  code: string
  all_workflow_codes: string[]
  category: string
  service_name_es: string
  allowed_solicitud_types: string[]
  allowed_sub_types: string[]
  requires_appointment: boolean
  documents_by_solicitud_type: Record<string, WorkflowDocumentOption[]>
  selection_fields: WorkflowSelectionField[]
}

export interface BatchWorkflowsResponse {
  workflows: BatchWorkflowOption[]
  count: number
}

// ============================================================================
// REQUEST TRANSFORMS (camelCase → snake_case for backend)
// ============================================================================

export function toBackendBatchCreate(r: BatchCreateRequest) {
  return {
    workflow_code: r.workflowCode,
    solicitud_type: r.solicitudType,
    company_id: r.companyId,
    entity_code: r.entityCode,
    notes: r.notes,
  }
}

export function toBackendBeneficiaryCreate(r: BeneficiaryCreateRequest) {
  return {
    beneficiary_name: r.beneficiaryName,
    beneficiary_identifier: r.beneficiaryIdentifier,
    beneficiary_identifier_type: r.beneficiaryIdentifierType,
    beneficiary_email: r.beneficiaryEmail,
    beneficiary_phone: r.beneficiaryPhone,
    conditions: r.conditions,
    item_order: r.itemOrder,
  }
}

export function toBackendBeneficiaryUpdate(r: BeneficiaryUpdateRequest) {
  return {
    beneficiary_name: r.beneficiaryName,
    beneficiary_identifier: r.beneficiaryIdentifier,
    beneficiary_identifier_type: r.beneficiaryIdentifierType,
    beneficiary_email: r.beneficiaryEmail,
    beneficiary_phone: r.beneficiaryPhone,
    conditions: r.conditions,
    form_data: r.formData,
    status: r.status,
  }
}

export function toBackendSubmit(r: SubmitRequest) {
  return {
    payment_method: r.paymentMethod,
    phone_number: r.phoneNumber,
    user_email: r.userEmail,
    user_phone: r.userPhone,
    user_name: r.userName,
  }
}

// ============================================================================
// TRANSFORM FUNCTIONS (Backend → Frontend)
// ============================================================================

export function transformBatchRequest(b: BackendBatchRequest): BatchRequest {
  return {
    id: b.id,
    reference: b.reference,
    submittedBy: b.submitted_by,
    companyId: b.company_id,
    workflowCode: b.workflow_code,
    solicitudType: b.solicitud_type,
    entityCode: b.entity_code,
    totalItems: b.total_items,
    itemsReady: b.items_ready,
    itemsSubmitted: b.items_submitted,
    itemsCompleted: b.items_completed,
    status: b.status as BatchStatus,
    sharedDocuments: (b.shared_documents || []).map(transformSharedDocument),
    perItemAmount: b.per_item_amount,
    totalAmount: b.total_amount,
    currency: b.currency,
    createdAt: b.created_at,
    updatedAt: b.updated_at,
    submittedAt: b.submitted_at,
    completedAt: b.completed_at,
    notes: b.notes,
  }
}

export function transformBatchItem(i: BackendBatchItem): BatchItem {
  return {
    id: i.id,
    batchId: i.batch_id,
    beneficiaryName: i.beneficiary_name,
    beneficiaryIdentifier: i.beneficiary_identifier,
    beneficiaryIdentifierType: i.beneficiary_identifier_type,
    beneficiaryEmail: i.beneficiary_email,
    beneficiaryPhone: i.beneficiary_phone,
    status: i.status as BatchItemStatus,
    serviceRequestId: i.service_request_id,
    assignedDocuments: (i.assigned_documents || []).map(transformAssignedDocument),
    requiredDocuments: i.required_documents || [],
    missingDocuments: i.missing_documents || [],
    conditions: i.conditions || {},
    formData: i.form_data || {},
    itemAmount: i.item_amount,
    validationErrors: (i.validation_errors || []).map(transformValidationError),
    itemOrder: i.item_order,
    createdAt: i.created_at,
    updatedAt: i.updated_at,
  }
}

function transformAssignedDocument(d: BackendAssignedDocument): AssignedDocument {
  return {
    documentCode: d.document_code,
    filePath: d.file_path,
    fileName: d.file_name,
    extractionData: d.extraction_data,
    confidence: d.confidence,
    matchMethod: d.match_method,
    matchScore: d.match_score,
  }
}

export function transformSharedDocument(d: BackendSharedDocument): SharedDocument {
  return {
    documentCode: d.document_code,
    filePath: d.file_path,
    fileName: d.file_name,
    fileSize: d.file_size,
    mimeType: d.mime_type,
    uploadedAt: d.uploaded_at,
  }
}

function transformValidationError(e: BackendValidationError): ValidationError {
  return {
    field: e.field,
    message: e.message,
    severity: e.severity,
  }
}

export function transformBatchSession(s: BackendBatchSession): BatchSession {
  return {
    sessionId: s.session_id,
    userId: s.user_id,
    workflowCode: s.workflow_code,
    solicitudType: s.solicitud_type,
    companyId: s.company_id,
    status: s.status,
    beneficiaries: (s.beneficiaries || []).map(transformSessionBeneficiary),
    sharedDocuments: (s.shared_documents || []).map(transformSharedDocument),
    formDataGrid: s.form_data_grid || {},
    classificationResults: s.classification_results
      ? s.classification_results.map(transformClassificationResult)
      : null,
    perItemTariffs: s.per_item_tariffs
      ? Object.fromEntries(
          Object.entries(s.per_item_tariffs).map(([k, v]) => [k, transformTariff(v)])
        )
      : null,
    totalAmount: s.total_amount,
    createdAt: s.created_at,
    expiresAt: s.expires_at,
  }
}

export function transformSessionBeneficiary(b: BackendSessionBeneficiary): SessionBeneficiary {
  return {
    id: b.id,
    name: b.name,
    identifier: b.identifier,
    identifierType: b.identifier_type,
    email: b.email,
    phone: b.phone,
    conditions: b.conditions || {},
    assignedDocuments: (b.assigned_documents || []).map(transformAssignedDocument),
    requiredDocuments: b.required_documents || [],
    missingDocuments: b.missing_documents || [],
    status: b.status,
  }
}

function transformClassificationResult(c: BackendClassificationResult): ClassificationResult {
  return {
    filePath: c.file_path,
    fileName: c.file_name,
    documentType: c.document_type,
    confidence: c.confidence,
    identityExtracted: c.identity_extracted
      ? {
          name: c.identity_extracted.name,
          identifier: c.identity_extracted.identifier,
          identifierType: c.identity_extracted.identifier_type,
        }
      : null,
    matchedBeneficiaryId: c.matched_beneficiary_id,
    matchMethod: c.match_method,
    matchScore: c.match_score,
  }
}

function transformTariff(t: BackendTariffBreakdown): TariffBreakdown {
  return {
    baseAmount: t.base_amount,
    supplements: t.supplements || [],
    supplementsTotal: t.supplements_total,
    penaltiesAmount: t.penalties_amount,
    totalAmount: t.total_amount,
    currency: t.currency,
  }
}

export function transformClassifyResponse(r: BackendClassifyResponse): ClassifyResponse {
  return {
    classifications: r.classifications.map(transformClassificationResult),
    assignments: r.assignments.map((a) => ({
      filePath: a.file_path,
      fileName: a.file_name,
      documentType: a.document_type,
      beneficiaryId: a.beneficiary_id,
      confidence: a.confidence,
      matchMethod: a.match_method,
      matchScore: a.match_score,
    })),
    stats: {
      totalFiles: r.stats.total_files,
      classified: r.stats.classified,
      matched: r.stats.matched,
      unmatched: r.stats.unmatched,
      shared: r.stats.shared,
    },
  }
}

export function transformExtractResponse(r: BackendExtractResponse): ExtractResponse {
  return {
    extracted: r.extracted,
    failed: r.failed,
    results: r.results.map((x) => ({
      beneficiaryId: x.beneficiary_id,
      documentCode: x.document_code,
      status: x.status,
      fieldsExtracted: x.fields_extracted,
      error: x.error,
    })),
  }
}

export function transformFormConfig(c: BackendBatchFormConfig): BatchFormConfig {
  return {
    workflowCode: c.workflow_code,
    solicitudType: c.solicitud_type,
    sections: c.sections.map((s) => ({
      id: s.id,
      titleEs: s.title_es,
      sourceDocument: s.source_document,
      fields: s.fields.map((f) => ({
        key: f.key,
        labelEs: f.label_es,
        type: f.type,
        required: f.required,
        readonly: f.readonly,
        options: f.options,
        placeholderEs: f.placeholder_es,
        validation: f.validation,
      })),
    })),
    formMapping: c.form_mapping,
    totalFields: c.total_fields,
  }
}

export function transformPreparePayment(
  r: BackendPreparePaymentResponse
): PreparePaymentResult {
  return {
    readyCount: r.ready_count,
    excludedCount: r.excluded_count,
    readyBeneficiaries: r.ready_beneficiaries,
    excludedBeneficiaries: r.excluded_beneficiaries,
    perItemAmount: r.per_item_amount,
    totalAmount: r.total_amount,
    currency: r.currency,
    paymentMethods: r.payment_methods,
  }
}

export function transformSubmitResult(r: BackendSubmitResponse): SubmitResult {
  return {
    batchId: r.batch_id,
    batchReference: r.batch_reference,
    status: r.status,
    serviceRequestsCreated: r.service_requests_created,
    totalAmount: r.total_amount,
    currency: r.currency,
    paymentType: r.payment_type,
    redirectUrl: r.redirect_url,
    actionType: r.action_type,
    message: r.message,
  }
}

// ============================================================================
// HELPERS
// ============================================================================

export function getBatchStatusColor(status: BatchStatus): string {
  switch (status) {
    case BatchStatus.DRAFT:
      return 'bg-gray-100 text-gray-700'
    case BatchStatus.UPLOADING:
    case BatchStatus.CLASSIFYING:
      return 'bg-blue-100 text-blue-700'
    case BatchStatus.REVIEW:
      return 'bg-yellow-100 text-yellow-700'
    case BatchStatus.PAYMENT_PENDING:
      return 'bg-orange-100 text-orange-700'
    case BatchStatus.PAID:
      return 'bg-green-100 text-green-700'
    case BatchStatus.IN_PROGRESS:
      return 'bg-purple-100 text-purple-700'
    case BatchStatus.COMPLETED:
      return 'bg-emerald-100 text-emerald-700'
    default:
      return 'bg-gray-100 text-gray-700'
  }
}

/**
 * i18n key for batch status. Use with useTranslations('batch'): t(getBatchStatusKey(status))
 */
export function getBatchStatusKey(status: BatchStatus): string {
  return `status.${status}`
}

/**
 * i18n key for item status. Use with useTranslations('batch'): t(getBatchItemStatusKey(status))
 */
export function getBatchItemStatusKey(status: BatchItemStatus): string {
  return `itemStatus.${status}`
}

export function getItemStatusColor(status: BatchItemStatus): string {
  switch (status) {
    case BatchItemStatus.PENDING:
      return 'bg-gray-100 text-gray-700'
    case BatchItemStatus.DOCUMENTS_ASSIGNED:
      return 'bg-blue-100 text-blue-700'
    case BatchItemStatus.REVIEW:
      return 'bg-yellow-100 text-yellow-700'
    case BatchItemStatus.READY:
      return 'bg-green-100 text-green-700'
    case BatchItemStatus.SUBMITTED:
      return 'bg-emerald-100 text-emerald-700'
    case BatchItemStatus.EXCLUDED:
      return 'bg-red-100 text-red-700'
    default:
      return 'bg-gray-100 text-gray-700'
  }
}
