/**
 * User Documents Components - Barrel Export
 *
 * @module user-documents/components
 */

export { DocumentVault } from './DocumentVault';
export { PersonalDocumentsGrid } from './PersonalDocumentsGrid';
export { GeneratedDocumentsGrid } from './GeneratedDocumentsGrid';
export { AlertsTab } from './AlertsTab';
export { ReadinessCheck } from './ReadinessCheck';
export { DocumentUploadDialog } from './DocumentUploadDialog';
export { DocumentCard } from './DocumentCard';
export { DocumentDetailSheet } from './DocumentDetailSheet';
export { DocumentPreview } from './DocumentPreview';
export { ExpiryBadge } from './ExpiryBadge';
export { WorkflowTagChips } from './WorkflowTagChips';

// Phase 2 - Agent Settings, Action Confirm, Proactive Notifications
export { AgentSettingsPanel } from './AgentSettingsPanel';
export { ActionConfirmCard } from './ActionConfirmCard';
export type { ActionConfirmCardAction, ActionConfirmCardProps } from './ActionConfirmCard';
export { ProactiveNotificationCard } from './ProactiveNotificationCard';
export type { ProactiveNotification, ProactiveNotificationCardProps } from './ProactiveNotificationCard';

// Vault Picker (wizard integration)
export { VaultDocumentPicker } from './VaultDocumentPicker';
export type { VaultDocumentPickerProps } from './VaultDocumentPicker';

// Phase 3 - Onboarding
export { AgentOnboarding } from './AgentOnboarding';
