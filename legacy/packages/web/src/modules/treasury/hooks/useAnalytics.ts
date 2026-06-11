/**
 * Treasury Analytics Hooks (Phase 5)
 * Hooks for analytics dashboard - Report and Explore tabs
 */

import { useQuery } from '@tanstack/react-query';
import { treasuryApi } from '../services/api';
import type {
  StatisticsResponse,
  CorrelationMatrix,
  TrendsResponse,
  AnomaliesResponse,
  PredictionsResponse,
  AnalyticsReport,
  ExploreResponse,
  AnalyticsParams,
  ReportParams,
  PredictionParams,
  ExploreParams,
} from '../types/analytics';

// =============================================================================
// QUERY KEYS
// =============================================================================

export const ANALYTICS_QUERY_KEYS = {
  statistics: 'treasury-analytics-statistics',
  correlations: 'treasury-analytics-correlations',
  trends: 'treasury-analytics-trends',
  anomalies: 'treasury-analytics-anomalies',
  predictions: 'treasury-analytics-predictions',
  report: 'treasury-analytics-report',
  explore: 'treasury-analytics-explore',
};

// =============================================================================
// REPORT TAB HOOKS (Fixed Variables)
// =============================================================================

/**
 * Hook for fetching complete analytics report
 * Used in Report tab - automatic analysis with fixed variables
 */
export function useAnalyticsReport(params: ReportParams = { period: 'month', language: 'es' }) {
  return useQuery<AnalyticsReport, Error>({
    queryKey: [ANALYTICS_QUERY_KEYS.report, params],
    queryFn: () => treasuryApi.getAnalyticsReport(params),
    staleTime: 5 * 60 * 1000, // 5 minutes
    refetchInterval: false, // Manual refresh only for reports
  });
}

/**
 * Hook for fetching descriptive statistics
 */
export function useStatistics(params: AnalyticsParams = { period: 'month' }) {
  return useQuery<StatisticsResponse, Error>({
    queryKey: [ANALYTICS_QUERY_KEYS.statistics, params],
    queryFn: () => treasuryApi.getStatistics(params),
    staleTime: 5 * 60 * 1000,
  });
}

/**
 * Hook for fetching correlation matrix
 */
export function useCorrelations(params: AnalyticsParams = { period: 'month' }) {
  return useQuery<CorrelationMatrix, Error>({
    queryKey: [ANALYTICS_QUERY_KEYS.correlations, params],
    queryFn: () => treasuryApi.getCorrelations(params),
    staleTime: 5 * 60 * 1000,
  });
}

/**
 * Hook for fetching trend analysis
 */
export function useTrends(params: AnalyticsParams = { period: 'month' }) {
  return useQuery<TrendsResponse, Error>({
    queryKey: [ANALYTICS_QUERY_KEYS.trends, params],
    queryFn: () => treasuryApi.getTrends(params),
    staleTime: 5 * 60 * 1000,
  });
}

/**
 * Hook for fetching detected anomalies
 */
export function useAnalyticsAnomalies(params: AnalyticsParams = { period: 'month' }) {
  return useQuery<AnomaliesResponse, Error>({
    queryKey: [ANALYTICS_QUERY_KEYS.anomalies, params],
    queryFn: () => treasuryApi.getAnalyticsAnomalies(params),
    staleTime: 5 * 60 * 1000,
  });
}

/**
 * Hook for fetching predictions
 */
export function usePredictions(params: PredictionParams = { period: 'month', horizonDays: 7 }) {
  return useQuery<PredictionsResponse, Error>({
    queryKey: [ANALYTICS_QUERY_KEYS.predictions, params],
    queryFn: () => treasuryApi.getPredictions(params),
    staleTime: 5 * 60 * 1000,
  });
}

// =============================================================================
// EXPLORE TAB HOOKS (Custom Variable Selection)
// =============================================================================

/**
 * Hook for exploring custom variable analysis
 * Used in Explore tab - user selects variables via dropdowns
 */
export function useExploreAnalytics(
  params: ExploreParams,
  options?: { enabled?: boolean }
) {
  return useQuery<ExploreResponse, Error>({
    queryKey: [ANALYTICS_QUERY_KEYS.explore, params],
    queryFn: () => treasuryApi.exploreAnalytics(params),
    staleTime: 5 * 60 * 1000,
    enabled: options?.enabled !== false && !!params.primaryVariable,
  });
}
