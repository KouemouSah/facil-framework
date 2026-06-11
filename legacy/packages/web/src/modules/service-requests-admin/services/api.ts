/**
 * Service Requests Admin API Service
 * Handles all API calls to the backend admin service-requests endpoints
 *
 * @module service-requests-admin/services
 * @author Claude Code
 * @date 2025-12-28
 *
 * BACKEND ALIGNMENT:
 * Routes: /api/v1/admin/service-requests (from admin_routes.py)
 */

import { fetchClient } from '@/core/api'
import type {
  Workflow,
  WorkflowCreate,
  WorkflowUpdate,
  WorkflowFilters,
  DocumentRequirement,
  DocumentRequirementCreate,
  DocumentRequirementUpdate,
  DocumentReorderItem,
  WorkflowTariff,
  WorkflowTariffCreate,
  WorkflowTariffUpdate,
  TariffFilters,
  TariffSupplement,
  TariffSupplementCreate,
  TariffSupplementUpdate,
  WorkflowSupplementConfig,
  WorkflowSupplementConfigCreate,
  WorkflowSupplementConfigUpdate,
  AppointmentSlotConfig,
  AppointmentSlotConfigCreate,
  AppointmentSlotConfigUpdate,
  AppointmentSlotConfigBatchCreate,
  AppointmentSlotConfigBatchResponse,
  AppointmentSlotConfigGroupUpdate,
  AppointmentSlotConfigGroupUpdateResponse,
  SlotConfigFilters,
  AppointmentBlockedDate,
  AppointmentBlockedDateCreate,
  AppointmentBlockedDateUpdate,
  BlockedDateFilters,
  AppointmentDelayRule,
  AppointmentDelayRuleCreate,
  AppointmentDelayRuleUpdate,
} from '../types'

// =============================================================================
// CONFIGURATION
// =============================================================================

const ADMIN_BASE = '/admin/service-requests'

// =============================================================================
// WORKFLOWS API
// =============================================================================

export const workflowsApi = {
  /**
   * List all workflows with optional filters
   * BACKEND: GET /api/v1/admin/service-requests/workflows
   */
  getAll: async (filters?: WorkflowFilters): Promise<Workflow[]> => {
    return fetchClient.get<Workflow[]>(`${ADMIN_BASE}/workflows`, filters)
  },

  /**
   * Get workflow by code
   * BACKEND: GET /api/v1/admin/service-requests/workflows/{code}
   */
  getByCode: async (code: string): Promise<Workflow> => {
    return fetchClient.get<Workflow>(`${ADMIN_BASE}/workflows/${code}`)
  },

  /**
   * Create a new workflow
   * BACKEND: POST /api/v1/admin/service-requests/workflows
   */
  create: async (data: WorkflowCreate): Promise<Workflow> => {
    return fetchClient.post<Workflow>(`${ADMIN_BASE}/workflows`, data)
  },

  /**
   * Update workflow
   * BACKEND: PUT /api/v1/admin/service-requests/workflows/{code}
   */
  update: async (code: string, data: WorkflowUpdate): Promise<Workflow> => {
    return fetchClient.put<Workflow>(`${ADMIN_BASE}/workflows/${code}`, data)
  },

  /**
   * Toggle workflow active status
   * BACKEND: PATCH /api/v1/admin/service-requests/workflows/{code}/activate
   */
  toggleStatus: async (code: string, isActive: boolean): Promise<{ message: string; code: string; is_active: boolean }> => {
    return fetchClient.patch<{ message: string; code: string; is_active: boolean }>(
      `${ADMIN_BASE}/workflows/${code}/activate`,
      { is_active: isActive }
    )
  },

  /**
   * Delete workflow (only generic workflows)
   * BACKEND: DELETE /api/v1/admin/service-requests/workflows/{code}
   */
  delete: async (code: string): Promise<void> => {
    return fetchClient.delete<void>(`${ADMIN_BASE}/workflows/${code}`)
  },
}

// =============================================================================
// DOCUMENT REQUIREMENTS API
// =============================================================================

