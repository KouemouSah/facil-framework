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
export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
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
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = (body && (body.detail || body.message)) || detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}
