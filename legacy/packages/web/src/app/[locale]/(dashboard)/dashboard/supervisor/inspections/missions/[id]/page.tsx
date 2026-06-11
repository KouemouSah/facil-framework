'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { useLocale, useTranslations } from 'next-intl'
import { useToast } from '@/hooks/use-toast'
import {
  ArrowLeft, CalendarDays, MapPin, Shield, Users,
  CheckCircle2, XCircle, Play, Flag, UserPlus, UserMinus,
  ClipboardCheck, Clock, ChevronUp,
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { Skeleton } from '@/components/ui/skeleton'
import { Separator } from '@/components/ui/separator'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table'
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel,
  AlertDialogContent, AlertDialogDescription, AlertDialogFooter,
  AlertDialogHeader, AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { inspectionApi } from '@/modules/inspections/services/api'
import { INSPECTION_STATUS_CONFIG, fmtXAF } from '@/modules/inspections/utils/formatters'
import type { Mission, MissionAgent, AgentAvailability, InspectionListItem, MissionStatus } from '@/modules/inspections/types'

// ---------------------------------------------------------------------------
// Status config
// ---------------------------------------------------------------------------

const MISSION_STATUS_STYLES: Record<MissionStatus, { bg: string; text: string; icon: React.ElementType }> = {
  planned: { bg: 'bg-blue-100', text: 'text-blue-800', icon: CalendarDays },
  in_progress: { bg: 'bg-amber-100', text: 'text-amber-800', icon: Play },
  completed: { bg: 'bg-green-100', text: 'text-green-800', icon: CheckCircle2 },
  cancelled: { bg: 'bg-gray-100', text: 'text-gray-600', icon: XCircle },
}

const AGENT_STATUS_STYLES: Record<string, string> = {
  assigned: 'bg-blue-100 text-blue-800',
  active: 'bg-green-100 text-green-800',
  completed: 'bg-emerald-100 text-emerald-800',
  absent: 'bg-red-100 text-red-800',
}

const VALID_TRANSITIONS: Record<MissionStatus, MissionStatus[]> = {
  planned: ['in_progress', 'cancelled'],
  in_progress: ['completed', 'cancelled'],
  completed: [],
  cancelled: [],
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function MissionDetailPage() {
  const params = useParams<{ id: string }>()
  const missionId = params.id
  const locale = useLocale()
  const router = useRouter()
  const { toast } = useToast()
  const t = useTranslations('inspection')

  // Core state
  const [mission, setMission] = useState<Mission | null>(null)
  const [loading, setLoading] = useState(true)

  // Agent add panel
  const [showAddAgents, setShowAddAgents] = useState(false)
  const [availableAgents, setAvailableAgents] = useState<AgentAvailability[]>([])
  const [loadingAgents, setLoadingAgents] = useState(false)
  const [selectedNewAgents, setSelectedNewAgents] = useState<Map<string, { profileId: string; target: number }>>(new Map())
  const [addingAgents, setAddingAgents] = useState(false)

  // Agent remove
  const [removeAgent, setRemoveAgent] = useState<MissionAgent | null>(null)
  const [removing, setRemoving] = useState(false)

  // Status change
  const [statusAction, setStatusAction] = useState<MissionStatus | null>(null)
  const [completeNotes, setCompleteNotes] = useState('')
  const [changingStatus, setChangingStatus] = useState(false)

  // Linked inspections (from the mission's agents)
  const [inspections, setInspections] = useState<InspectionListItem[]>([])
  const [loadingInspections, setLoadingInspections] = useState(false)

  // =========================================================================
  // Data fetching
  // =========================================================================

  const fetchMission = useCallback(async () => {
    try {
      setLoading(true)
      const data = await inspectionApi.getMission(missionId)
      setMission(data)
    } catch {
      toast({ title: t('common.error'), variant: 'destructive' })
    } finally {
      setLoading(false)
    }
  }, [missionId, toast, t])

  const fetchLinkedInspections = useCallback(async () => {
    if (!mission) return
    try {
      setLoadingInspections(true)
      const result = await inspectionApi.list({
        inspection_date: mission.mission_date,
        page_size: 50,
      })
      // Filter to only inspections from agents in this mission
      const agentIds = new Set(mission.agents.map(a => a.agent_id))
      setInspections(result.items.filter(i => agentIds.has(i.agent_id)))
    } catch {
      // Non-critical - silently fail
    } finally {
      setLoadingInspections(false)
    }
  }, [mission])

  const fetchAvailableAgents = useCallback(async () => {
    if (!mission) return
    try {
      setLoadingAgents(true)
      const agents = await inspectionApi.getAgentsAvailability(mission.mission_date)
      // Exclude already-assigned agents
      const assignedIds = new Set(mission.agents.map(a => a.agent_id))
      setAvailableAgents(agents.filter(a => !assignedIds.has(a.agent_id)))
    } catch {
      toast({ title: t('common.error'), variant: 'destructive' })
    } finally {
      setLoadingAgents(false)
    }
  }, [mission, toast, t])

  useEffect(() => { fetchMission() }, [fetchMission])
  useEffect(() => { if (mission) fetchLinkedInspections() }, [mission, fetchLinkedInspections])

  // =========================================================================
  // Computed
  // =========================================================================

  const overallProgress = useMemo(() => {
    if (!mission) return 0
    const done = mission.agents.reduce((s, a) => s + a.actual_inspections, 0)
    const target = mission.agents.reduce((s, a) => s + a.target_inspections, 0)
    return target > 0 ? Math.round((done / target) * 100) : 0
  }, [mission])

  const canTransition = useMemo(
    () => mission ? VALID_TRANSITIONS[mission.status] : [],
    [mission]
  )

  // =========================================================================
  // Handlers
  // =========================================================================

  const handleToggleNewAgent = useCallback((agent: AgentAvailability) => {
    setSelectedNewAgents(prev => {
      const next = new Map(prev)
      if (next.has(agent.agent_id)) {
        next.delete(agent.agent_id)
      } else {
        next.set(agent.agent_id, { profileId: agent.agent_profile_id, target: 10 })
      }
      return next
    })
  }, [])

  const handleTargetChange = useCallback((agentId: string, target: number) => {
    setSelectedNewAgents(prev => {
      const next = new Map(prev)
      const entry = next.get(agentId)
      if (entry) next.set(agentId, { ...entry, target: Math.max(1, Math.min(100, target)) })
      return next
    })
  }, [])

  const handleAddAgents = useCallback(async () => {
    if (!mission || selectedNewAgents.size === 0) return
    setAddingAgents(true)
    try {
      const agents = Array.from(selectedNewAgents.entries()).map(([agentId, data]) => ({
        agent_id: agentId,
        agent_profile_id: data.profileId,
        target_inspections: data.target,
      }))
      await inspectionApi.assignAgents(mission.id, agents)
      toast({ title: t('mission.agentAdded') })
      setSelectedNewAgents(new Map())
      setShowAddAgents(false)
      fetchMission()
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : t('common.error')
      toast({ title: t('common.error'), description: msg, variant: 'destructive' })
    } finally {
      setAddingAgents(false)
    }
  }, [mission, selectedNewAgents, toast, t, fetchMission])

  const handleRemoveAgent = useCallback(async () => {
    if (!mission || !removeAgent) return
    setRemoving(true)
    try {
      await inspectionApi.removeAgent(mission.id, removeAgent.agent_id)
      toast({ title: t('mission.agentRemoved') })
      setRemoveAgent(null)
      fetchMission()
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : t('common.error')
      toast({ title: t('common.error'), description: msg, variant: 'destructive' })
    } finally {
      setRemoving(false)
    }
  }, [mission, removeAgent, toast, t, fetchMission])

  const handleStatusChange = useCallback(async () => {
    if (!mission || !statusAction) return
    setChangingStatus(true)
    try {
      if (statusAction === 'completed') {
        await inspectionApi.completeMission(mission.id, completeNotes || undefined)
        toast({ title: t('mission.completed_msg') })
      } else if (statusAction === 'in_progress') {
        await inspectionApi.updateMission(mission.id, { status: 'in_progress' })
        toast({ title: t('mission.started') })
      } else if (statusAction === 'cancelled') {
        await inspectionApi.updateMission(mission.id, { status: 'cancelled' })
        toast({ title: t('mission.cancelled_msg') })
      }
      setStatusAction(null)
      setCompleteNotes('')
      fetchMission()
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : t('common.error')
      toast({ title: t('common.error'), description: msg, variant: 'destructive' })
    } finally {
      setChangingStatus(false)
    }
  }, [mission, statusAction, completeNotes, toast, t, fetchMission])

  // =========================================================================
  // Loading
  // =========================================================================

  if (loading || !mission) {
    return (
      <div className="p-4 space-y-3">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-48 w-full" />
      </div>
    )
  }

  const statusStyle = MISSION_STATUS_STYLES[mission.status]
  const StatusIcon = statusStyle.icon
  const missionDate = new Date(mission.mission_date + 'T00:00:00')

  // =========================================================================
  // Render
  // =========================================================================

  return (
    <div className="flex flex-col gap-4 p-4 max-h-[calc(100vh-64px)] overflow-y-auto">
      {/* ---- Header ---- */}
      <div className="flex items-center gap-3 flex-shrink-0">
        <Button variant="ghost" size="icon" className="h-8 w-8"
          onClick={() => router.push(`/${locale}/dashboard/supervisor/inspections/missions`)}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h1 className="text-lg font-bold truncate">
              {mission.title || t('mission.missionOf', { date: missionDate.toLocaleDateString(locale) })}
            </h1>
            <Badge className={`${statusStyle.bg} ${statusStyle.text} gap-1`}>
              <StatusIcon className="h-3 w-3" />
              {t(`mission.${mission.status}`)}
            </Badge>
          </div>
          <div className="flex items-center gap-4 text-xs text-muted-foreground mt-0.5">
            <span className="flex items-center gap-1">
              <CalendarDays className="h-3 w-3" />
              {missionDate.toLocaleDateString(locale, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}
            </span>
            <span className="flex items-center gap-1">
              <MapPin className="h-3 w-3" />
              {mission.location_name}
            </span>
            <span className="flex items-center gap-1">
              <Shield className="h-3 w-3" />
              {mission.supervisor_name}
            </span>
          </div>
        </div>

        {/* Status actions */}
        <div className="flex gap-2 shrink-0">
          {canTransition.includes('in_progress') && (
            <Button size="sm" className="h-8 gap-1 text-xs"
              onClick={() => setStatusAction('in_progress')}>
              <Play className="h-3 w-3" /> {t('mission.startMission')}
            </Button>
          )}
          {canTransition.includes('completed') && (
            <Button size="sm" className="h-8 gap-1 text-xs bg-green-600 hover:bg-green-700"
              onClick={() => setStatusAction('completed')}>
              <Flag className="h-3 w-3" /> {t('mission.completeMission')}
            </Button>
          )}
          {canTransition.includes('cancelled') && (
            <Button size="sm" variant="outline" className="h-8 gap-1 text-xs text-red-600 hover:text-red-700"
              onClick={() => setStatusAction('cancelled')}>
              <XCircle className="h-3 w-3" /> {t('mission.cancelMission')}
            </Button>
          )}
        </div>
      </div>

      {/* ---- Content: 2-column layout ---- */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 flex-1 min-h-0">

        {/* LEFT: Agents + Progress (2/3) */}
        <div className="lg:col-span-2 space-y-4 overflow-y-auto">

          {/* Overall progress */}
          <Card>
            <CardContent className="p-3">
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-sm font-medium">{t('mission.overallProgress')}</span>
                <span className="text-sm font-bold tabular-nums">{overallProgress}%</span>
              </div>
              <Progress value={overallProgress} className="h-2" />
              <div className="flex justify-between mt-1 text-[10px] text-muted-foreground">
                <span>{mission.agents.reduce((s, a) => s + a.actual_inspections, 0)} {t('mission.actual')}</span>
                <span>{mission.agents.reduce((s, a) => s + a.target_inspections, 0)} {t('mission.target')}</span>
              </div>
            </CardContent>
          </Card>

          {/* Agents list */}
          <Card>
            <CardHeader className="pb-2 pt-3 px-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm flex items-center gap-2">
                  <Users className="h-4 w-4" />
                  {t('mission.agentsAssigned')} ({mission.agents.length})
                </CardTitle>
                {(mission.status === 'planned' || mission.status === 'in_progress') && (
                  <Button size="sm" variant="outline" className="h-7 text-xs gap-1"
                    onClick={() => { setShowAddAgents(!showAddAgents); if (!showAddAgents) fetchAvailableAgents() }}>
                    {showAddAgents ? <ChevronUp className="h-3 w-3" /> : <UserPlus className="h-3 w-3" />}
                    {showAddAgents ? t('common.cancel') : t('mission.addAgent')}
                  </Button>
                )}
              </div>
            </CardHeader>
            <CardContent className="px-3 pb-3">
              {/* Add agents panel (inline collapsible) */}
              {showAddAgents && (
                <div className="mb-3 p-3 bg-muted/50 rounded-lg border space-y-2">
                  <p className="text-xs font-medium">{t('mission.addAgentsPanel')}</p>
                  {loadingAgents ? (
                    <div className="space-y-2">{[1, 2, 3].map(i => <Skeleton key={i} className="h-8" />)}</div>
                  ) : availableAgents.length === 0 ? (
                    <p className="text-xs text-muted-foreground py-2">{t('mission.noAgents')}</p>
                  ) : (
                    <>
                      <div className="space-y-1.5 max-h-40 overflow-y-auto">
                        {availableAgents.map(agent => {
                          const selected = selectedNewAgents.has(agent.agent_id)
                          return (
                            <div key={agent.agent_id} className="flex items-center gap-2 p-1.5 rounded hover:bg-background">
                              <Checkbox checked={selected} onCheckedChange={() => handleToggleNewAgent(agent)}
                                disabled={!agent.is_available} />
                              <span className={`h-2 w-2 rounded-full shrink-0 ${agent.is_available ? 'bg-green-500' : 'bg-gray-400'}`} />
                              <span className={`text-xs flex-1 ${!agent.is_available ? 'text-muted-foreground line-through' : ''}`}>
                                {agent.agent_name}
                              </span>
                              {selected && (
                                <Input type="number" min={1} max={100} className="h-6 w-16 text-xs"
                                  value={selectedNewAgents.get(agent.agent_id)?.target || 10}
                                  onChange={(e) => handleTargetChange(agent.agent_id, parseInt(e.target.value) || 10)} />
                              )}
                            </div>
                          )
                        })}
                      </div>
                      <Button size="sm" className="h-7 text-xs w-full" disabled={selectedNewAgents.size === 0 || addingAgents}
                        onClick={handleAddAgents}>
                        {addingAgents ? t('mission.creating') : `${t('mission.addAgent')} (${selectedNewAgents.size})`}
                      </Button>
                    </>
                  )}
                </div>
              )}

              {/* Current agents */}
              {mission.agents.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-6">{t('mission.noAgents')}</p>
              ) : (
                <div className="space-y-2">
                  {mission.agents.map(agent => {
                    const pct = agent.target_inspections > 0
                      ? Math.round((agent.actual_inspections / agent.target_inspections) * 100)
                      : 0
                    return (
                      <div key={agent.id} className="p-2.5 rounded-lg border flex items-center gap-3">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="font-medium text-sm truncate">{agent.agent_name}</span>
                            <Badge className={`text-[10px] ${AGENT_STATUS_STYLES[agent.status] || 'bg-gray-100 text-gray-700'}`}>
                              {t(`mission.${agent.status}`)}
                            </Badge>
                          </div>
                          <div className="flex items-center gap-3">
                            <Progress value={pct} className="h-1.5 flex-1" />
                            <span className="text-xs tabular-nums font-medium w-16 text-right">
                              {agent.actual_inspections}/{agent.target_inspections}
                            </span>
                          </div>
                          {agent.assigned_zones && agent.assigned_zones.length > 0 && (
                            <div className="flex gap-1 mt-1">
                              {agent.assigned_zones.map(z => (
                                <Badge key={z} variant="outline" className="text-[9px] h-4">{z}</Badge>
                              ))}
                            </div>
                          )}
                        </div>
                        {(mission.status === 'planned' || mission.status === 'in_progress') && (
                          <Button size="sm" variant="ghost" className="h-7 text-xs text-red-500 hover:text-red-700 shrink-0"
                            onClick={() => setRemoveAgent(agent)}>
                            <UserMinus className="h-3 w-3" />
                          </Button>
                        )}
                      </div>
                    )
                  })}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Linked inspections */}
          <Card>
            <CardHeader className="pb-2 pt-3 px-3">
              <CardTitle className="text-sm flex items-center gap-2">
                <ClipboardCheck className="h-4 w-4" />
                {t('mission.linkedInspections')} ({inspections.length})
              </CardTitle>
            </CardHeader>
            <CardContent className="px-3 pb-3">
              {loadingInspections ? (
                <div className="space-y-2">{[1, 2, 3].map(i => <Skeleton key={i} className="h-8" />)}</div>
              ) : inspections.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-4">{t('mission.noLinkedInspections')}</p>
              ) : (
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="text-xs">{t('payments.agent')}</TableHead>
                        <TableHead className="text-xs">{t('payments.company')}</TableHead>
                        <TableHead className="text-xs">{t('filters.result')}</TableHead>
                        <TableHead className="text-xs">{t('filters.status')}</TableHead>
                        <TableHead className="text-xs text-right">{t('payments.amount')}</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {inspections.map(insp => {
                        const cfg = INSPECTION_STATUS_CONFIG[insp.status] || { color: '', bgColor: '' }
                        return (
                          <TableRow key={insp.id} className="cursor-pointer hover:bg-muted/50"
                            onClick={() => router.push(`/${locale}/dashboard/supervisor/inspections`)}>
                            <TableCell className="text-xs font-medium">{insp.agent_name}</TableCell>
                            <TableCell className="text-xs">{insp.company_name}</TableCell>
                            <TableCell>
                              {insp.result && (
                                <Badge variant="outline" className={`text-[10px] ${insp.result === 'conforme' ? 'border-green-300 text-green-700' : 'border-red-300 text-red-700'}`}>
                                  {t(`result.${insp.result}`)}
                                </Badge>
                              )}
                            </TableCell>
                            <TableCell>
                              <Badge className={`${cfg.bgColor} ${cfg.color} text-[10px]`}>
                                {t(`status.${insp.status}`)}
                              </Badge>
                            </TableCell>
                            <TableCell className="text-xs text-right tabular-nums">
                              {insp.payment_amount ? fmtXAF(insp.payment_amount, locale) : '—'}
                            </TableCell>
                          </TableRow>
                        )
                      })}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* RIGHT: Info panel (1/3) */}
        <div className="space-y-4">
          {/* Mission info */}
          <Card>
            <CardHeader className="pb-2 pt-3 px-3">
              <CardTitle className="text-sm">{t('mission.detail')}</CardTitle>
            </CardHeader>
            <CardContent className="px-3 pb-3 space-y-3 text-sm">
              <div>
                <span className="text-xs text-muted-foreground">{t('mission.missionDate')}</span>
                <p className="font-medium">
                  {missionDate.toLocaleDateString(locale, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}
                </p>
              </div>
              <Separator />
              <div>
                <span className="text-xs text-muted-foreground">{t('mission.location')}</span>
                <p className="font-medium flex items-center gap-1"><MapPin className="h-3 w-3" />{mission.location_name}</p>
              </div>
              <Separator />
              <div>
                <span className="text-xs text-muted-foreground">{t('mission.supervisor')}</span>
                <p className="font-medium flex items-center gap-1"><Shield className="h-3 w-3" />{mission.supervisor_name}</p>
              </div>
              {mission.zone_ids && mission.zone_ids.length > 0 && (
                <>
                  <Separator />
                  <div>
                    <span className="text-xs text-muted-foreground">{t('mission.zones')}</span>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {mission.zone_ids.map(z => (
                        <Badge key={z} variant="outline" className="text-[10px]">{z.slice(0, 8)}</Badge>
                      ))}
                    </div>
                  </div>
                </>
              )}
              {mission.notes && (
                <>
                  <Separator />
                  <div>
                    <span className="text-xs text-muted-foreground">{t('mission.notes')}</span>
                    <p className="text-xs mt-0.5 whitespace-pre-wrap">{mission.notes}</p>
                  </div>
                </>
              )}
              {mission.started_at && (
                <>
                  <Separator />
                  <div className="flex items-center gap-1 text-xs text-muted-foreground">
                    <Clock className="h-3 w-3" />
                    {t('mission.started')}: {new Date(mission.started_at).toLocaleString(locale)}
                  </div>
                </>
              )}
              {mission.completed_at && (
                <div className="flex items-center gap-1 text-xs text-muted-foreground">
                  <CheckCircle2 className="h-3 w-3" />
                  {t('mission.completed_msg')}: {new Date(mission.completed_at).toLocaleString(locale)}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Quick stats */}
          <Card>
            <CardContent className="p-3 grid grid-cols-2 gap-3">
              <div className="text-center">
                <p className="text-2xl font-bold tabular-nums">{mission.agents_count}</p>
                <p className="text-[10px] text-muted-foreground">{t('mission.agents')}</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold tabular-nums">{mission.total_inspections}</p>
                <p className="text-[10px] text-muted-foreground">{t('mission.inspections')}</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold tabular-nums text-primary">{overallProgress}%</p>
                <p className="text-[10px] text-muted-foreground">{t('mission.overallProgress')}</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold tabular-nums">{mission.total_target}</p>
                <p className="text-[10px] text-muted-foreground">{t('mission.target')}</p>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* ---- Remove agent dialog ---- */}
      <AlertDialog open={!!removeAgent} onOpenChange={() => setRemoveAgent(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('mission.removeAgent')}</AlertDialogTitle>
            <AlertDialogDescription>
              {removeAgent && t('mission.removeAgentConfirm')}
              {removeAgent && (
                <span className="block font-medium mt-1">{removeAgent.agent_name}</span>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
            <AlertDialogAction onClick={handleRemoveAgent} disabled={removing}
              className="bg-red-600 hover:bg-red-700">
              {removing ? t('common.loading') : t('mission.removeAgent')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* ---- Status change dialog ---- */}
      <AlertDialog open={!!statusAction} onOpenChange={() => setStatusAction(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {statusAction === 'completed' && t('mission.completeMission')}
              {statusAction === 'in_progress' && t('mission.startMission')}
              {statusAction === 'cancelled' && t('mission.cancelMission')}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {statusAction === 'completed' && t('mission.completeConfirm')}
              {statusAction === 'in_progress' && t('mission.startConfirm')}
              {statusAction === 'cancelled' && t('mission.cancelConfirm')}
            </AlertDialogDescription>
          </AlertDialogHeader>
          {statusAction === 'completed' && (
            <Textarea
              placeholder={t('mission.completeNotes')}
              value={completeNotes}
              onChange={(e) => setCompleteNotes(e.target.value)}
              className="min-h-[80px]"
            />
          )}
          <AlertDialogFooter>
            <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
            <AlertDialogAction onClick={handleStatusChange} disabled={changingStatus}
              className={statusAction === 'cancelled' ? 'bg-red-600 hover:bg-red-700' : ''}>
              {changingStatus ? t('common.loading') : (
                statusAction === 'completed' ? t('mission.completeMission') :
                statusAction === 'in_progress' ? t('mission.startMission') :
                t('mission.cancelMission')
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
