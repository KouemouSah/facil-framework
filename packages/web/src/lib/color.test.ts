import { describe, expect, it } from "vitest";
import { hexToHslTriplet } from "@/lib/color";

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
