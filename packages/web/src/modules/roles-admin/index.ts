/**
 * Roles Admin Module
 * Role management for admin dashboard
 *
 * @module roles-admin
 * @author Claude Code
 * @date 2025-12-04
 */

// Types
export * from './types'

// API
export { rolesApi, permissionsSimulatorApi } from './services/api'

// Hooks
export {
  rolesKeys,
  useRoles,
  useSystemRoles,
  useCustomRoles,
  useRole,
  useRoleWithPermissions,
  useCreateRole,
  useUpdateRole,
  useDeleteRole,
  useAssignPermissions,
  useRemovePermissions,
  usePermissionMatrix,
  useCloneRole,
  useBulkDeleteRoles,
  useSimulateRolePermission,
  useSimulateUserRoleChange,
  useOverprivilegedUsers,
} from './hooks/useRoles'

export { useRbacWebSocket } from './hooks/useRbacWebSocket'

// Components
export { RolePermissionsDialog } from './components/RolePermissionsDialog'
export { RolesTab } from './components/RolesTab'
export { PermissionsCatalogTab } from './components/PermissionsCatalogTab'
export { UserPermissionsTab } from './components/UserPermissionsTab'
export { PermissionMatrix } from './components/PermissionMatrix'
export { PermissionSimulatorTab } from './components/PermissionSimulatorTab'
