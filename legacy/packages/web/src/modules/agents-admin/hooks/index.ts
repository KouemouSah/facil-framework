/**
 * Agents Admin Hooks
 * React Query hooks for agent and admin management
 *
 * @module agents-admin/hooks
 * @date 2025-01-14
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { agentCreationApi, agentProfilesApi, agentWorkloadApi, agentAlertsApi, adminAssistantApi, adminUsersApi, workflowsApi } from '../services/api';
import type { AdminAssistantPreviousContext } from '../services/api';
import type {
  AgentCompleteCreateRequest,
  AdminCreateRequest,
  AgentProfileUpdateRequest,
  AgentWorkloadUpdateRequest,
  AgentListFilters,
  AgentInviteRequest,
  AdminInviteRequest,
  AgentValidateRequest,
} from '../types';

// =============================================================================
// QUERY KEYS
// =============================================================================

export const agentQueryKeys = {
  all: ['agents'] as const,
  profiles: () => [...agentQueryKeys.all, 'profiles'] as const,
  profilesList: (filters?: AgentListFilters) => [...agentQueryKeys.profiles(), 'list', filters] as const,
  profileDetail: (id: string) => [...agentQueryKeys.profiles(), 'detail', id] as const,
  profileByUser: (userId: string) => [...agentQueryKeys.profiles(), 'user', userId] as const,
  supervisors: (ministryId?: number, entityId?: string) => [...agentQueryKeys.profiles(), 'supervisors', { ministryId, entityId }] as const,
  workload: (profileId: string) => [...agentQueryKeys.all, 'workload', profileId] as const,
  performance: (profileId: string) => [...agentQueryKeys.all, 'performance', profileId] as const,
  ministryStats: (ministryId: number) => [...agentQueryKeys.all, 'stats', 'ministry', ministryId] as const,
  entityStats: (entityId: string) => [...agentQueryKeys.all, 'stats', 'entity', entityId] as const,
  admins: () => [...agentQueryKeys.all, 'admins'] as const,
  adminsList: (page?: number) => [...agentQueryKeys.admins(), 'list', page] as const,
};

// =============================================================================
// AGENT PROFILES HOOKS
// =============================================================================

/**
 * Hook to list agent profiles with filters
 */
export function useAgentProfiles(filters?: AgentListFilters) {
  return useQuery({
    queryKey: agentQueryKeys.profilesList(filters),
    queryFn: () => agentProfilesApi.list(filters),
    staleTime: 30 * 1000, // 30 seconds
  });
}

/**
 * Hook to get agent profile by ID
 */
export function useAgentProfile(profileId: string, enabled = true) {
  return useQuery({
    queryKey: agentQueryKeys.profileDetail(profileId),
    queryFn: () => agentProfilesApi.getById(profileId),
    enabled: enabled && !!profileId,
    staleTime: 60 * 1000, // 1 minute
  });
}

/**
 * Hook to get prev/next agent IDs for navigation (lightweight — no full profile list loaded)
 */
export function useAgentNeighbors(profileId: string, enabled = true) {
  return useQuery({
    queryKey: [...agentQueryKeys.profileDetail(profileId), 'neighbors'] as const,
    queryFn: () => agentProfilesApi.getNeighbors(profileId),
    enabled: enabled && !!profileId,
    staleTime: 5 * 60 * 1000, // 5 minutes — rarely changes
  });
}

/**
 * Hook to get agent profile by user ID
 */
export function useAgentProfileByUser(userId: string, enabled = true) {
  return useQuery({
    queryKey: agentQueryKeys.profileByUser(userId),
    queryFn: () => agentProfilesApi.getByUserId(userId),
    enabled: enabled && !!userId,
    staleTime: 60 * 1000,
  });
}

/**
 * Hook to get supervisors
 */
