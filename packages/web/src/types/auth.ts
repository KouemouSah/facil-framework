/**
 * Authentication Types
 * 100% aligned with TaxasGE Backend Pydantic models
 * Source: packages/backend/app/models/user.py & auth_models.py
 */

// User Role Enum (aligned with user_role_enum from migration 048)
// Simplified roles - deprecated supervisor roles removed
export type UserRole =
  | 'citizen'
  | 'business'
  | 'accountant'
  | 'admin'
  | 'agent'           // Unified agent role (includes supervisors via is_supervisor flag)
  | 'funcionario';    // Civil servant role

// User Status Enum (aligned with backend UserStatus)
export type UserStatus = 'active' | 'inactive' | 'suspended' | 'pending_verification';

// User Profile (aligned with backend UserProfile)
export interface UserProfile {
  first_name: string;
  last_name: string;
  phone?: string;
  address?: string;
  city?: string;
  language: 'es' | 'fr' | 'en';
  avatar_url?: string;
}

// Citizen Profile (aligned with backend CitizenProfile)
export interface CitizenProfile extends UserProfile {
  national_id?: string;
  birth_date?: string;
  gender?: 'M' | 'F' | 'O';
  marital_status?: 'single' | 'married' | 'divorced' | 'widowed';
  occupation?: string;
}

// Business Profile (aligned with backend BusinessProfile)
export interface BusinessProfile extends UserProfile {
  business_name: string;
  business_type: 'sole_proprietor' | 'corporation' | 'partnership' | 'cooperative' | 'ngo';
  tax_id?: string;
  registration_number?: string;
  industry?: string;
  employee_count?: number;
  annual_revenue?: number;
  website?: string;
}

// User object returned from backend (aligned with users table in DATABASE_SCHEMA_REFERENCE.md)
export interface User {
  id: string;
  email: string;
  role: UserRole;
  status: UserStatus;
  first_name: string;
  last_name: string;
  full_name?: string;
  matricule?: string;
  phone_number?: string;
  document_type?: string;
  document_number?: string;
  preferred_language?: string;
  email_notifications?: boolean;
  push_notifications?: boolean;
  sms_notifications?: boolean;
  email_verified?: boolean;
  phone_verified?: boolean;
  address?: string;
  city?: string;
  avatar_url?: string;
  created_at: string;
  updated_at: string;
  last_login?: string;
  two_factor_enabled?: boolean;
  is_active: boolean;

  // Funcionario (civil servant) verification fields
  matricula_funcionario?: string;
  funcionario_verified_at?: string;
  funcionario_verified_by?: string;

  // Funcionario status from verified_identifiers table (real-time check)
  funcionario_status?: FuncionarioStatus;

  // RBAC role code from roles table (e.g. 'admin_agents', 'agent_cnedoge_pasaporte')
  role_code?: string;

  // Permissions from role_permissions and user_permissions
  permissions?: string[];
}

/**
 * Funcionario Status - Real-time status from verified_identifiers table
 * Used to control access to Funcionario menu and services
 *
 * Fields based on verified_identifiers schema:
 * - is_active (boolean): true = active, false = deactivated/suspended
 * - expires_at (timestamp): NULL = no expiry, or expiration date
 */
export interface FuncionarioStatus {
  /** User has been verified as funcionario (funcionario_verified_at exists) */
  verified: boolean;
  /** Matricula is active in verified_identifiers (is_active = true) */
  is_active: boolean;
  /** Matricula has expired (expires_at < now) */
  is_expired: boolean;
  /** Expiration date if applicable (NULL = no expiry) */
  expires_at: string | null;
  /** Source of verification (ministerio_funcion_publica, agent_manual, etc.) */
  source: string | null;
  /** Timestamp when status was checked */
  checked_at: string;
  /** Found in verified_identifiers table */
  found_in_registry: boolean;
}

// Login Request
export interface LoginRequest {
  email: string;
  password: string;
  remember_me?: boolean;
}

