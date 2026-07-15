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

  it("number step: rejects non-multiples, accepts multiples", () => {
    const s = rulesToZod({ key: "q", type: "number", rules: { step: 5 } } as FieldSpec);
    expect(s.safeParse("7").success).toBe(false);
    expect(s.safeParse("10").success).toBe(true);
  });

  it("date min (static ISO): rejects earlier dates", () => {
    const s = rulesToZod({ key: "d", type: "date", rules: { min: "2026-01-01" } } as FieldSpec);
    expect(s.safeParse("2025-12-31").success).toBe(false);
    expect(s.safeParse("2026-06-01").success).toBe(true);
  });

  it("number step: float-tolerant — accepts a fractional multiple the backend Decimal check accepts", () => {
    // 0.3 % 0.1 === 0.09999999999999998 in binary float — a strict `=== 0`
    // check would wrongly reject this and block a valid save.
    const s = rulesToZod({ key: "q", type: "number", rules: { step: 0.1 } } as FieldSpec);
    expect(s.safeParse("0.3").success).toBe(true);
  });

  it("number step: integer-step common case still rejects/accepts correctly", () => {
    const s = rulesToZod({ key: "q", type: "number", rules: { step: 5 } } as FieldSpec);
    expect(s.safeParse("7").success).toBe(false);
    expect(s.safeParse("10").success).toBe(true);
  });
});
