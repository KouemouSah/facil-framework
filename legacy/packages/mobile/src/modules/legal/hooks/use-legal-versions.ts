/**
 * useLegalVersions — fetches current Privacy/Terms/Cookies versions.
 *
 * Used by:
 *  - The sign-up screen (so the POST /auth/register payload includes the
 *    exact versions the user just saw and accepted).
 *  - The post-login mobile modal (to know if the user's stored version is
 *    stale and a re-acceptance prompt is needed).
 *
 * Caching: 1h staleTime — versions change rarely (legal review cycle). On
 * cache miss the request goes to a public endpoint, no auth needed.
 */

import { useQuery } from '@tanstack/react-query';

import apiClient from '@core/api/client';
import { API_ENDPOINTS } from '@core/api/endpoints';

import type { LegalVersionsResponse } from '../types';

const QUERY_KEY = ['legal', 'versions'] as const;

export function useLegalVersions() {
  return useQuery<LegalVersionsResponse>({
    queryKey: QUERY_KEY,
    queryFn: async () => {
      const { data } = await apiClient.get<LegalVersionsResponse>(API_ENDPOINTS.legal.versions);
      return data;
    },
    // Versions change ~ once per legal review cycle (months/years). 1h is
    // generous but ensures the user gets a fresh prompt within a session
    // when admin bumps the version.
    staleTime: 1000 * 60 * 60,
    gcTime: 1000 * 60 * 60 * 24,
  });
}

useLegalVersions.queryKey = QUERY_KEY;
