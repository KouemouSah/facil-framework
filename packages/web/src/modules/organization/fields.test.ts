import { describe, it, expect } from "vitest";
import { ORG_FIELD_SPECS } from "./fields";

const byName = (n: string) => ORG_FIELD_SPECS.find((f) => f.name === n);

describe("ORG_FIELD_SPECS (pilot 1 — Company canonical form)", () => {
  it("uploads the logo as an image, never a free-text URL input", () => {
    const logo = byName("logo_url");
    expect(logo).toBeDefined();
    // The audit finding: an asset field must be a FileUpload (type "image"),
    // not a raw text/URL field the operator pastes into.
    expect(logo?.type).toBe("image");
  });

  it("keeps `code` an immutable, required identifier", () => {
    const code = byName("code");
    expect(code?.required).toBe(true);
    expect(code?.immutable).toBe(true);
  });

  it("requires the legal name", () => {
    expect(byName("legal_name")?.required).toBe(true);
  });

  it("links canonical master data through FK pickers (no flat free-text geo/tax)", () => {
    expect(byName("party_id")?.type).toBe("party");
    expect(byName("parent_id")?.type).toBe("org");
    expect(byName("hq_address_id")?.type).toBe("address");
    expect(byName("currency_id")?.type).toBe("ref");
  });

  it("carries no raw text field pointing at an asset URL", () => {
    const textUrlAsset = ORG_FIELD_SPECS.find(
      (f) => /url$/i.test(f.name) && (f.type === undefined || f.type === "text"),
    );
    expect(textUrlAsset).toBeUndefined();
  });

  it("no longer edits document_identity as raw JSON — it is its own generated-form tab", () => {
    // Task 8 (SP1/M2): document_identity moved out of this form into
    // DocumentIdentityForm, driven by the server-served product schema.
    expect(byName("document_identity")).toBeUndefined();
  });
});
