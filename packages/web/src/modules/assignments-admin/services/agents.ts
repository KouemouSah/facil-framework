/**
 * Agents API Service
 * Fetch available agents for assignment/reassignment
 *
 * @module assignments-admin/services/agents
 * @date 2026-01-20
 *
 * BACKEND ALIGNMENT:
 * Routes: /api/v1/agents/profiles (from app/modules/agents/api/profile_routes.py)
 */

import { fetchClient } from '@/core/api'

const AGENTS_BASE = '/agents'

/**
 * AgentProfile - Response from agent_profiles table
 * Aligned with AgentProfileWithDetails from backend
 */
export interface AgentProfile {
  id: string
  user_id: string
  agent_type: 'ministry_agent' | 'entity_agent'
  is_supervisor: boolean
  ministry_id?: number
  entity_id?: string
  is_active: boolean
  // Joined from users table
  full_name?: string
  email?: string
  // Workload info
  current_workload?: number
  max_capacity?: number
  workload_status?: 'available' | 'normal' | 'busy' | 'overloaded' | 'unavailable'
  // Entity/Ministry info
  ministry_name?: string
  entity_name?: string
  // Specializations
  specializations?: string[]
  available_workflows?: string[]
}

export interface AgentListResponse {
  items: AgentProfile[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface AgentListFilters {
  agent_type?: 'ministry_agent' | 'entity_agent'
  is_supervisor?: boolean
  ministry_id?: number
  entity_id?: string
  is_active?: boolean
  page?: number
  page_size?: number
}

/**
 * Available agent for assignment (simplified view)
 */
export interface AvailableAgent {
  agent_profile_id: string
  user_id: string
  agent_name: string
  email?: string
  current_assignments: number
  max_concurrent_assignments: number
  workload_status: string
  specializations?: string[]
}

/**
 * Agents API Service
 */
export const agentsApi = {
  /**
   * Get available agents for assignment
   * Returns agents that are active and not overloaded
   * BACKEND: GET /api/v1/agents/available (or profiles with filters)
   */
  getAvailable: async (): Promise<AvailableAgent[]> => {
    try {
      // Try dedicated available endpoint first
      return await fetchClient.get<AvailableAgent[]>(`${AGENTS_BASE}/available`)
    } catch {
      // Fallback: get all active agents and filter client-side
      const response = await fetchClient.get<AgentListResponse>(`${AGENTS_BASE}/profiles`, {
        is_active: true,
        page_size: 100,
      })
      return response.items
        .filter(a => a.workload_status !== 'unavailable' && a.workload_status !== 'overloaded')
        .map(a => ({
          agent_profile_id: a.id,
          user_id: a.user_id,
          agent_name: a.full_name || a.email || 'Unknown',
          email: a.email,
          current_assignments: a.current_workload || 0,
          max_concurrent_assignments: a.max_capacity || 20,
          workload_status: a.workload_status || 'available',
          specializations: a.specializations,
        }))
    }
  },

  /**
   * Get paginated list of agent profiles
   * BACKEND: GET /api/v1/agents/profiles
   */
  getAll: async (params?: AgentListFilters): Promise<AgentListResponse> => {
    return fetchClient.get<AgentListResponse>(`${AGENTS_BASE}/profiles`, {
      agent_type: params?.agent_type,
      is_supervisor: params?.is_supervisor,
      ministry_id: params?.ministry_id,
      entity_id: params?.entity_id,
      is_active: params?.is_active ?? true,
      page: params?.page ?? 1,
      page_size: params?.page_size ?? 50,
    })
  },

  /**
   * Get single agent profile by ID
   * BACKEND: GET /api/v1/agents/profiles/{profile_id}
   */
  getById: async (profileId: string): Promise<AgentProfile> => {
    return fetchClient.get<AgentProfile>(`${AGENTS_BASE}/profiles/${profileId}`)
  },

  /**
   * Get available agents for a ministry (for reassignment)
   * BACKEND: GET /api/v1/agents/profiles/ministry/{ministry_id}/available
   */
  getAvailableByMinistry: async (ministryId: number): Promise<AgentProfile[]> => {
    return fetchClient.get<AgentProfile[]>(
      `${AGENTS_BASE}/profiles/ministry/${ministryId}/available`
    )
  },

  /**
   * Get available agents for an entity (for reassignment)
   * BACKEND: GET /api/v1/agents/profiles/entity/{entity_id}/available
   */
  getAvailableByEntity: async (entityId: string): Promise<AgentProfile[]> => {
    return fetchClient.get<AgentProfile[]>(
      `${AGENTS_BASE}/profiles/entity/${entityId}/available`
    )
  },

  /**
   * Get list of supervisors
   * BACKEND: GET /api/v1/agents/profiles/supervisors/list
   */
  getSupervisors: async (ministryId?: number, entityId?: string): Promise<AgentProfile[]> => {
    const params: Record<string, string | number> = {}
    if (ministryId) params.ministry_id = ministryId
    if (entityId) params.entity_id = entityId
    return fetchClient.get<AgentProfile[]>(`${AGENTS_BASE}/profiles/supervisors/list`, params)
  },

  /**
   * Get workload for an agent profile
   * BACKEND: GET /api/v1/agents/profiles/{profile_id}/workload
   */
  getWorkload: async (profileId: string) => {
    return fetchClient.get(`${AGENTS_BASE}/profiles/${profileId}/workload`)
  },
}

export default agentsApi
