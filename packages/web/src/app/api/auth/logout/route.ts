import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { REFRESH, backendProxy, clearAuthCookies } from "@/lib/server/backend";

export async function POST() {
  const refresh = (await cookies()).get(REFRESH)?.value;
  // Revoke the session server-side (best-effort), then drop the cookies.
  await backendProxy("/api/v1/auth/logout", {
    method: "POST",
    body: JSON.stringify({ refresh_token: refresh }),
  }).catch(() => undefined);
  await clearAuthCookies();
  return NextResponse.json({ ok: true });
}
