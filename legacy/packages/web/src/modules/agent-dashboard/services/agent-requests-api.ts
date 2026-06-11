/**
 * Agent Service Requests API
 * API client for agent dashboard service requests operations
 *
 * @module agent-dashboard/services/agent-requests-api
 * @date 2026-01-25
 */

import { getAuthData } from '@/core/auth/storage';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const API_VERSION = '/api/v1';

// =============================================================================
// TYPES
// =============================================================================

export type ActionType = 'pending' | 'validation' | 'appointments' | 'history' | 'escalations';

export type SolicitudType = 'expedicion' | 'renovacion';

export type RenovacionMotivo = 'vencimiento' | 'perdida' | 'robo' | 'deterioro';

export type Priority = 'LOW' | 'NORMAL' | 'HIGH' | 'URGENT';

export type SlaStatus = 'on_track' | 'at_risk' | 'violated';

/** Normalize backend SLA values (warning/breached) to canonical SlaStatus */
function normalizeSlaStatus(raw: string | null | undefined): SlaStatus {
  switch (raw) {
    case 'at_risk':
    case 'warning':
      return 'at_risk';
    case 'violated':
    case 'breached':
      return 'violated';
    default:
      return 'on_track';
  }
}

export interface ServiceRequestListItem {
  id: string;
  reference: string;
  workflowCode: string;
  solicitudType: string;
  motivo: string | null;
  status: string;
  priority: Priority;
  citizenName: string;
  citizenEmail: string | null;
  submittedAt: string | null;
  createdAt: string;
  assignedTo: string | null;
  assignedAgentName: string | null;
  slaDeadline: string | null;
  slaStatus: SlaStatus;
  // Batch context
  batchId?: string | null;
  batchReference?: string | null;
  // Escalation context (only populated for action=escalations)
  escalationReason?: string | null;
  escalatedAt?: string | null;
  // True when request was returned from escalation by supervisor
  supervisorAssigned?: boolean;
}

