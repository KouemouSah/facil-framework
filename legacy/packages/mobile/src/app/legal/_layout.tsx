/**
 * Legal stack layout — Privacy / Terms / Cookies pages.
 *
 * Stack-screen group, NOT in the bottom tab bar. Reachable from sign-up
 * (LegalAcceptanceCard links) and from the Profile screen (legal section).
 *
 * Each child screen sets its own `Stack.Screen options.title` to pick the
 * localized header label.
 */

import React from 'react';
import { Stack } from 'expo-router';

import { useAppTheme } from '@core/theme';

export default function LegalLayout() {
  const { colors } = useAppTheme();
  return (
    <Stack
      screenOptions={{
        headerStyle: { backgroundColor: colors.surface },
        headerTintColor: colors.onSurface,
        headerTitleStyle: { fontWeight: '600' },
        contentStyle: { backgroundColor: colors.background },
      }}
    />
  );
}
