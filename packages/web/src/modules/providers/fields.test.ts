import { describe, it, expect } from "vitest";
import {
  buildProviderFields, configFieldToFieldDef, createInitial, flattenProvider, splitPayload,
} from "./fields";
import type { ConfigField, Provider } from "./api";

const SCHEMA: ConfigField[] = [
  { key: "endpoint", label: "Endpoint", type: "text", required: false, default: null, hint: "http://minio:9000" },
  { key: "port", label: "Port", type: "number", required: false, default: 587, hint: "" },
  { key: "use_tls", label: "Use TLS", type: "boolean", required: false, default: true, hint: "" },
  { key: "paths", label: "Paths", type: "json", required: false, default: ["boot"], hint: "" },
];

describe("configFieldToFieldDef", () => {
  it("maps backend field types to RecordForm control types", () => {
    expect(configFieldToFieldDef(SCHEMA[0]).type).toBe("text");
    expect(configFieldToFieldDef(SCHEMA[1]).type).toBe("number");
    expect(configFieldToFieldDef(SCHEMA[2]).type).toBe("checkbox");
    expect(configFieldToFieldDef(SCHEMA[3]).type).toBe("json");
  });
  it("carries name/label/required and drops empty hints", () => {
    expect(configFieldToFieldDef(SCHEMA[1])).toMatchObject({ name: "port", label: "Port", required: false });
    expect(configFieldToFieldDef(SCHEMA[1]).hint).toBeUndefined();
    expect(configFieldToFieldDef(SCHEMA[0]).hint).toBe("http://minio:9000");
  });
});

describe("buildProviderFields", () => {
  it("appends the provider-level knobs after the guided config fields", () => {
    const names = buildProviderFields(SCHEMA).map((f) => f.name);
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
