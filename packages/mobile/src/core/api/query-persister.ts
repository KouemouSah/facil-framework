/**
 * Synchronous React Query persister backed by MMKV.
 *
 * Replaces the previous AsyncStorage persister (~500-2000ms hydration on
 * Android low-end devices) with MMKV (~5-50ms, synchronous reads). The result
 * is a near-instant cold start: the persisted catalog is in the cache before
 * the first screen even mounts, so `useQuery` returns `data` immediately
 * instead of bouncing through `isLoading: true` while AsyncStorage walks
 * SQLite.
 *
 * The Persister interface (`@tanstack/query-persist-client-core`) accepts
 * `Promisable<T>` for every method, so a fully sync implementation is
 * supported — no need for an extra package (`query-sync-storage-persister`
 * isn't installed; we don't add a dep just to wrap MMKV).
 *
 * Storage layout:
 *   key: `facil:rq-cache:v1`  (single bucket, JSON-serialized PersistedClient)
 *
 * Bump the suffix (`v1` → `v2`) to invalidate every persisted cache when the
 * shape of the data we whitelist changes. This is paired with the `buster`
 * prop on `<PersistQueryClientProvider>` for belt-and-braces.
 */

import type { Persister, PersistedClient } from '@tanstack/react-query-persist-client';

import { storage as mmkv } from '@core/storage/mmkv';

const STORAGE_KEY = 'facil:rq-cache:v1';

/**
 * Build a Persister that reads/writes to the shared MMKV instance.
 *
 * The instance is reused across calls — there is exactly one persister per
 * app process. We don't memoize here because `_layout.tsx` already calls this
 * once at module evaluation time.
 */
export function createMmkvPersister(): Persister {
  return {
    persistClient: (client: PersistedClient): void => {
      try {
        mmkv.set(STORAGE_KEY, JSON.stringify(client));
      } catch {
        // Either the cache is over MMKV's safety budget, or stringification
        // failed on a circular ref. Drop it — the next persistClient cycle
        // will retry and the in-memory cache stays usable in the meantime.
      }
    },

    restoreClient: (): PersistedClient | undefined => {
      const raw = mmkv.getString(STORAGE_KEY);
      if (raw === undefined) return undefined;
      try {
        return JSON.parse(raw) as PersistedClient;
      } catch {
        // Corrupt entry — wipe it so the persister doesn't keep tripping on
        // the same JSON.parse error on every cold start.
        mmkv.delete(STORAGE_KEY);
        return undefined;
      }
    },

    removeClient: (): void => {
      mmkv.delete(STORAGE_KEY);
    },
  };
}
