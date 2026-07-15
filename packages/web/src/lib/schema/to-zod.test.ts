import { describe, expect, it } from "vitest";
import { rulesToZod } from "./to-zod";
import type { FieldSpec } from "./types";

const L = { en: "X", fr: "X", es: "X" };
const spec = (over: Partial<FieldSpec>): FieldSpec => ({
  key: "f", type: "string", widget: "plain", label: L, hint: {}, required: false,
  default: null, rules: {}, options: [], relation_resource: "", relation_filter: {},
  group: "", order: 0, col_span: 1, indexed: false, index_state: "none", ...over,
});

describe("rulesToZod", () => {
  it("enforces max_length", () => {
    const z = rulesToZod(spec({ rules: { max_length: 3 } }));
    expect(z.safeParse("abcd").success).toBe(false);
    expect(z.safeParse("abc").success).toBe(true);
  });

  it("enforces numeric bounds on number", () => {
    const z = rulesToZod(spec({ type: "number", rules: { min: 0, max: 100 } }));
    expect(z.safeParse("150").success).toBe(false);
    expect(z.safeParse("50").success).toBe(true);
  });

  it("enforces pattern", () => {
    const z = rulesToZod(spec({ rules: { pattern: "^[A-Z]{2}$" } }));
    expect(z.safeParse("gq").success).toBe(false);
    expect(z.safeParse("GQ").success).toBe(true);
  });

  it("rejects an empty value when required", () => {
    const z = rulesToZod(spec({ required: true }));
    expect(z.safeParse("").success).toBe(false);
  });

  it("accepts an empty value when optional", () => {
    expect(rulesToZod(spec({})).safeParse("").success).toBe(true);
  });
});
