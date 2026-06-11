/**
 * Profile React Query Hooks
 *
 * useQuery for profile data + useMutation for updates.
 * All mutations invalidate the profile query and sync auth context.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import * as profileApi from './profile-api';
import type { UserUpdateRequest } from '@core/config/types';
import { useAuth } from '@core/hooks/use-auth';

// ---------------------------------------------------------------------------
// Query Keys
// ---------------------------------------------------------------------------

export const PROFILE_QUERY_KEYS = {
  profile: ['profile'] as const,
} as const;

// ---------------------------------------------------------------------------
// Queries
// ---------------------------------------------------------------------------

/**
 * Fetch user profile from backend.
 * staleTime: 2 min — profile rarely changes.
 */
export function useProfile(enabled = true) {
  return useQuery({
    queryKey: PROFILE_QUERY_KEYS.profile,
    queryFn: () => profileApi.getProfile(),
    enabled,
    staleTime: 2 * 60_000,
  });
}

// ---------------------------------------------------------------------------
// Mutations
// ---------------------------------------------------------------------------

/**
 * Update user profile.
 * Invalidates profile cache and syncs auth context on success.
 */
export function useUpdateProfile() {
  const queryClient = useQueryClient();
  const { refreshUser } = useAuth();

  return useMutation({
    mutationFn: (data: UserUpdateRequest) => profileApi.updateProfile(data),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: PROFILE_QUERY_KEYS.profile });
      // Sync auth context (MMKV cache + AuthProvider state)
      await refreshUser();
    },
  });
}

/**
 * Change password via profile route (direct, no 2-step).
 */
export function useChangePassword() {
  return useMutation({
    mutationFn: ({ oldPassword, newPassword }: { oldPassword: string; newPassword: string }) =>
      profileApi.changePassword(oldPassword, newPassword),
  });
}

/**
 * Upload avatar image.
 * Invalidates profile cache and syncs auth context on success.
 */
export function useUploadAvatar() {
  const queryClient = useQueryClient();
  const { refreshUser } = useAuth();

  return useMutation({
    mutationFn: ({
      uri,
      onProgress,
    }: {
      uri: string;
      onProgress?: (progress: number) => void;
    }) => profileApi.uploadAvatar(uri, onProgress),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: PROFILE_QUERY_KEYS.profile });
      await refreshUser();
    },
  });
}

/**
 * Delete avatar.
 * Invalidates profile cache and syncs auth context on success.
 */
export function useDeleteAvatar() {
  const queryClient = useQueryClient();
  const { refreshUser } = useAuth();

  return useMutation({
    mutationFn: () => profileApi.deleteAvatar(),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: PROFILE_QUERY_KEYS.profile });
      await refreshUser();
    },
  });
}
