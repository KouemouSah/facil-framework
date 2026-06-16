import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";
import { setAuthCookies } from "@/lib/server/backend";

// OIDC callback: validate state, exchange the code for tokens at the IdP, then
// store the IdP tokens in our httpOnly cookies. The BFF then presents the IdP
// access token as Bearer; the backend's keycloak_oidc verifier validates it and
// federation resolves it to a local account. (IdP-token refresh = follow-up.)
export async function GET(req: NextRequest) {
  const appUrl = process.env.APP_URL || "http://localhost:3000";
  const code = req.nextUrl.searchParams.get("code");
  const state = req.nextUrl.searchParams.get("state");
  const jar = await cookies();
  const expected = jar.get("facil_oidc_state")?.value;
  jar.delete("facil_oidc_state");

  const issuer = process.env.OIDC_ISSUER;
  const clientId = process.env.OIDC_CLIENT_ID;
  const clientSecret = process.env.OIDC_CLIENT_SECRET || "";
  const redirectUri = process.env.OIDC_REDIRECT_URI || "";
  if (!code || !state || state !== expected || !issuer || !clientId) {
    return NextResponse.redirect(new URL("/login?error=sso_failed", appUrl));
  }

  const body = new URLSearchParams({
    grant_type: "authorization_code", code, redirect_uri: redirectUri,
    client_id: clientId, ...(clientSecret ? { client_secret: clientSecret } : {}),
  });
  const res = await fetch(`${issuer.replace(/\/$/, "")}/protocol/openid-connect/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
    cache: "no-store",
  });
  if (!res.ok) {
    return NextResponse.redirect(new URL("/login?error=sso_failed", appUrl));
  }
  const tokens = await res.json();
  await setAuthCookies(tokens.access_token, tokens.refresh_token || "");
  return NextResponse.redirect(new URL("/", appUrl));
}
