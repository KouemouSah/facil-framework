import { NextRequest } from "next/server";
import { cookies } from "next/headers";
import { backendProxy, ACCESS, REFRESH } from "@/lib/server/backend";
import { MAX_ASSET_BYTES } from "@/lib/upload";

/**
 * Authenticated asset-upload channel (Phase 3a). The JSON BFF (`/api/bff/*`)
 * reads the body as text and would corrupt multipart binary, and the `/backend/*`
 * rewrite carries no auth — so image uploads get this dedicated route. It parses
 * the multipart form, re-forwards the file to the backend `POST /api/v1/assets`
 * with the httpOnly access token (via `backendProxy`, which refreshes on 401),
 * and returns the backend's `{ asset_id, url }`. The backend re-validates (magic
 * bytes + cap + RBAC `branding.manage`) — this route adds no trust.
 */
export async function POST(req: NextRequest): Promise<Response> {
  // Reject BEFORE buffering the body (DoS guard): an anonymous request never
  // reaches formData() parsing, and a declared oversize body is capped at the
  // Next tier — not only at the backend (which would parse the whole payload
  // first). The edge (Caddy) request-size cap is the complete mitigation in prod.
  const jar = await cookies();
  if (!jar.get(ACCESS)?.value && !jar.get(REFRESH)?.value) {
    return Response.json({ detail: "authentication required" }, { status: 401 });
  }
  if (Number(req.headers.get("content-length") || 0) > MAX_ASSET_BYTES) {
    return Response.json({ detail: "file too large" }, { status: 413 });
  }

  let file: FormDataEntryValue | null;
  try {
    file = (await req.formData()).get("file");
  } catch {
    return Response.json({ detail: "invalid multipart body" }, { status: 400 });
  }
  if (!(file instanceof File)) {
    return Response.json({ detail: "missing file" }, { status: 400 });
  }

  const forward = new FormData();
  forward.append("file", file, file.name);
  const res = await backendProxy("/api/v1/assets", { method: "POST", body: forward });

  const text = await res.text();
  return new Response(text, {
    status: res.status,
    headers: { "Content-Type": res.headers.get("content-type") || "application/json" },
  });
}
