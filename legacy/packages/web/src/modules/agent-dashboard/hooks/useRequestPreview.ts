/**
 * useRequestPreview Hook
 * Fetches service request preview for split view
 *
 * @module agent-dashboard/hooks/useRequestPreview
 * @date 2026-01-26
 */

import { useQuery } from '@tanstack/react-query';
import { agentRequestsApi, ServiceRequestPreview } from '../services/agent-requests-api';

interface UseRequestPreviewOptions {
  listIndex?: number;
  listTotal?: number;
  enabled?: boolean;
}

export function useRequestPreview(
  entityCode: string,
  requestId: string | null,
  options: UseRequestPreviewOptions = {}
) {
  const { listIndex, listTotal, enabled = true } = options;

  return useQuery<ServiceRequestPreview, Error>({
    queryKey: ['request-preview', entityCode, requestId, listIndex],
    queryFn: async () => {
      if (!requestId) throw new Error('No request ID');
      return agentRequestsApi.getPreview(entityCode, requestId, { listIndex, listTotal });
    },
    enabled: enabled && !!requestId && !!entityCode,
    staleTime: 30 * 1000, // 30 seconds
    gcTime: 5 * 60 * 1000, // 5 minutes
  });
}

export type { ServiceRequestPreview };
