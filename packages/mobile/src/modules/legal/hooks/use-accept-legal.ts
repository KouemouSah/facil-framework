/**
 * useAcceptLegal — mutation hook for POST /api/v1/legal/accept.
 *
 * Used by the mobile post-login modal when an existing user (NULL or
 * "1.0.0-legacy" persisted versions) needs to ratify the current versions.
 *
 * On success, invalidates the user-profile query so the UI reflects the
 * fresh `terms_accepted_at` / `privacy_accepted_at` timestamps.
 *
 * On 400 (stale version) — usually means the mobile app is out of date and
 * should refetch /legal/versions. The hook does NOT auto-retry: the caller
 * should show a "Please update the app" dialog.
 */

import { useMutation, useQueryClient } from '@tanstack/react-query';

import apiClient from '@core/api/client';
import { API_ENDPOINTS } from '@core/api/endpoints';

import type { LegalAcceptPayload, LegalAcceptResponse } from '../types';

export function useAcceptLegal() {
  const qc = useQueryClient();
  return useMutation<LegalAcceptResponse, unknown, LegalAcceptPayload>({
    mutationFn: async (payload) => {
      const { data } = await apiClient.post<LegalAcceptResponse>(
        API_ENDPOINTS.legal.accept,
        payload,
      );
      return data;
    },
    onSuccess: () => {
      // Refresh the user profile so terms_accepted_at + privacy_accepted_at
      // reflect the new state (and the post-login modal stays dismissed).
      qc.invalidateQueries({ queryKey: ['users', 'profile'] });
      qc.invalidateQueries({ queryKey: ['auth', 'profile'] });
    },
  });
}
