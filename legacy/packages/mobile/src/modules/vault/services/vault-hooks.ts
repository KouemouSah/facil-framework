/**
 * Vault React Query hooks.
 *
 * - List: `useInfiniteQuery` with cursor pagination.
 * - Detail: `useQuery` with conditional refetchInterval that polls
 *   `extraction_status` every 2s until completed/failed (mimics the
 *   server-side SSE without the SSE dependency).
 * - Mutations invalidate the relevant queries; UI does not need to call
 *   `refresh()` manually.
 *
 * Query keys are strings prefixed with 'vault.' so the unified
 * `queryClient.invalidateQueries({ queryKey: ['vault'] })` clears the
 * whole feature on sign-out (auth provider handles that).
 */

import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
  type UseInfiniteQueryResult,
  type UseQueryResult,
} from '@tanstack/react-query';

import * as vaultApi from './vault-api';
import { computeFileHash, readFileMeta } from './vault-hash';
import type {
  AlertResponse,
  GeneratedDocumentResponse,
  HashCheckResponse,
  ReadinessResult,
  UploadResult,
  UserDocumentBulkAction,
  UserDocumentListItem,
  UserDocumentListResponse,
  UserDocumentResponse,
  UserDocumentStats,
  UserDocumentUpdate,
  VaultAllowedMime,
} from '../types/vault.types';

const QK = {
  list: (params?: vaultApi.ListVaultParams) => ['vault', 'list', params ?? null] as const,
  detail: (id: string) => ['vault', 'detail', id] as const,
  versions: (id: string) => ['vault', 'versions', id] as const,
  stats: () => ['vault', 'stats'] as const,
  alerts: (params?: vaultApi.ListAlertsParams) => ['vault', 'alerts', params ?? null] as const,
  generated: (params?: vaultApi.ListGeneratedParams) => ['vault', 'generated', params ?? null] as const,
  readiness: (workflowCode?: string) =>
    workflowCode ? (['vault', 'readiness', workflowCode] as const) : (['vault', 'readiness', 'all'] as const),
  forWorkflow: (workflowCode: string) => ['vault', 'forWorkflow', workflowCode] as const,
  search: (q: string) => ['vault', 'search', q] as const,
  download: (id: string) => ['vault', 'download', id] as const,
  thumbnail: (id: string) => ['vault', 'thumbnail', id] as const,
};

// ---------------------------------------------------------------------------
// List + paginated reads
// ---------------------------------------------------------------------------

export function useVaultList(
  params: Omit<vaultApi.ListVaultParams, 'cursor'> = {},
): UseInfiniteQueryResult<{ pages: UserDocumentListResponse[]; pageParams: (string | undefined)[] }> {
  return useInfiniteQuery({
    queryKey: QK.list(params),
    initialPageParam: undefined as string | undefined,
    queryFn: ({ pageParam }) =>
      vaultApi.listVault({ ...params, cursor: pageParam }),
    getNextPageParam: (last) => last.next_cursor ?? undefined,
    staleTime: 30_000,
  });
}

export function useVaultStats(): UseQueryResult<UserDocumentStats> {
  return useQuery({
    queryKey: QK.stats(),
    queryFn: vaultApi.getVaultStats,
    staleTime: 60_000,
  });
}

export function useVaultGenerated(
  params: Omit<vaultApi.ListGeneratedParams, 'cursor'> = {},
): UseInfiniteQueryResult<{ pages: GeneratedDocumentResponse[][]; pageParams: (string | undefined)[] }> {
  return useInfiniteQuery({
    queryKey: QK.generated(params),
    initialPageParam: undefined as string | undefined,
    queryFn: ({ pageParam }) =>
      vaultApi.listGenerated({ ...params, cursor: pageParam }),
    // Backend returns a flat list (not paginated response); next_cursor is on
    // each item's pagination metadata when added — stay on a single page until
    // backend exposes it.
    getNextPageParam: () => undefined,
    staleTime: 60_000,
  });
}

// ---------------------------------------------------------------------------
// Detail + status polling
// ---------------------------------------------------------------------------

