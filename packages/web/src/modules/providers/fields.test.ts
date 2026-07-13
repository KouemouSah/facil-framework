import { describe, it, expect } from "vitest";
import {
  buildProviderFields, configFieldToFieldDef, createInitial, flattenProvider, splitPayload,
} from "./fields";
import type { ConfigField, Provider } from "./api";

// Task 3 changed the wire shape: `ConfigField` IS `FieldSpec` now — i18n
// `label`/`hint` dicts (backend's `cfg()` mirrors the English label into
// en/fr/es today), a `widget`, and the full FieldSpec envelope, not the old
// 4-type/plain-string shape. These fixtures mirror the real output of
// `Provider.config_schema()` (app/core/providers/base.py:cfg()).
const L = (s: string) => ({ en: s, fr: s, es: s });
const SCHEMA: ConfigField[] = [
  { key: "endpoint", type: "string", widget: "plain", label: L("Endpoint"), hint: L("http://minio:9000"),
    required: false, default: null, rules: {}, options: [], relation_resource: "", relation_filter: {},
    group: "", order: 0, col_span: 1, indexed: false },
  { key: "port", type: "number", widget: "plain", label: L("Port"), hint: {},
    required: false, default: 587, rules: {}, options: [], relation_resource: "", relation_filter: {},
    group: "", order: 0, col_span: 1, indexed: false },
  { key: "use_tls", type: "boolean", widget: "checkbox", label: L("Use TLS"), hint: {},
    required: false, default: true, rules: {}, options: [], relation_resource: "", relation_filter: {},
    group: "", order: 0, col_span: 1, indexed: false },
  { key: "paths", type: "json", widget: "raw", label: L("Paths"), hint: {},
    required: false, default: ["boot"], rules: {}, options: [], relation_resource: "", relation_filter: {},
    group: "", order: 0, col_span: 1, indexed: false },
];

describe("configFieldToFieldDef", () => {
  it("maps backend FieldSpec types straight through (RecordForm dispatches on type+widget)", () => {
    expect(configFieldToFieldDef(SCHEMA[0], "en").type).toBe("string");
    expect(configFieldToFieldDef(SCHEMA[1], "en").type).toBe("number");
    expect(configFieldToFieldDef(SCHEMA[2], "en").type).toBe("boolean");
    expect(configFieldToFieldDef(SCHEMA[3], "en").type).toBe("json");
  });
  it("carries the widget alongside the type", () => {
    expect(configFieldToFieldDef(SCHEMA[2], "en").widget).toBe("checkbox");
  });
  it("carries name/label (localised)/required and drops empty hints", () => {
    expect(configFieldToFieldDef(SCHEMA[1], "en")).toMatchObject({ name: "port", label: "Port", required: false });
    expect(configFieldToFieldDef(SCHEMA[1], "en").hint).toBeUndefined();
    expect(configFieldToFieldDef(SCHEMA[0], "en").hint).toBe("http://minio:9000");
  });
});

describe("buildProviderFields", () => {
  it("appends the provider-level knobs after the guided config fields", () => {
    const names = buildProviderFields(SCHEMA, "en").map((f) => f.name);
    expect(names.slice(0, 4)).toEqual(["endpoint", "port", "use_tls", "paths"]);
    expect(names).toContain("secret_ref");
    expect(names).toContain("is_active");
    expect(names).toContain("timeout_seconds");
  });
});

describe("splitPayload", () => {
  it("re-nests schema keys under config, keeps knobs top-level, never nulls secret_ref", () => {
    const body = splitPayload(
      { endpoint: "http://x", port: 587, use_tls: true, paths: ["a"],
        secret_ref: null, is_active: true, rate_limit_per_minute: 10,
        retry_attempts: null, timeout_seconds: 30 },
      ["endpoint", "port", "use_tls", "paths"],
    );
    expect(body.config).toEqual({ endpoint: "http://x", port: 587, use_tls: true, paths: ["a"] });
    expect(body.secret_ref).toBe("");        // null coerced to "" (str field)
    expect(body.is_active).toBe(true);
    expect(body.rate_limit_per_minute).toBe(10);
    expect(body.timeout_seconds).toBe(30);
    // Provider-level keys never leak into config.
    expect((body.config as Record<string, unknown>).secret_ref).toBeUndefined();
  });
  it("coerces a missing is_active to false", () => {
    expect(splitPayload({}, []).is_active).toBe(false);
  });
});

describe("flattenProvider / createInitial", () => {
  it("hoists config keys to the top level for the edit form", () => {
    const p = {
      capability: "storage", provider_code: "minio",
      config: { endpoint: "http://x", bucket: "b" }, secret_ref: "minio-creds",
      is_default: true, is_active: true, rate_limit_per_minute: 0, retry_attempts: 3, timeout_seconds: 30,
    } as Provider;
    const init = flattenProvider(p);
    expect(init).toMatchObject({ endpoint: "http://x", bucket: "b", secret_ref: "minio-creds", is_active: true });
  });
  it("seeds a create form from schema defaults + active", () => {
    const init = createInitial(SCHEMA);
    expect(init).toMatchObject({ is_active: true, port: 587, use_tls: true, paths: ["boot"] });
    expect("endpoint" in init).toBe(false); // null default not seeded
  });
});
