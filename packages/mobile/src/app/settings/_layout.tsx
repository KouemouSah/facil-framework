/**
 * Settings Stack Layout
 *
 * Stack navigator for security settings screens:
 * - Change Password (2-step flow)
 * - Two-Factor Authentication management
 * - Active Sessions list
 */

import { Stack } from 'expo-router';
import { useTranslation } from 'react-i18next';

import { useAppTheme } from '@core/theme';
import { useScreenProtection } from '@core/security/use-screen-protection';

export default function SettingsLayout() {
  useScreenProtection();
  const { colors } = useAppTheme();
  const { t } = useTranslation();

  return (
    <Stack
      screenOptions={{
        headerStyle: { backgroundColor: colors.surface },
        headerTintColor: colors.onSurface,
        headerTitleStyle: { fontWeight: '600' },
        contentStyle: { backgroundColor: colors.background },
        animation: 'slide_from_right',
      }}
    >
      <Stack.Screen
        name="change-password"
        options={{ title: t('profile.changePassword') }}
      />
      <Stack.Screen
        name="two-factor"
        options={{ title: t('profile.twoFactor') }}
      />
      <Stack.Screen
        name="sessions"
        options={{ title: t('profile.sessions') }}
      />
      <Stack.Screen
        name="about"
        options={{ title: t('settings.about.title', { defaultValue: 'About' }) }}
      />
    </Stack>
  );
}
