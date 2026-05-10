/**
 * Token Storage Management
 *
 * Strategy (cross-domain architecture: frontend ≠ backend domain):
 * - access_token: in-memory + JS cookie (taxasge_auth_token) for middleware & page refresh
 * - refresh_token: in-memory + sessionStorage (survives page refresh, cleared on tab close)
 * - user profile: localStorage (non-sensitive, needed for UI rendering)
 *
 * On page refresh: tokens restored from cookie/sessionStorage → no 401 cycle
 *
 * NOTE: Backend HttpOnly cookies are on the backend domain (Cloud Run),
 * NOT the frontend domain (Firebase Hosting). SameSite=strict prevents
 * cross-origin cookie sending. So we use JS-accessible storage on frontend.
 */

import type { AuthData, MenuConfig, DashboardConfig } from '@/types/auth';
import { APP_CONSTANTS } from '@/core/config/constants';
import { identifyLogRocket } from '@/core/observability/logrocket';
import { setAuthCookies, clearAuthCookies } from './cookies';
import { broadcastAuthEvent } from './broadcast';
import Cookies from 'js-cookie';

const STORAGE_KEY = APP_CONSTANTS.STORAGE_KEYS.AUTH_DATA;
const MENU_CONFIG_KEY = 'taxasge_menu_config';
const DASHBOARD_CONFIG_KEY = 'taxasge_dashboard_config';

// ============================================================================
// IN-MEMORY TOKEN STORE (XSS-safe — not accessible via localStorage)
// ============================================================================

let _accessToken: string | null = null;
let _refreshToken: string | null = null;

/** Get access token from memory, fallback to cookie on page refresh */
export function getAccessToken(): string | null {
  if (_accessToken) return _accessToken;
  // Page refresh: restore from JS cookie (set during login/refresh)
  if (typeof window !== 'undefined') {
    const cookieToken = Cookies.get('taxasge_auth_token');
    if (cookieToken) {
      _accessToken = cookieToken;
      return cookieToken;
    }
  }
  return null;
}

/** Set access token in memory */
export function setAccessToken(token: string | null): void {
  _accessToken = token;
}

/** Get refresh token from memory, fallback to sessionStorage on page refresh */
export function getRefreshToken(): string | null {
  if (_refreshToken) return _refreshToken;
  // Page refresh: restore from sessionStorage (cleared on tab close)
  if (typeof window !== 'undefined') {
    const stored = sessionStorage.getItem('_rt');
    if (stored) {
      _refreshToken = stored;
      return stored;
    }
  }
  return null;
}

/** Set refresh token in memory + sessionStorage (survives page refresh) */
export function setRefreshToken(token: string | null): void {
  _refreshToken = token;
  if (typeof window !== 'undefined') {
    if (token) {
      sessionStorage.setItem('_rt', token);
    } else {
      sessionStorage.removeItem('_rt');
    }
  }
}

// ============================================================================
// AUTH DATA (localStorage stores ONLY user profile, NOT tokens)
// ============================================================================

/**
 * Get authentication data from storage.
 * Reconstructs AuthData from localStorage (user) + memory/cookie/sessionStorage (tokens).
 */
export function getAuthData(): AuthData | null {
  if (typeof window === 'undefined') return null;

  const data = localStorage.getItem(STORAGE_KEY);
  if (!data) return null;

  try {
    const stored = JSON.parse(data);
    return {
      ...stored,
      access_token: getAccessToken() || '',
      refresh_token: getRefreshToken() || '',
    } as AuthData;
  } catch (error) {
    console.error('Error parsing auth data:', error);
    return null;
  }
}

/**
 * Save authentication data.
 * Tokens → memory + cookie/sessionStorage; user profile → localStorage.
 */
