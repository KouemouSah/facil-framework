/**
 * Notification Settings
 *
 * Toggle switches for email/push/sms notifications.
 * Each toggle triggers an immediate save to backend.
 */

import React from 'react';
import { View, StyleSheet } from 'react-native';
import { List, Switch, useTheme, Divider } from 'react-native-paper';
import { useTranslation } from 'react-i18next';

import { useUpdateProfile } from '../services/profile-hooks';

interface NotificationSettingsProps {
  emailNotifications: boolean;
  pushNotifications: boolean;
  smsNotifications: boolean;
  onUpdate: (field: string, value: boolean) => void;
}

export function NotificationSettings({
  emailNotifications,
  pushNotifications,
  smsNotifications,
  onUpdate,
}: NotificationSettingsProps) {
  const theme = useTheme();
  const { t } = useTranslation();
  const updateMutation = useUpdateProfile();

  const handleToggle = (field: string, value: boolean) => {
    onUpdate(field, value);
    updateMutation.mutate({ [field]: value });
  };

  return (
    <View style={styles.container}>
      <List.Subheader style={{ color: theme.colors.primary }}>
        {t('profile.notifications')}
      </List.Subheader>

      <List.Item
        title={t('profile.emailNotifications')}
        description={t('profile.emailNotificationsDesc')}
        left={(props) => <List.Icon {...props} icon="email-outline" />}
        right={() => (
          <Switch
            value={emailNotifications}
            onValueChange={(val) => handleToggle('email_notifications', val)}
            disabled={updateMutation.isPending}
          />
        )}
      />
      <Divider />

      <List.Item
        title={t('profile.pushNotifications')}
        description={t('profile.pushNotificationsDesc')}
        left={(props) => <List.Icon {...props} icon="bell-outline" />}
        right={() => (
          <Switch
            value={pushNotifications}
            onValueChange={(val) => handleToggle('push_notifications', val)}
            disabled={updateMutation.isPending}
          />
        )}
      />
      <Divider />

      <List.Item
        title={t('profile.smsNotifications')}
        description={t('profile.smsNotificationsDesc')}
        left={(props) => <List.Icon {...props} icon="message-text-outline" />}
        right={() => (
          <Switch
            value={smsNotifications}
            onValueChange={(val) => handleToggle('sms_notifications', val)}
            disabled={updateMutation.isPending}
          />
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    marginTop: 8,
  },
});
