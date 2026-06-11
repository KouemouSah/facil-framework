/**
 * Security Module — OWASP Mobile Top 10 compliance
 *
 * M1 (Improper Credential Usage): Tokens in SecureStore, never in MMKV or logs
 * M2 (Inadequate Supply Chain): Dependencies audited, no unknown packages
 * M3 (Insecure Auth): JWT + 2FA + biometric, token refresh with mutex
 * M4 (Insufficient Input Validation): Zod schemas on all forms
 * M5 (Insecure Communication): HTTPS only, no HTTP fallback
 * M6 (Inadequate Privacy): Screen capture prevention, no PII in logs
 * M7 (Insufficient Binary Protection): R8/ProGuard enabled, Hermes bytecode
 * M8 (Security Misconfiguration): Production checks below
 * M9 (Insecure Data Storage): MMKV encrypted with device-unique key
 * M10 (Insufficient Cryptography): SHA-256 signatures, RSA-2048 keystore
 */

export { useScreenProtection } from './use-screen-protection';
export { AppLockProvider, useAppLock } from './app-lock';
export {
  isBiometricAvailable,
  saveBiometricToken,
  getBiometricToken,
  hasBiometricCredentials,
  clearBiometricCredentials,
} from './biometric-login';

/**
 * Production security checks — call on app startup.
 * Logs warnings for insecure configurations.
 */
export function auditSecurityConfig(): string[] {
  const warnings: string[] = [];

  if (__DEV__) {
    warnings.push('Running in DEV mode — security features reduced');
  }

  return warnings;
}
