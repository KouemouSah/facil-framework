/**
 * Companies React Query hooks.
 *
 * Pagination is offset-based (page/page_size) — different from the vault
 * cursor-based pagination. `getNextPageParam` advances by 1 until total is
 * exhausted.
 */

import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
  type UseInfiniteQueryResult,
  type UseMutationResult,
  type UseQueryResult,
} from '@tanstack/react-query';

import * as companiesApi from './companies-api';
import { downloadLicensePdf } from './company-pdf';
import type {
  AddMemberRequest,
  CompanyCreate,
  CompanyListResponse,
  CompanyMember,
  CompanyResponse,
  CompanyUpdate,
  UpdateMemberRoleRequest,
} from '../types/companies.types';

const QK = {
  list: (params?: companiesApi.ListCompaniesParams) =>
    ['companies', 'list', params ?? null] as const,
  detail: (id: string) => ['companies', 'detail', id] as const,
  members: (id: string) => ['companies', 'members', id] as const,
};

const PAGE_SIZE = 20;

// ---------------------------------------------------------------------------
// List + detail
// ---------------------------------------------------------------------------

export function useCompaniesList(): UseInfiniteQueryResult<{
  pages: CompanyListResponse[];
  pageParams: number[];
}> {
  return useInfiniteQuery({
    queryKey: QK.list({ page_size: PAGE_SIZE }),
    initialPageParam: 1,
    queryFn: ({ pageParam }) =>
      companiesApi.listCompanies({ page: pageParam, page_size: PAGE_SIZE }),
    getNextPageParam: (last, all) => {
      const fetched = all.reduce((acc, p) => acc + p.companies.length, 0);
      return fetched < last.total ? last.page + 1 : undefined;
    },
    staleTime: 30_000,
  });
}

export function useCompanyDetail(id: string | null): UseQueryResult<CompanyResponse> {
  return useQuery({
    queryKey: id ? QK.detail(id) : ['companies', 'detail', 'disabled'],
    queryFn: () => companiesApi.getCompany(id as string),
    enabled: !!id,
    staleTime: 30_000,
  });
}

// ---------------------------------------------------------------------------
// CRUD mutations
// ---------------------------------------------------------------------------

export function useCreateCompany(): UseMutationResult<CompanyResponse, Error, CompanyCreate> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: CompanyCreate) => companiesApi.createCompany(payload),
    onSuccess: (data) => {
      qc.setQueryData(QK.detail(data.id), data);
      qc.invalidateQueries({ queryKey: ['companies', 'list'] });
    },
  });
}

export function useUpdateCompany(): UseMutationResult<
  CompanyResponse,
  Error,
  { id: string; patch: CompanyUpdate }
> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: CompanyUpdate }) =>
      companiesApi.updateCompany(id, patch),
    onSuccess: (data) => {
      qc.setQueryData(QK.detail(data.id), data);
      qc.invalidateQueries({ queryKey: ['companies', 'list'] });
    },
  });
}

export function useDeleteCompany(): UseMutationResult<{ message: string }, Error, string> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => companiesApi.deleteCompany(id),
    onSuccess: (_data, id) => {
      qc.removeQueries({ queryKey: QK.detail(id) });
      qc.removeQueries({ queryKey: QK.members(id) });
      qc.invalidateQueries({ queryKey: ['companies', 'list'] });
    },
  });
}

// ---------------------------------------------------------------------------
// Members
// ---------------------------------------------------------------------------

export function useCompanyMembers(companyId: string | null): UseQueryResult<CompanyMember[]> {
  return useQuery({
    queryKey: companyId ? QK.members(companyId) : ['companies', 'members', 'disabled'],
    queryFn: () => companiesApi.listMembers(companyId as string),
    enabled: !!companyId,
    staleTime: 30_000,
  });
}

/**
 * Resolve the current user's role inside a given company + role-derived
 * permissions. Mirrors the backend authorisation contract:
 *   PUT  /companies/{id}        -> company_owner | company_admin
 *   DELETE /companies/{id}      -> company_owner only
 *   POST /{id}/members          -> company_owner | company_admin
 *
 * NOTE: the citizen surfaces (web /empresas/[id], mobile /companies/[id]) do
 * NOT currently expose Edit/Delete CTAs because the backend DELETE performs
 * an unprotected hard-delete (no check on commercial_licenses, payments,
 * service_requests). This hook is shipped now so that the day the backend
 * gains soft-delete + dependency checks, future UI can subscribe without
 * re-deriving the rules.
 */
