import { NextRequest } from "next/server";
import { backendProxy } from "@/lib/server/backend";

// Single BFF proxy for every authenticated backend call. The client calls
// /api/bff/api/v1/... (verbatim backend path); we attach the access token from
// the httpOnly cookie and transparently refresh on 401. No token ever in JS.
async function handle(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  const search = new URL(req.url).search;
  const method = req.method;
  const body = method === "GET" || method === "HEAD" ? undefined : await req.text();

  const res = await backendProxy(`/${path.join("/")}${search}`, { method, body });
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
