/**
 * Treasury Analytics Dashboard (Phase 5)
 * Statistical analysis with 2 tabs:
 * - Report: Fixed variables, automatic analysis with findings
 * - Explore: Custom variable selection via dropdowns
 */

'use client';

import { useState, useMemo } from 'react';
import { useLocale, useTranslations } from 'next-intl';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Input } from '@/components/ui/input';
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
  TrendingUp,
  TrendingDown,
  Minus,
  BarChart3,
  FileText,
  Search,
  AlertTriangle,
  CheckCircle,
  Info,
  Activity,
  Target,
  ArrowRight,
  Calendar,
} from 'lucide-react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js';
import { Line } from 'react-chartjs-2';
import {
  useAnalyticsReport,
  useExploreAnalytics,
} from '@/modules/treasury/hooks';
import {
  ANALYTICS_VARIABLES,
  getCorrelationBadgeVariant,
  getTrendBadgeVariant,
  getFindingBadgeVariant,
  getHealthStatusColor,
  formatVariableName,
} from '@/modules/treasury/types/analytics';
import type {
  FindingSeverity,
  TrendDirection,
} from '@/modules/treasury/types/analytics';

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

type Period = 'week' | 'month' | 'year' | 'prev_week' | 'prev_month' | 'quarter' | 'prev_quarter' | 'custom';

/** Compute dateFrom/dateTo for each preset period */
function getDateRange(period: Period, customFrom?: string, customTo?: string): { dateFrom?: string; dateTo?: string; backendPeriod: string } {
  if (period === 'custom') {
    return { dateFrom: customFrom, dateTo: customTo, backendPeriod: 'month' };
  }

  const now = new Date();
  const fmt = (d: Date) => d.toISOString().split('T')[0];

  switch (period) {
    case 'week':
      return { backendPeriod: 'week' };
    case 'month':
      return { backendPeriod: 'month' };
    case 'year':
      return { backendPeriod: 'year' };
    case 'prev_week': {
      const end = new Date(now);
      end.setDate(end.getDate() - end.getDay()); // Start of current week (Sunday)
      const start = new Date(end);
      start.setDate(start.getDate() - 7);
      return { dateFrom: fmt(start), dateTo: fmt(end), backendPeriod: 'week' };
    }
    case 'prev_month': {
      const start = new Date(now.getFullYear(), now.getMonth() - 1, 1);
      const end = new Date(now.getFullYear(), now.getMonth(), 0); // Last day of prev month
      return { dateFrom: fmt(start), dateTo: fmt(end), backendPeriod: 'month' };
    }
    case 'quarter': {
      const qStart = new Date(now.getFullYear(), Math.floor(now.getMonth() / 3) * 3, 1);
      return { dateFrom: fmt(qStart), dateTo: fmt(now), backendPeriod: 'month' };
    }
    case 'prev_quarter': {
      const curQStart = Math.floor(now.getMonth() / 3) * 3;
      const start = new Date(now.getFullYear(), curQStart - 3, 1);
      const end = new Date(now.getFullYear(), curQStart, 0); // Last day of prev quarter
      return { dateFrom: fmt(start), dateTo: fmt(end), backendPeriod: 'month' };
    }
    default:
      return { backendPeriod: 'month' };
  }
}

