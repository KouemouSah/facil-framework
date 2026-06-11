/**
 * Templates API Service
 * Handles all API calls for document and procedure templates
 *
 * @module templates/services
 * @author Claude Code
 * @date 2025-11-25
 *
 * BACKEND ALIGNMENT: Phase 10
 * Base URL: /api/v1
 * Routes: /document-templates, /procedure-templates
 */

import { fetchClient } from '@/core/api'
import type {
  DocumentTemplate,
  DocumentTemplateCreate,
  DocumentTemplateUpdate,
  ProcedureTemplate,
  ProcedureTemplateCreate,
  ProcedureTemplateUpdate,
  ProcedureStep,
  ProcedureStepCreate,
  ProcedureStepUpdate,
} from '@/types/fiscal-service'

// =============================================================================
// CONFIGURATION
// =============================================================================

const DOCUMENTS_BASE = '/document-templates'
const PROCEDURES_BASE = '/procedure-templates'

// =============================================================================
// BACKEND RESPONSE TYPES (snake_case)
// =============================================================================

interface BackendDocumentTemplate {
  id: number
  template_code: string
  document_name_es: string
  description_es?: string
  category?: string
  validity_duration_months?: number
  validity_notes?: string
  usage_count: number
  is_active: boolean
  created_at: string
  updated_at?: string
  created_by?: number
}

interface BackendProcedureTemplate {
  id: number
  template_code: string
  name_es: string
  description_es?: string
  category?: string
  usage_count: number
  is_active: boolean
  created_at: string
  updated_at?: string
  created_by?: number
}

interface BackendProcedureStep {
  id: number
  template_id: number
  step_number: number
  description_es: string
  instructions_es?: string
  estimated_duration_minutes?: number
  location_address?: string
  office_hours?: string
  requires_appointment: boolean
  is_optional: boolean
  created_at: string
  updated_at?: string
}

