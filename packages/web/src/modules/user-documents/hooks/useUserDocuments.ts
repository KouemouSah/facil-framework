/**
 * useUserDocuments - React hooks for listing and managing user documents
 *
 * Uses TanStack React Query v5 for server state management with:
 * - Cursor-based infinite scrolling for the document list
 * - Optimistic query invalidation on mutations
 * - Structured query key factory for cache management
 *
 * @module user-documents/hooks
 * @date 2026-04-05
 */

'use client';

import {
  useQuery,
  useMutation,
  useQueryClient,
  useInfiniteQuery,
} from '@tanstack/react-query';
import { userDocumentsApi } from '../services/api';
import type {
  UserDocument,
  UserDocumentListItem,
  UserDocumentListResponse,
  UserDocumentStats,
  ReadinessResult,
  DocumentAlert,
  DocumentFilters,
  DocumentUpdateRequest,
  BulkActionRequest,
} from '../types';

// =============================================================================
// QUERY KEY FACTORY
// =============================================================================

export const userDocumentKeys = {
  all: ['user-documents'] as const,
  lists: () => [...userDocumentKeys.all, 'list'] as const,
  list: (filters?: DocumentFilters) =>
    [...userDocumentKeys.lists(), filters ?? {}] as const,
  details: () => [...userDocumentKeys.all, 'detail'] as const,
  detail: (id: string) => [...userDocumentKeys.details(), id] as const,
  stats: () => [...userDocumentKeys.all, 'stats'] as const,
  alerts: () => [...userDocumentKeys.all, 'alerts'] as const,
  readiness: (workflowCode?: string) =>
    [...userDocumentKeys.all, 'readiness', workflowCode] as const,
  generated: (generationType?: string) =>
    [...userDocumentKeys.all, 'generated', generationType] as const,
  versions: (id: string) => [...userDocumentKeys.all, 'versions', id] as const,
};

// =============================================================================
// LIST HOOK (INFINITE QUERY)
// =============================================================================

/**
 * Infinite-scroll list of user documents with cursor-based pagination.
 *
 * @param filters - Optional filters (source, category, status, etc.)
 * @returns Flattened document array, pagination controls, and quota info.
 */
export function useUserDocuments(filters?: DocumentFilters) {
  const query = useInfiniteQuery<UserDocumentListResponse, Error>({
    queryKey: userDocumentKeys.list(filters),
    queryFn: ({ pageParam }) => {
      return userDocumentsApi.list({
        ...filters,
        cursor: pageParam as string | undefined,
      });
    },
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
    staleTime: 30_000, // 30 seconds
    refetchOnWindowFocus: true,
  });

  // Flatten all pages into a single array of documents
  const documents: UserDocumentListItem[] =
    query.data?.pages.flatMap((page) => page.items) ?? [];

  // Pull quota from the most recent page (always reflects latest server state)
  const lastPage = query.data?.pages[query.data.pages.length - 1];

  return {
    ...query,
    documents,
    totalCount: lastPage?.total_count ?? 0,
    quotaUsedBytes: lastPage?.quota_used_bytes ?? 0,
    quotaMaxBytes: lastPage?.quota_max_bytes ?? 0,
  };
}

// =============================================================================
// DETAIL HOOK
// =============================================================================

/**
 * Fetch full detail for a single user document.
 *
 * @param documentId - UUID of the document
 */
export function useUserDocument(documentId: string) {
  const query = useQuery<UserDocument, Error>({
    queryKey: userDocumentKeys.detail(documentId),
    queryFn: () => userDocumentsApi.getById(documentId),
    enabled: !!documentId,
    staleTime: 60_000, // 1 minute
  });

  return {
    document: query.data ?? null,
    isLoading: query.isLoading,
    error: query.error,
    refetch: query.refetch,
  };
}

// =============================================================================
// MUTATION HOOKS
// =============================================================================

/**
 * Grouped mutations for document actions: update, archive, delete, reclassify, bulk.
 *
 * All mutations invalidate the relevant query keys on success so lists
 * and detail views stay in sync.
 */
