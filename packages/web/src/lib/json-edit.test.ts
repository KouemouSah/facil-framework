import { describe, it, expect } from "vitest";
import { parseJsonObject, prettyJson } from "./json-edit";

describe("parseJsonObject", () => {
  it("treats empty / whitespace as an empty object", () => {
    expect(parseJsonObject("")).toEqual({ value: {}, valid: true, error: null });
    expect(parseJsonObject("   \n  ")).toEqual({ value: {}, valid: true, error: null });
  });

  it("parses a valid JSON object", () => {
    expect(parseJsonObject('{"a": 1, "b": [2, 3]}')).toEqual({
      value: { a: 1, b: [2, 3] },
      valid: true,
      error: null,
    });
  });

  it("rejects malformed JSON", () => {
    const r = parseJsonObject("{not json}");
    expect(r.valid).toBe(false);
    expect(r.value).toBeUndefined();
    expect(r.error).toBe("Invalid JSON");
  });

  it("rejects arrays and primitives (backend field is a dict)", () => {
    for (const bad of ["[1, 2]", "42", '"text"', "true", "null"]) {
      const r = parseJsonObject(bad);
      expect(r.valid).toBe(false);
      expect(r.error).toBe("Must be a JSON object");
    }
  });
});

describe("prettyJson", () => {
  it("renders nullish and empty objects as empty string", () => {
    expect(prettyJson(null)).toBe("");
    expect(prettyJson(undefined)).toBe("");
    expect(prettyJson({})).toBe("");
  });

  it("pretty-prints a non-empty object with 2-space indent", () => {
    expect(prettyJson({ a: 1 })).toBe('{\n  "a": 1\n}');
  });

  it("round-trips with parseJsonObject", () => {
    const value = { mon: ["09:00-17:00"], sat: [] };
    const text = prettyJson(value);
    expect(parseJsonObject(text)).toEqual({ value, valid: true, error: null });
  });
});
