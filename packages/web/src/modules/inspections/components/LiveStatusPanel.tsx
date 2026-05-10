'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import { useLocale, useTranslations } from 'next-intl'
import {
  Activity, Users, ClipboardCheck, DollarSign, Wallet,
  Circle, Radio, RefreshCw,
} from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/core/utils'
import { inspectionApi } from '../services/api'
import { fmtXAF } from '../utils/formatters'
import type { LiveStatusResponse, AgentLiveStatus, AgentOnlineStatus } from '../types'

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const STATUS_CONFIG: Record<AgentOnlineStatus, { color: string; bg: string; dot: string; pulse: boolean }> = {
  active: { color: 'text-green-700', bg: 'bg-green-50 border-green-200', dot: 'bg-green-500', pulse: true },
  idle: { color: 'text-amber-700', bg: 'bg-amber-50 border-amber-200', dot: 'bg-amber-500', pulse: false },
  offline: { color: 'text-gray-500', bg: 'bg-gray-50 border-gray-200', dot: 'bg-gray-400', pulse: false },
}

const POLL_INTERVAL = 30_000 // 30 seconds

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatActivityTime(minutes: number | undefined | null, t: ReturnType<typeof useTranslations>): string {
  if (minutes === null || minutes === undefined || isNaN(minutes)) return t('live.noActivity')
  if (minutes < 1) return t('live.active')
  if (minutes < 60) return t('live.minutesAgo', { min: Math.round(minutes) })
  return t('live.hoursAgo', { hours: Math.round(minutes / 60) })
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function LiveStatusPanel() {
  const locale = useLocale()
  const t = useTranslations('inspection')

  const [data, setData] = useState<LiveStatusResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  // -----------------------------------------------------------------------
  // Fetch
  // -----------------------------------------------------------------------

  const fetchLiveStatus = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true)
    else setLoading(true)
    try {
      const result = await inspectionApi.getLiveStatus()
      setData(result)
    } catch {
      // Non-critical — keep stale data
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, []) // No deps — always fetches fresh from API

  // Initial fetch
  useEffect(() => { fetchLiveStatus() }, [fetchLiveStatus])

  // Polling every 30s — stable ref prevents interval reset
  useEffect(() => {
    const interval = setInterval(() => fetchLiveStatus(true), POLL_INTERVAL)
    return () => clearInterval(interval)
  }, [fetchLiveStatus])

  // -----------------------------------------------------------------------
  // Derived data
  // -----------------------------------------------------------------------

  const sortedAgents = useMemo(() => {
    if (!data) return []
    const order: Record<AgentOnlineStatus, number> = { active: 0, idle: 1, offline: 2 }
    return [...data.agents].sort((a, b) =>
      (order[a.status] ?? 2) - (order[b.status] ?? 2)
      || (a.minutes_since_activity ?? 9999) - (b.minutes_since_activity ?? 9999)
    )
  }, [data])

  // -----------------------------------------------------------------------
  // Loading skeleton
  // -----------------------------------------------------------------------

  if (loading || !data) {
    return (
      <div className="space-y-3">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          {[1, 2, 3, 4].map(i => <Skeleton key={i} className="h-16" />)}
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-2">
          {[1, 2, 3, 4, 5, 6].map(i => <Skeleton key={i} className="h-20" />)}
        </div>
      </div>
    )
  }

  const { counters } = data

  // -----------------------------------------------------------------------
  // Render
  // -----------------------------------------------------------------------

  return (
    <div className="space-y-3">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Radio className="h-4 w-4 text-green-600 animate-pulse" />
          <span className="text-sm font-medium">{t('live.title')}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-muted-foreground">
            {data.cached_at && t('live.lastUpdate', {
              time: new Date(data.cached_at).toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
            })}
          </span>
          <Button
            variant="ghost" size="icon" className="h-6 w-6"
            onClick={() => fetchLiveStatus(true)}
            disabled={refreshing}
          >
            <RefreshCw className={cn('h-3 w-3', refreshing && 'animate-spin')} />
          </Button>
        </div>
      </div>

      {/* Counters row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
        {/* Agents status */}
        <Card className="shadow-sm">
          <CardContent className="p-2.5 flex items-center gap-2">
            <Users className="h-4 w-4 text-blue-600 shrink-0" />
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-1.5">
                <span className="font-bold tabular-nums">{counters.total_agents}</span>
                <span className="text-[10px] text-muted-foreground">{t('live.agents')}</span>
              </div>
              <div className="flex items-center gap-2 text-[10px]">
                <span className="flex items-center gap-0.5">
                  <Circle className="h-2 w-2 fill-green-500 text-green-500" />
                  {counters.active_agents}
                </span>
                <span className="flex items-center gap-0.5">
                  <Circle className="h-2 w-2 fill-amber-500 text-amber-500" />
                  {counters.idle_agents}
                </span>
                <span className="flex items-center gap-0.5">
                  <Circle className="h-2 w-2 fill-gray-400 text-gray-400" />
                  {counters.offline_agents}
                </span>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Inspections today */}
        <Card className="shadow-sm">
          <CardContent className="p-2.5 flex items-center gap-2">
            <ClipboardCheck className="h-4 w-4 text-blue-600 shrink-0" />
            <div className="min-w-0">
              <p className="font-bold tabular-nums">{counters.inspections_today}</p>
              <p className="text-[10px] text-muted-foreground">{t('live.inspectionsToday')}</p>
            </div>
            {counters.inspections_in_progress > 0 && (
              <Badge className="ml-auto bg-blue-100 text-blue-800 text-[10px] shrink-0">
                <Activity className="h-2.5 w-2.5 mr-0.5" />
                {counters.inspections_in_progress} {t('live.inProgress')}
              </Badge>
            )}
          </CardContent>
        </Card>

        {/* Cash collected */}
        <Card className="shadow-sm">
          <CardContent className="p-2.5 flex items-center gap-2">
            <DollarSign className="h-4 w-4 text-amber-600 shrink-0" />
            <div className="min-w-0">
              <p className="font-bold tabular-nums">{fmtXAF(counters.cash_collected_today, locale)}</p>
              <p className="text-[10px] text-muted-foreground">{t('live.cashCollected')}</p>
            </div>
          </CardContent>
        </Card>

        {/* Cash pending */}
        <Card className={cn('shadow-sm', counters.cash_pending_reconciliation > 0 && 'border-red-200 bg-red-50/30')}>
          <CardContent className="p-2.5 flex items-center gap-2">
            <Wallet className={cn('h-4 w-4 shrink-0', counters.cash_pending_reconciliation > 0 ? 'text-red-600' : 'text-muted-foreground')} />
            <div className="min-w-0">
              <p className="font-bold tabular-nums">{fmtXAF(counters.cash_pending_reconciliation, locale)}</p>
              <p className="text-[10px] text-muted-foreground">{t('live.cashPending')}</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Agent cards grid */}
      {sortedAgents.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-2">
          {sortedAgents.map((agent) => (
            <AgentCard key={agent.agent_id} agent={agent} t={t} locale={locale} />
          ))}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// AgentCard sub-component
// ---------------------------------------------------------------------------

function AgentCard({
  agent,
  t,
  locale,
}: {
  agent: AgentLiveStatus
  t: ReturnType<typeof useTranslations>
  locale: string
}) {
  const cfg = STATUS_CONFIG[agent.status]

  return (
    <div className={cn(
      'rounded-lg border p-2.5 transition-colors',
      cfg.bg,
    )}>
      {/* Name + status dot */}
      <div className="flex items-center gap-1.5 mb-1">
        <span className="relative flex h-2.5 w-2.5 shrink-0">
          <span className={cn('absolute inline-flex h-full w-full rounded-full', cfg.dot, cfg.pulse && 'animate-ping opacity-75')} />
          <span className={cn('relative inline-flex h-2.5 w-2.5 rounded-full', cfg.dot)} />
        </span>
        <span className="font-medium text-xs truncate">{agent.agent_name}</span>
      </div>

      {/* Status label + time */}
      <div className="flex items-center justify-between text-[10px] mb-1.5">
        <Badge variant="secondary" className={cn('h-4 px-1.5 text-[9px]', cfg.color)}>
          {t(`live.${agent.status}`)}
        </Badge>
        <span className="text-muted-foreground tabular-nums">
          {formatActivityTime(agent.minutes_since_activity, t)}
        </span>
      </div>

      {/* Today's stats */}
      <div className="grid grid-cols-2 gap-x-2 text-[10px]">
        <div>
          <span className="text-muted-foreground">{t('live.inspectionsToday')}</span>
          <p className="font-semibold tabular-nums">{agent.inspections_today}</p>
        </div>
        <div>
          <span className="text-muted-foreground">{t('live.cashCollected')}</span>
          <p className="font-semibold tabular-nums">{fmtXAF(agent.cash_collected_today, locale)}</p>
        </div>
      </div>

      {/* In-progress indicator */}
      {agent.current_inspection_id && (
        <div className="mt-1.5 flex items-center gap-1 text-[9px] text-blue-700 bg-blue-100 rounded px-1.5 py-0.5">
          <Activity className="h-2.5 w-2.5" />
          {t('live.currentInspection')}
        </div>
      )}
    </div>
  )
}
