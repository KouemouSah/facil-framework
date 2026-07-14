import { describe, it, expect } from "vitest";
import { PARTY_FIELD_SPECS } from "./fields";

const by = (n: string) => PARTY_FIELD_SPECS.find((f) => f.name === n);

describe("PARTY_FIELD_SPECS (directory)", () => {
  it("party_type is a required, immutable select over person/organization", () => {
    const pt = by("party_type");
    expect(pt?.type).toBe("select");
    expect(pt?.required).toBe(true);
    expect(pt?.immutable).toBe(true);
    expect(pt?.selectOptions?.map((o) => o.value).sort()).toEqual(["organization", "person"]);
  });
  it("requires the name and exposes the contact fields", () => {
    expect(by("name")?.required).toBe(true);
    expect(by("email")?.type).toBe("email");
    expect(by("is_active")?.type).toBe("checkbox");
  });

  it("no longer carries a raw custom_fields JSON blob — superseded by the Studio's "
    + "schema-driven custom fields (Task 15), merged in by usePartyFields, not hand-declared here", () => {
    expect(by("custom_fields")).toBeUndefined();
  });
});
