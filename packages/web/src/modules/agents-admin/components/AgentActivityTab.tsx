'use client';

/**
 * Agent Activity Tab - Compact single-viewport dashboard
 * All metrics visible at a glance without scrolling on 1080p desktop.
 *
 * Row 1: KPIs (4 mini cards) — Processed, Approved, Rejected, Escalated
 * Row 2: Operations (6 inline metrics) — Capacity, Availability, SLA, Time, Quality, Locks
 * Footer: Last action / Last login / Period
 *
 * @module agents-admin/components
 */

import { useTranslations } from 'next-intl';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import {
  BarChart3,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Activity,
  Calendar,
  Clock,
  TrendingUp,
  Lock,
  Shield,
} from 'lucide-react';
import type { AgentWorkload, AgentPerformance } from '../types';

interface AgentActivityTabProps {
  workload?: AgentWorkload;
  performance?: AgentPerformance;
  isLoading: boolean;
}

export function AgentActivityTab({ workload, performance, isLoading }: AgentActivityTabProps) {
  const t = useTranslations('admin.agents');

  if (isLoading) {
    return (
      <div className="space-y-3">
        <div className="grid gap-2 grid-cols-4">
          {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-16" />)}
        </div>
        <div className="grid gap-2 grid-cols-3 lg:grid-cols-6">
          {[...Array(6)].map((_, i) => <Skeleton key={i} className="h-20" />)}
        </div>
      </div>
    );
  }

  if (!workload && !performance) {
    return (
      <div className="flex flex-col items-center justify-center py-10 text-center">
        <BarChart3 className="h-7 w-7 text-muted-foreground mb-2" />
        <p className="text-sm text-muted-foreground">{t('activity.noData')}</p>
        <p className="text-xs text-muted-foreground mt-1">{t('activity.noDataDesc')}</p>
      </div>
    );
  }

  // Performance metrics
  const processed = performance?.current_month_processed ?? 0;
  const approved = performance?.current_month_approved ?? 0;
  const rejected = performance?.current_month_rejected ?? 0;
  const escalated = performance?.current_month_escalated ?? 0;
  const slaRespected = performance?.sla_respected_count ?? 0;
  const slaMissed = performance?.sla_missed_count ?? 0;
  const slaTotal = slaRespected + slaMissed;
  const slaRate = slaTotal > 0 ? (slaRespected / slaTotal) * 100 : 100;

  // Workload metrics
  const currentAssignments = workload?.current_assignments ?? 0;
  const maxAssignments = workload?.max_concurrent_assignments ?? 20;
  const capacityPct = Number(workload?.capacity_percentage ?? 0);
  const availability = (workload?.availability as string) ?? 'available';
  const qualityScore = Number(workload?.quality_score_avg ?? 0);
  const successRate = Number(workload?.success_rate ?? 0);
  const deadlineRate = Number(workload?.deadline_compliance_rate ?? 0);

  const formatDuration = (minutes?: number) => {
    if (!minutes) return '-';
    if (minutes < 60) return `${Math.round(minutes)} min`;
    return `${(minutes / 60).toFixed(1)}h`;
  };

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleDateString();
  };

  const getAvailabilityConfig = (avail: string) => {
    const config: Record<string, { label: string; variant: 'default' | 'secondary' | 'destructive' | 'outline' }> = {
      available: { label: t('availability.available'), variant: 'default' },
      on_leave: { label: t('availability.onLeave'), variant: 'secondary' },
      sick_leave: { label: t('availability.sickLeave'), variant: 'destructive' },
      training: { label: t('availability.training'), variant: 'outline' },
      mission: { label: t('availability.mission'), variant: 'outline' },
      temporarily_unavailable: { label: t('availability.temporarilyUnavailable'), variant: 'secondary' },
    };
    return config[avail] || { label: avail, variant: 'outline' as const };
  };

  const getSlaColor = (rate: number) => {
    if (rate >= 90) return 'text-green-600';
    if (rate >= 70) return 'text-yellow-600';
    return 'text-red-600';
  };

  const getCapacityColor = (pct: number) => {
    if (pct > 80) return 'text-red-600';
    if (pct > 60) return 'text-yellow-600';
    return 'text-green-600';
  };

  const availConfig = getAvailabilityConfig(availability);

  return (
    <div className="space-y-3">
      {/* Row 1: KPI — 4 compact cards */}
      <div className="grid gap-2 grid-cols-2 md:grid-cols-4">
        <KpiCard
          icon={<BarChart3 className="h-3.5 w-3.5" />}
          label={t('activity.processedMonth')}
          value={processed}
        />
        <KpiCard
          icon={<CheckCircle2 className="h-3.5 w-3.5 text-green-500" />}
          label={t('activity.approved')}
          value={approved}
          valueColor="text-green-600"
          pct={processed > 0 ? ((approved / processed) * 100).toFixed(0) + '%' : undefined}
        />
        <KpiCard
          icon={<XCircle className="h-3.5 w-3.5 text-red-500" />}
          label={t('activity.rejected')}
          value={rejected}
          valueColor="text-red-600"
          pct={processed > 0 ? ((rejected / processed) * 100).toFixed(0) + '%' : undefined}
        />
        <KpiCard
          icon={<AlertTriangle className="h-3.5 w-3.5 text-orange-500" />}
          label={t('activity.escalated')}
          value={escalated}
          valueColor="text-orange-600"
          pct={processed > 0 ? ((escalated / processed) * 100).toFixed(0) + '%' : undefined}
        />
      </div>

      {/* Row 2: Operations — 6 dense metric cells */}
      <div className="grid gap-2 grid-cols-2 md:grid-cols-3 lg:grid-cols-6">
        {/* Capacity */}
        <div className="rounded-lg border bg-card p-3">
          <div className="text-[11px] text-muted-foreground flex items-center gap-1">
            <Activity className="h-3 w-3" />
            {t('activity.capacity')}
          </div>
          <div className="flex items-baseline gap-1 mt-1">
            <span className={`text-sm font-bold ${getCapacityColor(capacityPct)}`}>
              {currentAssignments}/{maxAssignments}
            </span>
            <span className="text-xs text-muted-foreground">{capacityPct}%</span>
          </div>
          <Progress value={capacityPct} className="h-1.5 mt-1.5" />
        </div>

        {/* Availability */}
        <div className="rounded-lg border bg-card p-3">
          <div className="text-[11px] text-muted-foreground flex items-center gap-1">
            <Calendar className="h-3 w-3" />
            {t('activity.availability')}
          </div>
          <div className="mt-1.5">
            <Badge variant={availConfig.variant} className="text-xs">{availConfig.label}</Badge>
          </div>
        </div>

        {/* SLA */}
        <div className="rounded-lg border bg-card p-3">
          <div className="text-[11px] text-muted-foreground flex items-center gap-1">
            <Shield className="h-3 w-3" />
            {t('activity.slaCompliance')}
          </div>
          <div className="flex items-baseline gap-1.5 mt-1">
            <span className="text-sm font-bold">{slaRate.toFixed(0)}%</span>
            <span className={`text-[11px] ${getSlaColor(slaRate)}`}>
              {slaRespected}✓ {slaMissed}✗
            </span>
          </div>
          <Progress value={slaRate} className="h-1.5 mt-1.5" />
        </div>

        {/* Processing Time */}
        <div className="rounded-lg border bg-card p-3">
          <div className="text-[11px] text-muted-foreground flex items-center gap-1">
            <Clock className="h-3 w-3" />
            {t('activity.avgTime')}
          </div>
          <div className="text-sm font-bold mt-1">
            {formatDuration(performance?.avg_processing_minutes)}
          </div>
          <div className="text-[11px] text-muted-foreground">{t('activity.perCase')}</div>
        </div>

        {/* Quality */}
        <div className="rounded-lg border bg-card p-3">
          <div className="text-[11px] text-muted-foreground flex items-center gap-1">
            <TrendingUp className="h-3 w-3" />
            {t('activity.quality')}
          </div>
          <div className="text-sm font-bold mt-1">{qualityScore.toFixed(1)}/10</div>
          <div className="text-[11px] text-muted-foreground">
            {(successRate * 100).toFixed(0)}% · {(deadlineRate * 100).toFixed(0)}%
          </div>
        </div>

        {/* Locks */}
        <div className="rounded-lg border bg-card p-3">
          <div className="text-[11px] text-muted-foreground flex items-center gap-1">
            <Lock className="h-3 w-3" />
            {t('activity.locks')}
          </div>
          <div className="flex items-baseline gap-1 mt-1">
            <span className="text-sm font-bold">{performance?.current_active_locks ?? 0}</span>
            <span className="text-[11px] text-muted-foreground">{t('activity.activeLocks')}</span>
          </div>
          <div className="text-[11px] text-muted-foreground">
            {t('activity.maxLocks', { count: performance?.max_concurrent_locks ?? 0 })}
          </div>
        </div>
      </div>

      {/* Footer: Activity dates — single line */}
      <div className="flex flex-wrap gap-x-4 gap-y-0.5 text-[11px] text-muted-foreground px-1">
        <span>{t('activity.lastAction', { date: formatDate(performance?.last_action_at) })}</span>
        <span>{t('activity.lastLogin', { date: formatDate(performance?.last_login_at) })}</span>
        {performance?.stats_period_start && (
          <span>{t('activity.periodSince', { date: performance.stats_period_start })}</span>
        )}
      </div>
    </div>
  );
}

/** Tiny KPI card — icon + label + bold value + optional percentage */
function KpiCard({
  icon,
  label,
  value,
  valueColor,
  pct,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
  valueColor?: string;
  pct?: string;
}) {
  return (
    <div className="rounded-lg border bg-card px-3 py-2">
      <div className="text-[11px] font-medium flex items-center gap-1 text-muted-foreground">
        {icon}
        {label}
      </div>
      <div className="flex items-baseline gap-1.5 mt-0.5">
        <span className={`text-xl font-bold ${valueColor ?? ''}`}>{value}</span>
        {pct && <span className="text-[11px] text-muted-foreground">{pct}</span>}
      </div>
    </div>
  );
}

export default AgentActivityTab;
