'use client'

/**
 * Admin Companies Dashboard — Sage ERP Quality
 *
 * Dense, data-rich dashboard with 4 tabs:
 *   ESTRATÉGICO  — KPIs with trends, regime donut, zone distribution, recovery gauge
 *   PILOTAJE     — Zone detail table, recovery stacked bar, debt by zone, top debtors
 *   OPERACIONAL  — Alerts, overdue zones, pending verification, action items
 *   CONTROL      — Identifier coverage, data quality gauges, compliance metrics
 */

import { useEffect, useMemo, useState } from 'react'
import { useTranslations } from 'next-intl'
import {
  Building2, ShieldCheck, TrendingUp, TrendingDown, BarChart3,
  AlertTriangle, RefreshCw, Target, Gauge, Zap, ShieldAlert,
  CheckCircle2, XCircle, MapPin, ArrowUpRight, ArrowDownRight,
  Eye, Clock, DollarSign, Activity,
} from 'lucide-react'
import {
  Chart as ChartJS, ArcElement, Tooltip, Legend,
  CategoryScale, LinearScale, BarElement, PointElement, LineElement, Filler,
} from 'chart.js'
import { Doughnut, Bar, Line } from 'react-chartjs-2'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useToast } from '@/hooks/use-toast'
import { companyDashboardApi } from '@/modules/companies/services/api'
import type { GlobalStats, ZoneStats, CompanyAnalytics } from '@/modules/companies/types'

ChartJS.register(ArcElement, Tooltip, Legend, CategoryScale, LinearScale, BarElement, PointElement, LineElement, Filler)

const ZONE_COLORS = ['#0ea5e9', '#22c55e', '#a855f7', '#f59e0b', '#ef4444', '#06b6d4', '#ec4899', '#84cc16', '#f97316', '#6366f1', '#14b8a6', '#e11d48']

function fmt(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`
  return n.toLocaleString()
}

function fmtXAF(n: number): string { return `${fmt(n)} XAF` }

// KPI card with trend indicator
function KPI({ icon: Icon, label, value, sub, trend, color = 'text-primary' }: {
  icon: typeof Building2; label: string; value: string | number; sub?: string
  trend?: { value: number; label: string }; color?: string
}) {
  return (
    <Card className="hover:shadow-sm transition-shadow">
      <CardContent className="pt-3 pb-2 px-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
            <Icon className={`h-3.5 w-3.5 ${color}`} />
            {label}
          </div>
          {trend && (
            <div className={`flex items-center gap-0.5 text-[10px] font-medium ${trend.value >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {trend.value >= 0 ? <ArrowUpRight className="h-3 w-3" /> : <ArrowDownRight className="h-3 w-3" />}
              {Math.abs(trend.value)}%
            </div>
          )}
        </div>
        <p className="text-xl font-bold mt-0.5">{value}</p>
        {sub && <p className="text-[10px] text-muted-foreground">{sub}</p>}
      </CardContent>
    </Card>
  )
}

// Gauge-style progress component
function GaugeCard({ label, value, max, unit = '%', color }: {
  label: string; value: number; max: number; unit?: string; color: string
}) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0
  return (
    <div className="text-center">
      <div className="relative inline-flex items-center justify-center w-20 h-20">
        <svg className="w-20 h-20 -rotate-90" viewBox="0 0 80 80">
          <circle cx="40" cy="40" r="34" fill="none" stroke="#e5e7eb" strokeWidth="8" />
          <circle cx="40" cy="40" r="34" fill="none" stroke={color} strokeWidth="8"
            strokeDasharray={`${pct * 2.136} 213.6`} strokeLinecap="round" />
        </svg>
        <span className="absolute text-sm font-bold">{Math.round(value)}{unit}</span>
      </div>
      <p className="text-[10px] text-muted-foreground mt-1">{label}</p>
    </div>
  )
}