export function useVaultDocument(id: string | null): UseQueryResult<UserDocumentResponse> {
  return useQuery({
    queryKey: id ? QK.detail(id) : ['vault', 'detail', 'disabled'],
    queryFn: () => vaultApi.getVaultDocument(id as string),
    enabled: !!id,
    refetchInterval: (query) => {
      const data = query.state.data as UserDocumentResponse | undefined;
      const status = data?.extraction_status;
      if (status === 'completed' || status === 'failed') return false;
      return 2000;
    },
    refetchIntervalInBackground: false,
    staleTime: 0,
  });
}

export function useVaultVersions(id: string | null): UseQueryResult<UserDocumentListItem[]> {
  return useQuery({
    queryKey: id ? QK.versions(id) : ['vault', 'versions', 'disabled'],
    queryFn: () => vaultApi.getVaultVersions(id as string),
    enabled: !!id,
    staleTime: 60_000,
  });
}

// ---------------------------------------------------------------------------
// Mutations (update / archive / delete / reclassify)
// ---------------------------------------------------------------------------

export function useUpdateVaultDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: UserDocumentUpdate }) =>
      vaultApi.updateVaultDocument(id, patch),
    onSuccess: (data) => {
      qc.setQueryData(QK.detail(data.id), data);
      qc.invalidateQueries({ queryKey: ['vault', 'list'] });
    },
  });
}

export function useArchiveVaultDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => vaultApi.archiveVaultDocument(id),
    onSuccess: (data) => {
      qc.setQueryData(QK.detail(data.id), data);
      qc.invalidateQueries({ queryKey: ['vault', 'list'] });
      qc.invalidateQueries({ queryKey: QK.stats() });
    },
  });
}

export function useDeleteVaultDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => vaultApi.deleteVaultDocument(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['vault', 'list'] });
      qc.invalidateQueries({ queryKey: QK.stats() });
    },
  });
}

export function useReclassifyVaultDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      payload,
    }: {
      id: string;
      payload: { document_type: string; notes?: string };
    }) => vaultApi.reclassifyVaultDocument(id, payload),
    onSuccess: (data) => {
      qc.setQueryData(QK.detail(data.id), data);
      qc.invalidateQueries({ queryKey: QK.versions(data.id) });
    },
  });
}

// ---------------------------------------------------------------------------
// Upload (with SHA-256 dedup pre-check)
// ---------------------------------------------------------------------------

export interface UploadInput {
  fileUri: string;
  fileName: string;
  mimeType: VaultAllowedMime;
  documentTypeHint?: string;
  notes?: string;
  onProgress?: (progress: number) => void;
  /** Skip the pre-upload SHA-256 hash check (force a re-upload). */
  skipDedup?: boolean;
}

export interface UploadOutcome {
  result?: UploadResult;
  duplicate?: HashCheckResponse;
}

export function useUploadVaultDocument() {
  const qc = useQueryClient();
  return useMutation<UploadOutcome, Error, UploadInput>({
    mutationFn: async (input) => {
      if (!input.skipDedup) {
        const { hash } = await readFileMeta(input.fileUri);
        const hashCheck = await vaultApi.checkHash(hash);
        if (hashCheck.exists) {
          return { duplicate: hashCheck };
        }
      } else {
        // Still compute the hash (we'll include it implicitly on the next
        // upload); skipping the check allows a re-upload after the user
        // explicitly confirms they want to ignore the dedup hint.
        await computeFileHash(input.fileUri);
      }
      const result = await vaultApi.uploadVaultDocument(input);
      return { result };
    },
    onSuccess: (outcome) => {
      if (outcome.result) {
        qc.invalidateQueries({ queryKey: ['vault', 'list'] });
        qc.invalidateQueries({ queryKey: QK.stats() });
      }
    },
  });
}

// ---------------------------------------------------------------------------
// Alerts
// ---------------------------------------------------------------------------

export function useVaultAlerts(
  params: vaultApi.ListAlertsParams = {},
): UseQueryResult<AlertResponse[]> {
  return useQuery({
    queryKey: QK.alerts(params),
    queryFn: () => vaultApi.listAlerts(params),
    staleTime: 30_000,
  });
}

export function useMarkAlertRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (alertId: string) => vaultApi.markAlertRead(alertId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['vault', 'alerts'] });
    },
  });
}

