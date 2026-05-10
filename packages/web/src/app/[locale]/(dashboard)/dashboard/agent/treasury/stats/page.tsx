/**
 * Treasury KPIs Dashboard (Phase 4)
 * Executive dashboard with key performance indicators
 * Using Chart.js for visualizations
 */

'use client';

import { useState } from 'react';
import { useTranslations, useLocale } from 'next-intl';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
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
  DollarSign,
  Receipt,
  Clock,
  CheckCircle,
  Building,
  CreditCard,
} from 'lucide-react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js';
import { Line, Doughnut, Bar } from 'react-chartjs-2';
import { useKPIs } from '@/modules/treasury/hooks';
import type { KPIPeriod } from '@/modules/treasury/types';
import { StatsTabNav } from './_components/StatsTabNav';

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

// Payment method colors for charts
const METHOD_COLORS: Record<string, string> = {
  mobile_money: '#10b981',
  card: '#3b82f6',
  bank_transfer: '#8b5cf6',
  cash: '#f59e0b',
  check: '#f97316',
};

// METHOD_LABELS removed - use t('methodLabels.KEY') instead

// Locale mapping for Intl formatters
const LOCALE_MAP: Record<string, string> = { es: 'es-GQ', fr: 'fr-FR', en: 'en-US' };

export default function TreasuryStatsPage() {
  const t = useTranslations('treasury');
  const locale = useLocale();

  const [period, setPeriod] = useState<KPIPeriod>('month');

  const { data: kpiData, isLoading, error, refetch } = useKPIs({ period });

  const intlLocale = LOCALE_MAP[locale] || 'es-GQ';

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat(intlLocale, {
      style: 'currency',
      currency: 'XAF',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(amount);
  };

  const formatNumber = (num: number) => {
    return new Intl.NumberFormat(intlLocale).format(num);
  };

  const getTrendIcon = (trend?: string) => {
    if (!trend) return <Minus className="h-4 w-4 text-gray-400" />;
    if (trend === 'up') return <TrendingUp className="h-4 w-4 text-green-500" />;
    if (trend === 'down') return <TrendingDown className="h-4 w-4 text-red-500" />;
    return <Minus className="h-4 w-4 text-gray-400" />;
  };

  const getTrendColor = (change: number) => {
    if (change > 0) return 'text-green-600';
    if (change < 0) return 'text-red-600';
    return 'text-gray-500';
  };

  // Prepare chart data for daily trend (Line Chart)
  const dailyTrendChartData = {
    labels: kpiData?.dailyTrend.map((d) => {
      const date = new Date(d.date);
      return `${date.getDate()}/${date.getMonth() + 1}`;
    }) || [],
    datasets: [
      {
        label: t('kpis.charts.amount'),
        data: kpiData?.dailyTrend.map((d) => d.amount) || [],
        borderColor: '#3b82f6',
        backgroundColor: 'rgba(59, 130, 246, 0.1)',
        fill: true,
        tension: 0.4,
      },
    ],
  };

  const lineChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: false,
      },
    },
    scales: {
      y: {
        beginAtZero: true,
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

  // Prepare chart data for payment methods (Doughnut Chart)
  const paymentMethodChartData = {
    labels: kpiData?.byPaymentMethod.map((m) => t(`methodLabels.${m.method}` as Parameters<typeof t>[0])) || [],
    datasets: [
      {
        data: kpiData?.byPaymentMethod.map((m) => m.amount) || [],
        backgroundColor: kpiData?.byPaymentMethod.map((m) => METHOD_COLORS[m.method] || '#6b7280') || [],
        borderWidth: 2,
        borderColor: '#ffffff',
      },
    ],
  };

  const doughnutOptions = {
    responsive: true,
    maintainAspectRatio: false,
    cutout: '60%',
    plugins: {
      legend: {
        position: 'right' as const,
        labels: {
          padding: 20,
          usePointStyle: true,
        },
      },
    },
  };

  // Prepare chart data for top entities (Horizontal Bar Chart)
  const entityChartData = {
    labels: kpiData?.byEntity.slice(0, 8).map((m) => {
      const name = m.entityName || 'N/A';
      return name.length > 25 ? name.substring(0, 25) + '...' : name;
    }) || [],
    datasets: [
      {
        label: t('kpis.charts.amount'),
        data: kpiData?.byEntity.slice(0, 8).map((m) => m.amount) || [],
        backgroundColor: '#8b5cf6',
        borderRadius: 4,
      },
    ],
  };

  const barChartOptions = {
    indexAxis: 'y' as const,
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: false,
      },
    },
    scales: {
      x: {
        beginAtZero: true,
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
      <StatsTabNav />
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
            <BarChart3 className="h-8 w-8" />
            {t('kpis.title')}
          </h1>
          <p className="text-muted-foreground mt-1">
            {t('kpis.description')}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Select value={period} onValueChange={(v) => setPeriod(v as KPIPeriod)}>
            <SelectTrigger className="w-40">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="day">{t('kpis.periods.day')}</SelectItem>
              <SelectItem value="week">{t('kpis.periods.week')}</SelectItem>
              <SelectItem value="month">{t('kpis.periods.month')}</SelectItem>
              <SelectItem value="year">{t('kpis.periods.year')}</SelectItem>
            </SelectContent>
          </Select>
          <Button onClick={() => refetch()} variant="outline" disabled={isLoading}>
            <RefreshCw className={`mr-2 h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
            {t('common.refresh')}
          </Button>
        </div>
      </div>

      {/* Error State */}
      {error && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="flex items-center gap-3 py-4">
            <AlertCircle className="h-5 w-5 text-red-500" />
            <p className="text-red-700">{t('kpis.loadError')}</p>
          </CardContent>
        </Card>
      )}

      {/* Loading State */}
      {isLoading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      )}

      {/* KPI Cards */}
      {kpiData && (
        <>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            {/* Total Collected */}
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">{t('kpis.cards.totalCollected')}</p>
                    <p className="text-2xl font-bold">{formatCurrency(kpiData.totalCollected)}</p>
                    {kpiData.previousPeriod && (
                      <div className={`flex items-center gap-1 text-sm ${getTrendColor(kpiData.previousPeriod.totalCollectedChange)}`}>
                        {getTrendIcon(kpiData.previousPeriod.trend)}
                        <span>{kpiData.previousPeriod.totalCollectedChange > 0 ? '+' : ''}{kpiData.previousPeriod.totalCollectedChange.toFixed(1)}%</span>
                      </div>
                    )}
                  </div>
                  <div className="p-3 bg-green-100 rounded-full">
                    <DollarSign className="h-6 w-6 text-green-600" />
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Total Transactions */}
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">{t('kpis.cards.totalTransactions')}</p>
                    <p className="text-2xl font-bold">{formatNumber(kpiData.totalTransactions)}</p>
                    {kpiData.previousPeriod && (
                      <div className={`flex items-center gap-1 text-sm ${getTrendColor(kpiData.previousPeriod.transactionsChange)}`}>
                        {getTrendIcon(kpiData.previousPeriod.trend)}
                        <span>{kpiData.previousPeriod.transactionsChange > 0 ? '+' : ''}{kpiData.previousPeriod.transactionsChange.toFixed(1)}%</span>
                      </div>
                    )}
                  </div>
                  <div className="p-3 bg-blue-100 rounded-full">
                    <Receipt className="h-6 w-6 text-blue-600" />
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Average Amount */}
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">{t('kpis.cards.avgAmount')}</p>
                    <p className="text-2xl font-bold">{formatCurrency(kpiData.avgTransactionAmount)}</p>
                  </div>
                  <div className="p-3 bg-yellow-100 rounded-full">
                    <Clock className="h-6 w-6 text-yellow-600" />
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* SLA Rate */}
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">{t('kpis.cards.slaRate')}</p>
                    <p className="text-2xl font-bold">{kpiData.slaRespectRate.toFixed(1)}%</p>
                    <Badge variant={kpiData.slaRespectRate >= 95 ? 'default' : kpiData.slaRespectRate >= 85 ? 'secondary' : 'destructive'}>
                      {kpiData.slaRespectRate >= 95 ? t('kpis.slaStatus.excellent') : kpiData.slaRespectRate >= 85 ? t('kpis.slaStatus.good') : t('kpis.slaStatus.needsImprovement')}
                    </Badge>
                  </div>
                  <div className="p-3 bg-purple-100 rounded-full">
                    <CheckCircle className="h-6 w-6 text-purple-600" />
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Charts Row */}
          <div className="grid gap-6 lg:grid-cols-2">
            {/* Daily Trend Line Chart */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <TrendingUp className="h-5 w-5" />
                  {t('kpis.charts.dailyTrend')}
                </CardTitle>
                <CardDescription>
                  {t('kpis.charts.dailyTrendDescription')}
                </CardDescription>
              </CardHeader>
              <CardContent>
                {kpiData.dailyTrend.length > 0 ? (
                  <div className="h-[300px]">
                    <Line data={dailyTrendChartData} options={lineChartOptions} />
                  </div>
                ) : (
                  <div className="flex items-center justify-center h-[300px] text-muted-foreground">
                    {t('kpis.noData')}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Payment Method Doughnut Chart */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <CreditCard className="h-5 w-5" />
                  {t('kpis.charts.byPaymentMethod')}
                </CardTitle>
                <CardDescription>
                  {t('kpis.charts.byPaymentMethodDescription')}
                </CardDescription>
              </CardHeader>
              <CardContent>
                {kpiData.byPaymentMethod.length > 0 ? (
                  <div className="h-[300px]">
                    <Doughnut data={paymentMethodChartData} options={doughnutOptions} />
                  </div>
                ) : (
                  <div className="flex items-center justify-center h-[300px] text-muted-foreground">
                    {t('kpis.noData')}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Top Ministries Bar Chart */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Building className="h-5 w-5" />
                {t('kpis.charts.topEntities')}
              </CardTitle>
              <CardDescription>
                {t('kpis.charts.topEntitiesDescription')}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {kpiData.byEntity.length > 0 ? (
                <div className="h-[350px]">
                  <Bar data={entityChartData} options={barChartOptions} />
                </div>
              ) : (
                <div className="flex items-center justify-center h-[300px] text-muted-foreground">
                  {t('kpis.noData')}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Payment Methods Detail Table */}
          <Card>
            <CardHeader>
              <CardTitle>{t('kpis.tables.paymentMethods')}</CardTitle>
              <CardDescription>
                {t('kpis.tables.paymentMethodsDescription')}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t('kpis.tables.method')}</TableHead>
                    <TableHead className="text-right">{t('kpis.tables.transactions')}</TableHead>
                    <TableHead className="text-right">{t('kpis.tables.amount')}</TableHead>
                    <TableHead className="text-right">{t('kpis.tables.percentage')}</TableHead>
                    <TableHead className="text-right">{t('kpis.tables.successRate')}</TableHead>
                    <TableHead className="text-right">{t('kpis.tables.avgTime')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {kpiData.byPaymentMethod.map((method) => (
                    <TableRow key={method.method}>
                      <TableCell className="font-medium">
                        <div className="flex items-center gap-2">
                          <div
                            className="w-3 h-3 rounded-full"
                            style={{ backgroundColor: METHOD_COLORS[method.method] || '#6b7280' }}
                          />
                          {t(`methodLabels.${method.method}` as Parameters<typeof t>[0])}
                        </div>
                      </TableCell>
                      <TableCell className="text-right">{formatNumber(method.count)}</TableCell>
                      <TableCell className="text-right font-medium">{formatCurrency(method.amount)}</TableCell>
                      <TableCell className="text-right">{method.percentage.toFixed(1)}%</TableCell>
                      <TableCell className="text-right">
                        <Badge variant={method.successRate >= 95 ? 'default' : 'secondary'}>
                          {method.successRate.toFixed(1)}%
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        {method.avgProcessingMinutes ? `${method.avgProcessingMinutes.toFixed(0)} ${t('statsPage.units.min')}` : '-'}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
