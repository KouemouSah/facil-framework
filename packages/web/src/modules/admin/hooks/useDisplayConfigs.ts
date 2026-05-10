/**
 * Workflow Display Config Hook
 * React Query hook for CRUD operations on workflow display configurations
 *
 * @module admin/hooks
 * @date 2026-02-01
 *
 * ERROR HANDLING:
 * - All mutations show toast messages on success/error
 * - Console logs for debugging in development
 * - Specific error messages for different failure scenarios
 */

'use client';

import { useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useTranslations } from 'next-intl';
import { toast } from 'sonner';
import { menuConfigApi } from '../services/menuConfigService';
import type {
  DisplayConfig,
  DisplayConfigListResponse,
  DisplayConfigCreateRequest,
  DisplayConfigUpdateRequest,
  PaginationParams,
  AvailableColumn,
  AvailableColumnsResponse,
  AvailableColumnsFilters,
} from '../services/menuConfigService';

// =============================================================================
// LOGGING UTILITY
// =============================================================================

const LOG_PREFIX = '[DisplayConfigs]';

function logInfo(message: string, data?: unknown) {
  if (process.env.NODE_ENV === 'development') {
    console.log(`${LOG_PREFIX} ${message}`, data ?? '');
  }
}

function logError(message: string, error: unknown, context?: Record<string, unknown>) {
  console.error(`${LOG_PREFIX} ERROR: ${message}`, {
    error: error instanceof Error ? error.message : error,
    stack: error instanceof Error ? error.stack : undefined,
    ...context,
  });
}

// =============================================================================
// QUERY KEYS
// =============================================================================

export const displayConfigKeys = {
  all: ['display-configs'] as const,
  lists: () => [...displayConfigKeys.all, 'list'] as const,
  list: (params?: PaginationParams) => [...displayConfigKeys.lists(), params] as const,
  details: () => [...displayConfigKeys.all, 'detail'] as const,
  detail: (id: number) => [...displayConfigKeys.details(), id] as const,
  byWorkflow: (code: string) => [...displayConfigKeys.all, 'by-workflow', code] as const,
  availableColumns: (pattern: string, filters?: AvailableColumnsFilters) =>
    [...displayConfigKeys.all, 'available-columns', pattern, filters] as const,
};

// =============================================================================
// HOOKS
// =============================================================================

/**
 * Hook to fetch paginated list of display configs
 */
export function useDisplayConfigs(params?: PaginationParams) {
  return useQuery<DisplayConfigListResponse, Error>({
    queryKey: displayConfigKeys.list(params),
    queryFn: async () => {
      logInfo('Fetching display configs', params);
      try {
        const result = await menuConfigApi.listDisplayConfigs(params);
        logInfo(`Fetched ${result.items.length} configs (total: ${result.total})`);
        return result;
      } catch (error) {
        logError('Failed to fetch display configs', error, { params });
        throw error;
      }
    },
    staleTime: 5 * 60 * 1000, // 5 min — config list changes on admin CRUD
  });
}

/**
 * Hook to fetch a single display config by ID
 */
export function useDisplayConfig(id: number, enabled = true) {
  return useQuery<DisplayConfig, Error>({
    queryKey: displayConfigKeys.detail(id),
    queryFn: async () => {
      logInfo(`Fetching display config id=${id}`);
      try {
        const result = await menuConfigApi.getDisplayConfig(id);
        logInfo(`Fetched config: ${result.workflow_code}`);
        return result;
      } catch (error) {
        logError(`Failed to fetch display config id=${id}`, error);
        throw error;
      }
    },
    enabled: enabled && id > 0,
    staleTime: 5 * 60 * 1000, // 5 min — same as list; admin edits invalidate via queryClient
  });
}

/**
 * Hook to fetch display config for a specific workflow code
 */
export function useDisplayConfigForWorkflow(workflowCode: string, enabled = true) {
  return useQuery<DisplayConfig, Error>({
    queryKey: displayConfigKeys.byWorkflow(workflowCode),
    queryFn: async () => {
      logInfo(`Fetching display config for workflow=${workflowCode}`);
      try {
        const result = await menuConfigApi.getDisplayConfigForWorkflow(workflowCode);
        logInfo(`Found config: ${result.workflow_code}`);
        return result;
      } catch (error) {
        logError(`No display config found for workflow=${workflowCode}`, error);
        throw error;
      }
    },
    enabled: enabled && !!workflowCode,
    staleTime: 5 * 60 * 1000, // 5 min — consistent with list/detail TTL
    retry: false, // Don't retry on 404
  });
}

/**
 * Hook for creating a new display config
 */
