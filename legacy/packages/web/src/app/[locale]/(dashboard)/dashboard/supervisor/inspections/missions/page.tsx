'use client'

/**
 * Missions Hub — 3 tabs: Planning, Attribution, Dashboard
 *
 * Planning: Calendar + create mission (existing)
 * Attribution: Manage agent assignments across active missions (new)
 * Dashboard: KPIs, trends, top agents (new)
 */

import { useCallback, useEffect, useMemo, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useLocale, useTranslations } from 'next-intl'
import { useToast } from '@/hooks/use-toast'
import { ArrowLeft, CalendarDays, Users, BarChart3, Clock } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { inspectionApi } from '@/modules/inspections/services/api'
import { MissionCalendar } from '@/modules/inspections/components/MissionCalendar'
import { MissionPlanPanel } from '@/modules/inspections/components/MissionPlanPanel'
import { MissionAttributionTab } from '@/modules/inspections/components/MissionAttributionTab'
import { MissionDashboardTab } from '@/modules/inspections/components/MissionDashboardTab'
import { MissionTemplatesTab } from '@/modules/inspections/components/MissionTemplatesTab'
import { LocationFilter, useLocationFilterState } from '@/modules/inspections/components/LocationFilter'
import { useAgentProfile } from '@/modules/agent-dashboard/hooks/useAgentDashboard'
import type { MissionListItem } from '@/modules/inspections/types'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getMonday(d: Date): string {
  const date = new Date(d)
  const day = date.getDay()
  const diff = day === 0 ? 6 : day - 1
  date.setDate(date.getDate() - diff)
  return date.toISOString().slice(0, 10)
}

function addDays(iso: string, days: number): string {
  const d = new Date(iso + 'T00:00:00')
  d.setDate(d.getDate() + days)
  return d.toISOString().slice(0, 10)
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function MissionsPage() {
  const locale = useLocale()
  const router = useRouter()
  const { toast } = useToast()
  const t = useTranslations('inspection')

  const { data: agentProfile } = useAgentProfile()
  const { locationFilter, setLocationFilter } = useLocationFilterState(agentProfile)

  const [activeTab, setActiveTab] = useState('planning')
  const [weekStart, setWeekStart] = useState(() => getMonday(new Date()))
  const [missions, setMissions] = useState<MissionListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [showPlan, setShowPlan] = useState(false)

  // Stats
  const stats = useMemo(() => {
    const planned = missions.filter(m => m.status === 'planned').length
    const inProgress = missions.filter(m => m.status === 'in_progress').length
    const completed = missions.filter(m => m.status === 'completed').length
    const totalInspections = missions.reduce((s, m) => s + m.inspections_done, 0)
    const totalTarget = missions.reduce((s, m) => s + m.inspections_target, 0)
    return { planned, inProgress, completed, totalInspections, totalTarget }
  }, [missions])

  // Fetch missions for the current week
  const fetchMissions = useCallback(async (start?: string) => {
    const ws = start || weekStart
    const weekEnd = addDays(ws, 6)
    try {
      setLoading(true)
      const result = await inspectionApi.listMissions({
        date_from: ws,
        date_to: weekEnd,
        page_size: 50,
        entity_location_id: locationFilter || undefined,
      })
      setMissions(result.items)
    } catch {
      toast({ title: t('common.error'), variant: 'destructive' })
    } finally {
      setLoading(false)
    }
  }, [weekStart, locationFilter, toast, t])

  useEffect(() => {
    if (activeTab === 'planning') fetchMissions()
  }, [fetchMissions, activeTab])

  const handleWeekChange = useCallback((ws: string) => {
    setWeekStart(ws)
    fetchMissions(ws)
  }, [fetchMissions])

  const handleMissionCreated = useCallback(() => {
    setShowPlan(false)
    fetchMissions()
  }, [fetchMissions])

  return (
    <div className="flex flex-col gap-3 p-4 max-h-[calc(100vh-64px)] overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost" size="icon" className="h-8 w-8"
            onClick={() => router.push(`/${locale}/dashboard/supervisor/inspections`)}
          >
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div className="flex items-center gap-2">
            <CalendarDays className="h-5 w-5 text-primary" />
            <h1 className="text-lg font-bold">{t('missions.missionsLabel', { defaultMessage: 'Missions' })}</h1>
          </div>
          <LocationFilter
            entityCode={agentProfile?.entity_code}
            isMainOffice={agentProfile?.is_main_office ?? false}
            value={locationFilter}
            onChange={setLocationFilter}
          />
        </div>

        {/* Week stats badges (planning tab only) */}
        {activeTab === 'planning' && (
          <div className="hidden md:flex items-center gap-4 text-xs text-muted-foreground">
            <span className="flex items-center gap-1">
              <span className="h-2 w-2 rounded-full bg-blue-500" />
              {stats.planned} {t('mission.planned', { defaultMessage: 'planned' })}
            </span>
            <span className="flex items-center gap-1">
              <span className="h-2 w-2 rounded-full bg-amber-500" />
              {stats.inProgress} {t('mission.in_progress', { defaultMessage: 'in progress' })}
            </span>
            <span className="flex items-center gap-1">
              <span className="h-2 w-2 rounded-full bg-green-500" />
              {stats.completed} {t('mission.completed', { defaultMessage: 'completed' })}
            </span>
          </div>
        )}
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col overflow-hidden">
        <TabsList className="flex-shrink-0">
          <TabsTrigger value="planning" className="gap-1.5">
            <CalendarDays className="h-3.5 w-3.5" />
            {t('missions.planning', { defaultMessage: 'Planning' })}
          </TabsTrigger>
          <TabsTrigger value="attribution" className="gap-1.5">
            <Users className="h-3.5 w-3.5" />
            {t('missions.attribution', { defaultMessage: 'Attribution' })}
          </TabsTrigger>
          <TabsTrigger value="dashboard" className="gap-1.5">
            <BarChart3 className="h-3.5 w-3.5" />
            {t('missions.dashboard', { defaultMessage: 'Dashboard' })}
          </TabsTrigger>
          <TabsTrigger value="templates" className="gap-1.5">
            <Clock className="h-3.5 w-3.5" />
            {t('missions.templates', { defaultMessage: 'Templates' })}
          </TabsTrigger>
        </TabsList>

        {/* Planning Tab */}
        <TabsContent value="planning" className="flex-1 overflow-y-auto mt-3">
          <MissionPlanPanel
            open={showPlan}
            onClose={() => setShowPlan(false)}
            onMissionCreated={handleMissionCreated}
          />
          <MissionCalendar
            missions={missions}
            loading={loading}
            onMissionClick={(id) => router.push(`/${locale}/dashboard/supervisor/inspections/missions/${id}`)}
            onWeekChange={handleWeekChange}
            onCreateMission={() => setShowPlan(true)}
          />
        </TabsContent>

        {/* Attribution Tab */}
        <TabsContent value="attribution" className="flex-1 overflow-y-auto mt-3">
          <MissionAttributionTab locationFilter={locationFilter || undefined} />
        </TabsContent>

        {/* Dashboard Tab */}
        <TabsContent value="dashboard" className="flex-1 overflow-y-auto mt-3">
          <MissionDashboardTab locationFilter={locationFilter || undefined} />
        </TabsContent>

        {/* Templates Tab */}
        <TabsContent value="templates" className="flex-1 overflow-y-auto mt-3">
          <MissionTemplatesTab locationFilter={locationFilter || undefined} />
        </TabsContent>
      </Tabs>
    </div>
  )
}
