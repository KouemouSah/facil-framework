/**
 * User Documents Hooks - Barrel Export
 *
 * @module user-documents/hooks
 * @date 2026-04-05
 */

// Query key factory (for external cache invalidation)
export { userDocumentKeys } from './useUserDocuments';

// Document listing, detail, mutations, stats, alerts, readiness
export {
  useUserDocuments,
  useUserDocument,
  useDocumentMutations,
  useDocumentStats,
  useDocumentAlerts,
  useReadiness,
  useDocumentVersions,
} from './useUserDocuments';

// Upload with progress tracking and dedup detection
export {
  useDocumentUpload,
  type UploadFileState,
  type UploadOptions,
  type UseDocumentUploadReturn,
} from './useDocumentUpload';

// Platform-generated documents (certificates, receipts, etc.)
export { useGeneratedDocuments } from './useGeneratedDocuments';
