/**
 * Permission Types for TaxasGE Permissions Module
 * Corresponds to backend models in app/modules/permissions/models/
 *
 * @module permissions-admin/types
 * @author Claude Code
 * @date 2025-11-17
 */

// =============================================================================
// CORE TYPES
// =============================================================================

/**
 * Permission - Represents a single permission
 * Corresponds to backend Permission model
 */
export interface Permission {
  id: string;
  name: string;                    // e.g., "assignment.create"
  resource: string;                // e.g., "assignment"
  action: string;                  // e.g., "create"
  description: string;             // Spanish description
  is_critical: boolean;            // If true, requires special confirmation
  module_name: string;             // e.g., "assignment", "declarations"
  created_at: string;
  updated_at: string;
}

/**
 * Role - Represents a role with associated permissions
 * Corresponds to backend Role model
 */
export interface Role {
  id: string;
  name: string;                    // e.g., "Superviseur Junior DGI"
  code: string;                    // e.g., "supervisor_dgi_junior"
  entity_type: string | null;      // "DGI", "Ministry", or null (global)
  description: string;
  is_system: boolean;              // If true, cannot be edited/deleted
  created_at: string;
  updated_at: string;
  created_by: string | null;
}

/**
 * RolePermission - Association between Role and Permission
 * Corresponds to backend RolePermission model
 */
export interface RolePermission {
  role_id: string;
  permission_id: string;
  granted: boolean;                // true = granted, false = explicitly denied
  created_at: string;
  created_by: string | null;
}

/**
 * UserPermission - Permission override for specific user
 * Corresponds to backend UserPermission model
 */
export interface UserPermission {
  user_id: string;
  permission_id: string;
  granted: boolean;
  granted_by: string | null;
  granted_at: string;
  expires_at: string | null;       // null = permanent, otherwise expires
  reason: string | null;           // Reason for granting (for audit)
}

/**
 * PermissionGrant - Audit log entry for permission changes
 * Corresponds to backend permission_audit_log table
 */
export interface PermissionGrant {
  id: string;
  action: "INSERT" | "UPDATE" | "DELETE";
  table_name: "role_permissions" | "user_permissions";
  record_id: string;
  user_id: string | null;
  permission_id: string | null;
  old_value: Record<string, unknown> | null;
  new_value: Record<string, unknown> | null;
  changed_by: string | null;
  changed_at: string;
}

// =============================================================================
// REQUEST/RESPONSE TYPES
// =============================================================================

/**
 * CreateRoleRequest - Request body for creating a new role
 */
export interface CreateRoleRequest {
  name: string;
  code: string;
  entity_type?: string | null;
  description: string;
  permissions?: string[];          // Array of permission IDs to grant
}

/**
 * UpdateRoleRequest - Request body for updating a role
 */
export interface UpdateRoleRequest {
  name?: string;
  description?: string;
  permissions?: string[];
}

/**
 * Grant User Permission Request - Request body for granting permission to user
 */
export interface GrantUserPermissionRequest {
  permission_id: string;
  granted: boolean;
  expires_at?: string | null;
  reason?: string;
}

/**
 * RoleWithPermissions - Role with its associated permissions loaded
 */
export interface RoleWithPermissions extends Role {
  permissions: Permission[];
  permissions_count: number;
  critical_permissions_count: number;
}

/**
 * UserWithPermissions - User with their effective permissions
 * (from role + individual overrides)
 */
export interface UserWithPermissions {
  user_id: string;
  email: string;
  full_name: string;
  role: Role;
  role_permissions: Permission[];        // From role
  user_permissions: UserPermission[];    // Individual overrides
  effective_permissions: Permission[];   // Combined (role + user)
}

// =============================================================================
// UI/DISPLAY TYPES
// =============================================================================

/**
 * PermissionCategory - Permissions grouped by resource
 */
export interface PermissionCategory {
  resource: string;
  module_name: string;
  permissions: Permission[];
  total_count: number;
  critical_count: number;
}

/**
 * RoleStats - Statistics for a role
 */
export interface RoleStats {
  role: Role;
  total_permissions: number;
  critical_permissions: number;
  users_count: number;              // Number of users with this role
  last_modified: string;
}

/**
 * PermissionFilter - Filters for permission list
 */
export interface PermissionFilter {
  module_name?: string;
  resource?: string;
  is_critical?: boolean;
  search?: string;                  // Search in name or description
}

/**
 * RoleFilter - Filters for role list
 */
export interface RoleFilter {
  entity_type?: string;
  is_system?: boolean;
  search?: string;
}

// =============================================================================
// FORM TYPES
// =============================================================================

/**
 * RoleFormData - Form data for creating/editing role
 */
export interface RoleFormData {
  name: string;
  code: string;
  entity_type: string;
  description: string;
  selected_permissions: Set<string>;  // Permission IDs
}

/**
 * UserPermissionFormData - Form data for granting user permission
 */
export interface UserPermissionFormData {
  permission_id: string;
  granted: boolean;
  expires_at: Date | null;
  reason: string;
}

// =============================================================================
// API RESPONSE TYPES
// =============================================================================

/**
 * PaginatedResponse - Generic paginated response
 */
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

/**
 * ErrorResponse - API error response
 */
export interface ErrorResponse {
  detail: string;
  code?: string;
  field?: string;
}

// =============================================================================
// CONSTANTS
// =============================================================================

/**
 * Entity Types
 */
export const ENTITY_TYPES = {
  DGI: "DGI",
  MINISTRY: "Ministry",
  GLOBAL: null,
} as const;

export type EntityType = typeof ENTITY_TYPES[keyof typeof ENTITY_TYPES];

/**
 * Permission Actions (common)
 */
export const PERMISSION_ACTIONS = {
  VIEW: "view",
  VIEW_ALL: "view_all",
  CREATE: "create",
  EDIT: "edit",
  DELETE: "delete",
  ACTIVATE: "activate",
  DEACTIVATE: "deactivate",
} as const;

/**
 * Module Names
 */
export const MODULE_NAMES = {
  ASSIGNMENT: "assignment",
  DECLARATIONS: "declarations",
  PERMISSIONS: "permissions",
} as const;

export type ModuleName = typeof MODULE_NAMES[keyof typeof MODULE_NAMES];
