import { describe, it, expect } from "vitest";
import { PARTY_FIELDS } from "./fields";

const by = (n: string) => PARTY_FIELDS.find((f) => f.name === n);

describe("PARTY_FIELDS (directory)", () => {
  it("party_type is a required, immutable select over person/organization", () => {
    const pt = by("party_type");
    expect(pt?.type).toBe("select");
    expect(pt?.required).toBe(true);
    expect(pt?.immutable).toBe(true);
    expect(pt?.selectOptions?.map((o) => o.value).sort()).toEqual(["organization", "person"]);
  });
  it("requires the name and exposes the contact + custom_fields", () => {
    expect(by("name")?.required).toBe(true);
    expect(by("email")?.type).toBe("email");
    expect(by("custom_fields")?.type).toBe("json");
    expect(by("is_active")?.type).toBe("checkbox");
  });
});
