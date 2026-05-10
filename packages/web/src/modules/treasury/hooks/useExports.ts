/**
 * Hooks for treasury exports management (Phase 2B)
 *
 * @module treasury/hooks
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { treasuryApi } from '../services/api';
import type {
  ExportParams,
  ExportListResponse,
  TreasuryExport,
  ExportCreateRequest,
  ExportTemplate,
  ExportDownloadResponse,
} from '../types';

export const EXPORTS_QUERY_KEY = 'treasury-exports';
export const EXPORT_DETAIL_QUERY_KEY = 'treasury-export-detail';
export const EXPORT_TEMPLATES_QUERY_KEY = 'treasury-export-templates';

/**
 * Fetch exports list with filters
 */
export function useExports(params: ExportParams = {}) {
  return useQuery<ExportListResponse, Error>({
    queryKey: [EXPORTS_QUERY_KEY, params],
    queryFn: () => treasuryApi.getExports(params),
    staleTime: 60 * 1000, // 1 minute
    retry: 2,
  });
}

/**
 * Fetch single export details
 */
export function useExport(exportId: string | undefined) {
  return useQuery<TreasuryExport, Error>({
    queryKey: [EXPORT_DETAIL_QUERY_KEY, exportId],
    queryFn: () => treasuryApi.getExport(exportId!),
    enabled: !!exportId,
    staleTime: 30 * 1000, // 30 seconds
    retry: 2,
    // Refetch more frequently if export is pending/processing
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data && (data.status === 'pending' || data.status === 'processing')) {
        return 5000; // 5 seconds
      }
      return false;
    },
  });
}

/**
 * Fetch export templates
 */
export function useExportTemplates(exportType?: string) {
  return useQuery<ExportTemplate[], Error>({
    queryKey: [EXPORT_TEMPLATES_QUERY_KEY, exportType],
    queryFn: () => treasuryApi.getExportTemplates(exportType),
    staleTime: 5 * 60 * 1000, // 5 minutes
    retry: 2,
  });
}

/**
 * Generate a new export
 */
export function useGenerateExport() {
  const queryClient = useQueryClient();

  return useMutation<TreasuryExport, Error, ExportCreateRequest>({
    mutationFn: (request) => treasuryApi.generateExport(request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [EXPORTS_QUERY_KEY] });
    },
  });
}

/**
 * Download export file
 */
export function useDownloadExport() {
  return useMutation<ExportDownloadResponse, Error, string>({
    mutationFn: (exportId) => treasuryApi.downloadExport(exportId),
  });
}

export default useExports;
