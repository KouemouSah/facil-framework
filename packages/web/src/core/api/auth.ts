/**
 * TaxasGE Authentication API Client
 * Aligns with backend /api/v1/auth endpoints
 */

import { appConfig } from '@/core/config/app';
import { getAuthData } from '@/core/auth/storage';
import { getDeviceFingerprint, getDeviceInfo } from '@/core/auth/device-fingerprint';

const AUTH_API_URL = `${appConfig.api.baseUrl}/api/${appConfig.api.version}/auth`;

/**
 * Extract user-friendly error message from API response
 * Handles FastAPI error formats (detail string or object)
 */
function extractErrorMessage(error: unknown, fallback: string): string {
  // FastAPI returns errors in multiple formats:
  // 1. { detail: "Error message" }
  // 2. { detail: [{ msg: "Error", type: "..." }] }
  // 3. { message: "Error message" }

  if (typeof error !== 'object' || error === null) {
    return fallback;
  }

  const errorObj = error as Record<string, unknown>;

  if (typeof errorObj.detail === 'string') {
    return errorObj.detail;
  }

  if (Array.isArray(errorObj.detail) && errorObj.detail.length > 0) {
    // Pydantic validation errors
    const firstError = errorObj.detail[0] as Record<string, unknown>;
    return (firstError.msg as string) || (firstError.message as string) || fallback;
  }

  if (typeof errorObj.detail === 'object' && errorObj.detail !== null) {
    const detailObj = errorObj.detail as Record<string, unknown>;
    if (typeof detailObj.message === 'string') {
      return detailObj.message;
    }
  }

  if (typeof errorObj.message === 'string') {
    return errorObj.message;
  }

  return fallback;
}

interface LoginRequest {
  email: string;
  password: string;
  remember_me?: boolean;
  device_info?: Record<string, string>;
}

interface RegisterRequest {
  email: string;
  verification_code: string;
  password: string;
  first_name: string;
  last_name: string;
  phone: string;
  role: 'citizen' | 'business';
  address?: string;
  city?: string;
}

interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: {
    id: string;
    email: string;
    role: 'citizen' | 'business' | 'accountant' | 'admin' | 'agent' | 'funcionario';
    status: 'active' | 'inactive' | 'suspended' | 'pending_verification';
    first_name: string;
    last_name: string;
    phone?: string;
    address?: string;
    city?: string;
    language: string;
    avatar_url?: string;
    created_at: string;
    updated_at: string;
    last_login?: string;
    email_verified?: boolean;
    two_factor_enabled?: boolean;
    is_active: boolean;
    permissions?: string[];
  };
}

interface TwoFactorLoginResponse {
  requires_2fa: boolean;
  temp_token: string;
  message: string;
}

interface TwoFactorVerifyRequest {
  temp_token: string;
  code: string;
  device_fingerprint?: string;
  device_info?: Record<string, string>;
}

interface PasswordResetRequestRequest {
  email: string;
}

interface PasswordResetRequestResponse {
  message: string;
  email: string;
}

interface PasswordResetConfirmRequest {
  token: string;
  new_password: string;
}

interface PasswordResetConfirmResponse {
  message: string;
}

interface EmailVerifyRequest {
  verification_code: string;
}

interface EmailVerifyResponse {
  message: string;
}

interface UserProfile {
  id: string;
  email: string;
  role: string;
  email_verified: boolean;
  two_factor_enabled: boolean;
  profile: {
    first_name: string;
    last_name: string;
    phone?: string;
  };
}

interface Session {
  id: string;
  user_id: string;
  device_info: string;
  ip_address: string;
  created_at: string;
  last_activity: string;
  is_current: boolean;
}

interface LogoutRequest {
  access_token: string;
  refresh_token: string;
}

interface LogoutResponse {
  message: string;
}

/**
 * Login endpoint - POST /auth/login
 * Returns tokens if no 2FA, or temp_token if 2FA enabled
 */
async function login(data: LoginRequest): Promise<TokenResponse | TwoFactorLoginResponse> {
  // Attach device info for session binding + audit
  const deviceInfo = getDeviceInfo();
  const payload = {
    ...data,
    device_info: Object.keys(deviceInfo).length > 0 ? deviceInfo : undefined,
  };

  const response = await fetch(`${AUTH_API_URL}/login`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(extractErrorMessage(error, 'Échec de la connexion'));
  }

  return response.json();
}