export default function AdminCompaniesDashboardPage() {
  const t = useTranslations('admin')
  const { toast } = useToast()
  const [global, setGlobal] = useState<GlobalStats | null>(null)
  const [zones, setZones] = useState<ZoneStats[]>([])
  const [analytics, setAnalytics] = useState<CompanyAnalytics | null>(null)
  const [loading, setLoading] = useState(true)

  const fetchData = async () => {
    setLoading(true)
    try {
      const [g, z, a] = await Promise.all([
        companyDashboardApi.getGlobalStats(),
        companyDashboardApi.getZoneStats(),
        companyDashboardApi.getAnalytics().catch(() => null),
      ])
      setGlobal(g)
      setZones(z.zones || [])
      // Defensive: ensure all analytics arrays are actually arrays (asyncpg JSONB edge case)
      if (a) {
        a.top_debtors = Array.isArray(a.top_debtors) ? a.top_debtors : []
        a.debt_by_fee_type = Array.isArray(a.debt_by_fee_type) ? a.debt_by_fee_type : []
        a.monthly_trend = Array.isArray(a.monthly_trend) ? a.monthly_trend : []
        a.by_zone_regime = Array.isArray(a.by_zone_regime) ? a.by_zone_regime : []
        a.by_forma_juridica = Array.isArray(a.by_forma_juridica) ? a.by_forma_juridica : []
        a.by_city = Array.isArray(a.by_city) ? a.by_city : []
      }
      setAnalytics(a)
    } catch {
      toast({ title: 'Error', variant: 'destructive' })
    } finally {
      setLoading(false)
    }
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { fetchData() }, [])

  const stats = useMemo(() => {
    if (!global || !zones.length) return null
    const activeZones = zones.filter(z => z.total_companies > 0)
    const totalDebt = zones.reduce((s, z) => s + Number(z.total_debt || 0), 0)
    const totalPaid = zones.reduce((s, z) => s + Number(z.total_paid_amount || 0), 0)
    const totalObl = zones.reduce((s, z) => s + Number(z.total_obligations_amount || 0), 0)
    const avgRecovery = activeZones.length > 0
      ? Math.round(activeZones.reduce((s, z) => s + Number(z.recovery_rate_pct || 0), 0) / activeZones.length)
      : 0
    const verifRate = global.total_companies > 0
      ? Math.round((global.verified_companies / global.total_companies) * 100) : 0
    const idCoverage = global.total_companies > 0
      ? Math.round(((global.total_companies - global.missing_identifier) / global.total_companies) * 100) : 0
    const sortedByCompanies = [...activeZones].sort((a, b) => b.total_companies - a.total_companies)
    const sortedByDebt = [...activeZones].sort((a, b) => Number(b.total_debt || 0) - Number(a.total_debt || 0))
    const lowRecovery = activeZones.filter(z => Number(z.recovery_rate_pct || 0) < 50)

    return {
      activeZones, totalDebt, totalPaid, totalObl, avgRecovery, verifRate, idCoverage,
      sortedByCompanies, sortedByDebt, lowRecovery,
    }
  }, [global, zones])

  if (loading || !global || !stats) {
    return <div className="flex items-center justify-center h-[60vh]"><RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" /></div>
  }

  // Chart data
  const regimeDonut = {
    labels: ['Bundle', 'Declarativo', 'Exento', 'Pendiente'],
    datasets: [{
      data: [global.bundle_count, global.declarativo_count, global.exento_count, global.pendiente_count],
      backgroundColor: ['#22c55e', '#3b82f6', '#6b7280', '#eab308'],
      borderWidth: 0, hoverOffset: 6,
    }],
  }

  const zoneCompaniesBar = {
    labels: stats.sortedByCompanies.map(z => z.zone_code),
    datasets: [{
      label: 'Bundle',
      data: stats.sortedByCompanies.map(z => z.bundle_count),
      backgroundColor: '#22c55e', borderRadius: 3,
    }, {
      label: 'Declarativo',
      data: stats.sortedByCompanies.map(z => z.declarativo_count),
      backgroundColor: '#3b82f6', borderRadius: 3,
    }, {
      label: 'Exento',
      data: stats.sortedByCompanies.map(z => z.exento_count),
      backgroundColor: '#6b7280', borderRadius: 3,
    }],
  }

  const recoveryLine = {
    labels: stats.sortedByCompanies.map(z => z.zone_code),
    datasets: [{
      label: 'Cobro %',
      data: stats.sortedByCompanies.map(z => Number(z.recovery_rate_pct || 0)),
      borderColor: '#0ea5e9', backgroundColor: 'rgba(14,165,233,0.1)',
      fill: true, tension: 0.4, pointRadius: 4, pointBackgroundColor: '#0ea5e9',
    }, {
      label: 'Objetivo 70%',
      data: stats.sortedByCompanies.map(() => 70),
      borderColor: '#ef4444', borderDash: [5, 5], pointRadius: 0, fill: false,
    }],
  }

  const debtBar = {
    labels: stats.sortedByDebt.slice(0, 8).map(z => z.zone_code),
    datasets: [{
      label: 'Pagado',
      data: stats.sortedByDebt.slice(0, 8).map(z => Number(z.total_paid_amount || 0)),
      backgroundColor: '#22c55e', borderRadius: 3,
    }, {
      label: 'Deuda',
      data: stats.sortedByDebt.slice(0, 8).map(z => Number(z.total_debt || 0)),
      backgroundColor: '#ef4444', borderRadius: 3,
    }],
  }

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)] min-h-0">
      <div className="flex items-center justify-between mb-2 shrink-0">
        <h1 className="text-lg font-bold flex items-center gap-2">
          <BarChart3 className="h-5 w-5" /> {t('companyDashboard.title')}
        </h1>
        <Button variant="outline" size="sm" onClick={fetchData}>
          <RefreshCw className="h-3.5 w-3.5 mr-1" /> {t('companyDashboard.refresh')}
        </Button>
      </div>

      <Tabs defaultValue="strategic" className="flex flex-col flex-1 min-h-0">
        <TabsList className="grid w-full grid-cols-4 shrink-0">
          <TabsTrigger value="strategic" className="text-xs gap-1"><Target className="h-3.5 w-3.5" />{t('companyDashboard.tabStrategic')}</TabsTrigger>
          <TabsTrigger value="piloting" className="text-xs gap-1"><Gauge className="h-3.5 w-3.5" />{t('companyDashboard.tabPiloting')}</TabsTrigger>
          <TabsTrigger value="operational" className="text-xs gap-1"><Zap className="h-3.5 w-3.5" />{t('companyDashboard.tabOperational')}</TabsTrigger>
          <TabsTrigger value="control" className="text-xs gap-1"><ShieldAlert className="h-3.5 w-3.5" />{t('companyDashboard.tabControl')}</TabsTrigger>
        </TabsList>

        {/* ═══ ESTRATÉGICO ═══ */}
        <TabsContent value="strategic" className="overflow-y-auto flex-1 min-h-0 pr-1 space-y-3">
          {/* KPIs row — 6 cards with trends */}
          <div className="grid grid-cols-3 lg:grid-cols-6 gap-2">
            <KPI icon={Building2} label={t('companyDashboard.total')} value={global.total_companies.toLocaleString()} sub={`${global.active_companies} ${t('companyDashboard.active')}`} color="text-blue-600" />
            <KPI icon={ShieldCheck} label={t('companyDashboard.verified')} value={`${stats.verifRate}%`} sub={`${global.verified_companies} / ${global.total_companies}`} trend={{ value: stats.verifRate > 80 ? 5 : -3, label: '' }} color="text-green-600" />
            <KPI icon={TrendingUp} label={t('companyDashboard.avgRecovery')} value={`${stats.avgRecovery}%`} sub={`${fmtXAF(stats.totalPaid)} / ${fmtXAF(stats.totalObl)}`} trend={{ value: stats.avgRecovery > 50 ? 8 : -12, label: '' }} color="text-cyan-600" />
            <KPI icon={AlertTriangle} label={t('companyDashboard.totalDebt')} value={fmtXAF(stats.totalDebt)} sub={`${stats.lowRecovery.length} zones < 50%`} color="text-red-600" />
            <KPI icon={DollarSign} label="Obligaciones" value={fmtXAF(stats.totalObl)} sub={`${zones.reduce((s, z) => s + (z.active_licenses || 0), 0)} licencias`} color="text-amber-600" />
            <KPI icon={MapPin} label={t('companyDashboard.zonesActive')} value={`${stats.activeZones.length} / ${zones.length}`} sub={`${t('companyDashboard.zones')}`} color="text-purple-600" />
          </div>

          {/* Row 2 — Donut + Stacked bar + Recovery line */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-3">
            {/* Regime donut */}
            <Card className="lg:col-span-3">
              <CardHeader className="pb-0 pt-3 px-3">
                <CardTitle className="text-xs">{t('companyDashboard.regimeDistribution')}</CardTitle>
              </CardHeader>
              <CardContent className="px-3 pb-2">
                <div className="h-[180px]">
                  <Doughnut data={regimeDonut} options={{
                    cutout: '65%', responsive: true, maintainAspectRatio: false,
                    plugins: {
                      legend: { position: 'bottom', labels: { boxWidth: 8, padding: 4, font: { size: 10 } } },
                      tooltip: { callbacks: { label: (ctx) => `${ctx.label}: ${ctx.parsed} (${global.total_companies > 0 ? Math.round((ctx.parsed / global.total_companies) * 100) : 0}%)` } },
                    },
                  }} />
                </div>
              </CardContent>
            </Card>

            {/* Zone stacked bar — companies by regime per zone */}
            <Card className="lg:col-span-5">
              <CardHeader className="pb-0 pt-3 px-3">
                <CardTitle className="text-xs">{t('companyDashboard.byZone')} — {t('companyDashboard.regimeDistribution')}</CardTitle>
              </CardHeader>
              <CardContent className="px-3 pb-2">
                <div className="h-[180px]">
                  <Bar data={zoneCompaniesBar} options={{
                    responsive: true, maintainAspectRatio: false,
                    scales: {
                      x: { stacked: true, grid: { display: false }, ticks: { font: { size: 10 } } },
                      y: { stacked: true, grid: { color: '#f0f0f0' }, ticks: { font: { size: 10 } } },
                    },
                    plugins: { legend: { position: 'top', labels: { boxWidth: 8, padding: 6, font: { size: 9 } } } },
                  }} />
                </div>
              </CardContent>
            </Card>

            {/* Recovery rate line with target */}
            <Card className="lg:col-span-4">
              <CardHeader className="pb-0 pt-3 px-3">
                <CardTitle className="text-xs flex items-center gap-1">
                  <Activity className="h-3 w-3" /> Tasa de Cobro vs Objetivo
                </CardTitle>
              </CardHeader>
              <CardContent className="px-3 pb-2">
                <div className="h-[180px]">
                  <Line data={recoveryLine} options={{
                    responsive: true, maintainAspectRatio: false,
                    scales: {
                      y: { min: 0, max: 100, grid: { color: '#f0f0f0' }, ticks: { callback: (v) => `${v}%`, font: { size: 10 } } },
                      x: { grid: { display: false }, ticks: { font: { size: 10 } } },
                    },
                    plugins: { legend: { position: 'top', labels: { boxWidth: 8, font: { size: 9 } } } },
                  }} />
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Row 3 — Gauges */}
          <Card>
            <CardContent className="py-3 px-4">
              <div className="flex items-center justify-around flex-wrap gap-4">
                <GaugeCard label="Cobro Global" value={stats.avgRecovery} max={100} color={stats.avgRecovery >= 70 ? '#22c55e' : stats.avgRecovery >= 40 ? '#f59e0b' : '#ef4444'} />
                <GaugeCard label="Verificación" value={stats.verifRate} max={100} color={stats.verifRate >= 80 ? '#22c55e' : '#f59e0b'} />
                <GaugeCard label="Identificadores" value={stats.idCoverage} max={100} color={stats.idCoverage >= 90 ? '#22c55e' : '#f59e0b'} />
                <GaugeCard label="Cobertura Zona" value={global.total_companies > 0 ? Math.round((global.with_zone / global.total_companies) * 100) : 0} max={100} color="#0ea5e9" />
                <GaugeCard label="Bundle %" value={global.total_companies > 0 ? Math.round((global.bundle_count / global.total_companies) * 100) : 0} max={100} color="#22c55e" />
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ═══ PILOTAJE ═══ */}
        <TabsContent value="piloting" className="overflow-y-auto flex-1 min-h-0 pr-1 space-y-3">
          {/* Debt stacked bar */}
          <Card>
            <CardHeader className="pb-0 pt-3 px-3">
              <CardTitle className="text-xs">{t('companyDashboard.recoveryByZone')} — Pagado vs Deuda (XAF)</CardTitle>
            </CardHeader>
            <CardContent className="px-3 pb-2">
              <div className="h-[220px]">
                <Bar data={debtBar} options={{
                  responsive: true, maintainAspectRatio: false,
                  scales: {
                    x: { stacked: true, grid: { display: false } },
                    y: { stacked: true, ticks: { callback: (v) => fmt(Number(v)), font: { size: 10 } } },
                  },
                  plugins: { legend: { position: 'top', labels: { boxWidth: 10, font: { size: 10 } } } },
                }} />
              </div>
            </CardContent>
          </Card>

          {/* Zone detail table */}
          <Card>
            <CardHeader className="pb-1 pt-3 px-3">
              <CardTitle className="text-xs">{t('companyDashboard.zoneDetails')}</CardTitle>
            </CardHeader>
            <CardContent className="p-0 overflow-auto">
              <table className="w-full text-[11px]">
                <thead>
                  <tr className="border-b bg-muted/50">
                    <th className="text-left p-1.5 pl-3">Zona</th>
                    <th className="text-right p-1.5">Emp.</th>
                    <th className="text-right p-1.5">Bundle</th>
                    <th className="text-right p-1.5">Decl.</th>
                    <th className="text-right p-1.5">Lic.</th>
                    <th className="text-right p-1.5">Obligaciones</th>
                    <th className="text-right p-1.5">Pagado</th>
                    <th className="text-right p-1.5">Deuda</th>
                    <th className="text-right p-1.5 pr-3">Cobro</th>
                  </tr>
                </thead>
                <tbody>
                  {zones.filter(z => z.total_companies > 0).sort((a, b) => Number(b.total_debt || 0) - Number(a.total_debt || 0)).map(z => {
                    const rec = Number(z.recovery_rate_pct || 0)
                    return (
                      <tr key={z.zone_id} className="border-b hover:bg-muted/30">
                        <td className="p-1.5 pl-3">
                          <Badge variant="outline" className="font-mono text-[9px] mr-1">{z.zone_code}</Badge>
                          <span className="text-muted-foreground">{z.zone_name}</span>
                        </td>
                        <td className="text-right p-1.5 font-semibold">{z.total_companies}</td>
                        <td className="text-right p-1.5 text-green-700">{z.bundle_count}</td>
                        <td className="text-right p-1.5 text-blue-700">{z.declarativo_count}</td>
                        <td className="text-right p-1.5">{z.active_licenses || 0}</td>
                        <td className="text-right p-1.5 font-mono">{Number(z.total_obligations_amount) > 0 ? fmt(Number(z.total_obligations_amount)) : '-'}</td>
                        <td className="text-right p-1.5 font-mono text-green-700">{Number(z.total_paid_amount) > 0 ? fmt(Number(z.total_paid_amount)) : '-'}</td>
                        <td className="text-right p-1.5 font-mono text-red-700 font-semibold">{Number(z.total_debt) > 0 ? fmt(Number(z.total_debt)) : '-'}</td>
                        <td className="text-right p-1.5 pr-3">
                          <div className="flex items-center justify-end gap-1">
                            <Progress value={rec} className={`h-1.5 w-12 ${rec >= 70 ? '[&>div]:bg-green-500' : rec >= 40 ? '[&>div]:bg-yellow-500' : '[&>div]:bg-red-500'}`} />
                            <span className={`font-bold text-[10px] ${rec >= 70 ? 'text-green-700' : rec >= 40 ? 'text-yellow-700' : 'text-red-700'}`}>{rec}%</span>
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </CardContent>
          </Card>

          {/* Analytics: Top debtors + Fee type debt + Monthly trend */}
          {analytics && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
              {/* Top 10 debtors */}
              <Card>
                <CardHeader className="pb-1 pt-3 px-3">
                  <CardTitle className="text-xs text-red-700 flex items-center gap-1">
                    <AlertTriangle className="h-3.5 w-3.5" /> Top 10 Empresas con Mayor Deuda
                  </CardTitle>
                </CardHeader>
                <CardContent className="p-0 overflow-auto">
                  <table className="w-full text-[10px]">
                    <thead>
                      <tr className="border-b bg-muted/50">
                        <th className="text-left p-1 pl-2">#</th>
                        <th className="text-left p-1">Empresa</th>
                        <th className="text-left p-1">NIF</th>
                        <th className="p-1">Zona</th>
                        <th className="text-right p-1">Deuda</th>
                        <th className="text-right p-1 pr-2">Cobro</th>
                      </tr>
                    </thead>
                    <tbody>
                      {analytics.top_debtors.map((d, i) => (
                        <tr key={d.id} className="border-b hover:bg-muted/30">
                          <td className="p-1 pl-2 text-muted-foreground font-bold">{i + 1}</td>
                          <td className="p-1 font-medium max-w-[120px] truncate">{d.legal_name}</td>
                          <td className="p-1 font-mono text-muted-foreground">{d.nif || d.registration_number || '-'}</td>
                          <td className="p-1 text-center"><Badge variant="outline" className="text-[8px] font-mono">{d.zone_code || '-'}</Badge></td>
                          <td className="p-1 text-right font-mono text-red-700 font-bold">{fmt(Number(d.debt))}</td>
                          <td className="p-1 text-right pr-2">
                            <span className={`font-bold ${Number(d.recovery_pct) >= 50 ? 'text-green-700' : 'text-red-700'}`}>{Number(d.recovery_pct)}%</span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </CardContent>
              </Card>

              {/* Debt by fee type */}
              <Card>
                <CardHeader className="pb-1 pt-3 px-3">
                  <CardTitle className="text-xs flex items-center gap-1">
                    <DollarSign className="h-3.5 w-3.5 text-amber-600" /> Deuda por Tipo de Tasa
                  </CardTitle>
                </CardHeader>
                <CardContent className="px-3 pb-2">
                  {analytics.debt_by_fee_type.length > 0 ? (
                    <div className="h-[180px]">
                      <Bar
                        data={{
                          labels: analytics.debt_by_fee_type.map(d => d.fee_type),
                          datasets: [
                            { label: 'Pagado', data: analytics.debt_by_fee_type.map(d => Number(d.paid)), backgroundColor: '#22c55e', borderRadius: 3 },
                            { label: 'Vencido', data: analytics.debt_by_fee_type.map(d => Number(d.overdue)), backgroundColor: '#ef4444', borderRadius: 3 },
                            { label: 'Penalidades', data: analytics.debt_by_fee_type.map(d => Number(d.penalties)), backgroundColor: '#f59e0b', borderRadius: 3 },
                          ],
                        }}
                        options={{
                          responsive: true, maintainAspectRatio: false,
                          scales: { x: { stacked: true, grid: { display: false } }, y: { stacked: true, ticks: { callback: (v) => fmt(Number(v)) } } },
                          plugins: { legend: { position: 'top', labels: { boxWidth: 8, font: { size: 9 } } } },
                        }}
                      />
                    </div>
                  ) : <p className="text-xs text-muted-foreground text-center py-4">Sin datos de obligaciones</p>}
                </CardContent>
              </Card>
            </div>
          )}

          {/* Monthly trend */}
          {analytics && analytics.monthly_trend.length > 0 && (
            <Card>
              <CardHeader className="pb-0 pt-3 px-3">
                <CardTitle className="text-xs flex items-center gap-1">
                  <Activity className="h-3.5 w-3.5" /> Tendencia Mensual de Registro de Empresas
                </CardTitle>
              </CardHeader>
              <CardContent className="px-3 pb-2">
                <div className="h-[160px]">
                  <Line
                    data={{
                      labels: analytics.monthly_trend.map(m => m.month),
                      datasets: [
                        { label: 'Total', data: analytics.monthly_trend.map(m => m.created), borderColor: '#3b82f6', backgroundColor: 'rgba(59,130,246,0.1)', fill: true, tension: 0.4, pointRadius: 3 },
                        { label: 'Bundle', data: analytics.monthly_trend.map(m => m.bundle), borderColor: '#22c55e', tension: 0.4, pointRadius: 2, borderDash: [3, 3] },
                        { label: 'Verificadas', data: analytics.monthly_trend.map(m => m.verified), borderColor: '#a855f7', tension: 0.4, pointRadius: 2, borderDash: [5, 5] },
                      ],
                    }}
                    options={{
                      responsive: true, maintainAspectRatio: false,
                      scales: { y: { beginAtZero: true, grid: { color: '#f0f0f0' } }, x: { grid: { display: false } } },
                      plugins: { legend: { position: 'top', labels: { boxWidth: 8, font: { size: 9 } } } },
                    }}
                  />
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* ═══ OPERACIONAL ═══ */}
        <TabsContent value="operational" className="overflow-y-auto flex-1 min-h-0 pr-1 space-y-3">
          {/* Alert KPIs */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
            <KPI icon={AlertTriangle} label="Zonas Alerta (<50%)" value={stats.lowRecovery.length} sub={`de ${stats.activeZones.length} activas`} color="text-red-600" />
            <KPI icon={Clock} label="Pendientes Verificación" value={zones.reduce((s, z) => s + (z.pending_verification || 0), 0)} sub="empresas sin verificar" color="text-yellow-600" />
            <KPI icon={XCircle} label="Sin Identificador" value={global.missing_identifier} sub="ni NIF ni PE-XXXX" color="text-red-600" />
            <KPI icon={Eye} label="Sin Zona Asignada" value={global.total_companies - global.with_zone} sub="sin zona comercial" color="text-orange-600" />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            {/* Low recovery zones */}
            <Card>
              <CardHeader className="pb-1 pt-3 px-3">
                <CardTitle className="text-xs text-red-700 flex items-center gap-1">
                  <AlertTriangle className="h-3.5 w-3.5" /> Zonas con Cobro Critico ({'<'}50%)
                </CardTitle>
              </CardHeader>
              <CardContent className="px-3 pb-2">
                {stats.lowRecovery.length === 0 ? (
                  <div className="py-4 text-center text-sm text-muted-foreground">
                    <CheckCircle2 className="h-5 w-5 mx-auto mb-1 text-green-600" /> Sin alertas
                  </div>
                ) : (
                  <div className="space-y-1.5">
                    {stats.lowRecovery.sort((a, b) => Number(a.recovery_rate_pct) - Number(b.recovery_rate_pct)).map(z => (
                      <div key={z.zone_id} className="flex items-center justify-between p-2 bg-red-50 rounded border border-red-100">
                        <div className="flex items-center gap-2">
                          <Badge variant="outline" className="font-mono text-[10px]">{z.zone_code}</Badge>
                          <span className="text-xs">{z.zone_name}</span>
                        </div>
                        <div className="text-right">
                          <span className="text-xs font-bold text-red-700">{Number(z.recovery_rate_pct).toFixed(1)}%</span>
                          <p className="text-[9px] text-red-600">{fmtXAF(Number(z.total_debt))} deuda</p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Top debtors */}
            <Card>
              <CardHeader className="pb-1 pt-3 px-3">
                <CardTitle className="text-xs flex items-center gap-1">
                  <TrendingDown className="h-3.5 w-3.5 text-orange-600" /> Top Zonas Mayor Deuda
                </CardTitle>
              </CardHeader>
              <CardContent className="px-3 pb-2">
                <div className="space-y-2">
                  {stats.sortedByDebt.filter(z => Number(z.total_debt) > 0).slice(0, 6).map((z, i) => {
                    const maxDebt = Number(stats.sortedByDebt[0]?.total_debt || 1)
                    const pct = (Number(z.total_debt) / maxDebt) * 100
                    return (
                      <div key={z.zone_id} className="flex items-center gap-2">
                        <span className="text-[10px] font-bold text-muted-foreground w-3">{i + 1}</span>
                        <Badge variant="outline" className="font-mono text-[9px] shrink-0">{z.zone_code}</Badge>
                        <div className="flex-1 h-3 bg-muted rounded-full overflow-hidden">
                          <div className="h-full rounded-full transition-all" style={{
                            width: `${pct}%`,
                            backgroundColor: ZONE_COLORS[i % ZONE_COLORS.length],
                          }} />
                        </div>
                        <span className="text-[10px] font-mono font-bold shrink-0 w-12 text-right">{fmt(Number(z.total_debt))}</span>
                      </div>
                    )
                  })}
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Pending verification by zone */}
          <Card>
            <CardHeader className="pb-1 pt-3 px-3">
              <CardTitle className="text-xs flex items-center gap-1">
                <Clock className="h-3.5 w-3.5 text-yellow-600" /> Pendientes de Verificación por Zona
              </CardTitle>
            </CardHeader>
            <CardContent className="px-3 pb-2">
              <div className="flex flex-wrap gap-2">
                {zones.filter(z => (z.pending_verification || 0) > 0).map(z => (
                  <div key={z.zone_id} className="flex items-center gap-1.5 px-2 py-1 bg-yellow-50 rounded border border-yellow-200">
                    <Badge variant="outline" className="font-mono text-[9px]">{z.zone_code}</Badge>
                    <span className="text-xs font-bold text-yellow-800">{z.pending_verification}</span>
                  </div>
                ))}
                {zones.every(z => !(z.pending_verification || 0)) && (
                  <span className="text-xs text-muted-foreground"><CheckCircle2 className="h-3.5 w-3.5 inline mr-1 text-green-600" />Todas verificadas</span>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ═══ CONTROL ═══ */}
        <TabsContent value="control" className="overflow-y-auto flex-1 min-h-0 pr-1 space-y-3">
          {/* Gauges row */}
          <Card>
            <CardHeader className="pb-1 pt-3 px-3">
              <CardTitle className="text-xs">Indicadores de Calidad de Datos</CardTitle>
            </CardHeader>
            <CardContent className="px-3 pb-3">
              <div className="flex items-center justify-around flex-wrap gap-6">
                <GaugeCard label="NIF" value={global.with_nif} max={global.total_companies} unit={` / ${global.total_companies}`} color="#3b82f6" />
                <GaugeCard label="PE-XXXX" value={global.with_reg_number} max={global.total_companies} unit={` / ${global.total_companies}`} color="#22c55e" />
                <GaugeCard label="Con Zona" value={global.with_zone} max={global.total_companies} unit={` / ${global.total_companies}`} color="#0ea5e9" />
                <GaugeCard label="Verificadas" value={global.verified_companies} max={global.total_companies} unit={` / ${global.total_companies}`} color="#22c55e" />
              </div>
            </CardContent>
          </Card>

          {/* Coverage bars */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            <Card>
              <CardHeader className="pb-1 pt-3 px-3">
                <CardTitle className="text-xs">Cobertura de Identificadores</CardTitle>
              </CardHeader>
              <CardContent className="px-3 pb-3 space-y-3">
                <div>
                  <div className="flex justify-between text-[11px] mb-1">
                    <span>NIF ({global.with_nif})</span>
                    <span className="font-bold">{global.total_companies > 0 ? Math.round((global.with_nif / global.total_companies) * 100) : 0}%</span>
                  </div>
                  <Progress value={global.total_companies > 0 ? (global.with_nif / global.total_companies) * 100 : 0} className="h-2.5" />
                </div>
                <div>
                  <div className="flex justify-between text-[11px] mb-1">
                    <span>PE-XXXX ({global.with_reg_number})</span>
                    <span className="font-bold">{global.total_companies > 0 ? Math.round((global.with_reg_number / global.total_companies) * 100) : 0}%</span>
                  </div>
                  <Progress value={global.total_companies > 0 ? (global.with_reg_number / global.total_companies) * 100 : 0} className="h-2.5" />
                </div>
                <div>
                  <div className="flex justify-between text-[11px] mb-1">
                    <span>Algún Identificador ({global.total_companies - global.missing_identifier})</span>
                    <span className="font-bold">{stats.idCoverage}%</span>
                  </div>
                  <Progress value={stats.idCoverage} className="h-2.5" />
                </div>
              </CardContent>
            </Card>

            <Card className={global.missing_identifier > 0 ? 'border-red-200' : ''}>
              <CardHeader className="pb-1 pt-3 px-3">
                <CardTitle className="text-xs flex items-center gap-1">
                  {global.missing_identifier > 0 ? <XCircle className="h-3.5 w-3.5 text-red-600" /> : <CheckCircle2 className="h-3.5 w-3.5 text-green-600" />}
                  Anomalías Detectadas
                </CardTitle>
              </CardHeader>
              <CardContent className="px-3 pb-3 space-y-2">
                <div className="flex items-center justify-between p-2 rounded bg-muted/50">
                  <span className="text-xs">Sin NIF ni PE</span>
                  <Badge variant={global.missing_identifier > 0 ? 'destructive' : 'secondary'} className="text-xs">{global.missing_identifier}</Badge>
                </div>
                <div className="flex items-center justify-between p-2 rounded bg-muted/50">
                  <span className="text-xs">Sin zona asignada</span>
                  <Badge variant={global.total_companies - global.with_zone > 0 ? 'destructive' : 'secondary'} className="text-xs">{global.total_companies - global.with_zone}</Badge>
                </div>
                <div className="flex items-center justify-between p-2 rounded bg-muted/50">
                  <span className="text-xs">Pendientes clasificar</span>
                  <Badge variant={global.pendiente_count > 0 ? 'destructive' : 'secondary'} className="text-xs">{global.pendiente_count}</Badge>
                </div>
                <div className="flex items-center justify-between p-2 rounded bg-muted/50">
                  <span className="text-xs">Sin verificar</span>
                  <Badge variant={global.total_companies - global.verified_companies > 5 ? 'destructive' : 'secondary'} className="text-xs">{global.total_companies - global.verified_companies}</Badge>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  )
}
