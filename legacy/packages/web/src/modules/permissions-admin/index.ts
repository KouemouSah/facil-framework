/**
 * Permissions Admin Module
 * Permission and role management for administrators
 *
 * @module permissions-admin
 */

// Components
export * from './components'

// Hooks
export * from './hooks'

// Services
export { permissionsApi, rolesApi, userPermissionsApi } from './services/api'
export { default as permissionsAdminApi } from './services/api'

// Types
export * from './types'

// Providers
export { QueryProvider } from './providers/QueryProvider'