export interface ServiceRequestListResponse {
  items: ServiceRequestListItem[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

export interface ServiceRequestFilters {
  action?: ActionType;
  status?: string;
  workflowCode?: string;
  solicitudType?: SolicitudType;
  motivo?: RenovacionMotivo;
  search?: string;
  priority?: Priority;
  agentId?: string;
  page?: number;
  pageSize?: number;
}

// Escalation item types
export interface EscalationHistoryEntry {
  action: string;
  performedAt: string;
  performedByName: string | null;
  comment: string | null;
}

export interface EscalationListItem {
  id: string;
  queueId: string;
  reason: string;
  priorityScore: number;
  status: string;
  escalationStatus: 'pending' | 'in_review' | 'resolved';
  caseReference: string;
  caseType: string;
  notes: string | null;
  createdAt: string;
  escalatedAt: string;
  direction: 'sent' | 'received';
  escalatedByName: string | null;
  citizenName: string | null;
  history: EscalationHistoryEntry[];
}

export interface PaginatedEscalationResponse {
  items: EscalationListItem[];
  total: number;
  page: number;
  pageSize: number;
}

interface BackendEscalationItem {
  id: string;
  queue_id: string;
  reason: string;
  priority_score: number;
  status: string;
  escalation_status: string;
  case_reference: string;
  case_type: string;
  notes?: string | null;
  created_at: string;
  escalated_at: string;
  direction: string;
  escalated_by_name?: string | null;
  citizen_name?: string | null;
  history?: Array<{
    action: string;
    performed_at: string;
    performed_by_name?: string | null;
    comment?: string | null;
  }>;
}

interface BackendPaginatedEscalation {
  items: BackendEscalationItem[];
  total: number;
  page: number;
  page_size: number;
}

// Workflow schema types for agent detail view
export interface WorkflowSchemaField {
  key: string;
  label: string;
  type: 'text' | 'date' | 'datetime' | 'email' | 'status';
  source?: 'request' | 'appointment' | 'form_data';
  default?: string;
}

export interface WorkflowSchemaSection {
  id: string;
  title: string;
  column: 'left' | 'right';
  fields: WorkflowSchemaField[];
}

export interface FormDisplaySchema {
  title: string;
  photoField?: string;
  layout: 'two-column' | 'single-column';
  sections: WorkflowSchemaSection[];
}

export interface AgentChecklistItem {
  id: string;
  label: string;
  required: boolean;
}

export interface WorkflowSchemaResponse {
  code: string;
  name: string;
  formDisplaySchema: FormDisplaySchema | null;
  agentChecklist: AgentChecklistItem[] | null;
}

export interface VerificationChecklistUpdate {
  checklist: Record<string, boolean>;
  verificationStatus?: 'pending' | 'in_progress' | 'verified' | 'partial_verification' | 'verification_failed';
  notes?: string;
}

export interface VerificationResponse {
  message: string;
  requestId: string;
  verificationStatus: string;
  checklistCompleted: number;
  checklistTotal: number;
}

// =============================================================================
// PREVIEW TYPES FOR SPLIT VIEW
// =============================================================================

/**
 * Structured data sections from display_config + OCR extraction_data.
 * Each section has a title and a list of label/value fields.
 */
export interface PreviewDataField {
  label: string;
  value: string;
}

export interface PreviewDataSection {
  title: string;
  fields: PreviewDataField[];
}

export interface RequestPreviewDocument {
  id: string;
  code: string;
  name: string;
  fileUrl?: string | null;
  mimeType?: string | null;  // For displaying image thumbnails
  validationStatus: string;
}

export interface RequestPreviewAppointment {
  date: string;
  time: string;
  locationName: string;
  locationAddress?: string | null;
}

export interface ServiceRequestPreview {
  id: string;
  reference: string;
  workflowCode: string;
  workflowLabel: string;
  solicitudType: string;
  motivo?: string | null;
  isMinor: boolean;
  status: string;
  priority: Priority;
  // SLA
  slaDeadline?: string | null;
  slaRemainingHours?: number | null;
  slaStatus: SlaStatus;
  // Structured data sections from display_config + OCR extraction_data
  dataSections: PreviewDataSection[];
  // Documents
  documents: RequestPreviewDocument[];
  documentsCount: number;
  // Contact
  contactName: string;
  contactEmail?: string | null;
  contactPhone?: string | null;
  // Appointment
  appointment?: RequestPreviewAppointment | null;
  // Payment details
  paymentStatus?: string | null;
  paymentMethod?: string | null;
  paymentAmount?: number | null;
  paymentCurrency?: string | null;
  paymentPaidAt?: string | null;
  paymentReference?: string | null;
  paymentReceiptNumber?: string | null;
  // Metadata
  createdAt: string;
  submittedAt?: string | null;
  // Batch context
  batchId?: string | null;
  batchReference?: string | null;
  // Navigation
  listIndex?: number | null;
  listTotal?: number | null;
}

// Backend response (snake_case)
interface BackendServiceRequestListItem {
  id: string;
  reference: string;
  workflow_code: string;
  solicitud_type: string;
  motivo: string | null;
  status: string;
  priority: string;
  citizen_name: string;
  citizen_email: string | null;
  submitted_at: string | null;
  created_at: string;
  assigned_to: string | null;
  assigned_agent_name: string | null;
  sla_deadline: string | null;
  sla_status: string;
  batch_id?: string | null;
  batch_reference?: string | null;
  escalation_reason?: string | null;
  escalated_at?: string | null;
  supervisor_assigned?: boolean;
}

interface BackendServiceRequestListResponse {
  items: BackendServiceRequestListItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// Backend preview extracted_data is now a dynamic dict (snake_case keys with dot notation)
interface BackendRequestPreviewDocument {
  id: string;
  code: string;
  name: string;
  file_url?: string | null;
  mime_type?: string | null;
  validation_status: string;
}

interface BackendRequestPreviewAppointment {
  date: string;
  time: string;
  location_name: string;
  location_address?: string | null;
}

interface BackendServiceRequestPreview {
  id: string;
  reference: string;
  workflow_code: string;
  workflow_label: string;
  solicitud_type: string;
  motivo?: string | null;
  is_minor: boolean;
  status: string;
  priority: string;
  sla_deadline?: string | null;
  sla_remaining_hours?: number | null;
  sla_status: string;
  data_sections?: Array<{ title: string; fields: Array<{ label: string; value: string }> }>;
  documents: BackendRequestPreviewDocument[];
  documents_count: number;
  contact_name: string;
  contact_email?: string | null;
  contact_phone?: string | null;
  appointment?: BackendRequestPreviewAppointment | null;
  payment_status?: string | null;
  payment_method?: string | null;
  payment_amount?: number | null;
  payment_currency?: string | null;
  payment_paid_at?: string | null;
  payment_reference?: string | null;
  payment_receipt_number?: string | null;
  created_at: string;
  submitted_at?: string | null;
  batch_id?: string | null;
  batch_reference?: string | null;
  list_index?: number | null;
  list_total?: number | null;
}

// =============================================================================
// TRANSFORM FUNCTIONS
// =============================================================================

function transformServiceRequestItem(item: BackendServiceRequestListItem): ServiceRequestListItem {
  return {
    id: item.id,
    reference: item.reference,
    workflowCode: item.workflow_code,
    solicitudType: item.solicitud_type,
    motivo: item.motivo,
    status: item.status,
    priority: (item.priority || 'NORMAL') as Priority,
    citizenName: item.citizen_name,
    citizenEmail: item.citizen_email,
    submittedAt: item.submitted_at,
    createdAt: item.created_at,
    assignedTo: item.assigned_to,
    assignedAgentName: item.assigned_agent_name,
    slaDeadline: item.sla_deadline,
    slaStatus: normalizeSlaStatus(item.sla_status),
    batchId: item.batch_id,
    batchReference: item.batch_reference,
    escalationReason: item.escalation_reason,
    escalatedAt: item.escalated_at,
    supervisorAssigned: item.supervisor_assigned || false,
  };
}

function transformServiceRequestPreview(data: BackendServiceRequestPreview): ServiceRequestPreview {
  return {
    id: data.id,
    reference: data.reference,
    workflowCode: data.workflow_code,
    workflowLabel: data.workflow_label,
    solicitudType: data.solicitud_type,
    motivo: data.motivo,
    isMinor: data.is_minor,
    status: data.status,
    priority: (data.priority || 'NORMAL') as Priority,
    slaDeadline: data.sla_deadline,
    slaRemainingHours: data.sla_remaining_hours,
    slaStatus: normalizeSlaStatus(data.sla_status),
    dataSections: (data.data_sections ?? []).map(s => ({
      title: s.title,
      fields: s.fields.map(f => ({ label: f.label, value: f.value })),
    })),
    documents: data.documents.map(doc => ({
      id: doc.id,
      code: doc.code,
      name: doc.name,
      fileUrl: doc.file_url,
      mimeType: doc.mime_type,
      validationStatus: doc.validation_status,
    })),
    documentsCount: data.documents_count,
    contactName: data.contact_name,
    contactEmail: data.contact_email,
    contactPhone: data.contact_phone,
    appointment: data.appointment ? {
      date: data.appointment.date,
      time: data.appointment.time,
      locationName: data.appointment.location_name,
      locationAddress: data.appointment.location_address,
    } : null,
    createdAt: data.created_at,
    submittedAt: data.submitted_at,
    batchId: data.batch_id,
    batchReference: data.batch_reference,
    paymentStatus: data.payment_status,
    paymentMethod: data.payment_method,
    paymentAmount: data.payment_amount,
    paymentCurrency: data.payment_currency,
    paymentPaidAt: data.payment_paid_at,
    paymentReference: data.payment_reference,
    paymentReceiptNumber: data.payment_receipt_number,
    listIndex: data.list_index,
    listTotal: data.list_total,
  };
}

// =============================================================================
// API CLIENT
// =============================================================================

class AgentRequestsApiClient {
  private baseUrl: string;

  constructor() {
    this.baseUrl = `${API_BASE_URL}${API_VERSION}/agent/service-requests`;
  }

  private getToken(): string | null {
    if (typeof window === 'undefined') return null;
    const authData = getAuthData();
    return authData?.access_token || null;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {},
    absoluteUrl: boolean = false,
  ): Promise<T> {
    const token = this.getToken();
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    };

    const url = absoluteUrl ? endpoint : `${this.baseUrl}${endpoint}`;

    const response = await fetch(url, {
      ...options,
      headers,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      let errorMessage = `API Error: ${response.status}`;
      if (errorData.detail) {
        errorMessage = typeof errorData.detail === 'string'
          ? errorData.detail
          : errorData.detail.message || JSON.stringify(errorData.detail);
      }
      console.error(`[AgentRequestsApi] Error: ${errorMessage}`);
      throw new Error(errorMessage);
    }

    return response.json();
  }

  /**
   * Get service requests for an entity with filters
   */
  async getEntityRequests(
    entityCode: string,
    filters: ServiceRequestFilters = {}
  ): Promise<ServiceRequestListResponse> {
    const params = new URLSearchParams();

    if (filters.action) params.append('action', filters.action);
    if (filters.status) params.append('status', filters.status);
    if (filters.workflowCode) params.append('workflow_code', filters.workflowCode);
    if (filters.solicitudType) params.append('solicitud_type', filters.solicitudType);
    if (filters.motivo) params.append('motivo', filters.motivo);
    if (filters.search) params.append('search', filters.search);
    if (filters.priority) params.append('priority', filters.priority);
    if (filters.agentId) params.append('agent_id', filters.agentId);
    if (filters.page) params.append('page', filters.page.toString());
    if (filters.pageSize) params.append('page_size', filters.pageSize.toString());

    const queryString = params.toString();
    const endpoint = `/entity/${entityCode}/requests${queryString ? `?${queryString}` : ''}`;

    const response = await this.request<BackendServiceRequestListResponse>(endpoint);

    return {
      items: response.items.map(transformServiceRequestItem),
      total: response.total,
      page: response.page,
      pageSize: response.page_size,
      totalPages: response.total_pages,
    };
  }

  /**
   * Get service request preview for split view
   */
  async getPreview(
    entityCode: string,
    requestId: string,
    options?: { listIndex?: number; listTotal?: number }
  ): Promise<ServiceRequestPreview> {
    const params = new URLSearchParams();
    if (options?.listIndex !== undefined) params.append('list_index', options.listIndex.toString());
    if (options?.listTotal !== undefined) params.append('list_total', options.listTotal.toString());

    const queryString = params.toString();
    const endpoint = `/entity/${entityCode}/requests/${requestId}/preview${queryString ? `?${queryString}` : ''}`;

    const response = await this.request<BackendServiceRequestPreview>(endpoint);
    return transformServiceRequestPreview(response);
  }

  /**
   * Get a single service request for agent review
   */
  async getRequest(requestId: string): Promise<unknown> {
    return this.request(`/${requestId}`);
  }

  /**
   * Make decision on a service request (approve, reject, request_documents)
   */
  async makeDecision(
    requestId: string,
    decision: 'approve' | 'reject' | 'request_documents',
    options: {
      comments?: string;
      rejectionReason?: string;
      requestedDocuments?: string[];
    } = {}
  ): Promise<{ message: string; new_status: string }> {
    return this.request(`/${requestId}/decision`, {
      method: 'POST',
      body: JSON.stringify({
        decision,
        comments: options.comments,
        rejection_reason: options.rejectionReason,
        requested_documents: options.requestedDocuments,
      }),
    });
  }

  /**
   * Escalate a service request
   */
  async escalate(
    requestId: string,
    reason: string,
    priorityBoost: number = 10
  ): Promise<{ message: string }> {
    return this.request(`/${requestId}/escalate`, {
      method: 'POST',
      body: JSON.stringify({
        reason,
        priority_boost: priorityBoost,
      }),
    });
  }

  /**
   * Resolve (de-escalate) a service request
   */
  async resolveEscalation(requestId: string): Promise<{ message: string }> {
    return this.request(`/${requestId}/resolve-escalation`, {
      method: 'POST',
    });
  }

  /**
   * Get my escalated service requests
   */
  async getMyEscalations(options?: {
    includeResolved?: boolean;
    direction?: 'sent' | 'received';
    page?: number;
    pageSize?: number;
  }): Promise<PaginatedEscalationResponse> {
    const params = new URLSearchParams();
    if (options?.includeResolved) params.set('include_resolved', 'true');
    if (options?.direction) params.set('direction', options.direction);
    if (options?.page) params.set('page', String(options.page));
    if (options?.pageSize) params.set('page_size', String(options.pageSize));
    const qs = params.toString();

    const data = await this.request<BackendPaginatedEscalation>(
      `/my-escalations${qs ? `?${qs}` : ''}`
    );

    const items = data.items.map((r) => ({
      id: r.id,
      queueId: r.queue_id,
      reason: r.reason,
      priorityScore: r.priority_score,
      status: r.status,
      escalationStatus: r.escalation_status as EscalationListItem['escalationStatus'],
      caseReference: r.case_reference,
      caseType: r.case_type,
      notes: r.notes || null,
      createdAt: r.created_at,
      escalatedAt: r.escalated_at,
      direction: r.direction as EscalationListItem['direction'],
      escalatedByName: r.escalated_by_name || null,
      citizenName: r.citizen_name || null,
      history: (r.history || []).map((h) => ({
        action: h.action,
        performedAt: h.performed_at,
        performedByName: h.performed_by_name || null,
        comment: h.comment || null,
      })),
    }));

    return {
      items,
      total: data.total,
      page: data.page,
      pageSize: data.page_size,
    };
  }

  /**
   * Get workflow display schema for agent view
   * Returns form layout schema and agent checklist items
   */
  async getWorkflowSchema(workflowCode: string): Promise<WorkflowSchemaResponse> {
    interface BackendResponse {
      code: string;
      name: string;
      formDisplaySchema: FormDisplaySchema | null;
      agentChecklist: AgentChecklistItem[] | null;
    }

    const response = await this.request<BackendResponse>(`/workflows/${workflowCode}/schema`);

    return {
      code: response.code,
      name: response.name,
      formDisplaySchema: response.formDisplaySchema,
      agentChecklist: response.agentChecklist,
    };
  }

  /**
   * Update verification checklist for a service request
   * Saves checklist state to service_requests.verification_details
   */
  async updateVerification(
    requestId: string,
    data: VerificationChecklistUpdate
  ): Promise<VerificationResponse> {
    interface BackendResponse {
      message: string;
      request_id: string;
      verification_status: string;
      checklist_completed: number;
      checklist_total: number;
    }

    const response = await this.request<BackendResponse>(`/${requestId}/verification`, {
      method: 'PATCH',
      body: JSON.stringify({
        checklist: data.checklist,
        verification_status: data.verificationStatus,
        notes: data.notes,
      }),
    });

    return {
      message: response.message,
      requestId: response.request_id,
      verificationStatus: response.verification_status,
      checklistCompleted: response.checklist_completed,
      checklistTotal: response.checklist_total,
    };
  }

  /**
   * Get service request detail for agent view (includes full form_data)
   */
  async getRequestDetail(requestId: string): Promise<ServiceRequestDetail> {
    interface BackendResponse {
      id: string;
      reference: string;
      workflow_code: string;
      solicitud_type: string;
      status: string;
      priority: string;
      form_data: Record<string, unknown>;
      extracted_data?: Record<string, unknown>;
      verification_status?: string;
      verification_details?: {
        checklist?: Record<string, boolean>;
        notes?: string;
        last_updated_by?: string;
        last_updated_at?: string;
      };
      user_id: string;
      user_name?: string;
      user_email?: string;
      user_phone?: string;
      created_at: string;
      submitted_at?: string;
      cita_date?: string;
      cita_time?: string;
      cita_location?: string;
      // Payment (augmented by agent endpoint)
      payment_id?: string;
      payment_status?: string;
      payment_amount?: number;
      payment_currency?: string;
      payment_method?: string;
      payment_workflow_status?: string;
      payment_reference?: string;
      payment_receipt_number?: string;
      payment_paid_at?: string;
      // Tariff
      tariff?: {
        base_amount: number;
        supplements_total: number;
        penalties_amount: number;
        total_amount: number;
      };
      provided_documents?: Array<{
        id: string;
        document_code: string;
        document_name: string;
        file_path: string;
        file_name: string;
        mime_type: string;
        validation_status?: string;
        extraction_data?: Record<string, unknown>;
        extraction_confidence?: number;
        extraction_status?: string;
      }>;
    }

    const response = await this.request<BackendResponse>(`/${requestId}`);

    return {
      id: response.id,
      reference: response.reference,
      workflowCode: response.workflow_code,
      solicitudType: response.solicitud_type,
      status: response.status,
      priority: response.priority as Priority,
      formData: response.form_data,
      extractedData: response.extracted_data,
      verificationStatus: response.verification_status,
      verificationDetails: response.verification_details ? {
        checklist: response.verification_details.checklist,
        notes: response.verification_details.notes,
        lastUpdatedBy: response.verification_details.last_updated_by,
        lastUpdatedAt: response.verification_details.last_updated_at,
      } : undefined,
      userId: response.user_id,
      userName: response.user_name,
      userEmail: response.user_email,
      userPhone: response.user_phone,
      createdAt: response.created_at,
      submittedAt: response.submitted_at,
      citaDate: response.cita_date,
      citaTime: response.cita_time,
      citaLocation: response.cita_location,
      // Payment
      paymentId: response.payment_id,
      paymentStatus: response.payment_status,
      paymentAmount: response.payment_amount,
      paymentCurrency: response.payment_currency,
      paymentMethod: response.payment_method,
      paymentWorkflowStatus: response.payment_workflow_status,
      paymentReference: response.payment_reference,
      paymentReceiptNumber: response.payment_receipt_number,
      paymentPaidAt: response.payment_paid_at,
      // Tariff
      tariff: response.tariff ? {
        baseAmount: response.tariff.base_amount,
        supplementsTotal: response.tariff.supplements_total,
        penaltiesAmount: response.tariff.penalties_amount,
        totalAmount: response.tariff.total_amount,
      } : undefined,
      providedDocuments: response.provided_documents?.map(doc => ({
        id: doc.id,
        documentCode: doc.document_code,
        documentName: doc.document_name,
        filePath: doc.file_path,
        fileName: doc.file_name,
        mimeType: doc.mime_type,
        validationStatus: doc.validation_status,
        extractionData: doc.extraction_data,
        extractionConfidence: doc.extraction_confidence,
        extractionStatus: doc.extraction_status,
      })),
    };
  }

  // ─── Agent Batch Endpoints ──────────────────────────────────

  async getEntityBatches(
    entityCode: string,
    filters?: { status?: string; search?: string; page?: number; pageSize?: number }
  ): Promise<AgentBatchListResponse> {
    const params = new URLSearchParams();
    if (filters?.status) params.set('status', filters.status);
    if (filters?.search) params.set('search', filters.search);
    if (filters?.page) params.set('page', String(filters.page));
    if (filters?.pageSize) params.set('page_size', String(filters.pageSize));
    const qs = params.toString();
    const url = `${API_BASE_URL}${API_VERSION}/batch-requests/agent/entity/${entityCode}${qs ? `?${qs}` : ''}`;
    return this.request(url, {}, true);
  }

  async getEntityBatchDetail(
    entityCode: string,
    batchId: string
  ): Promise<AgentBatchDetail> {
    const url = `${API_BASE_URL}${API_VERSION}/batch-requests/agent/entity/${entityCode}/${batchId}`;
    return this.request(url, {}, true);
  }

  async bulkDecision(
    entityCode: string,
    batchId: string,
    body: { decision: 'approve' | 'reject'; itemIds?: string[]; comments?: string; rejectionReason?: string }
  ): Promise<BulkDecisionResult> {
    const url = `${API_BASE_URL}${API_VERSION}/batch-requests/agent/entity/${entityCode}/${batchId}/bulk-decision`;
    return this.request(url, {
      method: 'POST',
      body: JSON.stringify({
        decision: body.decision,
        item_ids: body.itemIds,
        comments: body.comments,
        rejection_reason: body.rejectionReason,
      }),
    }, true);
  }
}

// Service request detail type
export interface ServiceRequestDetail {
  id: string;
  reference: string;
  workflowCode: string;
  solicitudType: string;
  status: string;
  priority: Priority;
  formData: Record<string, unknown>;
  extractedData?: Record<string, unknown>;
  verificationStatus?: string;
  verificationDetails?: {
    checklist?: Record<string, boolean>;
    notes?: string;
    lastUpdatedBy?: string;
    lastUpdatedAt?: string;
  };
  userId: string;
  userName?: string;
  userEmail?: string;
  userPhone?: string;
  createdAt: string;
  submittedAt?: string;
  citaDate?: string;
  citaTime?: string;
  citaLocation?: string;
  // Payment details (from service_payments)
  paymentId?: string;
  paymentStatus?: string;
  paymentAmount?: number;
  paymentCurrency?: string;
  paymentMethod?: string;
  paymentWorkflowStatus?: string;
  paymentReference?: string;
  paymentReceiptNumber?: string;
  paymentPaidAt?: string;
  // Tariff
  tariff?: {
    baseAmount: number;
    supplementsTotal: number;
    penaltiesAmount: number;
    totalAmount: number;
  };
  providedDocuments?: Array<{
    id: string;
    documentCode: string;
    documentName: string;
    filePath: string;
    fileName: string;
    mimeType: string;
    validationStatus?: string;
    extractionData?: Record<string, unknown>;
    extractionConfidence?: number;
    extractionStatus?: string;
  }>;
}

// ─── Agent Batch Types ──────────────────────────────────────

export interface AgentBatchListResponse {
  batches: AgentBatchSummary[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface AgentBatchSummary {
  id: string;
  reference: string | null;
  workflow_code: string;
  solicitud_type: string;
  total_items: number;
  items_ready: number;
  items_submitted: number;
  items_completed: number;
  status: string;
  total_amount: number | null;
  currency: string;
  created_at: string;
  submitted_at: string | null;
}

export interface AgentBatchDetail extends AgentBatchSummary {
  items: AgentBatchItem[];
  submitted_by_name: string | null;
  submitted_by_email: string | null;
  shared_documents: Array<{ document_code: string; file_path: string; file_name: string }>;
  notes: string | null;
}

export interface AgentBatchItem {
  id: string;
  batch_id: string;
  beneficiary_name: string;
  beneficiary_identifier: string | null;
  status: string;
  service_request_id: string | null;
  sr_status: string | null;
  sr_reference: string | null;
  sr_assigned_to: string | null;
  sr_payment_status: string | null;
  item_order: number;
  created_at: string;
}

export interface BulkDecisionResult {
  processed: number;
  failed: number;
  errors: Array<{ item_id: string; beneficiary: string; error: string }>;
  batch_completed: boolean;
}

// Export singleton instance
export const agentRequestsApi = new AgentRequestsApiClient();

// ============================================================================
// DOCUMENT URL HELPER
// ============================================================================

/**
 * Get signed download URL for a document
 * Uses the service-requests endpoint (not agent endpoint)
 */
export async function getDocumentDownloadUrl(
  requestId: string,
  documentCode: string
): Promise<string> {
  const token = typeof window !== 'undefined'
    ? getAuthData()?.access_token
    : null;

  const url = `${API_BASE_URL}${API_VERSION}/service-requests/${requestId}/documents/${documentCode}/url`;

  const response = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to get document URL: ${response.status}`);
  }

  const data = await response.json();
  return data.download_url;
}

// ============================================================================
// DOCUMENT VALIDATION (AGENT)
// ============================================================================

const AGENT_DOCS_BASE = `${API_BASE_URL}${API_VERSION}/agent/service-requests/documents`;

function agentHeaders(): Record<string, string> {
  const token = typeof window !== 'undefined' ? getAuthData()?.access_token : null;
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

/**
 * Agent validates (approves) a document
 */
export async function validateDocument(
  documentId: string,
  comment?: string
): Promise<{ message: string; document_id: string }> {
  const response = await fetch(`${AGENT_DOCS_BASE}/${documentId}/validate`, {
    method: 'POST',
    headers: agentHeaders(),
    body: JSON.stringify(comment ? { comment } : {}),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || `Validation failed: ${response.status}`);
  }
  return response.json();
}

/**
 * Agent rejects a document with reason
 */
export async function rejectDocument(
  documentId: string,
  reason: string
): Promise<{ message: string; document_id: string; reason: string }> {
  const response = await fetch(`${AGENT_DOCS_BASE}/${documentId}/reject`, {
    method: 'POST',
    headers: agentHeaders(),
    body: JSON.stringify({ reason }),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || `Rejection failed: ${response.status}`);
  }
  return response.json();
}

// ============================================================================
// SIGNED URL CACHE
// ============================================================================

const signedUrlCache = new Map<string, { url: string; expires: number }>();
const SIGNED_URL_TTL_MS = 10 * 60 * 1000; // 10 min (signed URLs last ~15 min)

/**
 * Get signed download URL with in-memory cache
 */
export async function getDocumentDownloadUrlCached(
  requestId: string,
  documentCode: string
): Promise<string> {
  const cacheKey = `${requestId}:${documentCode}`;
  const cached = signedUrlCache.get(cacheKey);
  if (cached && cached.expires > Date.now()) {
    return cached.url;
  }
  const url = await getDocumentDownloadUrl(requestId, documentCode);
  signedUrlCache.set(cacheKey, { url, expires: Date.now() + SIGNED_URL_TTL_MS });
  return url;
}
