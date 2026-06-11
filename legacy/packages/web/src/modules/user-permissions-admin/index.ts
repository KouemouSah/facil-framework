/**
 * User Permissions Admin Module
 * Manage individual user permission overrides
 *
 * @module user-permissions-admin
 * @author Claude Code
 * @date 2025-12-04
 */

// Types
export * from './types'

// API
export { userPermissionsApi } from './services/api'

// Hooks
export {
  userPermissionsKeys,
  useUserPermissionsList,
  useUserPermissions,
  useSearchUsers,
  useSearchAgents,
  useGrantPermission,
  useRevokePermission,
  useCheckPermission,
} from './hooks/useUserPermissions'

// Components
export { UserSelector, GrantPermissionDialog, UserPermissionList } from './components'