interface DocumentTemplateListResponse {
  templates: BackendDocumentTemplate[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

interface ProcedureTemplateListResponse {
  templates: BackendProcedureTemplate[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

// Paginated response types for frontend
export interface PaginatedDocumentTemplates {
  templates: DocumentTemplate[]
  total: number
  page: number
  pageSize: number
  totalPages: number
}

export interface PaginatedProcedureTemplates {
  templates: ProcedureTemplate[]
  total: number
  page: number
  pageSize: number
  totalPages: number
}

// =============================================================================
// CONVERTERS (snake_case -> camelCase)
// =============================================================================

function convertDocumentTemplate(backend: BackendDocumentTemplate): DocumentTemplate {
  return {
    id: backend.id,
    templateCode: backend.template_code,
    documentNameEs: backend.document_name_es,
    descriptionEs: backend.description_es,
    category: backend.category,
    validityDurationMonths: backend.validity_duration_months,
    validityNotes: backend.validity_notes,
    usageCount: backend.usage_count,
    isActive: backend.is_active,
    createdAt: backend.created_at,
    updatedAt: backend.updated_at,
    createdBy: backend.created_by,
  }
}

function convertProcedureTemplate(backend: BackendProcedureTemplate): ProcedureTemplate {
  return {
    id: backend.id,
    templateCode: backend.template_code,
    nameEs: backend.name_es,
    descriptionEs: backend.description_es,
    category: backend.category,
    usageCount: backend.usage_count,
    isActive: backend.is_active,
    createdAt: backend.created_at,
    updatedAt: backend.updated_at,
    createdBy: backend.created_by,
  }
}

function convertProcedureStep(backend: BackendProcedureStep): ProcedureStep {
  return {
    id: backend.id,
    templateId: backend.template_id,
    stepNumber: backend.step_number,
    descriptionEs: backend.description_es,
    instructionsEs: backend.instructions_es,
    estimatedDurationMinutes: backend.estimated_duration_minutes,
    locationAddress: backend.location_address,
    officeHours: backend.office_hours,
    requiresAppointment: backend.requires_appointment,
    isOptional: backend.is_optional,
    createdAt: backend.created_at,
    updatedAt: backend.updated_at,
  }
}

// =============================================================================
// DOCUMENT TEMPLATES API
// =============================================================================

export const documentTemplatesApi = {
  /**
   * GET /api/v1/document-templates
   * Get all document templates with i18n support
   */
  list: async (params?: {
    category?: string
    isActive?: boolean
    language?: string
    page?: number
    pageSize?: number
  }): Promise<DocumentTemplate[]> => {
    const response = await fetchClient.get<DocumentTemplateListResponse>(DOCUMENTS_BASE, {
      category: params?.category,
      is_active: params?.isActive,
      language: params?.language || 'es',
      page: params?.page,
      page_size: params?.pageSize,
    })
    return response.templates.map(convertDocumentTemplate)
  },

  /**
   * GET /api/v1/document-templates (with pagination info)
   * Get document templates with pagination metadata and i18n support
   */
  listPaginated: async (params?: {
    category?: string
    isActive?: boolean
    language?: string
    page?: number
    pageSize?: number
  }): Promise<PaginatedDocumentTemplates> => {
    const response = await fetchClient.get<DocumentTemplateListResponse>(DOCUMENTS_BASE, {
      category: params?.category,
      is_active: params?.isActive,
      language: params?.language || 'es',
      page: params?.page || 1,
      page_size: params?.pageSize || 20,
    })
    return {
      templates: response.templates.map(convertDocumentTemplate),
      total: response.total,
      page: response.page,
      pageSize: response.page_size,
      totalPages: response.total_pages,
    }
  },

  /**
   * GET /api/v1/document-templates/{template_id}
   * Get single document template
   */
  get: async (templateId: number | string): Promise<DocumentTemplate> => {
    const response = await fetchClient.get<BackendDocumentTemplate>(`${DOCUMENTS_BASE}/${templateId}`)
    return convertDocumentTemplate(response)
  },

  /**
   * POST /api/v1/document-templates
   * Create new document template
   * Auth: Required + Permission "templates.create"
   */
  create: async (data: DocumentTemplateCreate): Promise<DocumentTemplate> => {
    const response = await fetchClient.post<BackendDocumentTemplate>(DOCUMENTS_BASE, {
      template_code: data.templateCode,
      document_name_es: data.documentNameEs,
      description_es: data.descriptionEs,
      category: data.category,
      validity_duration_months: data.validityDurationMonths,
      validity_notes: data.validityNotes,
      is_active: data.isActive,
    })
    return convertDocumentTemplate(response)
  },

  /**
   * PUT /api/v1/document-templates/{template_id}
   * Update document template
   * Auth: Required + Permission "templates.update"
   */
  update: async (
    templateId: number | string,
    data: DocumentTemplateUpdate
  ): Promise<DocumentTemplate> => {
    const response = await fetchClient.put<BackendDocumentTemplate>(`${DOCUMENTS_BASE}/${templateId}`, {
      document_name_es: data.documentNameEs,
      description_es: data.descriptionEs,
      category: data.category,
      validity_duration_months: data.validityDurationMonths,
      validity_notes: data.validityNotes,
      is_active: data.isActive,
    })
    return convertDocumentTemplate(response)
  },

  /**
   * DELETE /api/v1/document-templates/{template_id}
   * Delete document template
   * Auth: Required + Permission "templates.delete"
   */
  delete: async (templateId: number | string): Promise<{ message: string }> => {
    return fetchClient.delete<{ message: string }>(`${DOCUMENTS_BASE}/${templateId}`)
  },
}

// =============================================================================
// PROCEDURE TEMPLATES API
// =============================================================================

export const procedureTemplatesApi = {
  /**
   * GET /api/v1/procedure-templates
   * Get all procedure templates with i18n support
   */
  list: async (params?: {
    category?: string
    isActive?: boolean
    language?: string
    page?: number
    pageSize?: number
  }): Promise<ProcedureTemplate[]> => {
    const response = await fetchClient.get<ProcedureTemplateListResponse>(PROCEDURES_BASE, {
      category: params?.category,
      is_active: params?.isActive,
      language: params?.language || 'es',
      page: params?.page,
      page_size: params?.pageSize,
    })
    return response.templates.map(convertProcedureTemplate)
  },

  /**
   * GET /api/v1/procedure-templates (with pagination info)
   * Get procedure templates with pagination metadata and i18n support
   */
  listPaginated: async (params?: {
    category?: string
    isActive?: boolean
    language?: string
    page?: number
    pageSize?: number
  }): Promise<PaginatedProcedureTemplates> => {
    const response = await fetchClient.get<ProcedureTemplateListResponse>(PROCEDURES_BASE, {
      category: params?.category,
      is_active: params?.isActive,
      language: params?.language || 'es',
      page: params?.page || 1,
      page_size: params?.pageSize || 20,
    })
    return {
      templates: response.templates.map(convertProcedureTemplate),
      total: response.total,
      page: response.page,
      pageSize: response.page_size,
      totalPages: response.total_pages,
    }
  },

  /**
   * GET /api/v1/procedure-templates/{template_id}
   * Get single procedure template
   */
  get: async (templateId: number | string): Promise<ProcedureTemplate> => {
    const response = await fetchClient.get<BackendProcedureTemplate>(`${PROCEDURES_BASE}/${templateId}`)
    return convertProcedureTemplate(response)
  },

  /**
   * POST /api/v1/procedure-templates
   * Create new procedure template
   * Auth: Required + Permission "templates.create"
   */
  create: async (data: ProcedureTemplateCreate): Promise<ProcedureTemplate> => {
    const response = await fetchClient.post<BackendProcedureTemplate>(PROCEDURES_BASE, {
      template_code: data.templateCode,
      name_es: data.nameEs,
      description_es: data.descriptionEs,
      category: data.category,
      is_active: data.isActive,
    })
    return convertProcedureTemplate(response)
  },

  /**
   * PUT /api/v1/procedure-templates/{template_id}
   * Update procedure template
   * Auth: Required + Permission "templates.update"
   */
  update: async (
    templateId: number | string,
    data: ProcedureTemplateUpdate
  ): Promise<ProcedureTemplate> => {
    const response = await fetchClient.put<BackendProcedureTemplate>(`${PROCEDURES_BASE}/${templateId}`, {
      name_es: data.nameEs,
      description_es: data.descriptionEs,
      category: data.category,
      is_active: data.isActive,
    })
    return convertProcedureTemplate(response)
  },

  /**
   * DELETE /api/v1/procedure-templates/{template_id}
   * Delete procedure template
   * Auth: Required + Permission "templates.delete"
   */
  delete: async (templateId: number | string): Promise<{ message: string }> => {
    return fetchClient.delete<{ message: string }>(`${PROCEDURES_BASE}/${templateId}`)
  },
}

// =============================================================================
// PROCEDURE STEPS API
// =============================================================================

export const procedureStepsApi = {
  /**
   * GET /api/v1/procedure-templates/{template_id}/steps
   * Get all steps for a procedure template
   */
  list: async (templateId: number | string): Promise<ProcedureStep[]> => {
    const response = await fetchClient.get<BackendProcedureStep[]>(`${PROCEDURES_BASE}/${templateId}/steps`)
    return response.map(convertProcedureStep)
  },

  /**
   * GET /api/v1/procedure-templates/{template_id}/steps/{step_id}
   * Get single procedure step
   */
  get: async (templateId: number | string, stepId: number): Promise<ProcedureStep> => {
    const response = await fetchClient.get<BackendProcedureStep>(`${PROCEDURES_BASE}/${templateId}/steps/${stepId}`)
    return convertProcedureStep(response)
  },

  /**
   * POST /api/v1/procedure-templates/{template_id}/steps
   * Create new procedure step
   * Auth: Required + Permission "templates.update"
   */
  create: async (
    templateId: number | string,
    data: ProcedureStepCreate
  ): Promise<ProcedureStep> => {
    const response = await fetchClient.post<BackendProcedureStep>(`${PROCEDURES_BASE}/${templateId}/steps`, {
      template_id: data.templateId,
      step_number: data.stepNumber,
      description_es: data.descriptionEs,
      instructions_es: data.instructionsEs,
      estimated_duration_minutes: data.estimatedDurationMinutes,
      location_address: data.locationAddress,
      office_hours: data.officeHours,
      requires_appointment: data.requiresAppointment,
      is_optional: data.isOptional,
    })
    return convertProcedureStep(response)
  },

  /**
   * PUT /api/v1/procedure-templates/{template_id}/steps/{step_id}
   * Update procedure step
   * Auth: Required + Permission "templates.update"
   */
  update: async (
    templateId: number | string,
    stepId: number,
    data: ProcedureStepUpdate
  ): Promise<ProcedureStep> => {
    const response = await fetchClient.put<BackendProcedureStep>(
      `${PROCEDURES_BASE}/${templateId}/steps/${stepId}`,
      {
        step_number: data.stepNumber,
        description_es: data.descriptionEs,
        instructions_es: data.instructionsEs,
        estimated_duration_minutes: data.estimatedDurationMinutes,
        location_address: data.locationAddress,
        office_hours: data.officeHours,
        requires_appointment: data.requiresAppointment,
        is_optional: data.isOptional,
      }
    )
    return convertProcedureStep(response)
  },

  /**
   * DELETE /api/v1/procedure-templates/{template_id}/steps/{step_id}
   * Delete procedure step
   * Auth: Required + Permission "templates.update"
   */
  delete: async (
    templateId: number | string,
    stepId: number
  ): Promise<{ message: string }> => {
    return fetchClient.delete<{ message: string }>(
      `${PROCEDURES_BASE}/${templateId}/steps/${stepId}`
    )
  },

  /**
   * POST /api/v1/procedure-templates/{template_id}/steps/reorder
   * Reorder procedure steps
   * Auth: Required + Permission "templates.update"
   */
  reorder: async (
    templateId: number | string,
    stepIds: number[]
  ): Promise<{ message: string }> => {
    return fetchClient.post<{ message: string }>(
      `${PROCEDURES_BASE}/${templateId}/steps/reorder`,
      { step_ids: stepIds }
    )
  },
}

// =============================================================================
// EXPORTS
// =============================================================================

export default {
  documents: documentTemplatesApi,
  procedures: procedureTemplatesApi,
  steps: procedureStepsApi,
}
