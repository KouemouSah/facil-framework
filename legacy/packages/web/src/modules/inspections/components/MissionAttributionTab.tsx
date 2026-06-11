'use client'

/**
 * MissionAttributionTab — Professional agent assignment management.
 *
 * Features:
 * - Status filter pills (planned / in_progress / all)
 * - Agent workload overview bar (global load across missions)
 * - Expandable mission cards with agent details
 * - Auto-assign with score explanation
 * - Progress bars with actual/target
 * - Available agents panel with availability indicator
 */

import { useCallback, useEffect, useMemo, useState } from 'react'
import { useTranslations } from 'next-intl'
import { toast } from 'sonner'
import {
  Users, Plus, Bot, Trash2, ChevronDown, ChevronUp,
  Calendar, UserX, Activity,
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Skeleton } from '@/components/ui/skeleton'
import { Progress } from '@/components/ui/progress'
import { inspectionApi } from '@/modules/inspections/services/api'
import type {
  MissionListItem, Mission, AgentAvailability, MissionAgent,
} from '@/modules/inspections/types'

interface Props {
  locationFilter?: string
}

const STATUS_COLORS: Record<string, string> = {
  planned: 'bg-blue-100 text-blue-800',
  in_progress: 'bg-amber-100 text-amber-800',
  assigned: 'bg-blue-100 text-blue-800',
  active: 'bg-green-100 text-green-800',
  completed: 'bg-gray-100 text-gray-600',
  absent: 'bg-red-100 text-red-800',
}

type StatusFilter = 'all' | 'planned' | 'in_progress'

