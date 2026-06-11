/**
 * Biometric Quick Login — Store encrypted credentials for fingerprint login
 *
 * Flow:
 * 1. After successful password login, prompt "Enable biometric login?"
 * 2. If yes → store email+password in expo-secure-store (hardware-backed keychain)
 * 3. On sign-in screen → show "Login with fingerprint" button
 * 4. Tap → biometric prompt → retrieve credentials → call login API
 * 5. User can disable in profile settings
 *
 * Security:
 * - Credentials stored in expo-secure-store (Keystore on Android, Keychain on iOS)
 * - Only accessible after device authentication (biometric/PIN)
 * - Cleared on sign out
 */

import * as SecureStore from 'expo-secure-store';
import * as LocalAuthentication from 'expo-local-authentication';

const CRED_EMAIL_KEY = 'biometric_login_email';
const CRED_PASS_KEY = 'biometric_login_pass';

export interface BiometricCredentials {
  email: string;
  password: string;
}

/**
 * Check if biometric hardware is available AND enrolled.
 */
export async function isBiometricAvailable(): Promise<boolean> {
  const hasHardware = await LocalAuthentication.hasHardwareAsync();
  if (!hasHardware) return false;
  return LocalAuthentication.isEnrolledAsync();
}

/**
 * Check if biometric login has stored credentials.
 */
export async function hasBiometricCredentials(): Promise<boolean> {
  try {
    const email = await SecureStore.getItemAsync(CRED_EMAIL_KEY);
    return !!email;
  } catch {
    return false;
  }
}

/**
 * Store credentials securely after successful login.
 *
 * P9.4 (S1 fix): the credential entries are now persisted with
 * `requireAuthentication: true`, which **wires the OS keystore to require
 * biometric / device credential authentication on every READ**. Before this
 * change the password could be read on a momentarily-unlocked device by any
 * code with `expo-secure-store` access. Now the platform itself blocks the
 * read until the user's fingerprint / face / PIN is presented.
 *
 * V1.5 / V2 plan: switch to a refresh-token-only model so we don't store a
 * plaintext password at all. That refactor is bigger (it changes the auth
 * bootstrap flow) and is tracked separately — this commit closes the
 * defense-in-depth gap without breaking the existing UX.
 */
export async function saveBiometricCredentials(email: string, password: string): Promise<void> {
  const opts: SecureStore.SecureStoreOptions = {
    requireAuthentication: true,
    authenticationPrompt: 'Verificar identidad',
  };
  await SecureStore.setItemAsync(CRED_EMAIL_KEY, email, opts);
  await SecureStore.setItemAsync(CRED_PASS_KEY, password, opts);
}

/**
 * Retrieve credentials — the keystore now triggers biometric prompt
 * automatically because the entries were written with `requireAuthentication`.
 *
 * We still do an explicit `LocalAuthentication.authenticateAsync()` first so
 * that we get a deterministic prompt even on legacy entries that were saved
 * before the P9.4 change (older versions of the app stored credentials
 * without requireAuthentication; on a fresh install everything goes through
 * the new path).
 */
export async function getBiometricCredentials(): Promise<BiometricCredentials | null> {
  // Explicit biometric gate (covers legacy entries + UX consistency)
  const authResult = await LocalAuthentication.authenticateAsync({
    promptMessage: 'Verificar identidad',
    fallbackLabel: 'PIN',
    cancelLabel: 'Cancelar',
    disableDeviceFallback: false,
  });

  if (!authResult.success) return null;

  // Pass the same options on read so the OS knows it should not skip the
  // hardware-backed auth check. Falls through gracefully for legacy entries.
  const readOpts: SecureStore.SecureStoreOptions = {
    requireAuthentication: true,
    authenticationPrompt: 'Verificar identidad',
  };

  try {
    const email = await SecureStore.getItemAsync(CRED_EMAIL_KEY, readOpts);
    const password = await SecureStore.getItemAsync(CRED_PASS_KEY, readOpts);
    if (!email || !password) return null;
    return { email, password };
  } catch {
    return null;
  }
}

/**
 * Clear stored credentials (on sign out or disable).
 */
export async function clearBiometricCredentials(): Promise<void> {
  await SecureStore.deleteItemAsync(CRED_EMAIL_KEY).catch(() => {});
  await SecureStore.deleteItemAsync(CRED_PASS_KEY).catch(() => {});
}