export const documentsApi = {
  /**
   * List document requirements for a workflow
   * BACKEND: GET /api/v1/admin/service-requests/workflows/{code}/documents
   */
  getByWorkflow: async (workflowCode: string): Promise<DocumentRequirement[]> => {
    return fetchClient.get<DocumentRequirement[]>(`${ADMIN_BASE}/workflows/${workflowCode}/documents`)
  },

  /**
   * Add document requirement
   * BACKEND: POST /api/v1/admin/service-requests/workflows/{code}/documents
   */
  add: async (workflowCode: string, data: DocumentRequirementCreate): Promise<DocumentRequirement> => {
    return fetchClient.post<DocumentRequirement>(`${ADMIN_BASE}/workflows/${workflowCode}/documents`, data)
  },

  /**
   * Update document requirement
   * BACKEND: PUT /api/v1/admin/service-requests/workflows/{code}/documents/{doc_code}
   */
  update: async (
    workflowCode: string,
    documentCode: string,
    data: DocumentRequirementUpdate
  ): Promise<DocumentRequirement> => {
    return fetchClient.put<DocumentRequirement>(
      `${ADMIN_BASE}/workflows/${workflowCode}/documents/${documentCode}`,
      data
    )
  },

  /**
   * Remove document requirement
   * BACKEND: DELETE /api/v1/admin/service-requests/workflows/{code}/documents/{doc_code}
   */
  remove: async (workflowCode: string, documentCode: string): Promise<void> => {
    return fetchClient.delete<void>(`${ADMIN_BASE}/workflows/${workflowCode}/documents/${documentCode}`)
  },

  /**
   * Reorder document requirements
   * BACKEND: PATCH /api/v1/admin/service-requests/workflows/{code}/documents/reorder
   */
  reorder: async (workflowCode: string, order: DocumentReorderItem[]): Promise<{ message: string }> => {
    return fetchClient.patch<{ message: string }>(
      `${ADMIN_BASE}/workflows/${workflowCode}/documents/reorder`,
      order
    )
  },
}

// =============================================================================
// TARIFFS API
// =============================================================================

export const tariffsApi = {
  /**
   * List all workflow tariffs
   * BACKEND: GET /api/v1/admin/service-requests/tariffs
   */
  getAll: async (filters?: TariffFilters): Promise<WorkflowTariff[]> => {
    return fetchClient.get<WorkflowTariff[]>(`${ADMIN_BASE}/tariffs`, filters)
  },

  /**
   * Create workflow tariff
   * BACKEND: POST /api/v1/admin/service-requests/tariffs
   */
  create: async (data: WorkflowTariffCreate): Promise<WorkflowTariff> => {
    return fetchClient.post<WorkflowTariff>(`${ADMIN_BASE}/tariffs`, data)
  },

  /**
   * Update workflow tariff
   * BACKEND: PUT /api/v1/admin/service-requests/tariffs/{tariff_id}
   */
  update: async (tariffId: number, data: WorkflowTariffUpdate): Promise<WorkflowTariff> => {
    return fetchClient.put<WorkflowTariff>(`${ADMIN_BASE}/tariffs/${tariffId}`, data)
  },

  /**
   * Delete workflow tariff
   * BACKEND: DELETE /api/v1/admin/service-requests/tariffs/{tariff_id}
   */
  delete: async (tariffId: number): Promise<void> => {
    return fetchClient.delete<void>(`${ADMIN_BASE}/tariffs/${tariffId}`)
  },
}

// =============================================================================
// TARIFF SUPPLEMENTS API
// =============================================================================

export const supplementsApi = {
  /**
   * List all tariff supplements
   * BACKEND: GET /api/v1/admin/service-requests/supplements
   */
  getAll: async (activeOnly?: boolean): Promise<TariffSupplement[]> => {
    return fetchClient.get<TariffSupplement[]>(
      `${ADMIN_BASE}/supplements`,
      activeOnly !== undefined ? { active_only: activeOnly } : undefined
    )
  },

  /**
   * Get supplement by code
   * BACKEND: GET /api/v1/admin/service-requests/supplements/{code}
   */
  getByCode: async (code: string): Promise<TariffSupplement> => {
    return fetchClient.get<TariffSupplement>(`${ADMIN_BASE}/supplements/${code}`)
  },

  /**
   * Create tariff supplement
   * BACKEND: POST /api/v1/admin/service-requests/supplements
   */
  create: async (data: TariffSupplementCreate): Promise<TariffSupplement> => {
    return fetchClient.post<TariffSupplement>(`${ADMIN_BASE}/supplements`, data)
  },

  /**
   * Update tariff supplement
   * BACKEND: PUT /api/v1/admin/service-requests/supplements/{code}
   */
  update: async (code: string, data: TariffSupplementUpdate): Promise<TariffSupplement> => {
    return fetchClient.put<TariffSupplement>(`${ADMIN_BASE}/supplements/${code}`, data)
  },

  /**
   * Delete tariff supplement
   * BACKEND: DELETE /api/v1/admin/service-requests/supplements/{code}
   */
  delete: async (code: string): Promise<void> => {
    return fetchClient.delete<void>(`${ADMIN_BASE}/supplements/${code}`)
  },
}

// =============================================================================
// WORKFLOW SUPPLEMENT CONFIG API
// =============================================================================