export function useSupervisors(ministryId?: number, entityId?: string) {
  return useQuery({
    queryKey: agentQueryKeys.supervisors(ministryId, entityId),
    queryFn: () => agentProfilesApi.getSupervisors(ministryId, entityId),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

/**
 * Hook to get ministry agent stats
 */
export function useMinistryAgentStats(ministryId: number, enabled = true) {
  return useQuery({
    queryKey: agentQueryKeys.ministryStats(ministryId),
    queryFn: () => agentProfilesApi.getMinistryStats(ministryId),
    enabled: enabled && !!ministryId,
    staleTime: 60 * 1000,
  });
}

/**
 * Hook to get entity agent stats
 */
export function useEntityAgentStats(entityId: string, enabled = true) {
  return useQuery({
    queryKey: agentQueryKeys.entityStats(entityId),
    queryFn: () => agentProfilesApi.getEntityStats(entityId),
    enabled: enabled && !!entityId,
    staleTime: 60 * 1000,
  });
}

// =============================================================================
// WORKLOAD & PERFORMANCE HOOKS
// =============================================================================

/**
 * Hook to get agent workload
 */
export function useAgentWorkload(profileId: string, enabled = true) {
  return useQuery({
    queryKey: agentQueryKeys.workload(profileId),
    queryFn: () => agentWorkloadApi.getWorkload(profileId),
    enabled: enabled && !!profileId,
    staleTime: 30 * 1000, // 30 seconds - workload changes frequently
    refetchInterval: 60 * 1000, // Auto refresh every minute
  });
}

/**
 * Hook to get agent performance
 */
export function useAgentPerformance(profileId: string, enabled = true) {
  return useQuery({
    queryKey: agentQueryKeys.performance(profileId),
    queryFn: () => agentWorkloadApi.getPerformance(profileId),
    enabled: enabled && !!profileId,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

// =============================================================================
// ADMIN ALERTS DASHBOARD HOOKS
// =============================================================================

/**
 * Hook to get admin alerts dashboard
 * Auto-refreshes every 60s, stale after 30s
 */
export function useAlertsDashboard(enabled = true) {
  return useQuery({
    queryKey: [...agentQueryKeys.all, 'alerts-dashboard'],
    queryFn: () => agentAlertsApi.getDashboard(),
    enabled,
    staleTime: 30_000,
    refetchInterval: 60_000,
    refetchOnWindowFocus: true,
  });
}

// =============================================================================
// ADMIN ASSISTANT HOOKS
// =============================================================================

/**
 * Hook for admin assistant Q&A mutation.
 * Accepts optional previous context for conversational continuity.
 */
export function useAdminAssistant() {
  return useMutation({
    mutationFn: ({
      question,
      previousContext,
      sessionId,
    }: {
      question: string;
      previousContext?: AdminAssistantPreviousContext;
      sessionId?: string;
    }) => adminAssistantApi.askQuestion(question, previousContext, sessionId),
  });
}

// =============================================================================
// ADMIN USERS HOOKS
// =============================================================================

/**
 * Hook to list admin users
 */
export function useAdminUsers(page = 1, pageSize = 50, search?: string) {
  return useQuery({
    queryKey: [...agentQueryKeys.adminsList(page), { search }],
    queryFn: () => adminUsersApi.listAdmins(page, pageSize, search),
    staleTime: 30 * 1000,
  });
}

// =============================================================================
// MUTATION HOOKS - CREATION
// =============================================================================

/**
 * Hook to create complete agent (user + profile)
 */
export function useCreateAgent() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: AgentCompleteCreateRequest) => agentCreationApi.createAgent(data),
    onSuccess: () => {
      // Invalidate agent profiles list
      queryClient.invalidateQueries({ queryKey: agentQueryKeys.profiles() });
    },
  });
}

/**
 * Hook to create admin user
 * @deprecated Use useInviteAdmin instead
 */
export function useCreateAdmin() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: AdminCreateRequest) => agentCreationApi.createAdmin(data),
    onSuccess: () => {
      // Invalidate admin users list
      queryClient.invalidateQueries({ queryKey: agentQueryKeys.admins() });
    },
  });
}

// =============================================================================
// MUTATION HOOKS - INVITATION FLOW (RECOMMENDED)
// =============================================================================

/**
 * Hook to invite agent (sends email with verification code)
 * Step 1 of 2-step invitation flow
 */
