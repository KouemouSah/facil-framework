/**
 * Menu Configuration API Service
 * Handles workflow mappings and role menu configuration
 *
 * @module admin/services
 * @date 2026-01-19
 * @updated 2026-01-31 - Removed unused menu_templates endpoints
 *
 * BACKEND ALIGNMENT:
 * Routes: /api/v1/menu-config (from app/modules/menu_config/api/menu_config_routes.py)
 * - GET    /api/v1/menu-config/me                    → get_my_menu_config
 * - GET    /api/v1/menu-config/workflow-mappings     → list_workflow_mappings
 * - POST   /api/v1/menu-config/workflow-mappings     → create_workflow_mapping
 * - PUT    /api/v1/menu-config/workflow-mappings/{id} → update_workflow_mapping
 * - DELETE /api/v1/menu-config/workflow-mappings/{id} → delete_workflow_mapping
 */

import { fetchClient } from '@/core/api';
import type {
  WorkflowMenuMapping,
  WorkflowMenuMappingListResponse,
  AgentMenuConfigResponse,
  CustomSubItem,
} from '@/modules/agent-dashboard/types/menu-config';

// =============================================================================
// CONFIGURATION
// =============================================================================

const MENU_CONFIG_BASE = '/menu-config';

// =============================================================================
// TYPES
// =============================================================================

export interface WorkflowMappingCreateRequest {
  workflow_pattern: string;
  menu_group_id: string;
  menu_title_key: string;
  menu_icon: string;
  display_order?: number;
  include_pending?: boolean;
  include_validation?: boolean;
  include_appointments?: boolean;
  include_history?: boolean;
  include_escalation?: boolean;
  include_batch?: boolean;
  custom_sub_items?: CustomSubItem[];
  permission_prefix?: string;
}

export interface WorkflowMappingUpdateRequest {
  menu_title_key?: string;
  menu_icon?: string;
  display_order?: number;
  include_pending?: boolean;
  include_validation?: boolean;
  include_appointments?: boolean;
  include_history?: boolean;
  include_escalation?: boolean;
  include_batch?: boolean;
  custom_sub_items?: CustomSubItem[];
  permission_prefix?: string;
  is_active?: boolean;
}

export interface PaginationParams {
  page?: number;
  page_size?: number;
}

// Workflow Code types (for dropdown selection)
export interface WorkflowCode {
  code: string;
  name_es: string;
  category: string | null;
}

export interface WorkflowCodeListResponse {
  items: WorkflowCode[];
  total: number;
}