export const workflowSupplementsApi = {
  /**
   * List supplements for a workflow
   * BACKEND: GET /api/v1/admin/service-requests/workflows/{code}/supplements
   */
  getByWorkflow: async (workflowCode: string): Promise<WorkflowSupplementConfig[]> => {
    return fetchClient.get<WorkflowSupplementConfig[]>(`${ADMIN_BASE}/workflows/${workflowCode}/supplements`)
  },

  /**
   * Add supplement to workflow
   * BACKEND: POST /api/v1/admin/service-requests/workflows/{code}/supplements
   */
  add: async (workflowCode: string, data: WorkflowSupplementConfigCreate): Promise<WorkflowSupplementConfig> => {
    return fetchClient.post<WorkflowSupplementConfig>(`${ADMIN_BASE}/workflows/${workflowCode}/supplements`, data)
  },

  /**
   * Update workflow supplement configuration
   * BACKEND: PUT /api/v1/admin/service-requests/workflows/{code}/supplements/{supplement_code}
   */
  update: async (
    workflowCode: string,
    supplementCode: string,
    data: WorkflowSupplementConfigUpdate
  ): Promise<WorkflowSupplementConfig> => {
    return fetchClient.put<WorkflowSupplementConfig>(
      `${ADMIN_BASE}/workflows/${workflowCode}/supplements/${supplementCode}`,
      data
    )
  },

  /**
   * Remove supplement from workflow
   * BACKEND: DELETE /api/v1/admin/service-requests/workflows/{code}/supplements/{supplement_code}
   */
  remove: async (workflowCode: string, supplementCode: string): Promise<void> => {
    return fetchClient.delete<void>(`${ADMIN_BASE}/workflows/${workflowCode}/supplements/${supplementCode}`)
  },
}

// =============================================================================
// APPOINTMENT SLOT CONFIGS API
// =============================================================================

export const slotConfigsApi = {
  /**
   * List appointment slot configurations
   * BACKEND: GET /api/v1/admin/service-requests/appointments/slot-configs
   */
  getAll: async (filters?: SlotConfigFilters): Promise<AppointmentSlotConfig[]> => {
    return fetchClient.get<AppointmentSlotConfig[]>(`${ADMIN_BASE}/appointments/slot-configs`, filters)
  },

  /**
   * Create slot configuration
   * BACKEND: POST /api/v1/admin/service-requests/appointments/slot-configs
   */
  create: async (data: AppointmentSlotConfigCreate): Promise<AppointmentSlotConfig> => {
    return fetchClient.post<AppointmentSlotConfig>(`${ADMIN_BASE}/appointments/slot-configs`, data)
  },

  /**
   * Create multiple slot configurations in batch (one request for multiple days)
   * BACKEND: POST /api/v1/admin/service-requests/appointments/slot-configs/batch
   */
  createBatch: async (data: AppointmentSlotConfigBatchCreate): Promise<AppointmentSlotConfigBatchResponse> => {
    return fetchClient.post<AppointmentSlotConfigBatchResponse>(`${ADMIN_BASE}/appointments/slot-configs/batch`, data)
  },

  /**
   * Update slot configuration
   * BACKEND: PUT /api/v1/admin/service-requests/appointments/slot-configs/{slot_id}
   */
  update: async (slotId: string, data: AppointmentSlotConfigUpdate): Promise<AppointmentSlotConfig> => {
    return fetchClient.put<AppointmentSlotConfig>(`${ADMIN_BASE}/appointments/slot-configs/${slotId}`, data)
  },

  /**
   * Batch update slot configurations (reconcile pattern)
   * BACKEND: PUT /api/v1/admin/service-requests/appointments/slot-configs/batch-update
   */
  batchUpdate: async (data: AppointmentSlotConfigGroupUpdate): Promise<AppointmentSlotConfigGroupUpdateResponse> => {
    return fetchClient.put<AppointmentSlotConfigGroupUpdateResponse>(`${ADMIN_BASE}/appointments/slot-configs/batch-update`, data)
  },

  /**
   * Delete slot configuration
   * BACKEND: DELETE /api/v1/admin/service-requests/appointments/slot-configs/{slot_id}
   */
  delete: async (slotId: string): Promise<void> => {
    return fetchClient.delete<void>(`${ADMIN_BASE}/appointments/slot-configs/${slotId}`)
  },
}

// =============================================================================
// BLOCKED DATES API
// =============================================================================

