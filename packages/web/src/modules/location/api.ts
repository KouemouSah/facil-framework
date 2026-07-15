import { apiFetch } from "@/lib/api";
import type { ServerPage } from "@/lib/use-server-table";

/** Site — the fields the list/detail surfaces read. */
export interface Site {
  id: string;
  code: string;
  name: string;
  site_type: string;
  city?: string | null;
  country_code?: string | null;
  is_primary: boolean;
  is_active: boolean;
}

export const SITE_BASE = "/api/v1/modules/location/sites";

export const listSites = (p: { orgId: string; sort: string; limit: number; cursor: string | null }) =>
  apiFetch<ServerPage<Site>>(
    `${SITE_BASE}?organization_id=${p.orgId}&sort=${p.sort}&limit=${p.limit}` +
    (p.cursor ? `&cursor=${encodeURIComponent(p.cursor)}` : ""));

export const getSite = (id: string) =>
  apiFetch<Record<string, unknown>>(`${SITE_BASE}/${id}`);

/** Resolved issuer identity for a document issued by this site: the site's
 *  own `document_identity` overrides, its org_unit's (and ancestors'), then
 *  the organization row — first non-empty per key, origin included
 *  (SP1 debt D1). */
export const getSiteIssuerIdentity = (id: string) =>
  apiFetch<import("../organization/document-preview").ResolvedIssuerIdentity>(
    `${SITE_BASE}/${id}/issuer-identity`);

export const createSite = (orgId: string, payload: Record<string, unknown>) =>
  apiFetch(SITE_BASE, {
    method: "POST",
    body: JSON.stringify({ ...payload, organization_id: orgId }),
  });

export const updateSite = (id: string, payload: Record<string, unknown>, etag?: string) =>
  apiFetch(`${SITE_BASE}/${id}`, {
    method: "PUT",
    headers: etag ? { "If-Match": etag } : undefined,
    body: JSON.stringify(payload),
  });

export const deleteSite = (id: string) =>
  apiFetch(`${SITE_BASE}/${id}`, { method: "DELETE" });
