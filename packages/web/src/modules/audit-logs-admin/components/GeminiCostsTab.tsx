'use client'

import { useState } from 'react'
import { useTranslations } from 'next-intl'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import {
  Cpu, AlertTriangle, CheckCircle, XCircle,
  RefreshCw, Zap, DollarSign, BarChart3,
} from 'lucide-react'
import type { TooltipItem } from 'chart.js'
import {
  Chart as ChartJS, CategoryScale, LinearScale, BarElement,
  ArcElement, PointElement, LineElement, Title, Tooltip, Legend, Filler,
} from 'chart.js'
import { Bar, Doughnut, Line } from 'react-chartjs-2'
import { useGeminiStats } from '../hooks/useAuditLogs'

ChartJS.register(
  CategoryScale, LinearScale, BarElement, ArcElement,
  PointElement, LineElement, Title, Tooltip, Legend, Filler,
)

const CHART_COLORS = [
  '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6',
  '#ec4899', '#14b8a6', '#f97316', '#6366f1', '#84cc16',
]

export function GeminiCostsTab() {
  const t = useTranslations('admin.auditLogs.gemini')
  const [days, setDays] = useState(30)
  const { data: stats, isLoading, error } = useGeminiStats(days)

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <RefreshCw className="h-5 w-5 animate-spin text-muted-foreground" />
        <span className="ml-2 text-sm text-muted-foreground">{t('loading')}</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center py-12 text-red-500 gap-2">
        <AlertTriangle className="h-5 w-5" />
        <span className="text-sm">{error instanceof Error ? error.message : String(error)}</span>
      </div>
    )
  }

  if (!stats) return null

  const errorRate = stats.total_calls > 0 ? ((stats.error_count / stats.total_calls) * 100).toFixed(1) : '0'
  const fallbackRate = stats.total_calls > 0 ? ((stats.fallback_count / stats.total_calls) * 100).toFixed(1) : '0'

  // Daily chart data (reversed: oldest → newest)
  const dailyData = [...(stats.daily_breakdown || [])].reverse()
  const dailyChartData = {
    labels: dailyData.map(d => {
      const date = new Date(d.day)
      return `${date.getDate()}/${date.getMonth() + 1}`
    }),
    datasets: [{
      label: t('tokens'),
      data: dailyData.map(d => d.tokens),
      borderColor: '#3b82f6',
      backgroundColor: 'rgba(59, 130, 246, 0.1)',
      fill: true,
      tension: 0.3,
      pointRadius: 2,
    }],
  }

  const dailyChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: (ctx: TooltipItem<'line'>) =>
            `${(ctx.parsed.y || 0).toLocaleString()} tokens`,
        },
      },
    },
    scales: {
      x: { grid: { display: false }, ticks: { font: { size: 10 }, maxTicksLimit: 15 } },
      y: { grid: { color: '#f1f5f9' }, ticks: { font: { size: 10 } } },
    },
  }

  // By workflow bar chart
  const workflowData = stats.by_workflow || []
  const workflowChartData = {
    labels: workflowData.map(w => w.workflow.replace(/_/g, ' ')),
    datasets: [{
      label: t('tokens'),
      data: workflowData.map(w => w.tokens),
      backgroundColor: workflowData.map((_, i) => CHART_COLORS[i % CHART_COLORS.length]),
      borderRadius: 4,
      maxBarThickness: 30,
    }],
  }

  const barOptions = {
    responsive: true,
    maintainAspectRatio: false,
    indexAxis: 'y' as const,
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: (ctx: TooltipItem<'bar'>) =>
            `${(ctx.parsed.x || 0).toLocaleString()} tokens (${workflowData[ctx.dataIndex]?.calls || 0} ${t('calls').toLowerCase()})`,
        },
      },
    },
    scales: {
      x: { grid: { color: '#f1f5f9' }, ticks: { font: { size: 10 } } },
      y: { grid: { display: false }, ticks: { font: { size: 10 } } },
    },
  }

  // By category donut
  const categoryData = stats.by_document_category || []
  const categoryDonutData = {
    labels: categoryData.map(c => c.category.replace(/_/g, ' ')),
    datasets: [{
      data: categoryData.map(c => c.tokens),
      backgroundColor: categoryData.map((_, i) => CHART_COLORS[i % CHART_COLORS.length]),
      borderWidth: 2,
      borderColor: '#ffffff',
    }],
  }

  const donutOptions = {
    responsive: true,
    maintainAspectRatio: false,
    cutout: '55%',
    plugins: {
      legend: {
        position: 'right' as const,
        labels: { usePointStyle: true, pointStyle: 'circle' as const, padding: 10, font: { size: 11 } },
      },
      tooltip: {
        callbacks: {
          label: (ctx: TooltipItem<'doughnut'>) => {
            const total = (ctx.dataset.data as number[]).reduce((a, b) => a + b, 0)
            const pct = total > 0 ? Math.round(((ctx.parsed || 0) / total) * 100) : 0
            return `${ctx.label}: ${(ctx.parsed || 0).toLocaleString()} tokens (${pct}%)`
          },
        },
      },
    },
  }

  const formatTokens = (n: number): string => {
    if (n > 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
    if (n > 1_000) return `${(n / 1_000).toFixed(0)}K`
    return String(n)
  }

  return (
    <div className="space-y-4">
      {/* Period selector */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold flex items-center gap-2">
          <Cpu className="h-5 w-5 text-blue-500" />
          {t('title')}
        </h2>
        <Select value={String(days)} onValueChange={(v) => setDays(Number(v))}>
          <SelectTrigger className="w-[140px] h-9">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="7">{t('days7')}</SelectItem>
            <SelectItem value="30">{t('days30')}</SelectItem>
            <SelectItem value="90">{t('days90')}</SelectItem>
            <SelectItem value="365">{t('days365')}</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
        <Card>
          <CardContent className="p-3">
            <div className="flex items-center gap-2">
              <Zap className="h-4 w-4 text-blue-500" />
              <div>
                <p className="text-xs text-muted-foreground">{t('calls')}</p>
                <p className="text-lg font-bold">{stats.total_calls.toLocaleString()}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-3">
            <div className="flex items-center gap-2">
              <BarChart3 className="h-4 w-4 text-indigo-500" />
              <div>
                <p className="text-xs text-muted-foreground">{t('tokens')}</p>
                <p className="text-lg font-bold">{formatTokens(stats.total_tokens)}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-3">
            <div className="flex items-center gap-2">
              <DollarSign className="h-4 w-4 text-green-500" />
              <div>
                <p className="text-xs text-muted-foreground">{t('estimatedCost')}</p>
                <p className="text-lg font-bold">${stats.estimated_cost_usd.toFixed(2)}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-3">
            <div className="flex items-center gap-2">
              <XCircle className="h-4 w-4 text-red-500" />
              <div>
                <p className="text-xs text-muted-foreground">{t('errors')}</p>
                <p className="text-lg font-bold">{errorRate}%</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-3">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-orange-500" />
              <div>
                <p className="text-xs text-muted-foreground">{t('fallback')}</p>
                <p className="text-lg font-bold">{fallbackRate}%</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-3">
            <div className="flex items-center gap-2">
              <CheckCircle className="h-4 w-4 text-green-500" />
              <div>
                <p className="text-xs text-muted-foreground">{t('confidence')}</p>
                <p className="text-lg font-bold">{(stats.avg_confidence * 100).toFixed(0)}%</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Charts grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Daily tokens line chart */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base font-semibold">{t('dailyTokens')}</CardTitle>
          </CardHeader>
          <CardContent>
            {dailyData.length > 0 ? (
              <div className="h-56">
                <Line data={dailyChartData} options={dailyChartOptions} />
              </div>
            ) : (
              <p className="text-sm text-muted-foreground text-center py-8">{t('noData')}</p>
            )}
          </CardContent>
        </Card>

        {/* Tokens by category donut */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base font-semibold">{t('tokensByCategory')}</CardTitle>
          </CardHeader>
          <CardContent>
            {categoryData.length > 0 ? (
              <div className="h-56">
                <Doughnut data={categoryDonutData} options={donutOptions} />
              </div>
            ) : (
              <p className="text-sm text-muted-foreground text-center py-8">{t('noData')}</p>
            )}
          </CardContent>
        </Card>

        {/* Tokens by workflow bar chart */}
        <Card className="lg:col-span-2">
          <CardHeader className="pb-2">
            <CardTitle className="text-base font-semibold">{t('tokensByWorkflow')}</CardTitle>
          </CardHeader>
          <CardContent>
            {workflowData.length > 0 ? (
              <div style={{ height: Math.max(workflowData.length * 30 + 40, 200) }}>
                <Bar data={workflowChartData} options={barOptions} />
              </div>
            ) : (
              <p className="text-sm text-muted-foreground text-center py-8">{t('noData')}</p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
