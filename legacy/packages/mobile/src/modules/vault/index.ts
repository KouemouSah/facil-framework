/**
 * Public surface of the vault feature module.
 *
 * Components live in `./components/`, screens in `app/documents/*`.
 */

export * from './types/vault.types';
export * as vaultApi from './services/vault-api';
export {
  // List + reads
  useVaultList,
  useVaultStats,
  useVaultGenerated,
  useVaultDocument,
  useVaultVersions,
  useVaultSearch,
  // Mutations
  useUpdateVaultDocument,
  useArchiveVaultDocument,
  useDeleteVaultDocument,
  useReclassifyVaultDocument,
  useUploadVaultDocument,
  // Alerts
  useVaultAlerts,
  useMarkAlertRead,
  useDismissAlert,
  // Readiness + workflow
  useVaultReadinessForWorkflow,
  useVaultReadinessAll,
  useDocumentsForWorkflow,
  // Signed URLs
  useDownloadUrl,
  useThumbnailUrl,
  // Bulk + export
  useBulkAction,
  useStartExport,
  useExportStatus,
  getExportDownload,
} from './services/vault-hooks';
export { computeFileHash, readFileMeta } from './services/vault-hash';
export { VaultPickerSheet } from './components/vault-picker-sheet';
export { ReadinessBanner } from './components/readiness-banner';
