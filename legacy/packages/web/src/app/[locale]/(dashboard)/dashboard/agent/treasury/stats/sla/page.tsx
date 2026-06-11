/**
 * Treasury SLA Stats Page (Phase 1B)
 * Displays SLA performance metrics and statistics
 */

'use client';

import { useMemo } from 'react';
import { useTranslations } from 'next-intl';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Loader2,
  AlertCircle,
  RefreshCw,
  Clock,
  CheckCircle,
  AlertTriangle,
  XCircle,
  Timer,
  TrendingUp,
  BarChart3,
} from 'lucide-react';
import { useSLAStats } from '@/modules/treasury/hooks';
import { SLABadge } from '@/modules/treasury/components';
import { StatsTabNav } from '../_components/StatsTabNav';

// SLA threshold configuration
const SLA_THRESHOLDS = {
  onTime: { min: 90, color: 'text-green-600' },
  warning: { min: 75, color: 'text-yellow-600' },
  critical: { min: 50, color: 'text-orange-600' },
  breached: { min: 0, color: 'text-red-600' },
};

function getPerformanceLevelKey(rate: number): { key: string; color: string } {
  if (rate >= SLA_THRESHOLDS.onTime.min) return { key: 'excellent', color: 'text-green-600' };
  if (rate >= SLA_THRESHOLDS.warning.min) return { key: 'good', color: 'text-yellow-600' };
  if (rate >= SLA_THRESHOLDS.critical.min) return { key: 'improvable', color: 'text-orange-600' };
  return { key: 'critical', color: 'text-red-600' };
}

