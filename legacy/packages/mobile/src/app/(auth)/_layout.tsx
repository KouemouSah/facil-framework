/**
 * Auth Stack Layout
 *
 * Stack navigator for authentication screens (sign-in, sign-up,
 * forgot-password, OTP verification). No header bar — each screen
 * manages its own navigation chrome.
 */

import { Stack } from 'expo-router';

import { useAppTheme } from '@core/theme';

export default function AuthLayout() {
  const { colors } = useAppTheme();

  return (
    <Stack
      screenOptions={{
        headerShown: false,
        contentStyle: { backgroundColor: colors.background },
        animation: 'slide_from_right',
      }}
    >
      <Stack.Screen name="sign-in" />
      <Stack.Screen name="sign-up" />
      <Stack.Screen name="forgot-password" />
      <Stack.Screen name="verify-otp" />
      <Stack.Screen name="reset-password" />
    </Stack>
  );
}
