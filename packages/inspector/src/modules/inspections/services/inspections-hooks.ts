/**
 * Inspections Hooks - React Query mutations + queries
 */

import { useQuery, useMutation, useQueryClient, useInfiniteQuery } from '@tanstack/react-query';
import {
  inspectionsApi,
  type CreateInspectionRequest,
  type UpdateInspectionRequest,
  type CompleteInspectionRequest,
  type MiseEnDemeureRequest,
  type SealProposeRequest,
  type SealApproveRequest,
  type FieldCollectRequest,
} from './inspections-api';
import { verificationApi } from '@modules/verification/services/verification-api';
import { appConfig } from '@core/config/app';
import type { InspectionListFilters, InspectionListResponse, LicenseObligation } from '@modules/inspections/types/inspection.types';

const KEYS = {
  list: ['inspections', 'list'] as const,
  detail: (id: string) => ['inspections', 'detail', id] as const,
  stats: ['inspections', 'stats'] as const,
  obligations: (licenseId: string) => ['inspections', 'obligations', licenseId] as const,
};

// ---------------------------------------------------------------------------
// Queries
// ---------------------------------------------------------------------------

/** Paginated inspection list with infinite scroll */
export function useInspectionList(filters?: Omit<InspectionListFilters, 'page'>) {
  return useInfiniteQuery<InspectionListResponse>({
    queryKey: [...KEYS.list, filters],
    queryFn: ({ pageParam }) =>
      inspectionsApi.list({ ...filters, page: pageParam as number, page_size: 20 }),
    initialPageParam: 1,
    getNextPageParam: (lastPage) => {
      const totalPages = Math.ceil(lastPage.total / lastPage.page_size);
      return lastPage.page < totalPages ? lastPage.page + 1 : undefined;
    },
    staleTime: appConfig.cache.inspections,
  });
}

/** Single inspection detail */
export function useInspectionDetail(id: string) {
  return useQuery({
    queryKey: KEYS.detail(id),
    queryFn: () => inspectionsApi.detail(id),
    enabled: !!id,
    staleTime: 30_000,
  });
}

/**
 * Load obligations for an inspection's license.
 * Uses the verify endpoint which filters by agent's entity fee_type.
 * Only unpaid obligations are returned (status != 'paid').
 */
export function useInspectionObligations(licenseId: string | undefined) {
  return useQuery({
    queryKey: KEYS.obligations(licenseId ?? ''),
    queryFn: async (): Promise<LicenseObligation[]> => {
      if (!licenseId) return [];
      const data = await verificationApi.verifyByLicenseId(licenseId);
      return data.obligations.filter((o) => o.status !== 'paid');
    },
    enabled: !!licenseId,
    staleTime: 60_000,
  });
}

// ---------------------------------------------------------------------------
// Mutations
// ---------------------------------------------------------------------------

function useInvalidateAll(id?: string) {
  const qc = useQueryClient();
  return () => {
    qc.invalidateQueries({ queryKey: KEYS.list });
    qc.invalidateQueries({ queryKey: ['dashboard'] });
    if (id) qc.invalidateQueries({ queryKey: KEYS.detail(id) });
  };
}

/**
 * Create inspection mutation.
 * @param idempotencyKey Optional — pass a stable UUID (useRef) for safe retries.
 */
export function useCreateInspection(idempotencyKey?: string) {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (data: CreateInspectionRequest) =>
      inspectionsApi.create(data, idempotencyKey),
    onSuccess: invalidate,
  });
}

export function useUpdateInspection(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: UpdateInspectionRequest) => inspectionsApi.update(id, data),
    onSuccess: (updated) => {
      qc.setQueryData(KEYS.detail(id), updated);
    },
  });
}

export function useCompleteInspection(id: string) {
  const invalidate = useInvalidateAll(id);
  return useMutation({
    mutationFn: (data?: CompleteInspectionRequest) => inspectionsApi.complete(id, data),
    onSuccess: invalidate,
  });
}

export function useMiseEnDemeure(id: string) {
  const invalidate = useInvalidateAll(id);
  return useMutation({
    mutationFn: (data: MiseEnDemeureRequest) => inspectionsApi.miseEnDemeure(id, data),
    onSuccess: invalidate,
  });
}

export function useProposeSeal(id: string) {
  const invalidate = useInvalidateAll(id);
  return useMutation({
    mutationFn: (data: SealProposeRequest) => inspectionsApi.seal(id, data),
    onSuccess: invalidate,
  });
}

export function useApproveSeal(id: string) {
  const invalidate = useInvalidateAll(id);
  return useMutation({
    mutationFn: (data: SealApproveRequest) => inspectionsApi.sealApprove(id, data),
    onSuccess: invalidate,
  });
}

/**
 * Collect payment mutation.
 * @param idempotencyKey CRITICAL — pass a stable UUID (useRef) to make retries
 *   safe against double-charge on unstable field networks (OWASP A04).
 */
export function useCollectPayment(id: string, idempotencyKey?: string) {
  const invalidate = useInvalidateAll(id);
  return useMutation({
    mutationFn: (data: FieldCollectRequest) =>
      inspectionsApi.collect(id, data, idempotencyKey),
    onSuccess: invalidate,
  });
}

export function useUploadPhoto(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ formData, onProgress }: { formData: FormData; onProgress?: (p: number) => void }) =>
      inspectionsApi.uploadPhoto(id, formData, onProgress),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.detail(id) });
    },
  });
}

export function useDeletePhoto(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (photoIndex: number) => inspectionsApi.deletePhoto(id, photoIndex),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.detail(id) });
    },
  });
}

// ---------------------------------------------------------------------------
// Supervisor Reconciliation
// ---------------------------------------------------------------------------

export function useSupervisorReconciliation(enabled = true) {
  return useQuery({
    queryKey: ['supervisor', 'reconciliation'] as const,
    queryFn: () => inspectionsApi.getSupervisorReconciliation(),
    enabled,
    staleTime: 60_000,
  });
}

export function useValidateReconciliation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (paymentId: string) => inspectionsApi.validateReconciliation(paymentId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['supervisor'] });
      qc.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });
}
