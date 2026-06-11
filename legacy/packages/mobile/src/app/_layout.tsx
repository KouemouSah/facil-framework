/**
 * Root Layout — Facil Mobile
 *
 * Wraps the entire app with required providers:
 * - GestureHandlerRootView (gesture support for bottom sheets, swipes)
 * - QueryClientProvider (TanStack Query for server state)
 * - ThemeProvider (MD3 + custom tokens)
 * - AuthProvider (JWT auth state)
 *
 * Splash screen stays visible until auth bootstrap completes (isLoading = false).
 */

import { useEffect } from 'react';
import { LogBox } from 'react-native';
import { Stack } from 'expo-router';
import { QueryClient } from '@tanstack/react-query';
import { PersistQueryClientProvider } from '@tanstack/react-query-persist-client';

import { createMmkvPersister } from '@core/api/query-persister';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { StatusBar } from 'expo-status-bar';
import * as SplashScreen from 'expo-splash-screen';

import { useTranslation } from 'react-i18next';

import { ThemeProvider } from '@core/theme';
import { AuthProvider } from '@core/auth/auth-provider';
import { useAuth } from '@core/hooks/use-auth';
import { useDeferredAfterInteractions } from '@core/hooks/use-deferred-after-interactions';
import { ErrorBoundary } from '@components/ui/error-boundary';
import { AppLockProvider } from '@core/security/app-lock';
import {
  initNotifications,
  getInitialNotificationResponse,
  routeFromPayload,
  type NotificationDataPayload,
} from '@core/notifications';
import { useDeviceTokenRegistration } from '@modules/notifications/hooks/use-device-token-registration';
import { useNotifications } from '@modules/notifications/hooks/use-notifications';
import { initSentry } from '@core/observability/sentry';
import { initLogRocket } from '@core/observability/logrocket';
import { reportDeviceIntegrity } from '@core/security/device-integrity';
import { setupQueryListeners } from '@core/api/query-listeners';
import '@core/i18n';

// Suppress known React 19 + New Architecture internal warnings
// These are React internals, not actionable — https://github.com/facebook/react/issues/28839
LogBox.ignoreLogs([
  'Internal React error: Expected static flag was missing',
  'Each child in a list',
  'Open debugger to view warnings',
  'Unable to activate keep awake',
]);

// Keep splash screen visible while providers initialize
SplashScreen.preventAutoHideAsync();

// `initNotifications()` (Android channels + foreground handler) used to fire at
// module load. Moved into <DeferredEffects /> below so it runs *after* the
// first paint and the auth-bootstrap settle — saves ~80-150ms TTI on cold
// start. The push observer registered later still catches every incoming
// notification because Expo's runtime bridge buffers them until subscribed.

// gcTime needs to be ≥ persisted maxAge so the persister can re-hydrate a cache
// entry without it being garbage-collected first.
const PERSISTED_MAX_AGE = 24 * 60 * 60 * 1000; // 24h

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 2 * 60 * 1000, // 2 min
      gcTime: PERSISTED_MAX_AGE,
      retry: 2,
      // RN doesn't fire `window.focus` — `setupQueryListeners()` below
      // wires `AppState` to `focusManager`. With that, this flag tells RQ
      // to refetch stale queries on app foreground.
      refetchOnWindowFocus: true,
      // Same for network: `NetInfo` → `onlineManager`. Resume queries
      // when the device reconnects.
      refetchOnReconnect: true,
    },
  },
});

/**
 * Whitelist of query-key prefixes that survive an app restart. Anything that
 * is rate-limited or sensitive (auth tokens, sessions, payment status
 * polling, support thread messages) stays excluded so that:
 *   1. cold start renders cached data instantly while the network refetches
 *      in background;
 *   2. user-scoped entries (dashboard, service-requests) only survive while
 *      the same user is logged in — `auth-provider.signOut()` calls
 *      `queryClient.clear()` which empties both in-memory and persisted
 *      buckets, so the next user never reads the previous user's data.
 */
const PERSISTED_QUERY_PREFIXES: readonly string[] = [
  // Public catalog data — services, ministries, fiscal-services, bundles config
  'fiscal-services',
  'workflows',
  'directory',
  'bundles',
  // Public-shape reference lists (target_role-filtered server-side)
  'support-categories',
  // User-scoped — paired with `queryClient.clear()` on signOut. Persisting
  // these eliminates the visible "long load" on cold start when the user
  // has been logged in for a while: dashboard stats and recent requests
  // hydrate from MMKV instantly, then refetch silently in background.
  'dashboard',
  'service-requests',
];

