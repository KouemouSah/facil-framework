'use client';

/**
 * Performance Stats Component
 * Displays agent performance statistics
 *
 * @module agents-admin/components
 */

import { useTranslations } from 'next-intl';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import {
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Clock,
  BarChart3,
  Lock,
} from 'lucide-react';
import type { AgentPerformance } from '../types';

interface PerformanceStatsProps {
  performance: AgentPerformance;
  className?: string;
}

export function PerformanceStats({ performance, className }: PerformanceStatsProps) {
  const t = useTranslations('admin.agents');

  const totalProcessed = performance.current_month_processed || 0;
  const approvalRate = totalProcessed > 0
    ? (performance.current_month_approved / totalProcessed) * 100
    : 0;
  const rejectionRate = totalProcessed > 0
    ? (performance.current_month_rejected / totalProcessed) * 100
    : 0;
  const escalationRate = totalProcessed > 0
    ? (performance.current_month_escalated / totalProcessed) * 100
    : 0;

  const slaTotal = performance.sla_respected_count + performance.sla_missed_count;
  const slaRate = slaTotal > 0
    ? (performance.sla_respected_count / slaTotal) * 100
    : 100;

  const formatMinutes = (minutes?: number) => {
    if (!minutes) return '-';
    if (minutes < 60) return `${Math.round(minutes)} min`;
    return `${(minutes / 60).toFixed(1)}h`;
  };

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleString();
  };

  const getSlaLabel = (rate: number) => {
    if (rate >= 90) return t('perf.excellent');
    if (rate >= 70) return t('perf.acceptable');
    return t('perf.needsImprovement');
  };

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Period Info */}
      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>{t('perf.period', { start: performance.stats_period_start })}</span>
        {performance.stats_period_end && (
          <span>{t('perf.periodTo', { end: performance.stats_period_end })}</span>
        )}
      </div>

      {/* Main Stats Grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {/* Total Processed */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <BarChart3 className="h-4 w-4 text-muted-foreground" />
              {t('perf.processedMonth')}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{totalProcessed}</div>
            <p className="text-xs text-muted-foreground mt-1">
              {t('perf.casesProcessed')}
            </p>
          </CardContent>
        </Card>

        {/* Approved */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-green-500" />
              {t('perf.approved')}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              <div className="text-2xl font-bold text-green-600">
                {performance.current_month_approved}
              </div>
              <Progress value={approvalRate} className="h-2 bg-gray-200" />
              <p className="text-xs text-muted-foreground">
                {t('perf.ofTotal', { rate: approvalRate.toFixed(1) })}
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Rejected */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <XCircle className="h-4 w-4 text-red-500" />
              {t('perf.rejected')}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              <div className="text-2xl font-bold text-red-600">
                {performance.current_month_rejected}
              </div>
              <Progress value={rejectionRate} className="h-2 bg-gray-200" />
              <p className="text-xs text-muted-foreground">
                {t('perf.ofTotal', { rate: rejectionRate.toFixed(1) })}
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Escalated */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-orange-500" />
              {t('perf.escalated')}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              <div className="text-2xl font-bold text-orange-600">
                {performance.current_month_escalated}
              </div>
              <Progress value={escalationRate} className="h-2 bg-gray-200" />
              <p className="text-xs text-muted-foreground">
                {t('perf.ofTotal', { rate: escalationRate.toFixed(1) })}
              </p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* SLA & Processing Times */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {/* SLA Compliance */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">{t('perf.slaCompliance')}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-2xl font-bold">{slaRate.toFixed(1)}%</span>
                <span className={`text-sm ${slaRate >= 90 ? 'text-green-600' : slaRate >= 70 ? 'text-yellow-600' : 'text-red-600'}`}>
                  {getSlaLabel(slaRate)}
                </span>
              </div>
              <Progress
                value={slaRate}
                className={`h-3 ${slaRate >= 90 ? 'bg-green-200' : slaRate >= 70 ? 'bg-yellow-200' : 'bg-red-200'}`}
              />
              <div className="flex justify-between text-xs text-muted-foreground">
                <span className="text-green-600">
                  {t('perf.slaRespected', { count: performance.sla_respected_count })}
                </span>
                <span className="text-red-600">
                  {t('perf.slaMissed', { count: performance.sla_missed_count })}
                </span>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Processing Time */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Clock className="h-4 w-4 text-muted-foreground" />
              {t('perf.avgTimes')}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-sm text-muted-foreground">{t('perf.processing')}</span>
                <span className="font-medium">
                  {formatMinutes(performance.avg_processing_minutes)}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-muted-foreground">{t('perf.locking')}</span>
                <span className="font-medium">
                  {formatMinutes(performance.avg_lock_duration_minutes)}
                </span>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Lock Stats */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Lock className="h-4 w-4 text-muted-foreground" />
              {t('perf.locks')}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-sm text-muted-foreground">{t('perf.activeLocks')}</span>
                <span className="font-medium">{performance.current_active_locks}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-muted-foreground">{t('perf.maxConcurrent')}</span>
                <span className="font-medium">{performance.max_concurrent_locks}</span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Activity Times */}
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">{t('perf.lastActivity')}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm">{formatDate(performance.last_action_at)}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">{t('perf.lastLogin')}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm">{formatDate(performance.last_login_at)}</p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

export default PerformanceStats;
