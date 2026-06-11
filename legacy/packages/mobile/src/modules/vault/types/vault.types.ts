/**
 * Vault feature types — re-exports from api-types + UI-only derived shapes.
 *
 * Source of truth: `src/core/api/api-types.ts` → openapi-types.
 */

import type {
  AlertResponse,
  GeneratedDocumentResponse,
  HashCheckResponse,
  ReadinessItem,
  ReadinessResult,
  UploadResult,
  UseVaultDocumentRequest,
  UserDocumentBulkAction,
  UserDocumentListItem,
  UserDocumentListResponse,
  UserDocumentResponse,
  UserDocumentStats,
  UserDocumentUpdate,
} from '@core/api/api-types';

// Re-exports for convenience inside the vault module.
export type {
  AlertResponse,
  GeneratedDocumentResponse,
  HashCheckResponse,
  ReadinessItem,
  ReadinessResult,
  UploadResult,
  UseVaultDocumentRequest,
  UserDocumentBulkAction,
  UserDocumentListItem,
  UserDocumentListResponse,
  UserDocumentResponse,
  UserDocumentStats,
  UserDocumentUpdate,
};

// ---------------------------------------------------------------------------
// UI-only derived types
// ---------------------------------------------------------------------------

/** Filter chip values shown above the vault list. */
export type VaultFilterValue =
  | 'all'
  | 'personal'
  | 'wizard'
  | 'generated'
  | 'expiring'
  | 'expired';

/** Tab selector at the top of the vault home. */
export type VaultTabValue = 'uploads' | 'generated' | 'alerts';

/** State carried across the upload bottom sheet UI. */
export interface UploadProgress {
  status: 'idle' | 'hashing' | 'checking' | 'uploading' | 'done' | 'error' | 'duplicate';
  progress: number; // 0..1
  errorMessage?: string;
  duplicateOf?: HashCheckResponse['document'];
  result?: UploadResult;
}

/** Picker context handed to VaultPickerSheet from the wizard step-upload. */
export interface VaultPickerContext {
  workflowCode: string;
  documentCode: string;
  /** Optional vault `document_type` to pre-filter by (saves a round-trip). */
  documentTypeHint?: string;
}

/** Possible MIME types accepted by the backend vault upload endpoint. */
export const VAULT_ALLOWED_MIME_TYPES = [
  'application/pdf',
  'image/jpeg',
  'image/png',
  'image/webp',
] as const;

export type VaultAllowedMime = (typeof VAULT_ALLOWED_MIME_TYPES)[number];

/** 10 MB hard limit on the backend (`MAX_FILE_SIZE_BYTES`). */
export const VAULT_MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024;
/** 100 MB total quota per user. */
export const VAULT_QUOTA_BYTES = 100 * 1024 * 1024;
/** Max files in a single bulk-upload call. */
export const VAULT_MAX_BULK_UPLOAD = 5;
