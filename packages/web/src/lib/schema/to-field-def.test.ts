import { describe, expect, it } from "vitest";
import { fieldSpecToFieldDef } from "./to-field-def";
import type { FieldSpec } from "./types";

const L = { en: "Amount", fr: "Montant", es: "Importe" };
const spec = (over: Partial<FieldSpec>): FieldSpec => ({
  key: "amount", type: "money", widget: "plain", label: L, hint: {}, required: true,
  default: null, rules: {}, options: [], relation_resource: "", relation_filter: {},
  group: "billing", order: 2, col_span: 2, indexed: true, ...over,
});

describe("fieldSpecToFieldDef", () => {
  it("maps key/label/required/colSpan onto the RecordForm contract", () => {
    const d = fieldSpecToFieldDef(spec({}), "fr");
    expect(d.name).toBe("amount");
    expect(d.label).toBe("Montant");   // localised, not the raw i18n object
    expect(d.required).toBe(true);
    expect(d.colSpan).toBe(2);
  });

  it("carries type AND widget so renderControl can dispatch on the pair", () => {
    const d = fieldSpecToFieldDef(spec({ type: "string", widget: "color" }), "en");
    expect(d.type).toBe("string");
    expect(d.widget).toBe("color");
  });

  it("maps select options to RecordForm's selectOptions", () => {
    const d = fieldSpecToFieldDef(
      spec({ type: "select", widget: "dropdown",
             options: [{ value: "draft", label: { en: "Draft", fr: "Brouillon", es: "Borrador" } }] }),
      "fr");
    expect(d.selectOptions).toEqual([{ value: "draft", label: "Brouillon" }]);
  });

  it("carries the relation resource", () => {
    const d = fieldSpecToFieldDef(
      spec({ type: "relation", widget: "combobox", relation_resource: "countries" }), "en");
    expect(d.relationResource).toBe("countries");
  });

  it("falls back to English when the requested locale is missing", () => {
    const d = fieldSpecToFieldDef(spec({ label: { en: "Amount", fr: "", es: "" } }), "fr");
    expect(d.label).toBe("Amount");
  });
});
