/**
 * Service Requests Module
 *
 * Provides components and hooks for managing service request workflows.
 *
 * Components:
 * - WorkflowWizard: Multi-step wizard for citizens
 * - DocumentUploader: Drag & drop document upload with preview
 * - ExtractionPreview: Display extracted data with confidence indicators
 * - AgentDashboard: Agent dashboard for processing requests
 * - RequestDetail: Detailed view with agent actions
 *
 * Hooks:
 * - useServiceRequests: State management for service requests
 *
 * Usage:
 * ```tsx
 * import { WorkflowWizard, useServiceRequests } from '@/modules/service-requests'
 *
 * function MyPage() {
 *   return <WorkflowWizard workflowCode="PASAPORTE_NUEVO" />
 * }
 * ```
 */

// Components
export * from './components'

// Hooks
export * from './hooks'

// Services
export * from './services'

// Types
export * from './types'