// Display Config types
export interface DisplayConfig {
  id: number;
  workflow_code: string;  // Changed from workflow_pattern (migration 088)
  list_columns: string[];
  preview_sections: string[];
  labels: Record<string, string>;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface DisplayConfigListResponse {
  items: DisplayConfig[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface DisplayConfigCreateRequest {
  workflow_code: string;  // Changed from workflow_pattern (migration 088)
  list_columns?: string[];
  preview_sections?: string[];
  labels?: Record<string, string>;
}

export interface DisplayConfigUpdateRequest {
  list_columns?: string[];
  preview_sections?: string[];
  labels?: Record<string, string>;
  is_active?: boolean;
}

// Available Columns types (from workflow document requirements + JSON schemas)
export interface AvailableColumn {
  id: string;
  label_key: string;
  label: string;
  source: 'system' | 'extracted';
  data_type: 'string' | 'number' | 'date' | 'boolean';
  sample_count: number;
  document_code?: string;
  document_name_es?: string;
}

export interface AvailableColumnsResponse {
  workflow_code: string;
  total_requests: number;
  system_columns: AvailableColumn[];
  extracted_columns: AvailableColumn[];
  filters_applied: Record<string, unknown> | null;
  available_filters: Record<string, unknown[]> | null;
  suggested_columns: string[];
  document_count: number;
}

/** Filters for available columns discovery */
export interface AvailableColumnsFilters {
  is_minor?: boolean;
}

// Sample Request types (for real data preview)
export interface SampleRequest {
  id: string;
  reference: string;
  citizen_name: string | null;
  workflow_code: string;
  status: string;
  priority: string | null;
  extracted_data: Record<string, unknown> | null;
  form_data: Record<string, unknown> | null;
  created_at: string;
}

// =============================================================================
// MENU CONFIG API
// =============================================================================

export const menuConfigApi = {
  // ===========================================================================
  // AGENT MENU CONFIG
  // ===========================================================================

  /**
   * Get current agent's menu configuration
   * BACKEND: GET /api/v1/menu-config/me
   * PERMISSION: authenticated
   */
  getMyMenuConfig: async (): Promise<AgentMenuConfigResponse> => {
    return fetchClient.get<AgentMenuConfigResponse>(`${MENU_CONFIG_BASE}/me`);
  },

  // ===========================================================================
  // WORKFLOW MENU MAPPINGS
  // ===========================================================================

  /**
   * List all workflow menu mappings with pagination
   * BACKEND: GET /api/v1/menu-config/workflow-mappings
   * PERMISSION: menu.view_mappings
   */
  listWorkflowMappings: async (
    params?: PaginationParams
  ): Promise<WorkflowMenuMappingListResponse> => {
    const searchParams = new URLSearchParams();
    if (params?.page) searchParams.set('page', params.page.toString());
    if (params?.page_size) searchParams.set('page_size', params.page_size.toString());

    const query = searchParams.toString();
    const url = query
      ? `${MENU_CONFIG_BASE}/workflow-mappings?${query}`
      : `${MENU_CONFIG_BASE}/workflow-mappings`;

    return fetchClient.get<WorkflowMenuMappingListResponse>(url);
  },

  /**
   * Get a single workflow mapping by ID
   * BACKEND: GET /api/v1/menu-config/workflow-mappings/{id}
   * PERMISSION: menu.view_mappings
   */
  getWorkflowMapping: async (id: number): Promise<WorkflowMenuMapping> => {
    return fetchClient.get<WorkflowMenuMapping>(
      `${MENU_CONFIG_BASE}/workflow-mappings/${id}`
    );
  },

  /**
   * Create a new workflow menu mapping
   * BACKEND: POST /api/v1/menu-config/workflow-mappings
   * PERMISSION: menu.create_mapping
   */
  createWorkflowMapping: async (
    data: WorkflowMappingCreateRequest
  ): Promise<WorkflowMenuMapping> => {
    return fetchClient.post<WorkflowMenuMapping>(
      `${MENU_CONFIG_BASE}/workflow-mappings`,
      data
    );
  },

  /**
   * Update an existing workflow mapping
   * BACKEND: PUT /api/v1/menu-config/workflow-mappings/{id}
   * PERMISSION: menu.update_mapping
   */
  updateWorkflowMapping: async (
    id: number,
    data: WorkflowMappingUpdateRequest
  ): Promise<WorkflowMenuMapping> => {
    return fetchClient.put<WorkflowMenuMapping>(
      `${MENU_CONFIG_BASE}/workflow-mappings/${id}`,
      data
    );
  },

  /**
   * Delete a workflow mapping
   * BACKEND: DELETE /api/v1/menu-config/workflow-mappings/{id}
   * PERMISSION: menu.delete_mapping
   */
  deleteWorkflowMapping: async (id: number): Promise<void> => {
    return fetchClient.delete(`${MENU_CONFIG_BASE}/workflow-mappings/${id}`);
  },

  // ===========================================================================
  // ROLE MENU CONFIG
  // ===========================================================================

  /**
   * Get menu config for a specific role
   * BACKEND: GET /api/v1/roles/{role_id}/menu-config
   * PERMISSION: roles.view
   */
  getRoleMenuConfig: async (
    roleId: string
  ): Promise<{ menu_config: Record<string, unknown>; dashboard_config: Record<string, unknown>; ui_config?: Record<string, unknown> }> => {
    return fetchClient.get(`/roles/${roleId}/menu-config`);
  },

  /**
   * Update menu config for a specific role
   * BACKEND: PUT /api/v1/roles/{role_id}/menu-config
   * PERMISSION: roles.update
   */
  updateRoleMenuConfig: async (
    roleId: string,
    data: {
      menu_config?: Record<string, unknown>;
      dashboard_config?: Record<string, unknown>;
      ui_config?: Record<string, unknown>;
    }
  ): Promise<void> => {
    return fetchClient.put(`/roles/${roleId}/menu-config`, data);
  },

  // ===========================================================================
  // WORKFLOW DISPLAY CONFIG
  // ===========================================================================

  /**
   * List all workflow display configs with pagination
   * BACKEND: GET /api/v1/menu-config/display-configs
   * PERMISSION: admin.menu.read
   */
  listDisplayConfigs: async (
    params?: PaginationParams
  ): Promise<DisplayConfigListResponse> => {
    const searchParams = new URLSearchParams();
    if (params?.page) searchParams.set('page', params.page.toString());
    if (params?.page_size) searchParams.set('page_size', params.page_size.toString());

    const query = searchParams.toString();
    const url = query
      ? `${MENU_CONFIG_BASE}/display-configs?${query}`
      : `${MENU_CONFIG_BASE}/display-configs`;

    return fetchClient.get<DisplayConfigListResponse>(url);
  },

  /**
   * Get a single display config by ID
   * BACKEND: GET /api/v1/menu-config/display-configs/{id}
   * PERMISSION: admin.menu.read
   */
  getDisplayConfig: async (id: number): Promise<DisplayConfig> => {
    return fetchClient.get<DisplayConfig>(`${MENU_CONFIG_BASE}/display-configs/${id}`);
  },

  /**
   * Get display config for a specific workflow code
   * BACKEND: GET /api/v1/menu-config/display-configs/by-workflow/{workflow_code}
   * PERMISSION: authenticated
   */
  getDisplayConfigForWorkflow: async (workflowCode: string): Promise<DisplayConfig> => {
    return fetchClient.get<DisplayConfig>(
      `${MENU_CONFIG_BASE}/display-configs/by-workflow/${encodeURIComponent(workflowCode)}`
    );
  },

  /**
   * Create a new display config
   * BACKEND: POST /api/v1/menu-config/display-configs
   * PERMISSION: admin.menu.create
   */
  createDisplayConfig: async (data: DisplayConfigCreateRequest): Promise<DisplayConfig> => {
    return fetchClient.post<DisplayConfig>(`${MENU_CONFIG_BASE}/display-configs`, data);
  },

  /**
   * Update an existing display config
   * BACKEND: PUT /api/v1/menu-config/display-configs/{id}
   * PERMISSION: admin.menu.update
   */
  updateDisplayConfig: async (
    id: number,
    data: DisplayConfigUpdateRequest
  ): Promise<DisplayConfig> => {
    return fetchClient.put<DisplayConfig>(`${MENU_CONFIG_BASE}/display-configs/${id}`, data);
  },

  /**
   * Delete a display config
   * BACKEND: DELETE /api/v1/menu-config/display-configs/{id}
   * PERMISSION: admin.menu.delete
   */
  deleteDisplayConfig: async (id: number): Promise<void> => {
    return fetchClient.delete(`${MENU_CONFIG_BASE}/display-configs/${id}`);
  },

  /**
   * Discover available columns for a workflow code
   * Uses workflow document requirements + JSON extraction schemas
   * BACKEND: GET /api/v1/menu-config/display-configs/available-columns/{workflow_code}
   * PERMISSION: menu.view_mappings
   */
  getAvailableColumns: async (
    workflowCode: string,
    filters?: AvailableColumnsFilters,
  ): Promise<AvailableColumnsResponse> => {
    const searchParams = new URLSearchParams();
    if (filters?.is_minor !== undefined) {
      searchParams.set('is_minor', String(filters.is_minor));
    }
    const query = searchParams.toString();
    const base = `${MENU_CONFIG_BASE}/display-configs/available-columns/${encodeURIComponent(workflowCode)}`;
    const url = query ? `${base}?${query}` : base;
    return fetchClient.get<AvailableColumnsResponse>(url);
  },

  // ===========================================================================
  // WORKFLOW CODES (for dropdown selection)
  // ===========================================================================

  /**
   * List all available workflow codes for dropdown selection
   * BACKEND: GET /api/v1/menu-config/workflows
   * PERMISSION: menu.view_mappings
   */
  getWorkflowCodes: async (): Promise<WorkflowCodeListResponse> => {
    return fetchClient.get<WorkflowCodeListResponse>(`${MENU_CONFIG_BASE}/workflows`);
  },

  /**
   * Get a sample service request for preview purposes
   * BACKEND: GET /api/v1/menu-config/display-configs/sample-request/{workflow_code}
   * PERMISSION: menu.view_mappings
   */
  getSampleRequest: async (workflowCode: string): Promise<SampleRequest | null> => {
    return fetchClient.get<SampleRequest | null>(
      `${MENU_CONFIG_BASE}/display-configs/sample-request/${encodeURIComponent(workflowCode)}`
    );
  },
};

// =============================================================================
// EXPORTS
// =============================================================================

export default menuConfigApi;
