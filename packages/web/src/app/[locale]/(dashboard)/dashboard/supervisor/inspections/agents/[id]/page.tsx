'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { useLocale, useTranslations } from 'next-intl'
import { useToast } from '@/hooks/use-toast'
import {
  ArrowLeft, User, ClipboardCheck, CheckCircle2, XCircle,
  DollarSign, AlertTriangle, Lock, Clock, MapPin, CalendarDays,
} from 'lucide-react'
import {
  Chart as ChartJS,
  CategoryScale, LinearScale, BarElement, LineElement,
  PointElement, Title, Tooltip, Legend, Filler,
  type ChartData, type ChartOptions,
} from 'chart.js'
import { Bar } from 'react-chartjs-2'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table'
import { cn } from '@/core/utils'
import { inspectionApi } from '@/modules/inspections/services/api'
import { INSPECTION_STATUS_CONFIG, fmtXAF } from '@/modules/inspections/utils/formatters'
import type { AgentDetailResponse, InspectionStatus } from '@/modules/inspections/types'

ChartJS.register(
  CategoryScale, LinearScale, BarElement, LineElement,
  PointElement, Title, Tooltip, Legend, Filler,
)

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function conformityDot(rate: number): string {
  if (rate >= 80) return 'bg-green-500'
  if (rate >= 60) return 'bg-yellow-500'
  return 'bg-red-500'
}

function conformityText(rate: number): string {
  if (rate >= 80) return 'text-green-700'
  if (rate >= 60) return 'text-yellow-700'
  return 'text-red-700'
}

function defaultDateFrom(): string {
  const d = new Date()
  d.setDate(d.getDate() - 30)
  return d.toISOString().slice(0, 10)
}

function defaultDateTo(): string {
  return new Date().toISOString().slice(0, 10)
}

function fmtWeek(iso: string, locale?: string): string {
  const d = new Date(iso + 'T00:00:00')
  return d.toLocaleDateString(locale, { month: 'short', day: 'numeric' })
}

function fmtDate(iso: string, locale?: string): string {
  return new Date(iso + 'T00:00:00').toLocaleDateString(locale, {
    year: 'numeric', month: 'short', day: 'numeric',
  })
}

// ---------------------------------------------------------------------------
// Result badge (conforme / non_conforme / pending)
// ---------------------------------------------------------------------------

const RESULT_COLORS: Record<string, { color: string; bg: string }> = {
  conforme: { color: 'text-green-700', bg: 'bg-green-100' },
  non_conforme: { color: 'text-red-700', bg: 'bg-red-100' },
  pending: { color: 'text-gray-600', bg: 'bg-gray-100' },
}

// ---------------------------------------------------------------------------
// KPI definition
// ---------------------------------------------------------------------------

interface KpiDef {
  key: string
  labelKey: string
  icon: React.ElementType
  color: string
  format: (v: AgentDetailResponse) => string
  special?: 'conformity'
}

const KPI_DEFS: KpiDef[] = [
  { key: 'inspections_total', labelKey: 'perf.inspections', icon: ClipboardCheck, color: 'text-blue-600', format: d => String(d.inspections_total) },
  { key: 'conforme', labelKey: 'perf.conforme', icon: CheckCircle2, color: 'text-green-600', format: d => String(d.conforme) },
  { key: 'non_conforme', labelKey: 'perf.non_conforme', icon: XCircle, color: 'text-red-600', format: d => String(d.non_conforme) },
  { key: 'conformity_rate', labelKey: 'perf.conformity_rate', icon: ClipboardCheck, color: '', format: d => `${d.conformity_rate.toFixed(1)}%`, special: 'conformity' },
  { key: 'collections_count', labelKey: 'perf.collections', icon: DollarSign, color: 'text-emerald-600', format: d => String(d.collections_count) },
  { key: 'collected_amount', labelKey: 'perf.amount', icon: DollarSign, color: 'text-amber-600', format: () => '' },
  { key: 'med_count', labelKey: 'perf.med', icon: AlertTriangle, color: 'text-orange-600', format: d => String(d.med_count) },
  { key: 'seal_count', labelKey: 'perf.seals', icon: Lock, color: 'text-red-600', format: d => String(d.seal_count) },
]

// ===========================================================================
// Page component
// ===========================================================================

