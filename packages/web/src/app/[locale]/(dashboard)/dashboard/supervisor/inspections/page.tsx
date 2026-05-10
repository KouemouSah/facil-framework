'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useLocale, useTranslations } from 'next-intl'
import { useToast } from '@/hooks/use-toast'
import {
  Shield, ClipboardCheck, CheckCircle2, XCircle, Lock,
  DollarSign, AlertTriangle, Clock, Wallet, ArrowRight,
  Users, MapPin, CalendarDays, BarChart3, ChevronDown,
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table'
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel,
  AlertDialogContent, AlertDialogDescription, AlertDialogFooter,
  AlertDialogHeader, AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Skeleton } from '@/components/ui/skeleton'
import { Progress } from '@/components/ui/progress'
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Checkbox } from '@/components/ui/checkbox'
import { inspectionApi } from '@/modules/inspections/services/api'
import { INSPECTION_STATUS_CONFIG, fmtXAF } from '@/modules/inspections/utils/formatters'
import { ExportButton } from '@/modules/inspections/components/ExportButton'
import { AgentPerformanceTable } from '@/modules/inspections/components/AgentPerformanceTable'
import { ZoneAnalyticsTable } from '@/modules/inspections/components/ZoneAnalyticsTable'
import { MissionCalendar } from '@/modules/inspections/components/MissionCalendar'
import { MissionPlanPanel } from '@/modules/inspections/components/MissionPlanPanel'
import { LiveStatusPanel } from '@/modules/inspections/components/LiveStatusPanel'
import { LocationFilter, useLocationFilterState } from '@/modules/inspections/components/LocationFilter'
import { useAgentProfile } from '@/modules/agent-dashboard/hooks/useAgentDashboard'
import type {
  SupervisorDashboard, FieldPayment,
  AgentPerformanceResponse, ZoneAnalyticsResponse,
} from '@/modules/inspections/types'

// ============================================================
// Tab configuration
// ============================================================
const TAB_KEYS = ['overview', 'payments', 'seals', 'agents', 'missions', 'zones'] as const
type TabKey = typeof TAB_KEYS[number]
const TAB_ICONS: Record<TabKey, React.ElementType> = {
  overview: BarChart3, payments: Wallet, seals: Lock,
  agents: Users, missions: CalendarDays, zones: MapPin,
}

