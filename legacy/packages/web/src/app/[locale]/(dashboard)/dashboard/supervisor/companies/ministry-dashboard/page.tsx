'use client'

/**
 * Supervisor Ministry Dashboard — Cross-zone ministry obligations (Sage ERP quality)
 *
 * 4 tabs:
 *   ESTRATÉGICO  — KPIs with gauges + fee type donut + zone recovery bar
 *   PILOTAJE     — Cross-zone table with recovery rates + stacked bar
 *   OPERACIONAL  — Top debtors (zones) + overdue alerts sorted by amount
 *   CONTRÔLE     — Compliance by zone (recovery gauges) + penalties breakdown
 */

import { useEffect, useMemo, useState } from 'react'
import { useTranslations } from 'next-intl'
import {
  DollarSign, TrendingUp, AlertTriangle, RefreshCw,
  CheckCircle2, Target, Gauge, Zap, BarChart3, ShieldAlert, XCircle,
} from 'lucide-react'
import {
  Chart as ChartJS, ArcElement, Tooltip, Legend,
  CategoryScale, LinearScale, BarElement, PointElement, LineElement, Filler,
} from 'chart.js'
import { Bar, Bubble, Doughnut } from 'react-chartjs-2'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useToast } from '@/hooks/use-toast'
import { companyDashboardApi } from '@/modules/companies/services/api'
import type { MinistryStatsResponse, MinistryZoneStats, CompanyAnalytics } from '@/modules/companies/types'

ChartJS.register(ArcElement, Tooltip, Legend, CategoryScale, LinearScale, BarElement, PointElement, LineElement, Filler)

