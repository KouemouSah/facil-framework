/**
 * Translations Module
 * Centralized translation management for admin
 *
 * @module translations
 *
 * Features:
 * - Entity translations (ministry, sector, category)
 * - System translations (ENUMs, UI, forms, messages)
 * - Frontend translations (next-intl JSON sync)
 */

// Types
export * from './types'

// Services
export { translationsApi, entityTranslationsApi, systemTranslationsApi, frontendTranslationsApi } from './services/api'

// Hooks
export * from './hooks'

// Components (to be added)
export * from './components'
