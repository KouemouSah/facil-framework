/**
 * Next.js Middleware for TaxasGE Cloud Run Deployment
 * Handles i18n, authentication, authorization, and security headers
 *
 * Security:
 * - JWT signature verification via `jose` (when JWT_SECRET_KEY is configured)
 * - Role extracted from JWT claims (not a separate cookie)
 * - CSP headers hardened (object-src, base-uri, form-action, upgrade-insecure-requests)
 *
 * @module middleware
 */

import createMiddleware from 'next-intl/middleware';
import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';
import { jwtVerify } from 'jose';
import { routing } from './i18n/routing';
import { locales, defaultLocale } from './i18n/config';

// JWT secret for signature verification (server-side only, NOT NEXT_PUBLIC_)
const JWT_SECRET = process.env.JWT_SECRET_KEY
  ? new TextEncoder().encode(process.env.JWT_SECRET_KEY)
  : null;

/**
 * Protected routes that require authentication
 */
const PROTECTED_ROUTES = [
  '/dashboard',
  '/profile',
  '/declarations',
  '/payments',
  '/documents',
  '/companies',
];

/**
 * Admin-only routes (requires admin, agent_*, or supervisor_* role)
 */
const ADMIN_ROUTES = [
  '/admin',
  '/dashboard/admin',
  '/dashboard/agent',
  '/dashboard/supervisor',
  '/agents',
  '/assignment',
  '/permissions',
];

/**
 * Public routes (accessible without auth)
 */
const PUBLIC_ROUTES = ['/', '/search', '/categories', '/guide', '/calculator', '/auth', '/services', '/ministries'];

/**
 * Verify JWT token and extract payload.
 * Returns decoded payload if valid, null if invalid/expired.
 * SECURITY: JWT_SECRET MUST be configured — no fallback to cookie-based auth.
 */
async function verifyJWT(token: string): Promise<{ sub: string; role: string; exp: number } | null> {
  if (!JWT_SECRET) {
    // FAIL-CLOSED: No secret = no authentication possible
    // This prevents attackers from forging cookies when JWT_SECRET_KEY is missing
    console.error('[SECURITY] JWT_SECRET_KEY not configured — all auth requests denied');
    return null;
  }
  try {
    const { payload } = await jwtVerify(token, JWT_SECRET, {
      algorithms: ['HS256'],
    });
    return {
      sub: payload.sub as string,
      role: (payload.role as string) || (payload as Record<string, unknown>).user_role as string || '',
      exp: payload.exp || 0,
    };
  } catch {
    // Token invalid, expired, or tampered
    return null;
  }
}

/**
 * Check if user is authenticated by verifying JWT token in cookies.
 * SECURITY: Always verifies JWT signature. No cookie-only fallback.
 */
async function isAuthenticated(request: NextRequest): Promise<{ authenticated: boolean; role: string | null }> {
  const authToken = request.cookies.get('taxasge_auth_token');
  if (!authToken?.value) {
    return { authenticated: false, role: null };
  }

  // ALWAYS verify JWT signature — no fallback to cookie-only auth
  const payload = await verifyJWT(authToken.value);
  if (!payload) {
    return { authenticated: false, role: null };
  }
  return { authenticated: true, role: payload.role || null };
}

/**
 * Check if user has admin/supervisor/agent permissions
 * JWT role values from user_role_enum: 'admin', 'agent', 'citizen', 'business', 'accountant', 'funcionario'
 * Note: JWT contains the enum value ('agent'), not the role code ('agent_cnedoge_pasaporte')
 */
function hasAdminPermissions(role: string | null): boolean {
  if (!role) return false;
  const r = role.toLowerCase();
  return r === 'admin' || r === 'agent' || r.startsWith('agent_') || r.startsWith('supervisor_');
}

/**
 * Check if user has write permissions (same as admin permissions)
 */
const hasWritePermissions = hasAdminPermissions;

/**
 * Extract locale from pathname (e.g., /es/services -> es)
 */
function getLocaleFromPathname(pathname: string): string | null {
  const segments = pathname.split('/');
  const potentialLocale = segments[1];
  return locales.includes(potentialLocale as (typeof locales)[number]) ? potentialLocale : null;
}

/**
 * Remove locale prefix from pathname
 */
function removeLocalePrefix(pathname: string): string {
  const locale = getLocaleFromPathname(pathname);
  if (!locale) return pathname;
  return pathname.replace(`/${locale}`, '') || '/';
}

/**
 * Check if route requires authentication
 */
function isProtectedRoute(pathname: string): boolean {
  const pathnameWithoutLocale = removeLocalePrefix(pathname);
  return PROTECTED_ROUTES.some((route) => pathnameWithoutLocale.startsWith(route));
}

/**
 * Check if route requires admin access
 */
function isAdminRoute(pathname: string): boolean {
  const pathnameWithoutLocale = removeLocalePrefix(pathname);
  return ADMIN_ROUTES.some((route) => pathnameWithoutLocale.startsWith(route));
}

/**
 * Check if route is public
 */