export function useDismissAlert() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (alertId: string) => vaultApi.dismissAlert(alertId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['vault', 'alerts'] });
    },
  });
}

// ---------------------------------------------------------------------------
// Readiness + workflow integration
// ---------------------------------------------------------------------------

export function useVaultReadinessForWorkflow(
  workflowCode: string | null,
): UseQueryResult<ReadinessResult> {
  return useQuery({
    queryKey: workflowCode ? QK.readiness(workflowCode) : ['vault', 'readiness', 'disabled'],
    queryFn: () => vaultApi.getReadinessForWorkflow(workflowCode as string),
    enabled: !!workflowCode,
    staleTime: 30_000,
  });
}

export function useVaultReadinessAll(): UseQueryResult<ReadinessResult[]> {
  return useQuery({
    queryKey: QK.readiness(),
    queryFn: vaultApi.getReadinessAll,
    staleTime: 30_000,
  });
}

export function useDocumentsForWorkflow(
  workflowCode: string | null,
): UseQueryResult<UserDocumentResponse[]> {
  return useQuery({
    queryKey: workflowCode ? QK.forWorkflow(workflowCode) : ['vault', 'forWorkflow', 'disabled'],
    queryFn: () => vaultApi.getDocumentsForWorkflow(workflowCode as string),
    enabled: !!workflowCode,
    staleTime: 30_000,
  });
}

// ---------------------------------------------------------------------------
// Search
// ---------------------------------------------------------------------------

export function useVaultSearch(query: string): UseQueryResult<UserDocumentListItem[]> {
  return useQuery({
    queryKey: QK.search(query),
    queryFn: () => vaultApi.searchVault(query),
    enabled: query.trim().length >= 2,
    staleTime: 30_000,
  });
}

// ---------------------------------------------------------------------------
// Signed URLs (download + thumbnail)
// ---------------------------------------------------------------------------

const FOURTEEN_MINUTES_MS = 14 * 60 * 1000;

export function useDownloadUrl(id: string | null): UseQueryResult<vaultApi.SignedUrlResponse> {
  return useQuery({
    queryKey: id ? QK.download(id) : ['vault', 'download', 'disabled'],
    queryFn: () => vaultApi.getDownloadUrl(id as string),
    enabled: !!id,
    // Backend signs URLs for 15 minutes. Refresh slightly earlier so a long
    // session never hits the 410.
    staleTime: FOURTEEN_MINUTES_MS,
    gcTime: FOURTEEN_MINUTES_MS + 60_000,
  });
}

export function useThumbnailUrl(id: string | null): UseQueryResult<vaultApi.SignedUrlResponse> {
  return useQuery({
    queryKey: id ? QK.thumbnail(id) : ['vault', 'thumbnail', 'disabled'],
    queryFn: () => vaultApi.getThumbnailUrl(id as string),
    enabled: !!id,
    staleTime: FOURTEEN_MINUTES_MS,
    gcTime: FOURTEEN_MINUTES_MS + 60_000,
    retry: false, // 404 = no thumbnail; don't retry, surface gracefully
  });
}

// ---------------------------------------------------------------------------
// Bulk action + export
// ---------------------------------------------------------------------------

export function useBulkAction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: UserDocumentBulkAction) => vaultApi.bulkAction(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['vault', 'list'] });
      qc.invalidateQueries({ queryKey: QK.stats() });
    },
  });
}

export function useStartExport() {
  return useMutation({
    mutationFn: (category?: string) => vaultApi.startExport(category),
  });
}

export function useExportStatus(exportId: string | null) {
  return useQuery({
    queryKey: exportId
      ? ['vault', 'export', 'status', exportId]
      : ['vault', 'export', 'status', 'disabled'],
    queryFn: () => vaultApi.getExportStatus(exportId as string),
    enabled: !!exportId,
    refetchInterval: (query) => {
      const data = query.state.data as vaultApi.ExportStatusResponse | undefined;
      if (!data) return 3000;
      if (data.status === 'completed' || data.status === 'failed') return false;
      return 3000;
    },
  });
}

export function getExportDownload(exportId: string) {
  return vaultApi.getExportDownload(exportId);
}
