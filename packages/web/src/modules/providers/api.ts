import { apiFetch } from "@/lib/api";

export const PROVIDERS_BASE = "/api/v1/admin/providers";
export const SETTINGS_BASE = "/api/v1/admin/settings";

// Backend capability allowlist (app.models.provider.CAPABILITIES), in display order.
export const CAPABILITIES = ["storage", "llm", "email", "secrets", "auth", "payment"] as const;
export type Capability = (typeof CAPABILITIES)[number];

/** Declarative, non-secret config field (backend `config_schema` — source of truth). */
export interface ConfigField {
  key: string;
  label: string;
  type: "text" | "number" | "boolean" | "json";
  required: boolean;
  default: unknown;
  hint: string;
}
export interface RegisteredType {
  capability: string;
  provider_code: string;
  config_schema: ConfigField[];
}
export interface Provider {
  capability: string;
  provider_code: string;
  config: Record<string, unknown>;
  secret_ref: string;
  is_default: boolean;
  is_active: boolean;
  rate_limit_per_minute: number;
  retry_attempts: number;
  timeout_seconds: number;
  updated_by?: string | null;
  etag?: string;
}
export interface HealthResult {
  capability: string;
  provider_code: string;
  ok: boolean;
  detail: string;
}
export interface RoutingView {
  routing: Record<string, string>;
  providers: Record<string, { kind: string; endpoint?: string; model?: string; api_key_secret?: string }>;
}
export type RoutingCheck = Record<string, { provider: string; model?: string; ok: boolean; detail: string }>;

export const listProviders = (capability?: string) =>
  apiFetch<Provider[]>(`${PROVIDERS_BASE}/${capability ? `?capability=${capability}` : ""}`);

export const listRegistered = () =>
  apiFetch<RegisteredType[]>(`${PROVIDERS_BASE}/registered`);

export const getProvider = (cap: string, code: string) =>
  apiFetch<Provider>(`${PROVIDERS_BASE}/${cap}/${code}`);

export const checkProvider = (cap: string, code: string) =>
  apiFetch<HealthResult>(`${PROVIDERS_BASE}/${cap}/${code}/check`, { method: "POST" });

export const getRouting = () =>
  apiFetch<RoutingView>(`${PROVIDERS_BASE}/llm/routing`);

export const checkRouting = () =>
  apiFetch<RoutingCheck>(`${PROVIDERS_BASE}/llm/routing/check`, { method: "POST" });
