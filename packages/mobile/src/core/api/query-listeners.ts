/**
 * React Query lifecycle listeners for React Native.
 *
 * Wires:
 * - `AppState` (foreground/background) → `focusManager.setFocused`
 * - `NetInfo`  (online/offline)        → `onlineManager.setOnline`
 * - Cold-resume > RESUME_THRESHOLD_MS → invalidate critical listing queries.
 *
 * Without this bridge, sockets killed by the OS during long backgrounds
 * remain "in flight" forever from React Query's POV, producing the m9.jpg
 * indefinite spinner on /servicios and /empresas.
 *
 * Call once at app boot from a deferred effect — returns a cleanup function.
 */

import { AppState, type AppStateStatus } from 'react-native';
import NetInfo from '@react-native-community/netinfo';
import { focusManager, onlineManager, type QueryClient } from '@tanstack/react-query';

/**
 * If the app stayed in background longer than this, invalidate listing
 * queries on resume so the user sees fresh data instead of stale cache.
 *
 * 5 min: short enough to cover the "few hours" terrain bug; long enough
 * to ignore short app-switching (e.g. authenticator code copy).
 */
const RESUME_THRESHOLD_MS = 5 * 60 * 1000;

/**
 * Query-key prefixes that should be invalidated on cold-resume.
 *
 * Keep this list focused on **listings/catalogs** that are display-only.
 * Excluded by design:
 * - `auth` / `session` / `refresh-token` — the API client interceptor
 *   already handles 401 and refresh
 * - `payments` / `payment-polling` — transactional state, refetching at
 *   the wrong moment can confuse the user
 * - `notifications` — pushed via FCM/APNs, no polling needed
 * - `support-thread-{id}` — message order matters; refetch happens on
 *   screen focus
 */
const CRITICAL_QUERY_PREFIXES: readonly string[] = [
  'fiscal-services',
  'companies',
  'directory',
  'dashboard',
  'service-requests',
  'bundles',
  'documents',
];

export function setupQueryListeners(queryClient: QueryClient): () => void {
  let lastBackgroundedAt: number | null = null;

  const handleAppStateChange = (status: AppStateStatus) => {
    const isActive = status === 'active';
    focusManager.setFocused(isActive);

    if (!isActive) {
      lastBackgroundedAt = Date.now();
      return;
    }
    if (lastBackgroundedAt === null) return;
    const elapsed = Date.now() - lastBackgroundedAt;
    lastBackgroundedAt = null;
    if (elapsed < RESUME_THRESHOLD_MS) return;

    void queryClient.invalidateQueries({
      predicate: (q) => {
        const prefix = String(q.queryKey[0] ?? '');
        return CRITICAL_QUERY_PREFIXES.includes(prefix);
      },
    });
  };

  const appStateSub = AppState.addEventListener('change', handleAppStateChange);

  const netInfoUnsub = NetInfo.addEventListener((state) => {
    // `isInternetReachable` can be `null` while NetInfo is probing — only
    // mark offline when we have an explicit `false`. Accept `null | true`
    // as "online" to avoid false negatives on slow DNS.
    const reachable = state.isInternetReachable;
    const online = !!state.isConnected && reachable !== false;
    onlineManager.setOnline(online);
  });

  return () => {
    appStateSub.remove();
    netInfoUnsub();
  };
}
