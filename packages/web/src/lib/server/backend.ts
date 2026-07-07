import "server-only";
import { cookies } from "next/headers";

/**
 * Server-only backend helper for the BFF (D5.1). Tokens live in httpOnly cookies
 * the browser cannot read (anti-XSS); route handlers attach them as Bearer and
 * refresh transparently. The browser never sees a token.
 */
export const ACCESS = "facil_at";
export const REFRESH = "facil_rt";

export const BACKEND = process.env.INTERNAL_API_URL || "http://localhost:8080";

const isProd = process.env.NODE_ENV === "production";
const baseCookie = { httpOnly: true, sameSite: "lax" as const, secure: isProd, path: "/" };

export async function setAuthCookies(access: string, refresh: string) {
  const jar = await cookies();
  // Access ~ short (mirrors backend access TTL); refresh longer. Idle/absolute
  // limits are enforced by the BACKEND — the cookie maxAge is just a ceiling.
  jar.set(ACCESS, access, { ...baseCookie, maxAge: 60 * 60 });
  jar.set(REFRESH, refresh, { ...baseCookie, maxAge: 60 * 60 * 24 * 7 });
}

export async function clearAuthCookies() {
  const jar = await cookies();
  jar.delete(ACCESS);
  jar.delete(REFRESH);
}

/** First-run status for server-side gating. Fail-safe = installed (never trap
 *  the operator in the installer if the backend is briefly unreachable). */
export async function getInstallStatus(): Promise<{ installed: boolean }> {
  try {
    const r = await fetch(`${BACKEND}/api/v1/system/install-status`, { cache: "no-store" });
    if (!r.ok) return { installed: true };
    return await r.json();
  } catch {
    return { installed: true };
  }
}

export interface Branding {
  app_name: string;
  tagline: string;
  logo_url: string;
  logo_dark_url: string;
  favicon_url: string;
  login_background_url: string;
  primary_color: string;
  secondary_color: string;
  theme_mode: string;
  default_locale: string;
  support_email: string;
  support_url: string;
  supported_locales: string[];
}

const DEFAULT_BRANDING: Branding = {
  app_name: "Facil", tagline: "", logo_url: "", logo_dark_url: "", favicon_url: "",
  login_background_url: "", primary_color: "#2563eb", secondary_color: "#7c3aed",
  theme_mode: "light", default_locale: "en", support_email: "", support_url: "",
  supported_locales: ["en", "fr", "es"],
};

/** Public theme payload for SSR theming. Cached (revalidate 60s, tag "branding")
 *  instead of per-request — branding changes rarely, and the layout renders it on
 *  every page. The editor calls revalidateTag("branding") on save for an instant
 *  refresh. Fail-safe = baked defaults (never block rendering on a backend hiccup). */
export async function getBranding(): Promise<Branding> {
  try {
    const r = await fetch(`${BACKEND}/api/v1/system/branding`, {
      next: { revalidate: 60, tags: ["branding"] },
    });
    if (!r.ok) return DEFAULT_BRANDING;
    return { ...DEFAULT_BRANDING, ...(await r.json()) };
  } catch {
    return DEFAULT_BRANDING;
  }
}

async function rawCall(path: string, init: RequestInit, token?: string) {
  const headers = new Headers(init.headers);
  // Only force JSON for string bodies. A FormData body (binary upload) must keep
  // its fetch-generated multipart Content-Type with boundary — overriding it here
  // would corrupt the stream. This lets the upload route reuse the 401-refresh.
  if (typeof init.body === "string") headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  return fetch(`${BACKEND}${path}`, { ...init, headers, cache: "no-store" });
}

/** Forward a request to the backend with the access token, refreshing once on
 *  401 (rotation: backend issues a new pair). Returns the Response; on a failed
 *  refresh, clears cookies so the caller answers 401 -> the client redirects. */
export async function backendProxy(path: string, init: RequestInit): Promise<Response> {
  const jar = await cookies();
  const access = jar.get(ACCESS)?.value;
  let res = await rawCall(path, init, access);
  if (res.status !== 401) return res;

  const refresh = jar.get(REFRESH)?.value;
  if (!refresh) return res;
  const r = await rawCall("/api/v1/auth/refresh", {
    method: "POST", body: JSON.stringify({ refresh_token: refresh }),
  });
  if (!r.ok) {
    await clearAuthCookies();
    return res; // original 401
  }
  const tokens = await r.json();
  await setAuthCookies(tokens.access, tokens.refresh);
  // retry the original request with the fresh access token (body may be consumed
  // -> callers pass a serializable body string, which we reuse here)
  return rawCall(path, init, tokens.access);
}