export default function AgentDetailPage() {
  const params = useParams<{ id: string }>()
  const agentId = params.id
  const locale = useLocale()
  const router = useRouter()
  const { toast } = useToast()
  const t = useTranslations('inspection')

  const [data, setData] = useState<AgentDetailResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [dateFrom, setDateFrom] = useState(defaultDateFrom)
  const [dateTo, setDateTo] = useState(defaultDateTo)

  // -----------------------------------------------------------------------
  // Fetch
  // -----------------------------------------------------------------------

  const fetchData = useCallback(async () => {
    setLoading(true)
    try {
      const res = await inspectionApi.getAgentDetail(agentId, {
        date_from: dateFrom,
        date_to: dateTo,
      })
      setData(res)
    } catch {
      toast({ title: t('common.error'), variant: 'destructive' })
    } finally {
      setLoading(false)
    }
  }, [agentId, dateFrom, dateTo, t, toast])

  useEffect(() => { fetchData() }, [fetchData])

  // -----------------------------------------------------------------------
  // Chart data
  // -----------------------------------------------------------------------

  const chartData = useMemo((): ChartData<'bar'> | null => {
    if (!data?.weekly_trend?.length) return null
    const labels = data.weekly_trend.map(w => fmtWeek(w.week_start, locale))
    return {
      labels,
      datasets: [
        {
          label: t('perf.conforme'),
          data: data.weekly_trend.map(w => w.conforme),
          backgroundColor: 'rgba(34,197,94,0.7)',
          stack: 'inspections',
          yAxisID: 'y',
          order: 2,
        },
        {
          label: t('perf.non_conforme'),
          data: data.weekly_trend.map(w => w.non_conforme),
          backgroundColor: 'rgba(239,68,68,0.7)',
          stack: 'inspections',
          yAxisID: 'y',
          order: 2,
        },
        {
          // Line overlay on bar chart — Chart.js supports this via type override
          type: 'line' as const,
          label: t('perf.amount'),
          data: data.weekly_trend.map(w => w.collected_amount),
          borderColor: 'rgb(245,158,11)',
          backgroundColor: 'rgba(245,158,11,0.1)',
          fill: true,
          tension: 0.3,
          pointRadius: 3,
          yAxisID: 'y1',
          order: 1,
        } as unknown as ChartData<'bar'>['datasets'][number],
      ],
    }
  }, [data, t, locale])

  const chartOptions = useMemo((): ChartOptions<'bar'> => ({
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index' as const, intersect: false },
    plugins: {
      legend: { position: 'bottom' as const, labels: { boxWidth: 12, padding: 10, font: { size: 11 } } },
      tooltip: {
        callbacks: {
          label: (ctx) => {
            const label = ctx.dataset.label || ''
            if (label === t('perf.amount')) return `${label}: ${fmtXAF(ctx.parsed.y, locale)}`
            return `${label}: ${ctx.parsed.y}`
          },
        },
      },
    },
    scales: {
      x: { grid: { display: false }, ticks: { font: { size: 10 } } },
      y: { position: 'left' as const, beginAtZero: true, ticks: { stepSize: 1, font: { size: 10 } }, grid: { color: 'rgba(0,0,0,0.05)' }, title: { display: false } },
      y1: { position: 'right' as const, beginAtZero: true, grid: { drawOnChartArea: false }, ticks: { font: { size: 10 }, callback: (v: number | string) => `${Number(v) >= 1000 ? `${Math.round(Number(v) / 1000)}k` : v}` } },
    },
  }), [locale, t])

  // -----------------------------------------------------------------------
  // Skeleton state
  // -----------------------------------------------------------------------

  if (loading && !data) {
    return (
      <div className="flex flex-col gap-4 p-4">
        <Skeleton className="h-8 w-64" />
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-8">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-20 w-full rounded-lg" />
          ))}
        </div>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <Skeleton className="col-span-2 h-80 rounded-lg" />
          <Skeleton className="h-80 rounded-lg" />
        </div>
      </div>
    )
  }

  if (!data) return null

  // -----------------------------------------------------------------------
  // Render
  // -----------------------------------------------------------------------

  return (
    <div className="flex flex-col gap-3 p-4">
      {/* ============== HEADER ============== */}
      <div className="flex flex-wrap items-center gap-3">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => router.push(`/${locale}/dashboard/supervisor/inspections`)}
        >
          <ArrowLeft className="mr-1 h-4 w-4" />
          {t('supervisor.title')}
        </Button>

        <div className="flex items-center gap-2">
          <User className="h-5 w-5 text-muted-foreground" />
          <h1 className="text-xl font-bold">{data.agent_name}</h1>
          <Badge variant="outline" className="text-xs">{data.entity_code}</Badge>
        </div>

        <div className="ml-auto flex items-center gap-2">
          <label className="text-xs text-muted-foreground">{t('filters.date_from')}</label>
          <input
            type="date"
            value={dateFrom}
            onChange={e => setDateFrom(e.target.value)}
            className="h-8 rounded-md border bg-background px-2 text-xs"
          />
          <label className="text-xs text-muted-foreground">{t('filters.date_to')}</label>
          <input
            type="date"
            value={dateTo}
            onChange={e => setDateTo(e.target.value)}
            className="h-8 rounded-md border bg-background px-2 text-xs"
          />
        </div>
      </div>

      {/* ============== KPI ROW ============== */}
      <div className="grid grid-cols-2 gap-2 md:grid-cols-4 lg:grid-cols-8">
        {KPI_DEFS.map(kpi => {
          const Icon = kpi.icon
          return (
            <Card key={kpi.key} className="p-0">
              <CardContent className="flex flex-col items-start gap-1 p-3">
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <Icon className={cn('h-3.5 w-3.5', kpi.color)} />
                  {t(kpi.labelKey)}
                </div>
                {kpi.key === 'collected_amount' ? (
                  <span className="tabular-nums text-lg font-bold text-amber-600">
                    {fmtXAF(data.collected_amount, locale)}
                  </span>
                ) : kpi.special === 'conformity' ? (
                  <div className="flex items-center gap-1.5">
                    <span className={cn('inline-block h-2.5 w-2.5 rounded-full', conformityDot(data.conformity_rate))} />
                    <span className={cn('tabular-nums text-lg font-bold', conformityText(data.conformity_rate))}>
                      {data.conformity_rate.toFixed(1)}%
                    </span>
                  </div>
                ) : (
                  <span className="tabular-nums text-lg font-bold">
                    {kpi.format(data)}
                  </span>
                )}
              </CardContent>
            </Card>
          )
        })}
      </div>

      {/* ============== CONTENT 2-COL ============== */}
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
        {/* ---------- LEFT (2/3) ---------- */}
        <div className="flex flex-col gap-3 lg:col-span-2">
          {/* Weekly trend chart */}
          <Card>
            <CardHeader className="pb-2 pt-3 px-4">
              <CardTitle className="text-sm font-semibold">
                {t('perf.inspections')} &mdash; {t('filters.date_from')} / {t('filters.date_to')}
              </CardTitle>
            </CardHeader>
            <CardContent className="px-4 pb-3">
              {chartData ? (
                <div style={{ height: 220 }}>
                  {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                  <Bar data={chartData} options={chartOptions} />
                </div>
              ) : (
                <div className="flex h-[220px] items-center justify-center text-sm text-muted-foreground">
                  {t('perf.empty')}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Recent inspections table */}
          <Card>
            <CardHeader className="pb-2 pt-3 px-4">
              <CardTitle className="text-sm font-semibold">
                {t('perf.inspections')} ({data.recent_inspections?.length ?? 0})
              </CardTitle>
            </CardHeader>
            <CardContent className="px-0 pb-2">
              {data.recent_inspections?.length ? (
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="text-xs">{t('payments.date')}</TableHead>
                        <TableHead className="text-xs">{t('payments.company')}</TableHead>
                        <TableHead className="text-xs">{t('filters.result')}</TableHead>
                        <TableHead className="text-xs">{t('filters.status')}</TableHead>
                        <TableHead className="text-right text-xs">{t('perf.amount')}</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {data.recent_inspections.slice(0, 10).map(row => {
                        const resultCfg = RESULT_COLORS[row.result] ?? RESULT_COLORS.pending
                        const statusCfg = INSPECTION_STATUS_CONFIG[row.status as InspectionStatus]
                        return (
                          <TableRow
                            key={row.id}
                            className="cursor-pointer hover:bg-muted/50"
                            onClick={() => router.push(`/${locale}/dashboard/supervisor/inspections/${row.id}`)}
                          >
                            <TableCell className="whitespace-nowrap text-xs tabular-nums">
                              {fmtDate(row.inspection_date, locale)}
                            </TableCell>
                            <TableCell className="max-w-[180px] truncate text-xs">
                              <span>{row.company_name}</span>
                              {row.company_nif && (
                                <span className="ml-1 text-muted-foreground">({row.company_nif})</span>
                              )}
                            </TableCell>
                            <TableCell>
                              <Badge variant="secondary" className={cn('text-[10px]', resultCfg.bg, resultCfg.color)}>
                                {t(`result.${row.result}` as Parameters<typeof t>[0])}
                              </Badge>
                            </TableCell>
                            <TableCell>
                              {statusCfg ? (
                                <Badge variant="secondary" className={cn('text-[10px]', statusCfg.bgColor, statusCfg.color)}>
                                  {t(`status.${row.status}` as Parameters<typeof t>[0])}
                                </Badge>
                              ) : (
                                <span className="text-xs text-muted-foreground">{row.status}</span>
                              )}
                            </TableCell>
                            <TableCell className="whitespace-nowrap text-right text-xs tabular-nums">
                              {row.payment_amount != null ? fmtXAF(row.payment_amount, locale) : '-'}
                            </TableCell>
                          </TableRow>
                        )
                      })}
                    </TableBody>
                  </Table>
                </div>
              ) : (
                <div className="flex h-20 items-center justify-center text-sm text-muted-foreground">
                  {t('perf.empty')}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* ---------- RIGHT (1/3) ---------- */}
        <div className="flex flex-col gap-3">
          {/* Zone coverage */}
          <Card>
            <CardHeader className="pb-2 pt-3 px-4">
              <CardTitle className="flex items-center gap-1.5 text-sm font-semibold">
                <MapPin className="h-4 w-4 text-muted-foreground" />
                {t('zone.zone')}
              </CardTitle>
            </CardHeader>
            <CardContent className="px-4 pb-3">
              {data.zone_breakdown?.length ? (
                <div className="flex flex-col gap-2">
                  {data.zone_breakdown.map(z => (
                    <div key={z.zone_code} className="rounded-md border p-2">
                      <div className="flex items-center justify-between">
                        <div>
                          <span className="text-xs font-semibold">{z.zone_code}</span>
                          <span className="ml-1.5 text-xs text-muted-foreground">{z.zone_name}</span>
                        </div>
                      </div>
                      <div className="mt-1 flex items-center gap-3 text-xs">
                        <span className="tabular-nums">
                          <ClipboardCheck className="mr-0.5 inline h-3 w-3 text-muted-foreground" />
                          {z.inspections}
                        </span>
                        <span className="tabular-nums text-green-600">
                          <CheckCircle2 className="mr-0.5 inline h-3 w-3" />
                          {z.conforme}
                        </span>
                        <span className="ml-auto tabular-nums text-amber-600">
                          {fmtXAF(z.collected_amount, locale)}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="flex h-20 items-center justify-center text-xs text-muted-foreground">
                  {t('zone.empty')}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Agent stats */}
          <Card>
            <CardHeader className="pb-2 pt-3 px-4">
              <CardTitle className="flex items-center gap-1.5 text-sm font-semibold">
                <User className="h-4 w-4 text-muted-foreground" />
                {t('perf.agent')}
              </CardTitle>
            </CardHeader>
            <CardContent className="px-4 pb-3">
              <div className="flex flex-col gap-3">
                <div className="flex items-center gap-2">
                  <Clock className="h-4 w-4 text-muted-foreground" />
                  <div className="flex flex-col">
                    <span className="text-[10px] uppercase text-muted-foreground">{t('perf.avg_duration')}</span>
                    <span className="tabular-nums text-sm font-semibold">
                      {data.avg_duration_minutes != null
                        ? `${Math.round(data.avg_duration_minutes)} min`
                        : '-'}
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <MapPin className="h-4 w-4 text-muted-foreground" />
                  <div className="flex flex-col">
                    <span className="text-[10px] uppercase text-muted-foreground">{t('perf.zones')}</span>
                    <span className="tabular-nums text-sm font-semibold">{data.zones_covered}</span>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <CalendarDays className="h-4 w-4 text-muted-foreground" />
                  <div className="flex flex-col">
                    <span className="text-[10px] uppercase text-muted-foreground">{t('perf.days_active')}</span>
                    <span className="tabular-nums text-sm font-semibold">{data.days_active}</span>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
