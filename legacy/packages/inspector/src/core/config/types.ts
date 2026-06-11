/**
 * Shared TypeScript Types - Facil Inspeccion
 *
 * Core type definitions for the inspection mobile app.
 * Types mirror backend Pydantic models.
 */

export type SupportedLanguage = 'es' | 'fr' | 'en';

export interface FuncionarioStatus {
  verified: boolean;
  is_active: boolean;
  is_expired: boolean;
  expires_at?: string;
  source?: string;
  checked_at?: string;
  found_in_registry?: boolean;
}

export interface UserProfile {
  id: string;
  email: string;
  role: string;
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
  // Agent profile fields (from /profiles/me)
  entity_location_id?: string;
  entity_code?: string;
  location_city?: string;
  location_region?: string;
  is_main_office?: boolean;
  ministry_id?: number | null;
  is_supervisor_agent?: boolean;
}

export function getFullName(user: Pick<UserProfile, 'first_name' | 'last_name'>): string {
  return `${user.first_name} ${user.last_name}`.trim();
}

/** Inspector context resolved from agent_profiles + permissions */
export interface InspectorContext {
  agentProfileId: string;
  entityId: string;
  entityCode: string;
  entityLocationId: string;
  locationName: string;
  region: string;
  isSupervisor: boolean;
  hasInspectionCreate: boolean;
  hasSealApprove: boolean;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: UserProfile;
}

export interface TokenRefreshResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user?: UserProfile;
}

export interface TwoFactorLoginResponse {
  requires_2fa: true;
  temp_token: string;
  message: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface ApiSuccessResponse {
  message: string;
}

export interface LogoutRequest {
  refresh_token?: string;
  all_sessions?: boolean;
}

export interface LogoutResponse {
  message: string;
  sessions_revoked: number;
}