export function setAuthData(authData: AuthData): void {
  if (typeof window === 'undefined') return;

  // Tokens → memory + persistent storage for page refresh survival
  setAccessToken(authData.access_token);
  setRefreshToken(authData.refresh_token);

  // User profile → localStorage (non-sensitive, needed for UI)
  // Strip tokens from localStorage copy
  const storageData = {
    ...authData,
    access_token: '',
    refresh_token: '',
  };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(storageData));

  // Set middleware cookies (access_token + role for Next.js middleware)
  if (authData.access_token && authData.user?.role) {
    setAuthCookies(authData.access_token, authData.user.role);
  }

  // LogRocket: attach non-PII user context (id + role + locale only)
  if (authData.user?.id) {
    identifyLogRocket({
      id: String(authData.user.id),
      role: authData.user.role,
      locale: authData.user.preferred_language,
    });
  }

  // Broadcast login event to other tabs
  broadcastAuthEvent('login');
}

/**
 * Clear all authentication data (memory + sessionStorage + localStorage + cookies)
 */
export function clearAuthData(): void {
  if (typeof window === 'undefined') return;

  // Clear tokens (memory + sessionStorage)
  setAccessToken(null);
  setRefreshToken(null);

  // Clear localStorage
  localStorage.removeItem(STORAGE_KEY);

  // Clear middleware cookies
  clearAuthCookies();

  // LogRocket: rotate to a fresh anonymous session
  identifyLogRocket(null);

  // Broadcast logout event to other tabs
  broadcastAuthEvent('logout');
}

/**
 * Check if user is authenticated
 */
export function isAuthenticated(): boolean {
  // Check in-memory token first, fallback to localStorage (page refresh case)
  if (_accessToken) return true;
  const authData = getAuthData();
  return authData !== null && !!authData.user;
}

/**
 * Update user's 2FA status in storage
 */
export function update2FAStatus(enabled: boolean): void {
  if (typeof window === 'undefined') return;

  const authData = getAuthData();
  if (!authData) return;

  authData.user.two_factor_enabled = enabled;
  setAuthData(authData);
}

// =============================================================================
// MENU CONFIGURATION STORAGE
// =============================================================================

export function getMenuConfig(): MenuConfig | null {
  if (typeof window === 'undefined') return null;

  const data = localStorage.getItem(MENU_CONFIG_KEY);
  if (!data) return null;

  try {
    return JSON.parse(data) as MenuConfig;
  } catch (error) {
    console.error('Error parsing menu config:', error);
    return null;
  }
}

export function setMenuConfig(menuConfig: MenuConfig): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem(MENU_CONFIG_KEY, JSON.stringify(menuConfig));
}

export function clearMenuConfig(): void {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(MENU_CONFIG_KEY);
}

// =============================================================================
// DASHBOARD CONFIGURATION STORAGE
// =============================================================================

export function getDashboardConfig(): DashboardConfig | null {
  if (typeof window === 'undefined') return null;

  const data = localStorage.getItem(DASHBOARD_CONFIG_KEY);
  if (!data) return null;

  try {
    return JSON.parse(data) as DashboardConfig;
  } catch (error) {
    console.error('Error parsing dashboard config:', error);
    return null;
  }
}

export function setDashboardConfig(dashboardConfig: DashboardConfig): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem(DASHBOARD_CONFIG_KEY, JSON.stringify(dashboardConfig));
}

export function clearDashboardConfig(): void {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(DASHBOARD_CONFIG_KEY);
}

// =============================================================================
// COMBINED OPERATIONS
// =============================================================================

export function clearAllAuthData(): void {
  clearAuthData();
  clearMenuConfig();
  clearDashboardConfig();
}

export function updateAgentConfig(
  menuConfig?: MenuConfig | null,
  dashboardConfig?: DashboardConfig | null
): void {
  if (menuConfig) setMenuConfig(menuConfig);
  if (dashboardConfig) setDashboardConfig(dashboardConfig);
}

// Legacy exports for backward compatibility
export { clearAuthData as clearAuth };
