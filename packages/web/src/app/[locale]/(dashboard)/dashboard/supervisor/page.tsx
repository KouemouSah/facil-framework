'use client';

/**
 * Enhanced Supervisor Dashboard — Single-viewport layout
 *
 * Combines team overview (stats, quick actions, anomalies)
 * with treasury analytics (charts, panels, badges) in one page.
 *
 * Layout (~600px total):
 *   Row 1: Header + 6 compact stat cells (team + treasury)
 *   Row 2: Alert banners (anomalies + SLA, conditional)
 *   Row 3: Quick action buttons (compact inline)
 *   Row 4: CashFlowChart (2/3) + ServiceDistribution (1/3)
 *   Row 5: AgentWorkload + SLAAlerts + RecentActivity (1/3 each)
 */

import { useState, useCallback, useMemo, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useLocale, useTranslations } from 'next-intl';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import Link from 'next/link';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Users,
  UserPlus,
  AlertTriangle,
  CheckCircle,
  Clock,
  CreditCard,
  ArrowRight,
  AlertCircle,
  RotateCcw,
  BarChart2,
  Settings2,
  FileBarChart,
  RefreshCw,
} from 'lucide-react';
import apiClient from '@/core/api/client';
import { useTreasuryStats, useSupervisorOverview } from '@/modules/treasury/hooks';
import {
  CashFlowChart,
  AgentWorkloadPanel,
  SLAAlertsPanel,
  ServiceDistributionChart,
  RecentActivityTimeline,
} from '@/modules/treasury/components';
import type { SupervisorDashboardStats, AnomalyResponse } from './types';

