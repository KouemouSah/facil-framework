import React from 'react';
import { Linking, Pressable, StyleSheet, View } from 'react-native';
import { Text } from 'react-native-paper';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useTranslation } from 'react-i18next';

import { useAppTheme } from '@core/theme';

interface NotificationPermissionsBannerProps {
  /** Called if the user can still grant permission via prompt (initial denial). */
  onPromptAgain?: () => void;
  /** When true, native settings are the only path — show a system-settings CTA. */
  needsSystemSettings: boolean;
}

export function NotificationPermissionsBanner({
  onPromptAgain,
  needsSystemSettings,
}: NotificationPermissionsBannerProps) {
  const { t } = useTranslation();
  const { colors } = useAppTheme();

  const handlePress = needsSystemSettings
    ? () => Linking.openSettings()
    : onPromptAgain;

  return (
    <Pressable
      onPress={handlePress}
      android_ripple={{ color: colors.surfaceVariant }}
      style={[styles.banner, { backgroundColor: colors.primaryContainer }]}
    >
      <MaterialCommunityIcons
        name="bell-off-outline"
        size={22}
        color={colors.onPrimaryContainer}
      />
      <View style={styles.body}>
        <Text
          variant="titleSmall"
          style={{ color: colors.onPrimaryContainer, fontWeight: '700' }}
        >
          {t('notifications.permission.title')}
        </Text>
        <Text variant="bodySmall" style={{ color: colors.onPrimaryContainer }}>
          {needsSystemSettings
            ? t('notifications.permission.openSettings')
            : t('notifications.permission.enable')}
        </Text>
      </View>
      <MaterialCommunityIcons
        name="chevron-right"
        size={22}
        color={colors.onPrimaryContainer}
      />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  banner: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 14,
    marginHorizontal: 16,
    marginTop: 8,
    borderRadius: 12,
    gap: 12,
  },
  body: {
    flex: 1,
  },
});