export function MissionAttributionTab({ locationFilter }: Props) {
  const t = useTranslations('inspection')
  const [missions, setMissions] = useState<Mission[]>([])
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [expandedMission, setExpandedMission] = useState<string | null>(null)
  const [availableAgents, setAvailableAgents] = useState<AgentAvailability[]>([])
  const [selectedAgents, setSelectedAgents] = useState<Set<string>>(new Set())
  const [assigning, setAssigning] = useState(false)

  const fetchMissions = useCallback(async () => {
    try {
      setLoading(true)
      const result = await inspectionApi.listMissions({
        entity_location_id: locationFilter || undefined,
        page_size: 50,
      })
      const activeMissions = result.items.filter(
        (m: MissionListItem) => m.status === 'planned' || m.status === 'in_progress'
      )
      const detailed = await Promise.all(
        activeMissions.slice(0, 15).map((m: MissionListItem) =>
          inspectionApi.getMission(m.id).catch(() => null)
        )
      )
      setMissions(detailed.filter(Boolean) as Mission[])
    } catch {
      toast.error(t('common.error', { defaultMessage: 'Error' }))
    } finally {
      setLoading(false)
    }
  }, [locationFilter, t])

  useEffect(() => { fetchMissions() }, [fetchMissions])

  // Filtered missions
  const filteredMissions = useMemo(() => {
    if (statusFilter === 'all') return missions
    return missions.filter(m => m.status === statusFilter)
  }, [missions, statusFilter])

  // Global agent load overview
  const agentLoad = useMemo(() => {
    const load: Record<string, { name: string; assigned: number; target: number; actual: number }> = {}
    missions.forEach(m => {
      (m.agents ?? []).forEach((a: MissionAgent) => {
        if (!load[a.agent_id]) {
          load[a.agent_id] = { name: a.agent_name ?? a.agent_id, assigned: 0, target: 0, actual: 0 }
        }
        load[a.agent_id].assigned++
        load[a.agent_id].target += a.target_inspections ?? 10
        load[a.agent_id].actual += a.actual_inspections ?? 0
      })
    })
    return Object.values(load).sort((a, b) => b.target - a.target)
  }, [missions])

  const handleExpand = useCallback(async (mission: Mission) => {
    if (expandedMission === mission.id) {
      setExpandedMission(null)
      return
    }
    setExpandedMission(mission.id)
    setSelectedAgents(new Set())
    try {
      const agents = await inspectionApi.getAgentsAvailability(
        mission.mission_date, mission.entity_location_id,
      )
      setAvailableAgents(agents)
    } catch {
      setAvailableAgents([])
    }
  }, [expandedMission])

  const handleAssign = useCallback(async (missionId: string) => {
    if (selectedAgents.size === 0) return
    setAssigning(true)
    try {
      const agents = availableAgents
        .filter((a: AgentAvailability) => selectedAgents.has(a.agent_id))
        .map((a: AgentAvailability) => ({
          agent_id: a.agent_id,
          agent_profile_id: a.agent_profile_id,
          target_inspections: 10,
        }))
      await inspectionApi.assignAgents(missionId, agents)
      setSelectedAgents(new Set())
      toast.success(t('missions.agentsAssigned', { defaultMessage: 'Agents assigned' }))
      fetchMissions()
    } catch (err) {
      toast.error(String(err))
    } finally {
      setAssigning(false)
    }
  }, [selectedAgents, availableAgents, t, fetchMissions])

  const handleAutoAssign = useCallback(async (missionId: string) => {
    try {
      const result = await inspectionApi.autoAssignMission(missionId)
      if (result.agents_proposed === 0) {
        toast.info(t('missions.noAvailable', { defaultMessage: 'No agents available' }))
        return
      }
      const agents = result.proposals.map((p: { agent_id: string; agent_profile_id: string; target_inspections: number }) => ({
        agent_id: p.agent_id,
        agent_profile_id: p.agent_profile_id,
        target_inspections: p.target_inspections,
      }))
      await inspectionApi.assignAgents(missionId, agents)
      toast.success(`${result.agents_proposed} ${t('missions.agentsAssigned', { defaultMessage: 'agents assigned' })}`)
      fetchMissions()
    } catch (err) {
      toast.error(String(err))
    }
  }, [t, fetchMissions])

  const handleRemoveAgent = useCallback(async (missionId: string, agentId: string) => {
    try {
      await inspectionApi.removeAgent(missionId, agentId)
      toast.success(t('missions.agentRemoved', { defaultMessage: 'Agent removed' }))
      fetchMissions()
    } catch (err) {
      toast.error(String(err))
    }
  }, [t, fetchMissions])

  if (loading) {
    return <div className="space-y-3">{[1,2,3].map(i => <Skeleton key={i} className="h-32 rounded-lg" />)}</div>
  }

  const plannedCount = missions.filter(m => m.status === 'planned').length
  const inProgressCount = missions.filter(m => m.status === 'in_progress').length

  return (
    <div className="space-y-4">
      {/* Status filter pills */}
      <div className="flex gap-2">
        <FilterPill
          active={statusFilter === 'all'}
          onClick={() => setStatusFilter('all')}
          label={`${t('common.all', { defaultMessage: 'All' })} (${missions.length})`}
        />
        <FilterPill
          active={statusFilter === 'planned'}
          onClick={() => setStatusFilter('planned')}
          label={`${t('mission.planned', { defaultMessage: 'Planned' })} (${plannedCount})`}
          color="text-blue-600"
        />
        <FilterPill
          active={statusFilter === 'in_progress'}
          onClick={() => setStatusFilter('in_progress')}
          label={`${t('mission.in_progress', { defaultMessage: 'In progress' })} (${inProgressCount})`}
          color="text-amber-600"
        />
      </div>

      {/* Agent workload overview */}
      {agentLoad.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <Activity className="h-4 w-4 text-primary" />
              {t('missions.agentWorkload', { defaultMessage: 'Agent workload' })}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
              {agentLoad.slice(0, 9).map((agent) => {
                const pct = agent.target > 0 ? Math.round(agent.actual / agent.target * 100) : 0
                return (
                  <div key={agent.name} className="flex items-center gap-2 py-1">
                    <span className="text-xs truncate w-20" title={agent.name}>{agent.name.split(' ')[0]}</span>
                    <div className="flex-1">
                      <Progress value={pct} className="h-2" />
                    </div>
                    <span className="text-xs tabular-nums text-muted-foreground w-14 text-right">
                      {agent.actual}/{agent.target}
                    </span>
                    <Badge variant="outline" className="text-xs px-1">
                      {agent.assigned}m
                    </Badge>
                  </div>
                )
              })}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Mission list */}
      {filteredMissions.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            <Calendar className="h-10 w-10 mx-auto mb-2 opacity-40" />
            <p>{t('missions.noActive', { defaultMessage: 'No active missions' })}</p>
          </CardContent>
        </Card>
      ) : (
        filteredMissions.map((mission) => {
          const agents: MissionAgent[] = mission.agents ?? []
          const actual = agents.reduce((s, a) => s + (a.actual_inspections ?? 0), 0)
          const target = agents.reduce((s, a) => s + (a.target_inspections ?? 10), 0)
          const pct = target > 0 ? Math.round(actual / target * 100) : 0
          const isExpanded = expandedMission === mission.id
          const absentCount = agents.filter(a => a.status === 'absent').length

          return (
            <Card key={mission.id} className="overflow-hidden">
              <CardHeader
                className="pb-2 cursor-pointer hover:bg-muted/30 transition-colors"
                onClick={() => handleExpand(mission)}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <CardTitle className="text-sm">
                      {mission.title ?? mission.mission_date}
                    </CardTitle>
                    <Badge className={STATUS_COLORS[mission.status] ?? ''} variant="secondary">
                      {t(`mission.${mission.status}`, { defaultMessage: mission.status })}
                    </Badge>
                    <span className="text-xs text-muted-foreground">{mission.mission_date}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-muted-foreground flex items-center gap-1">
                      <Users className="h-3 w-3" /> {agents.length}
                      {absentCount > 0 && (
                        <span className="text-red-500">(-{absentCount})</span>
                      )}
                    </span>
                    <span className={`text-xs font-medium tabular-nums ${pct >= 80 ? 'text-green-600' : pct >= 50 ? 'text-amber-600' : 'text-red-600'}`}>
                      {actual}/{target} ({pct}%)
                    </span>
                    {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                  </div>
                </div>
                <Progress value={pct} className="h-1.5 mt-2" />
              </CardHeader>

              {isExpanded && (
                <CardContent className="pt-0">
                  {/* Actions */}
                  <div className="flex gap-2 mb-3">
                    <Button size="sm" variant="outline" onClick={() => handleAutoAssign(mission.id)}>
                      <Bot className="h-3.5 w-3.5 mr-1" />
                      {t('missions.autoAssign', { defaultMessage: 'Auto-assign' })}
                    </Button>
                  </div>

                  {/* Agent list with metrics */}
                  {agents.length > 0 ? (
                    <div className="divide-y">
                      {agents.map((agent) => {
                        const agentPct = (agent.target_inspections ?? 10) > 0
                          ? Math.round((agent.actual_inspections ?? 0) / (agent.target_inspections ?? 10) * 100)
                          : 0
                        return (
                          <div key={agent.agent_id} className="flex items-center py-2.5 gap-2">
                            <div className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${
                              agent.status === 'active' ? 'bg-green-500' :
                              agent.status === 'absent' ? 'bg-red-500' :
                              agent.status === 'completed' ? 'bg-gray-400' : 'bg-blue-500'
                            }`} />
                            <div className="flex-1 min-w-0">
                              <div className="flex items-baseline gap-2">
                                <span className="text-sm font-medium truncate">{agent.agent_name ?? agent.agent_id}</span>
                                <Badge className={`text-[10px] px-1 py-0 ${STATUS_COLORS[agent.status] ?? ''}`} variant="secondary">
                                  {t(`mission.agent.${agent.status}`, { defaultMessage: agent.status })}
                                </Badge>
                              </div>
                              <div className="flex items-center gap-2 mt-0.5">
                                <Progress value={agentPct} className="h-1 flex-1" />
                                <span className="text-xs tabular-nums text-muted-foreground">
                                  {agent.actual_inspections ?? 0}/{agent.target_inspections ?? 10}
                                </span>
                              </div>
                            </div>
                            <div className="flex gap-1 flex-shrink-0">
                              {agent.status !== 'completed' && agent.status !== 'absent' && (
                                <Button
                                  size="icon" variant="ghost" className="h-7 w-7"
                                  title={t('missions.markAbsent', { defaultMessage: 'Mark absent' })}
                                  onClick={() => {/* TODO: mark absent */}}
                                >
                                  <UserX className="h-3.5 w-3.5 text-orange-500" />
                                </Button>
                              )}
                              {mission.status === 'planned' && (
                                <Button
                                  size="icon" variant="ghost" className="h-7 w-7"
                                  onClick={() => handleRemoveAgent(mission.id, agent.agent_id)}
                                >
                                  <Trash2 className="h-3.5 w-3.5 text-destructive" />
                                </Button>
                              )}
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground py-2">
                      {t('missions.noAgents', { defaultMessage: 'No agents assigned' })}
                    </p>
                  )}

                  {/* Available agents */}
                  {availableAgents.length > 0 && (
                    <div className="mt-3 p-3 bg-muted/30 rounded-lg">
                      <p className="text-xs font-medium mb-2">
                        {t('missions.available', { defaultMessage: 'Available' })} ({availableAgents.filter((a: AgentAvailability) => a.is_available).length})
                      </p>
                      <div className="max-h-40 overflow-y-auto space-y-1">
                        {availableAgents.filter((a: AgentAvailability) => a.is_available).map((a: AgentAvailability) => (
                          <label key={a.agent_id} className="flex items-center gap-2 py-1 cursor-pointer hover:bg-muted/50 rounded px-1">
                            <Checkbox
                              checked={selectedAgents.has(a.agent_id)}
                              onCheckedChange={() => {
                                setSelectedAgents(prev => {
                                  const next = new Set(prev)
                                  if (next.has(a.agent_id)) next.delete(a.agent_id)
                                  else next.add(a.agent_id)
                                  return next
                                })
                              }}
                            />
                            <span className="text-sm flex-1">{a.agent_name}</span>
                            {a.current_mission && (
                              <Badge variant="outline" className="text-[10px]">
                                {t('missions.busy', { defaultMessage: 'Busy' })}
                              </Badge>
                            )}
                          </label>
                        ))}
                      </div>
                      {selectedAgents.size > 0 && (
                        <Button
                          size="sm" className="mt-2 w-full"
                          onClick={() => handleAssign(mission.id)}
                          disabled={assigning}
                        >
                          <Plus className="h-3.5 w-3.5 mr-1" />
                          {assigning ? '...' : `${t('missions.assign', { defaultMessage: 'Assign' })} (${selectedAgents.size})`}
                        </Button>
                      )}
                    </div>
                  )}
                </CardContent>
              )}
            </Card>
          )
        })
      )}
    </div>
  )
}

function FilterPill({ active, onClick, label, color }: {
  active: boolean; onClick: () => void; label: string; color?: string
}) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
        active
          ? 'bg-primary text-primary-foreground'
          : `bg-muted hover:bg-muted/80 ${color ?? 'text-muted-foreground'}`
      }`}
    >
      {label}
    </button>
  )
}
