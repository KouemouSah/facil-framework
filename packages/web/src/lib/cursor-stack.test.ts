import { describe, expect, it } from "vitest";
import {
  hasPrev, initialPageStack, popPage, pushPage, type PageStack,
} from "./cursor-stack";

describe("cursor-stack (keyset Prev/Next)", () => {
  it("starts on page 1 with no previous", () => {
    expect(initialPageStack).toEqual({ cursor: null, stack: [] });
    expect(hasPrev(initialPageStack)).toBe(false);
  });

  it("pushes forward, remembering the page we came from", () => {
    const p2 = pushPage(initialPageStack, "c1");
    expect(p2).toEqual({ cursor: "c1", stack: [null] });
    expect(hasPrev(p2)).toBe(true);
    const p3 = pushPage(p2, "c2");
    expect(p3).toEqual({ cursor: "c2", stack: [null, "c1"] });
  });

  it("pops back to the exact prior cursor", () => {
    const p3 = pushPage(pushPage(initialPageStack, "c1"), "c2");
    const back2 = popPage(p3);
    expect(back2).toEqual({ cursor: "c1", stack: [null] });
    const back1 = popPage(back2);
    expect(back1).toEqual(initialPageStack); // null cursor = page 1
  });

  it("push then pop is a round-trip (no drift)", () => {
    const start: PageStack = { cursor: "x", stack: ["a", "b"] };
    expect(popPage(pushPage(start, "y"))).toEqual(start);
  });

  it("popping on the first page is a no-op", () => {
    expect(popPage(initialPageStack)).toBe(initialPageStack);
  });
});
