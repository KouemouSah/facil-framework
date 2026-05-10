/**
 * Agent Personal Statistics Page
 * Displays performance metrics for the current agent
 *
 * Backend: GET /api/v1/statistics/agent/{agent_profile_id}
 * @date 2026-01-25
 */

'use client';

import { useState } from 'react';
import { useTranslations } from 'next-intl';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Loader2,
  AlertCircle,
  RefreshCw,
  TrendingUp,
  CheckCircle,
  Clock,
  Target,
  BarChart3,
  FileText,
  XCircle,
  AlertTriangle,
} from 'lucide-react';
import { useAgentPersonalStats } from '@/modules/agent-dashboard/hooks';

type PeriodDays = 7 | 30 | 90;

export default function AgentStatsPage() {
  const t = useTranslations();
  const [periodDays, setPeriodDays] = useState<PeriodDays>(30);

  const { stats, isLoading, isError, refetch, hasProfile } = useAgentPersonalStats(periodDays);

  const formatNumber = (num: number) => {
    return new Intl.NumberFormat('es-GQ').format(num);
  };

  const formatPercent = (rate: number) => {
    return `${(rate * 100).toFixed(1)}%`;
  };

  const formatHours = (hours: number) => {
    if (hours < 1) {
      return `${Math.round(hours * 60)} min`;
    }
    return `${hours.toFixed(1)}h`;
  };

  const getPerformanceBadge = (rate: number) => {
    if (rate >= 0.95) return { label: t('agent.stats.excellent'), variant: 'default' as const };
    if (rate >= 0.85) return { label: t('agent.stats.good'), variant: 'secondary' as const };
    if (rate >= 0.7) return { label: t('agent.stats.average'), variant: 'outline' as const };
    return { label: t('agent.stats.needsImprovement'), variant: 'destructive' as const };
  };

  // No profile available
  if (!hasProfile && !isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Card className="max-w-md">
          <CardContent className="flex flex-col items-center gap-4 py-8">
            <AlertTriangle className="h-12 w-12 text-yellow-500" />
            <p className="text-center text-muted-foreground">
              {t('agent.stats.noProfile')}
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
            <BarChart3 className="h-8 w-8" />
            {t('agent.stats.title')}
          </h1>
          <p className="text-muted-foreground mt-1">
            {t('agent.stats.description')}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Select
            value={periodDays.toString()}
            onValueChange={(v) => setPeriodDays(parseInt(v) as PeriodDays)}
          >
            <SelectTrigger className="w-40">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="7">{t('agent.stats.periods.week')}</SelectItem>
              <SelectItem value="30">{t('agent.stats.periods.month')}</SelectItem>
              <SelectItem value="90">{t('agent.stats.periods.quarter')}</SelectItem>
            </SelectContent>
          </Select>
          <Button onClick={() => refetch()} variant="outline" disabled={isLoading}>
            <RefreshCw className={`mr-2 h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
            {t('common.refresh')}
          </Button>
        </div>
      </div>

      {/* Error State */}
      {isError && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="flex items-center gap-3 py-4">
            <AlertCircle className="h-5 w-5 text-red-500" />
            <p className="text-red-700">{t('agent.stats.loadError')}</p>
          </CardContent>
        </Card>
      )}

      {/* Loading State */}
      {isLoading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      )}

      {/* Stats Content */}
      {stats && (
        <>
          {/* KPI Cards */}
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            {/* Total Processed */}
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">{t('agent.stats.totalProcessed')}</p>
                    <p className="text-2xl font-bold">{formatNumber(stats.completedAssignments + stats.rejectedAssignments)}</p>
                    <p className="text-sm text-muted-foreground">
                      {t('agent.stats.ofTotalAssignments', { total: stats.totalAssignments })}
                    </p>
                  </div>
                  <div className="p-3 bg-blue-100 rounded-full">
                    <FileText className="h-6 w-6 text-blue-600" />
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Success Rate */}
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">{t('agent.stats.successRate')}</p>
                    <p className="text-2xl font-bold">{formatPercent(stats.successRate)}</p>
                    <Badge variant={getPerformanceBadge(stats.successRate).variant}>
                      {getPerformanceBadge(stats.successRate).label}
                    </Badge>
                  </div>
                  <div className="p-3 bg-green-100 rounded-full">
                    <CheckCircle className="h-6 w-6 text-green-600" />
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Average Time */}
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">{t('agent.stats.avgTime')}</p>
                    <p className="text-2xl font-bold">{formatHours(stats.avgProcessingTimeHours)}</p>
                    <p className="text-sm text-muted-foreground">
                      {t('agent.stats.perRequest')}
                    </p>
                  </div>
                  <div className="p-3 bg-yellow-100 rounded-full">
                    <Clock className="h-6 w-6 text-yellow-600" />
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* SLA Compliance */}
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">{t('agent.stats.slaCompliance')}</p>
                    <p className="text-2xl font-bold">{formatPercent(stats.deadlineComplianceRate)}</p>
                    <Badge variant={getPerformanceBadge(stats.deadlineComplianceRate).variant}>
                      {getPerformanceBadge(stats.deadlineComplianceRate).label}
                    </Badge>
                  </div>
                  <div className="p-3 bg-purple-100 rounded-full">
                    <Target className="h-6 w-6 text-purple-600" />
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Detailed Stats */}
          <div className="grid gap-6 lg:grid-cols-2">
            {/* Status Breakdown */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <TrendingUp className="h-5 w-5" />
                  {t('agent.stats.statusBreakdown')}
                </CardTitle>
                <CardDescription>
                  {t('agent.stats.statusBreakdownDesc', { days: periodDays })}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Completed */}
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="flex items-center gap-2">
                      <CheckCircle className="h-4 w-4 text-green-500" />
                      {t('agent.stats.statusCompleted')}
                    </span>
                    <span className="font-medium">{stats.completedAssignments}</span>
                  </div>
                  <Progress
                    value={stats.totalAssignments > 0 ? (stats.completedAssignments / stats.totalAssignments) * 100 : 0}
                    className="h-2"
                  />
                </div>

                {/* Pending */}
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="flex items-center gap-2">
                      <Clock className="h-4 w-4 text-yellow-500" />
                      {t('agent.stats.statusPending')}
                    </span>
                    <span className="font-medium">{stats.pendingAssignments}</span>
                  </div>
                  <Progress
                    value={stats.totalAssignments > 0 ? (stats.pendingAssignments / stats.totalAssignments) * 100 : 0}
                    className="h-2"
                  />
                </div>

                {/* Rejected */}
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="flex items-center gap-2">
                      <XCircle className="h-4 w-4 text-red-500" />
                      {t('agent.stats.statusRejected')}
                    </span>
                    <span className="font-medium">{stats.rejectedAssignments}</span>
                  </div>
                  <Progress
                    value={stats.totalAssignments > 0 ? (stats.rejectedAssignments / stats.totalAssignments) * 100 : 0}
                    className="h-2"
                  />
                </div>
              </CardContent>
            </Card>

            {/* Quality Score */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Target className="h-5 w-5" />
                  {t('agent.stats.qualityScore')}
                </CardTitle>
                <CardDescription>
                  {t('agent.stats.qualityScoreDesc')}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex flex-col items-center justify-center py-6">
                  <div className="relative w-32 h-32">
                    <svg className="w-full h-full transform -rotate-90">
                      <circle
                        cx="64"
                        cy="64"
                        r="56"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="12"
                        className="text-muted"
                      />
                      <circle
                        cx="64"
                        cy="64"
                        r="56"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="12"
                        strokeDasharray={`${(stats.qualityScoreAvg / 10) * 352} 352`}
                        className="text-primary"
                        strokeLinecap="round"
                      />
                    </svg>
                    <div className="absolute inset-0 flex items-center justify-center">
                      <span className="text-3xl font-bold">{stats.qualityScoreAvg.toFixed(1)}</span>
                    </div>
                  </div>
                  <p className="mt-4 text-sm text-muted-foreground">
                    {t('agent.stats.outOf10')}
                  </p>
                  <Badge variant={getPerformanceBadge(stats.qualityScoreAvg / 10).variant} className="mt-2">
                    {getPerformanceBadge(stats.qualityScoreAvg / 10).label}
                  </Badge>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Type Breakdown (if available) */}
          {Object.keys(stats.byType).length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>{t('agent.stats.typeBreakdown')}</CardTitle>
                <CardDescription>
                  {t('agent.stats.typeBreakdownDesc')}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  {Object.entries(stats.byType).map(([type, count]) => (
                    <div key={type} className="flex items-center justify-between p-3 bg-muted rounded-lg">
                      <span className="text-sm font-medium capitalize">
                        {type.replace(/_/g, ' ')}
                      </span>
                      <Badge variant="secondary">
                        {count} {t('agent.stats.totalLabel')}
                      </Badge>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
