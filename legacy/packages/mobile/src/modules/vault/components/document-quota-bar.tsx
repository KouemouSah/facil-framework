import React from 'react';
import { StyleSheet, View } from 'react-native';
import { ProgressBar, Text } from 'react-native-paper';
import { useTranslation } from 'react-i18next';

import { useAppTheme } from '@core/theme';
import { VAULT_QUOTA_BYTES } from '../types/vault.types';

interface DocumentQuotaBarProps {
  usedBytes: number;
  maxBytes?: number;
}

function formatMB(bytes: number): string {
  return (bytes / 1024 / 1024).toFixed(1);
}

export function DocumentQuotaBar({
  usedBytes,
  maxBytes = VAULT_QUOTA_BYTES,
}: DocumentQuotaBarProps) {
  const { t } = useTranslation();
  const { colors } = useAppTheme();
  const ratio = Math.min(1, usedBytes / maxBytes);
  const isWarning = ratio > 0.8;
  const isCritical = ratio > 0.95;
  const tint = isCritical ? colors.error : isWarning ? '#F57C00' : colors.primary;

  return (
    <View style={styles.container}>
      <View style={styles.labelRow}>
        <Text variant="labelMedium" style={{ color: colors.onSurface }}>
          {t('vault.quota.label', {
            used: formatMB(usedBytes),
            total: formatMB(maxBytes),
          })}
        </Text>
        <Text variant="labelSmall" style={{ color: colors.onSurfaceVariant }}>
          {Math.round(ratio * 100)}%
        </Text>
      </View>
      <ProgressBar progress={ratio} color={tint} style={styles.bar} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    gap: 6,
  },
  labelRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  bar: {
    height: 6,
    borderRadius: 3,
  },
});
