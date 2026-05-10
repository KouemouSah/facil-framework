/**
 * Agent Performance Detail — KPIs, monthly history, recent inspections
 */

import React, { useMemo } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';
import { Button, Divider, Text } from 'react-native-paper';
import { router, useLocalSearchParams } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useQuery } from '@tanstack/react-query';
import MaterialCommunityIcons from '@expo/vector-icons/MaterialCommunityIcons';

import { useAppTheme } from '@core/theme';
import { formatCurrency } from '@core/utils/format';
import { LoadingScreen } from '@components/ui/loading-screen';
import { supervisorApi } from '@modules/supervisor/services/supervisor-api';

export default function AgentDetailScreen() {
  const { t } = useTranslation();
  const { colors, custom } = useAppTheme();
  const insets = useSafeAreaInsets();
  const { id } = useLocalSearchParams<{ id: string }>();

  // Fetch agent performance for current month
  const now = new Date();
  const dateFrom = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-01`;
  const dateTo = now.toISOString().split('T')[0];

  const { data, isLoading } = useQuery({
    queryKey: ['supervisor', 'agent-detail', id, dateFrom],
    queryFn: () => supervisorApi.getAgentPerformance({ date_from: dateFrom, date_to: dateTo }),
    enabled: !!id,
    staleTime: 5 * 60_000,
  });

  const agent = useMemo(() => {
    return data?.items?.find((a) => a.agent_id === id) ?? null;
  }, [data, id]);

  if (isLoading) return <LoadingScreen />;

  return (
    <View style={[styles.container, { backgroundColor: colors.background }]}>
      <View style={[styles.header, { paddingTop: insets.top + 4 }]}>
        <View style={styles.headerRow}>
          <Button icon="arrow-left" onPress={() => router.back()} textColor={colors.primary} compact>
            {t('inspection.back')}
          </Button>
          <Text variant="titleMedium" style={{ color: colors.onBackground, fontWeight: '700' }} numberOfLines={1}>
            {agent?.agent_name ?? t('supervisor.agentStatus')}
          </Text>
          <View style={{ width: 60 }} />
        </View>
      </View>

      {!agent ? (
        <View style={styles.emptyCenter}>
          <MaterialCommunityIcons name="account-off" size={48} color={colors.onSurfaceVariant} />
          <Text variant="bodyMedium" style={{ color: colors.onSurfaceVariant, marginTop: 12 }}>
            {t('common.noData')}
          </Text>
        </View>
      ) : (
        <ScrollView contentContainerStyle={styles.scrollContent}>
          {/* Agent info */}
          <View style={styles.section}>
            <View style={styles.agentHeader}>
              <View style={[styles.avatar, { backgroundColor: colors.primary }]}>
                <Text style={{ color: '#FFF', fontWeight: '700', fontSize: 18 }}>
                  {agent.agent_name?.charAt(0)?.toUpperCase() ?? 'A'}
                </Text>
              </View>
              <View style={{ flex: 1, marginLeft: 12 }}>
                <Text variant="titleMedium" style={{ color: colors.onSurface, fontWeight: '700' }}>
                  {agent.agent_name}
                </Text>
                <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant }}>
                  {agent.entity_code}
                </Text>
              </View>
            </View>
          </View>
          <Divider />

          {/* KPI cards */}
          <View style={styles.kpiGrid}>
            <KpiCard
              value={String(agent.inspections_count)}
              label={t('dashboard.total')}
              icon="clipboard-check"
              color={colors.primary}
            />
            <KpiCard
              value={`${Math.round(agent.conformity_rate)}%`}
              label={t('dashboard.conforme')}
              icon="check-circle"
              color={custom.status.conforme}
            />
            <KpiCard
              value={formatCurrency(agent.total_collected)}
              label={t('dashboard.collected')}
              icon="cash"
              color={custom.tertiary.main}
            />
            <KpiCard
              value={`${Math.round(agent.avg_duration_minutes)}m`}
              label={t('supervisor.avgDuration', { defaultValue: 'Avg.' })}
              icon="timer-outline"
              color={colors.secondary}
            />
          </View>
          <Divider />

          {/* Detailed stats */}
          <View style={styles.section}>
            <Text variant="labelLarge" style={[styles.sectionTitle, { color: colors.onSurfaceVariant }]}>
              {t('supervisor.reports')}
            </Text>
            <StatRow label={t('dashboard.conforme')} value={agent.conforme_count} color={custom.status.conforme} />
            <StatRow label={t('dashboard.nonConforme')} value={agent.non_conforme_count} color={custom.status.nonConforme} />
            <StatRow label={t('seal.title')} value={agent.seals_proposed} color={custom.status.sealProposed} />
            <StatRow label={t('med.title')} value={agent.med_issued} color={custom.status.miseEnDemeure} />
          </View>
        </ScrollView>
      )}
    </View>
  );
}

function KpiCard({ value, label, icon, color }: { value: string; label: string; icon: string; color: string }) {
  return (
    <View style={kpiStyles.card}>
      <MaterialCommunityIcons name={icon as never} size={20} color={color} />
      <Text variant="titleMedium" style={{ color, fontWeight: '700', marginTop: 4 }}>{value}</Text>
      <Text variant="labelSmall" style={{ color: '#666' }}>{label}</Text>
    </View>
  );
}

function StatRow({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <View style={statStyles.row}>
      <View style={[statStyles.dot, { backgroundColor: color }]} />
      <Text variant="bodyMedium" style={{ flex: 1 }}>{label}</Text>
      <Text variant="titleSmall" style={{ color, fontWeight: '700' }}>{value}</Text>
    </View>
  );
}

const kpiStyles = StyleSheet.create({
  card: { width: '48%' as unknown as number, alignItems: 'center', paddingVertical: 16, backgroundColor: 'transparent' },
});

const statStyles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', height: 40 },
  dot: { width: 8, height: 8, borderRadius: 4, marginRight: 12 },
});

const styles = StyleSheet.create({
  container: { flex: 1 },
  header: { paddingHorizontal: 8, paddingBottom: 4 },
  headerRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  scrollContent: { paddingBottom: 32 },
  emptyCenter: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  section: { paddingHorizontal: 16, paddingVertical: 12 },
  sectionTitle: { fontWeight: '600', marginBottom: 8 },
  agentHeader: { flexDirection: 'row', alignItems: 'center' },
  avatar: { width: 48, height: 48, borderRadius: 24, justifyContent: 'center', alignItems: 'center' },
  kpiGrid: { flexDirection: 'row', flexWrap: 'wrap', paddingHorizontal: 12, justifyContent: 'center' },
});