export function useInviteAgent() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: AgentInviteRequest) => agentCreationApi.inviteAgent(data),
    onSuccess: () => {
      // Invalidate agent profiles list (pending invitation will show)
      queryClient.invalidateQueries({ queryKey: agentQueryKeys.profiles() });
    },
  });
}

/**
 * Hook to invite admin (sends email with verification code)
 * Step 1 of 2-step invitation flow
 */
export function useInviteAdmin() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: AdminInviteRequest) => agentCreationApi.inviteAdmin(data),
    onSuccess: () => {
      // Invalidate admin users list
      queryClient.invalidateQueries({ queryKey: agentQueryKeys.admins() });
    },
  });
}

// =============================================================================
// MUTATION HOOKS - UPDATE
// =============================================================================

/**
 * Hook to update agent profile
 */
export function useUpdateAgentProfile() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ profileId, data }: { profileId: string; data: AgentProfileUpdateRequest }) =>
      agentProfilesApi.update(profileId, data),
    onSuccess: (_, { profileId }) => {
      queryClient.invalidateQueries({ queryKey: agentQueryKeys.profileDetail(profileId) });
      queryClient.invalidateQueries({ queryKey: agentQueryKeys.profiles() });
    },
  });
}

/**
 * Hook to update agent workload
 */
export function useUpdateAgentWorkload() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ profileId, data }: { profileId: string; data: AgentWorkloadUpdateRequest }) =>
      agentWorkloadApi.updateWorkload(profileId, data),
    onSuccess: (_, { profileId }) => {
      queryClient.invalidateQueries({ queryKey: agentQueryKeys.workload(profileId) });
    },
  });
}

// =============================================================================
// MUTATION HOOKS - ACTIVATION/DEACTIVATION
// =============================================================================

/**
 * Hook to deactivate agent profile
 */
export function useDeactivateAgent() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ profileId, reason }: { profileId: string; reason?: string }) =>
      agentProfilesApi.deactivate(profileId, reason),
    onSuccess: (_, { profileId }) => {
      queryClient.invalidateQueries({ queryKey: agentQueryKeys.profileDetail(profileId) });
      queryClient.invalidateQueries({ queryKey: agentQueryKeys.profiles() });
    },
  });
}

/**
 * Hook to reactivate agent profile
 */
export function useReactivateAgent() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (profileId: string) => agentProfilesApi.reactivate(profileId),
    onSuccess: (_, profileId) => {
      queryClient.invalidateQueries({ queryKey: agentQueryKeys.profileDetail(profileId) });
      queryClient.invalidateQueries({ queryKey: agentQueryKeys.profiles() });
    },
  });
}

/**
 * Hook to activate user (admin/agent)
 */
export function useActivateUser() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (userId: string) => adminUsersApi.activateUser(userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: agentQueryKeys.admins() });
      queryClient.invalidateQueries({ queryKey: agentQueryKeys.profiles() });
    },
  });
}

/**
 * Hook to deactivate user (admin/agent)
 */
export function useDeactivateUser() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ userId, reason }: { userId: string; reason?: string }) =>
      adminUsersApi.deactivateUser(userId, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: agentQueryKeys.admins() });
      queryClient.invalidateQueries({ queryKey: agentQueryKeys.profiles() });
    },
  });
}

/**
 * Hook to delete agent user
 */
export function useDeleteAgentUser() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (userId: string) => adminUsersApi.deleteUser(userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: agentQueryKeys.profiles() });
    },
  });
}

// =============================================================================
// VALIDATION HOOKS
// =============================================================================

/**
 * Hook to validate agent data before submission
 */
export function useValidateAgent() {
  return useMutation({
    mutationFn: (data: AgentValidateRequest) => agentCreationApi.validateAgent(data),
  });
}

// =============================================================================
// WORKFLOWS HOOKS
// =============================================================================

/**
 * Hook to fetch available workflows for specializations
 */
export function useAvailableWorkflows(entityId?: string, category?: string, enabled = true) {
  return useQuery({
    queryKey: ['workflows', 'available', entityId, category],
    queryFn: () => workflowsApi.getAvailable(entityId, category),
    enabled,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}