export function useDocumentMutations() {
  const queryClient = useQueryClient();

  /** Invalidate all user-documents queries */
  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: userDocumentKeys.all });
  };

  /** Invalidate a specific document detail cache */
  const invalidateDetail = (documentId: string) => {
    queryClient.invalidateQueries({
      queryKey: userDocumentKeys.detail(documentId),
    });
  };

  // ---------------------------------------------------------------------------
  // Update Metadata
  // ---------------------------------------------------------------------------

  const updateMetadata = useMutation<
    UserDocument,
    Error,
    { documentId: string; data: DocumentUpdateRequest }
  >({
    mutationFn: ({ documentId, data }) =>
      userDocumentsApi.update(documentId, data),
    onSuccess: (_, { documentId }) => {
      invalidateDetail(documentId);
      queryClient.invalidateQueries({ queryKey: userDocumentKeys.lists() });
    },
  });

  // ---------------------------------------------------------------------------
  // Archive
  // ---------------------------------------------------------------------------

  const archiveDocument = useMutation<void, Error, { documentId: string }>({
    mutationFn: ({ documentId }) => userDocumentsApi.archive(documentId),
    onSuccess: () => {
      invalidateAll();
    },
  });

  // ---------------------------------------------------------------------------
  // Delete
  // ---------------------------------------------------------------------------

  const deleteDocument = useMutation<void, Error, { documentId: string }>({
    mutationFn: ({ documentId }) => userDocumentsApi.deleteDoc(documentId),
    onSuccess: () => {
      invalidateAll();
    },
  });

  // ---------------------------------------------------------------------------
  // Reclassify
  // ---------------------------------------------------------------------------

  const reclassifyDocument = useMutation<
    UserDocument,
    Error,
    { documentId: string }
  >({
    mutationFn: ({ documentId }) => userDocumentsApi.reclassify(documentId),
    onSuccess: (_, { documentId }) => {
      invalidateDetail(documentId);
      queryClient.invalidateQueries({ queryKey: userDocumentKeys.lists() });
    },
  });

  // ---------------------------------------------------------------------------
  // Bulk Action
  // ---------------------------------------------------------------------------

  const bulkAction = useMutation<
    { processed: number },
    Error,
    BulkActionRequest
  >({
    mutationFn: (data) => userDocumentsApi.bulkAction(data),
    onSuccess: () => {
      invalidateAll();
    },
  });

  return {
    updateMetadata,
    archiveDocument,
    deleteDocument,
    reclassifyDocument,
    bulkAction,
    // Convenience flags
    isUpdating: updateMetadata.isPending,
    isArchiving: archiveDocument.isPending,
    isDeleting: deleteDocument.isPending,
    isReclassifying: reclassifyDocument.isPending,
    isBulkProcessing: bulkAction.isPending,
  };
}

// =============================================================================
// STATS HOOK
// =============================================================================

/**
 * Aggregated vault statistics (counts, quota, expiry summary).
 */
export function useDocumentStats() {
  return useQuery<UserDocumentStats, Error>({
    queryKey: userDocumentKeys.stats(),
    queryFn: () => userDocumentsApi.getStats(),
    staleTime: 30_000, // 30 seconds
    refetchOnWindowFocus: true,
  });
}

// =============================================================================
// ALERTS HOOK
// =============================================================================

/**
 * Proactive document alerts (expiry warnings, missing for workflows, etc.).
 *
 * Includes mutations to mark alerts as read or dismiss them.
 */
export function useDocumentAlerts() {
  const queryClient = useQueryClient();

  const alertsQuery = useQuery<DocumentAlert[], Error>({
    queryKey: userDocumentKeys.alerts(),
    queryFn: () => userDocumentsApi.getAlerts(),
    staleTime: 60_000, // 1 minute
    refetchOnWindowFocus: true,
  });

  const markRead = useMutation<void, Error, { alertId: string }>({
    mutationFn: ({ alertId }) => userDocumentsApi.markAlertRead(alertId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: userDocumentKeys.alerts() });
    },
  });

  const dismiss = useMutation<void, Error, { alertId: string }>({
    mutationFn: ({ alertId }) => userDocumentsApi.dismissAlert(alertId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: userDocumentKeys.alerts() });
    },
  });

  // Derived counts
  const alerts = alertsQuery.data ?? [];
  const unreadCount = alerts.filter((a) => !a.is_read).length;
  const criticalCount = alerts.filter(
    (a) => a.severity === 'critical' && !a.is_dismissed
  ).length;

  return {
    alerts,
    isLoading: alertsQuery.isLoading,
    error: alertsQuery.error,
    unreadCount,
    criticalCount,
    markRead,
    dismiss,
    refetch: alertsQuery.refetch,
  };
}

// =============================================================================
// READINESS HOOK
// =============================================================================

/**
 * Check document readiness for a specific workflow.
 *
 * @param workflowCode - e.g. "PASAPORTE_EXPEDICION"
 */
export function useReadiness(workflowCode?: string) {
  return useQuery<ReadinessResult | ReadinessResult[], Error>({
    queryKey: userDocumentKeys.readiness(workflowCode),
    queryFn: () => userDocumentsApi.getReadiness(workflowCode),
    enabled: !!workflowCode,
    staleTime: 60_000, // 1 minute
  });
}

// =============================================================================
// VERSIONS HOOK
// =============================================================================

/**
 * Fetch version history chain for a document.
 *
 * @param documentId - UUID of the document
 */
export function useDocumentVersions(documentId: string) {
  return useQuery({
    queryKey: userDocumentKeys.versions(documentId),
    queryFn: () => userDocumentsApi.getVersions(documentId),
    enabled: !!documentId,
    staleTime: 60_000,
  });
}
