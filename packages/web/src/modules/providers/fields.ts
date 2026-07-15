import type { FieldDef } from "@/components/ui/record-form";
import { fieldSpecToFieldDef } from "@/lib/schema/to-field-def";
import type { Locale } from "@/lib/schema/types";
import type { ConfigField, Provider } from "./api";

/** One declarative backend config field → a RecordForm FieldDef (guided form,
 *  rendered from the backend schema — the single source of truth, no drift).
 *  `ConfigField` IS `FieldSpec` (Task 3) — this is now a locale-bound alias
 *  for `fieldSpecToFieldDef`, kept so providers call sites read unchanged.
 *  @deprecated call `fieldSpecToFieldDef` directly for new code. */
export function configFieldToFieldDef(cf: ConfigField, locale: Locale): FieldDef {
  return fieldSpecToFieldDef(cf, locale);
}

// Provider-level fields appended after the (guided, per-kind) config fields.
// `secret_ref` is a POINTER into the secret store — never the secret itself.
export function buildProviderFields(schema: ConfigField[], locale: Locale): FieldDef[] {
  return [
    ...schema.map((f) => configFieldToFieldDef(f, locale)),
    { name: "secret_ref", label: "Secret reference",
      hint: "Name in the secret store (e.g. \"minio-creds\") — never paste the secret here." },
    { name: "is_active", label: "Active", type: "checkbox" },
    { name: "rate_limit_per_minute", label: "Rate limit / min", type: "number" },
    { name: "retry_attempts", label: "Retry attempts", type: "number" },
    { name: "timeout_seconds", label: "Timeout (s)", type: "number" },
  ];
}

/** Flat RecordForm payload → the backend `ProviderIn` body. The config-schema keys
 *  are re-nested under `config`; the provider-level knobs stay top-level. */
export function splitPayload(
  payload: Record<string, unknown>, schemaKeys: string[],
): Record<string, unknown> {
  const config: Record<string, unknown> = {};
  for (const k of schemaKeys) if (k in payload) config[k] = payload[k];
  const s = payload.secret_ref;
  return {
    config,
    secret_ref: s == null ? "" : String(s),         // str field, never null
    is_active: payload.is_active === true,
    rate_limit_per_minute: payload.rate_limit_per_minute ?? null,
    retry_attempts: payload.retry_attempts ?? null,
    timeout_seconds: payload.timeout_seconds ?? null,
  };
}

/** Provider row → flat RecordForm `initial` (config keys hoisted to top level so
 *  they line up with the generated guided fields). */
export function flattenProvider(p: Provider): Record<string, unknown> {
  return {
    ...p.config,
    secret_ref: p.secret_ref,
    is_active: p.is_active,
    rate_limit_per_minute: p.rate_limit_per_minute,
    retry_attempts: p.retry_attempts,
    timeout_seconds: p.timeout_seconds,
  };
}

/** Seed a create form from the schema defaults (+ active by default). */
export function createInitial(schema: ConfigField[]): Record<string, unknown> {
  const init: Record<string, unknown> = { is_active: true };
  for (const f of schema) if (f.default != null) init[f.key] = f.default;
  return init;
}
