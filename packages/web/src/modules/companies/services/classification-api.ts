/**
 * Company Classification API Client
 * Endpoints: /companies/classification/*
 */

import apiClient from '@/core/api/client'
import { transformKeys, toSnakeCase } from '@/core/utils/api-transform'

const BASE = '/companies/classification'

async function get<T>(path: string): Promise<T> {
  const { data } = await apiClient.get(`${BASE}${path}`)
  return transformKeys<T>(data)
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const { data } = await apiClient.post(
    `${BASE}${path}`,
    body ? toSnakeCase(body) : undefined
  )
  return transformKeys<T>(data)
}

// ── Types ────────────────────────────────────────────────────────────────────

export interface ClassificationResult {
  regimenFiscal: string
  confidence: number
  reason: string
  rulesApplied: string[]
  commerceType: string | null
  llmValidated: boolean
  llmIssues: string[]
  flags: string[]
  suggestedActions: string[]
  classificationDetails: Record<string, unknown>
}

export interface DraftItem {
  id: string
  sourceType: string
  companyData: Record<string, unknown>
  regimenFiscal: string | null
  classificationConfidence: number
  classificationReason: string | null
  classificationDetails: Record<string, unknown>
  extractionConfidence: number
  status: string
  reviewerNotes: string | null
  reviewedAt: string | null
  createdCompanyId: string | null
  createdBy: string | null
  createdAt: string | null
  updatedAt: string | null
}

export interface DraftListResponse {
  items: DraftItem[]
  total: number
  page: number
  pageSize: number
}

export interface ClassificationStats {
  totalCompanies: number
  byRegimen: Record<string, number>
  totalDrafts: number
  draftsPending: number
  draftsApproved: number
  draftsAutoApproved: number
  draftsRejected: number
  draftsNeedsInfo: number
  autoApprovalRate: number
  avgConfidence: number
}

export interface HistoryEntry {
  id: string
  companyId: string
  oldRegimen: string | null
  newRegimen: string
  oldCommerceType: string | null
  newCommerceType: string | null
  reason: string
  confidence: number
  triggeredBy: string
  createdAt: string | null
}

export interface BatchResult {
  total: number
  classified: number
  autoApproved: number
  pendingReview: number
  errors: number
  results: Record<string, unknown>[]
}

export interface CsvImportResult {
  total: number
  imported: number
  autoApproved: number
  pendingReview: number
  classificationErrors: number
  validationErrors: string[]
  parseErrors: string[]
  batchId: string | null
}

// ── API Methods ──────────────────────────────────────────────────────────────

export const classificationApi = {
  /** Classify single company data */
  classify: (data: Record<string, unknown>) =>
    post<ClassificationResult>('/classify', data),

  /** Classify batch of companies */
  classifyBatch: (items: Record<string, unknown>[], zoneId?: string) =>
    post<BatchResult>('/classify-batch', { items, zoneId }),

  /** Reclassify existing company */
  reclassify: (companyId: string, reason = 'manual') =>
    post<ClassificationResult>(`/reclassify/${companyId}`, { reason }),

  /** Upload CSV for import */
  importCsv: async (file: File, zoneId?: string): Promise<CsvImportResult> => {
    const formData = new FormData()
    formData.append('file', file)
    const params = zoneId ? `?zone_id=${zoneId}` : ''
    const { data } = await apiClient.post(`${BASE}/import-csv${params}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return transformKeys<CsvImportResult>(data)
  },

  /** List drafts (paginated) */
  getDrafts: (params?: {
    status?: string
    batchId?: string
    page?: number
    pageSize?: number
  }) => {
    const sp = new URLSearchParams()
    if (params?.status) sp.set('status', params.status)
    if (params?.batchId) sp.set('batch_id', params.batchId)
    if (params?.page) sp.set('page', String(params.page))
    if (params?.pageSize) sp.set('page_size', String(params.pageSize))
    const q = sp.toString()
    return get<DraftListResponse>(`/drafts${q ? `?${q}` : ''}`)
  },

  /** Get single draft */
  getDraft: (id: string) => get<DraftItem>(`/drafts/${id}`),

  /** Approve draft → creates company + license (if autonomo/bundle with zone) */
  approveDraft: (id: string, notes?: string) =>
    post<{
      status: string
      companyId: string
      licenseId: string | null
      licenseWarning?: string
    }>(`/drafts/${id}/approve`, { notes }),

  /** Reject draft */
  rejectDraft: (id: string, notes?: string) =>
    post<{ status: string }>(`/drafts/${id}/reject`, { notes }),

  /** Request more info on draft */
  requestInfo: (id: string, notes?: string) =>
    post<{ status: string }>(`/drafts/${id}/request-info`, { notes }),

  /** Re-run classification on draft */
  reclassifyDraft: (id: string) =>
    post<{ classification: ClassificationResult; newStatus: string }>(
      `/drafts/${id}/reclassify`
    ),

  /** Get classification history for a company */
  getHistory: (companyId: string) =>
    get<{ companyId: string; entries: HistoryEntry[] }>(`/history/${companyId}`),

  /** Get classification stats */
  getStats: () => get<ClassificationStats>('/stats'),

  /** Download CSV template for import */
  getCsvTemplateUrl: (): string => {
    const headers = [
      'legal_name', 'forma_juridica', 'nif', 'registration_number',
      'sector_actividad', 'subsector_actividad', 'objeto_social',
      'commerce_type', 'capital_social', 'employee_count',
      'localidad', 'provincia', 'domicilio_fiscal',
      'representante_legal', 'telefono', 'email',
    ]
    const csv = headers.join(',') + '\n'
    return URL.createObjectURL(new Blob([csv], { type: 'text/csv' }))
  },
}

// ── AI Agents API ────────────────────────────────────────────────────────────

export interface AgentInfo {
  agentType: string
  label: string
  hasFunctions: boolean
  hasProcessFn: boolean
  functionCount: number
  subAgents: string[]
}

export interface TokenUsageStats {
  sdkInitialized: boolean
  project: string
  location: string
  totalTokensIn: number
  totalTokensOut: number
  totalRequests: number
  failedRequests: number
  consecutiveFailures: number
  circuitOpen: boolean
  errorRate: number
  estimatedCostUsd: number
  model: string
}

export const aiAgentsApi = {
  /** List all registered agent types */
  listAgents: async (): Promise<{ agents: AgentInfo[]; total: number }> => {
    const { data } = await apiClient.get('/agents/analyst/agents')
    return transformKeys(data)
  },

  /** Get token usage stats */
  getTokenUsage: async (): Promise<TokenUsageStats> => {
    const { data } = await apiClient.get('/agents/analyst/token-usage')
    return transformKeys(data)
  },
}