export default function SupervisorDashboardPage() {
  const locale = useLocale();
  const t = useTranslations('supervisor');
  const tTreasury = useTranslations('treasury');
  const tCommon = useTranslations('common');
  const queryClient = useQueryClient();
  const router = useRouter();

  // Detect supervisor entity — redirect non-TESORO to their OMS dashboard
  const { data: agentProfile } = useQuery({
    queryKey: ['agent-profile-redirect'],
    queryFn: async () => {
      const res = await apiClient.get('/agents/profiles/me');
      return res.data;
    },
    staleTime: 300_000,
  });

  useEffect(() => {
    if (!agentProfile) return;
    const entityCode = agentProfile.entity_code as string;
    if (!entityCode || entityCode === 'TESORO') return; // Stay on treasury dashboard

    // OMS supervisors (CAMARA, AYUNTAMIENTO, MIN_*) → entity-dashboard
    const omsEntities = [
      'CAMARA_COMERCIO', 'AYUNTAMIENTO',
      'MIN_HACIENDA', 'MIN_COMERCIO', 'MIN_INFORMACION',
      'MIN_TURISMO', 'MIN_AGRICULTURA', 'MIN_ELECTRICIDAD',
    ];
    if (omsEntities.includes(entityCode) || entityCode.startsWith('MIN_')) {
      router.replace(`/${locale}/dashboard/supervisor/entity-dashboard`);
    } else {
      // Service Request supervisors (CNEDOGE, DGT, etc.) → their agent dashboard
      const slug = entityCode.toLowerCase().replace(/_/g, '-');
      router.replace(`/${locale}/dashboard/agent/${slug}`);
    }
  }, [agentProfile, locale, router]);

  // Supervisor team stats
  const {
    data: stats,
    isLoading: statsLoading,
    error: statsError,
  } = useQuery<SupervisorDashboardStats>({
    queryKey: ['supervisor', 'dashboard', 'stats'],
    queryFn: async () => {
      const response = await apiClient.get('/supervisor/dashboard');
      return response.data;
    },
    staleTime: 30000,
    refetchInterval: 60000,
  });

  // Anomaly alerts
  const { data: anomalies } = useQuery<AnomalyResponse>({
    queryKey: ['supervisor', 'anomalies'],
    queryFn: async () => {
      const response = await apiClient.get('/supervisor/anomalies');
      return response.data;
    },
    staleTime: 300000,
  });

  // Treasury stats (badges: monto hoy, sin reconciliar)
  const { data: treasuryStats, isLoading: treasuryLoading } = useTreasuryStats();

  // Treasury supervisor overview (charts + panels)
  const [overviewDays, setOverviewDays] = useState(30);
  const {
    data: overview,
    isLoading: overviewLoading,
    error: overviewError,
  } = useSupervisorOverview(overviewDays);

  const isLoading = statsLoading || treasuryLoading;

  const formatCurrency = useCallback((amount: number) => {
    const intlLocale = locale === 'fr' ? 'fr-FR' : locale === 'en' ? 'en-US' : 'es-GQ';
    return new Intl.NumberFormat(intlLocale, {
      style: 'currency',
      currency: 'XAF',
      minimumFractionDigits: 0,
    }).format(amount);
  }, [locale]);

  // SLA breached count
  const breachedCount = overview?.slaAlerts?.filter(
    (a: { slaStatus: string }) => a.slaStatus === 'breached'
  ).length ?? 0;

  // Retry handler
  const handleRetry = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['supervisor', 'dashboard', 'stats'] });
    queryClient.invalidateQueries({ queryKey: ['treasury-stats'] });
    queryClient.invalidateQueries({ queryKey: ['treasury-supervisor-overview'] });
  }, [queryClient]);

  // Quick actions from supervisor menu structure
  const quickActions = useMemo(() => [
    { id: 'team', icon: Users, label: t('nav.team'), description: t('team.title'), href: `/${locale}/dashboard/supervisor/team/agents`, color: 'text-blue-500' },
    { id: 'workload', icon: BarChart2, label: t('nav.workload'), description: t('workload.title'), href: `/${locale}/dashboard/supervisor/team/workload`, color: 'text-purple-500' },
    { id: 'assignments', icon: UserPlus, label: t('nav.assignments') || 'Asignaciones', description: t('assignments.title') || 'Centro de asignaciones', href: `/${locale}/dashboard/supervisor/assignments/manual`, color: 'text-green-500' },
    { id: 'rules', icon: Settings2, label: t('nav.rules'), description: t('rules.title'), href: `/${locale}/dashboard/supervisor/assignments/rules`, color: 'text-gray-500' },
    { id: 'escalations', icon: AlertTriangle, label: t('nav.escalations'), href: `/${locale}/dashboard/supervisor/escalations/pending`, color: 'text-orange-500', badge: stats?.escalations.pending },
    { id: 'reports', icon: FileBarChart, label: t('nav.reports'), href: `/${locale}/dashboard/supervisor/reports`, color: 'text-teal-500' },
  ], [t, locale, stats?.escalations.pending]);

  return (
    <div className="space-y-3">
      {/* Row 1: Header + 6 Compact Stats */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{t('dashboard.title')}</h1>
          <p className="text-sm text-muted-foreground">{t('dashboard.welcome', { name: '' })}</p>
        </div>

        <div className="flex gap-2 flex-shrink-0 flex-wrap justify-end">
          {/* Team stats */}
          <StatCell
            icon={<Users className="h-4 w-4 text-blue-500" />}
            value={`${stats?.team.activeAgents ?? 0}/${stats?.team.totalAgents ?? 0}`}
            label={t('team.activeAgents')}
            isLoading={isLoading}
          />
          <StatCell
            icon={<Clock className="h-4 w-4 text-orange-500" />}
            value={stats?.escalations.pending ?? 0}
            label={t('escalations.pending')}
            isLoading={isLoading}
            highlight={(stats?.escalations.pending ?? 0) > 0}
          />
          <StatCell
            icon={<CheckCircle className="h-4 w-4 text-green-500" />}
            value={stats?.assignments.completedToday ?? 0}
            label={t('stats.teamCompleted')}
            isLoading={isLoading}
          />
          {/* Treasury stats */}
          <StatCell
            icon={<CreditCard className="h-4 w-4 text-blue-500" />}
            value={formatCurrency(treasuryStats?.todayValidatedAmount ?? 0)}
            label={tTreasury('stats.todayAmount')}
            isLoading={isLoading}
          />
          <StatCell
            icon={<AlertCircle className="h-4 w-4 text-orange-500" />}
            value={overview?.slaAlertsCount ?? 0}
            label={tTreasury('overview.slaAlerts')}
            isLoading={isLoading || overviewLoading}
            highlight={(overview?.slaAlertsCount ?? 0) > 0}
          />
          <StatCell
            icon={<RefreshCw className="h-4 w-4 text-muted-foreground" />}
            value={treasuryStats?.unreconciledCount ?? 0}
            label={tTreasury('stats.unreconciled')}
            isLoading={isLoading}
          />
        </div>
      </div>

      {/* Error State */}
      {/* Error State */}
      {(statsError || overviewError) && (
        <div className="flex items-center justify-between p-3 bg-red-50 border border-red-200 rounded-lg">
          <div className="flex items-center gap-3">
            <AlertCircle className="h-4 w-4 text-red-500 flex-shrink-0" />
            <p className="text-sm text-red-700">{tCommon('errorGeneric')}</p>
          </div>
          <Button variant="outline" size="sm" onClick={handleRetry} className="h-7 gap-1.5">
            <RotateCcw className="h-3 w-3" />
            {tTreasury('overview.retry')}
          </Button>
        </div>
      )}

      {/* Alert Banners (anomalies + SLA) */}
      {anomalies && anomalies.count > 0 && (
        <div className="flex items-center gap-3 p-2.5 bg-orange-50 border border-orange-200 rounded-lg" role="alert">
          <AlertTriangle className="h-4 w-4 text-orange-600 flex-shrink-0" />
          <span className="text-sm font-medium text-orange-800">
            {t('anomalies.title', { defaultValue: 'Alertas del Sistema' })} ({anomalies.count})
          </span>
          <div className="flex gap-1 ml-2">
            {anomalies.anomalies.slice(0, 3).map((a, i) => (
              <Badge key={i} variant={a.severity === 'critical' ? 'destructive' : 'secondary'} className="text-xs">
                {a.type}
              </Badge>
            ))}
          </div>
        </div>
      )}
      {breachedCount > 0 && (
        <div className="flex items-center gap-3 p-2.5 bg-amber-50 border border-amber-200 rounded-lg" role="alert">
          <AlertTriangle className="h-4 w-4 text-amber-600 flex-shrink-0" />
          <span className="text-sm font-medium text-amber-800">
            {tTreasury('overview.breachedCount', { count: breachedCount })} — {tTreasury('overview.slaAtRisk')}
          </span>
        </div>
      )}

      {/* Row 3: Quick Actions (compact inline buttons) */}
      <Card>
        <CardContent className="py-3 px-4">
          <div className="flex flex-wrap gap-2">
            {quickActions.map((action) => {
              const Icon = action.icon;
              return (
                <Link key={action.id} href={action.href}>
                  <Button variant="outline" size="sm" className="h-8 gap-1.5">
                    <Icon className={`h-3.5 w-3.5 ${action.color}`} />
                    {action.label}
                    {action.badge != null && action.badge > 0 && (
                      <Badge variant="destructive" className="h-4 px-1 text-[10px] ml-0.5">
                        {action.badge}
                      </Badge>
                    )}
                    <ArrowRight className="h-3 w-3 ml-1" />
                  </Button>
                </Link>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* Row 4-5: Treasury Charts + Panels */}
      {overview ? (
        <>
          <div className="grid gap-3 lg:grid-cols-3">
            <div className="lg:col-span-2">
              <CashFlowChart
                data={overview.paymentFlow}
                periodDays={overviewDays}
                onPeriodChange={setOverviewDays}
                t={tTreasury}
              />
            </div>
            <div>
              <ServiceDistributionChart data={overview.topServices} t={tTreasury} />
            </div>
          </div>
          <div className="grid gap-3 lg:grid-cols-3">
            <AgentWorkloadPanel agents={overview.agentLoad} t={tTreasury} />
            <SLAAlertsPanel alerts={overview.slaAlerts} t={tTreasury} />
            <RecentActivityTimeline activities={overview.recentActivity} t={tTreasury} />
          </div>
        </>
      ) : overviewLoading ? (
        <div className="space-y-3">
          <div className="grid gap-3 lg:grid-cols-3">
            <Skeleton className="h-[230px] lg:col-span-2" />
            <Skeleton className="h-[230px]" />
          </div>
          <div className="grid gap-3 lg:grid-cols-3">
            <Skeleton className="h-[200px]" />
            <Skeleton className="h-[200px]" />
            <Skeleton className="h-[200px]" />
          </div>
        </div>
      ) : null}
    </div>
  );
}

/** Compact stat cell for inline display */
function StatCell({
  icon,
  value,
  label,
  isLoading,
  highlight,
}: {
  icon: React.ReactNode;
  value: number | string;
  label: string;
  isLoading: boolean;
  highlight?: boolean;
}) {
  return (
    <div className="flex items-center gap-2 bg-muted/50 rounded-lg px-3 py-2">
      {icon}
      <div>
        {isLoading ? (
          <Skeleton className="h-5 w-12" />
        ) : (
          <p className={`text-lg font-bold leading-tight ${highlight ? 'text-orange-600' : ''}`}>
            {value}
          </p>
        )}
        <p className="text-[10px] text-muted-foreground leading-tight whitespace-nowrap">{label}</p>
      </div>
    </div>
  );
}
