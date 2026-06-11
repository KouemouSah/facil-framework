/**
 * Support Module
 *
 * A complete support ticketing system for:
 * - Users to request help and report issues
 * - Agents to request technical support from administration
 * - Admins to manage and respond to support tickets
 *
 * @module support
 * @author Claude Code
 * @date 2025-12-17
 */

export * from './components'
export { useSupport } from './hooks/useSupport'
export { supportApi } from './services/api'
export * from './types'
