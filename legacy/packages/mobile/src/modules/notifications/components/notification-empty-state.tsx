import React from 'react';
import { StyleSheet, View } from 'react-native';
import { Text } from 'react-native-paper';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useTranslation } from 'react-i18next';

import { useAppTheme } from '@core/theme';

export function NotificationEmptyState() {
  const { t } = useTranslation();
  const { colors } = useAppTheme();

  return (
    <View style={styles.container}>
      <MaterialCommunityIcons
        name="bell-outline"
        size={56}
        color={colors.onSurfaceVariant}
      />
      <Text
        variant="titleMedium"
        style={[styles.title, { color: colors.onSurface }]}
      >
        {t('notifications.empty.title')}
      </Text>
      <Text
        variant="bodySmall"
        style={[styles.body, { color: colors.onSurfaceVariant }]}
      >
        {t('notifications.empty.body')}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignItems: 'center',
    paddingVertical: 64,
    paddingHorizontal: 24,
  },
  title: {
    marginTop: 16,
    textAlign: 'center',
  },
  body: {
    marginTop: 8,
    textAlign: 'center',
  },
});