export function useCreateDisplayConfig() {
  const queryClient = useQueryClient();
  const t = useTranslations('admin.menuConfig.displayConfig');

  return useMutation<DisplayConfig, Error, DisplayConfigCreateRequest>({
    mutationFn: async (data) => {
      logInfo('Creating display config', { workflowCode: data.workflow_code });
      return menuConfigApi.createDisplayConfig(data);
    },
    onSuccess: (result) => {
      logInfo(`Config created successfully: id=${result.id}, workflowCode=${result.workflow_code}`);
      queryClient.invalidateQueries({ queryKey: displayConfigKeys.lists() });
      toast.success(t('messages.created'));
    },
    onError: (error, variables) => {
      logError('Failed to create display config', error, {
        workflowCode: variables.workflow_code,
        data: variables,
      });
      toast.error(t('messages.createError'), {
        description: error.message,
      });
    },
  });
}

/**
 * Hook for updating an existing display config
 */
export function useUpdateDisplayConfig() {
  const queryClient = useQueryClient();
  const t = useTranslations('admin.menuConfig.displayConfig');

  return useMutation<
    DisplayConfig,
    Error,
    { id: number; data: DisplayConfigUpdateRequest }
  >({
    mutationFn: async ({ id, data }) => {
      logInfo(`Updating display config id=${id}`, data);
      return menuConfigApi.updateDisplayConfig(id, data);
    },
    onSuccess: (result, variables) => {
      logInfo(`Config updated successfully: id=${variables.id}`, result);
      queryClient.invalidateQueries({
        queryKey: displayConfigKeys.detail(variables.id),
      });
      queryClient.invalidateQueries({ queryKey: displayConfigKeys.lists() });
      // Invalidate byWorkflow so agent previews pick up changes immediately
      if (result.workflow_code) {
        queryClient.invalidateQueries({
          queryKey: displayConfigKeys.byWorkflow(result.workflow_code),
        });
      }
      toast.success(t('messages.updated'));
    },
    onError: (error, variables) => {
      logError(`Failed to update display config id=${variables.id}`, error, {
        data: variables.data,
      });
      toast.error(t('messages.updateError'), {
        description: error.message,
      });
    },
  });
}

/**
 * Hook for deleting a display config
 */
export function useDeleteDisplayConfig() {
  const queryClient = useQueryClient();
  const t = useTranslations('admin.menuConfig.displayConfig');

  return useMutation<void, Error, { id: number; workflowCode?: string }>({
    mutationFn: async ({ id }) => {
      logInfo(`Deleting display config id=${id}`);
      return menuConfigApi.deleteDisplayConfig(id);
    },
    onSuccess: (_, { id, workflowCode }) => {
      logInfo(`Config deleted successfully: id=${id}`);
      queryClient.removeQueries({ queryKey: displayConfigKeys.detail(id) });
      queryClient.invalidateQueries({ queryKey: displayConfigKeys.lists() });
      // Invalidate byWorkflow cache
      if (workflowCode) {
        queryClient.invalidateQueries({
          queryKey: displayConfigKeys.byWorkflow(workflowCode),
        });
      }
      toast.success(t('messages.deleted'));
    },
    onError: (error, id) => {
      logError(`Failed to delete display config id=${id}`, error);
      toast.error(t('messages.deleteError'), {
        description: error.message,
      });
    },
  });
}

/**
 * Hook to discover available columns for a workflow code
 * Dynamically introspects form_data from actual DB records
 * Supports sub-workflow filtering (is_minor, solicitud_type, motivo)
 */
export function useAvailableColumns(
  workflowCode: string,
  filters?: AvailableColumnsFilters,
  enabled = true,
) {
  return useQuery<AvailableColumnsResponse, Error>({
    queryKey: displayConfigKeys.availableColumns(workflowCode, filters),
    queryFn: async () => {
      logInfo(`Discovering columns for code=${workflowCode}`, filters);
      try {
        const result = await menuConfigApi.getAvailableColumns(
          workflowCode,
          filters,
        );
        logInfo(
          `Found ${result.system_columns.length} system + ${result.extracted_columns.length} extracted columns`
        );
        return result;
      } catch (error) {
        logError(`Failed to discover columns for ${workflowCode}`, error);
        throw error;
      }
    },
    enabled: enabled && !!workflowCode,
    staleTime: 10 * 60 * 1000, // 10 minutes - column discovery is expensive
  });
}

/**
 * Hook to get all available columns (system + extracted) as a flat list
 * Useful for column selector components
 * Supports sub-workflow filtering (is_minor, solicitud_type, motivo)
 */
const EMPTY_COLUMNS: AvailableColumn[] = [];
const EMPTY_STRINGS: string[] = [];

