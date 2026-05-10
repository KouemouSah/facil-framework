/**
 * Agents Admin API Service
 * Handles agent and admin user management operations
 *
 * @module agents-admin/services
 * @date 2025-01-14
 *
 * BACKEND ALIGNMENT:
 * Routes: /api/v1/agents (from app/modules/agents/api/agent_routes.py)
 *
 * ENDPOINTS:
 * - POST   /agents/complete              → Create agent (user + profile)
 * - POST   /agents/admin                 → Create admin user
 * - GET    /agents/profiles              → List agent profiles
 * - GET    /agents/profiles/{id}         → Get agent profile
 * - PUT    /agents/profiles/{id}         → Update agent profile
 * - POST   /agents/profiles/{id}/deactivate → Deactivate agent
 * - POST   /agents/profiles/{id}/reactivate → Reactivate agent
 * - GET    /agents/profiles/{id}/workload   → Get workload
 * - GET    /agents/profiles/{id}/performance → Get performance
 */

import { fetchClient } from '@/core/api';
import type {
  AgentProfile,
  AgentWorkload,
  AgentPerformance,
  AgentCompleteCreateRequest,
  AgentCompleteResponse,
  AdminCreateRequest,
  AdminCreateResponse,
  AgentProfileUpdateRequest,
  AgentWorkloadUpdateRequest,
  AgentListFilters,
  AgentListResponse,
  AgentStats,
  WorkflowOption,
  AdminAlertsDashboard,
  AdminAssistantResponse,
  // Invitation flow types
  AgentInviteRequest,
  AgentInviteResponse,
  AgentActivateRequest,
  AgentActivateResponse,
  AdminInviteRequest,
  AdminInviteResponse,
  AdminActivateRequest,
  AdminActivateResponse,
  // Validation types
  AgentValidateRequest,
  AgentValidateResponse,
} from '../types';

// =============================================================================
// CONFIGURATION
// =============================================================================

const AGENTS_BASE = '/agents';
const ADMIN_USERS_BASE = '/admin/users';

// =============================================================================
// AGENT CREATION API
// =============================================================================

export const agentCreationApi = {
  // =========================================================================
  // INVITATION FLOW (2-step: invite → activate) - RECOMMENDED
  // =========================================================================

  /**
   * Step 1: Invite agent (sends email with verification code)
   * BACKEND: POST /api/v1/agents/invite
   *
   * Agent will receive email with code and activation link.
   * They must set their password via POST /agents/activate.
   */
  /**
   * Pre-submit validation: check data before sending invitation.
   * BACKEND: POST /api/v1/agents/validate
   */
  validateAgent: async (data: AgentValidateRequest): Promise<AgentValidateResponse> => {
    return fetchClient.post<AgentValidateResponse>(`${AGENTS_BASE}/validate`, data);
  },

  inviteAgent: async (data: AgentInviteRequest): Promise<AgentInviteResponse> => {
    return fetchClient.post<AgentInviteResponse>(`${AGENTS_BASE}/invite`, data);
  },

  /**
   * Step 2: Activate agent account (PUBLIC - no auth)
   * BACKEND: POST /api/v1/agents/activate
   *
   * Agent provides code from email and chooses password.
   * Account is created with email_verified=true.
   */
  activateAgent: async (data: AgentActivateRequest): Promise<AgentActivateResponse> => {
    return fetchClient.post<AgentActivateResponse>(`${AGENTS_BASE}/activate`, data);
  },

  /**
   * Step 1: Invite admin (sends email with verification code)
   * BACKEND: POST /api/v1/agents/admin/invite
   *
   * Admin will receive email with code and activation link.
   * They must set their password via POST /agents/admin/activate.
   */
  inviteAdmin: async (data: AdminInviteRequest): Promise<AdminInviteResponse> => {
    return fetchClient.post<AdminInviteResponse>(`${AGENTS_BASE}/admin/invite`, data);
  },

  /**
   * Step 2: Activate admin account (PUBLIC - no auth)
   * BACKEND: POST /api/v1/agents/admin/activate
   *
   * Admin provides code from email and chooses password.
   * Account is created with email_verified=true.
   */
  activateAdmin: async (data: AdminActivateRequest): Promise<AdminActivateResponse> => {
    return fetchClient.post<AdminActivateResponse>(`${AGENTS_BASE}/admin/activate`, data);
  },

  // =========================================================================
  // LEGACY METHODS (DEPRECATED - will return 410 GONE)
  // =========================================================================

  /**
   * @deprecated Use inviteAgent + activateAgent instead
   * BACKEND: POST /api/v1/agents/complete (returns 410 GONE)
   */
  createAgent: async (data: AgentCompleteCreateRequest): Promise<AgentCompleteResponse> => {
    console.warn('[DEPRECATED] Use inviteAgent() instead of createAgent()');
    return fetchClient.post<AgentCompleteResponse>(`${AGENTS_BASE}/complete`, data);
  },

  /**
   * @deprecated Use inviteAdmin + activateAdmin instead
   * BACKEND: POST /api/v1/agents/admin (returns 410 GONE)
   */
  createAdmin: async (data: AdminCreateRequest): Promise<AdminCreateResponse> => {
    console.warn('[DEPRECATED] Use inviteAdmin() instead of createAdmin()');
    return fetchClient.post<AdminCreateResponse>(`${AGENTS_BASE}/admin`, data);
  },
};

