/**
 * Supervisor Alerts - Pending seals, overdue MED, unreconciled cash
 */

import React from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { Divider, Text } from 'react-native-paper';
import { router } from 'expo-router';
import { useTranslation } from 'react-i18next';
import MaterialCommunityIcons from '@expo/vector-icons/MaterialCommunityIcons';
import { useAppTheme } from '@core/theme';
import { formatCurrency } from '@core/utils/format';

interface Props {
  pendingSeals: number;
  overdueMed: number;
  unreconciledCash: number;
  unreconciledCount: number;
  locationLabel?: string;
}

export function SupervisorAlerts({ pendingSeals, overdueMed, unreconciledCash, unreconciledCount, locationLabel }: Props) {
  const { t } = useTranslation();
  const { colors, custom } = useAppTheme();

  const alerts = [
    {
      icon: 'shield-alert' as const,
      label: t('dashboard.pendingSeals'),
      value: pendingSeals,
      color: custom.status.sealProposed,
      urgent: pendingSeals > 0,
      onPress: () => router.push('/supervisor/pending-seals' as never),
    },
    {
      icon: 'clock-alert' as const,
      label: t('dashboard.overdueNotices'),
      value: overdueMed,
      color: custom.status.miseEnDemeure,
      urgent: overdueMed > 0,
      onPress: undefined,
    },
    {
      icon: 'cash-fast' as const,
      label: `${t('dashboard.unreconciledCash')}${locationLabel ? ` (${locationLabel})` : ''}`,
      value: `${unreconciledCount} (${formatCurrency(unreconciledCash)})`,
      color: colors.primary,
      urgent: unreconciledCount > 0,
      onPress: () => router.push('/supervisor/reconciliation' as never),
    },
  ];

  return (
    <View style={[styles.container, { backgroundColor: colors.surface }]}>
      {alerts.map((alert, index) => (
        <React.Fragment key={index}>
          <Pressable
            onPress={alert.onPress}
            disabled={!alert.onPress}
            style={({ pressed }) => [
              styles.alertItem,
              pressed && alert.onPress && { backgroundColor: colors.surfaceVariant },
            ]}
            android_ripple={alert.onPress ? { color: colors.surfaceVariant } : undefined}
          >
            <MaterialCommunityIcons
              name={alert.icon}
              size={20}
              color={alert.urgent ? alert.color : colors.onSurfaceVariant}
            />
            <Text
              variant="bodyMedium"
              style={{ flex: 1, color: colors.onSurface, marginLeft: 12 }}
            >
              {alert.label}
            </Text>
            <Text
              variant="titleSmall"
              style={{ color: alert.urgent ? alert.color : colors.onSurfaceVariant, fontWeight: '700' }}
            >
              {alert.value}
            </Text>
          </Pressable>
          {index < alerts.length - 1 && <Divider />}
        </React.Fragment>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { marginHorizontal: 16, borderRadius: 8, overflow: 'hidden', marginBottom: 16 },
  alertItem: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    height: 52,
  },
});
