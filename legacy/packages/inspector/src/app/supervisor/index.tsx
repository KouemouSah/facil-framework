/**
 * Supervisor Hub — Navigation grid with live badges
 */

import React from 'react';
import { RefreshControl, ScrollView, StyleSheet, View } from 'react-native';
import { Text } from 'react-native-paper';
import { router } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Pressable } from 'react-native';
import MaterialCommunityIcons from '@expo/vector-icons/MaterialCommunityIcons';

import { useAppTheme } from '@core/theme';
import { useSupervisorDashboard } from '@modules/dashboard/services/dashboard-hooks';
import { formatCurrency } from '@core/utils/format';

interface HubItem {
  icon: string;
  labelKey: string;
  route: string;
  badge?: number | string;
  badgeColor?: string;
}

export default function SupervisorHub() {
  const { t } = useTranslation();
  const { colors, custom } = useAppTheme();
  const insets = useSafeAreaInsets();
  const { data: dashboard, refetch, isRefetching } = useSupervisorDashboard(true);

  const items: HubItem[] = [
    {
      icon: 'shield-alert',
      labelKey: 'supervisor.pendingSeals',
      route: '/supervisor/pending-seals',
      badge: dashboard?.pending_seals?.length,
      badgeColor: custom.status.sealProposed,
    },
    {
      icon: 'cash-fast',
      labelKey: 'supervisor.reconciliation',
      route: '/supervisor/reconciliation',
      badge: dashboard?.unreconciled_cash_count,
      badgeColor: colors.primary,
    },
    {
      icon: 'account-group',
      labelKey: 'supervisor.agentStatus',
      route: '/supervisor/agents',
    },
    {
      icon: 'chart-line',
      labelKey: 'supervisor.reports',
      route: '/supervisor/analytics',
    },
    {
      icon: 'map-marker-path',
      labelKey: 'supervisor.features.missionPlanning',
      route: '/supervisor/missions',
    },
  ];

  return (
    <View style={[styles.container, { backgroundColor: colors.background }]}>
      <View style={[styles.header, { paddingTop: insets.top + 8 }]}>
        <Text variant="headlineSmall" style={{ color: colors.primary, fontWeight: '700' }}>
          {t('supervisor.dashboard')}
        </Text>
        {dashboard && (
          <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant }}>
            {t('inspection.unpaidAmount')}: {formatCurrency(dashboard.unreconciled_cash_amount)}
          </Text>
        )}
      </View>

      <ScrollView
        contentContainerStyle={styles.grid}
        refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} colors={[colors.primary]} />}
      >
        {items.map((item) => {
          const hasBadge = item.badge != null && Number(item.badge) > 0;
          return (
            <Pressable
              key={item.route}
              onPress={() => router.push(item.route as never)}
              style={({ pressed }) => [
                styles.card,
                { backgroundColor: pressed ? colors.surfaceVariant : colors.surface },
              ]}
              android_ripple={{ color: colors.surfaceVariant }}
            >
              <View style={styles.cardContent}>
                <View style={styles.iconRow}>
                  <MaterialCommunityIcons
                    name={item.icon as never}
                    size={28}
                    color={hasBadge ? item.badgeColor : colors.primary}
                  />
                  {hasBadge && (
                    <View style={[styles.badge, { backgroundColor: item.badgeColor }]}>
                      <Text variant="labelSmall" style={{ color: '#FFF', fontWeight: '700', fontSize: 11 }}>
                        {item.badge}
                      </Text>
                    </View>
                  )}
                </View>
                <Text variant="bodyMedium" style={{ color: colors.onSurface, marginTop: 8 }}>
                  {t(item.labelKey)}
                </Text>
              </View>
            </Pressable>
          );
        })}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  header: { paddingHorizontal: 16, paddingBottom: 12 },
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    paddingHorizontal: 12,
    paddingBottom: 32,
    gap: 8,
  },
  card: {
    width: '47%' as unknown as number,
    borderRadius: 12,
    overflow: 'hidden',
  },
  cardContent: {
    padding: 16,
    minHeight: 100,
    justifyContent: 'center',
  },
  iconRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  badge: {
    marginLeft: 8,
    minWidth: 22,
    height: 22,
    borderRadius: 11,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 6,
  },
});
