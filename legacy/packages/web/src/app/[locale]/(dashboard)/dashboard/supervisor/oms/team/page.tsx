'use client'

/**
 * Supervisor OMS Team — Per-agent obligation processing performance
 *
 * Shows each agent's workload, completion rate, rejection rate,
 * processed amount, and average processing time. Supervisor-only.
 */

import { useCallback, useEffect, useState } from 'react'
import { useLocale, useTranslations } from 'next-intl'
import {
  Users, Clock, CheckCircle2, AlertTriangle,
  RefreshCw, XCircle, ArrowUpDown, ArrowUp, ArrowDown,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table'
import { useToast } from '@/hooks/use-toast'
import { omsQueueApi } from '@/modules/oms/services/api'
import type { AgentPerformance, TeamPerformanceResponse } from '@/modules/oms/types'
import { fmtXAF } from '@/modules/oms/utils/formatters'

const AVAILABILITY_BADGE: Record<string, { color: string; label: string }> = {
  available:               { color: 'bg-green-100 text-green-800', label: 'Disponible' },
  on_leave:                { color: 'bg-gray-100 text-gray-700',   label: 'Permiso' },
  sick_leave:              { color: 'bg-yellow-100 text-yellow-800', label: 'Baja' },
  training:                { color: 'bg-blue-100 text-blue-800',   label: 'Formación' },
  temporarily_unavailable: { color: 'bg-red-100 text-red-800',     label: 'No disponible' },
}

export default function SupervisorOmsTeamPage() {
  const locale = useLocale()
  const t = useTranslations('oms')
  const { toast } = useToast()

  const [data, setData] = useState<TeamPerformanceResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [period, setPeriod] = useState('30')
  const [sortCol, setSortCol] = useState<keyof AgentPerformance>('obligations_completed')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')

  const fetchData = useCallback(async () => {
    setLoading(true)
    try {
      const res = await omsQueueApi.getTeamPerformance({
        period_days: Number(period),
        fiscal_year: new Date().getFullYear(),
      })
      setData(res)
    } catch {
      toast({ title: t('team.loadError'), variant: 'destructive' })
    } finally {
      setLoading(false)
    }
  }, [period, toast, t])

  useEffect(() => { fetchData() }, [fetchData])

  const toggleSort = (col: keyof AgentPerformance) => {
    if (sortCol === col) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortCol(col); setSortDir('desc') }
  }

  const sortedAgents = [...(data?.agents ?? [])].sort((a, b) => {
    const va = a[sortCol]
    const vb = b[sortCol]
    if (typeof va === 'string') return sortDir === 'asc' ? va.localeCompare(vb as string) : (vb as string).localeCompare(va)
    return sortDir === 'asc' ? (va as number) - (vb as number) : (vb as number) - (va as number)
  })

  const totals = data?.team_totals
  const SortIcon = ({ col }: { col: keyof AgentPerformance }) => {
    if (sortCol !== col) return <ArrowUpDown className="h-3 w-3 opacity-30" />
    return sortDir === 'asc' ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />
  }

  return (
    <div className="space-y-4 p-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold flex items-center gap-2">
            <Users className="h-5 w-5" />
            {t('team.title')}
          </h1>
          <p className="text-sm text-muted-foreground">{t('team.subtitle')}</p>
        </div>
        <div className="flex gap-2">
          <Select value={period} onValueChange={setPeriod}>
            <SelectTrigger className="w-[100px] h-8 text-xs"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="7">7 {t('team.days')}</SelectItem>
              <SelectItem value="30">30 {t('team.days')}</SelectItem>
              <SelectItem value="90">90 {t('team.days')}</SelectItem>
            </SelectContent>
          </Select>
          <Button variant="outline" size="sm" onClick={fetchData} disabled={loading}>
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </div>

      {/* Team KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        {loading && !totals ? (
          Array.from({ length: 5 }).map((_, i) => (
            <Card key={i} className="p-3"><Skeleton className="h-14 w-full" /></Card>
          ))
        ) : totals ? (<>
          <Card className="p-3">
            <div className="text-xs text-muted-foreground">{t('team.activeAgents')}</div>
            <p className="text-2xl font-bold">{totals.total_agents}</p>
          </Card>
          <Card className="p-3">
            <div className="text-xs text-muted-foreground">{t('team.totalCompleted')}</div>
            <p className="text-2xl font-bold text-green-700">{totals.total_completed}</p>
            <p className="text-[10px] text-muted-foreground">/ {totals.total_assigned} {t('team.assigned')}</p>
          </Card>
          <Card className="p-3">
            <div className="text-xs text-muted-foreground">{t('team.totalPending')}</div>
            <p className="text-2xl font-bold text-amber-700">{totals.total_pending}</p>
          </Card>
          <Card className="p-3">
            <div className="text-xs text-muted-foreground">{t('team.amountProcessed')}</div>
            <p className="text-lg font-bold">{fmtXAF(totals.total_amount_processed, locale)}</p>
          </Card>
          <Card className="p-3">
            <div className="text-xs text-muted-foreground">{t('team.avgCompletionRate')}</div>
            <p className="text-2xl font-bold">{totals.avg_completion_rate}%</p>
            <Progress value={totals.avg_completion_rate} className="h-1.5 mt-1" />
          </Card>
        </>) : null}
      </div>

      {/* Agent Performance Table */}
      <Card>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="text-xs">
                <button onClick={() => toggleSort('agent_name')} className="flex items-center gap-1 hover:text-foreground">
                  {t('team.agent')} <SortIcon col="agent_name" />
                </button>
              </TableHead>
              <TableHead className="text-xs w-[70px]">{t('team.role')}</TableHead>
              <TableHead className="text-xs w-[70px]">{t('team.status')}</TableHead>
              <TableHead className="text-xs w-[70px] text-center">
                <button onClick={() => toggleSort('obligations_assigned')} className="flex items-center gap-1 hover:text-foreground">
                  {t('team.assigned')} <SortIcon col="obligations_assigned" />
                </button>
              </TableHead>
              <TableHead className="text-xs w-[70px] text-center">
                <button onClick={() => toggleSort('obligations_completed')} className="flex items-center gap-1 hover:text-foreground">
                  <CheckCircle2 className="h-3 w-3 text-green-600" /> <SortIcon col="obligations_completed" />
                </button>
              </TableHead>
              <TableHead className="text-xs w-[60px] text-center">
                <button onClick={() => toggleSort('obligations_pending')} className="flex items-center gap-1 hover:text-foreground">
                  <Clock className="h-3 w-3 text-amber-600" /> <SortIcon col="obligations_pending" />
                </button>
              </TableHead>
              <TableHead className="text-xs w-[60px] text-center">
                <button onClick={() => toggleSort('obligations_rejected')} className="flex items-center gap-1 hover:text-foreground">
                  <XCircle className="h-3 w-3 text-red-500" /> <SortIcon col="obligations_rejected" />
                </button>
              </TableHead>
              <TableHead className="text-xs w-[100px] text-right">
                <button onClick={() => toggleSort('amount_processed')} className="flex items-center gap-1 ml-auto hover:text-foreground">
                  {t('team.amount')} <SortIcon col="amount_processed" />
                </button>
              </TableHead>
              <TableHead className="text-xs w-[60px] text-center">
                <button onClick={() => toggleSort('avg_processing_minutes')} className="flex items-center gap-1 hover:text-foreground">
                  {t('team.avgTime')} <SortIcon col="avg_processing_minutes" />
                </button>
              </TableHead>
              <TableHead className="text-xs w-[100px]">
                <button onClick={() => toggleSort('completion_rate')} className="flex items-center gap-1 hover:text-foreground">
                  {t('team.rate')} <SortIcon col="completion_rate" />
                </button>
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow><TableCell colSpan={10} className="text-center py-8">...</TableCell></TableRow>
            ) : sortedAgents.length === 0 ? (
              <TableRow>
                <TableCell colSpan={10} className="text-center py-12 text-muted-foreground">
                  <Users className="h-8 w-8 mx-auto mb-2 opacity-30" />
                  <p>{t('team.noAgents')}</p>
                </TableCell>
              </TableRow>
            ) : sortedAgents.map(agent => {
              const avail = AVAILABILITY_BADGE[agent.availability] || AVAILABILITY_BADGE.available
              const rateColor = agent.completion_rate >= 80 ? 'text-green-700' : agent.completion_rate >= 50 ? 'text-amber-700' : 'text-red-700'
              return (
                <TableRow key={agent.agent_profile_id}>
                  <TableCell className="text-xs font-medium">{agent.agent_name}</TableCell>
                  <TableCell className="text-[10px] text-muted-foreground font-mono">{agent.entity_code}</TableCell>
                  <TableCell>
                    <Badge className={`text-[9px] ${avail.color}`}>{avail.label}</Badge>
                  </TableCell>
                  <TableCell className="text-xs text-center font-mono">{agent.obligations_assigned}</TableCell>
                  <TableCell className="text-xs text-center font-mono text-green-700">{agent.obligations_completed}</TableCell>
                  <TableCell className="text-xs text-center font-mono text-amber-700">{agent.obligations_pending}</TableCell>
                  <TableCell className="text-xs text-center font-mono text-red-600">{agent.obligations_rejected}</TableCell>
                  <TableCell className="text-xs text-right font-mono">{fmtXAF(agent.amount_processed, locale)}</TableCell>
                  <TableCell className="text-xs text-center">{agent.avg_processing_minutes > 0 ? `${agent.avg_processing_minutes}m` : '—'}</TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <Progress value={agent.completion_rate} className="h-1.5 flex-1" />
                      <span className={`text-xs font-bold ${rateColor}`}>{agent.completion_rate}%</span>
                    </div>
                    {agent.rejection_rate > 5 && (
                      <div className="flex items-center gap-1 mt-0.5">
                        <AlertTriangle className="h-3 w-3 text-red-500" />
                        <span className="text-[9px] text-red-600">{agent.rejection_rate}% {t('team.rejections')}</span>
                      </div>
                    )}
                  </TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      </Card>
    </div>
  )
}
