import { describe, expect, it } from "vitest";
import { hexToHslTriplet, contrastRatio, wcagAA } from "@/lib/color";

describe("hexToHslTriplet", () => {
  it("white", () => expect(hexToHslTriplet("#ffffff")).toBe("0 0% 100%"));
  it("black", () => expect(hexToHslTriplet("#000000")).toBe("0 0% 0%"));
  it("pure red", () => expect(hexToHslTriplet("#ff0000")).toBe("0 100% 50%"));
  it("expands 3-digit hex", () => expect(hexToHslTriplet("#fff")).toBe("0 0% 100%"));
  it("tolerates a leading #-less value", () => expect(hexToHslTriplet("000000")).toBe("0 0% 0%"));
  it("returns null for invalid input", () => {
    expect(hexToHslTriplet("nope")).toBeNull();
    expect(hexToHslTriplet("")).toBeNull();
    expect(hexToHslTriplet("#12")).toBeNull();
  });
});

describe("contrastRatio (WCAG 2.x)", () => {
  it("black on white is the maximum 21:1", () => {
    expect(contrastRatio("#000000", "#ffffff")).toBeCloseTo(21, 1);
  });
  it("is symmetric and 1:1 for identical colors", () => {
    expect(contrastRatio("#2563eb", "#2563eb")).toBeCloseTo(1, 2);
    expect(contrastRatio("#fff", "#000")).toBeCloseTo(contrastRatio("#000", "#fff")!, 5);
  });
  it("returns null on invalid input", () => {
    expect(contrastRatio("nope", "#000")).toBeNull();
  });
});

describe("wcagAA", () => {
  it("passes normal text at >=4.5, fails clearly below", () => {
    expect(wcagAA("#000000", "#ffffff")).toBe(true);   // 21:1
    expect(wcagAA("#595959", "#ffffff")).toBe(true);   // ~7:1
    expect(wcagAA("#808080", "#ffffff")).toBe(false);  // ~3.95:1, under 4.5
  });
  it("large-text threshold is 3.0", () => {
    // #808080 ~3.95:1 fails normal but clears the 3.0 large-text bar.
    expect(wcagAA("#808080", "#ffffff", { large: true })).toBe(true);
    expect(wcagAA("#808080", "#ffffff")).toBe(false);
  });
});
