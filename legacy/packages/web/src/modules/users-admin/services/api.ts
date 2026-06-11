/**
 * Users Admin API Service
 * Handles all API calls to the backend admin users endpoints
 *
 * @module users-admin/services
 * @author Claude Code
 * @date 2025-11-25
 *
 * BACKEND ALIGNMENT: Phase 6
 * Routes: /api/v1/admin/users (from app/modules/admin/api/user_management_routes.py)
 * - GET    /api/v1/admin/users              → list_users (paginated)
 * - POST   /api/v1/admin/users              → create_user
 * - GET    /api/v1/admin/users/{user_id}    → get_user
 * - PUT    /api/v1/admin/users/{user_id}    → update_user (partial updates supported)
 * - DELETE /api/v1/admin/users/{user_id}    → delete_user
 * - GET    /api/v1/admin/users/search       → search_users
 * - GET    /api/v1/admin/users/stats        → get_user_stats
 * - GET    /api/v1/admin/users/{user_id}/activities → get_user_activities
 */

import { fetchClient } from '@/core/api'
import type {
  User,
  CreateUserRequest,
  UpdateUserRequest,
  PaginatedUsersResponse,
  UserRole,
} from "../types";

// =============================================================================
// RESPONSE TRANSFORMATION
// =============================================================================

/**
 * Backend returns status (string enum), frontend expects is_active (boolean)
 * This function transforms the backend response to match frontend expectations
 */
function transformUserResponse(backendUser: any): User {
  return {
    id: backendUser.id,
    email: backendUser.email,
    first_name: backendUser.first_name,
    last_name: backendUser.last_name,
    role: backendUser.role,
    // Transform status to is_active boolean
    is_active: backendUser.status === 'active' || backendUser.is_active === true,
    two_factor_enabled: backendUser.two_factor_enabled ?? false,
    created_at: backendUser.created_at,
    updated_at: backendUser.updated_at,
    last_login: backendUser.last_login,
  };
}

// =============================================================================
// CONFIGURATION
// =============================================================================

const ADMIN_USERS_BASE = "/admin/users"; // Admin-only users endpoints

// =============================================================================
// USERS API
// =============================================================================

