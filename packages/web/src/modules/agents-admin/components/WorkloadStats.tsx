'use client';

/**
 * Workload Stats Component
 * Displays agent workload statistics
 *
 * @module agents-admin/components
 */

import { useTranslations } from 'next-intl';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import {
  Activity,
  Clock,
  CheckCircle2,
  AlertTriangle,
  TrendingUp,
  Calendar,
} from 'lucide-react';
import type { AgentWorkload } from '../types';

interface WorkloadStatsProps {
  workload: AgentWorkload;
  className?: string;
}

export function WorkloadStats({ workload, className }: WorkloadStatsProps) {
  const t = useTranslations('admin.agents');

  const getCapacityColor = (percentage: number) => {
    if (percentage < 50) return 'bg-green-500';
    if (percentage < 80) return 'bg-yellow-500';
    return 'bg-red-500';
  };

  const getAvailabilityBadge = (availability: string) => {
    const config: Record<string, { label: string; variant: 'default' | 'secondary' | 'destructive' | 'outline' }> = {
      available: { label: t('availability.available'), variant: 'default' },
      on_leave: { label: t('availability.onLeave'), variant: 'secondary' },
      sick_leave: { label: t('availability.sickLeave'), variant: 'destructive' },
      training: { label: t('availability.training'), variant: 'outline' },
      mission: { label: t('availability.mission'), variant: 'outline' },
      temporarily_unavailable: { label: t('availability.temporarilyUnavailable'), variant: 'secondary' },
    };
    const c = config[availability] || { label: availability, variant: 'outline' as const };
    return <Badge variant={c.variant}>{c.label}</Badge>;
  };

  const formatDuration = (hours?: number) => {
    if (!hours) return '-';
    if (hours < 1) return `${Math.round(hours * 60)} min`;
    return `${hours.toFixed(1)}h`;
  };

  return (
    <div className={`grid gap-4 md:grid-cols-2 lg:grid-cols-3 ${className}`}>
      {/* Capacity */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <Activity className="h-4 w-4 text-muted-foreground" />
            {t('wkld.capacity')}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span>{workload.current_assignments} / {workload.max_concurrent_assignments}</span>
              <span className="font-medium">{workload.capacity_percentage}%</span>
            </div>
            <Progress
              value={workload.capacity_percentage}
              className={`h-2 ${getCapacityColor(workload.capacity_percentage)}`}
            />
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span>{t('wkld.pending', { count: workload.pending_declarations })}</span>
              <span>{t('wkld.inProgress', { count: workload.in_progress_declarations })}</span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Availability */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <Calendar className="h-4 w-4 text-muted-foreground" />
            {t('wkld.availability')}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              {getAvailabilityBadge(workload.availability as string)}
            </div>
            {workload.availability_reason && (
              <p className="text-xs text-muted-foreground">
                {workload.availability_reason}
              </p>
            )}
            {workload.unavailable_until && (
              <p className="text-xs text-muted-foreground">
                {t('wkld.untilDate', { date: new Date(workload.unavailable_until).toLocaleDateString() })}
              </p>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Processing Time */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <Clock className="h-4 w-4 text-muted-foreground" />
            {t('wkld.processingTime')}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            <div className="text-2xl font-bold">
              {formatDuration(workload.avg_processing_time_hours)}
            </div>
            <p className="text-xs text-muted-foreground">
              {t('wkld.avgPerCase')}
            </p>
            {workload.avg_pending_duration_hours && (
              <p className="text-xs text-muted-foreground">
                {t('wkld.avgWait', { duration: formatDuration(workload.avg_pending_duration_hours) })}
              </p>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Completion Rate */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-muted-foreground" />
            {t('wkld.completionRate')}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            <div className="text-2xl font-bold">
              {(workload.completion_rate_7d * 100).toFixed(0)}%
            </div>
            <p className="text-xs text-muted-foreground">
              {t('wkld.last7Days')}
            </p>
            <div className="text-sm">
              {t('wkld.avgPerDay', { count: workload.avg_daily_completions.toFixed(1) })}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Quality Score */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
            {t('wkld.quality')}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            <div className="text-2xl font-bold">
              {workload.quality_score_avg.toFixed(1)}/10
            </div>
            <Progress value={workload.quality_score_avg * 10} className="h-2" />
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>{t('wkld.successRate', { rate: (workload.success_rate * 100).toFixed(0) })}</span>
              <span>{t('wkld.deadlineRate', { rate: (workload.deadline_compliance_rate * 100).toFixed(0) })}</span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Oldest Pending */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-muted-foreground" />
            {t('wkld.oldestPending')}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {workload.oldest_pending_assignment_date ? (
              <>
                <div className="text-lg font-medium">
                  {new Date(workload.oldest_pending_assignment_date).toLocaleDateString()}
                </div>
                <p className="text-xs text-muted-foreground">
                  {t('wkld.daysAgo', {
                    count: Math.floor(
                      (Date.now() - new Date(workload.oldest_pending_assignment_date).getTime()) /
                        (1000 * 60 * 60 * 24)
                    ),
                  })}
                </p>
              </>
            ) : (
              <div className="text-sm text-muted-foreground">
                {t('wkld.noPending')}
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export default WorkloadStats;
