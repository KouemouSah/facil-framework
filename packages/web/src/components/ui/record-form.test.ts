import { describe, expect, it } from "vitest";
import { controlKindFor, type FieldDef } from "./record-form";

/**
 * Pins the `text` collision fix (review Fix 1): `FieldDef.type` is the merged
 * union `FieldType | FieldSpecType`, and "text" means opposite things in each
 * vocabulary (see the comment on `FieldType` in record-form.tsx). The ONLY
 * thing that tells them apart is `widget` — a server-served `FieldSpec`
 * always carries one (`DEFAULT_WIDGET`, app/core/schema/types.py), a
 * hand-written legacy `FieldDef` never does.
 *
 * This test exercises the pure decision (not the DOM — Vitest here forbids
 * render-tests) and MUST fail if `renderControl`'s spec-driven branches are
 * ever ungated back to a bare `f.type === "text"` check.
 */
describe("controlKindFor (text collision guard)", () => {
  it("resolves a legacy `{type: \"text\"}` with no widget to the legacy (single-line) kind", () => {
    const legacy: FieldDef = { name: "code", label: "Code", type: "text" };
    expect(controlKindFor(legacy)).toBe("legacy");
  });

  it("resolves a spec `{type: \"text\", widget: \"plain\"}` to the spec (multi-line) kind", () => {
    const spec: FieldDef = { name: "notes", label: "Notes", type: "text", widget: "plain" };
    expect(controlKindFor(spec)).toBe("spec");
  });

  it("resolves an omitted type (the documented single-line default) to legacy", () => {
    const omitted: FieldDef = { name: "name", label: "Name" };
    expect(controlKindFor(omitted)).toBe("legacy");
  });

  it("resolves any other server-served (type, widget) pair to spec, e.g. boolean/relation", () => {
    expect(controlKindFor({ name: "use_tls", label: "TLS", type: "boolean", widget: "checkbox" }))
      .toBe("spec");
    expect(controlKindFor({ name: "country", label: "Country", type: "relation", widget: "combobox" }))
      .toBe("spec");
  });
});