export const usersApi = {
  /**
   * Get all users with optional filters and pagination
   * BACKEND: GET /api/v1/admin/users
   * ROUTE: list_users() in user_management_routes.py:62
   * RESPONSE: UserListResponse with pagination metadata
   */
  getAll: async (params?: {
    role?: UserRole;
    roles?: string;
    status?: string;
    search?: string;
    page?: number;
    size?: number;
  }): Promise<{ items: User[]; total: number; page: number; page_size: number; pages: number }> => {
    const response = await fetchClient.get<PaginatedUsersResponse>(ADMIN_USERS_BASE, {
      page: params?.page || 1,
      size: params?.size || 20,
      role: params?.role,
      roles: params?.roles,
      status: params?.status,
      search: params?.search,
    });

    return {
      items: (response.items || []).map(transformUserResponse),
      total: response.total || 0,
      page: response.page || 1,
      page_size: response.page_size || 20,
      pages: Math.ceil((response.total || 0) / (response.page_size || 20)) || 1,
    };
  },

  /**
   * Get user by ID
   * BACKEND: GET /api/v1/admin/users/{user_id}
   * ROUTE: get_user() in user_management_routes.py:177
   */
  getById: async (id: string): Promise<User> => {
    const response = await fetchClient.get<any>(`${ADMIN_USERS_BASE}/${id}`);
    return transformUserResponse(response);
  },

  /**
   * Create new user
   * BACKEND: POST /api/v1/admin/users
   * ROUTE: create_user() in user_management_routes.py:125
   *
   * CRITICAL: Backend expects nested profile object with first_name/last_name
   * Backend hashes password automatically using PasswordService
   * Frontend sends plain password, backend handles bcrypt hashing
   */
  create: async (data: CreateUserRequest): Promise<User> => {
    // Transform frontend flat structure to backend nested profile structure
    const backendPayload = {
      email: data.email,
      password: data.password,
      role: data.role,
      profile: {
        first_name: data.first_name,
        last_name: data.last_name,
        language: 'es', // Default language
      },
    };
    const response = await fetchClient.post<any>(ADMIN_USERS_BASE, backendPayload);
    return transformUserResponse(response);
  },

  /**
   * Update user (supports partial updates)
   * BACKEND: PUT /api/v1/admin/users/{user_id}
   * ROUTE: update_user() in user_management_routes.py:230
   *
   * CRITICAL:
   * - Backend supports partial updates (exclude_unset=True)
   * - Only sends non-null fields
   * - Email uniqueness check done backend-side
   * - Password hashing done backend-side if password provided
   */
  update: async (id: string, data: UpdateUserRequest): Promise<User> => {
    const response = await fetchClient.put<any>(`${ADMIN_USERS_BASE}/${id}`, data);
    return transformUserResponse(response);
  },

  /**
   * Delete user (hard delete for professionals, soft delete for citizen/business handled by UI)
   * BACKEND: DELETE /api/v1/admin/users/{user_id}
   * ROUTE: delete_user() in user_management_routes.py:323
   *
   * CRITICAL:
   * - Backend prevents deletion of admin users (400 error)
   * - Returns: { message: "User deleted successfully" }
   */
  delete: async (id: string): Promise<void> => {
    await fetchClient.delete<{ message: string }>(`${ADMIN_USERS_BASE}/${id}`);
  },

  /**
   * Activate/Deactivate user (soft delete for citizen/business)
   * Uses the same PUT endpoint for partial update
   * BACKEND: PUT /api/v1/admin/users/{user_id}
   *
   * NOTE: This is a convenience method that uses update() internally
   * Backend expects 'status' field, not 'is_active'
   */
  setActive: async (id: string, is_active: boolean): Promise<User> => {
    // Backend expects status enum, not is_active boolean
    const status = is_active ? 'active' : 'inactive';
    const response = await fetchClient.put<any>(`${ADMIN_USERS_BASE}/${id}`, { status });
    return transformUserResponse(response);
  },

  /**
   * Search users
   * BACKEND: GET /api/v1/admin/users/search
   * ROUTE: search_users() in user_management_routes.py:375
   */
  search: async (params?: {
    q?: string;
    role?: UserRole;
    status?: string;
    country?: string;
    limit?: number;
  }): Promise<User[]> => {
    const response = await fetchClient.get<any[]>(`${ADMIN_USERS_BASE}/search`, {
      q: params?.q,
      role: params?.role,
      status: params?.status,
      country: params?.country,
      limit: params?.limit,
    });
    return (response || []).map(transformUserResponse);
  },

  /**
   * Get user statistics
   * BACKEND: GET /api/v1/admin/users/stats
   * ROUTE: get_user_stats() in user_management_routes.py:423
   *
   * Backend returns: total_users, active_users, new_users_this_month, users_by_role, users_by_status
   */
  getStats: async (): Promise<{
    total_users: number;
    active_users: number;
    new_users_this_month: number;
    users_by_role: Record<string, number>;
    users_by_status: Record<string, number>;
    users_by_city?: Record<string, number>;
  }> => {
    return fetchClient.get(`${ADMIN_USERS_BASE}/stats`);
  },

  /**
   * Get user activity history
   * BACKEND: GET /api/v1/admin/users/{user_id}/activities
   * ROUTE: get_user_activities() in user_management_routes.py:451
   */
  getActivities: async (userId: string, limit: number = 50): Promise<Array<{
    id: string;
    user_id: string;
    action: string;
    resource: string;
    metadata?: Record<string, unknown>;
    timestamp: string;
  }>> => {
    return fetchClient.get(`${ADMIN_USERS_BASE}/${userId}/activities`, { limit });
  },
};

// =============================================================================
// EXPORTS
// =============================================================================

export default usersApi;
