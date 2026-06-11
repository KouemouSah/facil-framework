/**
 * Analytics Screen — Performance metrics, zones, trends, export
 * Text-based analytics (no chart library dependency).
 */

import React, { useMemo, useState } from 'react';
import { Alert, ScrollView, StyleSheet, View } from 'react-native';
import { Button, Divider, SegmentedButtons, Text } from 'react-native-paper';
import { router } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import MaterialCommunityIcons from '@expo/vector-icons/MaterialCommunityIcons';
import { shareAsync } from 'expo-sharing';

import { useAppTheme } from '@core/theme';
import { formatCurrency } from '@core/utils/format';
import { appConfig } from '@core/config/app';
import { LoadingScreen } from '@components/ui/loading-screen';
import {
  useAgentPerformance,
  useZoneAnalytics,
  useTrends,
  usePriorityZones,
} from '@modules/supervisor/services/supervisor-hooks';
import { supervisorApi } from '@modules/supervisor/services/supervisor-api';

type Period = 'week' | 'month' | '3months';

function getDateRange(period: Period) {
  const now = new Date();
  const to = now.toISOString().split('T')[0];
  const from = new Date(now);
  if (period === 'week') from.setDate(from.getDate() - 7);
  else if (period === 'month') from.setMonth(from.getMonth() - 1);
  else from.setMonth(from.getMonth() - 3);
  return { from: from.toISOString().split('T')[0], to };
}

export default function AnalyticsScreen() {
  const { t } = useTranslation();
  const { colors, custom } = useAppTheme();
  const insets = useSafeAreaInsets();
  const [period, setPeriod] = useState<Period>('month');
  const [exporting, setExporting] = useState(false);

  const range = useMemo(() => getDateRange(period), [period]);
  const performance = useAgentPerformance(range.from, range.to);
  const zones = useZoneAnalytics(range.from, range.to);
  const trends = useTrends(range.from, range.to, period === 'week' ? 'daily' : 'weekly');
  const priorityZones = usePriorityZones();

  const isLoading = performance.isLoading && zones.isLoading;

  const handleExport = async (format: 'csv' | 'pdf') => {
    setExporting(true);
    try {
      const { getAccessToken } = await import('@core/auth/auth-storage');
      const token = await getAccessToken();
      const endpoint = format === 'csv' ? '/inspections/export/csv' : '/inspections/export/pdf';
      const url = `${appConfig.api.baseUrl}/api/${appConfig.api.version}${endpoint}?date_from=${range.from}&date_to=${range.to}`;

      // Use expo-file-system new API (SDK 54) to download
      const { File } = await import('expo-file-system');
      const ext = format === 'csv' ? 'csv' : 'pdf';
      const tempFile = new File('cache', `report.${ext}`);

      const response = await fetch(url, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const blob = await response.blob();
      const text = await new Promise<string>((resolve) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result as string);
        reader.readAsDataURL(blob);
      });
      const base64 = text.split(',')[1];
      await tempFile.write(base64, { encoding: 'base64' });
      await shareAsync(tempFile.uri);
    } catch {
      Alert.alert(t('common.error'), t('errors.serverError'));
    } finally {
      setExporting(false);
    }
  };

  if (isLoading) return <LoadingScreen />;

  const agents = performance.data?.items ?? [];
  const zoneItems = zones.data?.items ?? [];
  const trendPoints = trends.data?.points ?? [];
  const priority = priorityZones.data?.items ?? [];

  // Aggregate KPIs
  const totalInspections = agents.reduce((s, a) => s + a.inspections_count, 0);
  const avgConformity = agents.length > 0
    ? Math.round(agents.reduce((s, a) => s + a.conformity_rate, 0) / agents.length)
    : 0;
  const totalCollected = agents.reduce((s, a) => s + a.total_collected, 0);

  return (
    <View style={[styles.container, { backgroundColor: colors.background }]}>
      <View style={[styles.header, { paddingTop: insets.top + 4 }]}>
        <View style={styles.headerRow}>
          <Button icon="arrow-left" onPress={() => router.back()} textColor={colors.primary} compact>
            {t('inspection.back')}
          </Button>
          <Text variant="titleMedium" style={{ color: colors.onBackground, fontWeight: '700' }}>
            {t('supervisor.reports')}
          </Text>
          <View style={{ width: 60 }} />
        </View>
      </View>

      {/* Period selector */}
      <View style={styles.periodRow}>
        <SegmentedButtons
          value={period}
          onValueChange={(v) => setPeriod(v as Period)}
          buttons={[
            { value: 'week', label: '7d' },
            { value: 'month', label: '30d' },
            { value: '3months', label: '90d' },
          ]}
          density="small"
          style={styles.segmented}
        />
      </View>

      <ScrollView contentContainerStyle={styles.scrollContent}>
        {/* KPI Summary */}
        <View style={styles.kpiRow}>
          <KpiCard value={String(totalInspections)} label={t('dashboard.total')} color={colors.primary} />
          <KpiCard value={`${avgConformity}%`} label={t('dashboard.conforme')} color={custom.status.conforme} />
          <KpiCard value={formatCurrency(totalCollected)} label={t('dashboard.collected')} color={custom.tertiary.main} />
        </View>
        <Divider />

        {/* Top Agents */}
        <View style={styles.section}>
          <Text variant="labelLarge" style={[styles.sectionTitle, { color: colors.onSurfaceVariant }]}>
            {t('supervisor.agentStatus')} ({agents.length})
          </Text>
          {agents.slice(0, 5).map((a, i) => (
            <View key={a.agent_id} style={styles.agentRow}>
              <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant, width: 20 }}>
                {i + 1}.
              </Text>
              <View style={{ flex: 1 }}>
                <Text variant="bodyMedium" style={{ color: colors.onSurface }} numberOfLines={1}>
                  {a.agent_name}
                </Text>
              </View>
              <Text variant="labelSmall" style={{ color: colors.primary, width: 40, textAlign: 'right' }}>
                {a.inspections_count}
              </Text>
              <Text variant="labelSmall" style={{ color: custom.status.conforme, width: 45, textAlign: 'right' }}>
                {Math.round(a.conformity_rate)}%
              </Text>
              <Text variant="labelSmall" style={{ color: custom.tertiary.main, width: 70, textAlign: 'right' }}>
                {formatCurrency(a.total_collected)}
              </Text>
            </View>
          ))}
        </View>
        <Divider />

        {/* Trends */}
        {trendPoints.length > 0 && (
          <>
            <View style={styles.section}>
              <Text variant="labelLarge" style={[styles.sectionTitle, { color: colors.onSurfaceVariant }]}>
                {t('supervisor.features.analytics')}
              </Text>
              {trendPoints.slice(-7).map((tp) => (
                <View key={tp.date} style={styles.trendRow}>
                  <Text variant="labelSmall" style={{ color: colors.onSurfaceVariant, width: 75 }}>
                    {tp.date.slice(5)}
                  </Text>
                  <View style={styles.trendBar}>
                    <View
                      style={[
                        styles.barSegment,
                        {
                          backgroundColor: custom.status.conforme,
                          flex: tp.conforme || 1,
                        },
                      ]}
                    />
                    <View
                      style={[
                        styles.barSegment,
                        {
                          backgroundColor: custom.status.nonConforme,
                          flex: tp.non_conforme || 0.1,
                        },
                      ]}
                    />
                  </View>
                  <Text variant="labelSmall" style={{ color: colors.onSurface, width: 30, textAlign: 'right' }}>
                    {tp.inspections}
                  </Text>
                </View>
              ))}
            </View>
            <Divider />
          </>
        )}

        {/* Priority Zones */}
        {priority.length > 0 && (
          <>
            <View style={styles.section}>
              <Text variant="labelLarge" style={[styles.sectionTitle, { color: colors.onSurfaceVariant }]}>
                {t('supervisor.features.missionPlanning')}
              </Text>
              {priority.slice(0, 5).map((z) => (
                <View key={z.zone_code} style={styles.zoneRow}>
                  <MaterialCommunityIcons name="map-marker" size={16} color={colors.error} />
                  <View style={{ flex: 1, marginLeft: 8 }}>
                    <Text variant="bodyMedium" style={{ color: colors.onSurface }}>
                      {z.zone_name ?? z.zone_code}
                    </Text>
                    <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant }}>
                      {z.uninspected_companies} {t('verify.companyName').toLowerCase()} • {formatCurrency(z.overdue_obligations_amount)}
                    </Text>
                  </View>
                </View>
              ))}
            </View>
            <Divider />
          </>
        )}

        {/* Export buttons */}
        <View style={styles.exportRow}>
          <Button
            mode="outlined"
            icon="file-delimited"
            onPress={() => handleExport('csv')}
            loading={exporting}
            disabled={exporting}
            style={[styles.exportButton, { flex: 1 }]}
            compact
          >
            CSV
          </Button>
          <Button
            mode="outlined"
            icon="file-pdf-box"
            onPress={() => handleExport('pdf')}
            loading={exporting}
            disabled={exporting}
            style={[styles.exportButton, { flex: 1 }]}
            compact
          >
            PDF
          </Button>
        </View>
      </ScrollView>
    </View>
  );
}

