import { describe, expect, it } from "vitest";
import { sanitizeFilename, sanitizeErrorMessage } from "@/lib/sanitize";

describe("sanitizeFilename", () => {
  it("strips path components (anti-traversal) keeping the base name", () => {
    expect(sanitizeFilename("../../etc/passwd")).toBe("passwd");
    expect(sanitizeFilename("a/b\\c.csv")).toBe("c.csv");
  });
  it("replaces control/illegal characters", () => {
    expect(sanitizeFilename('bad<>:"|?*name.csv')).toBe("bad_name.csv");
  });
  it("falls back when empty and bounds the length", () => {
    expect(sanitizeFilename("")).toBe("download");
    expect(sanitizeFilename("   ")).toBe("download");
    expect(sanitizeFilename("a".repeat(500)).length).toBeLessThanOrEqual(200);
  });
});

describe("sanitizeErrorMessage", () => {
  it("strips HTML tags but keeps text", () => {
    expect(sanitizeErrorMessage("<script>alert(1)</script>oops")).toBe("alert(1)oops");
    expect(sanitizeErrorMessage("<b>bad</b> input")).toBe("bad input");
  });
  it("truncates overly long messages", () => {
    expect(sanitizeErrorMessage("x".repeat(1000), 50).length).toBe(50);
  });
  it("trims and tolerates plain text", () => {
    expect(sanitizeErrorMessage("  plain error  ")).toBe("plain error");
  });
});
