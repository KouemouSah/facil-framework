/**
 * Shared TypeScript Types
 *
 * Core type definitions used across the Facil mobile app.
 * Types mirror the backend Pydantic models to ensure full-stack type safety.
 *
 * IMPORTANT: Keep in sync with backend models in:
 * - packages/backend/app/modules/auth/api/auth_routes.py
 * - packages/backend/app/modules/users/models/user.py
 * - packages/backend/app/modules/auth/models/auth_models.py
 */

import type { USER_ROLES } from '@core/config/constants';

// ---------------------------------------------------------------------------
// Utility Types
// ---------------------------------------------------------------------------

/** Extract union of object values */
export type ValueOf<T> = T[keyof T];

/** User role union derived from constants */
export type UserRole = ValueOf<typeof USER_ROLES>;

/** Supported i18n languages */
export type SupportedLanguage = 'es' | 'fr' | 'en';

// ---------------------------------------------------------------------------
// User & Auth
// ---------------------------------------------------------------------------

/**
 * Funcionario verification status from verified_identifiers table.
 */
export interface FuncionarioStatus {
  verified: boolean;
  is_active: boolean;
  is_expired: boolean;
  expires_at?: string;
  source?: string;
  checked_at?: string;
  found_in_registry?: boolean;
}

/**
 * User profile as returned by GET /users/profile and GET /auth/profile.
 *
 * Maps to the backend UserResponse model.
 * Stored in MMKV (non-sensitive) for fast sync access.
 *
 * IMPORTANT: Backend returns `phone_number` (not `phone`).
 * `full_name` is NOT returned by backend — computed client-side.
 */
export interface UserProfile {
  id: string;
  email: string;
  role: UserRole;
  role_code?: string;
  status: string;
  first_name: string;
  last_name: string;
  phone_number?: string;
  address?: string;
  city?: string;
  preferred_language: SupportedLanguage;
  avatar_url?: string;
  created_at: string;
  updated_at?: string;
  last_login?: string;
  email_verified?: boolean;
  two_factor_enabled?: boolean;
  email_notifications?: boolean;
  push_notifications?: boolean;
  sms_notifications?: boolean;
  permissions?: string[];
  entity_id?: string;
  entity_name?: string;
  matricula_funcionario?: string;
  funcionario_verified_at?: string;
  funcionario_verified_by?: string;
  funcionario_status?: FuncionarioStatus;
}

/**
 * Computed full name helper.
 * Backend does NOT return full_name — use this function instead.
 */
export function getFullName(user: Pick<UserProfile, 'first_name' | 'last_name'>): string {
  return `${user.first_name} ${user.last_name}`.trim();
}

/**
 * Token response from POST /auth/login or POST /auth/register.
 *
 * Maps to backend TokenResponse model.
 * Tokens are stored in SecureStore; user data in MMKV.
 */
export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: UserProfile;
}

/**
 * Token refresh response from POST /auth/refresh.
 *
 * Maps to backend TokenRefreshResponse model.
 * May include updated user data (role_code/permissions changes).
 */
export interface TokenRefreshResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user?: UserProfile;
}

/**
 * 2FA login response when user has TOTP enabled.
 *
 * Maps to backend TwoFactorLoginResponse model.
 * The temp_token has 5-minute validity.
 */
export interface TwoFactorLoginResponse {
  requires_2fa: true;
  temp_token: string;
  message: string;
}

/**
 * Registration data sent to POST /auth/register.
 *
 * Maps to backend RegisterRequest model.
 * IMPORTANT: Field names must match backend exactly:
 * - `phone` (not phone_number) - backend RegisterRequest accepts `phone`
 * - `verification_code` - 6-digit code from email verification step
 */
export interface RegisterData {
  email: string;
  verification_code: string;
  password: string;
  first_name: string;
  last_name: string;
  phone: string;
  role?: UserRole;
  address?: string;
  city?: string;
  preferred_language?: SupportedLanguage;
  // Phase 10/B — Legal acceptance (mobile-only, citizen/business/accountant).
  // Backend validates exact match against settings.LEGAL_*_VERSION and
  // persists users.terms_* / users.privacy_* columns. Optional so other
  // clients (web V1) can still register without it.
  // See migration 331 + .claude/plans/MOBILE_PHASE_10_B_LEGAL_DETAILED.md
  terms_version_accepted?: string;
  privacy_version_accepted?: string;
}

// ---------------------------------------------------------------------------
// Request Verification
// ---------------------------------------------------------------------------

/** Response from POST /auth/request-verification-code */
export interface RequestVerificationResponse {
  message: string;
  email: string;
  expires_in: number;
}

// ---------------------------------------------------------------------------
// Password Reset (public, 2-step)
// ---------------------------------------------------------------------------

/** Response from POST /auth/password/reset/request */
export interface PasswordResetRequestResponse {
  message: string;
  email: string;
}

/** Request body for POST /auth/password/reset/confirm */
export interface PasswordResetConfirmRequest {
  token: string;
  new_password: string;
}

/** Response from POST /auth/password/reset/confirm */
export interface PasswordResetConfirmResponse {
  message: string;
}

// ---------------------------------------------------------------------------
// Password Change (authenticated, 2-step via auth route)
// ---------------------------------------------------------------------------

/** Request body for POST /auth/password/change (step 1) */
/** Request body for POST /users/profile/change-password */
export interface PasswordChangeRequest {
  old_password: string;
  new_password: string;
}

/** Response from POST /users/profile/change-password */
export interface PasswordChangeResponse {
  message: string;
}

