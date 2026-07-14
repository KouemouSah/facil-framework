import { apiFetch } from "@/lib/api";
import type { FieldSpecType, I18nString } from "@/lib/schema/types";

/** Client for `/api/v1/admin/field-definitions` — the REAL routes, request/
 *  response shapes and status codes (Task 13,
 *  `packages/backend/app/api/admin_field_definitions.py`). The request body
 *  IS a `FieldSpec` (+ `target`/`inherit_to_suborgs`, see `FieldDefinitionIn`
 *  there) — mirrored below as `DefinitionIn`. The response is
 *  `FieldDefinition.as_dict()` (== `as_spec()` + row-identity fields) + etag. */

export const FIELD_DEF_BASE = "/api/v1/admin/field-definitions";

/** `EXTENSIBLE_TARGETS` (app/core/schema/registry.py) — the only (entity, json
 *  column) pairs a tenant may bolt custom fields onto. Order is the Studio's
 *  tab order. */
export const TARGETS = [
  "organization.custom_fields",
  "org_unit.custom_fields",
  "site.custom_fields",
  "party.custom_fields",
] as const;
export type Target = (typeof TARGETS)[number];

export type IndexState = "none" | "pending" | "ready" | "failed";

/** The create/update request body — mirrors `FieldDefinitionIn` exactly
 *  (a `FieldSpec` plus the two columns that are not part of the wire
 *  descriptor). `widget` may be sent blank — the backend resolves it to the
 *  type's canonical default (`_default_widget`). */
export interface DefinitionIn {
  key: string;
  type: FieldSpecType;
  widget: string;
  label: I18nString;
  hint: I18nString;
  required: boolean;
  default: unknown;
  rules: Record<string, unknown>;
  options: { value: string; label: I18nString }[];
  relation_resource: string;
  relation_filter: Record<string, string>;
  group: string;
  order: number;
  col_span: number;
  indexed: boolean;
  target: Target;
  inherit_to_suborgs: boolean;
}

/** The admin API response shape — `FieldDefinition.as_dict()` + etag. */
export interface Definition extends DefinitionIn {
  id: string;
  organization_id: string;
  index_state: IndexState;
  archived: boolean;
  is_active: boolean;
  etag: string;
}

const withMatch = (etag?: string): HeadersInit | undefined =>
  etag ? { "If-Match": etag } : undefined;

export const listDefinitions = (
  organizationId: string, target?: Target, includeArchived = false,
) =>
  apiFetch<{ items: Definition[]; count: number }>(
    `${FIELD_DEF_BASE}/?organization_id=${encodeURIComponent(organizationId)}` +
    (target ? `&target=${encodeURIComponent(target)}` : "") +
    (includeArchived ? `&include_archived=true` : ""));

export const getDefinition = (id: string) =>
  apiFetch<Definition>(`${FIELD_DEF_BASE}/${id}`);

export const createDefinition = (organizationId: string, body: DefinitionIn) =>
  apiFetch<Definition>(
    `${FIELD_DEF_BASE}/?organization_id=${encodeURIComponent(organizationId)}`,
    { method: "POST", body: JSON.stringify(body) });

export const updateDefinition = (id: string, body: DefinitionIn, etag?: string) =>
  apiFetch<Definition>(`${FIELD_DEF_BASE}/${id}`, {
    method: "PUT", headers: withMatch(etag), body: JSON.stringify(body),
  });

export const archiveDefinition = (id: string, etag?: string) =>
  apiFetch<Definition>(`${FIELD_DEF_BASE}/${id}/archive`, { method: "POST", headers: withMatch(etag) });

export const unarchiveDefinition = (id: string, etag?: string) =>
  apiFetch<Definition>(`${FIELD_DEF_BASE}/${id}/unarchive`, { method: "POST", headers: withMatch(etag) });

export const purgeDefinition = (id: string, etag?: string) =>
  apiFetch<{ deleted: string }>(`${FIELD_DEF_BASE}/${id}/purge`, { method: "POST", headers: withMatch(etag) });

export const buildIndex = (id: string, etag?: string) =>
  apiFetch<Definition>(`${FIELD_DEF_BASE}/${id}/index`, { method: "POST", headers: withMatch(etag) });
