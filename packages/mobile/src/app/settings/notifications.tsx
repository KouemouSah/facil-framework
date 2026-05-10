/**
 * Settings — Notifications preferences
 *
 * Standalone screen wrapping the existing `NotificationSettings` component used
 * in the profile tab. The three toggles (email / push / SMS) write directly
 * back to `users.email_notifications / push_notifications / sms_notifications`
 * via `PUT /users/profile` — no new backend endpoint needed (BD verified
 * 2026-04-27, the columns exist as bool with defaults true/true/false).
 */

import { useState } from 'react';
import { ActivityIndicator, ScrollView, StyleSheet, View } from 'react-native';
import { IconButton, Surface, Text } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { useTranslation } from 'react-i18next';

import { useAppTheme } from '@core/theme';
import { AuthGuard } from '@core/auth/auth-guard';
import { NotificationSettings } from '@modules/profile/components/notification-settings';
import { useProfile } from '@modules/profile/services/profile-hooks';

interface NotifPrefs {
  email_notifications: boolean;
  push_notifications: boolean;
  sms_notifications: boolean;
}

function NotificationsSettingsContent() {
  const router = useRouter();
  const { t } = useTranslation();
  const { colors, spacing, borderRadius } = useAppTheme();
  const profileQuery = useProfile();

  // Optimistic local state — `NotificationSettings` already fires the mutation,
  // we just keep an in-screen snapshot so the UI never shows a stale toggle
  // while the PUT is in flight.
  const [optimistic, setOptimistic] = useState<NotifPrefs | null>(null);

  const profile = profileQuery.data;
  const prefs: NotifPrefs = optimistic ?? {
    email_notifications: profile?.email_notifications ?? true,
    push_notifications: profile?.push_notifications ?? true,
    sms_notifications: profile?.sms_notifications ?? false,
  };

  const handleUpdate = (field: string, value: boolean) => {
    setOptimistic({ ...prefs, [field]: value });
  };

  return (
    <SafeAreaView
      style={[styles.container, { backgroundColor: colors.background }]}
      edges={['top']}
    >
      <View
        style={[
          styles.topBar,
          { backgroundColor: colors.surface, borderBottomColor: colors.outlineVariant },
        ]}
      >
        <IconButton icon="arrow-left" size={22} onPress={() => router.back()} />
        <Text
          variant="titleMedium"
          style={{ color: colors.onSurface, fontWeight: '600', flex: 1 }}
          numberOfLines={1}
        >
          {t('settings.notifications.title', { defaultValue: t('profile.notifications') })}
        </Text>
      </View>

      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={{ paddingBottom: 24 }}
      >
        {profileQuery.isLoading && !profile ? (
          <View style={styles.centered}>
            <ActivityIndicator size="large" color={colors.primary} />
          </View>
        ) : (
          <Surface
            style={[
              styles.card,
              {
                margin: spacing.md,
                borderRadius: borderRadius.md,
                backgroundColor: colors.surface,
              },
            ]}
            elevation={0}
          >
            <NotificationSettings
              emailNotifications={prefs.email_notifications}
              pushNotifications={prefs.push_notifications}
              smsNotifications={prefs.sms_notifications}
              onUpdate={handleUpdate}
            />
          </Surface>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  topBar: {
    flexDirection: 'row',
    alignItems: 'center',
    borderBottomWidth: 1,
    paddingRight: 8,
  },
  centered: { padding: 32, alignItems: 'center' },
  card: { paddingVertical: 8, overflow: 'hidden' },
});

export default function NotificationsSettingsScreen() {
  return (
    <AuthGuard>
      <NotificationsSettingsContent />
    </AuthGuard>
  );
}
