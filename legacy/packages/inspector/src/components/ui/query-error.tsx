/**
 * Query Error — Inline error with retry button for React Query failures
 * Replaces blank screens when API calls fail.
 */

import React from 'react';
import { StyleSheet, View } from 'react-native';
import { Button, Text } from 'react-native-paper';
import { useTranslation } from 'react-i18next';
import MaterialCommunityIcons from '@expo/vector-icons/MaterialCommunityIcons';
import { useAppTheme } from '@core/theme';

interface Props {
  error: Error | null;
  onRetry: () => void;
  isRetrying?: boolean;
  compact?: boolean;
}

export function QueryError({ error, onRetry, isRetrying, compact }: Props) {
  const { t } = useTranslation();
  const { colors } = useAppTheme();

  if (!error) return null;

  if (compact) {
    return (
      <View style={[styles.compactContainer, { backgroundColor: `${colors.error}10` }]}>
        <MaterialCommunityIcons name="wifi-alert" size={16} color={colors.error} />
        <Text variant="bodySmall" style={{ color: colors.error, flex: 1, marginLeft: 8 }}>
          {t('errors.network')}
        </Text>
        <Button
          mode="text"
          compact
          onPress={onRetry}
          loading={isRetrying}
          textColor={colors.error}
        >
          {t('common.retry')}
        </Button>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <MaterialCommunityIcons name="cloud-off-outline" size={48} color={colors.onSurfaceVariant} style={{ opacity: 0.5 }} />
      <Text variant="bodyMedium" style={{ color: colors.onSurfaceVariant, marginTop: 12, textAlign: 'center' }}>
        {t('errors.network')}
      </Text>
      <Button
        mode="outlined"
        icon="refresh"
        onPress={onRetry}
        loading={isRetrying}
        style={{ marginTop: 16, borderRadius: 20 }}
      >
        {t('common.retry')}
      </Button>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 32 },
  compactContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    marginHorizontal: 16,
    marginVertical: 8,
    padding: 10,
    borderRadius: 8,
  },
});
