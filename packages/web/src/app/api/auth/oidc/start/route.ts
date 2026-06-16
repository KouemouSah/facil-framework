import { cookies } from "next/headers";
import { NextResponse } from "next/server";

// OIDC auth-code (SSO) start: redirect the browser to the IdP. Config from env
// (OIDC_ISSUER / CLIENT_ID / REDIRECT_URI). State is stored in an httpOnly cookie
// for CSRF protection on the callback.
export async function GET() {
  const issuer = process.env.OIDC_ISSUER;
  const clientId = process.env.OIDC_CLIENT_ID;
  const redirectUri = process.env.OIDC_REDIRECT_URI;
  if (!issuer || !clientId || !redirectUri) {
    return NextResponse.redirect(new URL("/login?error=sso_unconfigured", process.env.APP_URL || "http://localhost:3000"));
  }
  const state = crypto.randomUUID();
  (await cookies()).set("facil_oidc_state", state, {
    httpOnly: true, sameSite: "lax", secure: process.env.NODE_ENV === "production",
    path: "/", maxAge: 600,
  });
  const url = new URL(`${issuer.replace(/\/$/, "")}/protocol/openid-connect/auth`);
  url.searchParams.set("client_id", clientId);
  url.searchParams.set("redirect_uri", redirectUri);
  url.searchParams.set("response_type", "code");
  url.searchParams.set("scope", "openid profile email");
  url.searchParams.set("state", state);
  return NextResponse.redirect(url);
}