export function useAllAvailableColumns(
  workflowCode: string,
  filters?: AvailableColumnsFilters,
  enabled = true,
) {
  const { data, isLoading, isError, error } = useAvailableColumns(
    workflowCode,
    filters,
    enabled,
  );

  // Stable references: use module-level constants when data is absent
  // to prevent infinite re-render loops in downstream useMemo/useEffect chains
  const systemColumns = data?.system_columns ?? EMPTY_COLUMNS;
  const extractedColumns = data?.extracted_columns ?? EMPTY_COLUMNS;
  const suggestedColumns = data?.suggested_columns ?? EMPTY_STRINGS;
  const allColumns = useMemo<AvailableColumn[]>(
    () => data ? [...data.system_columns, ...data.extracted_columns] : EMPTY_COLUMNS,
    [data]
  );

  return {
    columns: allColumns,
    systemColumns,
    extractedColumns,
    suggestedColumns,
    availableFilters: data?.available_filters ?? null,
    filtersApplied: data?.filters_applied ?? null,
    totalRequests: data?.total_requests ?? 0,
    documentCount: data?.document_count ?? 0,
    isLoading,
    isError,
    error,
  };
}

// =============================================================================
// COMBINED HOOK
// =============================================================================

/**
 * Combined hook for all display config operations
 * Provides a convenient interface for components
 */
export function useDisplayConfigOperations(params?: PaginationParams) {
  const configsQuery = useDisplayConfigs(params);
  const createMutation = useCreateDisplayConfig();
  const updateMutation = useUpdateDisplayConfig();
  const deleteMutation = useDeleteDisplayConfig();

  return {
    // Query data
    configs: configsQuery.data?.items ?? [],
    total: configsQuery.data?.total ?? 0,
    pages: configsQuery.data?.pages ?? 1,
    isLoading: configsQuery.isLoading,
    isError: configsQuery.isError,
    error: configsQuery.error,
    refetch: configsQuery.refetch,

    // Mutations
    createConfig: createMutation.mutate,
    createConfigAsync: createMutation.mutateAsync,
    isCreating: createMutation.isPending,

    updateConfig: (id: number, data: DisplayConfigUpdateRequest) =>
      updateMutation.mutate({ id, data }),
    updateConfigAsync: (id: number, data: DisplayConfigUpdateRequest) =>
      updateMutation.mutateAsync({ id, data }),
    isUpdating: updateMutation.isPending,

    deleteConfig: (id: number, workflowCode?: string) =>
      deleteMutation.mutate({ id, workflowCode }),
    deleteConfigAsync: (id: number, workflowCode?: string) =>
      deleteMutation.mutateAsync({ id, workflowCode }),
    isDeleting: deleteMutation.isPending,

    // Combined loading state
    isMutating:
      createMutation.isPending ||
      updateMutation.isPending ||
      deleteMutation.isPending,
  };
}

// =============================================================================
// AVAILABLE COLUMNS AND SECTIONS
// =============================================================================

/**
 * @deprecated Use useAvailableColumns() hook instead for dynamic column discovery
 *
 * FALLBACK system columns - used only when dynamic discovery fails
 * The actual columns are now discovered dynamically from service_requests.form_data
 */
export const FALLBACK_SYSTEM_COLUMNS = [
  { id: 'reference', label: 'Reference', description: 'Request reference number' },
  { id: 'fullName', label: 'Full Name', description: 'Applicant full name' },
  { id: 'solicitudType', label: 'Request Type', description: 'Type of request' },
  { id: 'createdAt', label: 'Created At', description: 'Submission date' },
  { id: 'priority', label: 'Priority', description: 'Request priority level' },
  { id: 'status', label: 'Status', description: 'Current status' },
  { id: 'totalAmount', label: 'Total Amount', description: 'Total amount to pay' },
  { id: 'paymentStatus', label: 'Payment Status', description: 'Payment workflow status' },
  { id: 'assignedAgent', label: 'Assigned Agent', description: 'Assigned agent name' },
] as const;

/**
 * Available sections for preview panel
 */
export const AVAILABLE_SECTIONS = [
  { id: 'info', label: 'General Info', description: 'Basic request information' },
  { id: 'extractedData', label: 'Extracted Data', description: 'OCR extracted data' },
  { id: 'documents', label: 'Documents', description: 'Attached documents' },
  { id: 'contact', label: 'Contact', description: 'Contact information' },
  { id: 'appointment', label: 'Appointment', description: 'Appointment details' },
  { id: 'paymentDetails', label: 'Payment Details', description: 'Payment information' },
  { id: 'timeline', label: 'Timeline', description: 'Request timeline' },
  { id: 'history', label: 'History', description: 'Action history' },
] as const;