// MMKV-backed sync persister. Hydrates the cache <50ms vs ~500-2000ms with
// AsyncStorage on Android low-end — see core/api/query-persister.ts for
// design notes and core/storage/mmkv.ts for the underlying instance.
const persister = createMmkvPersister();

const dehydrateOptions = {
  shouldDehydrateQuery: (query: { queryKey: readonly unknown[]; state: { status: string } }) => {
    if (query.state.status !== 'success') return false;
    const prefix = String(query.queryKey[0] ?? '');
    return PERSISTED_QUERY_PREFIXES.includes(prefix);
  },
};

/**
 * Prefetch slow catalog data in background AFTER splash is hidden.
 * Delayed 3s to avoid competing with auth bootstrap for network/CPU.
 * Non-blocking, errors silently ignored.
 *
 * Why we prefetch instead of letting each screen fetch on mount:
 * users on cellular often pay the round-trip cost the first time they open
 * /services or /companies. Fetching at boot when bandwidth is already in
 * use (auth, dashboard) hides the latency behind the first paint and lands
 * the data in the persisted React Query cache for the rest of the session.
 *
 * The query keys here MUST match the ones used by the consumer hooks
 * (`useMinistries`, `useCategories`, `useBundleCommerceTypes`, …) — that
 * is what makes React Query reuse this prefetch instead of triggering a
 * second network request when the user navigates to the tab.
 */
function usePrefetchCatalogs() {
  useEffect(() => {
    const timer = setTimeout(() => {
      const baseUrl = process.env.EXPO_PUBLIC_API_URL;
      if (!baseUrl) return;
      const api = `${baseUrl}/api/v1`;
      const lang = 'es'; // matches default in useMinistries()/useCategories()

      // Slow catalog (Service tab) — main offender on m9.jpg infinite spinner.
      // Reference data — 24 h stale (matches services-hooks.ts CATALOG_STALE_TIME).
      queryClient.prefetchQuery({
        queryKey: ['fiscal-services', 'ministries', lang],
        queryFn: () =>
          fetch(`${api}/fiscal-services/ministries?language=${lang}`)
            .then((r) => r.json())
            .catch(() => []),
        staleTime: 24 * 60 * 60_000,
      });
      queryClient.prefetchQuery({
        queryKey: ['fiscal-services', 'categories', lang],
        queryFn: () =>
          fetch(`${api}/fiscal-services/categories?language=${lang}`)
            .then((r) => r.json())
            .catch(() => []),
        staleTime: 24 * 60 * 60_000,
      });

      // Bundle reference (commerce types / zones) — used by /companies +
      // bundle wizard.
      queryClient.prefetchQuery({
        queryKey: ['bundles', 'commerce-types'],
        queryFn: () => fetch(`${api}/service-bundles/commerce-types`).then(r => r.json()).catch(() => []),
        staleTime: 24 * 60 * 60_000,
      });
      queryClient.prefetchQuery({
        queryKey: ['bundles', 'zones'],
        queryFn: () => fetch(`${api}/service-bundles/zones`).then(r => r.json()).catch(() => []),
        staleTime: 24 * 60 * 60_000,
      });
    }, 3000); // Delay 3s after mount — let auth bootstrap finish first
    return () => clearTimeout(timer);
  }, []);
}

/**
 * Effects that don't need to run for the first paint to be useful — they
 * depend on the auth/UI being mounted and on the JS thread being idle. This
 * sub-component is conditionally mounted by `<RootNavigator />` only after
 * `InteractionManager.runAfterInteractions` fires, which keeps the cold-start
 * critical path lean.
 */
function DeferredEffects() {
  // Sentry init — idempotent, no-op when DSN absent or in __DEV__.
  useEffect(() => {
    initSentry();
  }, []);
  // LogRocket session replay — idempotent, no-op when APP_ID absent or in __DEV__.
  // Order matters: must run after initSentry so the Sentry-bridge inside
  // LogRocket can pin the session URL onto the existing Sentry scope.
  useEffect(() => {
    initLogRocket();
  }, []);
  // Device integrity check — non-blocking telemetry only. Logs a Sentry
  // breadcrumb + warning when the device fingerprint looks suspicious
  // (emulator, generic SDK build, etc.).
  useEffect(() => {
    void reportDeviceIntegrity();
  }, []);
  // Channels + foreground handler — idempotent.
  useEffect(() => {
    void initNotifications();
  }, []);
  // Wire AppState → focusManager and NetInfo → onlineManager so RN tells
  // React Query when the app comes back from background or regains network.
  // Also invalidates listing queries after a long sleep to avoid showing
  // stale data on /servicios and /empresas (B6 — m9.jpg fix).
  useEffect(() => {
    return setupQueryListeners(queryClient);
  }, []);
  // Register device token with the backend after auth bootstrap.
  // No-ops while unauthenticated; idempotent on repeat calls.
  useDeviceTokenRegistration();
  // Subscribe to incoming pushes (foreground display + tap routing + MMKV).
  useNotifications();
  return null;
}