function KpiCard({ value, label, color }: { value: string; label: string; color: string }) {
  return (
    <View style={kpiStyles.card}>
      <Text variant="titleLarge" style={{ color, fontWeight: '700' }}>{value}</Text>
      <Text variant="labelSmall" style={{ color: '#666' }}>{label}</Text>
    </View>
  );
}

const kpiStyles = StyleSheet.create({
  card: { flex: 1, alignItems: 'center', paddingVertical: 12 },
});

const styles = StyleSheet.create({
  container: { flex: 1 },
  header: { paddingHorizontal: 8, paddingBottom: 4 },
  headerRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  periodRow: { paddingHorizontal: 16, paddingBottom: 8 },
  segmented: { maxWidth: 250 },
  scrollContent: { paddingBottom: 32 },
  kpiRow: { flexDirection: 'row', paddingHorizontal: 8 },
  section: { paddingHorizontal: 16, paddingVertical: 12 },
  sectionTitle: { fontWeight: '600', marginBottom: 8 },
  agentRow: { flexDirection: 'row', alignItems: 'center', height: 40 },
  trendRow: { flexDirection: 'row', alignItems: 'center', height: 28 },
  trendBar: { flex: 1, flexDirection: 'row', height: 12, borderRadius: 3, overflow: 'hidden', marginHorizontal: 8 },
  barSegment: { minWidth: 2 },
  zoneRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 8 },
  exportRow: { flexDirection: 'row', gap: 12, paddingHorizontal: 16, paddingTop: 16 },
  exportButton: { borderRadius: 8 },
});
