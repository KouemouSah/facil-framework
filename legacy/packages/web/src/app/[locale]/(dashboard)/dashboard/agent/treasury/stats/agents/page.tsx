/**
 * Treasury Workload Dashboard (Carga de Trabajo)
 *
 * Single-viewport layout with 5 chart panels + KPIs + compact rankings.
 * Replaces the old static table + bar chart that always showed 0.
 */

'use client';

import { useState } from 'react';
import { useTranslations } from 'next-intl';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  AlertCircle,
  RotateCcw,
  Users,
  Gauge,
  Zap,
  ListOrdered,
  Trophy,
  Award,
} from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';
import { useWorkloadDashboard, WORKLOAD_DASHBOARD_QUERY_KEY } from '@/modules/treasury/hooks';
import {
  VelocityChart,
  SLAComplianceDonut,
  AgentLoadChart,
  ProcessingTimeChart,
  VolumeTrendChart,
} from '@/modules/treasury/components';
import { StatsTabNav } from '../_components/StatsTabNav';

type PeriodDays = 7 | 30 | 90;

export default function TreasuryWorkloadPage() {
  const t = useTranslations('treasury');
  const queryClient = useQueryClient();
  const [days, setDays] = useState<PeriodDays>(30);

  const { data, isLoading, error } = useWorkloadDashboard(days);

  const handleRetry = () => {
    queryClient.invalidateQueries({ queryKey: [WORKLOAD_DASHBOARD_QUERY_KEY] });
  };

  return (
    <div className="space-y-3">
      <StatsTabNav />
      {/* Row 0: Header + KPIs */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">{t('workload.title')}</h1>
            <p className="text-sm text-muted-foreground">{t('workload.description')}</p>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          {/* Period selector */}
          {([7, 30, 90] as PeriodDays[]).map(d => (
            <Button
              key={d}
              size="sm"
              variant={days === d ? 'default' : 'outline'}
              onClick={() => setDays(d)}
              className="h-7 text-xs"
            >
              {d === 7 ? t('workload.period7d') : d === 30 ? t('workload.period30d') : t('workload.period90d')}
            </Button>
          ))}
          <Button variant="outline" size="sm" onClick={handleRetry} className="h-7 gap-1.5" disabled={isLoading}>
            <RotateCcw className={`h-3 w-3 ${isLoading ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </div>

      {/* KPI cells */}
      {data ? (
        <div className="flex gap-2 flex-wrap">
          <KPICell
            icon={<ListOrdered className="h-4 w-4 text-blue-500" />}
            value={data.kpis.queueSize}
            label={t('workload.queueSize')}
          />
          <KPICell
            icon={<Zap className="h-4 w-4 text-emerald-500" />}
            value={data.kpis.velocityPerDay}
            label={t('workload.velocityPerDay')}
          />
          <KPICell
            icon={<Gauge className="h-4 w-4 text-orange-500" />}
            value={`${data.slaBreakdown.compliancePct}%`}
            label={t('workload.slaCompliance')}
            highlight={data.slaBreakdown.compliancePct < 80}
          />
          <KPICell
            icon={<Users className="h-4 w-4 text-violet-500" />}
            value={`${data.kpis.activeAgents}/${data.kpis.totalAgents}`}
            label={t('workload.activeAgents')}
          />
        </div>
      ) : isLoading ? (
        <div className="flex gap-2">
          {[1, 2, 3, 4].map(i => <Skeleton key={i} className="h-14 w-36" />)}
        </div>
      ) : null}

      {/* Error */}
      {error && (
        <div className="flex items-center justify-between p-3 bg-red-50 border border-red-200 rounded-lg">
          <div className="flex items-center gap-3">
            <AlertCircle className="h-4 w-4 text-red-500 flex-shrink-0" />
            <p className="text-sm text-red-700">{t('errors.loadingStats')}</p>
          </div>
          <Button variant="outline" size="sm" onClick={handleRetry} className="h-7 gap-1.5">
            <RotateCcw className="h-3 w-3" />
            {t('overview.retry')}
          </Button>
        </div>
      )}

      {/* Charts + Rankings */}
      {data ? (
        <>
          {/* Row 1: Velocity (2/3) + SLA Donut (1/3) */}
          <div className="grid gap-3 lg:grid-cols-3">
            <div className="lg:col-span-2">
              <VelocityChart data={data.dailyVelocity} t={t} />
            </div>
            <SLAComplianceDonut data={data.slaBreakdown} t={t} />
          </div>

          {/* Row 2: Agent Load (1/2) + Processing Time (1/2) */}
          <div className="grid gap-3 lg:grid-cols-2">
            <AgentLoadChart data={data.agentLoad} t={t} />
            <ProcessingTimeChart data={data.processingTimes} t={t} />
          </div>

          {/* Row 3: Volume Trend (2/3) + Rankings Table (1/3) */}
          <div className="grid gap-3 lg:grid-cols-3">
            <div className="lg:col-span-2">
              <VolumeTrendChart data={data.volumeTrend} t={t} />
            </div>
            <Card>
              <CardHeader className="pb-2">
                <div className="flex items-center gap-2">
                  <Trophy className="h-4 w-4 text-amber-500" />
                  <CardTitle className="text-base">{t('workload.rankings')}</CardTitle>
                </div>
              </CardHeader>
              <CardContent className="px-0 pb-2">
                {data.rankings.length > 0 ? (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="pl-4 text-xs">#</TableHead>
                        <TableHead className="text-xs">{t('agents.table.agent')}</TableHead>
                        <TableHead className="text-right text-xs">{t('workload.validated')}</TableHead>
                        <TableHead className="text-right text-xs pr-4">{t('workload.score')}</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {data.rankings.slice(0, 5).map((agent, idx) => (
                        <TableRow key={agent.agentName}>
                          <TableCell className="pl-4 py-1.5">
                            {idx === 0 ? <Award className="h-4 w-4 text-amber-500" /> : <span className="text-xs text-muted-foreground">{idx + 1}</span>}
                          </TableCell>
                          <TableCell className="py-1.5">
                            <span className="text-sm truncate block max-w-[120px]" title={agent.agentName}>
                              {agent.agentName}
                            </span>
                          </TableCell>
                          <TableCell className="text-right py-1.5">
                            <span className="text-sm">{agent.validated}</span>
                          </TableCell>
                          <TableCell className="text-right pr-4 py-1.5">
                            <Badge variant={agent.score >= 70 ? 'default' : agent.score >= 50 ? 'secondary' : 'destructive'} className="text-xs">
                              {agent.score}
                            </Badge>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                ) : (
                  <p className="text-sm text-muted-foreground text-center py-4">{t('workload.noAgents')}</p>
                )}
              </CardContent>
            </Card>
          </div>
        </>
      ) : isLoading ? (
        <div className="space-y-3">
          <div className="grid gap-3 lg:grid-cols-3">
            <Skeleton className="h-[240px] lg:col-span-2" />
            <Skeleton className="h-[240px]" />
          </div>
          <div className="grid gap-3 lg:grid-cols-2">
            <Skeleton className="h-[240px]" />
            <Skeleton className="h-[240px]" />
          </div>
          <div className="grid gap-3 lg:grid-cols-3">
            <Skeleton className="h-[220px] lg:col-span-2" />
            <Skeleton className="h-[220px]" />
          </div>
        </div>
      ) : null}
    </div>
  );
}

function KPICell({
  icon,
  value,
  label,
  highlight,
}: {
  icon: React.ReactNode;
  value: number | string;
  label: string;
  highlight?: boolean;
}) {
  return (
    <div className="flex items-center gap-2 bg-muted/50 rounded-lg px-3 py-2">
      {icon}
      <div>
        <p className={`text-lg font-bold leading-tight ${highlight ? 'text-orange-600' : ''}`}>
          {value}
        </p>
        <p className="text-[10px] text-muted-foreground leading-tight whitespace-nowrap">{label}</p>
      </div>
    </div>
  );
}
