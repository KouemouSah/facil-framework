import { describe, it, expect } from "vitest";
import { flattenRules, nestRules, ruleSanity, UI_RULE_KEYS } from "./rules-adapter";

describe("rules-adapter", () => {
  it("flattenRules splits UI keys from advanced", () => {
    const { form, advanced } = flattenRules({ min_length: 2, pattern: "^x$", foo: 1 } as any);
    expect(form.rule_min_length).toBe(2);
    expect(form.rule_pattern).toBe("^x$");
    expect(advanced).toEqual({ foo: 1 });
  });
  it("nestRules merges UI + advanced and coalesces min/max", () => {
    const { rules, errorKey } = nestRules({ rule_date_min: "2026-01-01" }, { foo: 1 });
    expect(errorKey).toBeUndefined();
    expect(rules).toEqual({ min: "2026-01-01", foo: 1 });
  });
  it("nestRules rejects a UI-owned key placed in Advanced JSON (disjoint guard) with an i18n errorKey", () => {
    const { errorKey, errorParams } = nestRules({}, { min_length: 3 });
    expect(errorKey).toBe("advanced_has_ui_key");
    expect(errorParams).toEqual({ key: "min_length" });
  });
  it("UI_RULE_KEYS covers the managed set", () => {
    expect(UI_RULE_KEYS).toContain("must_be_true");
    expect(UI_RULE_KEYS).toContain("allowed_extensions");
  });
  it("round-trips visible_if / required_if through advanced", () => {
    const cond = { field: "type", op: "eq" as const, value: "relation" };
    const { form, advanced } = flattenRules({ visible_if: cond, foo: 1 } as any);
    expect(advanced.visible_if).toEqual(cond);
    const { rules, errorKey } = nestRules(form, advanced);
    expect(errorKey).toBeUndefined();
    expect((rules as any).visible_if).toEqual(cond);
    expect((rules as any).foo).toBe(1);
  });
  it("disjoint guard rejects EVERY UI-owned key in Advanced JSON", () => {
    for (const k of UI_RULE_KEYS) {
      const { errorKey, errorParams } = nestRules({}, { [k]: 1 });
      expect(errorKey, `key ${k} should be rejected`).toBe("advanced_has_ui_key");
      expect(errorParams, `key ${k} should be reported`).toEqual({ key: k });
    }
  });
});

describe("ruleSanity", () => {
  it("flags min>max and bad regex, via a stable i18n errorKey (never raw English)", () => {
    expect(ruleSanity({ rule_min: 5, rule_max: 1 }).errorKey).toBe("min_gt_max");
    expect(ruleSanity({ rule_pattern: "([" }).errorKey).toBe("bad_regex");
    expect(ruleSanity({ rule_min_length: 1, rule_max_length: 3 }).errorKey).toBeUndefined();
  });
  it("flags min_length>max_length and min_items>max_items", () => {
    expect(ruleSanity({ rule_min_length: 10, rule_max_length: 2 }).errorKey).toBe("minlen_gt_maxlen");
    expect(ruleSanity({ rule_min_items: 5, rule_max_items: 2 }).errorKey).toBe("minitems_gt_maxitems");
  });
  it("flags money_min>money_max (Finding 2)", () => {
    expect(ruleSanity({ rule_money_min: 100, rule_money_max: 10 }).errorKey).toBe("money_min_gt_max");
    expect(ruleSanity({ rule_money_min: 10, rule_money_max: 100 }).errorKey).toBeUndefined();
  });
  it("flags date_min>date_max for a static ISO pair (Finding 2)", () => {
    expect(ruleSanity({ rule_date_min: "2026-06-01", rule_date_max: "2026-01-01" }).errorKey)
      .toBe("date_min_gt_max");
    expect(ruleSanity({ rule_date_min: "2026-01-01", rule_date_max: "2026-06-01" }).errorKey)
      .toBeUndefined();
  });
  it("skips the date check when EITHER bound is the \"today\"/\"now\" token (ordering unknown statically)", () => {
    expect(ruleSanity({ rule_date_min: "today", rule_date_max: "2020-01-01" }).errorKey).toBeUndefined();
    expect(ruleSanity({ rule_date_min: "2099-01-01", rule_date_max: "now" }).errorKey).toBeUndefined();
    expect(ruleSanity({ rule_date_min: "today", rule_date_max: "now" }).errorKey).toBeUndefined();
  });
  it("flags a non-positive step", () => {
    expect(ruleSanity({ rule_step: 0 }).errorKey).toBe("step_not_positive");
    expect(ruleSanity({ rule_step: -1 }).errorKey).toBe("step_not_positive");
    expect(ruleSanity({ rule_step: 5 }).errorKey).toBeUndefined();
  });
  it("ignores blank/undefined values entirely", () => {
    expect(ruleSanity({}).errorKey).toBeUndefined();
    expect(ruleSanity({ rule_min: "", rule_max: "" }).errorKey).toBeUndefined();
  });
  it("accepts a compilable pattern", () => {
    expect(ruleSanity({ rule_pattern: "^[a-z]+$" }).errorKey).toBeUndefined();
  });
});
