/**
 * Agent Live Status Screen — Real-time agent monitoring
 * Auto-refreshes every 30s via useLiveStatus hook.
 */

import React, { useCallback, useMemo } from 'react';
import { FlatList, Pressable, RefreshControl, StyleSheet, View } from 'react-native';
import { Button, Divider, Text } from 'react-native-paper';
import { router } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import MaterialCommunityIcons from '@expo/vector-icons/MaterialCommunityIcons';

import { useAppTheme } from '@core/theme';
import { formatCurrency } from '@core/utils/format';
import { EmptyState } from '@components/ui/empty-state';
import { LoadingScreen } from '@components/ui/loading-screen';
import { useLiveStatus } from '@modules/dashboard/services/dashboard-hooks';
import type { AgentLiveStatus } from '@modules/inspections/types/inspection.types';

const STATUS_CONFIG: Record<string, { color: string; icon: string }> = {
  active: { color: '#2E7D32', icon: 'circle' },
  idle: { color: '#F9A825', icon: 'circle-outline' },
  offline: { color: '#C62828', icon: 'circle-off-outline' },
};

export default function AgentsScreen() {
  const { t } = useTranslation();
  const { colors } = useAppTheme();
  const insets = useSafeAreaInsets();
  const { data: liveData, isLoading, refetch, isRefetching } = useLiveStatus(true);

  const agents = useMemo(() => {
    if (!liveData?.agents) return [];
    const order = { active: 0, idle: 1, offline: 2 };
    return [...liveData.agents].sort(
      (a, b) => (order[a.status] ?? 3) - (order[b.status] ?? 3),
    );
  }, [liveData?.agents]);

  const counters = liveData?.counters;

  const renderItem = useCallback(
    ({ item }: { item: AgentLiveStatus }) => {
      const cfg = STATUS_CONFIG[item.status] ?? STATUS_CONFIG.offline;
      const timeLabel =
        item.status === 'active'
          ? item.inspections_today > 0
            ? `${item.inspections_today} insp.`
            : ''
          : item.minutes_since_activity != null
            ? `${item.minutes_since_activity}m`
            : '';

      return (
        <Pressable
          onPress={() => router.push(`/supervisor/agent/${item.agent_id}` as never)}
          style={({ pressed }) => [styles.item, pressed && { backgroundColor: colors.surfaceVariant }]}
          android_ripple={{ color: colors.surfaceVariant }}
        >
          <MaterialCommunityIcons name={cfg.icon as never} size={14} color={cfg.color} style={styles.dot} />
          <View style={styles.itemBody}>
            <Text variant="bodyMedium" style={{ color: colors.onSurface, fontWeight: '500' }} numberOfLines={1}>
              {item.agent_name}
            </Text>
            <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant }}>
              {item.inspections_today} {t('tabs.inspections').toLowerCase()}
              {item.cash_collected_today > 0 ? ` • ${formatCurrency(item.cash_collected_today)}` : ''}
            </Text>
          </View>
          <View style={styles.itemRight}>
            <Text variant="labelSmall" style={{ color: cfg.color, fontWeight: '600' }}>
              {t(`supervisor.${item.status}`)}
            </Text>
            {timeLabel ? (
              <Text variant="labelSmall" style={{ color: colors.onSurfaceVariant }}>
                {timeLabel}
              </Text>
            ) : null}
            {item.current_inspection_id && (
              <MaterialCommunityIcons name="clipboard-edit" size={14} color={colors.primary} />
            )}
          </View>
        </Pressable>
      );
    },
    [colors, t],
  );

  if (isLoading) return <LoadingScreen />;

  return (
    <View style={[styles.container, { backgroundColor: colors.background }]}>
      <View style={[styles.header, { paddingTop: insets.top + 4 }]}>
        <View style={styles.headerRow}>
          <Button icon="arrow-left" onPress={() => router.back()} textColor={colors.primary} compact>
            {t('inspection.back')}
          </Button>
          <Text variant="titleMedium" style={{ color: colors.onBackground, fontWeight: '700' }}>
            {t('supervisor.agentStatus')} ({agents.length})
          </Text>
          <View style={{ width: 60 }} />
        </View>
      </View>

      {/* Counters bar */}
      {counters && (
        <View style={[styles.countersBar, { backgroundColor: colors.surfaceVariant }]}>
          <CounterChip color="#2E7D32" count={counters.active_agents ?? 0} label={t('supervisor.active')} />
          <CounterChip color="#F9A825" count={counters.idle_agents ?? 0} label={t('supervisor.idle')} />
          <CounterChip color="#C62828" count={counters.offline_agents ?? 0} label={t('supervisor.offline')} />
          <View style={{ flex: 1 }} />
          <Text variant="labelSmall" style={{ color: colors.onSurfaceVariant }}>
            {counters.inspections_today ?? 0} insp.
          </Text>
        </View>
      )}

      <FlatList
        data={agents}
        keyExtractor={(item) => item.agent_id}
        renderItem={renderItem}
        ItemSeparatorComponent={() => <Divider style={{ marginLeft: 36 }} />}
        refreshControl={
          <RefreshControl refreshing={isRefetching} onRefresh={refetch} colors={[colors.primary]} />
        }
        ListEmptyComponent={
          <EmptyState
            icon="account-group"
            title={t('common.noData')}
            description={t('supervisor.noAgents', { defaultValue: 'No agents found' })}
          />
        }
        contentContainerStyle={agents.length === 0 ? styles.emptyContainer : styles.listContent}
      />
    </View>
  );
}

function CounterChip({ color, count, label }: { color: string; count: number; label: string }) {
  return (
    <View style={styles.chip}>
      <View style={[styles.chipDot, { backgroundColor: color }]} />
      <Text variant="labelSmall" style={{ fontWeight: '700' }}>{count}</Text>
      <Text variant="labelSmall" style={{ color: '#666', marginLeft: 2 }}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  header: { paddingHorizontal: 8, paddingBottom: 4 },
  headerRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  countersBar: {
    flexDirection: 'row',
    alignItems: 'center',
    marginHorizontal: 16,
    marginBottom: 8,
    padding: 10,
    borderRadius: 8,
    gap: 12,
  },
  chip: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  chipDot: { width: 8, height: 8, borderRadius: 4 },
  listContent: { paddingBottom: 32 },
  emptyContainer: { flexGrow: 1 },
  item: { flexDirection: 'row', alignItems: 'center', height: 64, paddingHorizontal: 16 },
  dot: { marginRight: 12 },
  itemBody: { flex: 1, justifyContent: 'center' },
  itemRight: { alignItems: 'flex-end', gap: 2 },
});
