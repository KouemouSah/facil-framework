/**
 * Client-side API helper. Calls go through the BFF proxy `/api/bff/*` (a Next
 * route handler) which attaches the access token from the httpOnly cookie and
 * refreshes it transparently — the browser never holds a token. Pass the verbatim
 * backend path, e.g. apiFetch("/api/v1/modules/organization/").
 *
 * 401 interceptor (D4 requirement): when the backend reports the session is
 * gone (idle/absolute expiry, revocation, or unauthenticated), we redirect to
 * the login page instead of surfacing a raw error.
 */
import { sanitizeErrorMessage } from "@/lib/sanitize";

export class ApiError extends Error {
  /** `detail` is the raw parsed error body. For a 422 it is FastAPI's
   * validation array (`[{loc:["body","field"], msg, type}]`), which lets a form
   * map each error onto its field (§11bis 422→field). */
  constructor(public status: number, message: string, public detail?: unknown) {
    super(message);
    this.name = "ApiError";
  }

  /** Field → message map parsed from a 422 body (empty if not a validation error). */
  fieldErrors(): Record<string, string> {
    const out: Record<string, string> = {};
    const d = this.detail as { detail?: unknown };
    const items = Array.isArray(this.detail) ? this.detail
      : Array.isArray(d?.detail) ? d.detail : [];
    for (const it of items as Array<{ loc?: unknown[]; msg?: string }>) {
      const loc = Array.isArray(it.loc) ? it.loc : [];
      const field = loc.length ? String(loc[loc.length - 1]) : "";
      if (field && field !== "body" && !(field in out)) out[field] = it.msg ?? "Invalid value";
    }
    return out;
  }
}

export interface ApiOptions extends RequestInit {
  /** Skip the automatic 401 -> /login redirect (e.g. on the login form itself). */
  noRedirectOn401?: boolean;
}

export async function apiFetch<T = unknown>(
  path: string,
  opts: ApiOptions = {},
): Promise<T> {
  const { noRedirectOn401, headers, ...rest } = opts;
  const res = await fetch(`/api/bff${path}`, {
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...headers },
    ...rest,
  });

  if (res.status === 401 && !noRedirectOn401 && typeof window !== "undefined") {
    const next = encodeURIComponent(window.location.pathname + window.location.search);
    window.location.assign(`/login?next=${next}`);
    throw new ApiError(401, "session expired — redirecting to login");
  }

  if (!res.ok) {
    let message = res.statusText;
    let raw: unknown;
    try {
      raw = await res.json();
      const d = (raw as { detail?: unknown; message?: unknown })?.detail
        ?? (raw as { message?: unknown })?.message;
      // A 422 `detail` is an array (per-field) — keep a readable message but
      // hand the structured body to ApiError for field mapping.
      message = typeof d === "string" ? sanitizeErrorMessage(d)
        : Array.isArray(d) ? "Validation failed" : message;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, message, raw);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}
