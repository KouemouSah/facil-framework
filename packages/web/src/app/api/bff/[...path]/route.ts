import { NextRequest } from "next/server";
import { backendProxy } from "@/lib/server/backend";

// Single BFF proxy for every authenticated backend call. The client calls
// /api/bff/api/v1/... (verbatim backend path); we attach the access token from
// the httpOnly cookie and transparently refresh on 401. No token ever in JS.
// Cap the proxied request body (audit 10): the BFF buffers it as text, so an
// oversized payload would inflate the Next tier's memory. JSON admin calls are
// small; 2 MiB is generous. Binary uploads use the dedicated /api/assets route.
const MAX_BFF_BODY_BYTES = 2 * 1024 * 1024;

async function handle(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  const search = new URL(req.url).search;
  const method = req.method;
  if (method !== "GET" && method !== "HEAD"
      && Number(req.headers.get("content-length") || 0) > MAX_BFF_BODY_BYTES) {
    return new Response(JSON.stringify({ detail: "payload too large" }), {
      status: 413, headers: { "Content-Type": "application/json" },
    });
  }
  const body = method === "GET" || method === "HEAD" ? undefined : await req.text();

  // Forward the optimistic-concurrency headers (allowlist only — never arbitrary
  // client headers). Without this, `If-Match` is dropped and every admin write's
  // 409 lost-update guard is silently inert end-to-end (SEC-001).
  const headers: Record<string, string> = {};
  for (const h of ["if-match", "if-none-match"]) {
    const v = req.headers.get(h);
    if (v) headers[h] = v;
  }

  const res = await backendProxy(`/${path.join("/")}${search}`, { method, body, headers });
  const text = await res.text();
  return new Response(text, {
    status: res.status,
    headers: { "Content-Type": res.headers.get("content-type") || "application/json" },
  });
}

export {
  handle as GET,
  handle as POST,
  handle as PUT,
  handle as PATCH,
  handle as DELETE,
};
