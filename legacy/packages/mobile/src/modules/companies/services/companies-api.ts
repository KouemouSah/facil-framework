/**
 * Companies API — thin wrappers over apiGet/apiPost/apiPut/apiDelete.
 *
 * Backend: app/modules/companies/api/company_routes.py
 * All paths centralised in `API_ENDPOINTS.companies.*` (P0).
 */

import { apiDelete, apiGet, apiPost, apiPut } from '@core/api/client';
import { API_ENDPOINTS } from '@core/api/endpoints';

import type {
  AddMemberRequest,
  CompanyCreate,
  CompanyListResponse,
  CompanyMember,
  CompanyResponse,
  CompanyUpdate,
  UpdateMemberRoleRequest,
} from '../types/companies.types';

// ---------------------------------------------------------------------------
// CRUD list / detail / create / update / delete
// ---------------------------------------------------------------------------

export interface ListCompaniesParams {
  page?: number;
  page_size?: number;
  [key: string]: unknown;
}

export async function listCompanies(
  params: ListCompaniesParams = {},
): Promise<CompanyListResponse> {
  return apiGet<CompanyListResponse>(API_ENDPOINTS.companies.list, params);
}

export async function getCompany(id: string): Promise<CompanyResponse> {
  return apiGet<CompanyResponse>(API_ENDPOINTS.companies.detail(id));
}

export async function createCompany(payload: CompanyCreate): Promise<CompanyResponse> {
  return apiPost<CompanyResponse>(API_ENDPOINTS.companies.create, payload);
}

export async function updateCompany(
  id: string,
  payload: CompanyUpdate,
): Promise<CompanyResponse> {
  return apiPut<CompanyResponse>(API_ENDPOINTS.companies.update(id), payload);
}

export async function deleteCompany(id: string): Promise<{ message: string }> {
  return apiDelete<{ message: string }>(API_ENDPOINTS.companies.delete(id));
}

/**
 * Soft-delete (archive) a company — citizen surface, owner-only.
 *
 * Backend may respond 409 with body
 * `{ detail: { message, blockers: { active_licenses, pending_payments,
 *   open_requests, active_inspections } } }` when the company has active
 * dependencies. Callers should surface the per-bucket counts to the user.
 */
export async function archiveCompany(
  id: string,
): Promise<{ message: string; archived_at: string | null }> {
  return apiPost<{ message: string; archived_at: string | null }>(
    API_ENDPOINTS.companies.archive(id),
    {},
  );
}

// ---------------------------------------------------------------------------
// Members
// ---------------------------------------------------------------------------

export async function listMembers(companyId: string): Promise<CompanyMember[]> {
  return apiGet<CompanyMember[]>(API_ENDPOINTS.companies.members(companyId));
}

export async function addMember(
  companyId: string,
  payload: AddMemberRequest,
): Promise<CompanyMember> {
  return apiPost<CompanyMember>(API_ENDPOINTS.companies.addMember(companyId), payload);
}

export async function updateMemberRole(
  companyId: string,
  memberUserId: string,
  payload: UpdateMemberRoleRequest,
): Promise<CompanyMember> {
  return apiPut<CompanyMember>(
    API_ENDPOINTS.companies.updateMemberRole(companyId, memberUserId),
    payload,
  );
}

export async function removeMember(
  companyId: string,
  memberUserId: string,
): Promise<{ message: string }> {
  return apiDelete<{ message: string }>(
    API_ENDPOINTS.companies.removeMember(companyId, memberUserId),
  );
}
