import { describe, expect, it } from "vitest";
import { validateImageFile, isSameOriginAsset, IMAGE_ACCEPT, MAX_ASSET_BYTES } from "@/lib/upload";

// Client-side pre-validation mirrors the backend allowlist + 5 MiB cap (defence
// in depth — the backend re-sniffs magic bytes and re-caps; the client just
// rejects the obvious cases early for UX). Order matches the backend: size cap
// first, then the type allowlist.
describe("validateImageFile", () => {
  const png = { type: "image/png", size: 1024 };

  it("accepts an allowed image within the cap", () => {
    expect(validateImageFile(png)).toBeNull();
  });

  it("accepts every allowed MIME type", () => {
    for (const type of IMAGE_ACCEPT) {
      expect(validateImageFile({ type, size: 10 })).toBeNull();
    }
  });

  it("rejects a non-image type (declared PDF)", () => {
    expect(validateImageFile({ type: "application/pdf", size: 10 })).toBe("type");
  });

  it("rejects SVG (XSS vector — never allowlisted)", () => {
    expect(validateImageFile({ type: "image/svg+xml", size: 10 })).toBe("type");
    expect(IMAGE_ACCEPT).not.toContain("image/svg+xml");
  });

  it("rejects a file over the cap (size checked before type)", () => {
    expect(validateImageFile({ type: "image/png", size: MAX_ASSET_BYTES + 1 })).toBe("size");
    // Over-cap wins even for a wrong type (size is the first, cheapest guard).
    expect(validateImageFile({ type: "application/pdf", size: MAX_ASSET_BYTES + 1 })).toBe("size");
  });

  it("honours a custom maxBytes", () => {
    expect(validateImageFile({ type: "image/png", size: 2048 }, { maxBytes: 1024 })).toBe("size");
  });
});

describe("isSameOriginAsset", () => {
  it("accepts a same-origin absolute path", () => {
    expect(isSameOriginAsset("/api/v1/assets/abc.png")).toBe(true);
  });
  it("rejects a protocol-relative //host (off-origin)", () => {
    expect(isSameOriginAsset("//evil.example/x.png")).toBe(false);
  });
  it("rejects absolute http(s) URLs", () => {
    expect(isSameOriginAsset("https://cdn.example/logo.png")).toBe(false);
    expect(isSameOriginAsset("http://x/y.png")).toBe(false);
  });
});
