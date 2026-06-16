import { NextResponse } from "next/server";
import { backendProxy } from "@/lib/server/backend";

// Whoami for the client: proxies /auth/me (refreshing the token if the access
// cookie expired). 401 here = the client redirects to /login.
export async function GET() {
  const res = await backendProxy("/api/v1/auth/me", { method: "GET" });
  if (!res.ok) {
    return NextResponse.json({ authenticated: false }, { status: 401 });
  }
  const me = await res.json();
  return NextResponse.json({ authenticated: true, ...me });
}
