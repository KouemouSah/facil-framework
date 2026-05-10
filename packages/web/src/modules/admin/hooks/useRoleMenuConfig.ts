/**
 * Role Menu Config Hook
 * React Query hooks for managing role menu/dashboard/ui configurations
 *
 * @module admin/hooks
 * @date 2026-01-25
 */

'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import apiClient from '@/core/api/client';

// =============================================================================
// TYPES
// =============================================================================

export interface RoleMenuConfigResponse {
  menu_config: Record<string, unknown> | null;
  dashboard_config: Record<string, unknown> | null;
  ui_config: Record<string, unknown> | null;
}

export interface RoleMenuConfigUpdateRequest {
  menu_config?: Record<string, unknown> | null;
  dashboard_config?: Record<string, unknown> | null;
  ui_config?: Record<string, unknown> | null;
}

// =============================================================================
// QUERY KEYS
// =============================================================================

export const roleMenuConfigKeys = {
  all: ['role-menu-config'] as const,
  detail: (roleId: string) => [...roleMenuConfigKeys.all, roleId] as const,
};

// =============================================================================
// API FUNCTIONS
// =============================================================================

async function fetchRoleMenuConfig(roleId: string): Promise<RoleMenuConfigResponse> {
  const response = await apiClient.get<RoleMenuConfigResponse>(
    `/roles/${roleId}/menu-config`
  );
  return response.data;
}

async function updateRoleMenuConfig(
  roleId: string,
  data: RoleMenuConfigUpdateRequest
): Promise<RoleMenuConfigResponse> {
  const response = await apiClient.put<RoleMenuConfigResponse>(
    `/roles/${roleId}/menu-config`,
    data
  );
  return response.data;
}

// =============================================================================
// HOOKS
// =============================================================================

/**
 * Hook to fetch role menu configuration
 */
export function useRoleMenuConfig(roleId: string, enabled = true) {
  return useQuery<RoleMenuConfigResponse, Error>({
    queryKey: roleMenuConfigKeys.detail(roleId),
    queryFn: () => fetchRoleMenuConfig(roleId),
    enabled: enabled && !!roleId,
    staleTime: 5 * 60 * 1000,
  });
}

/**
 * Hook for updating role menu configuration
 */
export function useUpdateRoleMenuConfig() {
  const queryClient = useQueryClient();

  return useMutation<
    RoleMenuConfigResponse,
    Error,
    { roleId: string; data: RoleMenuConfigUpdateRequest }
  >({
    mutationFn: ({ roleId, data }) => updateRoleMenuConfig(roleId, data),
    onSuccess: (_, { roleId }) => {
      queryClient.invalidateQueries({ queryKey: roleMenuConfigKeys.detail(roleId) });
      toast.success('Configuration du menu mise à jour');
    },
    onError: (error) => {
      toast.error('Erreur de mise à jour', {
        description: error.message,
      });
    },
  });
}

/**
 * Combined hook for role menu config operations
 */
export function useRoleMenuConfigOperations(roleId: string) {
  const query = useRoleMenuConfig(roleId);
  const updateMutation = useUpdateRoleMenuConfig();

  return {
    // Query data
    menuConfig: query.data?.menu_config ?? null,
    dashboardConfig: query.data?.dashboard_config ?? null,
    uiConfig: query.data?.ui_config ?? null,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    refetch: query.refetch,

    // Mutation
    update: (data: RoleMenuConfigUpdateRequest) =>
      updateMutation.mutate({ roleId, data }),
    updateAsync: (data: RoleMenuConfigUpdateRequest) =>
      updateMutation.mutateAsync({ roleId, data }),
    isUpdating: updateMutation.isPending,
  };
}