export interface CompanyMembershipPermissions {
  /** Membership row of the current user, or null if they're not a member. */
  membership: CompanyMember | null;
  isOwner: boolean;
  isAdmin: boolean;
  /** Allowed by backend permissions (does not mean we expose the UI today). */
  canEdit: boolean;
  /**
   * @deprecated Use {@link canArchive} (citizen surface). Hard-delete is now
   * gated server-side by `company.hard_delete` permission AND a prior archive,
   * so a citizen never legitimately holds it. Kept for back-compat with any
   * call sites still reading the flag.
   */
  canDelete: boolean;
  /** Owner can archive (soft-delete) — citizen surface gate. */
  canArchive: boolean;
  canManageMembers: boolean;
}

export function useCompanyMembership(
  companyId: string | null,
  currentUserId: string | null | undefined,
): CompanyMembershipPermissions {
  const members = useCompanyMembers(companyId);
  const membership =
    (members.data ?? []).find((m) => m.user_id === currentUserId) ?? null;
  const isOwner = membership?.role === 'company_owner';
  const isAdmin = membership?.role === 'company_admin';
  return {
    membership,
    isOwner,
    isAdmin,
    canEdit: isOwner || isAdmin,
    canDelete: isOwner,
    canArchive: isOwner,
    canManageMembers: isOwner || isAdmin,
  };
}

// ---------------------------------------------------------------------------
// Archive (soft-delete) — citizen surface
//
// Backend reference: migration 314 + .claude/plans/SOFT_DELETE_COMPANIES_PLAN.md
// ---------------------------------------------------------------------------

/** Counts returned in the structured 409 response when archive is blocked. */
export interface ArchiveBlockers {
  active_licenses: number;
  pending_payments: number;
  open_requests: number;
  active_inspections: number;
}

/**
 * Type-guard for the 409 blocker response. Reads ``status`` + ``data.detail``
 * from an axios-shaped error without leaning on @core/api/errors so this
 * file stays free of cross-module deps.
 */
export function isArchiveBlockedError(err: unknown): err is {
  response: { status: 409; data: { detail: { blockers: ArchiveBlockers } } };
} {
  if (!err || typeof err !== 'object') return false;
  const e = err as {
    response?: {
      status?: number;
      data?: { detail?: { blockers?: unknown } };
    };
  };
  if (e.response?.status !== 409) return false;
  const blockers = e.response?.data?.detail?.blockers;
  return !!blockers && typeof blockers === 'object';
}

export function getArchiveBlockers(err: unknown): ArchiveBlockers | null {
  if (!isArchiveBlockedError(err)) return null;
  return err.response.data.detail.blockers;
}

/**
 * Archive a company. Caller is responsible for surfacing the structured 409
 * blocker payload via {@link getArchiveBlockers}. Cache invalidation:
 * ``companies.list`` + ``companies.detail(id)`` + ``bundles`` queries.
 */
export function useArchiveCompany(): UseMutationResult<
  { message: string; archived_at: string | null },
  Error,
  string
> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (companyId: string) => companiesApi.archiveCompany(companyId),
    onSuccess: (_data, companyId) => {
      qc.invalidateQueries({ queryKey: QK.detail(companyId) });
      qc.invalidateQueries({ queryKey: ['companies'] });
      qc.invalidateQueries({ queryKey: ['bundles'] });
    },
  });
}

export function useAddMember(companyId: string): UseMutationResult<
  CompanyMember,
  Error,
  AddMemberRequest
> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: AddMemberRequest) => companiesApi.addMember(companyId, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: QK.members(companyId) });
      qc.invalidateQueries({ queryKey: QK.detail(companyId) });
    },
  });
}

export function useUpdateMemberRole(companyId: string): UseMutationResult<
  CompanyMember,
  Error,
  { memberUserId: string; payload: UpdateMemberRoleRequest }
> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      memberUserId,
      payload,
    }: {
      memberUserId: string;
      payload: UpdateMemberRoleRequest;
    }) => companiesApi.updateMemberRole(companyId, memberUserId, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: QK.members(companyId) });
    },
  });
}

export function useRemoveMember(companyId: string): UseMutationResult<
  { message: string },
  Error,
  string
> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (memberUserId: string) =>
      companiesApi.removeMember(companyId, memberUserId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: QK.members(companyId) });
      qc.invalidateQueries({ queryKey: QK.detail(companyId) });
    },
  });
}

// ---------------------------------------------------------------------------
// License PDF download
// ---------------------------------------------------------------------------

export function useDownloadLicensePdf(): UseMutationResult<
  void,
  Error,
  { companyId: string; language?: 'es' | 'fr' | 'en' }
> {
  return useMutation({
    mutationFn: ({ companyId, language }) =>
      downloadLicensePdf(companyId, language ?? 'es'),
  });
}
