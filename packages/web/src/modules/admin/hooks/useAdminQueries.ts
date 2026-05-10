/**
 * React Query hooks for Admin Dashboard
 *
 * Provides cached data fetching for:
 * - User management
 * - Audit logs
 * - System statistics
 * - Roles and permissions
 *
 * Cache strategy:
 * - User list: 1 min stale (admin views frequently)
 * - Audit logs: 30 sec stale (real-time monitoring)
 * - Stats: 5 min stale (aggregate data)
 * - Roles/permissions: 10 min stale (rarely changes)
 *
 * @module admin/hooks
 * @date 2026-01-25
 */

'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import apiClient from '@/core/api/client';

// =============================================================================
// TYPES
// =============================================================================

export interface AdminStats {
  totalUsers: number;
  activeUsers: number;
  pendingVerifications: number;
  totalDeclarations: number;
  declarationsThisMonth: number;
  totalPayments: number;
  paymentsThisMonth: number;
  revenue: number;
}

export interface UserListItem {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: string;
  status: string;
  created_at: string;
  last_login_at?: string;
}

export interface UserListResponse {
  users: UserListItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface UserFilters {
  search?: string;
  role?: string;
  status?: string;
  page?: number;
  pageSize?: number;
}

export interface AuditLogEntry {
  id: string;
  user_id: string;
  user_email?: string;
  action: string;
  resource: string;
  resource_id?: string;
  details?: Record<string, unknown>;
  ip_address?: string;
  created_at: string;
}

export interface AuditLogResponse {
  logs: AuditLogEntry[];
  total: number;
  page: number;
  page_size: number;
}

export interface AuditFilters {
  userId?: string;
  action?: string;
  resource?: string;
  startDate?: string;
  endDate?: string;
  page?: number;
  pageSize?: number;
}

export interface RoleWithPermissions {
  id: string;
  code: string;
  name: string;
  description?: string;
  permissions: string[];
  user_count?: number;
}

// =============================================================================
// QUERY KEYS
// =============================================================================

export const adminQueryKeys = {
  all: ['admin'] as const,
  stats: () => [...adminQueryKeys.all, 'stats'] as const,
  users: () => [...adminQueryKeys.all, 'users'] as const,
  userList: (filters: UserFilters) =>
    [...adminQueryKeys.users(), JSON.stringify(filters)] as const,
  userDetail: (userId: string) => [...adminQueryKeys.users(), 'detail', userId] as const,
  audit: () => [...adminQueryKeys.all, 'audit'] as const,
  auditLogs: (filters: AuditFilters) =>
    [...adminQueryKeys.audit(), JSON.stringify(filters)] as const,
  roles: () => [...adminQueryKeys.all, 'roles'] as const,
  permissions: () => [...adminQueryKeys.all, 'permissions'] as const,
};

// =============================================================================
// CACHE CONFIGURATION
// =============================================================================

const CACHE_CONFIG = {
  // User list - admin views frequently
  users: {
    staleTime: 1 * 60 * 1000, // 1 minute
    gcTime: 5 * 60 * 1000, // 5 minutes
  },
  // Audit logs - real-time monitoring
  audit: {
    staleTime: 30 * 1000, // 30 seconds
    gcTime: 5 * 60 * 1000, // 5 minutes
  },
  // Stats - aggregate data
  stats: {
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 15 * 60 * 1000, // 15 minutes
  },
  // Roles and permissions - rarely changes
  rolesPermissions: {
    staleTime: 10 * 60 * 1000, // 10 minutes
    gcTime: 30 * 60 * 1000, // 30 minutes
  },
};

// =============================================================================
// STATS HOOK
// =============================================================================

/**
 * Fetch admin dashboard statistics
 */
export function useAdminStats(options?: { enabled?: boolean }) {
  return useQuery<AdminStats>({
    queryKey: adminQueryKeys.stats(),
    queryFn: async () => {
      const response = await apiClient.get('/admin/stats');
      return response.data;
    },
    ...CACHE_CONFIG.stats,
    enabled: options?.enabled !== false,
    retry: 2,
  });
}

// =============================================================================
// USER MANAGEMENT HOOKS
// =============================================================================

/**
 * Fetch users list with filters and pagination
 */
export function useAdminUsers(filters: UserFilters = {}) {
  const { page = 1, pageSize = 20, ...otherFilters } = filters;

  return useQuery<UserListResponse>({
    queryKey: adminQueryKeys.userList(filters),
    queryFn: async () => {
      const params = new URLSearchParams();
      params.set('page', String(page));
      params.set('page_size', String(pageSize));
      if (otherFilters.search) params.set('search', otherFilters.search);
      if (otherFilters.role) params.set('role', otherFilters.role);
      if (otherFilters.status) params.set('status', otherFilters.status);

      const response = await apiClient.get(`/users/admin/list?${params}`);
      return response.data;
    },
    ...CACHE_CONFIG.users,
    placeholderData: (previousData) => previousData,
    retry: 2,
  });
}

/**
 * Fetch a single user by ID (admin view)
 */
export function useAdminUser(userId: string, options?: { enabled?: boolean }) {
  return useQuery<UserListItem>({
    queryKey: adminQueryKeys.userDetail(userId),
    queryFn: async () => {
      const response = await apiClient.get(`/users/admin/${userId}`);
      return response.data;
    },
    ...CACHE_CONFIG.users,
    enabled: options?.enabled !== false && !!userId,
    retry: 2,
  });
}

// =============================================================================
// AUDIT LOGS HOOKS
// =============================================================================

/**
 * Fetch audit logs with filters and pagination
 */
export function useAuditLogs(filters: AuditFilters = {}) {
  const { page = 1, pageSize = 50, ...otherFilters } = filters;

  return useQuery<AuditLogResponse>({
    queryKey: adminQueryKeys.auditLogs(filters),
    queryFn: async () => {
      const params = new URLSearchParams();
      params.set('page', String(page));
      params.set('page_size', String(pageSize));
      if (otherFilters.userId) params.set('user_id', otherFilters.userId);
      if (otherFilters.action) params.set('action', otherFilters.action);
      if (otherFilters.resource) params.set('resource', otherFilters.resource);
      if (otherFilters.startDate) params.set('start_date', otherFilters.startDate);
      if (otherFilters.endDate) params.set('end_date', otherFilters.endDate);

      const response = await apiClient.get(`/audit/logs?${params}`);
      return response.data;
    },
    ...CACHE_CONFIG.audit,
    placeholderData: (previousData) => previousData,
    retry: 2,
    // Auto-refresh every 30 seconds for real-time monitoring
    refetchInterval: 30 * 1000,
    refetchIntervalInBackground: false,
  });
}

// =============================================================================
// ROLES & PERMISSIONS HOOKS
// =============================================================================

/**
 * Fetch all roles with their permissions
 */
export function useRoles(options?: { enabled?: boolean }) {
  return useQuery<RoleWithPermissions[]>({
    queryKey: adminQueryKeys.roles(),
    queryFn: async () => {
      const response = await apiClient.get('/roles');
      return response.data;
    },
    ...CACHE_CONFIG.rolesPermissions,
    enabled: options?.enabled !== false,
    retry: 2,
  });
}

/**
 * Fetch all available permissions
 */
export function usePermissions(options?: { enabled?: boolean }) {
  return useQuery<string[]>({
    queryKey: adminQueryKeys.permissions(),
    queryFn: async () => {
      const response = await apiClient.get('/permissions');
      return response.data;
    },
    ...CACHE_CONFIG.rolesPermissions,
    enabled: options?.enabled !== false,
    retry: 2,
  });
}

// =============================================================================
// MUTATION HOOKS
// =============================================================================

/**
 * Update user status (activate, suspend, etc.)
 */
export function useUpdateUserStatus() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ userId, status }: { userId: string; status: string }) => {
      const response = await apiClient.patch(`/users/admin/${userId}/status`, { status });
      return response.data;
    },
    onSuccess: (_, variables) => {
      // Invalidate user list and specific user
      queryClient.invalidateQueries({ queryKey: adminQueryKeys.users() });
      queryClient.invalidateQueries({ queryKey: adminQueryKeys.userDetail(variables.userId) });
      queryClient.invalidateQueries({ queryKey: adminQueryKeys.stats() });
    },
  });
}