// =============================================================================
// AGENT PROFILES API
// =============================================================================

export const agentProfilesApi = {
  /**
   * List agent profiles with filters
   * BACKEND: GET /api/v1/agents/profiles
   * Handles both array response (legacy) and paginated response (new)
   */
  list: async (filters?: AgentListFilters): Promise<AgentListResponse> => {
    const params = new URLSearchParams();
    const page = filters?.page || 1;
    const pageSize = filters?.page_size || 100;

    if (filters) {
      if (filters.agent_type) params.append('agent_type', filters.agent_type);
      if (filters.is_supervisor !== undefined) params.append('is_supervisor', String(filters.is_supervisor));
      if (filters.ministry_id) params.append('ministry_id', String(filters.ministry_id));
      if (filters.entity_id) params.append('entity_id', filters.entity_id);
      if (filters.entity_code) params.append('entity_code', filters.entity_code);
      if (filters.agent_category) params.append('agent_category', filters.agent_category);
      if (filters.is_active !== undefined) params.append('is_active', String(filters.is_active));
      if (filters.availability) params.append('availability', filters.availability);
      if (filters.search) params.append('search', filters.search);
      if (filters.sort_by) params.append('sort_by', filters.sort_by);
      if (filters.sort_order) params.append('sort_order', filters.sort_order);
      if (filters.page) params.append('page', String(filters.page));
      if (filters.page_size) params.append('page_size', String(filters.page_size));
    }

    const queryString = params.toString();
    const url = `${AGENTS_BASE}/profiles${queryString ? `?${queryString}` : ''}`;

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const response = await fetchClient.get<AgentListResponse | AgentProfile[]>(url);

    // Handle both array response (legacy) and paginated response (new)
    if (Array.isArray(response)) {
      // Legacy: Convert array to paginated format
      return {
        items: response,
        total: response.length,
        page: page,
        page_size: pageSize,
        pages: Math.ceil(response.length / pageSize) || 1,
      };
    }

    // New paginated format
    return response;
  },

  /**
   * Get agent profile by ID
   * BACKEND: GET /api/v1/agents/profiles/{profile_id}
   */
  getById: async (profileId: string): Promise<AgentProfile> => {
    return fetchClient.get<AgentProfile>(`${AGENTS_BASE}/profiles/${profileId}`);
  },

  /**
   * Get agent profile by user ID
   * BACKEND: GET /api/v1/agents/profiles/user/{user_id}
   */
  getByUserId: async (userId: string): Promise<AgentProfile> => {
    return fetchClient.get<AgentProfile>(`${AGENTS_BASE}/profiles/user/${userId}`);
  },

  /**
   * Get prev/next agent IDs for navigation (lightweight)
   * BACKEND: GET /api/v1/agents/profiles/{profile_id}/neighbors
   */
  getNeighbors: async (profileId: string): Promise<{
    prev_id: string | null;
    next_id: string | null;
    position: number;
    total: number;
  }> => {
    return fetchClient.get(`${AGENTS_BASE}/profiles/${profileId}/neighbors`);
  },

  /**
   * Update agent profile
   * BACKEND: PUT /api/v1/agents/profiles/{profile_id}
   */
  update: async (profileId: string, data: AgentProfileUpdateRequest): Promise<AgentProfile> => {
    return fetchClient.put<AgentProfile>(`${AGENTS_BASE}/profiles/${profileId}`, data);
  },

  /**
   * Deactivate agent profile
   * BACKEND: POST /api/v1/agents/profiles/{profile_id}/deactivate
   */
  deactivate: async (profileId: string, reason?: string): Promise<{ message: string; profile_id: string }> => {
    return fetchClient.post(`${AGENTS_BASE}/profiles/${profileId}/deactivate`, { reason });
  },

  /**
   * Reactivate agent profile
   * BACKEND: POST /api/v1/agents/profiles/{profile_id}/reactivate
   */
  reactivate: async (profileId: string): Promise<{ message: string; profile_id: string }> => {
    return fetchClient.post(`${AGENTS_BASE}/profiles/${profileId}/reactivate`);
  },

  /**
   * Get supervisors
   * BACKEND: GET /api/v1/agents/profiles/supervisors
   */
  getSupervisors: async (ministryId?: number, entityId?: string): Promise<AgentProfile[]> => {
    const params = new URLSearchParams();
    if (ministryId) params.append('ministry_id', String(ministryId));
    if (entityId) params.append('entity_id', entityId);

    const queryString = params.toString();
    const url = `${AGENTS_BASE}/profiles/supervisors${queryString ? `?${queryString}` : ''}`;

    return fetchClient.get<AgentProfile[]>(url);
  },

  /**
   * Get available agents for ministry
   * BACKEND: GET /api/v1/agents/profiles/ministry/{ministry_id}/available
   */
  getAvailableForMinistry: async (ministryId: number, minApprovalAmount?: number): Promise<AgentProfile[]> => {
    const params = new URLSearchParams();
    if (minApprovalAmount) params.append('min_approval_amount', String(minApprovalAmount));

    const queryString = params.toString();
    const url = `${AGENTS_BASE}/profiles/ministry/${ministryId}/available${queryString ? `?${queryString}` : ''}`;

    return fetchClient.get<AgentProfile[]>(url);
  },

  /**
   * Get ministry agent stats
   * BACKEND: GET /api/v1/agents/profiles/ministry/{ministry_id}/stats
   */
  getMinistryStats: async (ministryId: number): Promise<AgentStats> => {
    return fetchClient.get<AgentStats>(`${AGENTS_BASE}/profiles/ministry/${ministryId}/stats`);
  },

  /**
   * Get entity agent stats
   * BACKEND: GET /api/v1/agents/profiles/entity/{entity_id}/stats
   */
  getEntityStats: async (entityId: string): Promise<AgentStats> => {
    return fetchClient.get<AgentStats>(`${AGENTS_BASE}/profiles/entity/${entityId}/stats`);
  },
};

