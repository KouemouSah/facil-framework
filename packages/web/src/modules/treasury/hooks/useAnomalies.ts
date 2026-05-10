/**
 * Hooks for treasury anomalies management (Phase 2A)
 *
 * @module treasury/hooks
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { treasuryApi } from '../services/api';
import type {
  AnomalyParams,
  AnomalyListResponse,
  Anomaly,
  AnomalyCreateRequest,
  AnomalyStatusUpdateRequest,
  AnomalyAction,
} from '../types';

export const ANOMALIES_QUERY_KEY = 'treasury-anomalies';
export const ANOMALY_DETAIL_QUERY_KEY = 'treasury-anomaly-detail';
export const ANOMALY_ACTIONS_QUERY_KEY = 'treasury-anomaly-actions';

/**
 * Fetch anomalies list with filters
 */
export function useAnomalies(params: AnomalyParams = {}) {
  return useQuery<AnomalyListResponse, Error>({
    queryKey: [ANOMALIES_QUERY_KEY, params],
    queryFn: () => treasuryApi.getAnomalies(params),
    staleTime: 60 * 1000, // 1 minute
    retry: 2,
  });
}

/**
 * Fetch single anomaly details
 */
export function useAnomaly(anomalyId: string | undefined) {
  return useQuery<Anomaly, Error>({
    queryKey: [ANOMALY_DETAIL_QUERY_KEY, anomalyId],
    queryFn: () => treasuryApi.getAnomaly(anomalyId!),
    enabled: !!anomalyId,
    staleTime: 30 * 1000, // 30 seconds
    retry: 2,
  });
}

/**
 * Fetch anomaly action history
 */
export function useAnomalyActions(anomalyId: string | undefined) {
  return useQuery<AnomalyAction[], Error>({
    queryKey: [ANOMALY_ACTIONS_QUERY_KEY, anomalyId],
    queryFn: () => treasuryApi.getAnomalyActions(anomalyId!),
    enabled: !!anomalyId,
    staleTime: 30 * 1000,
    retry: 2,
  });
}

/**
 * Create a manual anomaly
 */
export function useCreateAnomaly() {
  const queryClient = useQueryClient();

  return useMutation<Anomaly, Error, AnomalyCreateRequest>({
    mutationFn: (request) => treasuryApi.createAnomaly(request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [ANOMALIES_QUERY_KEY] });
    },
  });
}

/**
 * Update anomaly status
 */
export function useUpdateAnomalyStatus() {
  const queryClient = useQueryClient();

  return useMutation<
    Anomaly,
    Error,
    { anomalyId: string; request: AnomalyStatusUpdateRequest }
  >({
    mutationFn: ({ anomalyId, request }) =>
      treasuryApi.updateAnomalyStatus(anomalyId, request),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: [ANOMALIES_QUERY_KEY] });
      queryClient.invalidateQueries({
        queryKey: [ANOMALY_DETAIL_QUERY_KEY, variables.anomalyId],
      });
      queryClient.invalidateQueries({
        queryKey: [ANOMALY_ACTIONS_QUERY_KEY, variables.anomalyId],
      });
    },
  });
}

/**
 * Add comment to anomaly
 */
export function useAddAnomalyComment() {
  const queryClient = useQueryClient();

  return useMutation<AnomalyAction, Error, { anomalyId: string; comment: string }>({
    mutationFn: ({ anomalyId, comment }) =>
      treasuryApi.addAnomalyComment(anomalyId, comment),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: [ANOMALY_ACTIONS_QUERY_KEY, variables.anomalyId],
      });
    },
  });
}

/**
 * Run automatic anomaly detection
 */
export function useRunAnomalyDetection() {
  const queryClient = useQueryClient();

  return useMutation<
    { detectedAt: string; anomaliesFound: number; byType: Record<string, unknown> },
    Error,
    string[] | undefined
  >({
    mutationFn: (detectionTypes) => treasuryApi.runAnomalyDetection(detectionTypes),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [ANOMALIES_QUERY_KEY] });
    },
  });
}

export default useAnomalies;
