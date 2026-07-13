import { describe, expect, it } from "vitest";
import { curatedHref, isCurated } from "./curated";

describe("curated config keys", () => {
  it("flags branding.* and ai.routing/ai.providers as curated", () => {
    expect(isCurated("branding.logo_url")).toBe(true);
    expect(isCurated("branding.login_background_url")).toBe(true);
    expect(isCurated("ai.routing")).toBe(true);
    expect(isCurated("ai.providers")).toBe(true);
  });

  it("does not flag unrelated keys", () => {
    expect(isCurated("auth.oidc.issuer")).toBe(false);
    expect(isCurated("email.provider")).toBe(false);
    expect(isCurated("brandingx.foo")).toBe(false); // prefix must be exact
  });

  it("links branding.* to the Branding editor", () => {
    expect(curatedHref("branding.logo_url")).toBe("/settings");
    expect(curatedHref("branding.theme_mode")).toBe("/settings");
  });

  it("links ai.routing / ai.providers to the Providers page", () => {
    expect(curatedHref("ai.routing")).toBe("/providers");
    expect(curatedHref("ai.providers")).toBe("/providers");
  });

  it("returns null for non-curated keys", () => {
    expect(curatedHref("auth.oidc.issuer")).toBeNull();
    expect(curatedHref("email.provider")).toBeNull();
  });
});
