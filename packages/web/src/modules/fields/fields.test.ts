import { describe, expect, it } from "vitest";
import {
  buildDefinitionPayload, buildFieldDefFields, canRenderCreateSurface, FIELD_SPEC_TYPES,
  flattenDefinition, isSortable, INDEXABLE_TYPES, RECORD_FORM_ROUND_TRIPPABLE_TYPES,
  RELATION_RESOURCES, splitCustomPayload, STUDIO_OFFERED_TYPES, targetLabelKey, TARGETS,
  TYPE_OPTIONS, WIDGETS_BY_TYPE, widgetsFor,
} from "./fields";
import { ApiError } from "@/lib/api";
import type { Definition } from "./api";
import backendContract from "./__fixtures__/backend-field-contract.json";

// MINORS fix (final fix wave): the contract test pinning the hand-mirrored
// type tables against the backend. See `packages/backend/tests/
// test_field_type_contract_fixture.py`'s module docstring for the mechanism
// (one shared JSON fixture, asserted against from both sides, no live
// network call). This half pins the TS mirror; the backend half pins the
// fixture itself against the live Python constants.
describe("hand-mirrored type tables match the backend contract fixture", () => {
  it("FIELD_TYPES", () => {
    expect(FIELD_SPEC_TYPES).toEqual(backendContract.FIELD_TYPES);
  });
  it("WIDGETS_BY_TYPE", () => {
    expect(WIDGETS_BY_TYPE).toEqual(backendContract.WIDGETS_BY_TYPE);
  });
  it("INDEXABLE_TYPES", () => {
    expect(new Set(INDEXABLE_TYPES)).toEqual(new Set(backendContract.INDEXABLE_TYPES));
  });
  it("RELATION_RESOURCES", () => {
    expect(new Set(RELATION_RESOURCES)).toEqual(new Set(backendContract.RELATION_RESOURCES));
  });
});

