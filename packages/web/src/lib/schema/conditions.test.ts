import { describe, expect, it } from "vitest";
import { isRequired, isVisible } from "./conditions";
import type { FieldSpec } from "./types";

const L = { en: "X", fr: "X", es: "X" };
const base: FieldSpec = {
  key: "vat_no", type: "string", widget: "plain", label: L, hint: {},
  required: false, default: null, options: [], relation_resource: "",
  relation_filter: {}, group: "", order: 0, col_span: 1, indexed: false,
  rules: {
    visible_if: { field: "taxable", op: "eq", value: true },
    required_if: { field: "taxable", op: "eq", value: true },
  },
};

describe("conditions (mirror of app/core/schema/conditions.py)", () => {
  it("hides the field when the condition is not met", () => {
    expect(isVisible(base, { taxable: false })).toBe(false);
    expect(isVisible(base, { taxable: true })).toBe(true);
  });

  it("never requires an invisible field", () => {
    expect(isRequired(base, { taxable: false })).toBe(false);
    expect(isRequired(base, { taxable: true })).toBe(true);
  });

  it("treats a field with no condition as always visible", () => {
    expect(isVisible({ ...base, rules: {} }, {})).toBe(true);
  });
});
