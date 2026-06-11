/**
 * useMenuConfig Hook
 * Fetches dynamic menu configuration from the backend API
 *
 * This hook replaces the hardcoded entity-menus.ts with backend-driven
 * menu configuration based on:
 * - Workflow-based entities: Auto-generated from entity.workflow_codes
 * - Module-based entities: Configured via roles.menu_config
 *
 * @module agent-dashboard/hooks
 * @date 2026-01-19
 */

'use client';

import { useState, useEffect, useMemo } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useLocale } from 'next-intl';
import { getAuthData } from '@/core/auth/storage';
import apiClient from '@/core/api/client';
import type {
  AgentMenuConfigResponse,
  DynamicMenuItem,
  MenuConfig,
  DashboardConfig,
  SubMenuItem,
} from '../types/menu-config';

// =============================================================================
// HOOK: useMenuConfig
// Fetches the dynamic menu configuration for the current agent
// =============================================================================

interface UseMenuConfigReturn {
  // Loading states
  isLoading: boolean;
  isError: boolean;
  error: Error | null;

  // Menu config data
  menuConfig: MenuConfig | null;
  dashboardConfig: DashboardConfig | null;

  // Agent info
  entityCode: string | null;
  entityType: 'workflow' | 'module' | null;
  roleCode: string | null;
  availableWorkflows: string[];

  // Permissions
  permissions: string[];
  hasPermission: (permission: string) => boolean;

  // Processed menu items (with locale-prefixed hrefs)
  menuItems: DynamicMenuItem[];

  // Refetch function
  refetch: () => void;
}

export function useMenuConfig(): UseMenuConfigReturn {
  const locale = useLocale();

  // Use state to handle SSR/hydration timing
  const [authState, setAuthState] = useState<{
    userId: string | null;
    role: string | null;
    isLoaded: boolean;
  }>({
    userId: null,
    role: null,
    isLoaded: false,
  });

  // Load auth data on client-side only (after hydration)
  useEffect(() => {
    const authData = getAuthData();
    if (authData?.user) {
      setAuthState({
        userId: authData.user.id,
        role: authData.user.role,
        isLoaded: true,
      });
    } else {
      setAuthState({
        userId: null,
        role: null,
        isLoaded: true,
      });
    }
  }, []);

  // Only fetch if user is an agent
  const isAgent = authState.role === 'agent';

  const {
    data,
    isLoading: queryLoading,
    isError,
    error,
    refetch,
  } = useQuery<AgentMenuConfigResponse | null>({
    queryKey: ['agent-menu-config', 'me', authState.userId],
    queryFn: async () => {
      if (!authState.userId || !isAgent) return null;

      try {
        const response = await apiClient.get<AgentMenuConfigResponse>(
          '/menu-config/me'
        );
        return response.data;
      } catch (err) {
        console.error('[useMenuConfig] Failed to fetch menu config:', err);
        throw err;
      }
    },
    // Only enable after auth state is loaded and user is an agent
    enabled: authState.isLoaded && !!authState.userId && isAgent,
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 10 * 60 * 1000,
    refetchOnMount: 'always',
    retry: 2,
  });

  const isLoading = !authState.isLoaded || queryLoading;

  // Build permissions set for quick lookup
  const permissionsSet = useMemo(() => {
    return new Set(data?.permissions || []);
  }, [data?.permissions]);

  // Permission check helper
  const hasPermission = (permission: string): boolean => {
    return permissionsSet.has(permission);
  };

  // Process menu items: add locale prefix to hrefs
  const menuItems: DynamicMenuItem[] = useMemo(() => {
    if (!data?.menu_config?.menus) {
      return [];
    }

    return data.menu_config.menus.map((menu): DynamicMenuItem => {
      // Process submenu items
      const processedItems: SubMenuItem[] | undefined = menu.items?.map(
        (item): SubMenuItem => ({
          ...item,
          href: item.href.startsWith('/') ? `/${locale}${item.href}` : item.href,
        })
      );

      return {
        ...menu,
        href: menu.href
          ? menu.href.startsWith('/')
            ? `/${locale}${menu.href}`
            : menu.href
          : undefined,
        items: processedItems,
      };
    });
  }, [data?.menu_config?.menus, locale]);

  return {
    isLoading,
    isError,
    error: error as Error | null,
    menuConfig: data?.menu_config || null,
    dashboardConfig: data?.dashboard_config || null,
    entityCode: data?.entity_code || null,
    entityType: data?.entity_type || null,
    roleCode: data?.role_code || null,
    availableWorkflows: data?.available_workflows || [],
    permissions: data?.permissions || [],
    hasPermission,
    menuItems,
    refetch,
  };
}

// =============================================================================
// HOOK: useDynamicMenuItems
// Simplified hook that only returns processed menu items for sidebar rendering
// =============================================================================

export function useDynamicMenuItems(): {
  isLoading: boolean;
  menuItems: DynamicMenuItem[];
  entityCode: string | null;
  entityType: 'workflow' | 'module' | null;
} {
  const { isLoading, menuItems, entityCode, entityType } = useMenuConfig();

  return {
    isLoading,
    menuItems,
    entityCode,
    entityType,
  };
}

export default useMenuConfig;

// =============================================================================
// UTILITY: Prefetch Menu Config
// Call this after successful login to preload the menu configuration
// =============================================================================

export const MENU_CONFIG_QUERY_KEY = ['agent-menu-config', 'me'] as const;

/**
 * Prefetch agent menu configuration after login.
 * This populates the React Query cache so the sidebar loads instantly.
 *
 * @param queryClient - The React Query client instance
 * @param userId - The logged-in user's ID
 * @returns Promise that resolves when prefetch is complete
 */
export async function prefetchAgentMenuConfig(
  queryClient: ReturnType<typeof useQueryClient>,
  userId: string
): Promise<void> {
  try {
    await queryClient.prefetchQuery({
      queryKey: [...MENU_CONFIG_QUERY_KEY, userId],
      queryFn: async () => {
        const response = await apiClient.get<AgentMenuConfigResponse>(
          '/menu-config/me'
        );
        return response.data;
      },
      staleTime: 5 * 60 * 1000, // 5 minutes
    });
    // Prefetch successful
  } catch {
    // Don't throw - prefetch failures shouldn't break the login flow
  }
}

/**
 * Hook to get prefetch function with access to query client.
 * Use this in components that need to trigger prefetch.
 */
export function usePrefetchMenuConfig(): {
  prefetch: (userId: string) => Promise<void>;
} {
  const queryClient = useQueryClient();

  return {
    prefetch: (userId: string) => prefetchAgentMenuConfig(queryClient, userId),
  };
}