export default function TreasurySLAStatsPage() {
  const t = useTranslations('treasury');

  // Data fetching
  const { data: slaStats, isLoading, error, refetch } = useSLAStats();

  // Calculate percentages for the pie chart display
  const percentages = useMemo(() => {
    if (!slaStats || slaStats.totalPending === 0) {
      return { onTime: 0, warning: 0, critical: 0, breached: 0 };
    }
    const total = slaStats.totalPending;
    return {
      onTime: Math.round((slaStats.onTime / total) * 100),
      warning: Math.round((slaStats.warning / total) * 100),
      critical: Math.round((slaStats.critical / total) * 100),
      breached: Math.round((slaStats.breached / total) * 100),
    };
  }, [slaStats]);

  const performanceLevelInfo = useMemo(() => {
    return getPerformanceLevelKey(slaStats?.slaRespectRate || 100);
  }, [slaStats?.slaRespectRate]);

  const formatMinutes = (minutes?: number) => {
    if (!minutes) return '-';
    if (minutes < 60) return `${Math.round(minutes)} ${t('slaPage.units.min')}`;
    const hours = Math.floor(minutes / 60);
    const mins = Math.round(minutes % 60);
    return `${hours}${t('slaPage.units.h')} ${mins}${t('slaPage.units.m')}`;
  };

  return (
    <div className="space-y-6">
      <StatsTabNav />
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
            <BarChart3 className="h-8 w-8" />
            {t('sla.title')}
          </h1>
          <p className="text-muted-foreground mt-1">
            {t('sla.description')}
          </p>
        </div>
        <Button onClick={() => refetch()} disabled={isLoading}>
          <RefreshCw className={`mr-2 h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
          {t('common.refresh')}
        </Button>
      </div>

      {/* Error State */}
      {error && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="flex items-center gap-3 py-4">
            <AlertCircle className="h-5 w-5 text-red-500" />
            <p className="text-red-700">{t('slaPage.loadError')}</p>
          </CardContent>
        </Card>
      )}

      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : slaStats ? (
        <>
          {/* KPI Cards */}
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            {/* Tasa de cumplimiento */}
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">{t('sla.complianceRate')}</CardTitle>
                <TrendingUp className={`h-4 w-4 ${performanceLevelInfo.color}`} />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{slaStats.slaRespectRate.toFixed(1)}%</div>
                <p className={`text-xs ${performanceLevelInfo.color}`}>
                  {t(`slaPage.performanceLevel.${performanceLevelInfo.key}`)}
                </p>
                <Progress value={slaStats.slaRespectRate} className="mt-2" />
              </CardContent>
            </Card>

            {/* Total Pendientes */}
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">{t('sla.totalPending')}</CardTitle>
                <Clock className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{slaStats.totalPending}</div>
                <p className="text-xs text-muted-foreground">
                  {t('slaPage.paymentsInProcess')}
                </p>
              </CardContent>
            </Card>

            {/* Tiempo Promedio */}
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">{t('sla.avgProcessingTime')}</CardTitle>
                <Timer className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {formatMinutes(slaStats.avgProcessingMinutes)}
                </div>
                <p className="text-xs text-muted-foreground">
                  {t('slaPage.processingTime')}
                </p>
              </CardContent>
            </Card>

            {/* Vencidos */}
            <Card className={slaStats.breached > 0 ? 'border-red-200' : ''}>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">{t('sla.breached')}</CardTitle>
                <XCircle className={`h-4 w-4 ${slaStats.breached > 0 ? 'text-red-500' : 'text-muted-foreground'}`} />
              </CardHeader>
              <CardContent>
                <div className={`text-2xl font-bold ${slaStats.breached > 0 ? 'text-red-600' : ''}`}>
                  {slaStats.breached}
                </div>
                <p className="text-xs text-muted-foreground">
                  {t('slaPage.requireImmediate')}
                </p>
              </CardContent>
            </Card>
          </div>

          {/* SLA Distribution */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BarChart3 className="h-5 w-5" />
                {t('slaPage.distribution.title')}
              </CardTitle>
              <CardDescription>
                {t('slaPage.distribution.description')}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid gap-6 md:grid-cols-2">
                {/* Visual bars */}
                <div className="space-y-4">
                  {/* On Time */}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <CheckCircle className="h-4 w-4 text-green-600" />
                        <span className="text-sm font-medium">{t('sla.status.on_time')}</span>
                      </div>
                      <span className="text-sm text-muted-foreground">
                        {slaStats.onTime} ({percentages.onTime}%)
                      </span>
                    </div>
                    <Progress value={percentages.onTime} className="h-2 bg-green-100" />
                  </div>

                  {/* Warning */}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Clock className="h-4 w-4 text-yellow-600" />
                        <span className="text-sm font-medium">{t('sla.status.warning')}</span>
                      </div>
                      <span className="text-sm text-muted-foreground">
                        {slaStats.warning} ({percentages.warning}%)
                      </span>
                    </div>
                    <Progress value={percentages.warning} className="h-2 bg-yellow-100" />
                  </div>

                  {/* Critical */}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <AlertTriangle className="h-4 w-4 text-orange-600" />
                        <span className="text-sm font-medium">{t('sla.status.critical')}</span>
                      </div>
                      <span className="text-sm text-muted-foreground">
                        {slaStats.critical} ({percentages.critical}%)
                      </span>
                    </div>
                    <Progress value={percentages.critical} className="h-2 bg-orange-100" />
                  </div>

                  {/* Breached */}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <XCircle className="h-4 w-4 text-red-600" />
                        <span className="text-sm font-medium">{t('sla.status.breached')}</span>
                      </div>
                      <span className="text-sm text-muted-foreground">
                        {slaStats.breached} ({percentages.breached}%)
                      </span>
                    </div>
                    <Progress value={percentages.breached} className="h-2 bg-red-100" />
                  </div>
                </div>

                {/* Legend / Summary */}
                <div className="flex flex-col justify-center space-y-3 p-4 bg-muted/50 rounded-lg">
                  <h4 className="font-medium">{t('sla.thresholds.title')}</h4>
                  <div className="space-y-2 text-sm">
                    <div className="flex items-center gap-2">
                      <SLABadge status="on_time" showCountdown={false} />
                      <span className="text-muted-foreground">{t('sla.thresholds.onTime')}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <SLABadge status="warning" showCountdown={false} />
                      <span className="text-muted-foreground">{t('sla.thresholds.warning')}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <SLABadge status="critical" showCountdown={false} />
                      <span className="text-muted-foreground">{t('sla.thresholds.critical')}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <SLABadge status="breached" showCountdown={false} />
                      <span className="text-muted-foreground">{t('sla.thresholds.breached')}</span>
                    </div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* By Payment Method */}
          {slaStats.byPaymentMethod && Object.keys(slaStats.byPaymentMethod).length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Timer className="h-5 w-5" />
                  {t('slaPage.byPaymentMethod.title')}
                </CardTitle>
                <CardDescription>
                  {t('slaPage.byPaymentMethod.description')}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>{t('slaPage.byPaymentMethod.method')}</TableHead>
                        <TableHead className="text-center">{t('slaPage.byPaymentMethod.total')}</TableHead>
                        <TableHead className="text-center">
                          <span className="text-green-600">{t('sla.status.on_time')}</span>
                        </TableHead>
                        <TableHead className="text-center">
                          <span className="text-yellow-600">{t('sla.status.warning')}</span>
                        </TableHead>
                        <TableHead className="text-center">
                          <span className="text-orange-600">{t('sla.status.critical')}</span>
                        </TableHead>
                        <TableHead className="text-center">
                          <span className="text-red-600">{t('sla.status.breached')}</span>
                        </TableHead>
                        <TableHead className="text-center">{t('slaPage.byPaymentMethod.compliance')}</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {Object.entries(slaStats.byPaymentMethod).map(([method, stats]) => {
                        const total = stats.total || 0;
                        const rate = total > 0 ? ((stats.onTime / total) * 100) : 100;
                        const level = getPerformanceLevelKey(rate);
                        return (
                          <TableRow key={method}>
                            <TableCell className="font-medium">
                              {t(`methodLabels.${method}` as Parameters<typeof t>[0])}
                            </TableCell>
                            <TableCell className="text-center">
                              <Badge variant="secondary">{total}</Badge>
                            </TableCell>
                            <TableCell className="text-center text-green-600 font-medium">
                              {stats.onTime}
                            </TableCell>
                            <TableCell className="text-center text-yellow-600 font-medium">
                              {stats.warning}
                            </TableCell>
                            <TableCell className="text-center text-orange-600 font-medium">
                              {stats.critical}
                            </TableCell>
                            <TableCell className="text-center text-red-600 font-medium">
                              {stats.breached}
                            </TableCell>
                            <TableCell className="text-center">
                              <span className={`font-bold ${level.color}`}>
                                {rate.toFixed(1)}%
                              </span>
                            </TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                </div>
              </CardContent>
            </Card>
          )}
        </>
      ) : null}
    </div>
  );
}