/**
 * Update user role
 */
export function useUpdateUserRole() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ userId, role }: { userId: string; role: string }) => {
      const response = await apiClient.patch(`/users/admin/${userId}/role`, { role });
      return response.data;
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: adminQueryKeys.users() });
      queryClient.invalidateQueries({ queryKey: adminQueryKeys.userDetail(variables.userId) });
    },
  });
}

// =============================================================================
// PREFETCH UTILITIES
// =============================================================================

/**
 * Prefetch admin data for faster navigation
 */
export function usePrefetchAdminData() {
  const queryClient = useQueryClient();

  const prefetchStats = () => {
    queryClient.prefetchQuery({
      queryKey: adminQueryKeys.stats(),
      queryFn: async () => {
        const response = await apiClient.get('/admin/stats');
        return response.data;
      },
      ...CACHE_CONFIG.stats,
    });
  };

  const prefetchUsers = (filters: UserFilters = {}) => {
    queryClient.prefetchQuery({
      queryKey: adminQueryKeys.userList(filters),
      queryFn: async () => {
        const params = new URLSearchParams();
        params.set('page', String(filters.page || 1));
        params.set('page_size', String(filters.pageSize || 20));
        const response = await apiClient.get(`/users/admin/list?${params}`);
        return response.data;
      },
      ...CACHE_CONFIG.users,
    });
  };

  return { prefetchStats, prefetchUsers };
}

// =============================================================================
// CACHE INVALIDATION
// =============================================================================

/**
 * Hook to invalidate admin caches
 */
export function useInvalidateAdminCache() {
  const queryClient = useQueryClient();

  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: adminQueryKeys.all });
  };

  const invalidateStats = () => {
    queryClient.invalidateQueries({ queryKey: adminQueryKeys.stats() });
  };

  const invalidateUsers = () => {
    queryClient.invalidateQueries({ queryKey: adminQueryKeys.users() });
  };

  const invalidateAudit = () => {
    queryClient.invalidateQueries({ queryKey: adminQueryKeys.audit() });
  };

  const invalidateRolesPermissions = () => {
    queryClient.invalidateQueries({ queryKey: adminQueryKeys.roles() });
    queryClient.invalidateQueries({ queryKey: adminQueryKeys.permissions() });
  };

  return {
    invalidateAll,
    invalidateStats,
    invalidateUsers,
    invalidateAudit,
    invalidateRolesPermissions,
  };
}

export default useAdminUsers;
