import { describe, it, expect } from "vitest";
import { ACCOUNT_CREATE_FIELDS, ACCOUNT_EDIT_FIELDS } from "./fields";
import { ACCOUNT_STATUSES, BLOCKING_STATUSES } from "./api";

const c = (n: string) => ACCOUNT_CREATE_FIELDS.find((f) => f.name === n);
const e = (n: string) => ACCOUNT_EDIT_FIELDS.find((f) => f.name === n);

describe("ACCOUNT fields (pilot 2 — mirrors backend AccountIn/AccountUpdate)", () => {
  it("create takes a masked, required temporary password", () => {
    const p = c("password");
    expect(p?.type).toBe("password");
    expect(p?.required).toBe(true);
  });

  it("email uses the email input type, required on create", () => {
    expect(c("email")?.type).toBe("email");
    expect(c("email")?.required).toBe(true);
  });

  it("organization is an org picker", () => {
    expect(c("organization_id")?.type).toBe("org");
  });

  it("edit never exposes the password, but keeps email editable", () => {
    expect(e("password")).toBeUndefined();
    expect(e("email")).toBeDefined();
    expect(e("email")?.required).toBeFalsy();
  });
});

describe("account status vocabulary", () => {
  it("marks suspend/deactivate as session-revoking (blocking) transitions", () => {
    expect(BLOCKING_STATUSES.has("suspended")).toBe(true);
    expect(BLOCKING_STATUSES.has("deactivated")).toBe(true);
    expect(BLOCKING_STATUSES.has("active")).toBe(false);
  });

  it("lists all four backend statuses in order", () => {
    expect([...ACCOUNT_STATUSES]).toEqual([
      "pending_identity", "active", "suspended", "deactivated",
    ]);
  });
});
