'use client'

import React, { useState, useMemo } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { useTranslations } from 'next-intl'
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  RefreshCw,
  Database,
  Activity,
  Server,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  ShieldAlert,
  Users,
  CreditCard,
  GitBranch,
  Zap,
  Play,
  Loader2,
  Clock,
} from 'lucide-react'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  ArcElement,
  Tooltip,
  Legend,
} from 'chart.js'
import { Doughnut, Bar } from 'react-chartjs-2'
import { monitoringApi } from '@/modules/admin/services/monitoringApi'
import type { PaymentEntityRow } from '@/modules/admin/services/monitoringApi'
import { useToast } from '@/hooks/use-toast'

ChartJS.register(CategoryScale, LinearScale, BarElement, ArcElement, Tooltip, Legend)

// ---------- helpers ----------
const formatCurrency = (n: number) =>
  new Intl.NumberFormat('es-GQ', { style: 'decimal', maximumFractionDigits: 0 }).format(n)

// ---------- mini pool gauge ----------
const GAUGE_OPTIONS = {
  cutout: '70%',
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { display: false }, tooltip: { enabled: false } },
} as const

function MiniPoolGauge({ used, max }: { used: number; max: number }) {
  const pct = max > 0 ? Math.round((used / max) * 100) : 0
  const color = pct >= 80 ? '#ef4444' : pct >= 50 ? '#f59e0b' : '#10b981'
  const data = useMemo(() => ({
    datasets: [{
      data: [used, Math.max(0, max - used)],
      backgroundColor: [color, '#e5e7eb'],
      borderWidth: 0,
      circumference: 270,
      rotation: 225,
    }],
  }), [used, max, color])
  return (
    <div className="relative h-[50px] w-[50px]">
      <Doughnut data={data} options={GAUGE_OPTIONS} />
      <div className="absolute inset-0 flex items-center justify-center pt-0.5">
        <span className="text-[10px] font-bold" style={{ color }}>{pct}%</span>
      </div>
    </div>
  )
}

// ---------- status dot ----------
function StatusDot({ status, label }: { status: string; label: string }) {
  const isOk = ['ok', 'connected', 'available'].includes(status)
  const isWarn = ['degraded', 'timeout', 'disabled'].includes(status)
  const color = isOk ? 'bg-green-500' : isWarn ? 'bg-amber-400' : 'bg-red-500'
  return (
    <div className="flex items-center gap-1.5">
      <div className={`h-2.5 w-2.5 rounded-full ${color} ${isOk ? '' : 'animate-pulse'}`} />
      <span className="text-xs font-medium">{label}</span>
      <span className="text-[10px] text-muted-foreground">{status}</span>
    </div>
  )
}

// ---------- error inline ----------
function ErrorInline({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="flex items-center gap-2 p-3 rounded-lg border border-red-200 bg-red-50 dark:bg-red-950/20">
      <XCircle className="h-4 w-4 text-red-500 shrink-0" />
      <span className="text-xs text-red-600 flex-1">{message}</span>
      <Button variant="ghost" size="sm" onClick={onRetry} className="h-6 px-2 text-xs">
        <RefreshCw className="h-3 w-3" />
      </Button>
    </div>
  )
}

