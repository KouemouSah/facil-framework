/**
 * Idempotency-Key helpers for safe retries on mutating endpoints.
 *
 * Plan P4 — INSPECTION_BUNDLE_P4_DETAIL.md §3 P4.B
 *
 * Usage in a screen:
 *
 *   import { useRef } from 'react';
 *   import { generateIdempotencyKey, IDEMPOTENCY_HEADER } from '@core/api/idempotency';
 *
 *   const idempotencyKeyRef = useRef(generateIdempotencyKey());
 *
 *   await inspectionsApi.collect(id, data, { [IDEMPOTENCY_HEADER]: idempotencyKeyRef.current });
 *
 * The key is generated once at component mount and reused for every retry of
 * the same conceptual operation. React Navigation unmount/remount → new key.
 *
 * Backend: app/core/idempotency.py (P3)
 *   - Accepts 8-128 chars
 *   - 24h cache TTL (Upstash Redis + in-memory fallback)
 *   - Returns Idempotency-Replay: true header on cache hit
 */

import * as Crypto from 'expo-crypto';

export const IDEMPOTENCY_HEADER = 'Idempotency-Key';
export const IDEMPOTENCY_REPLAY_HEADER = 'idempotency-replay';

/** Generate a RFC 4122 v4 UUID using Expo's crypto module. */
export function generateIdempotencyKey(): string {
  // Crypto.randomUUID() is available from Expo SDK 52+
  // https://docs.expo.dev/versions/latest/sdk/crypto/#cryptorandomuuid
  try {
    return Crypto.randomUUID();
  } catch {
    // Defensive fallback if the underlying platform does not expose randomUUID.
    // Produces a 32-hex pseudo-UUID — good enough as an Idempotency-Key since
    // the backend cache key includes {user_id, endpoint, key}.
    const hex = '0123456789abcdef';
    let out = '';
    for (let i = 0; i < 32; i += 1) {
      out += hex[Math.floor(Math.random() * 16)];
    }
    return out;
  }
}

/**
 * Build the headers object to pass to apiPost / apiPut / apiPostRaw.
 * Idempotency-Key is optional — if absent, the backend treats the call as non-idempotent.
 */
export function withIdempotencyKey(key: string): Record<string, string> {
  return { [IDEMPOTENCY_HEADER]: key };
}

/**
 * Detect if a response is a replay of a previously cached result (P3 backend).
 * Pass an AxiosResponse (from apiPostRaw) — returns true if the backend
 * short-circuited the request because it had the same Idempotency-Key cached.
 */
export function isIdempotencyReplay(
  responseHeaders: Record<string, unknown> | undefined,
): boolean {
  if (!responseHeaders) return false;
  const value = responseHeaders[IDEMPOTENCY_REPLAY_HEADER];
  return value === 'true' || value === true;
}
