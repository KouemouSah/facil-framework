import { describe, expect, it } from "vitest";
import {
  buildFieldDefFields, flattenDefinition, isSortable, splitCustomPayload,
  TARGETS, TYPE_OPTIONS, widgetsFor,
} from "./fields";
import type { Definition } from "./api";

describe("the field-creation form is itself schema-driven", () => {
  it("offers exactly the 15 types", () => {
    expect(TYPE_OPTIONS).toHaveLength(15);
    expect(TYPE_OPTIONS.map((o) => o.value)).toContain("relation");
  });

  it("narrows the widget list to the selected type", () => {
    expect(widgetsFor("string")).toContain("color");
    expect(widgetsFor("string")).not.toContain("rating");
    expect(widgetsFor("number")).toContain("rating");
  });

  it("marks key immutable in edit mode (renaming would orphan stored values)", () => {
    const def = buildFieldDefFields("en").find((f) => f.name === "key");
    expect(def?.immutable).toBe(true);
  });

  it("requires the three locale labels", () => {
    const names = buildFieldDefFields("en").map((f) => f.name);
    expect(names).toEqual(expect.arrayContaining(["label_en", "label_fr", "label_es"]));
    for (const n of ["label_en", "label_fr", "label_es"]) {
      expect(buildFieldDefFields("en").find((f) => f.name === n)?.required).toBe(true);
    }
  });
});

describe("EXTENSIBLE_TARGETS mirror", () => {
  it("lists exactly the four opt-in targets (mirrors app/core/schema/registry.py)", () => {
    expect(TARGETS).toEqual([
      "organization.custom_fields", "org_unit.custom_fields",
      "site.custom_fields", "party.custom_fields",
    ]);
  });
});

describe("widgetsFor — full WIDGETS_BY_TYPE mirror", () => {
  it("covers every one of the 15 types with a non-empty list", () => {
    for (const { value } of TYPE_OPTIONS) {
      expect(widgetsFor(value).length).toBeGreaterThan(0);
    }
  });
  it("returns an empty array for an unknown type (never throws)", () => {
    expect(widgetsFor("not-a-type")).toEqual([]);
  });
});

describe("isSortable — the not-sortable-unless-ready rule", () => {
  it("is false when not indexed at all", () => {
    expect(isSortable({ indexed: false, index_state: "none" })).toBe(false);
  });
  it("is false while an index build is pending or has failed", () => {
    expect(isSortable({ indexed: true, index_state: "pending" })).toBe(false);
    expect(isSortable({ indexed: true, index_state: "failed" })).toBe(false);
  });
  it("is true only once the index is actually ready", () => {
    expect(isSortable({ indexed: true, index_state: "ready" })).toBe(true);
  });
});

describe("splitCustomPayload — nests custom values under custom_fields, never flat", () => {
  it("keeps declared base keys top-level and buckets everything else under custom_fields", () => {
    const { base, customFields } = splitCustomPayload(
      { code: "HQ", name: "Head office", department: "Sales", floor: "3" },
      ["code", "name"],
    );
    expect(base).toEqual({ code: "HQ", name: "Head office" });
    expect(customFields).toEqual({ department: "Sales", floor: "3" });
  });
  it("returns an empty customFields object when nothing beyond the base keys is present", () => {
    const { customFields } = splitCustomPayload({ code: "HQ" }, ["code"]);
    expect(customFields).toEqual({});
  });
});

describe("flattenDefinition — Definition row -> RecordForm initial (label/hint dicts flattened)", () => {
  const row: Definition = {
    id: "d1", organization_id: "o1", target: "site.custom_fields",
    key: "floor", type: "number", widget: "plain",
    label: { en: "Floor", fr: "Étage", es: "Piso" },
    hint: { en: "", fr: "", es: "" },
    required: false, default: null, rules: {}, options: [],
    relation_resource: "", relation_filter: {},
    group: "", order: 0, col_span: 1, indexed: false, index_state: "none",
    inherit_to_suborgs: false, archived: false, is_active: true, etag: "abc",
  };

  it("flattens the i18n label dict into label_en/fr/es", () => {
    const flat = flattenDefinition(row);
    expect(flat.label_en).toBe("Floor");
    expect(flat.label_fr).toBe("Étage");
    expect(flat.label_es).toBe("Piso");
  });

  it("wraps the array-shaped `options` and the Any-typed `default` in an object envelope "
    + "(RecordForm's json control only accepts objects, never arrays/scalars)", () => {
    const withOptions = flattenDefinition({ ...row, type: "select", options: [{ value: "a", label: { en: "A", fr: "A", es: "A" } }], default: 42 });
    expect(withOptions.options).toEqual({ items: [{ value: "a", label: { en: "A", fr: "A", es: "A" } }] });
    expect(withOptions.default).toEqual({ value: 42 });
  });
});
