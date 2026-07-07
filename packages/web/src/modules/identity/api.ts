import { apiFetch } from "@/lib/api";
import type { ServerPage } from "@/lib/use-server-table";

export interface Account {
  id: string;
  email?: string | null;
  account_number?: string | null;
  display_name?: string | null;
  organization_id?: string | null;
  status: string;
  is_active: boolean;
}
export interface Role { id: string; code: string; name: string }
export interface Assignment {
  id: string;
  role_id: string;
  organization_id?: string | null;
  org_unit_id?: string | null;
  site_id?: string | null;
}

// Account status vocabulary (backend `ACCOUNT_STATUSES`) and the blocking set
// that revokes sessions on transition (`_BLOCKING`) — these transitions are the
// ones the UI gates behind a ConfirmDialog.
export const ACCOUNT_STATUSES = ["pending_identity", "active", "suspended", "deactivated"] as const;
export const BLOCKING_STATUSES = new Set(["suspended", "deactivated"]);

const ACC_BASE = "/api/v1/admin/accounts";
const RBAC_BASE = "/api/v1/rbac";

export const listAccounts = (p: { q: string; status: string; sort: string; limit: number; cursor: string | null }) =>
  apiFetch<ServerPage<Account>>(
    `${ACC_BASE}?q=${encodeURIComponent(p.q)}&status=${p.status}&sort=${p.sort}&limit=${p.limit}` +
    (p.cursor ? `&cursor=${encodeURIComponent(p.cursor)}` : ""));

export const getAccount = (id: string) =>
  apiFetch<Record<string, unknown>>(`${ACC_BASE}/${id}`);

export const createAccount = (payload: Record<string, unknown>) =>
  apiFetch(`${ACC_BASE}`, { method: "POST", body: JSON.stringify(payload) });

export const updateAccount = (id: string, payload: Record<string, unknown>, etag?: string) =>
  apiFetch(`${ACC_BASE}/${id}`, {
    method: "PUT",
    headers: etag ? { "If-Match": etag } : undefined,
    body: JSON.stringify(payload),
  });

export const setAccountStatus = (id: string, status: string) =>
  apiFetch(`${ACC_BASE}/${id}/status`, { method: "PATCH", body: JSON.stringify({ status }) });

/** Per-item outcome of a bulk mutation (backend returns updated/assigned + errors). */
export interface BulkResult {
  updated?: string[];
  assigned?: string[];
  errors: { account_id: string; detail: string }[];
}

export const bulkAccountStatus = (account_ids: string[], status: string) =>
  apiFetch<BulkResult>(`${ACC_BASE}/bulk-status`, { method: "POST", body: JSON.stringify({ account_ids, status }) });

export const listAccountRoles = (accountId: string) =>
  apiFetch<Assignment[]>(`${RBAC_BASE}/accounts/${accountId}/roles`);

export const listRoles = () =>
  apiFetch<{ items: Role[] }>(`${RBAC_BASE}/roles?limit=200`).then((r) => r.items);

export const assignRole = (accountId: string, body: Record<string, unknown>) =>
  apiFetch(`${RBAC_BASE}/accounts/${accountId}/roles`, { method: "POST", body: JSON.stringify(body) });

export const revokeRole = (accountId: string, assignmentId: string) =>
  apiFetch(`${RBAC_BASE}/accounts/${accountId}/roles/${assignmentId}`, { method: "DELETE" });

export const bulkAssignRole = (body: Record<string, unknown>) =>
  apiFetch<BulkResult>(`${RBAC_BASE}/accounts/bulk-roles`, { method: "POST", body: JSON.stringify(body) });

export const accountsExportPath = (q: string, status: string, sort: string) =>
  `${ACC_BASE}/export?q=${encodeURIComponent(q)}&status=${status}&sort=${sort}`;
