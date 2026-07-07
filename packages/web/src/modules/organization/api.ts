import { apiFetch } from "@/lib/api";
import type { ServerPage } from "@/lib/use-server-table";

/** Organization (Company) — the fields the list/detail surfaces read. */
export interface Org {
  id: string;
  code: string;
  legal_name: string;
  display_name?: string;
}

export const ORG_BASE = "/api/v1/modules/organization";

export const listOrgs = (p: { q: string; sort: string; limit: number; cursor: string | null }) =>
  apiFetch<ServerPage<Org>>(
    `${ORG_BASE}/?q=${encodeURIComponent(p.q)}&sort=${p.sort}&limit=${p.limit}` +
    (p.cursor ? `&cursor=${encodeURIComponent(p.cursor)}` : ""));

export const getOrg = (id: string) =>
  apiFetch<Record<string, unknown>>(`${ORG_BASE}/${id}`);

export const createOrg = (payload: Record<string, unknown>) =>
  apiFetch(`${ORG_BASE}/`, { method: "POST", body: JSON.stringify(payload) });

export const updateOrg = (id: string, payload: Record<string, unknown>, etag?: string) =>
  apiFetch(`${ORG_BASE}/${id}`, {
    method: "PUT",
    headers: etag ? { "If-Match": etag } : undefined,
    body: JSON.stringify(payload),
  });

export const deleteOrg = (id: string) =>
  apiFetch(`${ORG_BASE}/${id}`, { method: "DELETE" });
