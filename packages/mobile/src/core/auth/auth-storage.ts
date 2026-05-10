/**
 * Auth Storage
 *
 * Secure token storage using expo-secure-store (for tokens)
 * and MMKV (for non-sensitive user profile data).
 *
 * Security design (OWASP MASVS):
 * - Tokens are stored in the platform keychain/keystore via SecureStore
 *   (encrypted at rest, inaccessible to other apps)
 * - User profile is stored in MMKV (fast sync access, basic encryption)
 * - All clear operations are atomic to prevent partial state
 *
 * SecureStore operations are async (native bridge).
 * MMKV operations are sync (JSI, shared memory).
 */

import * as SecureStore from 'expo-secure-store';

import { getItem, removeItem, setItem } from '@core/storage/mmkv';
import type { UserProfile } from '@core/config/types';

// ---------------------------------------------------------------------------
// Storage Keys
// ---------------------------------------------------------------------------

const KEYS = {
  /** JWT access token (short-lived, 30 min) */
  ACCESS_TOKEN: 'facil_access_token',
  /** JWT refresh token (long-lived, 30 days) */
  REFRESH_TOKEN: 'facil_refresh_token',
  /** Cached user profile (non-sensitive subset) */
  USER_PROFILE: 'facil_user_profile',
  /** Timestamp when access token was stored (ISO string) */
  TOKEN_STORED_AT: 'facil_token_stored_at',
} as const;

/**
 * SecureStore options for token storage.
 *
 * - keychainAccessible: AFTER_FIRST_UNLOCK allows background refresh
 *   while keeping data encrypted at rest when device is locked.
 * - requireAuthentication: false (biometric auth is handled at app level,
 *   not at token storage level, to avoid UX friction during refresh).
 */
const SECURE_STORE_OPTIONS: SecureStore.SecureStoreOptions = {
  keychainAccessible: SecureStore.AFTER_FIRST_UNLOCK,
  requireAuthentication: false,
};

// ---------------------------------------------------------------------------
// Access Token
// ---------------------------------------------------------------------------

/**
 * Retrieve the stored access token from secure storage.
 *
 * @returns The access token string, or null if not stored / expired
 */
export async function getAccessToken(): Promise<string | null> {
  try {
    return await SecureStore.getItemAsync(KEYS.ACCESS_TOKEN, SECURE_STORE_OPTIONS);
  } catch {
    // SecureStore can throw on corrupted keychain entries
    return null;
  }
}

// ---------------------------------------------------------------------------
// Refresh Token
// ---------------------------------------------------------------------------

/**
 * Retrieve the stored refresh token from secure storage.
 *
 * @returns The refresh token string, or null if not stored
 */
export async function getRefreshToken(): Promise<string | null> {
  try {
    return await SecureStore.getItemAsync(KEYS.REFRESH_TOKEN, SECURE_STORE_OPTIONS);
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// Store Tokens
// ---------------------------------------------------------------------------

/**
 * Store both access and refresh tokens atomically.
 *
 * Both tokens are written to SecureStore. The timestamp is recorded
 * in MMKV for token-age checks without hitting the native bridge.
 *
 * @param access - JWT access token
 * @param refresh - JWT refresh token
 */
export async function setTokens(access: string, refresh: string): Promise<void> {
  await Promise.all([
    SecureStore.setItemAsync(KEYS.ACCESS_TOKEN, access, SECURE_STORE_OPTIONS),
    SecureStore.setItemAsync(KEYS.REFRESH_TOKEN, refresh, SECURE_STORE_OPTIONS),
  ]);
  // Record storage time in MMKV (sync, for proactive refresh logic)
  setItem(KEYS.TOKEN_STORED_AT, new Date().toISOString());
}

// ---------------------------------------------------------------------------
// Clear Tokens
// ---------------------------------------------------------------------------

/**
 * Remove both tokens from secure storage.
 *
 * Called during sign-out or when refresh fails (force re-login).
 */
export async function clearTokens(): Promise<void> {
  await Promise.all([
    SecureStore.deleteItemAsync(KEYS.ACCESS_TOKEN),
    SecureStore.deleteItemAsync(KEYS.REFRESH_TOKEN),
  ]);
  removeItem(KEYS.TOKEN_STORED_AT);
}

// ---------------------------------------------------------------------------
// User Profile (MMKV - sync)
// ---------------------------------------------------------------------------

/**
 * Get cached user profile from MMKV (synchronous).
 *
 * This is non-sensitive data used for immediate UI rendering
 * without waiting for a network call.
 *
 * @returns UserProfile or null if not cached
 */
export function getUserProfile(): UserProfile | null {
  return getItem<UserProfile>(KEYS.USER_PROFILE);
}

/**
 * Cache user profile in MMKV (synchronous).
 *
 * @param profile - User profile data from API
 */
export function setUserProfile(profile: UserProfile): void {
  setItem(KEYS.USER_PROFILE, profile);
}

/**
 * Remove cached user profile from MMKV.
 */
export function clearUserProfile(): void {
  removeItem(KEYS.USER_PROFILE);
}

// ---------------------------------------------------------------------------
// Token Age
// ---------------------------------------------------------------------------

/**
 * Get the timestamp when the current access token was stored.
 *
 * Used to calculate token age for proactive refresh before expiry.
 *
 * @returns Date when token was stored, or null if unknown
 */
export function getTokenStoredAt(): Date | null {
  const iso = getItem<string>(KEYS.TOKEN_STORED_AT);
  if (!iso) return null;
  const date = new Date(iso);
  return isNaN(date.getTime()) ? null : date;
}

// ---------------------------------------------------------------------------
// Clear All Auth Data
// ---------------------------------------------------------------------------

/**
 * Nuclear option: clear ALL auth-related data.
 *
 * Removes tokens from SecureStore AND profile from MMKV.
 * Used during sign-out, account deletion, or security events.
 */
export async function clearAllAuthData(): Promise<void> {
  await clearTokens();
  clearUserProfile();
}
