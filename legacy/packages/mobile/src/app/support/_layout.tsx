/**
 * Support Stack Layout
 *
 * Stack navigator for support ticket screens:
 * - List of tickets
 * - Create new ticket
 * - Ticket detail / conversation
 */

import { Stack } from 'expo-router';

import { useAppTheme } from '@core/theme';

export default function SupportLayout() {
  const { colors } = useAppTheme();

  return (
    <Stack
      screenOptions={{
        headerShown: false,
        contentStyle: { backgroundColor: colors.background },
        animation: 'slide_from_right',
      }}
    >
      <Stack.Screen name="index" />
      <Stack.Screen name="new" />
      <Stack.Screen name="[id]" />
    </Stack>
  );
}
