/**
 * Crypto Utilities - Signature hash for tamper detection
 *
 * Uses expo-crypto for real SHA-256 hashing.
 * OWASP A08: Integrity verification of agent signatures.
 */

import * as Crypto from 'expo-crypto';

/**
 * Hash a signature for tamper detection.
 * The backend performs the same hash to verify integrity.
 *
 * @param signatureBase64 - Base64 encoded signature image
 * @param userId - Agent's user ID
 * @returns SHA-256 hash string
 */
export async function hashSignature(signatureBase64: string, userId: string): Promise<string> {
  const input = `${signatureBase64}|${userId}`;
  return Crypto.digestStringAsync(Crypto.CryptoDigestAlgorithm.SHA256, input);
}
