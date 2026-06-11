/**
 * Permissions Admin Hooks
 * Barrel export for permission query hooks
 *
 * NOTE: Role hooks are in @/modules/roles-admin/hooks/useRoles
 *       User permission hooks are in @/modules/user-permissions-admin/hooks/useUserPermissions
 *       These were previously duplicated here and have been removed.
 */

export {
  usePermissions,
  usePermission,
  usePermissionsByResource,
  useModuleNames,
  useResources,
  permissionsKeys,
} from "./usePermissions";
