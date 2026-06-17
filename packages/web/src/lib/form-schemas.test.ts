import { describe, it, expect } from "vitest";
import { codeField, requiredText, optionalText, emailField, passwordField } from "./form-schemas";

describe("codeField (mirrors backend _CODE)", () => {
  it("accepts valid codes", () => {
    for (const ok of ["acme", "HQ", "a", "org-1", "x.y_z", "A1.2-3"]) {
      expect(codeField.safeParse(ok).success).toBe(true);
    }
  });
  it("rejects empty, bad first char, illegal chars, and >50", () => {
    for (const bad of ["", "-bad", ".bad", "_bad", "has space", "emoji😀", "a".repeat(51)]) {
      expect(codeField.safeParse(bad).success).toBe(false);
    }
  });
});

describe("requiredText / optionalText", () => {
  it("requiredText rejects blank, accepts content, enforces max", () => {
    expect(requiredText("Name").safeParse("").success).toBe(false);
    expect(requiredText("Name").safeParse("   ").success).toBe(false);
    expect(requiredText("Name").safeParse("Jane").success).toBe(true);
    expect(requiredText("Name", 3).safeParse("abcd").success).toBe(false);
  });
  it("optionalText allows empty and bounded content", () => {
    expect(optionalText().safeParse("").success).toBe(true);
    expect(optionalText(120).safeParse("Malabo").success).toBe(true);
    expect(optionalText(2).safeParse("abc").success).toBe(false);
  });
});

describe("emailField (mirrors backend _EMAIL_RE)", () => {
  it("accepts a plausible address, rejects malformed", () => {
    expect(emailField.safeParse("a@b.co").success).toBe(true);
    for (const bad of ["", "no-at", "a@b", "a b@c.d", "@b.co"]) {
      expect(emailField.safeParse(bad).success).toBe(false);
    }
  });
});

describe("passwordField (mirrors check_strength)", () => {
  it("requires >=8 chars with upper, lower and digit", () => {
    expect(passwordField.safeParse("Secret123").success).toBe(true);
    for (const bad of ["short1A", "alllower1", "ALLUPPER1", "NoDigitsHere"]) {
      expect(passwordField.safeParse(bad).success).toBe(false);
    }
  });
});