function _isPublicRoute(pathname: string): boolean {
  const pathnameWithoutLocale = removeLocalePrefix(pathname);
  return PUBLIC_ROUTES.some((route) =>
    pathnameWithoutLocale === route || pathnameWithoutLocale.startsWith(`${route}/`)
  );
}

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Skip middleware for static files and API routes
  if (
    pathname.startsWith('/_next') ||
    pathname.startsWith('/api') ||
    pathname.includes('.') // Static files (.svg, .png, etc.)
  ) {
    return NextResponse.next();
  }

  // 0. Redirect bare / to /chat (chat-first landing page)
  // Only redirect bare domain — locale-prefixed URLs (/es, /fr, /en) still show homepage
  if (pathname === '/') {
    const url = request.nextUrl.clone();
    url.pathname = `/${defaultLocale}/chat`;
    return NextResponse.redirect(url);
  }

  // 1. Handle i18n (locale detection and routing)
  const intlMiddleware = createMiddleware(routing);

  // Apply i18n middleware first
  const intlResponse = intlMiddleware(request);

  // Get the response URL after i18n processing
  const responsePathname = intlResponse.headers.get('x-middleware-request-x-matched-path') || pathname;

  const { authenticated, role: userRole } = await isAuthenticated(request);

  // 2. Protect authenticated routes
  if (isProtectedRoute(responsePathname)) {
    if (!authenticated) {
      // Redirect to login with return URL
      const locale = getLocaleFromPathname(responsePathname) || defaultLocale;
      const loginUrl = new URL(`/${locale}/auth`, request.url);
      loginUrl.searchParams.set('redirect', responsePathname);
      return NextResponse.redirect(loginUrl);
    }
  }

  // 3. Protect admin routes
  if (isAdminRoute(responsePathname)) {
    if (!authenticated) {
      const locale = getLocaleFromPathname(responsePathname) || defaultLocale;
      const loginUrl = new URL(`/${locale}/auth`, request.url);
      loginUrl.searchParams.set('redirect', responsePathname);
      return NextResponse.redirect(loginUrl);
    }

    if (!hasAdminPermissions(userRole)) {
      const locale = getLocaleFromPathname(responsePathname) || defaultLocale;
      return NextResponse.redirect(new URL(`/${locale}/dashboard`, request.url));
    }

    // Check write permissions for specific routes
    const writeOnlyRoutes = ['/admin/users/create', '/agents/assign'];
    const pathnameWithoutLocale = removeLocalePrefix(responsePathname);
    const isWriteOnlyRoute = writeOnlyRoutes.some((route) => pathnameWithoutLocale.startsWith(route));

    if (isWriteOnlyRoute && !hasWritePermissions(userRole)) {
      const locale = getLocaleFromPathname(responsePathname) || defaultLocale;
      return NextResponse.redirect(new URL(`/${locale}/dashboard`, request.url));
    }
  }

  // 4. Redirect authenticated users away from auth pages
  const pathnameWithoutLocale = removeLocalePrefix(responsePathname);
  if (pathnameWithoutLocale.startsWith('/auth') && authenticated) {
    const locale = getLocaleFromPathname(responsePathname) || defaultLocale;
    return NextResponse.redirect(new URL(`/${locale}/dashboard`, request.url));
  }

  // 5. Add security headers
  const response = intlResponse || NextResponse.next();

  response.headers.set('X-DNS-Prefetch-Control', 'on');
  response.headers.set('Strict-Transport-Security', 'max-age=63072000; includeSubDomains; preload');
  response.headers.set('X-XSS-Protection', '1; mode=block');
  response.headers.set('X-Frame-Options', 'DENY');
  response.headers.set('X-Content-Type-Options', 'nosniff');
  response.headers.set('Referrer-Policy', 'strict-origin-when-cross-origin');

  // CSP: Allow API calls to Cloud Run backend services
  const apiOrigins = [
    'https://taxasge-backend-staging-xrlbgdr5eq-uc.a.run.app',  // Cloud Run staging
    'https://taxasge-backend-staging-392159428433.us-central1.run.app',  // Cloud Run staging alt
    'https://taxasge-backend-dev.run.app',  // Legacy dev
    'https://taxasge-backend-prod.run.app',  // Legacy prod
  ].join(' ');

  // LogRocket allowlist — required so the SDK can load its recording
  // script and upload sessions. Without these the browser blocks
  //   https://cdn.lr-in.com/logger-1.min.js
  // with "Refused to load … violates Content Security Policy" and the
  // dashboard stays on "Waiting for data" forever.
  // Reference: https://docs.logrocket.com/reference/content-security-policy
  const logrocketScript = 'https://cdn.lr-in.com https://cdn.logr-in.com';
  const logrocketConnect =
    'https://*.lr-in.com https://*.logr-in.com https://*.lr-ingest.io ' +
    'https://*.logrocket.io https://*.logrocket.com';

  const scriptBase =
    process.env.NODE_ENV === 'development'
      ? "script-src 'self' 'unsafe-eval' 'unsafe-inline'"
      : "script-src 'self' 'unsafe-inline'";

  response.headers.set(
    'Content-Security-Policy',
    [
      "default-src 'self'",
      `${scriptBase} ${logrocketScript}`,
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data: blob: https:",
      "font-src 'self' data:",
      `connect-src 'self' ${apiOrigins} ${logrocketConnect}`,
      // LogRocket spawns a Web Worker created from a Blob URL; without
      // this the worker fails silently on Chrome.
      "worker-src 'self' blob:",
      // frame-src extended (mig 323) for embedded business dashboards:
      //   - https://*.grafana.net          : Grafana Cloud workspace iframes (10 dashboards)
      //   - https://lookerstudio.google.com : Looker Studio embeds (services catalog)
      "frame-src 'self' https://storage.googleapis.com https://firebasestorage.googleapis.com https://*.firebasestorage.app https://*.grafana.net https://lookerstudio.google.com",
      "frame-ancestors 'none'",
      "object-src 'none'",
      "base-uri 'self'",
      "form-action 'self'",
      "upgrade-insecure-requests",
    ].join('; ')
  );

  return response;
}

/**
 * Middleware configuration
 */
export const config = {
  matcher: [
    '/((?!api|_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico)$).*)',
  ],
};
