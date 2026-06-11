'use client'

/**
 * MissionDashboardTab — Professional analytics dashboard with Chart.js.
 *
 * Features:
 * - 4 KPI cards with delta arrows (↑↓ vs previous period)
 * - Line chart: inspections + conformity trends (dual axis)
 * - Doughnut: mission status breakdown
 * - Horizontal bar: top agents by inspections (with target %)
 * - Stale zones table with CTAs
 * - Agent × Zone heatmap matrix
 */

import { useCallback, useEffect, useMemo, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useLocale, useTranslations } from 'next-intl'
import {
  Chart as ChartJS,
  CategoryScale, LinearScale, BarElement, LineElement,
  PointElement, ArcElement, Tooltip, Legend, Filler,
} from 'chart.js'
import { Line, Doughnut, Bar } from 'react-chartjs-2'
import {
  CalendarDays, CheckCircle2, Target, DollarSign,
  TrendingUp, TrendingDown, MapPin, AlertTriangle,
  Trophy, Plus, Download,
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Progress } from '@/components/ui/progress'
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table'
import { inspectionApi } from '@/modules/inspections/services/api'
import type {
  MissionAnalyticsResponse, MissionTrendPoint, AgentZoneCell, ZoneConformity,
} from '@/modules/inspections/types'

ChartJS.register(
  CategoryScale, LinearScale, BarElement, LineElement,
  PointElement, ArcElement, Tooltip, Legend, Filler,
)

interface Props {
  locationFilter?: string
}

