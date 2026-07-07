/**
 * Client-side asset upload helpers (Phase 3a frontend). The security core lives
 * on the backend (`app/api/assets.py`: magic-byte sniff, 5 MiB cap, SVG refused,
 * prefix-locked serving). These helpers are *defence in depth + UX*: reject the
 * obvious wrong file before the round-trip, and POST through the authenticated
 * Next route (`/api/assets/upload`) — NOT the JSON BFF, which would corrupt the
 * multipart binary. The route attaches the httpOnly access token server-side.
 */

//: MIME types the browser reports for the raster formats the backend accepts
//: (png/jpeg/gif/webp/ico). SVG is intentionally absent — it can carry script.
export const IMAGE_ACCEPT = [
  "image/png",
  "image/jpeg",
  "image/gif",
  "image/webp",
  "image/x-icon",
  "image/vnd.microsoft.icon",
] as const;

//: Mirrors backend `MAX_ASSET_BYTES` (5 MiB). Kept in sync deliberately; the
//: backend remains the enforcer, this only avoids a doomed upload.
export const MAX_ASSET_BYTES = 5 * 1024 * 1024;

export type UploadError = "type" | "size";

/** True for a same-origin absolute path (`/x`) but NOT a protocol-relative
 *  `//host` (which resolves off-origin). Decides whether `next/image` may
 *  optimize an asset (same-origin) or must pass it through `unoptimized`
 *  (external host — no `remotePatterns` allowlist, would otherwise throw). */
export function isSameOriginAsset(url: string): boolean {
  return url.startsWith("/") && !url.startsWith("//");
}

export interface UploadedAsset {
  asset_id: string;
  url: string;
}

/** Validate a picked file against the allowlist + cap. Returns an error key
 *  (i18n) or null. Size is checked first (cheapest, matches backend order). */
export function validateImageFile(
  file: { type: string; size: number },
  opts?: { maxBytes?: number },
): UploadError | null {
  const max = opts?.maxBytes ?? MAX_ASSET_BYTES;
  if (file.size > max) return "size";
  if (!(IMAGE_ACCEPT as readonly string[]).includes(file.type)) return "type";
  return null;
}

/** Raised when a file fails client-side validation before any network call. */
export class UploadValidationError extends Error {
  constructor(public readonly reason: UploadError) {
    super(`upload rejected: ${reason}`);
    this.name = "UploadValidationError";
  }
}

/** Upload an image to the backend via the authenticated Next route. Validates
 *  client-side first (throws UploadValidationError), then POSTs multipart. The
 *  backend re-validates and returns a same-origin `url` (`/api/v1/assets/<id>`). */
export async function uploadAsset(
  file: File,
  opts?: { maxBytes?: number },
): Promise<UploadedAsset> {
  const bad = validateImageFile(file, opts);
  if (bad) throw new UploadValidationError(bad);

  const form = new FormData();
  form.append("file", file);
  const res = await fetch("/api/assets/upload", { method: "POST", body: form });
  if (!res.ok) {
    // 422 = backend rejected (spoofed type/oversize); 401 = session expired.
    const detail = await res.json().catch(() => ({}));
    throw new Error(typeof detail?.detail === "string" ? detail.detail : `upload failed (${res.status})`);
  }
  return res.json();
}
