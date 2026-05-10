/**
 * useAgentDashboard Hook
 * Fetches current user's agent profile and determines dashboard configuration
 *
 * Updated 2026-01-19: Dynamic menu configuration from backend API.
 * Updated 2026-02-14: 100% dynamic — backend API is the sole source of truth.
 * No static imports from entity-menus.ts. All entity metadata (icon, name,
 * menus) comes from GET /menu-config/me which reads from PredefinedWorkflow
 * classes synced to DB at startup.
 *
 * @module agent-dashboard/hooks
 * @date 2026-01-19
 */

'use client';

import { useState, useEffect, useMemo, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useLocale } from 'next-intl';
import { getAuthData } from '@/core/auth/storage';
import apiClient from '@/core/api/client';
import type { AgentDashboardContext, EntityCode, MenuItem } from '../types';
import type { AgentMenuConfigResponse, DynamicMenuItem } from '../types/menu-config';
import { FEATURE_DYNAMIC_MENUS } from '@/core/config/features';

// =============================================================================
// API RESPONSE TYPES
// =============================================================================

interface AgentProfileResponse {
  id: string;
  user_id: string;
  agent_type: 'ministry_agent' | 'entity_agent';
  is_supervisor: boolean;
  entity_id: string | null;
  entity_location_id: string | null;
  ministry_id: number | null;
  specializations: string[];
  is_active: boolean;
  // Joined fields
  entity_code?: string;
  entity_name?: string;
  ministry_code?: string;
  ministry_name?: string;
  location_name?: string;
  location_city?: string;
  is_main_office?: boolean;
  // Entity hierarchy (derived from DB)
  child_entity_codes?: string[];
  ministry_entities?: string[];
}

// =============================================================================
// HOOK: useAgentProfile
// Fetches the current user's agent profile
// =============================================================================

export function useAgentProfile() {
  // Use state to handle SSR/hydration timing - getAuthData() relies on localStorage
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

  // Only fetch if user is an agent (new unified role from migration 048)
  const isAgent = authState.role === 'agent';

  return useQuery<AgentProfileResponse | null>({
    queryKey: ['agent-profile', 'me', authState.userId],
    queryFn: async () => {
      if (!authState.userId || !isAgent) return null;

      try {
        const response = await apiClient.get<AgentProfileResponse>(
          '/agents/profiles/me'
        );
        return response.data;
      } catch (error) {
        console.error('Failed to fetch agent profile:', error);
        return null;
      }
    },
    // Only enable after auth state is loaded and user is an agent
    enabled: authState.isLoaded && !!authState.userId && isAgent,
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 10 * 60 * 1000,
  });
}

// =============================================================================
// HOOK: useAgentDashboard
// Main hook for agent dashboard configuration
// =============================================================================

interface UseAgentDashboardReturn {
  // Loading states
  isLoading: boolean;
  isError: boolean;
  error: Error | null;

  // Agent context
  context: AgentDashboardContext | null;

  // Entity info (from backend API — 100% dynamic)
  entityCode: EntityCode | null;
  entityName: string | null;
  entityIcon: string | null;

  // Menu items (legacy — always empty, kept for backward compatibility)
  menuItems: MenuItem[];

  // Dynamic menu items from API
  dynamicMenuItems: DynamicMenuItem[];
  useDynamicMenus: boolean;

  // Helper functions
  hasPermission: (permission: string) => boolean;
  getBasePath: () => string;

  // Ministry agent specific
  isMinistryAgent: boolean;
  ministryEntities: EntityCode[];

  // Dynamic config
  menuConfig: AgentMenuConfigResponse | null;
}

