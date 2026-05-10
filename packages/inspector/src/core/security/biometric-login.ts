/**
 * Biometric Login - Facil Inspeccion
 *
 * Security: Stores a REFRESH TOKEN (revocable server-side) instead of
 * the user's plaintext password. If the device is compromised:
 * - Refresh token can be revoked via /auth/logout (all_sessions=true)
 * - The actual password is never exposed
 * - Token has a 30-day TTL (vs password which never expires)
 *
 * Flow:
 * 1. After successful login → save refresh token + email via saveBiometricToken()
 * 2. On next launch → biometric prompt → retrieve refresh token
 * 3. Call /auth/refresh with the token → new access + refresh tokens
 * 4. Update stored biometric token with the new refresh token
 */

import * as LocalAuthentication from 'expo-local-authentication';
import * as SecureStore from 'expo-secure-store';

const BIO_KEYS = {
  /** User email (display only, not used for auth) */
  EMAIL: 'inspector_bio_email',
  /** Refresh token (revocable, 30-day TTL) — NEVER store passwords */
  REFRESH_TOKEN: 'inspector_bio_refresh_token',
  /** Whether biometric login is enabled */
  ENABLED: 'inspector_bio_enabled',
} as const;

const SECURE_OPTIONS: SecureStore.SecureStoreOptions = {
  keychainAccessible: SecureStore.AFTER_FIRST_UNLOCK,
};

// ---------------------------------------------------------------------------
// Hardware check
// ---------------------------------------------------------------------------

export async function isBiometricAvailable(): Promise<boolean> {
  const hasHardware = await LocalAuthentication.hasHardwareAsync();
  if (!hasHardware) return false;
  return LocalAuthentication.isEnrolledAsync();
}

// ---------------------------------------------------------------------------
// Save (called after successful email/password login)
// ---------------------------------------------------------------------------

/**
 * Save the refresh token for biometric login.
 *
 * @param email - User email (for display in biometric prompt)
 * @param refreshToken - JWT refresh token (NOT the password)
 */
export async function saveBiometricToken(
  email: string,
  refreshToken: string,
): Promise<void> {
  await Promise.all([
    SecureStore.setItemAsync(BIO_KEYS.EMAIL, email, SECURE_OPTIONS),
    SecureStore.setItemAsync(BIO_KEYS.REFRESH_TOKEN, refreshToken, SECURE_OPTIONS),
    SecureStore.setItemAsync(BIO_KEYS.ENABLED, 'true', SECURE_OPTIONS),
  ]);
}

/**
 * Update the stored refresh token after a token refresh.
 * Called when the biometric login flow gets a new refresh token.
 */
export async function updateBiometricToken(refreshToken: string): Promise<void> {
  const enabled = await SecureStore.getItemAsync(BIO_KEYS.ENABLED, SECURE_OPTIONS);
  if (enabled !== 'true') return;
  await SecureStore.setItemAsync(BIO_KEYS.REFRESH_TOKEN, refreshToken, SECURE_OPTIONS);
}

// ---------------------------------------------------------------------------
// Retrieve (called when user taps biometric button)
// ---------------------------------------------------------------------------

/**
 * Authenticate with biometrics and retrieve the stored refresh token.
 *
 * @returns { email, refreshToken } on success, null on failure/cancel
 */
export async function getBiometricToken(): Promise<{
  email: string;
  refreshToken: string;
} | null> {
  const enabled = await SecureStore.getItemAsync(BIO_KEYS.ENABLED, SECURE_OPTIONS);
  if (enabled !== 'true') return null;

  const result = await LocalAuthentication.authenticateAsync({
    promptMessage: 'Acceso biometrico - Facil Inspeccion',
    cancelLabel: 'Cancelar',
    disableDeviceFallback: false,
  });

  if (!result.success) return null;

  const [email, refreshToken] = await Promise.all([
    SecureStore.getItemAsync(BIO_KEYS.EMAIL, SECURE_OPTIONS),
    SecureStore.getItemAsync(BIO_KEYS.REFRESH_TOKEN, SECURE_OPTIONS),
  ]);

  if (!email || !refreshToken) return null;

  return { email, refreshToken };
}

// ---------------------------------------------------------------------------
// Clear (called on sign-out)
// ---------------------------------------------------------------------------

export async function clearBiometricCredentials(): Promise<void> {
  await Promise.all([
    SecureStore.deleteItemAsync(BIO_KEYS.EMAIL),
    SecureStore.deleteItemAsync(BIO_KEYS.REFRESH_TOKEN),
    SecureStore.deleteItemAsync(BIO_KEYS.ENABLED),
  ]);
}

// ---------------------------------------------------------------------------
// Status check
// ---------------------------------------------------------------------------

export async function hasBiometricCredentials(): Promise<boolean> {
  const enabled = await SecureStore.getItemAsync(BIO_KEYS.ENABLED, SECURE_OPTIONS);
  return enabled === 'true';
}
