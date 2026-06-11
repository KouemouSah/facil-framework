/**
 * MMKV Storage - Facil Inspeccion
 *
 * Fast synchronous key-value store (~30x faster than AsyncStorage).
 * Used for user preferences, cached profile, and UI state.
 *
 * Security: Encryption key is generated at first launch and stored
 * in expo-secure-store (hardware-backed keychain). MMKV starts
 * unencrypted, then recrypt() is called during bootstrap.
 * This ensures the key is never in the source code or APK binary.
 */

import { MMKV } from 'react-native-mmkv';
import { Platform } from 'react-native';
import * as SecureStore from 'expo-secure-store';
import * as Crypto from 'expo-crypto';

const MMKV_KEY_STORE = 'inspector_mmkv_encryption_key';

// MMKV starts without encryption — recrypt() called during bootstrap
const storage = new MMKV({
  id: 'facil-inspector-storage',
});

let _secured = false;

/**
 * Secure MMKV storage with a device-unique encryption key.
 *
 * Must be called once during app bootstrap (before splash screen hides).
 * On first launch: generates a random 32-char hex key, stores in SecureStore.
 * On subsequent launches: reads the key from SecureStore and recrypts.
 *
 * Uses recrypt() which re-encrypts all existing data with the new key.
 * Safe to call multiple times (no-op if already secured).
 */
export async function secureStorage(): Promise<void> {
  if (_secured || Platform.OS === 'web') return;

  try {
    let key = await SecureStore.getItemAsync(MMKV_KEY_STORE, {
      keychainAccessible: SecureStore.AFTER_FIRST_UNLOCK,
    });

    if (!key) {
      // Generate cryptographically random 32-char hex key
      const randomBytes = await Crypto.getRandomBytesAsync(16);
      key = Array.from(new Uint8Array(randomBytes), (b) => b.toString(16).padStart(2, '0')).join('');

      await SecureStore.setItemAsync(MMKV_KEY_STORE, key, {
        keychainAccessible: SecureStore.AFTER_FIRST_UNLOCK,
      });
    }

    storage.recrypt(key);
    _secured = true;
  } catch {
    // If SecureStore fails (e.g. first boot race condition), MMKV remains
    // unencrypted for this session. Next launch will retry.
    // This is safer than crashing the app on startup.
  }
}

/** Whether MMKV has been encrypted with the device-unique key. */
export function isStorageSecured(): boolean {
  return _secured;
}

// ---------------------------------------------------------------------------
// Standard CRUD operations
// ---------------------------------------------------------------------------

export function getItem<T>(key: string): T | null {
  try {
    const value = storage.getString(key);
    if (value === undefined) return null;
    return JSON.parse(value) as T;
  } catch {
    return null;
  }
}

export function setItem<T>(key: string, value: T): void {
  storage.set(key, JSON.stringify(value));
}

export function removeItem(key: string): void {
  storage.delete(key);
}

export function clearAll(): void {
  storage.clearAll();
}

export function hasKey(key: string): boolean {
  return storage.contains(key);
}

export function getAllKeys(): string[] {
  return storage.getAllKeys();
}

export { storage };
