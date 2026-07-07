import { describe, expect, it } from "vitest";
import { needsEmailVerification, parseSession, type Session } from "@/lib/session-schema";

// Audit 9: the /session response is validated at the trust boundary. A malformed
// or unexpected body must fail SAFE to an unauthenticated session (never crash a
// consumer that assumes the shape, never grant a truthy `authenticated`).
describe("parseSession", () => {
  it("passes a well-formed authenticated session through", () => {
    const raw = {
      authenticated: true,
      break_glass: false,
      account: { id: "a1", email: "x@y.z" },
      roles: [{ role_id: "r", organization_id: null, org_unit_id: null, site_id: null }],
      idp: null,
    };
    const s = parseSession(raw);
    expect(s.authenticated).toBe(true);
    expect(s.account?.id).toBe("a1");
  });

  it("fails safe to unauthenticated on garbage or wrong types", () => {
    for (const bad of [null, undefined, "nope", 42, {}, { authenticated: "yes" }, { account: {} }]) {
      expect(parseSession(bad)).toEqual({ authenticated: false });
    }
  });

  it("accepts a minimal unauthenticated session", () => {
    expect(parseSession({ authenticated: false })).toEqual({ authenticated: false });
  });

  it("parses email_verified on the account", () => {
    const s = parseSession({ authenticated: true, account: { id: "a", email: "x@y.z", email_verified: false } });
    expect(s.account?.email_verified).toBe(false);
  });
});

describe("needsEmailVerification", () => {
  const base = (over: Partial<Session["account"] & object> = {}, s: Partial<Session> = {}): Session => ({
    authenticated: true,
    account: { id: "a", email: "x@y.z", email_verified: false, ...over },
    ...s,
  });

  it("nudges an authenticated account with an unverified email", () => {
    expect(needsEmailVerification(base())).toBe(true);
  });

  it("stays quiet when verified, break-glass, unauthenticated, or email absent/unknown", () => {
    expect(needsEmailVerification(base({ email_verified: true }))).toBe(false);
    expect(needsEmailVerification(base({}, { break_glass: true }))).toBe(false);
    expect(needsEmailVerification({ authenticated: false })).toBe(false);
    // NIU-only account: no email to verify.
    expect(needsEmailVerification(base({ email: undefined }))).toBe(false);
    // Unknown verification state (backend omitted the field) → don't nag.
    expect(needsEmailVerification(base({ email_verified: undefined }))).toBe(false);
  });
});
