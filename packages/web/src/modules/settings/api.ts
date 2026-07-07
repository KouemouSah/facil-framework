import { apiFetch } from "@/lib/api";

export const SETTINGS_BASE = "/api/v1/admin/settings";

// Config-store value types (backend `VALUE_TYPES`).
export const VALUE_TYPES = ["string", "number", "boolean", "json"] as const;
export type ValueType = (typeof VALUE_TYPES)[number];

export interface Setting {
  key: string;
  value: unknown;
  value_type: string;
  scope: string;
  secret_ref: string;
  is_active: boolean;
  name: { es: string | null; fr: string | null; en: string | null };
  description: string | null;
  updated_by?: string | null;
  etag?: string;
}

/** Body for `PUT /admin/settings/{key}` (updated_by is server-derived, not sent). */
export interface SettingIn {
  value: unknown;
  value_type: string;
  scope: string;
  secret_ref: string;
  name_es: string | null;
  name_fr: string | null;
  name_en: string | null;
  description: string | null;
  is_active: boolean;
}

export const listSettings = (scope?: string) =>
  apiFetch<Setting[]>(`${SETTINGS_BASE}/${scope ? `?scope=${encodeURIComponent(scope)}` : ""}`);

export const getSetting = (key: string) =>
  apiFetch<Setting>(`${SETTINGS_BASE}/${encodeURIComponent(key)}`);

export const putSetting = (key: string, body: SettingIn, etag?: string) =>
  apiFetch<Setting>(`${SETTINGS_BASE}/${encodeURIComponent(key)}`, {
    method: "PUT",
    headers: etag ? { "If-Match": etag } : undefined,
    body: JSON.stringify(body),
  });

export const deleteSetting = (key: string) =>
  apiFetch(`${SETTINGS_BASE}/${encodeURIComponent(key)}`, { method: "DELETE" });
