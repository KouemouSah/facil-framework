/**
 * Auth API Service
 *
 * Thin wrappers around the API client for all authentication endpoints.
 * Each function maps 1:1 to a backend route.
 *
 * Screens should NOT call these directly — use auth-hooks.ts instead.
 */

import { apiPost, apiGet } from '@core/api/client';
import { API_ENDPOINTS } from '@core/api/endpoints';
import type {
  RequestVerificationResponse,
  PasswordResetRequestResponse,
  PasswordResetConfirmResponse,
  EmailVerifyResponse,
  EmailResendResponse,
  SessionsListResponse,
  TwoFactorStatusResponse,
  TwoFactorEnableResponse,
  TwoFactorSetupVerifyRequest,
  TwoFactorSetupVerifyResponse,
  TwoFactorDisableResponse,
} from '@core/config/types';

// ---------------------------------------------------------------------------
// Verification
// ---------------------------------------------------------------------------

/** POST /auth/request-verification-code */
export async function requestVerificationCode(
  email: string,
): Promise<RequestVerificationResponse> {
  return apiPost<RequestVerificationResponse>(
    API_ENDPOINTS.auth.requestVerificationCode,
    { email },
  );
}

// ---------------------------------------------------------------------------
// Password Reset (public, 2-step)
// ---------------------------------------------------------------------------

/** POST /auth/password/reset/request */
export async function passwordResetRequest(
  email: string,
): Promise<PasswordResetRequestResponse> {
  return apiPost<PasswordResetRequestResponse>(
    API_ENDPOINTS.auth.passwordResetRequest,
    { email },
  );
}

/** POST /auth/password/reset/confirm */
export async function passwordResetConfirm(
  token: string,
  newPassword: string,
): Promise<PasswordResetConfirmResponse> {
  return apiPost<PasswordResetConfirmResponse>(
    API_ENDPOINTS.auth.passwordResetConfirm,
    { token, new_password: newPassword },
  );
}

// ---------------------------------------------------------------------------
// Password Change (authenticated, direct — same endpoint as web)
// ---------------------------------------------------------------------------

/** POST /users/profile/change-password */
export async function changePassword(
  data: { old_password: string; new_password: string },
): Promise<{ message: string }> {
  return apiPost<{ message: string }>(
    API_ENDPOINTS.auth.passwordChange,
    data,
  );
}

// ---------------------------------------------------------------------------
// Email Verification
// ---------------------------------------------------------------------------

/** POST /auth/email/verify */
export async function emailVerify(
  verificationCode: string,
): Promise<EmailVerifyResponse> {
  return apiPost<EmailVerifyResponse>(
    API_ENDPOINTS.auth.emailVerify,
    { verification_code: verificationCode },
  );
}

/** POST /auth/email/resend */
export async function emailResend(): Promise<EmailResendResponse> {
  return apiPost<EmailResendResponse>(API_ENDPOINTS.auth.emailResend);
}

// ---------------------------------------------------------------------------
// Sessions
// ---------------------------------------------------------------------------

/** GET /auth/sessions */
export async function getSessions(): Promise<SessionsListResponse> {
  return apiGet<SessionsListResponse>(API_ENDPOINTS.auth.sessions);
}

// ---------------------------------------------------------------------------
// Two-Factor Authentication
// ---------------------------------------------------------------------------

/** GET /auth/2fa/status */
export async function get2FAStatus(): Promise<TwoFactorStatusResponse> {
  return apiGet<TwoFactorStatusResponse>(API_ENDPOINTS.auth.twoFactorStatus);
}

/** POST /auth/2fa/enable */
export async function enable2FA(): Promise<TwoFactorEnableResponse> {
  return apiPost<TwoFactorEnableResponse>(API_ENDPOINTS.auth.twoFactorEnable);
}

/** POST /auth/2fa/verify (setup verification, NOT login 2FA) */
export async function verify2FASetup(
  data: TwoFactorSetupVerifyRequest,
): Promise<TwoFactorSetupVerifyResponse> {
  return apiPost<TwoFactorSetupVerifyResponse>(
    API_ENDPOINTS.auth.twoFactorVerify,
    data,
  );
}

/** POST /auth/2fa/disable */
export async function disable2FA(
  password: string,
): Promise<TwoFactorDisableResponse> {
  return apiPost<TwoFactorDisableResponse>(
    API_ENDPOINTS.auth.twoFactorDisable,
    { password },
  );
}
