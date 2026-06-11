/**
 * Auth Storage - Facil Inspeccion
 */

import * as SecureStore from 'expo-secure-store';
import { getItem, removeItem, setItem } from '@core/storage/mmkv';
import type { UserProfile } from '@core/config/types';

const KEYS = {
  ACCESS_TOKEN: 'inspector_access_token',
  REFRESH_TOKEN: 'inspector_refresh_token',
  USER_PROFILE: 'inspector_user_profile',
  TOKEN_STORED_AT: 'inspector_token_stored_at',
  INSPECTOR_CONTEXT: 'inspector_context',
} as const;

const SECURE_STORE_OPTIONS: SecureStore.SecureStoreOptions = {
  keychainAccessible: SecureStore.AFTER_FIRST_UNLOCK,
  requireAuthentication: false,
};

export async function getAccessToken(): Promise<string | null> {
  try {
    return await SecureStore.getItemAsync(KEYS.ACCESS_TOKEN, SECURE_STORE_OPTIONS);
  } catch {
    return null;
  }
}

export async function getRefreshToken(): Promise<string | null> {
  try {
    return await SecureStore.getItemAsync(KEYS.REFRESH_TOKEN, SECURE_STORE_OPTIONS);
  } catch {
    return null;
  }
}

export async function setTokens(access: string, refresh: string): Promise<void> {
  await Promise.all([
    SecureStore.setItemAsync(KEYS.ACCESS_TOKEN, access, SECURE_STORE_OPTIONS),
    SecureStore.setItemAsync(KEYS.REFRESH_TOKEN, refresh, SECURE_STORE_OPTIONS),
  ]);
  setItem(KEYS.TOKEN_STORED_AT, new Date().toISOString());
}

export async function clearTokens(): Promise<void> {
  await Promise.all([
    SecureStore.deleteItemAsync(KEYS.ACCESS_TOKEN),
    SecureStore.deleteItemAsync(KEYS.REFRESH_TOKEN),
  ]);
  removeItem(KEYS.TOKEN_STORED_AT);
}

export function getUserProfile(): UserProfile | null {
  return getItem<UserProfile>(KEYS.USER_PROFILE);
}

export function setUserProfile(profile: UserProfile): void {
  setItem(KEYS.USER_PROFILE, profile);
}

export function clearUserProfile(): void {
  removeItem(KEYS.USER_PROFILE);
}

export function getTokenStoredAt(): Date | null {
  const iso = getItem<string>(KEYS.TOKEN_STORED_AT);
  if (!iso) return null;
  const date = new Date(iso);
  return isNaN(date.getTime()) ? null : date;
}

export async function clearAllAuthData(): Promise<void> {
  await clearTokens();
  clearUserProfile();
  removeItem(KEYS.INSPECTOR_CONTEXT);
}
