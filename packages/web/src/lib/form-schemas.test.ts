import { describe, it, expect } from "vitest";
import {
  codeField, requiredText, optionalText, emailField, passwordField,
  exactLen, numericField, hexColor,
} from "./form-schemas";

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

describe("passwordField (mirrors check_strength: min 12 + classes)", () => {
  it("requires >=12 chars with upper, lower and digit", () => {
    expect(passwordField.safeParse("Coralreef8892").success).toBe(true);
    for (const bad of [
      "Secret123",        // 9 chars — was valid under the stale min-8 rule
      "Short1Aaaaa",       // 11 chars, still under 12
      "alllowercase1",     // no uppercase
      "ALLUPPERCASE1",     // no lowercase
      "NoDigitsHereAtAll",  // no digit
    ]) {
      expect(passwordField.safeParse(bad).success).toBe(false);
    }
  });
});

describe("exactLen (referential codes: ISO country/currency)", () => {
  it("accepts exactly N chars, rejects shorter/longer/blank", () => {
    expect(exactLen(3).safeParse("USD").success).toBe(true);
    for (const bad of ["US", "USDD", "", "  "]) {
      expect(exactLen(3).safeParse(bad).success).toBe(false);
    }
  });
});

describe("numericField (mirrors backend numeric bounds)", () => {
  const s = numericField({ min: 0, max: 4, int: true });
  it("accepts an in-range integer", () => {
    expect(s.safeParse("3").success).toBe(true);
    expect(s.safeParse("0").success).toBe(true);
  });
  it("rejects out-of-range, negative, and non-integer", () => {
    for (const bad of ["5", "-1", "2.5", "abc"]) {
      expect(s.safeParse(bad).success).toBe(false);
    }
  });
  it("allows floats when int is not set", () => {
    expect(numericField({ min: 0 }).safeParse("2.5").success).toBe(true);
  });
});

describe("hexColor (mirrors branding color, max_length 7)", () => {
  it("accepts #RRGGBB, rejects short/long/non-hex", () => {
    expect(hexColor.safeParse("#2563eb").success).toBe(true);
    for (const bad of ["2563eb", "#fff", "#12345g", "#1234567", "red"]) {
      expect(hexColor.safeParse(bad).success).toBe(false);
    }
  });
});
