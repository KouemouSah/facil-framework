/**
 * usePermissions Hook
 * React Query hook for fetching and managing permissions
 *
 * @module permissions-admin/hooks
 * @author Claude Code
 * @date 2025-11-17
 */

import { useQuery } from "@tanstack/react-query";
import type { PermissionFilter } from "../types";
import { permissionsApi } from "../services/api";

// =============================================================================
// QUERY KEYS
// =============================================================================

export const permissionsKeys = {
  all: ["permissions"] as const,
  lists: () => [...permissionsKeys.all, "list"] as const,
  list: (filters: PermissionFilter) => [...permissionsKeys.lists(), filters] as const,
  details: () => [...permissionsKeys.all, "detail"] as const,
  detail: (id: string) => [...permissionsKeys.details(), id] as const,
  byResource: () => [...permissionsKeys.all, "by-resource"] as const,
};

// =============================================================================
// HOOKS
// =============================================================================

/**
 * Hook to fetch all permissions with optional filters
 */
export function usePermissions(filters?: PermissionFilter) {
  return useQuery({
    queryKey: permissionsKeys.list(filters || {}),
    queryFn: async () => {
      const params: {
        module_name?: string;
        resource?: string;
        is_critical?: boolean;
      } = {};

      if (filters?.module_name) params.module_name = filters.module_name;
      if (filters?.resource) params.resource = filters.resource;
      if (filters?.is_critical !== undefined) params.is_critical = filters.is_critical;

      const permissions = await permissionsApi.getAll(params);

      // Client-side filtering for search
      if (filters?.search) {
        const searchLower = filters.search.toLowerCase();
        return permissions.filter(
          (perm) =>
            perm.name.toLowerCase().includes(searchLower) ||
            perm.description.toLowerCase().includes(searchLower)
        );
      }

      return permissions;
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

/**
 * Hook to fetch a single permission by ID
 */
export function usePermission(id: string | null) {
  return useQuery({
    queryKey: permissionsKeys.detail(id || ""),
    queryFn: () => permissionsApi.getById(id!),
    enabled: !!id,
    staleTime: 5 * 60 * 1000,
  });
}

/**
 * Hook to fetch permissions grouped by resource
 */
export function usePermissionsByResource() {
  return useQuery({
    queryKey: permissionsKeys.byResource(),
    queryFn: () => permissionsApi.getByResource(),
    staleTime: 5 * 60 * 1000,
  });
}

/**
 * Hook to get unique module names from permissions
 */
export function useModuleNames() {
  const { data: permissions = [] } = usePermissions();

  const moduleNames = Array.from(
    new Set(permissions.map((p) => p.module_name))
  ).sort();

  return moduleNames;
}

/**
 * Hook to get unique resources from permissions, optionally filtered by module
 */
export function useResources(moduleName?: string) {
  const { data: permissions = [] } = usePermissions(
    moduleName ? { module_name: moduleName } : undefined
  );

  const resources = Array.from(
    new Set(permissions.map((p) => p.resource))
  ).sort();

  return resources;
}
