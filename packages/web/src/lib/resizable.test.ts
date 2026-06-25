import { describe, expect, it } from "vitest";
import {
  RS_MAX_VW,
  RS_MIN_WIDTH,
  clampWidth,
  parseStoredWidth,
  widthStorageKey,
} from "./resizable";

describe("clampWidth", () => {
  it("floors at the minimum width", () => {
    expect(clampWidth(100, { vw: 1400 })).toBe(RS_MIN_WIDTH);
  });

  it("caps at maxVw of the viewport", () => {
    // 0.6 * 1000 = 600
    expect(clampWidth(99999, { vw: 1000 })).toBe(Math.round(1000 * RS_MAX_VW));
  });

  it("passes a value already in range through (rounded)", () => {
    expect(clampWidth(512.4, { vw: 1400 })).toBe(512);
  });

  it("never returns below min even on a tiny viewport where maxVw<min", () => {
    // 0.6 * 400 = 240 < 360 → upper is raised to min, result stays min.
    expect(clampWidth(500, { vw: 400 })).toBe(RS_MIN_WIDTH);
  });

  it("falls back to min on NaN", () => {
    expect(clampWidth(Number.NaN, { vw: 1400 })).toBe(RS_MIN_WIDTH);
  });

  it("honours custom min/maxVw", () => {
    expect(clampWidth(300, { vw: 1000, min: 320, maxVw: 0.5 })).toBe(320);
    expect(clampWidth(9999, { vw: 1000, min: 320, maxVw: 0.5 })).toBe(500);
  });
});

describe("widthStorageKey / parseStoredWidth", () => {
  it("namespaces per resource", () => {
    expect(widthStorageKey("organization")).toBe("rs:width:organization");
  });

  it("parses valid positive numbers, rejects junk", () => {
    expect(parseStoredWidth("480")).toBe(480);
    expect(parseStoredWidth(null)).toBeNull();
    expect(parseStoredWidth("abc")).toBeNull();
    expect(parseStoredWidth("-5")).toBeNull();
    expect(parseStoredWidth("0")).toBeNull();
  });
});
