import { apiFetch } from "@/lib/api";

const ORG_BASE = "/api/v1/modules/organization";

export interface OrgUnit {
  id: string;
  organization_id: string;
  parent_id: string | null;
  code: string;
  name: string;
  unit_type: string;
  description: string | null;
  path: string;
  depth: number;
  external_ref: string | null;
  metadata: Record<string, unknown>;
  is_active: boolean;
  etag?: string;
}

export const listUnits = (orgId: string) =>
  apiFetch<OrgUnit[]>(`${ORG_BASE}/${orgId}/units?limit=200`);

export const getUnit = (unitId: string) =>
  apiFetch<OrgUnit>(`${ORG_BASE}/units/${unitId}`);

export const createUnit = (orgId: string, body: Record<string, unknown>) =>
  apiFetch<OrgUnit>(`${ORG_BASE}/${orgId}/units`, { method: "POST", body: JSON.stringify(body) });

export const updateUnit = (unitId: string, body: Record<string, unknown>, etag?: string) =>
  apiFetch<OrgUnit>(`${ORG_BASE}/units/${unitId}`, {
    method: "PUT",
    headers: etag ? { "If-Match": etag } : undefined,
    body: JSON.stringify(body),
  });

export const deleteUnit = (unitId: string) =>
  apiFetch(`${ORG_BASE}/units/${unitId}`, { method: "DELETE" });

export const unitsExportPath = (orgId: string) => `${ORG_BASE}/${orgId}/units/export`;
