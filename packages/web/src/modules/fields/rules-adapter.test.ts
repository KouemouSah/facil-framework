import { describe, it, expect } from "vitest";
import { flattenRules, nestRules, UI_RULE_KEYS } from "./rules-adapter";

describe("rules-adapter", () => {
  it("flattenRules splits UI keys from advanced", () => {
    const { form, advanced } = flattenRules({ min_length: 2, pattern: "^x$", foo: 1 } as any);
    expect(form.rule_min_length).toBe(2);
    expect(form.rule_pattern).toBe("^x$");
    expect(advanced).toEqual({ foo: 1 });
  });
  it("nestRules merges UI + advanced and coalesces min/max", () => {
    const { rules, error } = nestRules({ rule_date_min: "2026-01-01" }, { foo: 1 });
    expect(error).toBeUndefined();
    expect(rules).toEqual({ min: "2026-01-01", foo: 1 });
  });
  it("nestRules rejects a UI-owned key placed in Advanced JSON (disjoint guard)", () => {
    const { error } = nestRules({}, { min_length: 3 });
    expect(error).toMatch(/min_length/);
  });
  it("UI_RULE_KEYS covers the managed set", () => {
    expect(UI_RULE_KEYS).toContain("must_be_true");
    expect(UI_RULE_KEYS).toContain("allowed_extensions");
  });
  it("round-trips visible_if / required_if through advanced", () => {
    const cond = { field: "type", op: "eq" as const, value: "relation" };
    const { form, advanced } = flattenRules({ visible_if: cond, foo: 1 } as any);
    expect(advanced.visible_if).toEqual(cond);
    const { rules, error } = nestRules(form, advanced);
    expect(error).toBeUndefined();
    expect((rules as any).visible_if).toEqual(cond);
    expect((rules as any).foo).toBe(1);
  });
  it("disjoint guard rejects EVERY UI-owned key in Advanced JSON", () => {
    for (const k of UI_RULE_KEYS) {
      const { error } = nestRules({}, { [k]: 1 });
      expect(error, `key ${k} should be rejected`).toMatch(new RegExp(k));
    }
  });
});