describe("the field-creation form is itself schema-driven", () => {
  it("offers exactly the 13 types RecordForm can actually save (money/multiselect excluded)", () => {
    expect(TYPE_OPTIONS).toHaveLength(13);
    expect(TYPE_OPTIONS.map((o) => o.value)).toContain("relation");
  });

  it("never offers money or multiselect — RecordForm cannot round-trip either (IMPORTANT-1 fix)", () => {
    const offered = TYPE_OPTIONS.map((o) => o.value);
    expect(offered).not.toContain("money");
    expect(offered).not.toContain("multiselect");
  });

  it("the Studio's offered set is a SUBSET of what RecordForm can round-trip", () => {
    // The parity rule, pinned: never advertise a type the form cannot save.
    // Also guards the reverse drift — a future type added to FIELD_SPEC_TYPES
    // (the backend mirror) without RecordForm support must fail here, not
    // become silently offerable.
    for (const t of STUDIO_OFFERED_TYPES) {
      expect(RECORD_FORM_ROUND_TRIPPABLE_TYPES).toContain(t);
    }
  });

  it("STUDIO_OFFERED_TYPES + money/multiselect together still cover all 15 backend types", () => {
    // money/multiselect are excluded from the PICKER, not from the backend
    // contract (document_identity still uses them) — this pins that the
    // narrowing removed exactly those two, nothing more.
    const covered = new Set([...STUDIO_OFFERED_TYPES, "money", "multiselect"]);
    expect(covered.size).toBe(FIELD_SPEC_TYPES.length);
    for (const t of FIELD_SPEC_TYPES) expect(covered.has(t)).toBe(true);
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

  it("re-admits seedType into the type picker even when it's money/multiselect", () => {
    // An EXISTING money/multiselect definition (created before this fix, or
    // via a direct API call) must stay editable — its `type` <select> must
    // still offer its own current value, or saving the form would silently
    // coerce it to whatever renders first.
    const moneyField = buildFieldDefFields("en", "money").find((f) => f.name === "type");
    expect(moneyField?.selectOptions?.map((o) => o.value)).toContain("money");
    // A NEW field (no seedType) never gets the unsupported option.
    const newField = buildFieldDefFields("en").find((f) => f.name === "type");
    expect(newField?.selectOptions?.map((o) => o.value)).not.toContain("money");
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

describe("targetLabelKey — dot-free key for next-intl (Task 16 e2e regression)", () => {
  it("strips the .custom_fields suffix so next-intl doesn't mis-parse the dot as nesting", () => {
    expect(targetLabelKey("organization.custom_fields")).toBe("organization");
    expect(targetLabelKey("org_unit.custom_fields")).toBe("org_unit");
    expect(targetLabelKey("site.custom_fields")).toBe("site");
  });
  it("stays unique across all three targets (no collision in the messages object)", () => {
    const keys = TARGETS.map(targetLabelKey);
    expect(new Set(keys).size).toBe(TARGETS.length);
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
    relation_resource: "", relation_filter: {},
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

// Task 5: the type-aware `rule_*` inputs + `rules_advanced` replace the old
// single raw-JSON `rules` field — this pins the re-nesting adapters wired
// into `buildDefinitionPayload` (via `nestRules`/`ruleSanity`, Task 4/5).
describe("buildDefinitionPayload — type-aware rule_* inputs -> rules (Task 5)", () => {
  const base = {
    key: "floor", type: "number", widget: "plain",
    label_en: "Floor", label_fr: "Étage", label_es: "Piso",
    hint_en: "", hint_fr: "", hint_es: "",
    required: false, group: "", order: "0", col_span: "1", indexed: false,
    inherit_to_suborgs: false,
    relation_resource: "", relation_filter: {},
    options: { items: [] }, default: { value: null },
  };

  function captureError(fn: () => unknown): ApiError {
    try { fn(); } catch (e) { return e as ApiError; }
    throw new Error("expected buildDefinitionPayload to throw");
  }

  it("nests rule_min/rule_max into rules.min/rules.max", () => {
    const out = buildDefinitionPayload({ ...base, rule_min: 1, rule_max: 10 }, "site.custom_fields");
    expect(out.rules).toEqual({ min: 1, max: 10 });
  });

  // Finding 4 (test gap): money and date had NO round-trip coverage at all —
  // which is how Finding 2's missing ruleSanity checks went unnoticed.
  it("nests rule_money_min/rule_money_max into rules.min/rules.max", () => {
    const out = buildDefinitionPayload(
      { ...base, type: "money", rule_money_min: 5, rule_money_max: 500 }, "site.custom_fields");
    expect(out.rules).toEqual({ min: 5, max: 500 });
  });

  it("nests rule_date_min/rule_date_max into rules.min/rules.max", () => {
    const out = buildDefinitionPayload(
      { ...base, type: "date", rule_date_min: "2026-01-01", rule_date_max: "2026-12-31" }, "site.custom_fields");
    expect(out.rules).toEqual({ min: "2026-01-01", max: "2026-12-31" });
  });

  it("splits the comma-joined rule_allowed_extensions string into an array", () => {
    const out = buildDefinitionPayload(
      { ...base, type: "file", rule_allowed_extensions: "pdf, png,  jpg" }, "site.custom_fields");
    expect(out.rules).toEqual({ allowed_extensions: ["pdf", "png", "jpg"] });
  });

  it("drops rule_allowed_extensions entirely when left blank", () => {
    const out = buildDefinitionPayload({ ...base, type: "file", rule_allowed_extensions: "" }, "site.custom_fields");
    expect(out.rules).toEqual({});
  });

  it("resolves a pattern preset into rules.pattern when no explicit pattern is typed", () => {
    const out = buildDefinitionPayload(
      { ...base, type: "string", rule_pattern_preset: "email" }, "site.custom_fields");
    expect((out.rules as Record<string, unknown>).pattern).toBe("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$");
  });

  it("a NAMED preset wins over an already-typed pattern (Finding 3 fix — the edit-mode bug)", () => {
    // Before the fix: `preset && !payload.rule_pattern ? preset.pattern : payload.rule_pattern`
    // meant a preset selection did NOTHING once `rule_pattern` was already
    // populated — which is ALWAYS true on edit (the field seeds the prior
    // pattern). Picking "Email" from the dropdown must actually switch the
    // pattern even over a pre-existing custom one.
    const out = buildDefinitionPayload(
      { ...base, type: "string", rule_pattern_preset: "email", rule_pattern: "^foo$" }, "site.custom_fields");
    expect((out.rules as Record<string, unknown>).pattern).toBe("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$");
  });

  it("the \"custom\" preset keeps whatever pattern was typed (never overrides)", () => {
    const out = buildDefinitionPayload(
      { ...base, type: "string", rule_pattern_preset: "custom", rule_pattern: "^foo$" }, "site.custom_fields");
    expect((out.rules as Record<string, unknown>).pattern).toBe("^foo$");
  });

  it("the \"custom\" preset never injects a pattern when nothing was typed", () => {
    const out = buildDefinitionPayload(
      { ...base, type: "string", rule_pattern_preset: "custom" }, "site.custom_fields");
    expect(out.rules).toEqual({});
  });

  it("a blank preset also keeps whatever pattern was typed", () => {
    const out = buildDefinitionPayload(
      { ...base, type: "string", rule_pattern_preset: "", rule_pattern: "^foo$" }, "site.custom_fields");
    expect((out.rules as Record<string, unknown>).pattern).toBe("^foo$");
  });

  it("merges rules_advanced (non-UI keys) alongside the rule_* inputs", () => {
    const out = buildDefinitionPayload(
      { ...base, rule_min: 1, rules_advanced: { multiple_of: 5 } }, "site.custom_fields");
    expect(out.rules).toEqual({ min: 1, multiple_of: 5 });
  });

  it("throws an ApiError(422) with a rules_advanced field error when min>max (ruleSanity)", () => {
    const err = captureError(() => buildDefinitionPayload({ ...base, rule_min: 10, rule_max: 1 }, "site.custom_fields"));
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(422);
    // No translator passed -> falls back to the bare errorKey (Finding 1).
    expect(err.fieldErrors().rules_advanced).toMatch(/min/);
  });

  it("throws an ApiError(422) when money min>max (Finding 2)", () => {
    const err = captureError(() => buildDefinitionPayload(
      { ...base, type: "money", rule_money_min: 500, rule_money_max: 5 }, "site.custom_fields"));
    expect(err.status).toBe(422);
    expect(err.fieldErrors().rules_advanced).toMatch(/money/);
  });

  it("throws an ApiError(422) when date min>max for a static ISO pair (Finding 2)", () => {
    const err = captureError(() => buildDefinitionPayload(
      { ...base, type: "date", rule_date_min: "2026-12-31", rule_date_max: "2026-01-01" }, "site.custom_fields"));
    expect(err.status).toBe(422);
    expect(err.fieldErrors().rules_advanced).toMatch(/date/);
  });

  it("does NOT throw when a date bound is the \"today\"/\"now\" token (Finding 2 — static-only check)", () => {
    const out = buildDefinitionPayload(
      { ...base, type: "date", rule_date_min: "today", rule_date_max: "2020-01-01" }, "site.custom_fields");
    expect(out.rules).toEqual({ min: "today", max: "2020-01-01" });
  });

  it("throws an ApiError(422) when a UI-owned key is duplicated in rules_advanced (disjoint guard)", () => {
    const err = captureError(() => buildDefinitionPayload({ ...base, rules_advanced: { min_length: 3 } }, "site.custom_fields"));
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(422);
    // No translator passed -> fallback embeds the errorParams so the
    // offending key is still discoverable (Finding 1).
    expect(err.fieldErrors().rules_advanced).toMatch(/min_length/);
  });

  it("throws an ApiError(422) with a TRANSLATED message when a translator is passed (Finding 1)", () => {
    const t = (k: string, params?: Record<string, unknown>) =>
      `X:${k}${params ? `:${JSON.stringify(params)}` : ""}`;
    const err = captureError(() => buildDefinitionPayload({ ...base, rule_min: 10, rule_max: 1 }, "site.custom_fields", t));
    expect(err.status).toBe(422);
    expect(err.message).toBe("X:f.rule_sanity.min_gt_max");
    expect(err.fieldErrors().rules_advanced).toBe("X:f.rule_sanity.min_gt_max");
  });

  it("threads the errorParams through to the translator on the disjoint guard (Finding 1)", () => {
    const t = (k: string, params?: Record<string, unknown>) =>
      `X:${k}${params ? `:${JSON.stringify(params)}` : ""}`;
    const err = captureError(() => buildDefinitionPayload(
      { ...base, rules_advanced: { min_length: 3 } }, "site.custom_fields", t));
    expect(err.status).toBe(422);
    expect(err.message).toBe('X:f.rule_sanity.advanced_has_ui_key:{"key":"min_length"}');
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

  // Task 5: `rules` is no longer passed through raw — it's split into the
  // type-aware `rule_*` inputs (via `flattenRules`, Task 4) + whatever isn't
  // UI-managed goes to `rules_advanced`.
  it("flattens rules into rule_* inputs + rules_advanced, and joins allowed_extensions into text", () => {
    const flat = flattenDefinition({
      ...row,
      rules: { min_length: 2, max_length: 10, allowed_extensions: ["pdf", "png"], multiple_of: 5 } as Definition["rules"],
    });
    expect(flat.rule_min_length).toBe(2);
    expect(flat.rule_max_length).toBe(10);
    expect(flat.rule_allowed_extensions).toBe("pdf, png");
    expect(flat.rules_advanced).toEqual({ multiple_of: 5 });
  });

  it("defaults rule_allowed_extensions to an empty string and rules_advanced to {} when rules is empty", () => {
    const flat = flattenDefinition(row);
    expect(flat.rule_allowed_extensions).toBe("");
    expect(flat.rules_advanced).toEqual({});
  });
});
