import { describe, expect, it } from "vitest";
import { confirmTextMatches } from "@/lib/confirm";

// The confirm button of a destructive action is gated: with no `requireText` it
// is always enabled; with one (high-impact deletes), it stays disabled until the
// operator types the exact value (trimmed, case-sensitive) — an anti-mistake lock.
describe("confirmTextMatches", () => {
  it("enables when no requireText is set", () => {
    expect(confirmTextMatches(undefined, "")).toBe(true);
    expect(confirmTextMatches(undefined, "whatever")).toBe(true);
    expect(confirmTextMatches("", "")).toBe(true);
  });

  it("requires an exact (trimmed) match", () => {
    expect(confirmTextMatches("DELETE", "DELETE")).toBe(true);
    expect(confirmTextMatches("DELETE", "  DELETE  ")).toBe(true);
  });

  it("stays disabled on mismatch, partial, or empty input", () => {
    expect(confirmTextMatches("DELETE", "delete")).toBe(false); // case-sensitive
    expect(confirmTextMatches("DELETE", "DELE")).toBe(false);
    expect(confirmTextMatches("DELETE", "")).toBe(false);
    expect(confirmTextMatches("my-org", "my-orgg")).toBe(false);
  });
});