export function MissionDashboardTab({ locationFilter }: Props) {
  const t = useTranslations('inspection')
  const locale = useLocale()
  const router = useRouter()
  const [data, setData] = useState<MissionAnalyticsResponse | null>(null)
  const [loading, setLoading] = useState(true)

  const fetch = useCallback(async () => {
    try {
      setLoading(true)
      const result = await inspectionApi.getMissionAnalytics({
        entity_location_id: locationFilter || undefined,
      })
      setData(result)
    } catch { /* silent */ }
    finally { setLoading(false) }
  }, [locationFilter])

  useEffect(() => { fetch() }, [fetch])

  const fmtXAF = (v: number) => new Intl.NumberFormat('es-GQ', { maximumFractionDigits: 0 }).format(v)

  // Build heatmap matrix
  const matrix = useMemo(() => {
    if (!data?.agent_zone_matrix?.length) return null
    const agents = Array.from(new Set(data.agent_zone_matrix.map((c: AgentZoneCell) => c.agent_name)))
    const zones = Array.from(new Set(data.agent_zone_matrix.map((c: AgentZoneCell) => c.zone_code))).sort()
    const lookup: Record<string, number> = {}
    data.agent_zone_matrix.forEach((c: AgentZoneCell) => {
      lookup[`${c.agent_name}|${c.zone_code}`] = c.inspections
    })
    return { agents, zones, lookup }
  }, [data?.agent_zone_matrix])

  // Export CSV — must be declared before early return (React hooks rule)
  const exportCSV = useCallback((d: MissionAnalyticsResponse) => {
    const rows: string[] = [
      'Metric,Value',
      `Missions completed,${d.summary.completed}/${d.summary.total_missions}`,
      `Completion rate,${d.summary.completion_rate}%`,
      `Inspections,${d.summary.total_inspections_actual}/${d.summary.total_inspections_target}`,
      `Conformity,${d.summary.conformity_rate}%`,
      `Collected,${d.summary.total_collected} XAF`,
      `Avg duration,${d.summary.avg_duration_hours}h`,
      '',
      'Week,Missions,Inspections,Conformity%',
      ...d.trends.map((p: MissionTrendPoint) => `${p.week},${p.missions},${p.inspections},${p.conformity ?? ''}`),
      '',
      'Agent,Missions,Inspections,Target%',
      ...d.top_agents.map(a => `${a.agent_name},${a.missions_count},${a.inspections},${a.avg_target_pct ?? ''}`),
      '',
      'Zone,Total,Conforme,Non conforme,Conformity%',
      ...(d.zone_conformity ?? []).map((z: ZoneConformity) =>
        `${z.zone_code} ${z.zone_name ?? ''},${z.total},${z.conforme},${z.non_conforme},${z.conformity_rate ?? ''}`
      ),
    ]
    const blob = new Blob([rows.join('\n')], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `mission_analytics_${d.period.date_from}_${d.period.date_to}.csv`
    link.click()
    URL.revokeObjectURL(url)
  }, [])

  if (loading || !data) {
    return (
      <div className="space-y-4">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {[1,2,3,4].map(i => <Skeleton key={i} className="h-28 rounded-lg" />)}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <Skeleton className="h-72 rounded-lg" />
          <Skeleton className="h-72 rounded-lg" />
        </div>
      </div>
    )
  }

  const s = data.summary
  const d = data.deltas

  // Chart data
  const trendLabels = data.trends.map((p: MissionTrendPoint) => p.week.replace('2026-', ''))
  const lineData = {
    labels: trendLabels,
    datasets: [
      {
        label: t('missions.inspections', { defaultMessage: 'Inspections' }),
        data: data.trends.map((p: MissionTrendPoint) => p.inspections),
        borderColor: '#2563eb',
        backgroundColor: 'rgba(37,99,235,0.1)',
        fill: true,
        tension: 0.3,
        yAxisID: 'y',
      },
      {
        label: t('missions.conformity', { defaultMessage: 'Conformity %' }),
        data: data.trends.map((p: MissionTrendPoint) => p.conformity ?? 0),
        borderColor: '#16a34a',
        borderDash: [5, 3],
        tension: 0.3,
        yAxisID: 'y1',
      },
    ],
  }

  const doughnutData = {
    labels: [
      t('mission.planned', { defaultMessage: 'Planned' }),
      t('mission.in_progress', { defaultMessage: 'In progress' }),
      t('mission.completed', { defaultMessage: 'Completed' }),
      t('mission.cancelled', { defaultMessage: 'Cancelled' }),
    ],
    datasets: [{
      data: [
        data.status_breakdown.planned,
        data.status_breakdown.in_progress,
        data.status_breakdown.completed,
        data.status_breakdown.cancelled,
      ],
      backgroundColor: ['#3b82f6', '#f59e0b', '#22c55e', '#9ca3af'],
      borderWidth: 0,
    }],
  }

  const barData = {
    labels: data.top_agents.slice(0, 8).map(a => a.agent_name.split(' ')[0]),
    datasets: [{
      label: t('missions.inspections', { defaultMessage: 'Inspections' }),
      data: data.top_agents.slice(0, 8).map(a => a.inspections),
      backgroundColor: data.top_agents.slice(0, 8).map(a =>
        (a.avg_target_pct ?? 0) >= 80 ? '#22c55e' : (a.avg_target_pct ?? 0) >= 50 ? '#f59e0b' : '#ef4444'
      ),
      borderRadius: 4,
    }],
  }

  return (
    <div className="space-y-4">
      {/* Row 1: KPIs with deltas */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <KpiCard
          icon={CalendarDays} color="text-blue-600" bg="bg-blue-50"
          value={`${s.completed}/${s.total_missions}`}
          label={t('missions.completed', { defaultMessage: 'Missions' })}
          delta={d.completion} progress={s.completion_rate}
        />
        <KpiCard
          icon={Target} color="text-green-600" bg="bg-green-50"
          value={`${s.total_inspections_actual}/${s.total_inspections_target}`}
          label={t('missions.inspections', { defaultMessage: 'Inspections' })}
          delta={d.inspections} progress={s.target_achievement_rate}
        />
        <KpiCard
          icon={CheckCircle2} color="text-emerald-600" bg="bg-emerald-50"
          value={`${s.conformity_rate}%`}
          label={t('missions.conformity', { defaultMessage: 'Conformity' })}
          progress={s.conformity_rate}
        />
        <KpiCard
          icon={DollarSign} color="text-orange-600" bg="bg-orange-50"
          value={`${fmtXAF(s.total_collected)}`}
          label={t('missions.collected', { defaultMessage: 'Collected (XAF)' })}
          delta={d.collected}
        />
      </div>

      {/* Row 2: Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Line Chart — 2 cols */}
        <Card className="lg:col-span-2">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-primary" />
              {t('missions.weeklyTrends', { defaultMessage: 'Weekly trends' })}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {data.trends.length > 0 ? (
              <div className="h-56">
                <Line data={lineData} options={{
                  responsive: true, maintainAspectRatio: false,
                  interaction: { mode: 'index' as const, intersect: false },
                  scales: {
                    y: { position: 'left' as const, title: { display: true, text: 'Inspections' }, beginAtZero: true },
                    y1: { position: 'right' as const, title: { display: true, text: '%' }, min: 0, max: 100, grid: { drawOnChartArea: false } },
                  },
                  plugins: { legend: { position: 'bottom' as const, labels: { boxWidth: 12 } } },
                }} />
              </div>
            ) : (
              <p className="text-sm text-muted-foreground py-12 text-center">{t('common.noData', { defaultMessage: 'No data' })}</p>
            )}
          </CardContent>
        </Card>

        {/* Doughnut — 1 col */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">{t('missions.statusBreakdown', { defaultMessage: 'Status' })}</CardTitle>
          </CardHeader>
          <CardContent className="flex justify-center">
            <div className="h-48 w-48">
              <Doughnut data={doughnutData} options={{
                responsive: true, maintainAspectRatio: false,
                cutout: '65%',
                plugins: { legend: { position: 'bottom' as const, labels: { boxWidth: 10, font: { size: 11 } } } },
              }} />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Row 3: Top agents + Stale zones */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Bar chart — Top agents */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <Trophy className="h-4 w-4 text-amber-500" />
              {t('missions.topAgents', { defaultMessage: 'Top agents' })}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {data.top_agents.length > 0 ? (
              <div className="h-52">
                <Bar data={barData} options={{
                  responsive: true, maintainAspectRatio: false,
                  indexAxis: 'y' as const,
                  scales: { x: { beginAtZero: true } },
                  plugins: { legend: { display: false },
                    tooltip: { callbacks: { afterLabel: (ctx: { dataIndex: number }) => {
                      const agent = data.top_agents[ctx.dataIndex]
                      return agent ? `${agent.avg_target_pct ?? 0}% ${t('missions.targetReached', { defaultMessage: 'target' })}` : ''
                    }}}
                  },
                  onClick: (_evt: unknown, elements: Array<{ index: number }>) => {
                    if (elements.length > 0) {
                      const idx = elements[0].index
                      const agent = data.top_agents[idx]
                      if (agent) {
                        router.push(`/${locale}/dashboard/supervisor/inspections/agents`)
                      }
                    }
                  },
                }} />
              </div>
            ) : (
              <p className="text-sm text-muted-foreground py-12 text-center">{t('common.noData', { defaultMessage: 'No data' })}</p>
            )}
          </CardContent>
        </Card>

        {/* Stale zones with CTA */}
        <Card className={data.stale_zones.length > 0 ? 'border-orange-200' : ''}>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2 text-orange-700">
              <AlertTriangle className="h-4 w-4" />
              {t('missions.staleZones', { defaultMessage: 'Zones requiring attention' })}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {data.stale_zones.length === 0 ? (
              <p className="text-sm text-muted-foreground py-8 text-center">
                {t('missions.allCovered', { defaultMessage: 'All zones covered' })}
              </p>
            ) : (
              <div className="space-y-2">
                {data.stale_zones.slice(0, 5).map((zone) => {
                  const days = zone.days_since
                  const urgent = days == null || days > 30
                  return (
                    <div key={zone.zone_code} className="flex items-center justify-between py-1.5 border-b last:border-0">
                      <div className="flex items-center gap-2">
                        <MapPin className={`h-3.5 w-3.5 ${urgent ? 'text-red-500' : 'text-orange-400'}`} />
                        <div>
                          <span className="text-sm font-medium">{zone.zone_code}</span>
                          <span className="text-xs text-muted-foreground ml-1">{zone.zone_name}</span>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge variant={urgent ? 'destructive' : 'secondary'} className="text-xs">
                          {days != null ? `${days}d` : t('missions.never', { defaultMessage: 'Never' })}
                        </Badge>
                        {zone.pending_count > 0 && (
                          <Badge variant="outline" className="text-xs">{zone.pending_count}</Badge>
                        )}
                        <Button
                          size="sm" variant="ghost" className="h-6 px-2 text-xs"
                          onClick={() => router.push(`/${locale}/dashboard/supervisor/inspections/missions?createForZone=${zone.zone_code}`)}
                        >
                          <Plus className="h-3 w-3 mr-0.5" />{t('mission.create', { defaultMessage: 'Plan' })}
                        </Button>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Row 4: Agent × Zone Matrix */}
      {matrix && matrix.agents.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">
              {t('missions.agentZoneMatrix', { defaultMessage: 'Agent × Zone coverage' })}
            </CardTitle>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="text-xs sticky left-0 bg-background">{t('common.agent', { defaultMessage: 'Agent' })}</TableHead>
                  {matrix.zones.map(z => (
                    <TableHead key={z} className="text-xs text-center px-2">{z}</TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {matrix.agents.map(agent => (
                  <TableRow key={agent}>
                    <TableCell className="text-xs font-medium sticky left-0 bg-background whitespace-nowrap">
                      {agent.split(' ')[0]}
                    </TableCell>
                    {matrix.zones.map(zone => {
                      const count = matrix.lookup[`${agent}|${zone}`] || 0
                      const intensity = count === 0 ? '' : count >= 5 ? 'bg-green-200 font-bold' : count >= 2 ? 'bg-green-100' : 'bg-green-50'
                      return (
                        <TableCell key={zone} className={`text-xs text-center px-2 tabular-nums ${intensity}`}>
                          {count || <span className="text-muted-foreground">-</span>}
                        </TableCell>
                      )
                    })}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* Row 5: Conformity × Zone */}
      {data.zone_conformity && data.zone_conformity.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-600" />
              {t('missions.zoneConformity', { defaultMessage: 'Conformity by zone' })}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-52">
              <Bar
                data={{
                  labels: data.zone_conformity.map((z: ZoneConformity) => z.zone_code),
                  datasets: [
                    {
                      label: t('missions.conforme', { defaultMessage: 'Conforme' }),
                      data: data.zone_conformity.map((z: ZoneConformity) => z.conforme),
                      backgroundColor: '#22c55e',
                      borderRadius: 3,
                    },
                    {
                      label: t('missions.nonConforme', { defaultMessage: 'Non conforme' }),
                      data: data.zone_conformity.map((z: ZoneConformity) => z.non_conforme),
                      backgroundColor: '#ef4444',
                      borderRadius: 3,
                    },
                  ],
                }}
                options={{
                  responsive: true,
                  maintainAspectRatio: false,
                  scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true } },
                  plugins: { legend: { position: 'bottom' as const, labels: { boxWidth: 10 } } },
                }}
              />
            </div>
          </CardContent>
        </Card>
      )}

      {/* Footer: Period + Export */}
      <div className="flex items-center justify-between">
        <p className="text-xs text-muted-foreground">
          {t('missions.period', { defaultMessage: 'Period' })}: {data.period.date_from} — {data.period.date_to}
        </p>
        <Button size="sm" variant="outline" className="gap-1.5" onClick={() => exportCSV(data)}>
          <Download className="h-3.5 w-3.5" />
          {t('common.export', { defaultMessage: 'Export CSV' })}
        </Button>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// KPI Card with delta indicator
// ---------------------------------------------------------------------------

function KpiCard({ icon: Icon, color, bg, value, label, delta, progress }: {
  icon: React.ElementType; color: string; bg: string;
  value: string; label: string; delta?: number; progress?: number;
}) {
  const isPositive = (delta ?? 0) >= 0
  return (
    <Card className="shadow-sm hover:shadow-md transition-shadow">
      <CardContent className="p-4">
        <div className="flex items-center justify-between mb-2">
          <div className={`p-2 rounded-lg ${bg}`}>
            <Icon className={`h-4 w-4 ${color}`} />
          </div>
          {delta != null && delta !== 0 && (
            <div className={`flex items-center gap-0.5 text-xs font-medium ${isPositive ? 'text-green-600' : 'text-red-600'}`}>
              {isPositive ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
              {isPositive ? '+' : ''}{delta}%
            </div>
          )}
        </div>
        <p className="text-xl font-bold tabular-nums">{value}</p>
        <p className="text-xs text-muted-foreground mt-0.5">{label}</p>
        {progress != null && (
          <Progress value={Math.min(progress, 100)} className="h-1 mt-2" />
        )}
      </CardContent>
    </Card>
  )
}
