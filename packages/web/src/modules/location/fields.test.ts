import { describe, it, expect } from "vitest";
import { SITE_FIELD_SPECS, SITE_TYPES } from "./fields";

const byName = (n: string) => SITE_FIELD_SPECS.find((f) => f.name === n);

describe("SITE_FIELD_SPECS (pilot 1 — Site canonical form)", () => {
  it("keeps `code` an immutable, required identifier", () => {
    const code = byName("code");
    expect(code?.required).toBe(true);
    expect(code?.immutable).toBe(true);
  });

  it("requires the name", () => {
    expect(byName("name")?.required).toBe(true);
  });

  it("renders the site type as a required select over the known types", () => {
    const st = byName("site_type");
    expect(st?.type).toBe("select");
    expect(st?.required).toBe(true);
    const values = SITE_TYPES.map((o) => o.value);
    expect(values).toContain("branch");
    expect(values).toContain("headquarters");
  });

  it("captures geo through the reusable Address picker (no flat address inputs)", () => {
    expect(byName("address_id")?.type).toBe("address");
    expect(byName("city")).toBeUndefined();
    expect(byName("country_code")).toBeUndefined();
  });
});
