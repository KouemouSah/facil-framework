'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import { useTranslations } from 'next-intl'
import { CalendarDays, Loader2, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Checkbox } from '@/components/ui/checkbox'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Collapsible,
  CollapsibleContent,
} from '@/components/ui/collapsible'
import { useToast } from '@/hooks/use-toast'
import { cn } from '@/core/utils'
import { inspectionApi } from '../services/api'
import type { ZoneSuggestion, AgentAvailability, Mission } from '../types'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface MissionPlanPanelProps {
  open: boolean
  onClose: () => void
  onMissionCreated: (mission: Mission) => void
}

interface SelectedAgent {
  agent_id: string
  agent_profile_id: string
  target_inspections: number
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DEFAULT_TARGET = 10
const MIN_TARGET = 1
const MAX_TARGET = 100

const PRIORITY_STYLES: Record<string, string> = {
  high: 'bg-red-100 text-red-700',
  medium: 'bg-amber-100 text-amber-700',
  low: 'bg-green-100 text-green-700',
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatDateLabel(dateStr: string, locale = 'es'): string {
  if (!dateStr) return ''
  const d = new Date(dateStr + 'T00:00:00')
  return d.toLocaleDateString(locale, { day: '2-digit', month: 'short', year: 'numeric' })
}

function todayISO(): string {
  const now = new Date()
  const y = now.getFullYear()
  const m = String(now.getMonth() + 1).padStart(2, '0')
  const d = String(now.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function MissionPlanPanel({
  open,
  onClose,
  onMissionCreated,
}: MissionPlanPanelProps) {
  const t = useTranslations('inspection')
  const { toast } = useToast()

  // Form state
  const [missionDate, setMissionDate] = useState(todayISO)
  const [title, setTitle] = useState('')
  const [titleManuallyEdited, setTitleManuallyEdited] = useState(false)
  const [notes, setNotes] = useState('')
  const [selectedZoneIds, setSelectedZoneIds] = useState<Set<string>>(new Set())
  const [selectedAgents, setSelectedAgents] = useState<Map<string, SelectedAgent>>(new Map())

  // Data state
  const [zones, setZones] = useState<ZoneSuggestion[]>([])
  const [agents, setAgents] = useState<AgentAvailability[]>([])
  const [zonesLoading, setZonesLoading] = useState(false)
  const [agentsLoading, setAgentsLoading] = useState(false)
  const [creating, setCreating] = useState(false)

  // ---------------------------------------------------------------------------
  // Fetch zones on mount (when panel opens)
  // ---------------------------------------------------------------------------

  useEffect(() => {
    if (!open) return
    let cancelled = false
    setZonesLoading(true)
    inspectionApi
      .suggestZones()
      .then((data) => {
        if (!cancelled) setZones(data)
      })
      .catch(() => {
        if (!cancelled) setZones([])
      })
      .finally(() => {
        if (!cancelled) setZonesLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [open])

  // ---------------------------------------------------------------------------
  // Fetch agents when date changes
  // ---------------------------------------------------------------------------

  useEffect(() => {
    if (!open || !missionDate) {
      setAgents([])
      return
    }
    let cancelled = false
    setAgentsLoading(true)
    inspectionApi
      .getAgentsAvailability(missionDate)
      .then((data) => {
        if (!cancelled) setAgents(data)
      })
      .catch(() => {
        if (!cancelled) setAgents([])
      })
      .finally(() => {
        if (!cancelled) setAgentsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [open, missionDate])

  // ---------------------------------------------------------------------------
  // Auto-suggest title when first zone selected
  // ---------------------------------------------------------------------------

  const sortedZones = useMemo(() => {
    const priorityOrder = { high: 0, medium: 1, low: 2 }
    return [...zones].sort(
      (a, b) =>
        (priorityOrder[a.suggested_priority] ?? 2) -
        (priorityOrder[b.suggested_priority] ?? 2),
    )
  }, [zones])

  useEffect(() => {
    if (titleManuallyEdited) return
    if (selectedZoneIds.size === 0) {
      setTitle('')
      return
    }
    // Use the first selected zone (by priority order)
    const firstSelectedZone = sortedZones.find((z) => selectedZoneIds.has(z.zone_id))
    if (firstSelectedZone && missionDate) {
      const label = formatDateLabel(missionDate)
      setTitle(`Mission ${firstSelectedZone.zone_code} - ${label}`)
    }
  }, [selectedZoneIds, sortedZones, missionDate, titleManuallyEdited])

  // ---------------------------------------------------------------------------
  // Reset form when panel closes
  // ---------------------------------------------------------------------------

  useEffect(() => {
    if (!open) {
      setMissionDate(todayISO())
      setTitle('')
      setTitleManuallyEdited(false)
      setNotes('')
      setSelectedZoneIds(new Set())
      setSelectedAgents(new Map())
    }
  }, [open])

  // ---------------------------------------------------------------------------
  // Handlers
  // ---------------------------------------------------------------------------

  const toggleZone = useCallback((zoneId: string) => {
    setSelectedZoneIds((prev) => {
      const next = new Set(prev)
      if (next.has(zoneId)) next.delete(zoneId)
      else next.add(zoneId)
      return next
    })
  }, [])

  const toggleAgent = useCallback(
    (agent: AgentAvailability) => {
      setSelectedAgents((prev) => {
        const next = new Map(prev)
        if (next.has(agent.agent_id)) {
          next.delete(agent.agent_id)
        } else {
          next.set(agent.agent_id, {
            agent_id: agent.agent_id,
            agent_profile_id: agent.agent_profile_id,
            target_inspections: DEFAULT_TARGET,
          })
        }
        return next
      })
    },
    [],
  )

  const updateAgentTarget = useCallback(
    (agentId: string, target: number) => {
      setSelectedAgents((prev) => {
        const next = new Map(prev)
        const existing = next.get(agentId)
        if (existing) {
          next.set(agentId, {
            ...existing,
            target_inspections: Math.max(MIN_TARGET, Math.min(MAX_TARGET, target)),
          })
        }
        return next
      })
    },
    [],
  )

  // ---------------------------------------------------------------------------
  // Validation
  // ---------------------------------------------------------------------------

  const isValid = useMemo(
    () => !!missionDate && selectedZoneIds.size > 0 && selectedAgents.size > 0,
    [missionDate, selectedZoneIds, selectedAgents],
  )

  // ---------------------------------------------------------------------------
  // Submit
  // ---------------------------------------------------------------------------

  const handleCreate = useCallback(async () => {
    if (!isValid || creating) return
    setCreating(true)
    try {
      // 1. Create the mission
      const mission = await inspectionApi.createMission({
        mission_date: missionDate,
        title: title || undefined,
        notes: notes || undefined,
        zone_ids: Array.from(selectedZoneIds),
      })

      // 2. Assign agents (rollback mission on failure)
      const agentsPayload = Array.from(selectedAgents.values()).map((a) => ({
        agent_id: a.agent_id,
        agent_profile_id: a.agent_profile_id,
        assigned_zones: Array.from(selectedZoneIds),
        target_inspections: a.target_inspections,
      }))

      try {
        await inspectionApi.assignAgents(mission.id, agentsPayload)
      } catch (assignErr) {
        // Rollback: cancel the mission since agents weren't assigned
        try {
          await inspectionApi.updateMission(mission.id, { status: 'cancelled' })
        } catch {
          // Rollback failed — mission exists without agents (manual cleanup needed)
        }
        throw assignErr // Re-throw to outer catch
      }

      toast({
        title: t('mission.created'),
        description: title || mission.title || mission.id,
      })

      onMissionCreated(mission)
      onClose()
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : String(err)
      toast({
        title: t('common.error'),
        description: message,
        variant: 'destructive',
      })
    } finally {
      setCreating(false)
    }
  }, [
    isValid,
    creating,
    missionDate,
    title,
    notes,
    selectedZoneIds,
    selectedAgents,
    onMissionCreated,
    onClose,
    toast,
    t,
  ])

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <Collapsible open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <CollapsibleContent className="overflow-hidden data-[state=closed]:animate-collapse data-[state=open]:animate-expand">
        <div className="rounded-lg border bg-muted/30 p-4">
          {/* Header */}
          <div className="mb-4 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <CalendarDays className="h-4 w-4 text-primary" />
              <h3 className="text-sm font-semibold">{t('mission.create')}</h3>
            </div>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              onClick={onClose}
            >
              <X className="h-4 w-4" />
            </Button>
          </div>

          {/* Form grid */}
          <div className="grid gap-4 md:grid-cols-2">
            {/* ---- Left column: date, title, notes ---- */}
            <div className="flex flex-col gap-3">
              {/* Date */}
              <div className="flex flex-col gap-1">
                <label className="text-xs font-medium text-muted-foreground">
                  {t('mission.missionDate')} *
                </label>
                <Input
                  type="date"
                  value={missionDate}
                  onChange={(e) => setMissionDate(e.target.value)}
                  className="h-9 text-sm"
                />
              </div>

              {/* Title */}
              <div className="flex flex-col gap-1">
                <label className="text-xs font-medium text-muted-foreground">
                  {t('mission.title')}
                </label>
                <Input
                  value={title}
                  onChange={(e) => {
                    setTitle(e.target.value)
                    setTitleManuallyEdited(true)
                  }}
                  placeholder={t('mission.title')}
                  className="h-9 text-sm"
                />
              </div>

              {/* Notes */}
              <div className="flex flex-col gap-1">
                <label className="text-xs font-medium text-muted-foreground">
                  {t('mission.notes')}
                </label>
                <textarea
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder={t('mission.notes')}
                  rows={3}
                  className="rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                />
              </div>
            </div>

            {/* ---- Right column: zones ---- */}
            <div className="flex flex-col gap-1">
              <label className="text-xs font-medium text-muted-foreground">
                {t('mission.selectZones')} *
              </label>
              <div className="max-h-[220px] overflow-y-auto rounded-md border bg-background p-2">
                {zonesLoading ? (
                  <div className="flex flex-col gap-2">
                    {Array.from({ length: 4 }).map((_, i) => (
                      <Skeleton key={i} className="h-8 w-full rounded" />
                    ))}
                  </div>
                ) : sortedZones.length === 0 ? (
                  <p className="py-4 text-center text-xs text-muted-foreground">
                    {t('mission.selectZones')}
                  </p>
                ) : (
                  <div className="flex flex-col gap-1">
                    {sortedZones.map((zone) => {
                      const checked = selectedZoneIds.has(zone.zone_id)
                      return (
                        <label
                          key={zone.zone_id}
                          className={cn(
                            'flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 transition-colors hover:bg-muted',
                            checked && 'bg-primary/5',
                          )}
                        >
                          <Checkbox
                            checked={checked}
                            onCheckedChange={() => toggleZone(zone.zone_id)}
                          />
                          <span className="flex-1 text-xs font-medium">
                            {zone.zone_code} - {zone.zone_name}
                          </span>
                          <div className="flex items-center gap-1.5">
                            {zone.days_since_last_inspection != null && (
                              <Badge
                                variant="outline"
                                className="h-5 px-1.5 text-[10px] tabular-nums"
                              >
                                {zone.days_since_last_inspection}d
                              </Badge>
                            )}
                            <Badge
                              className={cn(
                                'h-5 px-1.5 text-[10px]',
                                PRIORITY_STYLES[zone.suggested_priority] ||
                                  'bg-gray-100 text-gray-700',
                              )}
                            >
                              {zone.suggested_priority}
                            </Badge>
                          </div>
                        </label>
                      )
                    })}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* ---- Agents section (full width) ---- */}
          <div className="mt-4 flex flex-col gap-1">
            <label className="text-xs font-medium text-muted-foreground">
              {t('mission.selectAgents')} *
            </label>
            <div className="max-h-[200px] overflow-y-auto rounded-md border bg-background p-2">
              {agentsLoading ? (
                <div className="flex flex-col gap-2">
                  {Array.from({ length: 3 }).map((_, i) => (
                    <Skeleton key={i} className="h-9 w-full rounded" />
                  ))}
                </div>
              ) : agents.length === 0 ? (
                <p className="py-4 text-center text-xs text-muted-foreground">
                  {missionDate
                    ? t('mission.selectAgents')
                    : t('mission.missionDate')}
                </p>
              ) : (
                <div className="flex flex-col gap-1">
                  {agents.map((agent) => {
                    const selected = selectedAgents.has(agent.agent_id)
                    const agentData = selectedAgents.get(agent.agent_id)

                    return (
                      <div
                        key={agent.agent_id}
                        className={cn(
                          'flex items-center gap-2 rounded-md px-2 py-1.5 transition-colors',
                          selected ? 'bg-primary/5' : 'hover:bg-muted',
                          !agent.is_available && 'opacity-60',
                        )}
                      >
                        <Checkbox
                          checked={selected}
                          onCheckedChange={() => toggleAgent(agent)}
                          disabled={!agent.is_available && !selected}
                        />

                        {/* Availability indicator */}
                        <span
                          className={cn(
                            'h-2 w-2 shrink-0 rounded-full',
                            agent.is_available
                              ? 'bg-green-500'
                              : 'bg-gray-400',
                          )}
                        />

                        <span className="flex-1 text-xs font-medium">
                          {agent.agent_name}
                        </span>

                        {agent.current_mission && (
                          <Badge
                            variant="outline"
                            className="h-5 px-1.5 text-[10px]"
                          >
                            {agent.availability_status}
                          </Badge>
                        )}

                        {/* Target inspections input (visible when selected) */}
                        {selected && (
                          <div className="flex items-center gap-1">
                            <label className="text-[10px] text-muted-foreground">
                              {t('mission.targetInspections')}:
                            </label>
                            <Input
                              type="number"
                              min={MIN_TARGET}
                              max={MAX_TARGET}
                              value={agentData?.target_inspections ?? DEFAULT_TARGET}
                              onChange={(e) =>
                                updateAgentTarget(
                                  agent.agent_id,
                                  parseInt(e.target.value, 10) || DEFAULT_TARGET,
                                )
                              }
                              className="h-7 w-16 text-center text-xs tabular-nums"
                            />
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          </div>

          {/* ---- Actions ---- */}
          <div className="mt-4 flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              {selectedZoneIds.size > 0 && (
                <Badge variant="secondary" className="text-[10px]">
                  {selectedZoneIds.size} {t('mission.selectZones').toLowerCase()}
                </Badge>
              )}
              {selectedAgents.size > 0 && (
                <Badge variant="secondary" className="text-[10px]">
                  {selectedAgents.size} {t('mission.agents').toLowerCase()}
                </Badge>
              )}
            </div>

            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                className="h-8 text-xs"
                onClick={onClose}
                disabled={creating}
              >
                {t('mission.cancel')}
              </Button>
              <Button
                size="sm"
                className="h-8 gap-1.5 text-xs"
                onClick={handleCreate}
                disabled={!isValid || creating}
              >
                {creating && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                {creating ? t('mission.creating') : t('mission.save')}
              </Button>
            </div>
          </div>
        </div>
      </CollapsibleContent>
    </Collapsible>
  )
}
