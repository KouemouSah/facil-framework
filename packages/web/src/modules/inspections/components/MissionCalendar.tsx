'use client'

import { useCallback, useMemo, useState } from 'react'
import { useLocale, useTranslations } from 'next-intl'
import { ChevronLeft, ChevronRight, Plus, MapPin, Users } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/core/utils'
import type { MissionListItem, MissionStatus } from '../types'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface MissionCalendarProps {
  missions: MissionListItem[]
  loading?: boolean
  onMissionClick?: (missionId: string) => void
  onWeekChange?: (weekStart: string) => void
  onCreateMission?: () => void
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const STATUS_STYLES: Record<MissionStatus, string> = {
  planned: 'border-l-blue-500 bg-blue-50',
  in_progress: 'border-l-amber-500 bg-amber-50',
  completed: 'border-l-green-500 bg-green-50',
  cancelled: 'border-l-gray-400 bg-gray-50',
}

// Day names derived at render time via locale-aware toLocaleDateString

// ---------------------------------------------------------------------------
// Date Helpers
// ---------------------------------------------------------------------------

/** Returns the Monday of the week containing `date`. */
function getMonday(date: Date): Date {
  const d = new Date(date)
  const day = d.getDay()
  // Sunday = 0 → offset 6, Monday = 1 → offset 0, etc.
  const diff = day === 0 ? 6 : day - 1
  d.setDate(d.getDate() - diff)
  d.setHours(0, 0, 0, 0)
  return d
}

function addDays(date: Date, days: number): Date {
  const d = new Date(date)
  d.setDate(d.getDate() + days)
  return d
}

function formatISO(date: Date): string {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

function formatDayNumber(date: Date): string {
  return String(date.getDate())
}

function formatMonthShort(date: Date, locale = 'es'): string {
  return date.toLocaleDateString(locale, { month: 'short' })
}

function isSameDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  )
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function MissionCard({
  mission,
  onClick,
  t,
}: {
  mission: MissionListItem
  onClick?: (id: string) => void
  t: ReturnType<typeof useTranslations>
}) {
  const progress =
    mission.inspections_target > 0
      ? Math.round((mission.inspections_done / mission.inspections_target) * 100)
      : 0

  return (
    <button
      type="button"
      onClick={() => onClick?.(mission.id)}
      className={cn(
        'w-full rounded-md border-l-4 p-2.5 text-left transition-shadow hover:shadow-md',
        STATUS_STYLES[mission.status],
      )}
    >
      {/* Title */}
      <p className="truncate text-xs font-semibold text-foreground">
        {mission.title || t('mission.missionOf')}
      </p>

      {/* Location */}
      <div className="mt-1 flex items-center gap-1 text-[11px] text-muted-foreground">
        <MapPin className="h-3 w-3 shrink-0" />
        <span className="truncate">{mission.location_name}</span>
      </div>

      {/* Progress bar */}
      <div className="mt-1.5">
        <div className="flex items-center justify-between text-[10px] text-muted-foreground">
          <span>{t('mission.inspections')}</span>
          <span className="tabular-nums">
            {mission.inspections_done}/{mission.inspections_target}
          </span>
        </div>
        <div className="mt-0.5 h-1.5 w-full rounded-full bg-muted">
          <div
            className={cn(
              'h-full rounded-full transition-all',
              mission.status === 'completed'
                ? 'bg-green-500'
                : mission.status === 'in_progress'
                  ? 'bg-amber-500'
                  : 'bg-blue-400',
            )}
            style={{ width: `${Math.min(progress, 100)}%` }}
          />
        </div>
      </div>

      {/* Agents badge + status */}
      <div className="mt-1.5 flex items-center justify-between">
        <div className="flex items-center gap-1 text-[11px] text-muted-foreground">
          <Users className="h-3 w-3" />
          <span>{mission.agents_count}</span>
        </div>
        <Badge
          variant="secondary"
          className={cn(
            'h-4 px-1.5 text-[10px] font-medium',
            mission.status === 'planned' && 'bg-blue-100 text-blue-700',
            mission.status === 'in_progress' && 'bg-amber-100 text-amber-700',
            mission.status === 'completed' && 'bg-green-100 text-green-700',
            mission.status === 'cancelled' && 'bg-gray-100 text-gray-500',
          )}
        >
          {t(`mission.${mission.status}`)}
        </Badge>
      </div>
    </button>
  )
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function MissionCalendar({
  missions,
  loading,
  onMissionClick,
  onWeekChange,
  onCreateMission,
}: MissionCalendarProps) {
  const t = useTranslations('inspection')
  const locale = useLocale()
  const today = useMemo(() => new Date(), [])

  const [weekStart, setWeekStart] = useState<Date>(() => getMonday(today))

  // Weekday dates (Mon-Fri)
  const weekDays = useMemo(
    () => Array.from({ length: 5 }, (_, i) => addDays(weekStart, i)),
    [weekStart],
  )

  // Group missions by date string
  const missionsByDay = useMemo(() => {
    const map = new Map<string, MissionListItem[]>()
    for (const m of missions) {
      const dateKey = m.mission_date.slice(0, 10) // YYYY-MM-DD
      if (!map.has(dateKey)) map.set(dateKey, [])
      map.get(dateKey)!.push(m)
    }
    return map
  }, [missions])

  // Navigation
  const goToPrevWeek = useCallback(() => {
    setWeekStart((prev) => {
      const next = addDays(prev, -7)
      onWeekChange?.(formatISO(next))
      return next
    })
  }, [onWeekChange])

  const goToNextWeek = useCallback(() => {
    setWeekStart((prev) => {
      const next = addDays(prev, 7)
      onWeekChange?.(formatISO(next))
      return next
    })
  }, [onWeekChange])

  const goToThisWeek = useCallback(() => {
    const monday = getMonday(new Date())
    setWeekStart(monday)
    onWeekChange?.(formatISO(monday))
  }, [onWeekChange])

  // Week label
  const weekLabel = useMemo(() => {
    const day = formatDayNumber(weekStart)
    const month = formatMonthShort(weekStart)
    const year = weekStart.getFullYear()
    return t('mission.weekOf', { date: `${day} ${month} ${year}` })
  }, [weekStart, t])

  // -----------------------------------------------------------------------
  // Loading skeleton
  // -----------------------------------------------------------------------
  if (loading) {
    return (
      <div className="flex flex-col gap-3">
        {/* Header skeleton */}
        <div className="flex items-center justify-between">
          <Skeleton className="h-8 w-8 rounded" />
          <Skeleton className="h-5 w-40" />
          <Skeleton className="h-8 w-8 rounded" />
        </div>
        {/* Columns skeleton - desktop */}
        <div className="hidden gap-2 md:grid md:grid-cols-5">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="flex flex-col gap-2 rounded-lg border border-dashed p-2">
              <Skeleton className="h-4 w-20" />
              <Skeleton className="h-20 w-full rounded-md" />
              <Skeleton className="h-20 w-full rounded-md" />
            </div>
          ))}
        </div>
        {/* Mobile skeleton */}
        <div className="flex flex-col gap-2 md:hidden">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-24 w-full rounded-md" />
          ))}
        </div>
      </div>
    )
  }

  // -----------------------------------------------------------------------
  // Render
  // -----------------------------------------------------------------------
  return (
    <div className="flex flex-col gap-3">
      {/* ---- Header ---- */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1">
          <Button
            variant="outline"
            size="icon"
            className="h-8 w-8"
            onClick={goToPrevWeek}
            aria-label={t('mission.prevWeek')}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-8 px-3 text-xs font-medium"
            onClick={goToThisWeek}
          >
            {t('mission.thisWeek')}
          </Button>
          <Button
            variant="outline"
            size="icon"
            className="h-8 w-8"
            onClick={goToNextWeek}
            aria-label={t('mission.nextWeek')}
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>

        <span className="text-sm font-medium text-muted-foreground">
          {weekLabel}
        </span>

        {onCreateMission && (
          <Button
            size="sm"
            className="h-8 gap-1 px-3 text-xs"
            onClick={onCreateMission}
          >
            <Plus className="h-3.5 w-3.5" />
            {t('mission.create')}
          </Button>
        )}
      </div>

      {/* ---- Desktop: 5-column grid ---- */}
      <div className="hidden gap-2 md:grid md:grid-cols-5">
        {weekDays.map((day) => {
          const key = formatISO(day)
          const dayMissions = missionsByDay.get(key) || []
          const isToday = isSameDay(day, today)

          return (
            <div
              key={key}
              className={cn(
                'flex min-h-[200px] flex-col rounded-lg border p-2',
                isToday
                  ? 'border-blue-200 bg-blue-50/50'
                  : dayMissions.length === 0
                    ? 'border-dashed border-muted-foreground/20'
                    : 'border-muted',
              )}
            >
              {/* Day header */}
              <div className="mb-2 flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <span
                    className={cn(
                      'flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold',
                      isToday
                        ? 'bg-blue-600 text-white'
                        : 'text-muted-foreground',
                    )}
                  >
                    {formatDayNumber(day)}
                  </span>
                  <span className="text-[11px] text-muted-foreground">
                    {day.toLocaleDateString(locale, { weekday: 'short' })}
                  </span>
                </div>
                {dayMissions.length > 0 && (
                  <Badge variant="secondary" className="h-4 px-1 text-[10px]">
                    {dayMissions.length}
                  </Badge>
                )}
              </div>

              {/* Scrollable mission list */}
              <div className="flex flex-1 flex-col gap-1.5 overflow-y-auto" style={{ maxHeight: 'calc(100vh - 320px)' }}>
                {dayMissions.length === 0 && (
                  <div className="flex flex-1 items-center justify-center">
                    <p className="text-[11px] text-muted-foreground/50">
                      {t('mission.noMissions')}
                    </p>
                  </div>
                )}
                {dayMissions.map((mission) => (
                  <MissionCard
                    key={mission.id}
                    mission={mission}
                    onClick={onMissionClick}
                    t={t}
                  />
                ))}
              </div>
            </div>
          )
        })}
      </div>

      {/* ---- Mobile: vertical list ---- */}
      <div className="flex flex-col gap-3 md:hidden">
        {weekDays.map((day) => {
          const key = formatISO(day)
          const dayMissions = missionsByDay.get(key) || []
          const isToday = isSameDay(day, today)

          if (dayMissions.length === 0 && !isToday) return null

          return (
            <div key={key}>
              {/* Day label */}
              <div className="mb-1.5 flex items-center gap-2">
                <span
                  className={cn(
                    'flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold',
                    isToday
                      ? 'bg-blue-600 text-white'
                      : 'bg-muted text-muted-foreground',
                  )}
                >
                  {formatDayNumber(day)}
                </span>
                <span className="text-xs font-medium text-muted-foreground">
                  {day.toLocaleDateString(locale, { weekday: 'short' })}
                </span>
                {isToday && (
                  <Badge variant="secondary" className="h-4 px-1.5 text-[10px]">
                    {t('mission.thisWeek')}
                  </Badge>
                )}
              </div>

              {/* Missions */}
              {dayMissions.length === 0 ? (
                <p className="pl-9 text-xs text-muted-foreground/50">
                  {t('mission.noMissions')}
                </p>
              ) : (
                <div className="flex flex-col gap-1.5 pl-9">
                  {dayMissions.map((mission) => (
                    <MissionCard
                      key={mission.id}
                      mission={mission}
                      onClick={onMissionClick}
                      t={t}
                    />
                  ))}
                </div>
              )}
            </div>
          )
        })}

        {/* If entire week is empty on mobile */}
        {weekDays.every(
          (day) => (missionsByDay.get(formatISO(day)) || []).length === 0,
        ) && (
          <div className="flex flex-col items-center justify-center gap-2 py-12">
            <p className="text-sm font-medium text-muted-foreground">
              {t('mission.noMissions')}
            </p>
            <p className="text-xs text-muted-foreground/70">
              {t('mission.noMissionsDesc')}
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
