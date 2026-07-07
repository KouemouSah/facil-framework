import { describe, it, expect } from "vitest";
import {
  filterSettings, formatValuePreview, fromSettingValue, groupByScope, scopesOf, toSettingValue,
} from "./value";
import type { Setting } from "./api";

const mk = (over: Partial<Setting>): Setting => ({
  key: "k", value: null, value_type: "string", scope: "global", secret_ref: "",
  is_active: true, name: { es: null, fr: null, en: null }, description: null, ...over,
});

const SET: Setting[] = [
  mk({ key: "ai.routing", scope: "ai", description: "role routing" }),
  mk({ key: "email.provider", scope: "email", name: { es: null, fr: null, en: "Email provider" } }),
  mk({ key: "ai.providers", scope: "ai" }),
];

describe("scopesOf", () => {
  it("returns the distinct scopes, sorted", () => {
    expect(scopesOf(SET)).toEqual(["ai", "email"]);
  });
});

describe("filterSettings", () => {
  it("filters by scope (order preserved)", () => {
    expect(filterSettings(SET, "", "ai").map((s) => s.key)).toEqual(["ai.routing", "ai.providers"]);
  });
  it("searches across key / name / description", () => {
    expect(filterSettings(SET, "routing", "").map((s) => s.key)).toEqual(["ai.routing"]);
    expect(filterSettings(SET, "email provider", "").map((s) => s.key)).toEqual(["email.provider"]);
    expect(filterSettings(SET, "", "").length).toBe(3);
  });
});

describe("groupByScope", () => {
  it("groups by scope (scopes + keys sorted)", () => {
    const g = groupByScope(SET);
    expect(g.map(([scope]) => scope)).toEqual(["ai", "email"]);
    expect(g[0][1].map((s) => s.key)).toEqual(["ai.providers", "ai.routing"]);
  });
});

describe("toSettingValue", () => {
  it("picks the typed value per value_type", () => {
    expect(toSettingValue("string", { text: "smtp", bool: false, json: {} })).toEqual({ ok: true, value: "smtp" });
    expect(toSettingValue("number", { text: "587", bool: false, json: {} })).toEqual({ ok: true, value: 587 });
    expect(toSettingValue("boolean", { text: "", bool: true, json: {} })).toEqual({ ok: true, value: true });
    expect(toSettingValue("json", { text: "", bool: false, json: { a: 1 } })).toEqual({ ok: true, value: { a: 1 } });
  });
  it("rejects a non-numeric number", () => {
    expect(toSettingValue("number", { text: "abc", bool: false, json: {} })).toEqual({ ok: false, error: "number" });
    expect(toSettingValue("number", { text: "", bool: false, json: {} })).toEqual({ ok: false, error: "number" });
  });
});

describe("fromSettingValue", () => {
  it("seeds the right field per type", () => {
    expect(fromSettingValue({ value: 587, value_type: "number" }).text).toBe("587");
    expect(fromSettingValue({ value: true, value_type: "boolean" }).bool).toBe(true);
    expect(fromSettingValue({ value: { a: 1 }, value_type: "json" }).json).toEqual({ a: 1 });
    expect(fromSettingValue({ value: null, value_type: "string" }).text).toBe("");
  });
});

describe("formatValuePreview", () => {
  it("renders scalars and compact json, truncating", () => {
    expect(formatValuePreview("smtp", "string")).toBe("smtp");
    expect(formatValuePreview(587, "number")).toBe("587");
    expect(formatValuePreview(true, "boolean")).toBe("true");
    expect(formatValuePreview({ a: 1 }, "json")).toBe('{"a":1}');
    expect(formatValuePreview(null, "string")).toBe("—");
    expect(formatValuePreview("x".repeat(90), "string").endsWith("…")).toBe(true);
  });
});