export default function TreasuryAnalyticsPage() {
  const t = useTranslations('treasury');
  const locale = useLocale();

  const [period, setPeriod] = useState<Period>('month');
  const [customFrom, setCustomFrom] = useState('');
  const [customTo, setCustomTo] = useState('');
  const [activeTab, setActiveTab] = useState('report');

  // Explore tab state
  const [primaryVariable, setPrimaryVariable] = useState('total_amount');
  const [secondaryVariable, setSecondaryVariable] = useState<string | undefined>();

  // Compute date range from period selection
  const { dateFrom, dateTo, backendPeriod } = useMemo(
    () => getDateRange(period, customFrom, customTo),
    [period, customFrom, customTo]
  );

  // For custom period, only fetch when both dates are set
  const isCustomReady = period !== 'custom' || (!!customFrom && !!customTo);

  // Report data
  const {
    data: reportData,
    isLoading: reportLoading,
    error: reportError,
    refetch: refetchReport,
  } = useAnalyticsReport({
    period: backendPeriod,
    dateFrom,
    dateTo,
    language: locale,
  });

  // Explore data
  const {
    data: exploreData,
    isLoading: exploreLoading,
    error: exploreError,
    refetch: refetchExplore,
  } = useExploreAnalytics(
    {
      primaryVariable,
      secondaryVariable,
      period: backendPeriod,
      dateFrom,
      dateTo,
    },
    { enabled: activeTab === 'explore' && !!primaryVariable && isCustomReady }
  );

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat(locale, {
      style: 'currency',
      currency: 'XAF',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(amount);
  };

  const formatNumber = (num: number, decimals = 2) => {
    return new Intl.NumberFormat(locale, {
      minimumFractionDigits: 0,
      maximumFractionDigits: decimals,
    }).format(num);
  };

  const formatPercent = (num: number) => {
    return `${num >= 0 ? '+' : ''}${num.toFixed(1)}%`;
  };

  const getTrendIcon = (direction: TrendDirection) => {
    switch (direction) {
      case 'growing':
        return <TrendingUp className="h-4 w-4 text-green-500" />;
      case 'declining':
        return <TrendingDown className="h-4 w-4 text-red-500" />;
      default:
        return <Minus className="h-4 w-4 text-gray-400" />;
    }
  };

  const getSeverityIcon = (severity: FindingSeverity) => {
    switch (severity) {
      case 'critical':
        return <AlertCircle className="h-4 w-4 text-red-500" />;
      case 'warning':
        return <AlertTriangle className="h-4 w-4 text-yellow-500" />;
      default:
        return <Info className="h-4 w-4 text-blue-500" />;
    }
  };

  const getVariableLabel = (value: string) => {
    return formatVariableName(value, locale);
  };

  // Prepare chart data for predictions
  const predictionsChartData = reportData?.predictions.length ? {
    labels: reportData.predictions.map((p) => {
      const date = new Date(p.date);
      return `${date.getDate()}/${date.getMonth() + 1}`;
    }),
    datasets: [
      {
        label: t('analytics.predictions'),
        data: reportData.predictions.map((p) => p.predictedValue),
        borderColor: '#8b5cf6',
        backgroundColor: 'rgba(139, 92, 246, 0.1)',
        fill: true,
        tension: 0.4,
      },
      {
        label: t('analytics.upperBound'),
        data: reportData.predictions.map((p) => p.upperBound),
        borderColor: 'rgba(139, 92, 246, 0.3)',
        borderDash: [5, 5],
        fill: false,
        tension: 0.4,
        pointRadius: 0,
      },
      {
        label: t('analytics.lowerBound'),
        data: reportData.predictions.map((p) => p.lowerBound),
        borderColor: 'rgba(139, 92, 246, 0.3)',
        borderDash: [5, 5],
        fill: false,
        tension: 0.4,
        pointRadius: 0,
      },
    ],
  } : null;

  const lineChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: true,
        position: 'top' as const,
      },
    },
    scales: {
      y: {
        beginAtZero: false,
        ticks: {
          callback: function(value: string | number) {
            if (typeof value === 'number') {
              return value >= 1000000 ? `${(value / 1000000).toFixed(1)}M` : formatNumber(value);
            }
            return value;
          },
        },
      },
    },
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
            <Activity className="h-8 w-8" />
            {t('analytics.title')}
          </h1>
          <p className="text-muted-foreground mt-1">
            {t('analytics.description')}
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap justify-end">
          <Select value={period} onValueChange={(v) => setPeriod(v as Period)}>
            <SelectTrigger className="w-48">
              <Calendar className="h-4 w-4 mr-2" />
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                <SelectLabel>{t('analytics.periods.week')}</SelectLabel>
                <SelectItem value="week">{t('analytics.periods.week')}</SelectItem>
                <SelectItem value="prev_week">{t('analytics.periods.prev_week')}</SelectItem>
              </SelectGroup>
              <SelectGroup>
                <SelectLabel>{t('analytics.periods.month')}</SelectLabel>
                <SelectItem value="month">{t('analytics.periods.month')}</SelectItem>
                <SelectItem value="prev_month">{t('analytics.periods.prev_month')}</SelectItem>
              </SelectGroup>
              <SelectGroup>
                <SelectLabel>{t('analytics.periods.quarter')}</SelectLabel>
                <SelectItem value="quarter">{t('analytics.periods.quarter')}</SelectItem>
                <SelectItem value="prev_quarter">{t('analytics.periods.prev_quarter')}</SelectItem>
              </SelectGroup>
              <SelectItem value="year">{t('analytics.periods.year')}</SelectItem>
              <SelectItem value="custom">{t('analytics.periods.custom')}</SelectItem>
            </SelectContent>
          </Select>
          {period === 'custom' && (
            <>
              <Input
                type="date"
                value={customFrom}
                onChange={(e) => setCustomFrom(e.target.value)}
                className="w-36"
                aria-label={t('analytics.dateFrom')}
              />
              <span className="text-sm text-muted-foreground">—</span>
              <Input
                type="date"
                value={customTo}
                onChange={(e) => setCustomTo(e.target.value)}
                className="w-36"
                aria-label={t('analytics.dateTo')}
              />
            </>
          )}
          <Button
            onClick={() => activeTab === 'report' ? refetchReport() : refetchExplore()}
            variant="outline"
            disabled={reportLoading || exploreLoading}
          >
            <RefreshCw className={`mr-2 h-4 w-4 ${(reportLoading || exploreLoading) ? 'animate-spin' : ''}`} />
            {t('common.refresh')}
          </Button>
        </div>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full max-w-md grid-cols-2">
          <TabsTrigger value="report" className="flex items-center gap-2">
            <FileText className="h-4 w-4" />
            {t('analytics.tabs.report')}
          </TabsTrigger>
          <TabsTrigger value="explore" className="flex items-center gap-2">
            <Search className="h-4 w-4" />
            {t('analytics.tabs.explore')}
          </TabsTrigger>
        </TabsList>

        {/* ============================================= */}
        {/* REPORT TAB - Fixed Variables */}
        {/* ============================================= */}
        <TabsContent value="report" className="space-y-6">
          {/* Error State */}
          {reportError && (
            <Card className="border-red-200 bg-red-50">
              <CardContent className="flex items-center gap-3 py-4">
                <AlertCircle className="h-5 w-5 text-red-500" />
                <p className="text-red-700">{t('analytics.loadError')}</p>
              </CardContent>
            </Card>
          )}

          {/* Loading State */}
          {reportLoading && (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          )}

          {reportData && (
            <>
              {/* Health Score Card */}
              <Card className="border-2">
                <CardHeader>
                  <CardTitle className="flex items-center justify-between">
                    <span className="flex items-center gap-2">
                      <Target className="h-5 w-5" />
                      {t('analytics.healthScore')}
                    </span>
                    <div className="flex items-center gap-2">
                      <span className={`text-4xl font-bold ${getHealthStatusColor(reportData.healthStatus as 'good' | 'warning' | 'critical')}`}>
                        {reportData.healthScore}
                      </span>
                      <span className="text-lg text-muted-foreground">/100</span>
                    </div>
                  </CardTitle>
                  <CardDescription>
                    {t('analytics.healthScoreDescription')}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="text-center">
                      <p className="text-2xl font-bold">{formatNumber(reportData.totalRecords)}</p>
                      <p className="text-sm text-muted-foreground">{t('analytics.totalRecords')}</p>
                    </div>
                    <div className="text-center">
                      <p className="text-2xl font-bold">{formatCurrency(reportData.totalAmount)}</p>
                      <p className="text-sm text-muted-foreground">{t('analytics.totalAmount')}</p>
                    </div>
                    <div className="text-center">
                      <p className="text-2xl font-bold text-red-600">{reportData.alertsCount}</p>
                      <p className="text-sm text-muted-foreground">{t('analytics.alerts')}</p>
                    </div>
                    <div className="text-center">
                      <p className="text-2xl font-bold text-yellow-600">{reportData.warningsCount}</p>
                      <p className="text-sm text-muted-foreground">{t('analytics.warnings')}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Findings */}
              {reportData.findings.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <AlertTriangle className="h-5 w-5" />
                      {t('analytics.findings')}
                    </CardTitle>
                    <CardDescription>
                      {t('analytics.findingsDescription')}
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-4">
                      {reportData.findings.map((finding, idx) => (
                        <div
                          key={idx}
                          className={`p-4 rounded-lg border ${
                            finding.severity === 'critical'
                              ? 'border-red-200 bg-red-50'
                              : finding.severity === 'warning'
                              ? 'border-yellow-200 bg-yellow-50'
                              : 'border-blue-200 bg-blue-50'
                          }`}
                        >
                          <div className="flex items-start gap-3">
                            {getSeverityIcon(finding.severity)}
                            <div className="flex-1">
                              <div className="flex items-center gap-2 mb-1">
                                <span className="font-medium">{finding.title}</span>
                                <Badge variant={getFindingBadgeVariant(finding.severity)}>
                                  {finding.category}
                                </Badge>
                              </div>
                              <p className="text-sm text-muted-foreground">{finding.message}</p>
                              {finding.recommendation && (
                                <div className="mt-2 flex items-center gap-2 text-sm">
                                  <ArrowRight className="h-4 w-4" />
                                  <span className="font-medium">{finding.recommendation}</span>
                                </div>
                              )}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Trends Analysis */}
              {reportData.trends.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <TrendingUp className="h-5 w-5" />
                      {t('analytics.trendsAnalysis')}
                      {!reportData.dataSufficient && (
                        <Badge variant="outline" className="ml-2 text-yellow-600 border-yellow-300">
                          {reportData.dataDays}d — Exploratorio
                        </Badge>
                      )}
                    </CardTitle>
                    <CardDescription>
                      {t('analytics.trendsDescription')}
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>{t('analytics.metric')}</TableHead>
                          <TableHead>{t('analytics.direction')}</TableHead>
                          <TableHead className="text-right">{t('analytics.change')}</TableHead>
                          <TableHead className="text-right">R²</TableHead>
                          <TableHead className="text-right">{t('analytics.projection7d')}</TableHead>
                          <TableHead className="text-right">{t('analytics.projection30d')}</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {reportData.trends.map((trend) => (
                          <TableRow key={trend.metricName}>
                            <TableCell className="font-medium">
                              {getVariableLabel(trend.metricName)}
                            </TableCell>
                            <TableCell>
                              <div className="flex items-center gap-2">
                                {getTrendIcon(trend.direction)}
                                <Badge variant={getTrendBadgeVariant(trend.direction)}>
                                  {t(`analytics.trendDirection.${trend.direction}`)}
                                </Badge>
                              </div>
                            </TableCell>
                            <TableCell className="text-right">
                              {formatPercent(trend.slopePercentage)}
                            </TableCell>
                            <TableCell className="text-right">
                              <Badge variant={trend.rSquared >= 0.7 ? 'default' : 'secondary'}>
                                {trend.rSquared.toFixed(2)}
                              </Badge>
                            </TableCell>
                            <TableCell className="text-right">
                              {trend.isReliable && trend.projection7d != null
                                ? formatNumber(trend.projection7d)
                                : <Badge variant="outline" className="text-xs text-muted-foreground">Datos insuf.</Badge>
                              }
                            </TableCell>
                            <TableCell className="text-right">
                              {trend.isReliable && trend.projection30d != null
                                ? formatNumber(trend.projection30d)
                                : <Badge variant="outline" className="text-xs text-muted-foreground">Datos insuf.</Badge>
                              }
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                    {/* NL Trend Summary */}
                    {reportData.trendSummary && (
                      <div className="mt-4 p-3 bg-muted/50 border rounded-lg text-sm text-muted-foreground flex items-start gap-2">
                        <Info className="h-4 w-4 mt-0.5 shrink-0" />
                        <span>{reportData.trendSummary}</span>
                      </div>
                    )}
                  </CardContent>
                </Card>
              )}

              {/* Correlations — show table only if sufficient data */}
              {reportData.correlations.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <BarChart3 className="h-5 w-5" />
                      {t('analytics.correlationsAnalysis')}
                      {!reportData.dataSufficient && (
                        <Badge variant="outline" className="ml-2 text-yellow-600 border-yellow-300">
                          Exploratorio
                        </Badge>
                      )}
                    </CardTitle>
                    <CardDescription>
                      {t('analytics.correlationsDescription')}
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    {reportData.dataSufficient ? (
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>{t('analytics.variable1')}</TableHead>
                            <TableHead>{t('analytics.variable2')}</TableHead>
                            <TableHead className="text-right">{t('analytics.coefficient')}</TableHead>
                            <TableHead>{t('analytics.strength')}</TableHead>
                            <TableHead>{t('analytics.significant')}</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {reportData.correlations.map((corr, idx) => (
                            <TableRow key={idx}>
                              <TableCell>{getVariableLabel(corr.variable1)}</TableCell>
                              <TableCell>{getVariableLabel(corr.variable2)}</TableCell>
                              <TableCell className="text-right font-mono">
                                {corr.coefficient.toFixed(3)}
                              </TableCell>
                              <TableCell>
                                <Badge variant={getCorrelationBadgeVariant(corr.strength)}>
                                  {t(`analytics.correlationStrength.${corr.strength}`)}
                                </Badge>
                              </TableCell>
                              <TableCell>
                                {corr.isSignificant ? (
                                  <CheckCircle className="h-4 w-4 text-green-500" />
                                ) : (
                                  <Minus className="h-4 w-4 text-gray-400" />
                                )}
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    ) : null}
                    {/* NL Correlation Summary */}
                    {reportData.correlationSummary && (
                      <div className={`${reportData.dataSufficient ? 'mt-4' : ''} p-3 bg-muted/50 border rounded-lg text-sm text-muted-foreground flex items-start gap-2`}>
                        <Info className="h-4 w-4 mt-0.5 shrink-0" />
                        <span>{reportData.correlationSummary}</span>
                      </div>
                    )}
                  </CardContent>
                </Card>
              )}

              {/* Predictions Chart */}
              {predictionsChartData && (
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Activity className="h-5 w-5" />
                      {t('analytics.predictionsChart')}
                    </CardTitle>
                    <CardDescription>
                      {t('analytics.predictionsDescription')}
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="h-[350px]">
                      <Line data={predictionsChartData} options={lineChartOptions} />
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Anomalies */}
              {reportData.anomalies.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <AlertTriangle className="h-5 w-5" />
                      {t('analytics.anomaliesDetected')}
                    </CardTitle>
                    <CardDescription>
                      {t('analytics.anomaliesDescription')}
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>{t('analytics.date')}</TableHead>
                          <TableHead>{t('analytics.metric')}</TableHead>
                          <TableHead className="text-right">{t('analytics.value')}</TableHead>
                          <TableHead className="text-right">{t('analytics.expected')}</TableHead>
                          <TableHead className="text-right">{t('analytics.deviation')}</TableHead>
                          <TableHead>{t('analytics.type')}</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {reportData.anomalies.slice(0, 10).map((anomaly, idx) => (
                          <TableRow key={idx}>
                            <TableCell>{new Date(anomaly.date).toLocaleDateString(locale)}</TableCell>
                            <TableCell>{getVariableLabel(anomaly.metricName)}</TableCell>
                            <TableCell className="text-right font-mono">
                              {formatNumber(anomaly.value)}
                            </TableCell>
                            <TableCell className="text-right font-mono text-muted-foreground">
                              {formatNumber(anomaly.expectedValue)}
                            </TableCell>
                            <TableCell className="text-right">
                              <span className={anomaly.anomalyType === 'high' ? 'text-red-600' : 'text-blue-600'}>
                                {formatPercent(anomaly.deviationPercentage)}
                              </span>
                            </TableCell>
                            <TableCell>
                              <Badge variant={anomaly.anomalyType === 'high' ? 'destructive' : 'default'}>
                                {anomaly.anomalyType === 'high' ? t('analytics.anomalyHigh') : t('analytics.anomalyLow')}
                              </Badge>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </CardContent>
                </Card>
              )}

              {/* Statistics */}
              {reportData.statistics.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <BarChart3 className="h-5 w-5" />
                      {t('analytics.descriptiveStats')}
                    </CardTitle>
                    <CardDescription>
                      {t('analytics.descriptiveStatsDescription')}
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>{t('analytics.metric')}</TableHead>
                          <TableHead className="text-right">N</TableHead>
                          <TableHead className="text-right">{t('analytics.mean')}</TableHead>
                          <TableHead className="text-right">{t('analytics.median')}</TableHead>
                          <TableHead className="text-right">{t('analytics.std')}</TableHead>
                          <TableHead className="text-right">{t('analyticsPage.min')}</TableHead>
                          <TableHead className="text-right">{t('analyticsPage.max')}</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {reportData.statistics.map((stat) => (
                          <TableRow key={stat.metricName}>
                            <TableCell className="font-medium">
                              {getVariableLabel(stat.metricName)}
                            </TableCell>
                            <TableCell className="text-right">{stat.count}</TableCell>
                            <TableCell className="text-right font-mono">{formatNumber(stat.mean)}</TableCell>
                            <TableCell className="text-right font-mono">{formatNumber(stat.median)}</TableCell>
                            <TableCell className="text-right font-mono">{formatNumber(stat.std)}</TableCell>
                            <TableCell className="text-right font-mono">{formatNumber(stat.min)}</TableCell>
                            <TableCell className="text-right font-mono">{formatNumber(stat.max)}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </CardContent>
                </Card>
              )}
            </>
          )}
        </TabsContent>

        {/* ============================================= */}
        {/* EXPLORE TAB - Custom Variable Selection */}
        {/* ============================================= */}
        <TabsContent value="explore" className="space-y-6">
          {/* Variable Selection */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Search className="h-5 w-5" />
                {t('analytics.selectVariables')}
              </CardTitle>
              <CardDescription>
                {t('analytics.selectVariablesDescription')}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium mb-2 block">
                    {t('analytics.primaryVariable')}
                  </label>
                  <Select value={primaryVariable} onValueChange={setPrimaryVariable}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {ANALYTICS_VARIABLES.map((v) => (
                        <SelectItem key={v.value} value={v.value}>
                          {locale === 'fr' ? v.labelFr : locale === 'en' ? v.labelEn : v.labelEs}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <label className="text-sm font-medium mb-2 block">
                    {t('analytics.secondaryVariable')} ({t('analytics.optional')})
                  </label>
                  <Select
                    value={secondaryVariable || 'none'}
                    onValueChange={(v) => setSecondaryVariable(v === 'none' ? undefined : v)}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder={t('analytics.selectSecondary')} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">{t('analytics.noSecondary')}</SelectItem>
                      {ANALYTICS_VARIABLES.filter((v) => v.value !== primaryVariable).map((v) => (
                        <SelectItem key={v.value} value={v.value}>
                          {locale === 'fr' ? v.labelFr : locale === 'en' ? v.labelEn : v.labelEs}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Error State */}
          {exploreError && (
            <Card className="border-red-200 bg-red-50">
              <CardContent className="flex items-center gap-3 py-4">
                <AlertCircle className="h-5 w-5 text-red-500" />
                <p className="text-red-700">{t('analytics.loadError')}</p>
              </CardContent>
            </Card>
          )}

          {/* Loading State */}
          {exploreLoading && (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          )}

          {exploreData && (
            <>
              {/* Explore Summary */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    {t('analytics.analysisFor')}: {getVariableLabel(exploreData.primaryVariable)}
                    {exploreData.secondaryVariable && ` + ${getVariableLabel(exploreData.secondaryVariable)}`}
                    {exploreData.dataDays != null && exploreData.dataDays < 14 && (
                      <Badge variant="outline" className="ml-2 text-yellow-600 border-yellow-300">
                        {exploreData.dataDays}d — Exploratorio
                      </Badge>
                    )}
                  </CardTitle>
                  <CardDescription>
                    {t('analytics.period')}: {exploreData.period} | {t('analytics.records')}: {exploreData.totalRecords}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {exploreData.message && (
                    <div className="mb-4 p-3 bg-yellow-50 border border-yellow-200 rounded-lg text-sm">
                      {exploreData.message}
                    </div>
                  )}

                  <div className="grid gap-6 md:grid-cols-2">
                    {/* Statistics */}
                    {exploreData.statistics && (
                      <div className="space-y-2">
                        <h4 className="font-medium flex items-center gap-2">
                          <BarChart3 className="h-4 w-4" />
                          {t('analytics.statistics')}
                        </h4>
                        <div className="grid grid-cols-2 gap-2 text-sm">
                          <div className="p-2 bg-muted rounded">
                            <span className="text-muted-foreground">{t('analytics.mean')}:</span>{' '}
                            <span className="font-mono">{formatNumber(exploreData.statistics.mean)}</span>
                          </div>
                          <div className="p-2 bg-muted rounded">
                            <span className="text-muted-foreground">{t('analytics.median')}:</span>{' '}
                            <span className="font-mono">{formatNumber(exploreData.statistics.median)}</span>
                          </div>
                          <div className="p-2 bg-muted rounded">
                            <span className="text-muted-foreground">{t('analytics.std')}:</span>{' '}
                            <span className="font-mono">{formatNumber(exploreData.statistics.std)}</span>
                          </div>
                          <div className="p-2 bg-muted rounded">
                            <span className="text-muted-foreground">IQR:</span>{' '}
                            <span className="font-mono">{formatNumber(exploreData.statistics.iqr)}</span>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Trend */}
                    {exploreData.trend && (
                      <div className="space-y-2">
                        <h4 className="font-medium flex items-center gap-2">
                          <TrendingUp className="h-4 w-4" />
                          {t('analytics.trend')}
                        </h4>
                        <div className="space-y-2 text-sm">
                          <div className="flex items-center gap-2">
                            {getTrendIcon(exploreData.trend.direction)}
                            <Badge variant={getTrendBadgeVariant(exploreData.trend.direction)}>
                              {t(`analytics.trendDirection.${exploreData.trend.direction}`)}
                            </Badge>
                            <span className="text-muted-foreground">
                              ({formatPercent(exploreData.trend.slopePercentage)})
                            </span>
                          </div>
                          <div className="p-2 bg-muted rounded">
                            <span className="text-muted-foreground">R²:</span>{' '}
                            <span className="font-mono">{exploreData.trend.rSquared.toFixed(3)}</span>
                            <span className="ml-2 text-muted-foreground">
                              ({exploreData.trend.confidenceLevel})
                            </span>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Correlation */}
                    {exploreData.correlation && (
                      <div className="space-y-2">
                        <h4 className="font-medium flex items-center gap-2">
                          <Activity className="h-4 w-4" />
                          {t('analytics.correlation')}
                        </h4>
                        <div className="space-y-2 text-sm">
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-lg">{exploreData.correlation.coefficient.toFixed(3)}</span>
                            <Badge variant={getCorrelationBadgeVariant(exploreData.correlation.strength)}>
                              {t(`analytics.correlationStrength.${exploreData.correlation.strength}`)}
                            </Badge>
                          </div>
                          <div className="p-2 bg-muted rounded flex items-center gap-2">
                            <span className="text-muted-foreground">{t('analytics.significant')}:</span>
                            {exploreData.correlation.isSignificant ? (
                              <CheckCircle className="h-4 w-4 text-green-500" />
                            ) : (
                              <Minus className="h-4 w-4 text-gray-400" />
                            )}
                            <span className="text-muted-foreground">
                              (p = {exploreData.correlation.pValue.toFixed(4)})
                            </span>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* NL Explore Summary */}
                  {exploreData.summary && (
                    <div className="mt-4 p-3 bg-muted/50 border rounded-lg text-sm text-muted-foreground flex items-start gap-2">
                      <Info className="h-4 w-4 mt-0.5 shrink-0" />
                      <span>{exploreData.summary}</span>
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Anomalies for Explore */}
              {exploreData.anomalies.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <AlertTriangle className="h-5 w-5" />
                      {t('analytics.anomaliesDetected')} ({exploreData.anomalies.length})
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>{t('analytics.date')}</TableHead>
                          <TableHead className="text-right">{t('analytics.value')}</TableHead>
                          <TableHead className="text-right">{t('analytics.expected')}</TableHead>
                          <TableHead className="text-right">Z-Score</TableHead>
                          <TableHead>{t('analytics.type')}</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {exploreData.anomalies.map((anomaly, idx) => (
                          <TableRow key={idx}>
                            <TableCell>{new Date(anomaly.date).toLocaleDateString(locale)}</TableCell>
                            <TableCell className="text-right font-mono">
                              {formatNumber(anomaly.value)}
                            </TableCell>
                            <TableCell className="text-right font-mono text-muted-foreground">
                              {formatNumber(anomaly.expectedValue)}
                            </TableCell>
                            <TableCell className="text-right font-mono">
                              {anomaly.zScore.toFixed(2)}
                            </TableCell>
                            <TableCell>
                              <Badge variant={anomaly.anomalyType === 'high' ? 'destructive' : 'default'}>
                                {anomaly.anomalyType === 'high' ? t('analytics.anomalyHigh') : t('analytics.anomalyLow')}
                              </Badge>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </CardContent>
                </Card>
              )}
            </>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
