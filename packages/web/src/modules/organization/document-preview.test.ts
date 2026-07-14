import { describe, it, expect } from "vitest";
import { buildDocumentPreviewModel, previewAspectRatio, PREVIEW_FORMATS,
  type ResolvedIssuerIdentity } from "./document-preview";

const resolved: ResolvedIssuerIdentity = {
  legal_name: { value: "Facil SA", from: "organization" },
  tax_id: { value: "NIF-12345", from: "organization" },
  registration_number: { value: "RC-4471", from: "organization" },
  logo_url: { value: "/api/v1/assets/logo", from: "organization" },
  short_code: { value: "FAC", from: "organization" },
  seal_url: { value: null, from: null },
  header_note: { value: null, from: null },
  footer_note: { value: "Facil SA · RC 4471", from: "organization" },
  legal_mentions: { value: null, from: null },
  contact_line: { value: "Malabo", from: "organization" },
};

describe("buildDocumentPreviewModel (SP1 D1 preview)", () => {
  it("falls back to the inherited value when the override is empty", () => {
    const model = buildDocumentPreviewModel({}, resolved, "a4-portrait");
    expect(model.legalName).toBe("Facil SA");
    expect(model.footerNote).toBe("Facil SA · RC 4471");
    expect(model.contactLine).toBe("Malabo");
  });

  it("an empty-string form value also falls back (not just an absent key)", () => {
    const model = buildDocumentPreviewModel({ legal_name: "" }, resolved, "a4-portrait");
    expect(model.legalName).toBe("Facil SA");
  });

  it("a live override wins over the resolved/inherited value regardless of its origin", () => {
    const model = buildDocumentPreviewModel({ legal_name: "Branch Malabo" }, resolved, "a4-portrait");
    expect(model.legalName).toBe("Branch Malabo");
    // Untouched keys still fall back — the override is per-field, not all-or-nothing.
    expect(model.taxId).toBe("NIF-12345");
  });

  it("a key with no resolved value and no override renders blank, never 'null'/'undefined'", () => {
    const model = buildDocumentPreviewModel({}, resolved, "a4-portrait");
    expect(model.sealUrl).toBe("");
    expect(model.headerNote).toBe("");
  });

  it("resolves cleanly with no resolved identity at all (still loading)", () => {
    const model = buildDocumentPreviewModel({ short_code: "TMP" }, undefined, "a4-portrait");
    expect(model.shortCode).toBe("TMP");
    expect(model.legalName).toBe("");
  });

  it("changing the format changes ONLY the sheet geometry, never the resolved content", () => {
    const values = { legal_name: "Branch Malabo" };
    const portrait = buildDocumentPreviewModel(values, resolved, "a4-portrait");
    const landscape = buildDocumentPreviewModel(values, resolved, "a5-landscape");
    const { format: _p, ...portraitContent } = portrait;
    const { format: _l, ...landscapeContent } = landscape;
    expect(landscapeContent).toEqual(portraitContent);
    expect(portrait.format).toBe("a4-portrait");
    expect(landscape.format).toBe("a5-landscape");
  });
});

describe("previewAspectRatio", () => {
  it("computes A4 portrait as the ISO 216 width/height ratio", () => {
    expect(previewAspectRatio("a4-portrait")).toBe("210 / 297");
  });

  it("swaps width/height for landscape (reflow driver, never a fixed per-format class)", () => {
    expect(previewAspectRatio("a4-landscape")).toBe("297 / 210");
  });

  it("A5 uses the smaller ISO 216 dimensions", () => {
    expect(previewAspectRatio("a5-portrait")).toBe("148 / 210");
    expect(previewAspectRatio("a5-landscape")).toBe("210 / 148");
  });

  it("declares exactly the four supported formats, A4/A5 × portrait/landscape", () => {
    expect(PREVIEW_FORMATS).toEqual(["a4-portrait", "a4-landscape", "a5-portrait", "a5-landscape"]);
  });
});