/**
 * Inner navigator component that has access to AuthContext.
 * Hides the splash screen only after auth bootstrap finishes.
 */
function RootNavigator() {
  const { isLoading, isAuthenticated } = useAuth();
  // Subscribe to language changes so the entire tree re-renders when i18n locale switches
  useTranslation();
  // Prefetch catalog data in background (already self-deferred 3s)
  usePrefetchCatalogs();
  // Gate the heavy push / device-token / notification setup until the JS
  // thread has settled — so they never compete with the first frame.
  const interactionsReady = useDeferredAfterInteractions();

  useEffect(() => {
    if (!isLoading) {
      SplashScreen.hideAsync();
    }
  }, [isLoading]);

  // Cold-start deep link: if the app was launched by tapping a push, route to
  // the target only AFTER auth bootstrap finishes — earlier and we'd land on
  // /index which would re-redirect away.
  useEffect(() => {
    if (isLoading || !isAuthenticated) return;
    let cancelled = false;
    void (async () => {
      const response = await getInitialNotificationResponse();
      if (cancelled || !response) return;
      const data = response.notification.request.content.data as
        | NotificationDataPayload
        | undefined;
      routeFromPayload(data);
    })();
    return () => {
      cancelled = true;
    };
  }, [isLoading, isAuthenticated]);

  return (
    <>
      <Stack screenOptions={{ headerShown: false }}>
        <Stack.Screen name="index" />
        <Stack.Screen name="onboarding" options={{ animation: 'fade' }} />
        <Stack.Screen name="+not-found" />
        <Stack.Screen name="(auth)" />
        <Stack.Screen name="(tabs)" />
        <Stack.Screen
          name="wizard"
          options={{ presentation: 'fullScreenModal' }}
        />
        <Stack.Screen name="settings" />
        <Stack.Screen name="support" />
        <Stack.Screen name="notifications" />
        <Stack.Screen name="documents/index" />
        <Stack.Screen name="documents/[id]" />
        <Stack.Screen name="documents/upload" />
        <Stack.Screen name="companies/index" />
        <Stack.Screen name="companies/[id]" />
        <Stack.Screen name="companies/[id]/edit" />
        <Stack.Screen name="companies/[id]/members" />
        <Stack.Screen name="companies/[id]/payments" />
        <Stack.Screen name="bundle-wizard" />
        <Stack.Screen name="calculator/index" />
        <Stack.Screen name="licencias" />
        <Stack.Screen name="directorio" />
      </Stack>
      {/* Mounted only after the first paint settles — InteractionManager keeps
          channel setup, device-token registration and push subscription off
          the cold-start critical path. */}
      {interactionsReady ? <DeferredEffects /> : null}
    </>
  );
}

export default function RootLayout() {
  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <PersistQueryClientProvider
        client={queryClient}
        persistOptions={{
          persister,
          maxAge: PERSISTED_MAX_AGE,
          dehydrateOptions,
          // Bumping the buster invalidates every persisted cache on next launch.
          // Bump on schema changes or when whitelisted query shapes evolve.
          buster: 'v1',
        }}
      >
        <ThemeProvider>
          <AuthProvider>
            <AppLockProvider>
              {/* Single ErrorBoundary — its componentDidCatch forwards every
                  caught error to Sentry via `captureException`, which is a
                  no-op in dev. Wrapping it in a separate SentryErrorBoundary
                  would have been redundant: the inner boundary already swallows
                  errors via `getDerivedStateFromError`, so the outer one would
                  never receive them. */}
              <ErrorBoundary>
                <StatusBar style="auto" />
                <RootNavigator />
              </ErrorBoundary>
            </AppLockProvider>
          </AuthProvider>
        </ThemeProvider>
      </PersistQueryClientProvider>
    </GestureHandlerRootView>
  );
}
