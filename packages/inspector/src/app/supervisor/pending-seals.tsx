/**
 * Pending Seals Screen — List seals awaiting supervisor approval
 * Sorted by urgency (oldest first). Red badge if >20h without decision.
 */

import React, { useCallback, useMemo } from 'react';
import { FlatList, Pressable, RefreshControl, StyleSheet, View } from 'react-native';
import { Button, Divider, Text } from 'react-native-paper';
import { router } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import MaterialCommunityIcons from '@expo/vector-icons/MaterialCommunityIcons';

import { useAppTheme } from '@core/theme';
import { formatDate, formatCurrency } from '@core/utils/format';
import { EmptyState } from '@components/ui/empty-state';
import { LoadingScreen } from '@components/ui/loading-screen';
import { useSupervisorDashboard } from '@modules/dashboard/services/dashboard-hooks';
import type { PendingSealItem } from '@modules/inspections/types/inspection.types';

const URGENT_THRESHOLD_HOURS = 20;

function getHoursAgo(isoDate: string | null): number {
  if (!isoDate) return 0;
  return Math.floor((Date.now() - new Date(isoDate).getTime()) / (1000 * 60 * 60));
}

export default function PendingSealsScreen() {
  const { t } = useTranslation();
  const { colors, custom } = useAppTheme();
  const insets = useSafeAreaInsets();
  const { data: dashboard, isLoading, refetch, isRefetching } = useSupervisorDashboard(true);

  const seals = useMemo(() => {
    if (!dashboard?.pending_seals) return [];
    // Sort by oldest first (most urgent)
    return [...dashboard.pending_seals].sort((a, b) => {
      const ta = a.seal_proposed_at ? new Date(a.seal_proposed_at).getTime() : 0;
      const tb = b.seal_proposed_at ? new Date(b.seal_proposed_at).getTime() : 0;
      return ta - tb;
    });
  }, [dashboard?.pending_seals]);

  const renderItem = useCallback(
    ({ item }: { item: PendingSealItem }) => {
      const hoursAgo = getHoursAgo(item.seal_proposed_at);
      const isUrgent = hoursAgo >= URGENT_THRESHOLD_HOURS;

      return (
        <Pressable
          onPress={() => router.push(`/inspection/${item.id}/seal-review` as never)}
          style={({ pressed }) => [styles.item, pressed && { backgroundColor: colors.surfaceVariant }]}
          android_ripple={{ color: colors.surfaceVariant }}
        >
          <View style={styles.itemLeft}>
            <MaterialCommunityIcons
              name="shield-alert"
              size={22}
              color={isUrgent ? colors.error : custom.status.sealProposed}
            />
          </View>
          <View style={styles.itemBody}>
            <Text variant="bodyMedium" style={{ color: colors.onSurface, fontWeight: '600' }} numberOfLines={1}>
              {item.company_name ?? '—'}
            </Text>
            <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant }} numberOfLines={1}>
              {item.company_nif ?? ''} {item.inspection_date ? `• ${formatDate(item.inspection_date)}` : ''}
            </Text>
            <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant }}>
              {t('seal.reason')}: {item.seal_reason ? t(`seal.reasons.${item.seal_reason}`) : '—'}
            </Text>
            <Text variant="labelSmall" style={{ color: colors.onSurfaceVariant }}>
              {t('seal.proposedBy')}: {item.agent_name ?? '—'} • {hoursAgo}h
            </Text>
          </View>
          <View style={styles.itemRight}>
            {isUrgent && (
              <View style={[styles.urgentBadge, { backgroundColor: colors.error }]}>
                <Text variant="labelSmall" style={{ color: '#FFF', fontSize: 9, fontWeight: '700' }}>
                  {t('common.urgent', { defaultValue: 'URGENT' })}
                </Text>
              </View>
            )}
            <Text variant="labelSmall" style={{ color: custom.status.nonConforme }}>
              {formatCurrency(item.unpaid_obligations_amount)}
            </Text>
            <MaterialCommunityIcons name="chevron-right" size={18} color={colors.onSurfaceVariant} />
          </View>
        </Pressable>
      );
    },
    [colors, custom, t],
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
            {t('supervisor.pendingSeals')} ({seals.length})
          </Text>
          <View style={{ width: 60 }} />
        </View>
      </View>

      <FlatList
        data={seals}
        keyExtractor={(item) => item.id}
        renderItem={renderItem}
        ItemSeparatorComponent={() => <Divider style={{ marginLeft: 52 }} />}
        refreshControl={
          <RefreshControl refreshing={isRefetching} onRefresh={refetch} colors={[colors.primary]} />
        }
        ListEmptyComponent={
          <EmptyState
            icon="shield-check"
            title={t('common.noData')}
            description={t('supervisor.noSeals', { defaultValue: 'No pending seals to review' })}
          />
        }
        contentContainerStyle={seals.length === 0 ? styles.emptyContainer : styles.listContent}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  header: { paddingHorizontal: 8, paddingBottom: 4 },
  headerRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  listContent: { paddingBottom: 32 },
  emptyContainer: { flexGrow: 1 },
  item: { flexDirection: 'row', alignItems: 'center', paddingVertical: 12, paddingHorizontal: 16 },
  itemLeft: { width: 36, alignItems: 'center' },
  itemBody: { flex: 1, marginLeft: 4, gap: 1 },
  itemRight: { alignItems: 'flex-end', marginLeft: 8, gap: 4 },
  urgentBadge: { paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4 },
});
