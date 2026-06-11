/**
 * Authentication Cookie Management
 * Manages cookies for middleware route protection
 *
 * In cross-domain architecture (frontend on Cloud Run/Firebase, backend on separate Cloud Run),
 * backend HttpOnly cookies are on the backend domain and NOT accessible to the frontend.
 * So we set taxasge_auth_token via JS cookie on the frontend domain for:
 * - Next.js Edge Middleware JWT verification
 * - Access token restoration after page refresh
 */

import Cookies from 'js-cookie';

/**
 * Set authentication cookies after successful login.
 *
 * NOTE: In cross-domain architecture (frontend on Firebase Hosting, backend on Cloud Run),
 * the backend's HttpOnly Set-Cookie applies to the backend domain only.
 * The Next.js middleware runs on the frontend domain and needs the auth token cookie there.
 * So we MUST set taxasge_auth_token via JS on the frontend domain.
 */
export function setAuthCookies(accessToken: string, userRole: string) {
  // Auth token cookie — needed by Next.js middleware for JWT verification
  // In cross-domain mode, backend HttpOnly cookie is on the wrong domain
  Cookies.set('taxasge_auth_token', accessToken, {
    expires: 35 / (24 * 60), // 35 minutes aligned with JWT lifetime
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'strict',
    path: '/',
  });

  // User role cookie for middleware access control (non-sensitive)
  Cookies.set('taxasge_user_role', userRole, {
    expires: 35 / (24 * 60),
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'strict',
    path: '/',
  });
}

/**
 * Clear authentication cookies on logout.
 */
export function clearAuthCookies() {
  Cookies.remove('taxasge_auth_token', { path: '/' });
  Cookies.remove('taxasge_user_role', { path: '/' });
}

/**
 * Get user role from cookie
 */
export function getUserRoleFromCookie(): string | undefined {
  return Cookies.get('taxasge_user_role');
}

/**
 * Check if user is authenticated based on cookies.
 * Checks the role cookie as a proxy since the auth token is HttpOnly.
 */
export function isAuthenticatedFromCookie(): boolean {
  return !!Cookies.get('taxasge_user_role');
}