// =============================================================================
// WORKLOAD & PERFORMANCE API
// =============================================================================

export const agentWorkloadApi = {
  /**
   * Get agent workload
   * BACKEND: GET /api/v1/agents/profiles/{agent_profile_id}/workload
   */
  getWorkload: async (profileId: string): Promise<AgentWorkload> => {
    return fetchClient.get<AgentWorkload>(`${AGENTS_BASE}/profiles/${profileId}/workload`);
  },

  /**
   * Update agent workload
   * BACKEND: PUT /api/v1/agents/profiles/{agent_profile_id}/workload
   */
  updateWorkload: async (profileId: string, data: AgentWorkloadUpdateRequest): Promise<AgentWorkload> => {
    return fetchClient.put<AgentWorkload>(`${AGENTS_BASE}/profiles/${profileId}/workload`, data);
  },

  /**
   * Get agent performance
   * BACKEND: GET /api/v1/agents/profiles/{agent_profile_id}/performance
   */
  getPerformance: async (profileId: string): Promise<AgentPerformance> => {
    return fetchClient.get<AgentPerformance>(`${AGENTS_BASE}/profiles/${profileId}/performance`);
  },
};

// =============================================================================
// ADMIN ALERTS DASHBOARD API
// =============================================================================

export const agentAlertsApi = {
  /**
   * Get aggregated alerts dashboard for admin
   * BACKEND: GET /api/v1/agents/admin/alerts-dashboard
   */
  getDashboard: async (): Promise<AdminAlertsDashboard> => {
    return fetchClient.get<AdminAlertsDashboard>(`${AGENTS_BASE}/admin/alerts-dashboard`);
  },
};