export function useAgentDashboard(): UseAgentDashboardReturn {
  const locale = useLocale();

  // Use state to handle SSR/hydration timing - getAuthData() relies on localStorage
  const [userState, setUserState] = useState<{
    user: { id?: string; role?: string; permissions?: string[] } | null;
    isLoaded: boolean;
  }>({
    user: null,
    isLoaded: false,
  });

  // Load user data on client-side only (after hydration)
  useEffect(() => {
    const authData = getAuthData();
    setUserState({
      user: authData?.user || null,
      isLoaded: true,
    });
  }, []);

  const user = userState.user;

  // Fetch agent profile
  const {
    data: agentProfile,
    isLoading: profileLoading,
    isError: profileError,
    error: profileErr,
  } = useAgentProfile();

  // Fetch dynamic menu configuration from backend API
  const isAgent = userState.user?.role === 'agent';
  const {
    data: menuConfigData,
    isLoading: menuConfigLoading,
    isError: menuConfigError,
  } = useQuery<AgentMenuConfigResponse | null>({
    queryKey: ['agent-menu-config', 'me', userState.user?.id],
    queryFn: async () => {
      if (!userState.user?.id || !isAgent) return null;
      const response = await apiClient.get<AgentMenuConfigResponse>('/menu-config/me');
      return response.data;
    },
    enabled: userState.isLoaded && !!userState.user?.id && isAgent,
    staleTime: 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
    retry: 2,
  });

  // Use dynamic menus if feature flag is enabled and API returns menus
  const hasDynamicMenusFromApi = !!menuConfigData?.menu_config?.menus?.length;
  const useDynamicMenus = FEATURE_DYNAMIC_MENUS && hasDynamicMenusFromApi;

  // Log critical errors: DB has menu_config but parsing failed
  if (typeof window !== 'undefined' && !menuConfigLoading && menuConfigData) {
    if (menuConfigData.has_role_menu_config && !hasDynamicMenusFromApi) {
      console.error(
        `[useAgentDashboard] role.menu_config exists in DB but no menus parsed. ` +
        `role=${menuConfigData.role_code}. Check JSON format in roles.menu_config.`
      );
    }
  }

  // Include userState.isLoaded in loading check to prevent SSR mismatch
  const isLoading = !userState.isLoaded || profileLoading || (isAgent && menuConfigLoading);
  const isError = profileError || menuConfigError;
  const error = profileErr;

  // Build agent context
  const context: AgentDashboardContext | null = agentProfile
    ? {
        agentProfileId: agentProfile.id,
        userId: agentProfile.user_id,
        entityCode: (agentProfile.entity_code as EntityCode) || null,
        entityId: agentProfile.entity_id,
        entityName: agentProfile.entity_name || null,
        entityLocationId: agentProfile.entity_location_id || null,
        isMainOffice: agentProfile.is_main_office ?? true,
        locationName: agentProfile.location_name || null,
        ministryId: agentProfile.ministry_id,
        ministryName: agentProfile.ministry_name || null,
        isSupervisor: agentProfile.is_supervisor,
        permissions: user?.permissions || [],
        specializations: agentProfile.specializations || [],
      }
    : null;

  // Entity code: from agent profile (primary) or menu config API (fallback)
  const entityCode: EntityCode | null =
    (agentProfile?.entity_code as EntityCode) ||
    (menuConfigData?.entity_code as EntityCode) ||
    null;

  // Entity metadata from backend API (100% dynamic, no static config)
  const entityName: string | null = menuConfigData?.entity_name || agentProfile?.entity_name || null;
  const entityIcon: string | null = menuConfigData?.entity_icon || null;

  // Get user permissions (from auth data or agent profile)
  const userPermissions = useMemo(
    () => new Set(user?.permissions || []),
    [user?.permissions]
  );

  // Helper to check permission (memoized to prevent infinite re-renders)
  const hasPermission = useCallback((permission: string): boolean => {
    // Supervisors have all permissions within their entity
    if (context?.isSupervisor) return true;
    // Check if user has the specific permission
    return userPermissions.has(permission);
  }, [context?.isSupervisor, userPermissions]);

  // Determine if this is a ministry_agent (supervisor over ministry entities)
  const isMinistryAgent = agentProfile?.agent_type === 'ministry_agent';

  // Get ministry entities from backend profile (no hardcoded mapping)
  const ministryEntities: EntityCode[] = (
    isMinistryAgent && agentProfile?.ministry_entities?.length
      ? agentProfile.ministry_entities
      : []
  ) as EntityCode[];

  // Legacy menuItems: always empty — dynamic menus from API are the sole source of truth.
  const menuItems: MenuItem[] = useMemo(() => [], []);

  // Process dynamic menu items with locale-prefixed hrefs
  const dynamicMenuItems: DynamicMenuItem[] = useMemo(() => {
    if (!menuConfigData?.menu_config?.menus) {
      return [];
    }
    // Check if user has a specific permission
    const checkPerm = (perm?: string) => {
      if (!perm) return true; // No permission required → visible
      if (context?.isSupervisor) return true; // Supervisors see everything
      return userPermissions.has(perm);
    };

    const items = menuConfigData.menu_config.menus
      // Filter top-level items by permission
      .filter((menu) => checkPerm(menu.permission))
      .map((menu) => ({
        ...menu,
        href: menu.href
          ? menu.href.startsWith('/')
            ? `/${locale}${menu.href}`
            : menu.href
          : undefined,
        // Filter sub-items by permission
        items: menu.items
          ?.filter((item) => checkPerm(item.permission))
          .map((item) => ({
            ...item,
            href: item.href.startsWith('/') ? `/${locale}${item.href}` : item.href,
          })),
      }))
      // Remove groups with no visible sub-items (after permission filtering)
      .filter((menu) => menu.href || (menu.items && menu.items.length > 0));

    // Inject AI Assistant right after dashboard item (i18n via agent.nav.assistant)
    const hasAnalystPermission = context?.permissions?.includes('analyst.ask');
    if (hasAnalystPermission) {
      const dashboardIdx = items.findIndex((m) => m.id === 'dashboard');
      if (dashboardIdx >= 0) {
        const dashboardHref = items[dashboardIdx].href || '';
        const assistantItem: DynamicMenuItem = {
          id: 'assistant',
          titleKey: 'agent.nav.assistant',
          icon: 'Sparkles',
          href: `${dashboardHref}/assistant`,
        };
        items.splice(dashboardIdx + 1, 0, assistantItem as typeof items[number]);
      }
    }

    return items;
  }, [menuConfigData?.menu_config?.menus, locale, context?.permissions, context?.isSupervisor, userPermissions]);

  // Derive base path from menu_config dashboard href (role-aware)
  // Priority: 1) ministry agent → /ministry  2) menu_config dashboard href  3) entity code fallback
  const getBasePath = (): string => {
    if (isMinistryAgent) {
      return `/${locale}/dashboard/agent/ministry`;
    }
    // Use the role's menu_config dashboard href (isLoading waits for menuConfigLoading)
    const dashboardMenu = menuConfigData?.menu_config?.menus?.find(
      (m: { id: string }) => m.id === 'dashboard'
    );
    if (dashboardMenu?.href) {
      return `/${locale}${dashboardMenu.href}`;
    }
    if (!entityCode) return `/${locale}/dashboard/agent`;
    const entityPath = entityCode.toLowerCase().replace(/_/g, '-');
    return `/${locale}/dashboard/agent/${entityPath}`;
  };

  return {
    isLoading,
    isError,
    error: error as Error | null,
    context,
    entityCode,
    entityName,
    entityIcon,
    menuItems,
    dynamicMenuItems,
    useDynamicMenus,
    hasPermission,
    getBasePath,
    isMinistryAgent,
    ministryEntities,
    menuConfig: menuConfigData || null,
  };
}

// =============================================================================
// HOOK: useAgentEntityRedirect
// Determines the correct dashboard URL for the current agent
// =============================================================================

export function useAgentEntityRedirect(): {
  isLoading: boolean;
  redirectUrl: string | null;
  entityCode: EntityCode | null;
} {
  const { isLoading, entityCode, getBasePath } = useAgentDashboard();

  const redirectUrl = entityCode ? getBasePath() : null;

  return {
    isLoading,
    redirectUrl,
    entityCode,
  };
}

export default useAgentDashboard;