/**
 * Verify 2FA code - POST /auth/login/2fa-verify
 * Completes login after 2FA verification
 */
async function verify2FA(data: TwoFactorVerifyRequest): Promise<TokenResponse> {
  // Attach device fingerprint for 2FA device binding
  let fingerprint: string | undefined;
  try {
    fingerprint = await getDeviceFingerprint();
  } catch { /* non-blocking */ }
  const deviceInfo = getDeviceInfo();
  const payload = {
    ...data,
    device_fingerprint: fingerprint,
    device_info: Object.keys(deviceInfo).length > 0 ? deviceInfo : undefined,
  };

  const response = await fetch(`${AUTH_API_URL}/login/2fa-verify`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(extractErrorMessage(error, 'Échec de la vérification 2FA'));
  }

  return response.json();
}

/**
 * Register endpoint - POST /auth/register
 */
async function register(data: RegisterRequest): Promise<TokenResponse> {
  const response = await fetch(`${AUTH_API_URL}/register`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(extractErrorMessage(error, "Échec de l'inscription"));
  }

  return response.json();
}

/**
 * Refresh token endpoint - POST /auth/refresh
 */
async function refreshToken(refreshToken: string): Promise<TokenResponse> {
  const response = await fetch(`${AUTH_API_URL}/refresh`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
    body: JSON.stringify({ refresh_token: refreshToken }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(extractErrorMessage(error, 'Échec du rafraîchissement du token'));
  }

  return response.json();
}

/**
 * Logout endpoint - POST /auth/logout
 */
async function logout(data: LogoutRequest): Promise<LogoutResponse> {
  const response = await fetch(`${AUTH_API_URL}/logout`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(extractErrorMessage(error, 'Échec de la déconnexion'));
  }

  return response.json();
}

/**
 * Get current user profile - GET /auth/profile
 */
async function getProfile(accessToken: string): Promise<UserProfile> {
  const response = await fetch(`${AUTH_API_URL}/profile`, {
    method: 'GET',
    headers: {
      Authorization: `Bearer ${accessToken}`,
      'Content-Type': 'application/json',
    },
    credentials: 'include',
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(extractErrorMessage(error, 'Échec du chargement du profil'));
  }

  return response.json();
}

/**
 * Request password reset - POST /auth/password/reset/request
 */
async function requestPasswordReset(
  data: PasswordResetRequestRequest
): Promise<PasswordResetRequestResponse> {
  const response = await fetch(`${AUTH_API_URL}/password/reset/request`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(extractErrorMessage(error, 'Échec de la demande de réinitialisation'));
  }

  return response.json();
}

/**
 * Confirm password reset - POST /auth/password/reset/confirm
 */
async function confirmPasswordReset(
  data: PasswordResetConfirmRequest
): Promise<PasswordResetConfirmResponse> {
  const response = await fetch(`${AUTH_API_URL}/password/reset/confirm`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(extractErrorMessage(error, 'Échec de la réinitialisation du mot de passe'));
  }

  return response.json();
}

/**
 * Verify email - POST /auth/email/verify
 */
async function verifyEmail(data: EmailVerifyRequest, accessToken: string): Promise<EmailVerifyResponse> {
  const response = await fetch(`${AUTH_API_URL}/email/verify`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${accessToken}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(extractErrorMessage(error, "Échec de la vérification de l'email"));
  }

  return response.json();
}

/**
 * Resend email verification - POST /auth/email/resend
 */
async function resendEmailVerification(
  accessToken: string
): Promise<{ message: string; email: string }> {
  const response = await fetch(`${AUTH_API_URL}/email/resend`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${accessToken}`,
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(extractErrorMessage(error, "Échec du renvoi de l'email de vérification"));
  }

  return response.json();
}

/**
 * Get active sessions - GET /auth/sessions
 */
async function getSessions(accessToken: string): Promise<Session[]> {
  const response = await fetch(`${AUTH_API_URL}/sessions`, {
    method: 'GET',
    headers: {
      Authorization: `Bearer ${accessToken}`,
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(extractErrorMessage(error, 'Échec du chargement des sessions'));
  }

  return response.json();
}

/**
 * Request verification code - POST /auth/request-verification-code
 * Step 1 of two-step registration
 */
async function requestVerificationCode(
  email: string
): Promise<{ message: string; email: string; expires_in: number }> {
  const response = await fetch(`${AUTH_API_URL}/request-verification-code`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
    body: JSON.stringify({ email }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(extractErrorMessage(error, "Échec de l'envoi du code de vérification"));
  }

  return response.json();
}

/**
 * Request password change - POST /auth/password/change
 * For authenticated users who want to change their password
 * Sends verification code to user's email
 */
async function requestPasswordChange(data: {
  current_password: string;
}): Promise<{ message: string; email: string }> {
  // Get token from proper storage (taxasge_auth object)
  const authData = getAuthData();
  if (!authData?.access_token) {
    throw new Error('Not authenticated');
  }
  const accessToken = authData.access_token;

  const response = await fetch(`${AUTH_API_URL}/password/change`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${accessToken}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(extractErrorMessage(error, 'Échec de la demande de changement de mot de passe'));
  }

  return response.json();
}

/**
 * Verify password change - POST /auth/password/change/verify
 * Complete password change with verification code
 */
async function verifyPasswordChange(data: {
  email: string;
  verification_code: string;
  new_password: string;
}): Promise<{ message: string }> {
  const response = await fetch(`${AUTH_API_URL}/password/change/verify`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(extractErrorMessage(error, 'Échec de la vérification du changement de mot de passe'));
  }

  return response.json();
}

export const authApi = {
  login,
  verify2FA,
  register,
  requestVerificationCode,
  refreshToken,
  logout,
  getProfile,
  requestPasswordReset,
  confirmPasswordReset,
  requestPasswordChange,
  verifyPasswordChange,
  verifyEmail,
  resendEmailVerification,
  getSessions,
};

export type {
  LoginRequest,
  RegisterRequest,
  TokenResponse,
  TwoFactorLoginResponse,
  TwoFactorVerifyRequest,
  UserProfile,
  Session,
  LogoutRequest,
  LogoutResponse,
  PasswordResetRequestRequest,
  PasswordResetRequestResponse,
  PasswordResetConfirmRequest,
  PasswordResetConfirmResponse,
  EmailVerifyRequest,
  EmailVerifyResponse,
};

/**
 * Enable 2FA - POST /auth/2fa/enable
 * Returns QR code and backup codes for setup
 */
async function enable2FA(accessToken: string): Promise<{
  secret: string;
  qr_code_svg: string;
  backup_codes: string[];
}> {
  const response = await fetch(`${AUTH_API_URL}/2fa/enable`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${accessToken}`,
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(extractErrorMessage(error, "Impossible d'activer la 2FA"));
  }

  return response.json();
}

/**
 * Verify 2FA setup - POST /auth/2fa/verify
 * Confirms 2FA setup with TOTP code
 */
async function verify2FASetup(
  accessToken: string,
  data: { secret: string; code: string; backup_codes: string[] }
): Promise<{
  message: string;
  two_factor_enabled: boolean;
}> {
  const response = await fetch(`${AUTH_API_URL}/2fa/verify`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${accessToken}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(extractErrorMessage(error, 'Échec de la vérification de la configuration 2FA'));
  }

  return response.json();
}

/**
 * Disable 2FA - POST /auth/2fa/disable
 * Requires password confirmation
 */
async function disable2FA(accessToken: string, password: string): Promise<{ message: string }> {
  const response = await fetch(`${AUTH_API_URL}/2fa/disable`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${accessToken}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ password }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(extractErrorMessage(error, 'Impossible de désactiver la 2FA'));
  }

  return response.json();
}

/**
 * Get 2FA status - GET /auth/2fa/status
 */
async function get2FAStatus(accessToken: string): Promise<{
  two_factor_enabled: boolean;
  enabled_at: string | null;
}> {
  const response = await fetch(`${AUTH_API_URL}/2fa/status`, {
    method: 'GET',
    headers: {
      Authorization: `Bearer ${accessToken}`,
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(extractErrorMessage(error, 'Échec du chargement du statut 2FA'));
  }

  return response.json();
}

// Update exports
export const authApi2FA = {
  enable: enable2FA,
  verifySetup: verify2FASetup,
  disable: disable2FA,
  getStatus: get2FAStatus,
};