// ---------------------------------------------------------------------------
// Email Verification
// ---------------------------------------------------------------------------

/** Request body for POST /auth/email/verify */
export interface EmailVerifyRequest {
  verification_code: string;
}

/** Response from POST /auth/email/verify */
export interface EmailVerifyResponse {
  message: string;
}

/** Response from POST /auth/email/resend */
export interface EmailResendResponse {
  message: string;
  email: string;
}

// ---------------------------------------------------------------------------
// Sessions
// ---------------------------------------------------------------------------

/** Single active session info */
export interface SessionInfo {
  id: string;
  device: string;
  browser: string;
  location: string;
  ip_address?: string;
  created_at: string;
  last_activity: string;
  expires_at: string;
  is_current: boolean;
}

/** Response from GET /auth/sessions */
export interface SessionsListResponse {
  sessions: SessionInfo[];
  total: number;
}

// ---------------------------------------------------------------------------
// Two-Factor Authentication Management
// ---------------------------------------------------------------------------

/** Response from POST /auth/2fa/enable */
export interface TwoFactorEnableResponse {
  secret: string;
  qr_code_svg: string;
  backup_codes: string[];
  message: string;
}

/** Request body for POST /auth/2fa/verify (setup verification) */
export interface TwoFactorSetupVerifyRequest {
  secret: string;
  code: string;
  backup_codes: string[];
}

/** Response from POST /auth/2fa/verify (setup verification) */
export interface TwoFactorSetupVerifyResponse {
  message: string;
  two_factor_enabled: boolean;
}

/** Request body for POST /auth/2fa/disable */
export interface TwoFactorDisableRequest {
  password: string;
}

/** Response from POST /auth/2fa/disable */
export interface TwoFactorDisableResponse {
  message: string;
  two_factor_enabled: boolean;
}

/** Response from GET /auth/2fa/status */
export interface TwoFactorStatusResponse {
  two_factor_enabled: boolean;
  backup_codes_remaining?: number;
}

// ---------------------------------------------------------------------------
// Profile Update (PUT /users/profile)
// ---------------------------------------------------------------------------

/** Request body for PUT /users/profile */
export interface UserUpdateRequest {
  first_name?: string;
  last_name?: string;
  email?: string;
  phone_number?: string;
  address?: string;
  city?: string;
  preferred_language?: SupportedLanguage;
  avatar_url?: string;
  email_notifications?: boolean;
  push_notifications?: boolean;
  sms_notifications?: boolean;
}

/** Request body for POST /users/profile/change-password */
export interface ProfilePasswordChangeRequest {
  old_password: string;
  new_password: string;
}

/** Response from POST /users/profile/change-password */
export interface ProfilePasswordChangeResponse {
  message: string;
}

/** Logout request body */
export interface LogoutRequest {
  refresh_token?: string;
  all_sessions?: boolean;
}

/** Logout response */
export interface LogoutResponse {
  message: string;
  sessions_revoked: number;
}

// ---------------------------------------------------------------------------
// Pagination
// ---------------------------------------------------------------------------

/**
 * Generic paginated response wrapper.
 *
 * Used by all list endpoints that support pagination.
 * Backend uses `items` array + metadata fields.
 */
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

// ---------------------------------------------------------------------------
// Service Requests
// ---------------------------------------------------------------------------

/** Service request status in list views */
export interface ServiceRequestListItem {
  id: string;
  workflow_code: string;
  workflow_name: string;
  status: string;
  current_step: number;
  total_steps: number;
  created_at: string;
  updated_at: string;
  reference_number?: string;
}

/** Dashboard summary response from GET /service-requests/dashboard-summary */
export interface DashboardSummary {
  stats: {
    active: number;
    completed: number;
    pending_action: number;
    total_paid: number;
  };
  recent_requests: ServiceRequestListItem[];
  recent_payments: PaymentListItem[];
  notifications: NotificationItem[];
  unread_count: number;
  upcoming_appointment?: AppointmentInfo;
  action_required?: ActionRequiredInfo;
}

/** Payment list item for dashboard/lists */
export interface PaymentListItem {
  id: string;
  amount: number;
  currency: string;
  status: string;
  payment_method: string;
  created_at: string;
  service_name?: string;
}

/** Notification item for citizen notifications panel */
export interface NotificationItem {
  id: string;
  type: string;
  message: string;
  created_at: string;
  is_read: boolean;
  request_id?: string;
}

/** Upcoming appointment info */
export interface AppointmentInfo {
  date: string;
  time: string;
  location: string;
  service_name: string;
  request_id: string;
}

/** Action required banner info */
export interface ActionRequiredInfo {
  request_id: string;
  message: string;
  action_type: string;
}

// ---------------------------------------------------------------------------
// Fiscal Services
// ---------------------------------------------------------------------------

/** Fiscal service catalog item */
export interface FiscalService {
  id: string;
  name_es: string;
  name_fr?: string;
  name_en?: string;
  description_es?: string;
  description_fr?: string;
  description_en?: string;
  ministry_id?: string;
  ministry_name?: string;
  sector_id?: string;
  category_id?: string;
  category_name?: string;
  service_type: string;
  status: string;
  base_price?: number;
  currency?: string;
  workflow_code?: string;
}

// ---------------------------------------------------------------------------
// API Response Helpers
// ---------------------------------------------------------------------------

/** Standard API success response with message */
export interface ApiSuccessResponse {
  message: string;
}

/** API error response shape (matches extractApiError output) */
export interface ApiErrorResponse {
  detail: string | { loc: (string | number)[]; msg: string; type: string }[];
  code?: string;
}