export default function SupervisorInspectionDashboard() {
  const locale = useLocale()
  const router = useRouter()
  const { toast } = useToast()
  const t = useTranslations('inspection')

  // --- Agent profile for location filter ---
  const { data: agentProfile } = useAgentProfile()

  // --- Location filter: defaults to supervisor's own site ---
  const { locationFilter, setLocationFilter } = useLocationFilterState(agentProfile)

  // --- Core dashboard ---
  const [data, setData] = useState<SupervisorDashboard | null>(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<TabKey>('overview')

  // --- Versements (tab 2) ---
  const [fieldPayments, setFieldPayments] = useState<FieldPayment[]>([])
  const [fieldTotal, setFieldTotal] = useState(0)
  const [loadingField, setLoadingField] = useState(false)
  const [confirmPayment, setConfirmPayment] = useState<FieldPayment | null>(null)
  const [validating, setValidating] = useState(false)

  // --- Batch selection ---
  const [selectedPayments, setSelectedPayments] = useState<Set<string>>(new Set())
  const [batchValidating, setBatchValidating] = useState(false)
  const [batchProgress, setBatchProgress] = useState({ current: 0, total: 0 })
  const [showBatchConfirm, setShowBatchConfirm] = useState(false)

  // --- Lazy-loaded tab data ---
  const [agentData, setAgentData] = useState<AgentPerformanceResponse | null>(null)
  const [loadingAgents, setLoadingAgents] = useState(false)
  const [zoneData, setZoneData] = useState<ZoneAnalyticsResponse | null>(null)
  const [loadingZones, setLoadingZones] = useState(false)

  // --- Missions ---
  const [missionWeekStart, setMissionWeekStart] = useState<string>(() => {
    const now = new Date()
    const day = now.getDay()
    const diff = day === 0 ? -6 : 1 - day
    const mon = new Date(now)
    mon.setDate(now.getDate() + diff)
    return mon.toISOString().slice(0, 10)
  })
  const [missions, setMissions] = useState<import('@/modules/inspections/types').MissionListItem[]>([])
  const [loadingMissions, setLoadingMissions] = useState(false)
  const [showMissionPlan, setShowMissionPlan] = useState(false)

  // ============================================================
  // Data fetching
  // ============================================================

  const fetchDashboard = useCallback(async () => {
    try {
      setLoading(true)
      const result = await inspectionApi.getSupervisorDashboard(locationFilter || undefined)
      setData(result)
    } catch {
      toast({ title: t('common.error'), description: 'Dashboard', variant: 'destructive' })
    } finally {
      setLoading(false)
    }
  }, [toast, t, locationFilter])

  const fetchFieldPayments = useCallback(async () => {
    try {
      setLoadingField(true)
      const result = await inspectionApi.getSupervisorReconciliation()
      setFieldPayments(result.items as FieldPayment[])
      setFieldTotal(result.total_amount)
      setSelectedPayments(new Set())
    } catch {
      toast({ title: t('common.error'), variant: 'destructive' })
    } finally {
      setLoadingField(false)
    }
  }, [toast, t])

  const fetchAgents = useCallback(async () => {
    if (agentData) return
    try {
      setLoadingAgents(true)
      const result = await inspectionApi.getAgentPerformance()
      setAgentData(result)
    } catch {
      toast({ title: t('common.error'), variant: 'destructive' })
    } finally {
      setLoadingAgents(false)
    }
  }, [agentData, toast, t])

  const fetchZones = useCallback(async () => {
    if (zoneData) return
    try {
      setLoadingZones(true)
      const result = await inspectionApi.getZoneAnalytics()
      setZoneData(result)
    } catch {
      toast({ title: t('common.error'), variant: 'destructive' })
    } finally {
      setLoadingZones(false)
    }
  }, [zoneData, toast, t])

  const fetchMissions = useCallback(async (weekStart?: string) => {
    const start = weekStart || missionWeekStart
    const end = new Date(start + 'T00:00:00')
    end.setDate(end.getDate() + 6)
    try {
      setLoadingMissions(true)
      const result = await inspectionApi.listMissions({
        date_from: start,
        date_to: end.toISOString().slice(0, 10),
        page_size: 50,
        entity_location_id: locationFilter || undefined,
      })
      setMissions(result.items)
    } catch {
      toast({ title: t('common.error'), variant: 'destructive' })
    } finally {
      setLoadingMissions(false)
    }
  }, [missionWeekStart, locationFilter, toast, t])

  useEffect(() => { fetchDashboard() }, [fetchDashboard])

  // Lazy load tab data
  const handleTabChange = useCallback((tab: string) => {
    setActiveTab(tab as TabKey)
    if (tab === 'payments') fetchFieldPayments()
    else if (tab === 'agents') fetchAgents()
    else if (tab === 'zones') fetchZones()
    else if (tab === 'missions') fetchMissions()
  }, [fetchFieldPayments, fetchAgents, fetchZones, fetchMissions])

  // ============================================================
  // Payment validation
  // ============================================================

  const handleValidatePayment = useCallback(async () => {
    if (!confirmPayment) return
    try {
      setValidating(true)
      const result = await inspectionApi.validateFieldReconciliation(confirmPayment.id)
      setFieldPayments(prev => prev.filter(p => p.id !== confirmPayment.id))
      setFieldTotal(prev => prev - (confirmPayment.total_amount || 0))
      setSelectedPayments(prev => { const n = new Set(prev); n.delete(confirmPayment.id); return n })
      setConfirmPayment(null)
      toast({
        title: t('payments.validated'),
        description: t('payments.routedDesc', { count: result.routed_obligations || 0 }),
      })
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : t('common.error')
      toast({ title: t('common.error'), description: msg, variant: 'destructive' })
    } finally {
      setValidating(false)
    }
  }, [confirmPayment, toast, t])

  // ============================================================
  // Batch validation
  // ============================================================

  const selectedPaymentsList = useMemo(
    () => fieldPayments.filter(p => selectedPayments.has(p.id)),
    [fieldPayments, selectedPayments]
  )
  const selectedTotal = useMemo(
    () => selectedPaymentsList.reduce((sum, p) => sum + (p.total_amount || 0), 0),
    [selectedPaymentsList]
  )

  const togglePayment = useCallback((id: string) => {
    setSelectedPayments(prev => {
      const n = new Set(prev)
      if (n.has(id)) n.delete(id); else n.add(id)
      return n
    })
  }, [])

  const toggleAllPayments = useCallback(() => {
    setSelectedPayments(prev =>
      prev.size === fieldPayments.length
        ? new Set()
        : new Set(fieldPayments.map(p => p.id))
    )
  }, [fieldPayments])

  const handleBatchValidate = useCallback(async () => {
    const ids = Array.from(selectedPayments)
    if (ids.length === 0) return
    setBatchValidating(true)
    setBatchProgress({ current: 0, total: ids.length })
    setShowBatchConfirm(false)
    let successCount = 0
    for (let i = 0; i < ids.length; i++) {
      setBatchProgress({ current: i + 1, total: ids.length })
      try {
        await inspectionApi.validateFieldReconciliation(ids[i])
        successCount++
        setFieldPayments(prev => prev.filter(p => p.id !== ids[i]))
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : ids[i]
        toast({ title: t('common.error'), description: msg, variant: 'destructive' })
      }
    }
    setSelectedPayments(new Set())
    setBatchValidating(false)
    if (successCount > 0) {
      toast({ title: t('payments.validated'), description: `${successCount}/${ids.length}` })
      // Refresh total
      fetchFieldPayments()
    }
  }, [selectedPayments, toast, t, fetchFieldPayments])

  // ============================================================
  // Mission week navigation
  // ============================================================

  const handleWeekChange = useCallback((weekStart: string) => {
    setMissionWeekStart(weekStart)
    fetchMissions(weekStart)
  }, [fetchMissions])

  const handleMissionCreated = useCallback(() => {
    fetchMissions()
    setShowMissionPlan(false)
  }, [fetchMissions])

  // ============================================================
  // Loading state
  // ============================================================

  if (loading || !data) {
    return (
      <div className="p-4 space-y-3">
        <Skeleton className="h-8 w-64" />
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-2">
          {Array.from({ length: 7 }).map((_, i) => <Skeleton key={i} className="h-20" />)}
        </div>
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  // ============================================================
  // 7 KPI cards
  // ============================================================

  const kpiCards = [
    { label: t('supervisor.today'), value: data.today.total, icon: ClipboardCheck, color: 'text-blue-600' },
    { label: t('supervisor.conforme'), value: data.today.conforme, icon: CheckCircle2, color: 'text-green-600' },
    { label: t('supervisor.nonConforme'), value: data.today.non_conforme, icon: XCircle, color: 'text-red-600' },
    { label: t('supervisor.seals'), value: (data.today.seals_proposed || 0) + (data.today.seals_approved || 0), icon: Lock, color: 'text-purple-600' },
    { label: t('supervisor.collectedToday'), value: fmtXAF(data.today.total_collected_amount, locale), icon: DollarSign, color: 'text-amber-600' },
    {
      label: t('supervisor.overdueMed'),
      value: data.overdue_med || 0,
      icon: Clock,
      color: data.overdue_med > 0 ? 'text-orange-600' : 'text-muted-foreground',
      alert: data.overdue_med > 0,
    },
    {
      label: t('supervisor.unreconciledCash'),
      value: data.unreconciled_cash_count || 0,
      icon: Wallet,
      color: data.unreconciled_cash_count > 0 ? 'text-red-600' : 'text-muted-foreground',
      alert: data.unreconciled_cash_count > 0,
    },
  ]

  // ============================================================
  // Tab badge counts
  // ============================================================

  const tabBadges: Partial<Record<TabKey, number>> = {
    payments: data.unreconciled_cash_count || 0,
    seals: data.pending_seals.length,
  }

  return (
    <div className="flex flex-col gap-3 p-4 max-h-[calc(100vh-64px)] overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-2">
          <Shield className="h-5 w-5 text-green-700" />
          <h1 className="text-lg font-bold">{t('supervisor.title')}</h1>
          <LocationFilter
            entityCode={agentProfile?.entity_code}
            isMainOffice={agentProfile?.is_main_office ?? false}
            value={locationFilter}
            onChange={setLocationFilter}
            className="ml-4"
          />
        </div>
        <ExportButton
          filters={{ tab: activeTab }}
        />
      </div>

      {/* 7 KPI cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2 flex-shrink-0">
        {kpiCards.map((k) => (
          <Card key={k.label} className={`shadow-sm ${(k as { alert?: boolean }).alert ? 'border-orange-300 bg-orange-50/40' : ''}`}>
            <CardContent className="p-2 flex items-center gap-1.5">
              <k.icon className={`h-4 w-4 ${k.color} shrink-0`} />
              <div className="min-w-0">
                <p className="text-base font-bold leading-tight truncate tabular-nums">{k.value}</p>
                <p className="text-[10px] text-muted-foreground truncate leading-tight">{k.label}</p>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* 6 Tabs - Desktop: horizontal, Mobile: dropdown */}
      <Tabs value={activeTab} onValueChange={handleTabChange} className="flex-1 flex flex-col min-h-0">
        {/* Desktop tabs */}
        <TabsList className="hidden sm:flex w-full flex-shrink-0 justify-start gap-0.5">
          {TAB_KEYS.map((tab) => {
            const Icon = TAB_ICONS[tab]
            const badge = tabBadges[tab]
            return (
              <TabsTrigger key={tab} value={tab} className="text-xs gap-1 px-3">
                <Icon className="h-3.5 w-3.5" />
                {t(`tabs.${tab}`)}
                {badge && badge > 0 && (
                  <Badge variant="destructive" className="ml-0.5 text-[10px] px-1 py-0 h-4">{badge}</Badge>
                )}
              </TabsTrigger>
            )
          })}
        </TabsList>

        {/* Mobile dropdown */}
        <div className="sm:hidden flex-shrink-0">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" className="w-full justify-between text-sm">
                <span className="flex items-center gap-2">
                  {(() => { const Icon = TAB_ICONS[activeTab]; return <Icon className="h-4 w-4" /> })()}
                  {t(`tabs.${activeTab}`)}
                  {tabBadges[activeTab] && tabBadges[activeTab]! > 0 && (
                    <Badge variant="destructive" className="text-[10px] px-1 h-4">{tabBadges[activeTab]}</Badge>
                  )}
                </span>
                <ChevronDown className="h-4 w-4 opacity-50" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent className="w-[--radix-dropdown-menu-trigger-width]">
              {TAB_KEYS.map((tab) => {
                const Icon = TAB_ICONS[tab]
                const badge = tabBadges[tab]
                return (
                  <DropdownMenuItem key={tab} onClick={() => handleTabChange(tab)} className="gap-2">
                    <Icon className="h-4 w-4" />
                    {t(`tabs.${tab}`)}
                    {badge && badge > 0 && (
                      <Badge variant="destructive" className="ml-auto text-[10px] px-1 h-4">{badge}</Badge>
                    )}
                  </DropdownMenuItem>
                )
              })}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        {/* ============ TAB 1: Overview ============ */}
        <TabsContent value="overview" className="flex-1 overflow-y-auto space-y-3 mt-2">
          {/* Alerts row */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {data.overdue_med > 0 && (
              <Card className="border-orange-200 bg-orange-50">
                <CardContent className="p-3 flex items-center gap-2">
                  <Clock className="h-5 w-5 text-orange-600 shrink-0" />
                  <div>
                    <p className="font-medium text-sm text-orange-800">
                      {data.overdue_med} {t('supervisor.overdueMed')}
                    </p>
                    <p className="text-xs text-orange-600">{t('supervisor.overdueMedAction')}</p>
                  </div>
                </CardContent>
              </Card>
            )}
            {data.unreconciled_cash_count > 0 && (
              <Card className="border-red-200 bg-red-50">
                <CardContent className="p-3 flex items-center gap-2">
                  <Wallet className="h-5 w-5 text-red-600 shrink-0" />
                  <div>
                    <p className="font-medium text-sm text-red-800">
                      {fmtXAF(data.unreconciled_cash_amount, locale)} {t('supervisor.unreconciledCash')}
                    </p>
                    <p className="text-xs text-red-600">
                      {data.unreconciled_cash_count} {t('supervisor.transactionsThisWeek')}
                    </p>
                  </div>
                  <Button
                    size="sm" variant="outline" className="ml-auto shrink-0 h-7 text-xs"
                    onClick={() => handleTabChange('payments')}
                  >
                    {t('supervisor.viewAll')} <ArrowRight className="h-3 w-3 ml-1" />
                  </Button>
                </CardContent>
              </Card>
            )}
          </div>

          {/* Live agent status */}
          <LiveStatusPanel />

          {/* Week summary */}
          <Card>
            <CardHeader className="pb-1 pt-3 px-3">
              <CardTitle className="text-sm">{t('supervisor.thisWeek')}</CardTitle>
            </CardHeader>
            <CardContent className="grid grid-cols-3 gap-2 text-center text-sm px-3 pb-3">
              <div>
                <p className="text-lg font-bold tabular-nums">{data.week.total}</p>
                <p className="text-[10px] text-muted-foreground">{t('supervisor.totalWeek')}</p>
              </div>
              <div>
                <p className="text-lg font-bold text-green-600 tabular-nums">
                  {data.week.total > 0 ? Math.round((data.week.conforme / data.week.total) * 100) : 0}%
                </p>
                <p className="text-[10px] text-muted-foreground">{t('supervisor.conformityRate')}</p>
              </div>
              <div>
                <p className="text-lg font-bold text-amber-600 tabular-nums">{fmtXAF(data.week.total_collected_amount, locale)}</p>
                <p className="text-[10px] text-muted-foreground">{t('supervisor.collectedWeek')}</p>
              </div>
            </CardContent>
          </Card>

          {/* Recent activity */}
          <Card>
            <CardHeader className="pb-1 pt-3 px-3">
              <CardTitle className="text-sm">{t('supervisor.recentActivity')}</CardTitle>
            </CardHeader>
            <CardContent className="px-3 pb-3">
              {data.recent_inspections.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-4">{t('supervisor.noRecentInspections')}</p>
              ) : (
                <div className="space-y-1.5">
                  {data.recent_inspections.slice(0, 8).map((item) => {
                    const cfg = INSPECTION_STATUS_CONFIG[item.status] || { color: '', bgColor: '' }
                    return (
                      <div
                        key={item.id}
                        className="flex items-center justify-between p-1.5 rounded border text-sm cursor-pointer hover:bg-muted/50 transition-colors"
                        onClick={() => router.push(`/${locale}/dashboard/supervisor/inspections/${item.id}`)}
                      >
                        <div className="flex items-center gap-2 min-w-0">
                          <span className="text-[10px] text-muted-foreground w-10 shrink-0 tabular-nums">
                            {new Date(item.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                          </span>
                          <span className="font-medium truncate">{item.agent_name}</span>
                          <span className="text-muted-foreground truncate hidden md:inline">— {item.company_name}</span>
                        </div>
                        <Badge className={`${cfg.bgColor} ${cfg.color} text-[10px] shrink-0`}>
                          {t(`status.${item.status}`)}
                        </Badge>
                      </div>
                    )
                  })}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ============ TAB 2: Versements terrain ============ */}
        <TabsContent value="payments" className="flex-1 overflow-y-auto mt-2">
          <Card>
            <CardHeader className="pb-2 pt-3 px-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm flex items-center gap-2">
                  <Wallet className="h-4 w-4 text-amber-600" />
                  {t('payments.title')}
                </CardTitle>
                {fieldPayments.length > 0 && (
                  <div className="flex items-center gap-3">
                    <div className="text-right">
                      <p className="text-base font-bold text-amber-600 tabular-nums">{fmtXAF(fieldTotal, locale)}</p>
                      <p className="text-[10px] text-muted-foreground">{t('payments.paymentCount', { count: fieldPayments.length })}</p>
                    </div>
                  </div>
                )}
              </div>
            </CardHeader>
            <CardContent className="px-3 pb-3">
              {loadingField ? (
                <div className="space-y-2">{[1, 2, 3].map(i => <Skeleton key={i} className="h-10" />)}</div>
              ) : fieldPayments.length === 0 ? (
                <div className="text-center py-6 text-muted-foreground">
                  <Wallet className="h-8 w-8 mx-auto mb-2 opacity-30" />
                  <p className="text-sm">{t('payments.noPayments')}</p>
                </div>
              ) : (
                <>
                  {/* Batch selection header */}
                  <div className="flex items-center justify-between mb-2 p-2 bg-muted/50 rounded-lg">
                    <div className="flex items-center gap-3">
                      <Checkbox
                        checked={selectedPayments.size === fieldPayments.length && fieldPayments.length > 0}
                        onCheckedChange={toggleAllPayments}
                      />
                      <span className="text-xs text-muted-foreground">
                        {selectedPayments.size > 0
                          ? t('payments.batchSelected', { count: selectedPayments.size })
                          : t('payments.batchSelectAll')}
                      </span>
                    </div>
                    {selectedPayments.size > 0 && (
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-medium tabular-nums">{fmtXAF(selectedTotal, locale)}</span>
                        <Button
                          size="sm" className="h-7 text-xs gap-1"
                          onClick={() => setShowBatchConfirm(true)}
                          disabled={batchValidating}
                        >
                          <CheckCircle2 className="h-3 w-3" />
                          {t('payments.batchValidate')} ({selectedPayments.size})
                        </Button>
                      </div>
                    )}
                  </div>

                  {/* Batch confirm inline panel */}
                  {showBatchConfirm && (
                    <div className="mb-3 p-3 border border-amber-200 bg-amber-50 rounded-lg space-y-2">
                      <p className="text-sm font-medium">{t('payments.batchConfirmTitle')}</p>
                      <p className="text-xs text-muted-foreground">
                        {t('payments.batchConfirmDesc', {
                          count: selectedPayments.size,
                          amount: fmtXAF(selectedTotal, locale),
                        })}
                      </p>
                      <div className="max-h-24 overflow-y-auto space-y-1">
                        {selectedPaymentsList.slice(0, 5).map(p => (
                          <div key={p.id} className="flex items-center justify-between text-xs">
                            <span className="font-mono">{p.payment_reference}</span>
                            <span className="font-medium tabular-nums">{fmtXAF(p.total_amount, locale)}</span>
                          </div>
                        ))}
                        {selectedPaymentsList.length > 5 && (
                          <p className="text-[10px] text-muted-foreground">+{selectedPaymentsList.length - 5} ...</p>
                        )}
                      </div>
                      <div className="flex gap-2">
                        <Button size="sm" className="h-7 text-xs" onClick={handleBatchValidate}>
                          {t('payments.confirmValidation')}
                        </Button>
                        <Button size="sm" variant="ghost" className="h-7 text-xs" onClick={() => setShowBatchConfirm(false)}>
                          {t('common.cancel')}
                        </Button>
                      </div>
                    </div>
                  )}

                  {/* Batch progress */}
                  {batchValidating && (
                    <div className="mb-3 p-2 bg-blue-50 border border-blue-200 rounded-lg">
                      <p className="text-xs text-blue-800 mb-1">
                        {t('payments.batchValidating', { current: batchProgress.current, total: batchProgress.total })}
                      </p>
                      <Progress value={batchProgress.total > 0 ? (batchProgress.current / batchProgress.total) * 100 : 0} className="h-1.5" />
                    </div>
                  )}

                  {/* Payment table */}
                  <div className="overflow-x-auto">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead className="w-8"></TableHead>
                          <TableHead className="text-xs">{t('payments.ref')}</TableHead>
                          <TableHead className="text-xs">{t('payments.agent')}</TableHead>
                          <TableHead className="text-xs">{t('payments.company')}</TableHead>
                          <TableHead className="text-xs">{t('payments.type')}</TableHead>
                          <TableHead className="text-xs text-right">{t('payments.amount')}</TableHead>
                          <TableHead className="text-xs">{t('payments.date')}</TableHead>
                          <TableHead className="text-xs w-20"></TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {fieldPayments.map((p) => (
                          <TableRow key={p.id} className={selectedPayments.has(p.id) ? 'bg-amber-50/50' : ''}>
                            <TableCell className="pr-0">
                              <Checkbox
                                checked={selectedPayments.has(p.id)}
                                onCheckedChange={() => togglePayment(p.id)}
                                disabled={batchValidating}
                              />
                            </TableCell>
                            <TableCell className="font-mono text-[10px]">{p.payment_reference}</TableCell>
                            <TableCell className="text-xs font-medium">{p.agent_name}</TableCell>
                            <TableCell className="text-xs">
                              {p.company_name}<br />
                              <span className="text-muted-foreground text-[10px]">{p.company_nif}</span>
                            </TableCell>
                            <TableCell><Badge variant="outline" className="text-[10px]">{p.fee_type}</Badge></TableCell>
                            <TableCell className="text-right font-bold text-xs tabular-nums">{fmtXAF(p.total_amount, locale)}</TableCell>
                            <TableCell className="text-[10px] text-muted-foreground tabular-nums">
                              {(p.inspection_date || p.created_at) && new Date(p.inspection_date || p.created_at).toLocaleDateString(locale)}
                            </TableCell>
                            <TableCell>
                              <Button
                                size="sm" className="h-7 text-xs gap-1"
                                onClick={() => setConfirmPayment(p)}
                                disabled={validating || batchValidating}
                              >
                                <CheckCircle2 className="h-3 w-3" /> {t('payments.validate')}
                              </Button>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ============ TAB 3: Scellés ============ */}
        <TabsContent value="seals" className="flex-1 overflow-y-auto mt-2">
          <Card>
            <CardHeader className="pb-2 pt-3 px-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4 text-red-600" /> {t('supervisor.pendingSeals')}
                </CardTitle>
                <Badge variant={data.pending_seals.length > 0 ? 'destructive' : 'secondary'}>
                  {data.pending_seals.length}
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="px-3 pb-3">
              {data.pending_seals.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-6">{t('supervisor.noPendingSeals')}</p>
              ) : (
                <div className="space-y-2">
                  {data.pending_seals.map((seal) => (
                    <div key={seal.id} className="flex items-center justify-between p-2.5 rounded-lg border border-red-200 bg-red-50">
                      <div className="min-w-0">
                        <span className="font-medium text-sm">{seal.company_name}</span>
                        <span className="text-muted-foreground ml-2 text-xs">{seal.company_nif}</span>
                        <br />
                        <span className="text-[10px] text-muted-foreground">
                          {seal.agent_name} — {fmtXAF(seal.unpaid_obligations_amount, locale)}
                        </span>
                      </div>
                      <Button size="sm" variant="outline" className="gap-1 h-7 text-xs shrink-0"
                        onClick={() => router.push(`/${locale}/dashboard/supervisor/inspections/pending-seals`)}>
                        {t('supervisor.manage') || 'Gérer'} <ArrowRight className="h-3 w-3" />
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ============ TAB 4: Agents ============ */}
        <TabsContent value="agents" className="flex-1 overflow-y-auto mt-2">
          <AgentPerformanceTable
            data={agentData?.items || []}
            loading={loadingAgents}
            onAgentClick={(id) => router.push(`/${locale}/dashboard/supervisor/inspections/agents/${id}`)}
          />
        </TabsContent>

        {/* ============ TAB 5: Missions ============ */}
        <TabsContent value="missions" className="flex-1 overflow-y-auto mt-2 space-y-3">
          <div className="flex justify-end mb-2">
            <Button
              variant="outline" size="sm"
              onClick={() => router.push(`/${locale}/dashboard/supervisor/inspections/missions`)}
              className="gap-1.5"
            >
              <CalendarDays className="h-3.5 w-3.5" />
              {t('mission.viewAll') || 'Hub Missions'}
            </Button>
          </div>
          <MissionPlanPanel
            open={showMissionPlan}
            onClose={() => setShowMissionPlan(false)}
            onMissionCreated={handleMissionCreated}
          />
          <MissionCalendar
            missions={missions}
            loading={loadingMissions}
            onMissionClick={(id) => router.push(`/${locale}/dashboard/supervisor/inspections/missions/${id}`)}
            onWeekChange={handleWeekChange}
            onCreateMission={() => setShowMissionPlan(true)}
          />
        </TabsContent>

        {/* ============ TAB 6: Zones ============ */}
        <TabsContent value="zones" className="flex-1 overflow-y-auto mt-2">
          <ZoneAnalyticsTable
            data={zoneData?.items || []}
            loading={loadingZones}
            summary={zoneData ? {
              total_zones: zoneData.total_zones,
              covered_zones: zoneData.covered_zones,
              stale_zones: zoneData.stale_zones,
            } : undefined}
          />
        </TabsContent>
      </Tabs>

      {/* ============ Confirm single validation dialog ============ */}
      <AlertDialog open={!!confirmPayment} onOpenChange={() => setConfirmPayment(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <Wallet className="h-5 w-5 text-amber-600" />
              {t('payments.confirmTitle')}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {confirmPayment && t('payments.confirmDesc', { agent: confirmPayment.agent_name })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          {confirmPayment && (
            <div className="bg-amber-50 p-3 rounded text-sm space-y-1">
              <p><strong>{t('payments.confirmRef')} :</strong> {confirmPayment.payment_reference}</p>
              <p><strong>{t('payments.confirmCompany')} :</strong> {confirmPayment.company_name} ({confirmPayment.company_nif})</p>
              <p><strong>{t('payments.confirmAmount')} :</strong> <span className="font-bold text-amber-700 tabular-nums">{fmtXAF(confirmPayment.total_amount, locale)}</span></p>
              <p><strong>{t('payments.confirmType')} :</strong> {confirmPayment.fee_type}</p>
            </div>
          )}
          <div className="bg-blue-50 border border-blue-200 rounded p-2 text-xs text-blue-800">
            {t('payments.confirmInfo')}
            <ul className="list-disc ml-4 mt-1">
              <li>{t('payments.confirmAction1')}</li>
              <li>{t('payments.confirmAction2')}</li>
              <li>{t('payments.confirmAction3')}</li>
            </ul>
          </div>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
            <AlertDialogAction onClick={handleValidatePayment} disabled={validating}>
              {validating ? t('payments.validating') : t('payments.confirmValidation')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
