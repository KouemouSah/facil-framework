/**
 * Dashboard Screen - Facil Inspeccion
 *
 * Auto-detects agent vs supervisor.
 * Agent: today stats + quick actions + recent inspections
 * Supervisor: live counters + today/week stats + alerts + recent inspections
 */

import React, { useCallback } from 'react';
import { Alert, RefreshControl, ScrollView, StyleSheet, View } from 'react-native';
import { IconButton, Text } from 'react-native-paper';
import { useTranslation } from 'react-i18next';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { router } from 'expo-router';
import { useQueryClient } from '@tanstack/react-query';

import { useAuth } from '@core/hooks/use-auth';
import { useAppTheme } from '@core/theme';
import { getFullName } from '@core/config/types';
import {
  useAgentStats,
  useRecentInspections,
  useSupervisorDashboard,
  useLiveStatus,
} from '@modules/dashboard/services/dashboard-hooks';
import { StatsGrid } from '@modules/dashboard/components/stats-grid';
import { RecentInspections } from '@modules/dashboard/components/recent-inspections';
import { QuickActions } from '@modules/dashboard/components/quick-actions';
import { SupervisorAlerts } from '@modules/dashboard/components/supervisor-alerts';
import { LiveCounters } from '@modules/dashboard/components/live-counters';
import { usePushNotifications } from '@modules/notifications/services/use-push-notifications';
import { SkeletonStatsGrid, SkeletonListItem } from '@components/ui/skeleton';
import { AnimatedSection } from '@components/ui/animated-section';
import { QueryError } from '@components/ui/query-error';

export default function DashboardScreen() {
  const { t } = useTranslation();
  const { user, isSupervisor, agentContext, signOut } = useAuth();
  const { colors } = useAppTheme();
  const insets = useSafeAreaInsets();

  // Register push notifications on dashboard mount (main entry point)
  usePushNotifications();
  const queryClient = useQueryClient();

  // Agent data
  const agentStats = useAgentStats();
  const recentInspections = useRecentInspections();

  // Supervisor data (only fetched if supervisor)
  const supervisorDashboard = useSupervisorDashboard(isSupervisor);
  const liveStatus = useLiveStatus(isSupervisor);

  const isRefreshing =
    agentStats.isFetching || recentInspections.isFetching ||
    (isSupervisor && (supervisorDashboard.isFetching || liveStatus.isFetching));

  const onRefresh = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['dashboard'] });
  }, [queryClient]);

  const userName = user ? getFullName(user) : '';
  const entityName = user?.entity_name ?? '';
  const locationLabel = agentContext
    ? `${agentContext.locationCity} (${agentContext.locationRegion})`
    : '';

  return (
    <View style={[styles.container, { backgroundColor: colors.background }]}>
      {/* AppBar Material */}
      <View style={[styles.appBar, { paddingTop: insets.top + 4, backgroundColor: colors.surface }]}>
        <View style={[styles.avatar, { backgroundColor: colors.primary }]}>
          <Text style={{ color: '#FFF', fontWeight: '700', fontSize: 14 }}>
            {userName?.charAt(0)?.toUpperCase() ?? 'A'}
          </Text>
        </View>
        <View style={styles.appBarTitle}>
          <Text variant="titleMedium" style={{ color: colors.onSurface, fontWeight: '700' }}>
            {t('app.name')}
          </Text>
          <Text variant="labelSmall" style={{ color: colors.onSurfaceVariant }} numberOfLines={1}>
            {entityName}{locationLabel ? ` \u2022 ${locationLabel}` : ''}
          </Text>
        </View>
        {isSupervisor && (
          <IconButton
            icon="shield-account"
            size={22}
            iconColor={colors.primary}
            onPress={() => router.push('/supervisor/' as never)}
          />
        )}
        <IconButton
          icon="logout"
          size={20}
          iconColor={colors.onSurfaceVariant}
          onPress={() => {
            Alert.alert(
              t('auth.signOut'),
              '',
              [
                { text: t('common.cancel'), style: 'cancel' },
                { text: t('auth.signOut'), style: 'destructive', onPress: () => signOut() },
              ],
            );
          }}
        />
      </View>

      <ScrollView
        contentContainerStyle={styles.scrollContent}
        refreshControl={
          <RefreshControl
            refreshing={!!isRefreshing}
            onRefresh={onRefresh}
            colors={[colors.primary]}
          />
        }
      >
        {/* Quick Actions */}
        <AnimatedSection delay={0}>
          <QuickActions />
        </AnimatedSection>

        {/* Supervisor: Live Counters */}
        {isSupervisor && liveStatus.data && (
          <AnimatedSection delay={100}>
            <LiveCounters counters={liveStatus.data.counters} />
          </AnimatedSection>
        )}

        {/* Supervisor: Alerts */}
        {isSupervisor && supervisorDashboard.data && (
          <AnimatedSection delay={200}>
            <SupervisorAlerts
            pendingSeals={supervisorDashboard.data.pending_seals.length}
            overdueMed={supervisorDashboard.data.overdue_med}
            unreconciledCash={supervisorDashboard.data.unreconciled_cash_amount}
            unreconciledCount={supervisorDashboard.data.unreconciled_cash_count}
            locationLabel={agentContext?.isMainOffice ? t('dashboard.allLocations', { defaultValue: 'global' }) : agentContext?.locationCity}
          />
          </AnimatedSection>
        )}

        {/* Stats Grid (with skeleton fallback) */}
        <AnimatedSection delay={300}>
          {isSupervisor && supervisorDashboard.data ? (
            <>
              <StatsGrid stats={supervisorDashboard.data.today} label={`${t('dashboard.todayStats')} — ${agentContext?.isMainOffice ? t('dashboard.allLocations', { defaultValue: 'All locations' }) : agentContext?.locationCity ?? ''}`} />
              <StatsGrid stats={supervisorDashboard.data.week} label={`${t('dashboard.weekStats')} — ${agentContext?.isMainOffice ? t('dashboard.allLocations', { defaultValue: 'All locations' }) : agentContext?.locationCity ?? ''}`} />
            </>
          ) : agentStats.data ? (
            <StatsGrid stats={agentStats.data} label={`${t('dashboard.todayStats')}${agentContext?.locationCity ? ` — ${agentContext.locationCity}` : ''}`} />
          ) : agentStats.isLoading ? (
            <SkeletonStatsGrid />
          ) : agentStats.error ? (
            <QueryError error={agentStats.error} onRetry={() => agentStats.refetch()} isRetrying={agentStats.isFetching} compact />
          ) : null}
        </AnimatedSection>

        {/* Recent Inspections (with skeleton fallback) */}
        {recentInspections.isLoading && !recentInspections.data ? (
          <View style={{ paddingTop: 8 }}>
            <SkeletonListItem />
            <SkeletonListItem />
            <SkeletonListItem />
          </View>
        ) : (
          <AnimatedSection delay={400}>
            <RecentInspections
              items={
                isSupervisor && supervisorDashboard.data
                  ? supervisorDashboard.data.recent_inspections
                  : recentInspections.data?.items ?? []
              }
              title={t('dashboard.recent')}
            />
          </AnimatedSection>
        )}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  appBar: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingBottom: 8,
    borderBottomWidth: 0.5,
    borderBottomColor: '#E0E0E0',
  },
  avatar: {
    width: 36,
    height: 36,
    borderRadius: 18,
    justifyContent: 'center',
    alignItems: 'center',
  },
  appBarTitle: {
    flex: 1,
    marginLeft: 10,
  },
  scrollContent: { paddingTop: 12, paddingBottom: 24 },
});