// Register Request
export interface RegisterRequest {
  email: string;
  password: string;
  first_name: string;
  last_name: string;
  phone?: string;
  role?: UserRole;
}

// Token Response (when 2FA disabled)
export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

// 2FA Login Response (when 2FA enabled)
export interface TwoFactorLoginResponse {
  requires_2fa: boolean;
  temp_token: string;
  message: string;
}

// 2FA Verify Request
export interface TwoFactorVerifyRequest {
  temp_token: string;
  code: string;
}

// Session (aligned with backend Session)
export interface Session {
  id: string;
  user_id: string;
  device_info: Record<string, string>;
  ip_address: string;
  user_agent: string;
  created_at: string;
  last_activity: string;
  is_current: boolean;
}

// Password Reset Request
export interface PasswordResetRequest {
  email: string;
}

export interface PasswordResetResponse {
  message: string;
  email: string;
}

// Password Reset Confirm
export interface PasswordResetConfirm {
  token: string;
  new_password: string;
}

export interface PasswordResetConfirmResponse {
  message: string;
}

// Password Change (for authenticated users)
export interface PasswordChangeRequest {
  current_password: string;
}

export interface PasswordChangeResponse {
  message: string;
  email: string;
}

export interface PasswordChangeVerifyRequest {
  email: string;
  verification_code: string;
  new_password: string;
}

export interface PasswordChangeVerifyResponse {
  message: string;
}

// Email Verification
export interface EmailVerifyRequest {
  verification_code: string;
}

export interface EmailVerifyResponse {
  message: string;
}

export interface EmailResendResponse {
  message: string;
  email: string;
}

// Logout Request
export interface LogoutRequest {
  access_token: string;
  refresh_token: string;
}

export interface LogoutResponse {
  message: string;
}

// Profile Update
export interface ProfileUpdateRequest {
  first_name?: string;
  last_name?: string;
  phone?: string;
  address?: string;
  city?: string;
  language?: 'es' | 'fr' | 'en';
}

// Auth Data stored in localStorage
export interface AuthData {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

// API Error Response
export interface ApiError {
  detail: string;
  status_code?: number;
}

// =============================================================================
// MENU & DASHBOARD CONFIGURATION
// =============================================================================

/**
 * Dynamic menu configuration types
 * Used for agent dashboards with configurable menus from backend
 */

// Menu badge configuration
export interface MenuBadgeConfig {
  type: 'count' | 'status';
  source: string;
}

// Sub-menu item in a menu group
export interface SubMenuItemConfig {
  id: string;
  titleKey: string;
  href: string;
  icon: string;
  permission?: string;
  badge?: MenuBadgeConfig;
}

// Menu item (can be a direct link or a group with sub-items)
export interface MenuItemConfig {
  id: string;
  titleKey: string;
  icon: string;
  href?: string;
  permission?: string;
  items?: SubMenuItemConfig[];
}

// Source of menu configuration
export type MenuConfigSource = 'workflow' | 'role' | 'custom';

// Complete menu configuration
export interface MenuConfig {
  version: string;
  source: MenuConfigSource;
  menus: MenuItemConfig[];
}

// Widget size options
export type WidgetSize = 'small' | 'medium' | 'large' | 'full';

// Widget configuration for dashboard
export interface WidgetConfig {
  id: string;
  visible: boolean;
  position: number;
  size: WidgetSize;
  customConfig?: Record<string, unknown>;
}

// Dashboard layout options
export type DashboardLayout = 'grid' | 'list' | 'custom';

// Complete dashboard configuration
export interface DashboardConfig {
  version: string;
  layout: DashboardLayout;
  widgets: WidgetConfig[];
}

// Extended AuthData with menu configuration (for agents)
export interface AuthDataWithMenuConfig extends AuthData {
  menu_config?: MenuConfig;
  dashboard_config?: DashboardConfig;
  permissions?: string[];
}
