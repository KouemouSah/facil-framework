import { describe, it, expect, vi } from "vitest";
import { QueryClient, hydrate } from "@tanstack/react-query";

const readMock = vi.fn();
vi.mock("@/lib/server/backend", () => ({ readForPrefetch: readMock }));

async function rehydrated() {
  const { dehydratedAuthState } = await import("./prefetch-session");
  const state = await dehydratedAuthState();
  const qc = new QueryClient();
  hydrate(qc, state);
  return qc;
}

describe("dehydratedAuthState", () => {
  it("seeds [session] as {authenticated:true, ...me} and [my-permissions]", async () => {
    readMock.mockImplementation(async (path: string) =>
      path.endsWith("/permissions")
        ? { break_glass: false, permissions: ["*"] }
        : { break_glass: false, account: { id: "a1", display_name: null } });
    const qc = await rehydrated();
    expect(qc.getQueryData(["session"])).toEqual({
      authenticated: true, break_glass: false, account: { id: "a1", display_name: null },
    });
    expect(qc.getQueryData(["my-permissions"])).toEqual({ break_glass: false, permissions: ["*"] });
  });

  it("omits a key whose prefetch returned null (fail-safe, no crash)", async () => {
    readMock.mockImplementation(async (path: string) =>
      path.endsWith("/permissions") ? null : { break_glass: false, account: { id: "a1" } });
    const qc = await rehydrated();
    expect(qc.getQueryData(["session"])).toBeDefined();
    expect(qc.getQueryData(["my-permissions"])).toBeUndefined();
  });

  it("returns an empty dehydrated state when both prefetches fail", async () => {
    readMock.mockResolvedValue(null);
    const qc = await rehydrated();
    expect(qc.getQueryData(["session"])).toBeUndefined();
    expect(qc.getQueryData(["my-permissions"])).toBeUndefined();
  });
});