export const blockedDatesApi = {
  /**
   * List blocked dates
   * BACKEND: GET /api/v1/admin/service-requests/appointments/blocked-dates
   */
  getAll: async (filters?: BlockedDateFilters): Promise<AppointmentBlockedDate[]> => {
    return fetchClient.get<AppointmentBlockedDate[]>(`${ADMIN_BASE}/appointments/blocked-dates`, filters)
  },

  /**
   * Add blocked date
   * BACKEND: POST /api/v1/admin/service-requests/appointments/blocked-dates
   */
  add: async (data: AppointmentBlockedDateCreate): Promise<AppointmentBlockedDate> => {
    return fetchClient.post<AppointmentBlockedDate>(`${ADMIN_BASE}/appointments/blocked-dates`, data)
  },

  /**
   * Update blocked date
   * BACKEND: PUT /api/v1/admin/service-requests/appointments/blocked-dates/{blocked_date_id}
   */
  update: async (blockedDateId: string, data: AppointmentBlockedDateUpdate): Promise<AppointmentBlockedDate> => {
    return fetchClient.put<AppointmentBlockedDate>(`${ADMIN_BASE}/appointments/blocked-dates/${blockedDateId}`, data)
  },

  /**
   * Remove blocked date
   * BACKEND: DELETE /api/v1/admin/service-requests/appointments/blocked-dates/{blocked_date_id}
   */
  remove: async (blockedDateId: string): Promise<void> => {
    return fetchClient.delete<void>(`${ADMIN_BASE}/appointments/blocked-dates/${blockedDateId}`)
  },
}

// =============================================================================
// DELAY RULES API
// =============================================================================

export const delayRulesApi = {
  /**
   * List delay rules
   * BACKEND: GET /api/v1/admin/service-requests/appointments/delay-rules
   */
  getAll: async (workflowCode?: string): Promise<AppointmentDelayRule[]> => {
    return fetchClient.get<AppointmentDelayRule[]>(
      `${ADMIN_BASE}/appointments/delay-rules`,
      workflowCode ? { workflow_code: workflowCode } : undefined
    )
  },

  /**
   * Create delay rule
   * BACKEND: POST /api/v1/admin/service-requests/appointments/delay-rules
   */
  create: async (data: AppointmentDelayRuleCreate): Promise<AppointmentDelayRule> => {
    return fetchClient.post<AppointmentDelayRule>(`${ADMIN_BASE}/appointments/delay-rules`, data)
  },

  /**
   * Update delay rule
   * BACKEND: PUT /api/v1/admin/service-requests/appointments/delay-rules/{rule_id}
   */
  update: async (ruleId: string, data: AppointmentDelayRuleUpdate): Promise<AppointmentDelayRule> => {
    return fetchClient.put<AppointmentDelayRule>(`${ADMIN_BASE}/appointments/delay-rules/${ruleId}`, data)
  },

  /**
   * Delete delay rule
   * BACKEND: DELETE /api/v1/admin/service-requests/appointments/delay-rules/{rule_id}
   */
  delete: async (ruleId: string): Promise<void> => {
    return fetchClient.delete<void>(`${ADMIN_BASE}/appointments/delay-rules/${ruleId}`)
  },
}

// =============================================================================
// SYNC API - Synchronize predefined workflows to database
// =============================================================================

export interface WorkflowSyncResult {
  workflows_synced: number
  workflows_created: number
  workflows_updated: number
  tariffs_synced: number
  tariffs_created: number
  tariffs_updated: number
  errors: string[]
  details: Array<{
    action: string
    workflow_code: string
    parent_code?: string | null
    data?: Record<string, unknown>
    reason?: string
    solicitud_type?: string
    amount?: number
  }>
}

export const syncApi = {
  /**
   * Sync predefined workflows from Python classes to database
   * BACKEND: POST /api/v1/admin/service-requests/sync/workflows
   */
  syncWorkflows: async (dryRun: boolean = false): Promise<WorkflowSyncResult> => {
    return fetchClient.post<WorkflowSyncResult>(
      `${ADMIN_BASE}/sync/workflows`,
      undefined,
      { dry_run: dryRun }
    )
  },
}

// =============================================================================
// EXTRACTION SCHEMAS API
// =============================================================================

export interface ExtractionSchema {
  key: string
  name: string
  version: string
}

export const extractionSchemasApi = {
  /**
   * List available OCR extraction schemas
   * BACKEND: GET /api/v1/admin/service-requests/extraction-schemas
   */
  getAll: async (): Promise<ExtractionSchema[]> => {
    return fetchClient.get<ExtractionSchema[]>(`${ADMIN_BASE}/extraction-schemas`)
  },
}

// =============================================================================
// COMBINED EXPORT
// =============================================================================

export const serviceRequestsAdminApi = {
  workflows: workflowsApi,
  documents: documentsApi,
  tariffs: tariffsApi,
  supplements: supplementsApi,
  workflowSupplements: workflowSupplementsApi,
  slotConfigs: slotConfigsApi,
  blockedDates: blockedDatesApi,
  delayRules: delayRulesApi,
  extractionSchemas: extractionSchemasApi,
  sync: syncApi,
}

export default serviceRequestsAdminApi