// =============================================================================
// ADMIN ASSISTANT API
// =============================================================================

export interface AdminAssistantPreviousContext {
  question: string;
  tools_used: string[];
}

export const adminAssistantApi = {
  /**
   * Send question to LLM admin assistant
   * BACKEND: POST /api/v1/agents/admin/assistant
   */
  askQuestion: async (
    question: string,
    previousContext?: AdminAssistantPreviousContext,
    sessionId?: string,
  ): Promise<AdminAssistantResponse> => {
    return fetchClient.post<AdminAssistantResponse>(`${AGENTS_BASE}/admin/assistant`, {
      question,
      ...(previousContext ? { previous_context: previousContext } : {}),
      ...(sessionId ? { session_id: sessionId } : {}),
    });
  },
};

// =============================================================================
// WORKFLOWS API (for specializations)
// =============================================================================

export const workflowsApi = {
  /**
   * Get all available workflows for specializations
   * BACKEND: GET /api/v1/agents/workflows/available
   */
  getAvailable: async (entityId?: string, category?: string): Promise<WorkflowOption[]> => {
    const params = new URLSearchParams();
    if (entityId) params.append('entity_id', entityId);
    if (category) params.append('category', category);

    const queryString = params.toString();
    const url = `${AGENTS_BASE}/workflows/available${queryString ? `?${queryString}` : ''}`;

    return fetchClient.get<WorkflowOption[]>(url);
  },
};

// =============================================================================
// ADMIN USERS API (for listing admins)
// =============================================================================

export const adminUsersApi = {
  /**
   * List users filtered by role (for getting admins)
   * BACKEND: GET /api/v1/admin/users?role=admin
   */
  listAdmins: async (page = 1, pageSize = 50, search?: string): Promise<{
    items: Array<{
      id: string;
      email: string;
      role: 'admin';
      status: string;
      first_name: string;
      last_name: string;
      created_at: string;
      updated_at: string;
      last_login?: string;
    }>;
    total: number;
    page: number;
    page_size: number;
    pages: number;
  }> => {
    const params = new URLSearchParams({ role: 'admin', page: String(page), size: String(pageSize) });
    if (search) params.append('search', search);
    return fetchClient.get(`${ADMIN_USERS_BASE}?${params.toString()}`);
  },

  /**
   * Activate user
   * BACKEND: POST /api/v1/admin/users/{user_id}/activate
   */
  activateUser: async (userId: string): Promise<{ message: string; user_id: string; status: string }> => {
    return fetchClient.post(`${ADMIN_USERS_BASE}/${userId}/activate`);
  },

  /**
   * Deactivate user
   * BACKEND: POST /api/v1/admin/users/{user_id}/deactivate
   */
  deactivateUser: async (userId: string, reason?: string): Promise<{ message: string; user_id: string; status: string; reason?: string }> => {
    const params = reason ? `?reason=${encodeURIComponent(reason)}` : '';
    return fetchClient.post(`${ADMIN_USERS_BASE}/${userId}/deactivate${params}`);
  },

  /**
   * Update user profile (email, phone, etc.)
   * BACKEND: PUT /api/v1/admin/users/{user_id}
   */
  updateUser: async (userId: string, data: { email?: string; phone_number?: string }): Promise<unknown> => {
    return fetchClient.put(`${ADMIN_USERS_BASE}/${userId}`, data);
  },

  /**
   * Delete user (agents only)
   * BACKEND: DELETE /api/v1/admin/users/{user_id}
   */
  deleteUser: async (userId: string): Promise<{ message: string }> => {
    return fetchClient.delete(`${ADMIN_USERS_BASE}/${userId}`);
  },
};

// =============================================================================
// COMBINED EXPORTS
// =============================================================================

export const agentsAdminApi = {
  creation: agentCreationApi,
  profiles: agentProfilesApi,
  workload: agentWorkloadApi,
  alerts: agentAlertsApi,
  assistant: adminAssistantApi,
  users: adminUsersApi,
};

export default agentsAdminApi;
