/**
 * File hashing utility — SHA-256 via Web Crypto API
 *
 * Used for client-side deduplication: compute hash before upload
 * to check if the file already exists in the vault.
 *
 * Performance: ~200ms for 50MB file (native WebCrypto, not JS)
 *
 * @module core/utils/file-hash
 * @date 2026-04-25
 */

/**
 * Compute SHA-256 hash of a File object using Web Crypto API.
 *
 * @param file - File to hash
 * @returns 64-character lowercase hex string (SHA-256 digest)
 */
export async function computeFileHash(file: File): Promise<string> {
  const buffer = await file.arrayBuffer();
  const hashBuffer = await crypto.subtle.digest('SHA-256', buffer);
  return Array.from(new Uint8Array(hashBuffer))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

/**
 * Compute SHA-256 hash of raw bytes (ArrayBuffer).
 *
 * @param buffer - Raw bytes to hash
 * @returns 64-character lowercase hex string
 */
export async function computeBufferHash(buffer: ArrayBuffer): Promise<string> {
  const hashBuffer = await crypto.subtle.digest('SHA-256', buffer);
  return Array.from(new Uint8Array(hashBuffer))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}
