/**
 * Wizard Stack Layout
 *
 * Full-screen modal stack for the service request wizard.
 * No header — the wizard manages its own navigation chrome
 * (stepper, back button, close button).
 */

import { Stack } from 'expo-router';

import { useAppTheme } from '@core/theme';

export default function WizardLayout() {
  const { colors } = useAppTheme();

  return (
    <Stack
      screenOptions={{
        headerShown: false,
        contentStyle: { backgroundColor: colors.background },
        animation: 'slide_from_right',
      }}
    >
      <Stack.Screen name="select-workflow" />
      <Stack.Screen name="create" />
      <Stack.Screen name="[session-id]" />
      <Stack.Screen name="payment-result" />
    </Stack>
  );
}