function fmtXAF(n: number): string {
  if (n >= 1_000_000_000) return `${(n / 1_000_000_000).toFixed(1)}B`
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`
  return n.toLocaleString()
}

function GaugeRing({ value, max, color, size = 56 }: { value: number; max: number; color: string; size?: number }) {
  const pct = max > 0 ? Math.min(value / max, 1) : 0
  const r = (size - 6) / 2
  const circ = 2 * Math.PI * r
  return (
    <svg width={size} height={size} className="shrink-0 -rotate-90">
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="currentColor" strokeWidth={5} className="text-gray-100" />
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={5} strokeLinecap="round"
        strokeDasharray={circ} strokeDashoffset={circ * (1 - pct)} className="transition-all duration-700" />
      <text x={size / 2} y={size / 2} textAnchor="middle" dominantBaseline="central"
        className="rotate-90 origin-center fill-gray-700" fontSize={12} fontWeight="bold">
        {Math.round(pct * 100)}%
      </text>
    </svg>
  )
}

export default function SupervisorMinistryDashboardPage() {
  const t = useTranslations('supervisor')
  const { toast } = useToast()

  const [data, setData] = useState<MinistryStatsResponse | null>(null)
  const [analytics, setAnalytics] = useState<CompanyAnalytics | null>(null)
  const [loading, setLoading] = useState(true)

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    setLoading(true)
    Promise.all([
      companyDashboardApi.getMinistryStats().then(setData),
      companyDashboardApi.getAnalytics().then(setAnalytics),
    ]).catch(() => toast({ title: 'Error', variant: 'destructive' }))
      .finally(() => setLoading(false))
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // --- Derived data (MUST be before early returns) ---
  const { byZone, overdue, totalPenalties } = useMemo(() => {
    if (!data) return { byZone: [] as { code: string; paid: number; overdue: number; total: number; companies: number; penalties: number; recovery: number }[], overdue: [] as MinistryZoneStats[], totalPenalties: 0 }
    const zoneMap = new Map<string, { code: string; paid: number; overdue: number; total: number; companies: number; penalties: number; recovery: number }>()
    let penalties = 0
    for (const z of data.zones) {
      const code = z.zone_code || 'N/A'
      const ex = zoneMap.get(code) || { code, paid: 0, overdue: 0, total: 0, companies: 0, penalties: 0, recovery: 0 }
      ex.paid += z.paid_amount; ex.overdue += z.overdue_amount; ex.total += z.total_amount
      ex.companies += z.companies_count; ex.penalties += z.total_penalties
      zoneMap.set(code, ex)
      penalties += z.total_penalties
    }
    const zones = Array.from(zoneMap.values()).map(z => ({ ...z, recovery: z.total > 0 ? Math.round((z.paid / z.total) * 100) : 0 })).sort((a, b) => b.total - a.total)
    return { byZone: zones, overdue: data.zones.filter(z => z.overdue_count > 0).sort((a, b) => b.overdue_amount - a.overdue_amount), totalPenalties: penalties }
  }, [data])

  // Top debtors with risk scoring
  const topDebtors = useMemo(() => {
    if (!analytics?.top_debtors?.length) return []
    return analytics.top_debtors.map(d => ({
      ...d,
      risk: d.recovery_pct < 20 && d.debt > 100_000 ? 'critical'
        : d.recovery_pct < 40 ? 'high'
        : d.recovery_pct < 70 ? 'medium' : 'low',
    }))
  }, [analytics])

  // Monthly trend direction (last 2 months)
  const trendDirection = useMemo(() => {
    if (!analytics?.monthly_trend || analytics.monthly_trend.length < 2) return null
    const last = analytics.monthly_trend[analytics.monthly_trend.length - 1]
    const prev = analytics.monthly_trend[analytics.monthly_trend.length - 2]
    return {
      created: last.created - prev.created,
      verified: last.verified - prev.verified,
      bundle: last.bundle - prev.bundle,
    }
  }, [analytics])

  const barOptions = useMemo(() => ({
    responsive: true, maintainAspectRatio: false,
    scales: { x: { stacked: true, grid: { display: false } }, y: { stacked: true, grid: { color: '#f0f0f0' }, ticks: { callback: (v: unknown) => fmtXAF(Number(v)) } } },
    plugins: { legend: { position: 'top' as const, labels: { boxWidth: 10, font: { size: 11 } } } },
  }), [])

  if (loading) {
    return <div className="flex items-center justify-center h-[60vh]"><RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" /></div>
  }
  if (!data || data.zones.length === 0) {
    return <div className="p-6 text-center text-muted-foreground"><DollarSign className="h-10 w-10 mx-auto mb-3 opacity-30" /><p>{t('ministryDashboard.noData')}</p></div>
  }

  const { totals } = data

  // Charts
  const zoneRecoveryBar = {
    labels: byZone.map(z => z.code),
    datasets: [
      { label: t('ministryDashboard.paid'), data: byZone.map(z => z.paid), backgroundColor: '#22c55e', borderRadius: 4 },
      { label: t('ministryDashboard.overdue'), data: byZone.map(z => z.overdue), backgroundColor: '#ef4444', borderRadius: 4 },
    ],
  }
  // Penalties breakdown bar
  const penaltiesBar = {
    labels: byZone.filter(z => z.penalties > 0).map(z => z.code),
    datasets: [{
      label: 'Pénalités',
      data: byZone.filter(z => z.penalties > 0).map(z => z.penalties),
      backgroundColor: '#f59e0b',
      borderRadius: 4,
    }],
  }

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)] min-h-0">
      <div className="flex items-center justify-between mb-2 shrink-0">
        <h1 className="text-lg font-bold flex items-center gap-2"><BarChart3 className="h-5 w-5" />{t('ministryDashboard.title')}</h1>
        <Button variant="outline" size="sm" onClick={() => {
          setLoading(true)
          companyDashboardApi.getMinistryStats().then(setData).catch(() => {}).finally(() => setLoading(false))
        }}><RefreshCw className="h-3.5 w-3.5 mr-1" /></Button>
      </div>

      <Tabs defaultValue="strategic" className="flex flex-col flex-1 min-h-0">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="strategic" className="text-xs gap-1"><Target className="h-3.5 w-3.5" />{t('ministryDashboard.tabStrategic')}</TabsTrigger>
          <TabsTrigger value="piloting" className="text-xs gap-1"><Gauge className="h-3.5 w-3.5" />{t('ministryDashboard.tabPiloting')}</TabsTrigger>
          <TabsTrigger value="operational" className="text-xs gap-1"><Zap className="h-3.5 w-3.5" />{t('ministryDashboard.tabOperational')}</TabsTrigger>
          <TabsTrigger value="control" className="text-xs gap-1"><ShieldAlert className="h-3.5 w-3.5" />Control</TabsTrigger>
        </TabsList>

        {/* ═══ ESTRATÉGICO ═══ */}
        <TabsContent value="strategic" className="space-y-3 overflow-y-auto flex-1 min-h-0 pr-1">
          <div className="grid grid-cols-2 lg:grid-cols-6 gap-3">
            <Card>
              <CardContent className="pt-3 pb-2 px-4">
                <div className="text-xs text-muted-foreground flex items-center gap-1"><DollarSign className="h-3.5 w-3.5" />{t('ministryDashboard.totalAmount')}</div>
                <p className="text-2xl font-bold mt-1">{fmtXAF(totals.total_amount)}</p>
                <p className="text-[10px] text-muted-foreground">XAF</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-3 pb-2 px-4">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-xs text-muted-foreground flex items-center gap-1"><CheckCircle2 className="h-3.5 w-3.5 text-green-600" />{t('ministryDashboard.paid')}</div>
                    <p className="text-2xl font-bold mt-1 text-green-700">{fmtXAF(totals.paid_amount)}</p>
                  </div>
                  <GaugeRing value={totals.recovery_rate_pct} max={100} color={totals.recovery_rate_pct >= 60 ? '#22c55e' : '#ef4444'} />
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-3 pb-2 px-4">
                <div className="text-xs text-muted-foreground flex items-center gap-1"><DollarSign className="h-3.5 w-3.5 text-orange-600" />Restante</div>
                <p className="text-2xl font-bold mt-1 text-orange-700">{fmtXAF(totals.total_amount - totals.paid_amount)}</p>
                <p className="text-[10px] text-muted-foreground">{Math.round(((totals.total_amount - totals.paid_amount) / (totals.total_amount || 1)) * 100)}% pendiente</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-3 pb-2 px-4">
                <div className="text-xs text-muted-foreground flex items-center gap-1"><AlertTriangle className="h-3.5 w-3.5 text-red-600" />{t('ministryDashboard.overdue')}</div>
                <p className="text-2xl font-bold mt-1 text-red-700">{fmtXAF(totals.overdue_amount)}</p>
                <p className="text-[10px] text-muted-foreground">{overdue.length} zones en retard</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-3 pb-2 px-4">
                <div className="text-xs text-muted-foreground flex items-center gap-1"><TrendingUp className="h-3.5 w-3.5 text-blue-600" />{t('ministryDashboard.recoveryRate')}</div>
                <p className={`text-2xl font-bold mt-1 ${totals.recovery_rate_pct >= 60 ? 'text-green-700' : 'text-red-700'}`}>{totals.recovery_rate_pct}%</p>
              </CardContent>
            </Card>
            {totalPenalties > 0 && (
              <Card>
                <CardContent className="pt-3 pb-2 px-4">
                  <div className="text-xs text-muted-foreground flex items-center gap-1"><AlertTriangle className="h-3.5 w-3.5 text-amber-500" />Pénalités</div>
                  <p className="text-2xl font-bold mt-1 text-amber-700">{fmtXAF(totalPenalties)}</p>
                  <p className="text-[10px] text-muted-foreground">XAF en pénalités</p>
                </CardContent>
              </Card>
            )}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-5 gap-3">
            <Card className="lg:col-span-2">
              <CardHeader className="pb-1"><CardTitle className="text-sm">Par Statut d&apos;Obligation</CardTitle></CardHeader>
              <CardContent>
                <div className="h-[200px] flex items-center justify-center">
                  <Doughnut data={{
                    labels: ['Pagado', 'Vencido', 'Pendiente'],
                    datasets: [{ data: [totals.paid_amount, totals.overdue_amount, Math.max(0, totals.total_amount - totals.paid_amount - totals.overdue_amount)], backgroundColor: ['#22c55e', '#ef4444', '#f59e0b'], borderWidth: 0 }],
                  }} options={{ cutout: '55%', responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'right', labels: { boxWidth: 10, font: { size: 10 } } } } }} />
                </div>
              </CardContent>
            </Card>
            <Card className="lg:col-span-3">
              <CardHeader className="pb-1"><CardTitle className="text-sm">{t('ministryDashboard.recoveryByZone')}</CardTitle></CardHeader>
              <CardContent>
                <div className="h-[200px]"><Bar data={zoneRecoveryBar} options={barOptions} /></div>
              </CardContent>
            </Card>
          </div>

          {/* Row 3 — Bubble Risk Map + Payment Composition */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            {/* Bubble Chart: Zone Risk Assessment (3D: recovery × restante × entreprises) */}
            <Card>
              <CardHeader className="pb-0">
                <CardTitle className="text-sm">Carte de Risque par Zone</CardTitle>
                <p className="text-[10px] text-muted-foreground">X: Recouvrement % · Y: Montant restant · Taille: Nb entreprises</p>
              </CardHeader>
              <CardContent>
                <div className="h-[220px]">
                  <Bubble data={{
                    datasets: byZone.map((z) => ({
                      label: z.code,
                      data: [{ x: z.recovery, y: z.total - z.paid, r: Math.min(Math.max(Math.sqrt(z.companies) * 4, 5), 25) }],
                      backgroundColor: z.recovery >= 70 ? 'rgba(34,197,94,0.6)' : z.recovery >= 40 ? 'rgba(245,158,11,0.6)' : 'rgba(239,68,68,0.6)',
                      borderColor: z.recovery >= 70 ? '#16a34a' : z.recovery >= 40 ? '#d97706' : '#dc2626',
                      borderWidth: 1.5,
                    })),
                  }} options={{
                    responsive: true, maintainAspectRatio: false,
                    scales: {
                      x: { title: { display: true, text: 'Recouvrement %', font: { size: 10 } }, min: 0, max: 100, grid: { color: '#f0f0f0' } },
                      y: { title: { display: true, text: 'Restante (XAF)', font: { size: 10 } }, ticks: { callback: (v: unknown) => fmtXAF(Number(v)) }, grid: { color: '#f0f0f0' } },
                    },
                    plugins: {
                      legend: { display: false },
                      tooltip: { callbacks: {
                        label: (ctx) => {
                          const z = byZone[ctx.datasetIndex]
                          return [`Zone ${z.code}: ${z.companies} empresas`, `Restante: ${fmtXAF(z.total - z.paid)} XAF`, `Recouvrement: ${z.recovery}%`]
                        },
                      }},
                    },
                  }} />
                </div>
              </CardContent>
            </Card>

            {/* Horizontal Stacked: Payment Composition by Zone (Pagado/Pendiente/Vencido) */}
            <Card>
              <CardHeader className="pb-0">
                <CardTitle className="text-sm">Composition des Paiements par Zone</CardTitle>
                <p className="text-[10px] text-muted-foreground">Proportion Pagado / Pendiente / Vencido par zone</p>
              </CardHeader>
              <CardContent>
                <div className="h-[220px]">
                  <Bar data={{
                    labels: byZone.map(z => z.code),
                    datasets: [
                      { label: 'Pagado', data: byZone.map(z => z.paid), backgroundColor: '#22c55e', borderRadius: 2 },
                      { label: 'Pendiente', data: byZone.map(z => Math.max(0, z.total - z.paid - z.overdue)), backgroundColor: '#f59e0b', borderRadius: 2 },
                      { label: 'Vencido', data: byZone.map(z => z.overdue), backgroundColor: '#ef4444', borderRadius: 2 },
                    ],
                  }} options={{
                    responsive: true, maintainAspectRatio: false, indexAxis: 'y',
                    scales: {
                      x: { stacked: true, ticks: { callback: (v: unknown) => fmtXAF(Number(v)) }, grid: { color: '#f0f0f0' } },
                      y: { stacked: true, grid: { display: false } },
                    },
                    plugins: { legend: { position: 'top', labels: { boxWidth: 10, font: { size: 10 } } } },
                  }} />
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* ═══ PILOTAJE ═══ */}
        <TabsContent value="piloting" className="space-y-3 overflow-y-auto flex-1 min-h-0 pr-1">
          <Card>
            <CardHeader className="pb-1"><CardTitle className="text-sm">{t('ministryDashboard.zoneBreakdown')}</CardTitle></CardHeader>
            <CardContent className="p-0 overflow-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b bg-muted/50">
                    <th className="text-left p-2 pl-3">Zona</th>
                    <th className="text-right p-2">{t('ministryDashboard.companies')}</th>
                    <th className="text-right p-2">{t('ministryDashboard.obligations')}</th>
                    <th className="text-right p-2">{t('ministryDashboard.paid')}</th>
                    <th className="text-right p-2">{t('ministryDashboard.overdue')}</th>
                    <th className="text-right p-2">Pénalités</th>
                    <th className="text-right p-2">{t('ministryDashboard.total')}</th>
                    <th className="text-right p-2">Restante</th>
                    <th className="text-right p-2 pr-3">{t('ministryDashboard.recoveryRate')}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.zones.map((z, i) => {
                    const restante = z.total_amount - z.paid_amount
                    return (
                    <tr key={i} className="border-b hover:bg-muted/30">
                      <td className="p-2 pl-3"><Badge variant="outline" className="font-mono text-[10px]">{z.zone_code || 'N/A'}</Badge></td>
                      <td className="text-right p-2">{z.companies_count}</td>
                      <td className="text-right p-2">{z.obligations_count}</td>
                      <td className="text-right p-2 font-mono text-green-700">{z.paid_count}</td>
                      <td className="text-right p-2 font-mono text-red-700">{z.overdue_count}</td>
                      <td className="text-right p-2 font-mono text-amber-600">{fmtXAF(z.total_penalties)}</td>
                      <td className="text-right p-2 font-mono">{fmtXAF(z.total_amount)}</td>
                      <td className="text-right p-2 font-mono text-orange-700">{fmtXAF(restante)}</td>
                      <td className="text-right p-2 pr-3">
                        <Badge className={`text-[10px] ${z.recovery_rate_pct >= 70 ? 'bg-green-100 text-green-800' : z.recovery_rate_pct >= 40 ? 'bg-yellow-100 text-yellow-800' : 'bg-red-100 text-red-800'}`}>
                          {z.recovery_rate_pct}%
                        </Badge>
                      </td>
                    </tr>
                    )
                  })}
                </tbody>
                <tfoot>
                  <tr className="border-t-2 bg-muted/30 font-bold">
                    <td className="p-2 pl-3">Total</td>
                    <td className="text-right p-2">{data.zones.reduce((s, z) => s + z.companies_count, 0)}</td>
                    <td className="text-right p-2">{data.zones.reduce((s, z) => s + z.obligations_count, 0)}</td>
                    <td className="text-right p-2 font-mono text-green-700">{data.zones.reduce((s, z) => s + z.paid_count, 0)}</td>
                    <td className="text-right p-2 font-mono text-red-700">{data.zones.reduce((s, z) => s + z.overdue_count, 0)}</td>
                    <td className="text-right p-2 font-mono text-amber-600">{fmtXAF(data.zones.reduce((s, z) => s + z.total_penalties, 0))}</td>
                    <td className="text-right p-2 font-mono">{fmtXAF(totals.total_amount)}</td>
                    <td className="text-right p-2 font-mono text-orange-700">{fmtXAF(totals.total_amount - totals.paid_amount)}</td>
                    <td className="text-right p-2 pr-3">
                      <Badge className={`text-[10px] ${totals.recovery_rate_pct >= 70 ? 'bg-green-100 text-green-800' : totals.recovery_rate_pct >= 40 ? 'bg-yellow-100 text-yellow-800' : 'bg-red-100 text-red-800'}`}>
                        {totals.recovery_rate_pct}%
                      </Badge>
                    </td>
                  </tr>
                </tfoot>
              </table>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ═══ OPERACIONAL ═══ */}
        <TabsContent value="operational" className="space-y-3 overflow-y-auto flex-1 min-h-0 pr-1">
          {/* Trend direction banner */}
          {trendDirection && (
            <div className="flex items-center gap-4 p-2.5 bg-muted/30 rounded-lg border text-xs">
              <span className="text-muted-foreground font-medium">Tendencia mes:</span>
              <span className={trendDirection.created >= 0 ? 'text-blue-600' : 'text-red-600'}>
                {trendDirection.created >= 0 ? '↑' : '↓'} {Math.abs(trendDirection.created)} creadas
              </span>
              <span className={trendDirection.verified >= 0 ? 'text-green-600' : 'text-red-600'}>
                {trendDirection.verified >= 0 ? '↑' : '↓'} {Math.abs(trendDirection.verified)} verificadas
              </span>
            </div>
          )}

          {/* Top debtor COMPANIES with risk scoring */}
          {topDebtors.length > 0 && (
            <Card>
              <CardHeader className="pb-2"><CardTitle className="text-sm">Top empresas deudoras — Scoring de riesgo</CardTitle></CardHeader>
              <CardContent className="p-0">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b bg-muted/50">
                      <th className="text-left p-2 pl-3">#</th>
                      <th className="text-left p-2">Empresa</th>
                      <th className="text-left p-2">Identificador</th>
                      <th className="text-left p-2">Zona</th>
                      <th className="text-right p-2">Deuda</th>
                      <th className="text-right p-2">Recovery</th>
                      <th className="text-center p-2 pr-3">Riesgo</th>
                    </tr>
                  </thead>
                  <tbody>
                    {topDebtors.map((d, i) => (
                      <tr key={d.id} className="border-b hover:bg-muted/30">
                        <td className="p-2 pl-3 font-bold text-muted-foreground">{i + 1}</td>
                        <td className="p-2 font-medium max-w-[180px] truncate">{d.legal_name}</td>
                        <td className="p-2 font-mono">{d.nif || d.registration_number || '—'}</td>
                        <td className="p-2"><Badge variant="outline" className="font-mono text-[10px]">{d.zone_code || '—'}</Badge></td>
                        <td className="p-2 text-right font-mono text-red-700">{fmtXAF(d.debt)}</td>
                        <td className="p-2 text-right">{d.recovery_pct}%</td>
                        <td className="p-2 text-center pr-3">
                          <Badge className={`text-[9px] ${
                            d.risk === 'critical' ? 'bg-red-600 text-white' :
                            d.risk === 'high' ? 'bg-red-100 text-red-800' :
                            d.risk === 'medium' ? 'bg-yellow-100 text-yellow-800' :
                            'bg-green-100 text-green-800'
                          }`}>
                            {d.risk === 'critical' ? 'CRÍTICO' : d.risk === 'high' ? 'ALTO' : d.risk === 'medium' ? 'MEDIO' : 'BAJO'}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </CardContent>
            </Card>
          )}

          {/* Top debtor zones */}
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-sm">Top zones endeudadas</CardTitle></CardHeader>
            <CardContent className="space-y-2">
              {byZone.filter(z => z.overdue > 0).slice(0, 5).map((z, i) => (
                <div key={z.code} className="flex items-center gap-3 p-2 rounded border">
                  <span className="text-xs font-bold text-muted-foreground w-5">#{i + 1}</span>
                  <Badge variant="outline" className="font-mono text-xs">{z.code}</Badge>
                  <div className="flex-1">
                    <div className="flex items-center justify-between">
                      <span className="text-xs">{z.companies} empresas</span>
                      <span className="text-xs font-bold text-red-700">{fmtXAF(z.overdue)} XAF</span>
                    </div>
                    <div className="h-1.5 w-full bg-gray-100 rounded-full mt-1 overflow-hidden">
                      <div className="h-full rounded-full" style={{ width: `${z.recovery}%`, backgroundColor: z.recovery >= 60 ? '#22c55e' : z.recovery >= 30 ? '#eab308' : '#ef4444' }} />
                    </div>
                  </div>
                  <span className="text-xs font-mono">{z.recovery}%</span>
                </div>
              ))}
              {byZone.filter(z => z.overdue > 0).length === 0 && (
                <div className="text-center py-4 text-muted-foreground text-sm"><CheckCircle2 className="h-5 w-5 mx-auto mb-1 text-green-500" />Sin deudas pendientes</div>
              )}
            </CardContent>
          </Card>

          {/* Overdue alerts */}
          <Card>
            <CardHeader className="pb-1">
              <CardTitle className="text-sm flex items-center gap-2 text-red-700"><AlertTriangle className="h-4 w-4" />{t('ministryDashboard.overdueZones')} ({overdue.length})</CardTitle>
            </CardHeader>
            <CardContent>
              {overdue.length === 0 ? (
                <div className="text-center py-6 text-muted-foreground"><CheckCircle2 className="h-6 w-6 mx-auto mb-2 text-green-600" /><p className="text-sm">{t('ministryDashboard.noOverdue')}</p></div>
              ) : (
                <div className="space-y-2">
                  {overdue.map((z, i) => (
                    <div key={i} className="flex items-center justify-between p-2.5 bg-red-50 rounded border border-red-100">
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="font-mono text-xs">{z.zone_code || 'N/A'}</Badge>
                        <span className="text-sm">{z.fee_type}</span>
                        <Badge variant="secondary" className="text-[10px]">{z.overdue_count} {t('ministryDashboard.overdueCount')}</Badge>
                      </div>
                      <div className="text-right">
                        <p className="text-sm font-bold text-red-700">{fmtXAF(z.overdue_amount)}</p>
                        <p className="text-[10px] text-muted-foreground">{z.companies_count} {t('ministryDashboard.companies')}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ═══ CONTRÔLE ═══ */}
        <TabsContent value="control" className="space-y-3 overflow-y-auto flex-1 min-h-0 pr-1">
          {/* Recovery gauges by zone */}
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-sm">Compliance par zone — Taux de recouvrement</CardTitle></CardHeader>
            <CardContent>
              <div className="grid grid-cols-3 md:grid-cols-5 lg:grid-cols-9 gap-3">
                {byZone.map(z => (
                  <div key={z.code} className="text-center">
                    <GaugeRing value={z.recovery} max={100} color={z.recovery >= 70 ? '#22c55e' : z.recovery >= 40 ? '#eab308' : '#ef4444'} size={52} />
                    <p className="text-[10px] font-mono font-semibold mt-1">{z.code}</p>
                    <p className="text-[9px] text-muted-foreground">{fmtXAF(z.total)}</p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Penalties bar chart */}
          {penaltiesBar.labels.length > 0 && (
            <Card>
              <CardHeader className="pb-1"><CardTitle className="text-sm">Pénalités par zone</CardTitle></CardHeader>
              <CardContent>
                <div className="h-[180px]">
                  <Bar data={penaltiesBar} options={{
                    responsive: true, maintainAspectRatio: false,
                    scales: { x: { grid: { display: false } }, y: { ticks: { callback: (v: unknown) => fmtXAF(Number(v)) } } },
                    plugins: { legend: { display: false } },
                  }} />
                </div>
              </CardContent>
            </Card>
          )}

          {/* Anomalies */}
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-sm">Anomalías detectadas</CardTitle></CardHeader>
            <CardContent className="space-y-1.5">
              {totals.recovery_rate_pct < 40 && (
                <div className="flex items-center gap-2 text-xs"><XCircle className="h-3.5 w-3.5 text-red-500" /><span>Taux global &lt; 40% — <strong className="text-red-600">{totals.recovery_rate_pct}%</strong></span></div>
              )}
              {byZone.filter(z => z.recovery < 20).length > 0 && (
                <div className="flex items-center gap-2 text-xs"><XCircle className="h-3.5 w-3.5 text-red-500" /><span>{byZone.filter(z => z.recovery < 20).length} zones avec recovery &lt; 20%</span></div>
              )}
              {totalPenalties > 100_000 && (
                <div className="flex items-center gap-2 text-xs"><XCircle className="h-3.5 w-3.5 text-amber-500" /><span>Pénalités élevées : <strong className="text-amber-600">{fmtXAF(totalPenalties)} XAF</strong></span></div>
              )}
              {totals.recovery_rate_pct >= 40 && byZone.filter(z => z.recovery < 20).length === 0 && totalPenalties <= 100_000 && (
                <div className="flex items-center gap-2 text-xs"><CheckCircle2 className="h-3.5 w-3.5 text-green-500" /><span className="text-green-700">Sin anomalías detectadas</span></div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
