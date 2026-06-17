import { describe, expect, it } from "vitest";
import { hasPerm } from "@/lib/perm";

describe("hasPerm (mirrors backend wildcard matching)", () => {
  it("matches the exact code", () => expect(hasPerm(["account.read"], "account.read")).toBe(true));
  it("matches the global wildcard *", () => expect(hasPerm(["*"], "anything.read")).toBe(true));
  it("matches a resource wildcard", () => expect(hasPerm(["account.*"], "account.read")).toBe(true));
  it("does not match a different resource", () => expect(hasPerm(["account.read"], "rbac.read")).toBe(false));
  it("does not match a different verb without wildcard", () =>
    expect(hasPerm(["account.read"], "account.manage")).toBe(false));
  it("treats an empty needed permission as allowed", () => expect(hasPerm([], "")).toBe(true));
  it("returns false when nothing is granted", () => expect(hasPerm([], "account.read")).toBe(false));
});
