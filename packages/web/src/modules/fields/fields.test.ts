import { describe, expect, it } from "vitest";
import {
  buildDefinitionPayload, buildFieldDefFields, canRenderCreateSurface, flattenDefinition,
  isSortable, splitCustomPayload, TARGETS, TYPE_OPTIONS, widgetsFor,
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

describe("canRenderCreateSurface (Fix wave 1, Important #3)", () => {
  it("never renders the create surface without fields.manage, even when isNew", () => {
    // The exact regression: `?new=1&sel=<anything>` makes the page's
    // `surfaceOpen` true via the `sel` disjunct, and the render dispatch then
    // branches on `isNew` alone — this predicate is the fix, gating the
    // CreateSurface render itself on `canManage` too.
    expect(canRenderCreateSurface(true, false)).toBe(false);
  });
  it("renders when the caller can manage and is creating", () => {
    expect(canRenderCreateSurface(true, true)).toBe(true);
  });
  it("is false outside create (the edit branch is gated by readOnly instead)", () => {
    expect(canRenderCreateSurface(false, true)).toBe(false);
    expect(canRenderCreateSurface(false, false)).toBe(false);
  });
});

describe("EXTENSIBLE_TARGETS mirror", () => {
  it("lists exactly the three opt-in targets (mirrors app/core/schema/registry.py)", () => {
    // `party.custom_fields` is deliberately absent — Party is a global
    // directory row with no organisation to own a definition set (Fix wave 1,
    // SP1 Task 15). Do not re-add it here without re-admitting it server-side
    // first.
    expect(TARGETS).toEqual([
      "organization.custom_fields", "org_unit.custom_fields", "site.custom_fields",
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

describe("buildDefinitionPayload — flat RecordForm payload -> DefinitionIn (Also: Minor)", () => {
  const base = {
    key: "floor", type: "number", widget: "plain",
    label_en: "Floor", label_fr: "Étage", label_es: "Piso",
    hint_en: "", hint_fr: "", hint_es: "",
    required: true, group: "geo", order: "2", col_span: "2", indexed: true,
    inherit_to_suborgs: true,
    relation_resource: "", relation_filter: {}, rules: {},
    options: { items: [] }, default: { value: null },
  };

  it("re-nests the flat label_en/fr/es and hint_en/fr/es back into i18n dicts", () => {
    const out = buildDefinitionPayload(base, "site.custom_fields");
    expect(out.label).toEqual({ en: "Floor", fr: "Étage", es: "Piso" });
    expect(out.hint).toEqual({ en: "", fr: "", es: "" });
  });

  it("coerces required/indexed/inherit_to_suborgs to real booleans (not just truthy)", () => {
    const out = buildDefinitionPayload(base, "site.custom_fields");
    expect(out.required).toBe(true);
    expect(out.indexed).toBe(true);
    expect(out.inherit_to_suborgs).toBe(true);
    const off = buildDefinitionPayload({ ...base, required: "true" }, "site.custom_fields");
    // A stray string "true" (not the literal boolean) must NOT coerce to true —
    // RecordForm's checkbox always sends a real boolean, but this pins the
    // adapter doesn't silently truthy-coerce a differently-shaped payload.
    expect(off.required).toBe(false);
  });

  it("coerces order/col_span to numbers, defaulting order to 0 and col_span to 1", () => {
    const out = buildDefinitionPayload(base, "site.custom_fields");
    expect(out.order).toBe(2);
    expect(out.col_span).toBe(2);
    const blank = buildDefinitionPayload({ ...base, order: "", col_span: "" }, "site.custom_fields");
    expect(blank.order).toBe(0);
    expect(blank.col_span).toBe(1);
  });

  it("unwraps the JSON envelope for options (array) and default (Any) — the inverse of "
    + "flattenDefinition's wrap", () => {
    const withOptions = buildDefinitionPayload(
      { ...base, type: "select",
        options: { items: [{ value: "a", label: { en: "A", fr: "A", es: "A" } }] },
        default: { value: "a" } },
      "site.custom_fields");
    expect(withOptions.options).toEqual([{ value: "a", label: { en: "A", fr: "A", es: "A" } }]);
    expect(withOptions.default).toBe("a");
  });

  it("defaults default/options/relation_filter/rules when the envelope is malformed or absent", () => {
    const out = buildDefinitionPayload({ key: "k", type: "string" }, "site.custom_fields");
    expect(out.default).toBeNull();
    expect(out.options).toEqual([]);
    expect(out.relation_filter).toEqual({});
    expect(out.rules).toEqual({});
  });

  it("stamps the caller-supplied target onto the payload", () => {
    expect(buildDefinitionPayload(base, "org_unit.custom_fields").target).toBe("org_unit.custom_fields");
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
