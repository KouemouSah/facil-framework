/**
 * Root Layout - Facil Inspeccion
 *
 * Provider hierarchy: GestureHandler -> QueryClient -> Theme -> Auth -> SplashGate -> AppLock -> Router
 */

import React, { useEffect } from 'react';
import { Stack } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { StatusBar } from 'expo-status-bar';

import { ThemeProvider } from '@core/theme';
import { AuthProvider } from '@core/auth/auth-provider';
import { AppLockProvider } from '@core/security/app-lock';
import { useAuth } from '@core/hooks/use-auth';
import { secureStorage } from '@core/storage/mmkv';
import { ErrorBoundary } from '@components/ui/error-boundary';
import { NetworkBanner } from '@components/ui/network-banner';
import { useScreenProtection } from '@core/security/use-screen-protection';
import { initLogRocket } from '@core/observability/logrocket';
import '@core/i18n';

SplashScreen.preventAutoHideAsync();

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 2 * 60_000,       // 2 min — fresh enough for field work
      gcTime: 15 * 60_000,         // 15 min — keep cache longer (reduces network)
      retry: 1,                     // 1 retry only (field agents on slow networks)
      retryDelay: 2_000,            // 2s between retries
      refetchOnWindowFocus: false,  // Mobile: no window focus events
      refetchOnReconnect: true,     // Refetch when network returns
    },
    mutations: {
      retry: 0,                     // Never auto-retry mutations (user re-triggers)
    },
  },
});

function SplashGate({ children }: { children: React.ReactNode }) {
  const { isLoading } = useAuth();
  const [storageReady, setStorageReady] = React.useState(false);

  // Prevent screenshots/screen recording in production builds
  useScreenProtection();

  useEffect(() => {
    // Secure MMKV storage with device-unique key before anything else
    secureStorage().finally(() => setStorageReady(true));
  }, []);

  useEffect(() => {
    if (!isLoading && storageReady) {
      SplashScreen.hideAsync();
    }
  }, [isLoading, storageReady]);

  // LogRocket session replay — idempotent, no-op when APP_ID absent or in __DEV__.
  // Deferred until after the splash so SDK init doesn't compete with cold-start.
  useEffect(() => {
    if (storageReady) initLogRocket();
  }, [storageReady]);

  return <>{children}</>;
}

export default function RootLayout() {
  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <QueryClientProvider client={queryClient}>
        <ThemeProvider>
          <AuthProvider>
            <SplashGate>
              <AppLockProvider>
                <ErrorBoundary>
                  <StatusBar style="auto" />
                  <NetworkBanner />
                  <Stack screenOptions={{ headerShown: false }}>
                    <Stack.Screen name="(auth)" />
                    <Stack.Screen name="(tabs)" />
                    <Stack.Screen name="inspection" options={{ presentation: 'modal' }} />
                    <Stack.Screen name="supervisor" options={{ presentation: 'modal' }} />
                  </Stack>
                </ErrorBoundary>
              </AppLockProvider>
            </SplashGate>
          </AuthProvider>
        </ThemeProvider>
      </QueryClientProvider>
    </GestureHandlerRootView>
  );
}
