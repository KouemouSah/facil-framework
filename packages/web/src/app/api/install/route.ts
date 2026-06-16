import { NextRequest, NextResponse } from "next/server";
import { BACKEND } from "@/lib/server/backend";

// First-run install (D5.3). Orchestrates the backend with the operator's
// break-glass admin token (kept server-side, never returned to the browser):
//   1) seed the profile's roles  2) set branding  3) create the first
//   super-admin (account + global admin role). Then the operator signs in.
export async function POST(req: NextRequest) {
  const { adminToken, profile, appName, primaryColor, email, password } = await req.json();
  if (!adminToken || !email || !password) {
    return NextResponse.json({ error: "missing_fields" }, { status: 400 });
  }
  const H = { "Content-Type": "application/json", "X-Admin-Token": adminToken };

  // 1) roles for the chosen profile
  const seed = await fetch(
    `${BACKEND}/api/v1/rbac/admin/reseed?profile=${encodeURIComponent(profile || "empty")}`,
    { method: "POST", headers: H, cache: "no-store" });
  if (seed.status === 401) return NextResponse.json({ error: "invalid_admin_token" }, { status: 401 });
  if (!seed.ok) return NextResponse.json({ error: "seed_failed" }, { status: 502 });

  // 2) branding (best-effort)
  for (const [key, value] of [["branding.app_name", appName], ["branding.primary_color", primaryColor]]) {
    if (value) {
      await fetch(`${BACKEND}/api/v1/admin/settings/${key}`, {
        method: "PUT", headers: H,
        body: JSON.stringify({ value, value_type: "string" }),
      }).catch(() => undefined);
    }
  }

  // 3) first super-admin: register + assign the global `admin` role
  const reg = await fetch(`${BACKEND}/api/v1/auth/register`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }), cache: "no-store",
  });
  if (!reg.ok) {
    const d = await reg.json().catch(() => ({}));
    return NextResponse.json({ error: d.detail || "register_failed" }, { status: 400 });
  }
  const account = await reg.json();
  const roles = await (await fetch(`${BACKEND}/api/v1/rbac/roles`, { headers: H, cache: "no-store" })).json();
  const adminRole = roles.find((r: { code: string }) => r.code === "admin");
  if (!adminRole) return NextResponse.json({ error: "no_admin_role" }, { status: 500 });
  await fetch(`${BACKEND}/api/v1/rbac/accounts/${account.id}/roles`, {
    method: "POST", headers: H, body: JSON.stringify({ role_id: adminRole.id }),
  });
  return NextResponse.json({ ok: true });
}
