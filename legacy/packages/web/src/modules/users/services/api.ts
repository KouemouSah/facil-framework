/**
 * Users Profile API Service
 * Handles user profile self-service operations
 *
 * @module users/services
 * @author Claude Code
 * @date 2025-11-26
 *
 * BACKEND ALIGNMENT:
 * Routes: /api/v1/users (from app/modules/users/api/user_routes.py)
 * - GET    /api/v1/users/profile              → get_profile
 * - PUT    /api/v1/users/profile              → update_profile
 * - POST   /api/v1/users/profile/change-password → change_password
 * - POST   /api/v1/users/profile/avatar       → upload_avatar
 * - DELETE /api/v1/users/profile/avatar       → delete_avatar
 *
 * NOTE: This is for USER SELF-SERVICE only
 * Admin user management is in users-admin module
 */

import { fetchClient } from '@/core/api';
import type {
  UserResponse,
  ProfileUpdateRequest,
  PasswordChangeRequest,
} from '../types';

// =============================================================================
// CONFIGURATION
// =============================================================================

const USERS_BASE = '/users';

// =============================================================================
// PROFILE API
// =============================================================================

export const profileApi = {
  /**
   * Get current user profile
   * BACKEND: GET /api/v1/users/profile
   * ROUTE: get_profile() in user_routes.py
   */
  getProfile: async (): Promise<UserResponse> => {
    return fetchClient.get<UserResponse>(`${USERS_BASE}/profile`);
  },

  /**
   * Update current user profile
   * BACKEND: PUT /api/v1/users/profile
   * ROUTE: update_profile() in user_routes.py
   *
   * VALIDATIONS:
   * - Email format RFC 5322, uniqueness check (409 Conflict if duplicate)
   * - Phone format E.164: +240XXXXXXXXX
   * - Users CANNOT modify their own status (admin only)
   */
  updateProfile: async (data: ProfileUpdateRequest): Promise<UserResponse> => {
    return fetchClient.put<UserResponse>(`${USERS_BASE}/profile`, data);
  },

  /**
   * Change password
   * BACKEND: POST /api/v1/users/profile/change-password
   * ROUTE: change_password() in user_routes.py
   *
   * VALIDATIONS:
   * - Old password must match
   * - New password must be different from old
   * - Minimum 8 characters
   */
  changePassword: async (data: PasswordChangeRequest): Promise<{ message: string }> => {
    return fetchClient.post<{ message: string }>(`${USERS_BASE}/profile/change-password`, data);
  },

  /**
   * Upload avatar
   * BACKEND: POST /api/v1/users/profile/avatar
   * ROUTE: upload_avatar() in user_routes.py
   *
   * VALIDATIONS:
   * - Allowed types: image/jpeg, image/jpg, image/png, image/gif
   * - Max size: 5MB
   */
  uploadAvatar: async (file: File): Promise<UserResponse> => {
    const formData = new FormData();
    formData.append('file', file);

    // Use fetch directly for multipart/form-data
    const response = await fetch(`${fetchClient.getBaseUrl()}${USERS_BASE}/profile/avatar`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${fetchClient.getAuthToken()}`,
      },
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || 'Avatar upload failed');
    }

    return response.json();
  },

  /**
   * Delete avatar
   * BACKEND: DELETE /api/v1/users/profile/avatar
   * ROUTE: delete_avatar() in user_routes.py
   */
  deleteAvatar: async (): Promise<UserResponse> => {
    return fetchClient.delete<UserResponse>(`${USERS_BASE}/profile/avatar`);
  },
};

// =============================================================================
// EXPORTS
// =============================================================================

export default profileApi;
