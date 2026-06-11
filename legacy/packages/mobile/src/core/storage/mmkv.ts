/**
 * MMKV Storage Instance
 *
 * Fast, synchronous key-value storage for non-sensitive data.
 * Uses react-native-mmkv which is ~30x faster than AsyncStorage.
 *
 * Use this for:
 * - User preferences (language, theme)
 * - Cached user profile (non-sensitive fields)
 * - UI state persistence (last viewed tab, onboarding status)
 * - Feature flags / app config cache
 *
 * DO NOT use this for:
 * - Auth tokens (use expo-secure-store via auth-storage.ts)
 * - Passwords or API keys
 * - Any PII that requires encryption at rest
 *
 * @see https://github.com/mrousavy/react-native-mmkv
 */

import { MMKV } from 'react-native-mmkv';
import { Platform } from 'react-native';

/**
 * Primary MMKV storage instance.
 *
 * encryptionKey provides basic obfuscation for non-sensitive data on native.
 * Web does not support encryptionKey — omitted on web platform.
 * **This is NOT a substitute for SecureStore for sensitive data** — the
 * contract above is the load-bearing one.
 *
 * Audit note (P9.5 / S4 from MOBILE_HOLISTIC_AUDIT_2026_04_27.md): the key
 * below is hardcoded. Migrating it to a SecureStore-derived value requires
 * making the MMKV bootstrap async (so we can read the key first), which
 * cascades into every synchronous `storage.getString(...)` call site at boot
 * time and is therefore deferred to a dedicated V1.5 refactor. The current
 * exposure is *bounded by the contract above*: an attacker who reverse-
 * engineers the key only sees UI preferences, never tokens or PII.
 */
export const storage = new MMKV({
  id: 'facil-app-storage',
  ...(Platform.OS !== 'web' ? { encryptionKey: 'facil-mmkv-key' } : {}),
});

/**
 * Get a JSON-serialized value from MMKV storage.
 *
 * @param key - Storage key
 * @returns Parsed value or null if not found / parse error
 */
export function getItem<T>(key: string): T | null {
  const value = storage.getString(key);
  if (value === undefined) return null;

  try {
    return JSON.parse(value) as T;
  } catch {
    // If the value is not valid JSON, remove it to avoid corruption
    storage.delete(key);
    return null;
  }
}

/**
 * Store a JSON-serializable value in MMKV storage.
 *
 * @param key - Storage key
 * @param value - Value to serialize and store
 */
export function setItem<T>(key: string, value: T): void {
  storage.set(key, JSON.stringify(value));
}

/**
 * Remove a single key from MMKV storage.
 *
 * @param key - Storage key to remove
 */
export function removeItem(key: string): void {
  storage.delete(key);
}

/**
 * Clear all data from MMKV storage.
 *
 * WARNING: This removes ALL app data from MMKV.
 * Use only during sign-out or data reset flows.
 */
export function clearAll(): void {
  storage.clearAll();
}

/**
 * Check if a key exists in MMKV storage.
 *
 * @param key - Storage key to check
 * @returns true if the key exists
 */
export function hasKey(key: string): boolean {
  return storage.contains(key);
}

/**
 * Get all keys currently stored in MMKV.
 *
 * @returns Array of storage keys
 */
export function getAllKeys(): string[] {
  return storage.getAllKeys();
}
