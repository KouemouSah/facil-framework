/**
 * Auth Guard
 *
 * Route protection component for authenticated-only screens.
 *
 * Usage in Expo Router layouts:
 * ```tsx
 * // app/(dashboard)/_layout.tsx
 * export default function DashboardLayout() {
 *   return (
 *     <AuthGuard>
 *       <Stack />
 *     </AuthGuard>
 *   );
 * }
 * ```
 *
 * Behavior:
 * - While checking auth state (isLoading): shows a loading screen
 * - If not authenticated: redirects to sign-in screen
 * - If authenticated: renders children
 */

import React from 'react';
import { ActivityIndicator, StyleSheet, View } from 'react-native';
import { Redirect } from 'expo-router';

import { useAuth } from '@core/hooks/use-auth';
import { useAppTheme } from '@core/theme';

// ---------------------------------------------------------------------------
// Loading Screen
// ---------------------------------------------------------------------------

/**
 * Minimal loading screen shown during initial auth state check.
 *
 * Uses theme tokens for the spinner and background color.
 * This screen is only visible briefly on cold start.
 */
function LoadingScreen() {
  const { colors } = useAppTheme();

  return (
    <View style={[styles.loadingContainer, { backgroundColor: colors.background }]}>
      <ActivityIndicator size="large" color={colors.primary} />
    </View>
  );
}

// ---------------------------------------------------------------------------
// Auth Guard Component
// ---------------------------------------------------------------------------

interface AuthGuardProps {
  children: React.ReactNode;
}

export function AuthGuard({ children }: AuthGuardProps) {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return <LoadingScreen />;
  }

  if (!isAuthenticated) {
    return <Redirect href="/(auth)/sign-in" />;
  }

  return <>{children}</>;
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const styles = StyleSheet.create({
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
});
