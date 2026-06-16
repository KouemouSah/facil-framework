import { NextRequest, NextResponse } from "next/server";
import { BACKEND, setAuthCookies } from "@/lib/server/backend";

// BFF login: proxy to the backend, store the token pair in httpOnly cookies,
// return ONLY the account (never tokens) to the browser.
export async function POST(req: NextRequest) {
  const body = await req.json();
  const res = await fetch(`${BACKEND}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  });

  if (res.ok) {
    const data = await res.json();
    await setAuthCookies(data.access, data.refresh);
    return NextResponse.json({ account: data.account });
  }
  const detail = (await res.json().catch(() => ({}))).detail || "";
  if (res.status === 401 && detail === "totp_required") {
    return NextResponse.json({ totp_required: true }, { status: 200 });
  }
  if (res.status === 423) {
    return NextResponse.json({ error: "account_locked" }, { status: 423 });
  }
  return NextResponse.json({ error: "invalid_credentials" }, { status: 401 });
}
