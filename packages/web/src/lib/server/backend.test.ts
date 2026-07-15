import { describe, it, expect, vi, beforeEach } from "vitest";

const setSpy = vi.fn();
const deleteSpy = vi.fn();
const fetchMock = vi.fn();

vi.mock("server-only");

vi.mock("next/headers", () => ({
  cookies: async () => ({
    get: (n: string) => (n === "facil_at" ? { value: "tok-abc" } : undefined),
    set: setSpy,
    delete: deleteSpy,
  }),
}));

beforeEach(() => {
  setSpy.mockClear();
  deleteSpy.mockClear();
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

describe("readForPrefetch", () => {
  it("returns parsed JSON on 2xx and forwards the access token, never mutating cookies", async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ permissions: ["*"] }), { status: 200 }),
    );
    const { readForPrefetch } = await import("./backend");
    const out = await readForPrefetch<{ permissions: string[] }>("/api/v1/auth/me/permissions");
    expect(out).toEqual({ permissions: ["*"] });
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toContain("/api/v1/auth/me/permissions");
    expect(new Headers(init.headers).get("Authorization")).toBe("Bearer tok-abc");
    expect(setSpy).not.toHaveBeenCalled();
    expect(deleteSpy).not.toHaveBeenCalled();
  });

  it("returns null on 401 WITHOUT attempting a refresh or mutating cookies", async () => {
    fetchMock.mockResolvedValue(new Response("", { status: 401 }));
    const { readForPrefetch } = await import("./backend");
    expect(await readForPrefetch("/api/v1/auth/me")).toBeNull();
    // exactly ONE call — no refresh round-trip like backendProxy does
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(setSpy).not.toHaveBeenCalled();
    expect(deleteSpy).not.toHaveBeenCalled();
  });

  it("returns null on a network error", async () => {
    fetchMock.mockRejectedValue(new Error("ECONNREFUSED"));
    const { readForPrefetch } = await import("./backend");
    expect(await readForPrefetch("/api/v1/auth/me")).toBeNull();
  });
});
