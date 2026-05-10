'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useLocale, useTranslations } from 'next-intl'
import { useToast } from '@/hooks/use-toast'
import {
  ArrowLeft, BarChart3, MapPin, Trophy, TrendingUp, Users, Map,
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { inspectionApi } from '@/modules/inspections/services/api'
import { InspectionTrendChart } from '@/modules/inspections/components/InspectionTrendChart'
import { ZoneAnalyticsTable } from '@/modules/inspections/components/ZoneAnalyticsTable'
import { fmtXAF } from '@/modules/inspections/utils/formatters'
import type {
  TrendResponse,
  ZoneAnalyticsResponse,
  PriorityZonesResponse,
  PriorityZoneItem,
  AgentPerformanceResponse,
  CompareResponse,
  CompareItem,
} from '@/modules/inspections/types'
import { cn } from '@/core/utils'

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const TIER_COLORS: Record<string, string> = {
  A: 'bg-blue-500',
  B: 'bg-green-500',
  C: 'bg-yellow-500',
  D: 'bg-red-500',
}

const TIER_TEXT: Record<string, string> = {
  A: 'text-blue-700 border-blue-200 bg-blue-50',
  B: 'text-green-700 border-green-200 bg-green-50',
  C: 'text-yellow-700 border-yellow-200 bg-yellow-50',
  D: 'text-red-700 border-red-200 bg-red-50',
}

type Granularity = 'daily' | 'weekly' | 'monthly'

function defaultDateFrom(): string {
  const d = new Date()
  d.setDate(d.getDate() - 30)
  return d.toISOString().slice(0, 10)
}

function defaultDateTo(): string {
  return new Date().toISOString().slice(0, 10)
}

// ---------------------------------------------------------------------------
// Compare metric helpers
// ---------------------------------------------------------------------------

interface MetricDef {
  key: keyof CompareItem
  labelKey: string
  format: 'number' | 'percent' | 'currency'
  higherIsBetter: boolean
}

const COMPARE_METRICS: MetricDef[] = [
  { key: 'inspections', labelKey: 'perf.inspections', format: 'number', higherIsBetter: true },
  { key: 'conforme', labelKey: 'trend.conformes', format: 'number', higherIsBetter: true },
  { key: 'non_conforme', labelKey: 'trend.nonConformes', format: 'number', higherIsBetter: false },
  { key: 'conformity_rate', labelKey: 'zone.conformity', format: 'percent', higherIsBetter: true },
  { key: 'collections', labelKey: 'zone.collections', format: 'number', higherIsBetter: true },
  { key: 'collected_amount', labelKey: 'zone.amount', format: 'currency', higherIsBetter: true },
  { key: 'med_count', labelKey: 'zone.med', format: 'number', higherIsBetter: false },
  { key: 'seal_count', labelKey: 'zone.seals', format: 'number', higherIsBetter: false },
]

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function AnalyticsPage() {
  const locale = useLocale()
  const router = useRouter()
  const { toast } = useToast()
  const t = useTranslations('inspection')

  // --- Date range ---
  const [dateFrom, setDateFrom] = useState(defaultDateFrom)
  const [dateTo, setDateTo] = useState(defaultDateTo)
  const [granularity, setGranularity] = useState<Granularity>('weekly')

  // --- Data ---
  const [trends, setTrends] = useState<TrendResponse | null>(null)
  const [zones, setZones] = useState<ZoneAnalyticsResponse | null>(null)
  const [priority, setPriority] = useState<PriorityZonesResponse | null>(null)
  const [agents, setAgents] = useState<AgentPerformanceResponse | null>(null)

  // --- Loading ---
  const [loadingTrends, setLoadingTrends] = useState(true)
  const [loadingZones, setLoadingZones] = useState(true)
  const [loadingPriority, setLoadingPriority] = useState(true)
  const [_loadingAgents, setLoadingAgents] = useState(true)

  // --- Compare ---
  const [compareType, setCompareType] = useState<'agents' | 'zones'>('agents')
  const [compareId1, setCompareId1] = useState('')
  const [compareId2, setCompareId2] = useState('')
  const [compareResult, setCompareResult] = useState<CompareResponse | null>(null)
  const [loadingCompare, setLoadingCompare] = useState(false)

  // --- Bottom tab ---
  const [bottomTab, setBottomTab] = useState<'zones' | 'compare'>('zones')

  // --- Fetch all data ---
  const fetchAll = useCallback(async () => {
    const params = { date_from: dateFrom, date_to: dateTo }

    setLoadingTrends(true)
    setLoadingZones(true)
    setLoadingPriority(true)
    setLoadingAgents(true)

    const [trendsRes, zonesRes, priorityRes, agentsRes] = await Promise.allSettled([
      inspectionApi.getTrends({ ...params, granularity }),
      inspectionApi.getZoneAnalytics(params),
      inspectionApi.getPriorityZones(5),
      inspectionApi.getAgentPerformance(params),
    ])

    if (trendsRes.status === 'fulfilled') {
      setTrends(trendsRes.value)
    } else {
      toast({ title: t('common.error'), description: t('analytics.trends'), variant: 'destructive' })
    }
    setLoadingTrends(false)

    if (zonesRes.status === 'fulfilled') {
      setZones(zonesRes.value)
    } else {
      toast({ title: t('common.error'), description: t('analytics.noZoneData'), variant: 'destructive' })
    }
    setLoadingZones(false)

    if (priorityRes.status === 'fulfilled') {
      setPriority(priorityRes.value)
    } else {
      toast({ title: t('common.error'), description: t('analytics.priorityZones'), variant: 'destructive' })
    }
    setLoadingPriority(false)

    if (agentsRes.status === 'fulfilled') {
      setAgents(agentsRes.value)
    } else {
      toast({ title: t('common.error'), description: t('perf.empty'), variant: 'destructive' })
    }
    setLoadingAgents(false)
  }, [dateFrom, dateTo, granularity, toast])

  useEffect(() => { fetchAll() }, [fetchAll])

  // Reset compare result when type/selections change
  useEffect(() => {
    setCompareResult(null)
    setCompareId1('')
    setCompareId2('')
  }, [compareType])

  // --- Refetch trends on granularity change ---
  const handleGranularityChange = useCallback((g: Granularity) => {
    setGranularity(g)
    setLoadingTrends(true)
    inspectionApi.getTrends({ date_from: dateFrom, date_to: dateTo, granularity: g })
      .then(setTrends)
      .catch(() => toast({ title: t('common.error'), description: t('analytics.trends'), variant: 'destructive' }))
      .finally(() => setLoadingTrends(false))
  }, [dateFrom, dateTo, toast])

  // --- Compare handler ---
  const handleCompare = useCallback(async () => {
    if (!compareId1 || !compareId2 || compareId1 === compareId2) return
    setLoadingCompare(true)
    try {
      const res = await inspectionApi.getComparison({
        compare_type: compareType,
        id1: compareId1,
        id2: compareId2,
        date_from: dateFrom,
        date_to: dateTo,
      })
      setCompareResult(res)
    } catch {
      toast({ title: t('common.error'), description: t('analytics.compare'), variant: 'destructive' })
    } finally {
      setLoadingCompare(false)
    }
  }, [compareType, compareId1, compareId2, dateFrom, dateTo, toast])

  // --- Dropdown options ---
  const agentOptions = useMemo(() =>
    (agents?.items ?? []).map(a => ({ value: a.agent_id, label: a.agent_name })),
    [agents],
  )
  const zoneOptions = useMemo(() =>
    (zones?.items ?? []).map(z => ({ value: z.zone_id ?? z.zone_code, label: `${z.zone_code} - ${z.zone_name}` })),
    [zones],
  )
  const compareOptions = compareType === 'agents' ? agentOptions : zoneOptions

  const priorityTop5 = useMemo(() =>
    (priority?.items ?? []).slice(0, 5).sort((a, b) => b.priority_score - a.priority_score),
    [priority],
  )

  // =========================================================================
  // RENDER
  // =========================================================================

  return (
    <div className="flex h-full flex-col gap-3 p-4">
      {/* ---- HEADER ---- */}
      <div className="flex flex-wrap items-center gap-3">
        <Button
          variant="ghost"
          size="sm"
          className="gap-1.5"
          onClick={() => router.push(`/${locale}/dashboard/supervisor/inspections`)}
        >
          <ArrowLeft className="h-4 w-4" />
          {t('analytics.back')}
        </Button>

        <div className="flex items-center gap-2">
          <BarChart3 className="h-5 w-5 text-primary" />
          <h1 className="text-lg font-semibold">{t('analytics.title')}</h1>
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

      {/* ---- TOP ROW ---- */}
      <div className="grid min-h-0 flex-1 grid-cols-3 gap-3" style={{ maxHeight: '45%' }}>
        {/* Trend chart (2/3) */}
        <Card className="col-span-2 flex flex-col overflow-hidden">
          <CardHeader className="flex-row items-center gap-2 space-y-0 pb-2 pt-3 px-4">
            <TrendingUp className="h-4 w-4 text-primary" />
            <CardTitle className="text-sm font-medium">{t('analytics.trends')}</CardTitle>
          </CardHeader>
          <CardContent className="flex-1 px-4 pb-3">
            <InspectionTrendChart
              data={trends?.data ?? []}
              granularity={granularity}
              onGranularityChange={handleGranularityChange}
              loading={loadingTrends}
              height={220}
            />
          </CardContent>
        </Card>

        {/* Priority zones (1/3) */}
        <Card className="flex flex-col overflow-hidden">
          <CardHeader className="flex-row items-center gap-2 space-y-0 pb-2 pt-3 px-4">
            <MapPin className="h-4 w-4 text-destructive" />
            <CardTitle className="text-sm font-medium">{t('analytics.priorityZones')}</CardTitle>
          </CardHeader>
          <CardContent className="flex-1 overflow-y-auto px-4 pb-3">
            {loadingPriority ? (
              <div className="space-y-3">
                {Array.from({ length: 5 }).map((_, i) => (
                  <Skeleton key={i} className="h-12 w-full rounded-md" />
                ))}
              </div>
            ) : priorityTop5.length === 0 ? (
              <p className="py-6 text-center text-xs text-muted-foreground">
                {t('zone.empty')}
              </p>
            ) : (
              <div className="space-y-2">
                {priorityTop5.map((z: PriorityZoneItem, idx: number) => (
                  <PriorityZoneCard key={z.zone_code + idx} zone={z} rank={idx + 1} locale={locale} />
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* ---- BOTTOM ROW ---- */}
      <Card className="flex min-h-0 flex-1 flex-col overflow-hidden">
        <Tabs
          value={bottomTab}
          onValueChange={v => setBottomTab(v as 'zones' | 'compare')}
          className="flex flex-1 flex-col overflow-hidden"
        >
          <div className="flex items-center border-b px-4 pt-2">
            <TabsList className="h-8">
              <TabsTrigger value="zones" className="gap-1.5 text-xs">
                <Map className="h-3.5 w-3.5" />
                {t('analytics.compareZones')}
              </TabsTrigger>
              <TabsTrigger value="compare" className="gap-1.5 text-xs">
                <Trophy className="h-3.5 w-3.5" />
                {t('analytics.compare')}
              </TabsTrigger>
            </TabsList>
          </div>

          {/* Tab: Zones */}
          <TabsContent value="zones" className="mt-0 flex-1 overflow-y-auto p-4">
            <ZoneAnalyticsTable
              data={zones?.items ?? []}
              loading={loadingZones}
              summary={zones ? {
                total_zones: zones.total_zones,
                covered_zones: zones.covered_zones,
                stale_zones: zones.stale_zones,
              } : undefined}
            />
          </TabsContent>

          {/* Tab: Compare */}
          <TabsContent value="compare" className="mt-0 flex-1 overflow-y-auto p-4">
            <div className="space-y-4">
              {/* Controls */}
              <div className="flex flex-wrap items-end gap-3">
                <div className="w-40">
                  <label className="mb-1 block text-xs font-medium text-muted-foreground">{t('analytics.compareType')}</label>
                  <Select value={compareType} onValueChange={v => setCompareType(v as 'agents' | 'zones')}>
                    <SelectTrigger className="h-8 text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="agents">
                        <span className="flex items-center gap-1.5"><Users className="h-3.5 w-3.5" />{t('analytics.compareAgents')}</span>
                      </SelectItem>
                      <SelectItem value="zones">
                        <span className="flex items-center gap-1.5"><MapPin className="h-3.5 w-3.5" />{t('analytics.compareZones')}</span>
                      </SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="w-52">
                  <label className="mb-1 block text-xs font-medium text-muted-foreground">
                    {t('analytics.select1')}
                  </label>
                  <Select value={compareId1} onValueChange={setCompareId1}>
                    <SelectTrigger className="h-8 text-xs">
                      <SelectValue placeholder={t('analytics.selectPlaceholder')} />
                    </SelectTrigger>
                    <SelectContent>
                      {compareOptions.map(o => (
                        <SelectItem key={o.value} value={o.value} disabled={o.value === compareId2}>
                          {o.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="w-52">
                  <label className="mb-1 block text-xs font-medium text-muted-foreground">
                    {t('analytics.select2')}
                  </label>
                  <Select value={compareId2} onValueChange={setCompareId2}>
                    <SelectTrigger className="h-8 text-xs">
                      <SelectValue placeholder={t('analytics.selectPlaceholder')} />
                    </SelectTrigger>
                    <SelectContent>
                      {compareOptions.map(o => (
                        <SelectItem key={o.value} value={o.value} disabled={o.value === compareId1}>
                          {o.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <Button
                  size="sm"
                  className="h-8"
                  disabled={!compareId1 || !compareId2 || compareId1 === compareId2 || loadingCompare}
                  onClick={handleCompare}
                >
                  {loadingCompare ? (
                    <span className="flex items-center gap-1.5">
                      <span className="h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent" />
                      ...
                    </span>
                  ) : (
                    <span className="flex items-center gap-1.5">
                      <Trophy className="h-3.5 w-3.5" />
                      {t('analytics.compareAction')}
                    </span>
                  )}
                </Button>
              </div>

              {/* Compare results */}
              {compareResult && compareResult.items.length === 2 && (
                <CompareCards
                  items={compareResult.items}
                  locale={locale}
                  t={t}
                />
              )}

              {!compareResult && !loadingCompare && (
                <div className="flex h-32 items-center justify-center text-sm text-muted-foreground">
                  {t('analytics.noCompareData')}
                </div>
              )}
            </div>
          </TabsContent>
        </Tabs>
      </Card>
    </div>
  )
}

// ===========================================================================
// Sub-components
// ===========================================================================

function PriorityZoneCard({
  zone, rank, locale,
}: {
  zone: PriorityZoneItem
  rank: number
  locale: string
}) {
  const t = useTranslations('inspection')
  const tierBg = TIER_COLORS[zone.zone_tier] ?? TIER_COLORS.D
  const tierStyle = TIER_TEXT[zone.zone_tier] ?? TIER_TEXT.D
  const scoreWidth = Math.min(Math.max(zone.priority_score, 0), 100)

  return (
    <div className="flex items-center gap-2.5 rounded-lg border p-2.5">
      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-muted text-[10px] font-bold tabular-nums">
        {rank}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5">
          <span className="truncate text-xs font-medium">{zone.zone_code}</span>
          <Badge variant="outline" className={cn('px-1.5 py-0 text-[10px] font-semibold', tierStyle)}>
            {zone.zone_tier}
          </Badge>
          <span className="truncate text-[10px] text-muted-foreground">{zone.zone_name}</span>
        </div>
        <div className="mt-1 flex items-center gap-2">
          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
            <div
              className={cn('h-full rounded-full', tierBg)}
              style={{ width: `${scoreWidth}%` }}
            />
          </div>
          <span className="text-[10px] font-semibold tabular-nums">{zone.priority_score.toFixed(0)}</span>
        </div>
        <div className="mt-0.5 flex gap-3 text-[10px] text-muted-foreground">
          <span>{t('analytics.daysAgo', { days: zone.days_since_last_inspection })}</span>
          <span>{t('analytics.pendingCount', { count: zone.pending_obligations })}</span>
          <span>{fmtXAF(zone.pending_amount, locale)}</span>
        </div>
      </div>
    </div>
  )
}

function CompareCards({
  items,
  locale,
  t,
}: {
  items: CompareItem[]
  locale: string
  t: (key: string) => string
}) {
  const [a, b] = items

  function formatVal(metric: MetricDef, value: number): string {
    switch (metric.format) {
      case 'percent':
        return `${value.toFixed(1)}%`
      case 'currency':
        return fmtXAF(value, locale)
      default:
        return String(value)
    }
  }

  function isWinner(metric: MetricDef, valA: number, valB: number, side: 'a' | 'b'): boolean {
    if (valA === valB) return false
    const aWins = metric.higherIsBetter ? valA > valB : valA < valB
    return side === 'a' ? aWins : !aWins
  }

  return (
    <div className="grid grid-cols-2 gap-4">
      {[a, b].map((item, sideIdx) => (
        <Card key={item.label} className="overflow-hidden">
          <CardHeader className="bg-muted/40 pb-2 pt-3 px-4">
            <CardTitle className="flex items-center gap-2 text-sm">
              <Users className="h-4 w-4 text-primary" />
              {item.label}
            </CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-3 pt-2">
            <div className="space-y-1.5">
              {COMPARE_METRICS.map(metric => {
                const val = item[metric.key] as number
                const otherVal = (sideIdx === 0 ? b : a)[metric.key] as number
                const winner = isWinner(metric, val, otherVal, sideIdx === 0 ? 'a' : 'b')

                return (
                  <div
                    key={metric.key}
                    className={cn(
                      'flex items-center justify-between rounded px-2 py-1 text-xs',
                      winner ? 'bg-green-50' : '',
                    )}
                  >
                    <span className="text-muted-foreground">{t(metric.labelKey)}</span>
                    <span className={cn('font-semibold tabular-nums', winner ? 'text-green-700' : '')}>
                      {formatVal(metric, val)}
                    </span>
                  </div>
                )
              })}
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