// ---------- page ----------
export default function OperationsCenterPage() {
  const t = useTranslations('admin')
  const { toast } = useToast()
  const [triggeredJobs, setTriggeredJobs] = useState<Record<string, string>>({})

  // --- i18n CRON job config (inside component for t() access) ---
  const CRON_JOBS = useMemo(() => [
    { key: 'treasury_refresh_views', icon: Database, label: t('operations.cronRefreshViews') },
    { key: 'workload_rebalance', icon: Users, label: t('operations.cronRebalance') },
    { key: 'cleanup_expired_holds', icon: Clock, label: t('operations.cronCleanupHolds') },
    { key: 'assignment_health_check', icon: Activity, label: t('operations.cronHealthCheck') },
  ] as const, [t])

  // --- error message helper ---
  const getErrorMessage = (error: unknown): string => {
    const err = error as { response?: { status?: number } }
    const status = err?.response?.status ?? 500
    if (status === 403) return t('operations.errorPermission')
    if (status === 401) return t('operations.errorSession')
    return t('operations.errorServer', { status })
  }

  // --- data queries ---
  const {
    data: dashboard, isLoading: loadingDash, isError: errorDash,
    error: dashError, refetch: refetchDash,
  } = useQuery({
    queryKey: ['ops', 'dashboard'],
    queryFn: () => monitoringApi.getOperationsDashboard(),
    refetchInterval: 30000,
    retry: 1,
  })

  const {
    data: integrations, isLoading: loadingInt, isError: errorInt,
    error: intError, refetch: refetchInt,
  } = useQuery({
    queryKey: ['ops', 'integrations'],
    queryFn: () => monitoringApi.getIntegrationsHealth(),
    refetchInterval: 15000,
    retry: 1,
  })

  // --- CRON trigger mutation ---
  const triggerMutation = useMutation({
    mutationFn: (jobName: string) => monitoringApi.triggerCronJob(jobName),
    onSuccess: (data) => {
      setTriggeredJobs(prev => ({ ...prev, [data.job]: JSON.stringify(data.result) }))
      toast({ title: data.job, description: t('operations.cronSuccess') })
      refetchDash()
    },
    onError: (err: unknown) => {
      const e = err as { response?: { status?: number; data?: { detail?: string } } }
      const msg = e?.response?.status === 429
        ? t('operations.cronRateLimit')
        : e?.response?.data?.detail || t('operations.cronError')
      toast({ title: 'Error', description: msg, variant: 'destructive' })
    },
  })

  const handleRefreshAll = () => { refetchDash(); refetchInt() }

  // --- critical alerts detection ---
  const alerts = useMemo(() => {
    if (!dashboard) return []
    const list: { severity: 'critical' | 'warning'; msg: string }[] = []

    const slaViolated = dashboard.payments.by_entity.reduce((s, e) => s + e.sla_violated_count, 0)
    if (slaViolated > 0) list.push({ severity: 'critical', msg: t('operations.slaExpired', { count: slaViolated }) })
    if (dashboard.stale_locks > 0) list.push({ severity: 'critical', msg: t('operations.staleLocks', { count: dashboard.stale_locks }) })
    if (dashboard.agents.agents_overloaded > 2) list.push({ severity: 'warning', msg: t('operations.overloadedAgents', { count: dashboard.agents.agents_overloaded }) })
    if (dashboard.agents.agents_inactive_48h > 0) list.push({ severity: 'warning', msg: t('operations.inactiveAgents', { count: dashboard.agents.agents_inactive_48h }) })
    if (dashboard.pipeline.high_priority > 0) list.push({ severity: 'warning', msg: t('operations.highPriorityRequests', { count: dashboard.pipeline.high_priority }) })
    if (dashboard.pool && dashboard.pool.max_size > 0) {
      const pct = Math.round((dashboard.pool.used / dashboard.pool.max_size) * 100)
      if (pct >= 85) list.push({ severity: 'critical', msg: t('operations.poolSaturation', { pct }) })
    }
    return list
  }, [dashboard, t])

  // --- chart data (memoized) ---
  const agentChartData = useMemo(() => {
    if (!dashboard) return null
    const { agents_available, agents_overloaded, agents_unavailable, agents_inactive_48h } = dashboard.agents
    const total = agents_available + agents_overloaded + agents_unavailable + agents_inactive_48h
    if (total === 0) return null
    return {
      labels: [
        t('operations.chartAvailable'),
        t('operations.chartOverloaded'),
        t('operations.chartUnavailable'),
        t('operations.chartInactive48h'),
      ],
      datasets: [{
        data: [agents_available, agents_overloaded, agents_unavailable, agents_inactive_48h],
        backgroundColor: ['#10b981', '#ef4444', '#6b7280', '#f59e0b'],
        borderWidth: 1,
        borderColor: '#fff',
      }],
    }
  }, [dashboard, t])

  const pipelineChartData = useMemo(() => {
    if (!dashboard) return null
    return {
      labels: [
        t('operations.chartSubmitted'),
        t('operations.chartPayment'),
        t('operations.chartPaid'),
        t('operations.chartUnderReview'),
        t('operations.chartInProgress'),
        t('operations.chartEscalated'),
      ],
      datasets: [{
        data: [
          dashboard.pipeline.submitted,
          dashboard.pipeline.payment_phase,
          dashboard.pipeline.paid,
          dashboard.pipeline.under_review,
          dashboard.pipeline.in_progress,
          dashboard.pipeline.active_escalations,
        ],
        backgroundColor: ['#3b82f6', '#f59e0b', '#10b981', '#8b5cf6', '#06b6d4', '#ef4444'],
        borderRadius: 4,
      }],
    }
  }, [dashboard, t])

  const waitTimeChartData = useMemo(() => {
    if (!dashboard || dashboard.payments.by_entity.length === 0) return null
    return {
      labels: dashboard.payments.by_entity.map(e => e.entity_code),
      datasets: [{
        label: t('operations.avgHoursLabel'),
        data: dashboard.payments.by_entity.map(e => e.avg_wait_hours),
        backgroundColor: dashboard.payments.by_entity.map(e =>
          e.avg_wait_hours > 24 ? '#ef4444'
            : e.avg_wait_hours > 12 ? '#f59e0b'
            : '#10b981'
        ),
        borderRadius: 4,
      }],
    }
  }, [dashboard, t])

  // --- chart options (stable refs) ---
  const doughnutOptions = useMemo(() => ({
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { position: 'right' as const, labels: { font: { size: 10 }, boxWidth: 10, padding: 8 } },
    },
  }), [])

  const barHorizontalOptions = useMemo(() => ({
    indexAxis: 'y' as const,
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
      x: { grid: { display: false }, ticks: { font: { size: 9 } } },
      y: { grid: { display: false }, ticks: { font: { size: 9 } } },
    },
  }), [])

  const barVerticalOptions = useMemo(() => ({
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
      x: { grid: { display: false }, ticks: { font: { size: 9 } } },
      y: {
        grid: { display: false },
        ticks: { font: { size: 9 }, callback: (v: string | number) => `${v}h` },
      },
    },
  }), [])

  return (
    <div className="space-y-3">
      {/* ═══ HEADER ═══ */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">{t('operations.title')}</h1>
          <p className="text-muted-foreground text-sm">{t('operations.subtitle')}</p>
        </div>
        <Button variant="outline" size="sm" onClick={handleRefreshAll}>
          <RefreshCw className="h-4 w-4 mr-2" />
          {t('operations.refresh')}
        </Button>
      </div>

      {/* ═══ INTEGRATION HEALTH BAR ═══ */}
      <Card className="p-3">
        <div className="flex items-center justify-between flex-wrap gap-3">
          {loadingInt ? (
            <div className="flex items-center gap-2 text-muted-foreground text-xs">
              <Loader2 className="h-3 w-3 animate-spin" /> {t('operations.checkingIntegrations')}
            </div>
          ) : errorInt ? (
            <ErrorInline message={getErrorMessage(intError)} onRetry={() => refetchInt()} />
          ) : integrations ? (
            <>
              <div className="flex items-center gap-4 flex-wrap">
                <StatusDot status={integrations.database.status} label="Database" />
                <StatusDot status={integrations.redis.status} label="Redis" />
                <StatusDot status={integrations.bange.status} label="BANGE" />
                <StatusDot status={integrations.gemini.status} label="Gemini" />
              </div>
              {dashboard?.pool && (
                <div className="flex items-center gap-2">
                  <span className="text-xs text-muted-foreground">{t('operations.pool')}</span>
                  <MiniPoolGauge used={dashboard.pool.used} max={dashboard.pool.max_size} />
                </div>
              )}
            </>
          ) : null}
        </div>
      </Card>

      {/* ═══ CRITICAL ALERTS ═══ */}
      {alerts.length > 0 && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 dark:bg-amber-950/20 dark:border-amber-800 p-3 space-y-1">
          <div className="flex items-center gap-2">
            <ShieldAlert className="h-4 w-4 text-amber-600" />
            <span className="text-sm font-semibold text-amber-800 dark:text-amber-300">
              {alerts.some(a => a.severity === 'critical') ? t('operations.criticalAlerts') : t('operations.warnings')}
            </span>
          </div>
          {alerts.map((a, i) => (
            <div key={i} className="flex items-center gap-2 ml-6">
              {a.severity === 'critical'
                ? <XCircle className="h-3 w-3 text-red-500 shrink-0" />
                : <AlertTriangle className="h-3 w-3 text-amber-500 shrink-0" />}
              <span className="text-xs text-amber-700 dark:text-amber-400">{a.msg}</span>
            </div>
          ))}
        </div>
      )}

      {/* ═══ SUMMARY CARDS ═══ */}
      {loadingDash ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          {[1, 2, 3, 4].map(i => (
            <Card key={i}><CardContent className="pt-6 text-center text-muted-foreground">...</CardContent></Card>
          ))}
        </div>
      ) : errorDash ? (
        <ErrorInline message={getErrorMessage(dashError)} onRetry={() => refetchDash()} />
      ) : dashboard ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          {/* Card 1: Payments */}
          <Card>
            <CardHeader className="pb-1 pt-3 px-4">
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                <CreditCard className="h-4 w-4 text-blue-500" />
                {t('operations.paymentsPending')}
              </CardTitle>
            </CardHeader>
            <CardContent className="px-4 pb-3 space-y-1">
              <div className="text-3xl font-bold">{dashboard.payments.total_pending}</div>
              <div className="text-sm text-muted-foreground">
                {formatCurrency(dashboard.payments.total_pending_amount)} XAF
              </div>
              {dashboard.payments.by_entity.some(e => e.sla_violated_count > 0) && (
                <Badge variant="destructive" className="text-[10px]">
                  {t('operations.slaViolated', { count: dashboard.payments.by_entity.reduce((s, e) => s + e.sla_violated_count, 0) })}
                </Badge>
              )}
            </CardContent>
          </Card>

          {/* Card 2: Agents */}
          <Card>
            <CardHeader className="pb-1 pt-3 px-4">
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                <Users className="h-4 w-4 text-green-500" />
                {t('operations.agentStatus')}
              </CardTitle>
            </CardHeader>
            <CardContent className="px-4 pb-3 space-y-1">
              <div className="text-3xl font-bold">
                {dashboard.agents.agents_available}
                <span className="text-base font-normal text-muted-foreground">/{dashboard.agents.total_agents}</span>
              </div>
              <div className="flex gap-2 flex-wrap">
                {dashboard.agents.agents_overloaded > 0 && (
                  <Badge variant="destructive" className="text-[10px]">
                    {t('operations.overloaded', { count: dashboard.agents.agents_overloaded })}
                  </Badge>
                )}
                {dashboard.agents.agents_inactive_48h > 0 && (
                  <Badge variant="secondary" className="text-[10px]">
                    {t('operations.inactive', { count: dashboard.agents.agents_inactive_48h })}
                  </Badge>
                )}
              </div>
              <div className="text-xs text-muted-foreground">
                {t('operations.avgCapacity', { pct: dashboard.agents.avg_capacity })}
              </div>
            </CardContent>
          </Card>

          {/* Card 3: Pipeline */}
          <Card>
            <CardHeader className="pb-1 pt-3 px-4">
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                <GitBranch className="h-4 w-4 text-violet-500" />
                {t('operations.pipeline')}
              </CardTitle>
            </CardHeader>
            <CardContent className="px-4 pb-3 space-y-1">
              <div className="flex items-baseline gap-2">
                <span className="text-3xl font-bold">{dashboard.pipeline.new_24h}</span>
                <span className="text-xs text-muted-foreground">{t('operations.new24h')}</span>
              </div>
              <div className="flex items-baseline gap-2">
                <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
                <span className="text-sm font-medium">{t('operations.completed', { count: dashboard.pipeline.completed_24h })}</span>
              </div>
              <div className="text-xs text-muted-foreground">
                {t('operations.underReviewInProgress', { review: dashboard.pipeline.under_review, progress: dashboard.pipeline.in_progress })}
              </div>
            </CardContent>
          </Card>

          {/* Card 4: Escalations */}
          <Card>
            <CardHeader className="pb-1 pt-3 px-4">
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                <Zap className="h-4 w-4 text-amber-500" />
                {t('operations.escalations')}
              </CardTitle>
            </CardHeader>
            <CardContent className="px-4 pb-3 space-y-1">
              <div className="text-3xl font-bold">{dashboard.pipeline.active_escalations}</div>
              <div className="text-xs text-muted-foreground">{t('operations.activeEscalations')}</div>
              {dashboard.pipeline.high_priority > 0 && (
                <Badge variant="secondary" className="text-[10px]">
                  {t('operations.highPriority', { count: dashboard.pipeline.high_priority })}
                </Badge>
              )}
              {dashboard.stale_locks > 0 && (
                <Badge variant="destructive" className="text-[10px]">
                  {t('operations.locksBlocked', { count: dashboard.stale_locks })}
                </Badge>
              )}
            </CardContent>
          </Card>
        </div>
      ) : null}

      {/* ═══ CHARTS ROW ═══ */}
      {dashboard && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
          {/* Agent Distribution Doughnut */}
          <Card>
            <CardHeader className="pb-1 pt-3 px-4">
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                <Users className="h-4 w-4 text-green-500" />
                {t('operations.agentDistribution')}
              </CardTitle>
            </CardHeader>
            <CardContent className="px-4 pb-3">
              <div className="h-[160px]">
                {agentChartData ? (
                  <Doughnut data={agentChartData} options={doughnutOptions} />
                ) : (
                  <div className="h-full flex items-center justify-center text-muted-foreground text-xs">
                    {t('operations.noData')}
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Pipeline Funnel Bar Chart */}
          <Card>
            <CardHeader className="pb-1 pt-3 px-4">
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                <GitBranch className="h-4 w-4 text-violet-500" />
                {t('operations.pipelineRequests')}
              </CardTitle>
            </CardHeader>
            <CardContent className="px-4 pb-3">
              <div className="h-[160px]">
                {pipelineChartData ? (
                  <Bar data={pipelineChartData} options={barHorizontalOptions} />
                ) : (
                  <div className="h-full flex items-center justify-center text-muted-foreground text-xs">
                    {t('operations.noData')}
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Payment Wait Time by Entity */}
          <Card>
            <CardHeader className="pb-1 pt-3 px-4">
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                <Clock className="h-4 w-4 text-amber-500" />
                {t('operations.waitTimeByEntity')}
              </CardTitle>
            </CardHeader>
            <CardContent className="px-4 pb-3">
              <div className="h-[160px]">
                {waitTimeChartData ? (
                  <Bar data={waitTimeChartData} options={barVerticalOptions} />
                ) : (
                  <div className="h-full flex items-center justify-center text-muted-foreground text-xs">
                    {t('operations.noData')}
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* ═══ BOTTOM ROW: Payment Queue + Quick Actions ═══ */}
      {dashboard && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
          {/* Payment Queue by Entity */}
          <Card className="lg:col-span-2">
            <CardHeader className="pb-2 pt-3 px-4">
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                <Server className="h-4 w-4 text-blue-500" />
                {t('operations.paymentQueue')}
              </CardTitle>
            </CardHeader>
            <CardContent className="px-3 pb-3">
              {dashboard.payments.by_entity.length === 0 ? (
                <div className="text-center py-6 text-muted-foreground text-sm flex flex-col items-center gap-2">
                  <CheckCircle2 className="h-6 w-6 text-green-500" />
                  {t('operations.noPendingPayments')}
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="text-xs">{t('operations.entity')}</TableHead>
                      <TableHead className="text-xs text-right">{t('operations.pending')}</TableHead>
                      <TableHead className="text-xs text-right">{t('operations.amount')}</TableHead>
                      <TableHead className="text-xs text-right">{t('operations.avgHours')}</TableHead>
                      <TableHead className="text-xs text-right">SLA</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {dashboard.payments.by_entity.map((row: PaymentEntityRow) => (
                      <TableRow key={row.entity_code}>
                        <TableCell className="font-mono text-xs py-2 font-medium">{row.entity_code}</TableCell>
                        <TableCell className="text-right font-mono text-xs py-2">{row.pending_count}</TableCell>
                        <TableCell className="text-right font-mono text-xs py-2">{formatCurrency(row.pending_amount)}</TableCell>
                        <TableCell className="text-right font-mono text-xs py-2">
                          <span className={row.avg_wait_hours > 24 ? 'text-red-500 font-bold' : ''}>
                            {row.avg_wait_hours}h
                          </span>
                        </TableCell>
                        <TableCell className="text-right py-2">
                          {row.sla_violated_count > 0 ? (
                            <Badge variant="destructive" className="text-[10px]">
                              {row.sla_violated_count}
                            </Badge>
                          ) : (
                            <CheckCircle2 className="h-3.5 w-3.5 text-green-500 inline" />
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>

          {/* Quick Actions */}
          <Card>
            <CardHeader className="pb-2 pt-3 px-4">
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                <Play className="h-4 w-4 text-green-500" />
                {t('operations.quickActions')}
              </CardTitle>
            </CardHeader>
            <CardContent className="px-4 pb-3 space-y-2">
              {CRON_JOBS.map(job => {
                const isRunning = triggerMutation.isPending && triggerMutation.variables === job.key
                const lastResult = triggeredJobs[job.key]
                return (
                  <div key={job.key}>
                    <Button
                      variant="outline"
                      size="sm"
                      className="w-full justify-start text-xs h-8"
                      disabled={isRunning}
                      onClick={() => triggerMutation.mutate(job.key)}
                    >
                      {isRunning ? (
                        <Loader2 className="h-3.5 w-3.5 mr-2 animate-spin" />
                      ) : (
                        <job.icon className="h-3.5 w-3.5 mr-2" />
                      )}
                      {job.label}
                    </Button>
                    {lastResult && (
                      <p className="text-[10px] text-muted-foreground mt-0.5 ml-6 truncate" title={lastResult}>
                        {lastResult.length > 60 ? lastResult.slice(0, 57) + '...' : lastResult}
                      </p>
                    )}
                  </div>
                )
              })}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}
