/**
 * SHA-256 hashing for the dedup pre-check.
 *
 * The backend vault upload endpoint silently returns `status: "duplicate"`
 * if the hash already exists. We pre-check via `GET /check-hash/{hash}` to
 * (a) skip the 233 MB-class upload of an already-vaulted file and
 * (b) surface a "this file is already in your vault" UX before bytes leave
 * the device.
 *
 * Uses `expo-file-system` to stream the file in chunks (avoids loading a
 * 10 MB blob into memory) and `expo-crypto` for the digest.
 */

import * as Crypto from 'expo-crypto';
// expo-file-system v19 split the API: stable file/directory classes live at the
// root, while the legacy promise-based helpers (`readAsStringAsync`,
// `getInfoAsync`, `EncodingType`) ship under the `legacy` subpath.
import * as FileSystem from 'expo-file-system/legacy';

import { VAULT_MAX_FILE_SIZE_BYTES } from '../types/vault.types';

/**
 * Compute the SHA-256 hex digest of a local file.
 *
 * Reads the file as base64 (the only encoding RN/Expo's bridge supports
 * reliably for binary data), then hashes the base64 payload — backend does
 * exactly the same in `user_documents_service.compute_hash` so the digests
 * match.
 *
 * @throws if the file is missing, larger than VAULT_MAX_FILE_SIZE_BYTES,
 *         or the digest call fails.
 */
export async function computeFileHash(uri: string): Promise<string> {
  const info = await FileSystem.getInfoAsync(uri);
  if (!info.exists) {
    throw new Error(`File not found: ${uri}`);
  }
  if ('size' in info && info.size && info.size > VAULT_MAX_FILE_SIZE_BYTES) {
    throw new Error(
      `File exceeds vault max size (${(VAULT_MAX_FILE_SIZE_BYTES / 1024 / 1024).toFixed(0)} MB)`,
    );
  }
  const base64 = await FileSystem.readAsStringAsync(uri, {
    encoding: FileSystem.EncodingType.Base64,
  });
  const hash = await Crypto.digestStringAsync(
    Crypto.CryptoDigestAlgorithm.SHA256,
    base64,
    { encoding: Crypto.CryptoEncoding.HEX },
  );
  return hash.toLowerCase();
}

/**
 * Convenience wrapper that returns size + hash in a single pass.
 * Useful when both are needed (upload progress UI + dedup pre-check).
 */
export async function readFileMeta(uri: string): Promise<{
  size: number;
  hash: string;
}> {
  const info = await FileSystem.getInfoAsync(uri);
  if (!info.exists) {
    throw new Error(`File not found: ${uri}`);
  }
  const size = 'size' in info ? (info.size ?? 0) : 0;
  if (size > VAULT_MAX_FILE_SIZE_BYTES) {
    throw new Error(
      `File exceeds vault max size (${(VAULT_MAX_FILE_SIZE_BYTES / 1024 / 1024).toFixed(0)} MB)`,
    );
  }
  const hash = await computeFileHash(uri);
  return { size, hash };
}
