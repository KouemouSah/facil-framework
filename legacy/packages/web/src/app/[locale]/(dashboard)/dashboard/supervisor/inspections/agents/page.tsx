'use client'

/**
 * Supervisor Inspections — Agent Performance Page
 *
 * Displays agent performance metrics for field inspections.
 * Accessed via /supervisor/inspections/agents
 */

import { useCallback, useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useLocale, useTranslations } from 'next-intl'
import { useToast } from '@/hooks/use-toast'
import {
  ArrowLeft, Users, TrendingUp, Clock, CheckCircle2, RefreshCw,
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table'
import { inspectionApi } from '@/modules/inspections/services/api'
import type { AgentPerformanceResponse, AgentPerformanceItem } from '@/modules/inspections/types'

export default function AgentPerformancePage() {
  const locale = useLocale()
  const router = useRouter()
  const { toast } = useToast()
  const t = useTranslations('inspection')

  const [data, setData] = useState<AgentPerformanceResponse | null>(null)
  const [loading, setLoading] = useState(true)

  const fetch = useCallback(async () => {
    try {
      setLoading(true)
      const result = await inspectionApi.getAgentPerformance()
      setData(result)
    } catch {
      toast({ title: t('common.error'), variant: 'destructive' })
    } finally {
      setLoading(false)
    }
  }, [toast, t])

  useEffect(() => { fetch() }, [fetch])

  return (
    <div className="space-y-4 p-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" className="h-8 w-8"
            onClick={() => router.push(`/${locale}/dashboard/supervisor/inspections`)}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-lg font-bold flex items-center gap-2">
              <Users className="h-5 w-5" />
              {t('analytics.agentPerformance')}
            </h1>
            <p className="text-sm text-muted-foreground">{t('analytics.agentPerformanceDesc')}</p>
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={fetch} disabled={loading}>
          <RefreshCw className={`h-4 w-4 mr-1 ${loading ? 'animate-spin' : ''}`} />
          {t('common.refresh')}
        </Button>
      </div>

      {/* Loading */}
      {loading && !data && (
        <div className="space-y-3">
          {[1, 2, 3, 4].map(i => <Skeleton key={i} className="h-16 w-full" />)}
        </div>
      )}

      {/* Data */}
      {data && (
        <>
          {/* KPIs */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Card className="p-3">
              <div className="text-xs text-muted-foreground">{t('analytics.totalAgents')}</div>
              <p className="text-xl font-bold">{data.items?.length ?? 0}</p>
            </Card>
            <Card className="p-3">
              <div className="text-xs text-muted-foreground flex items-center gap-1">
                <CheckCircle2 className="h-3 w-3" />{t('analytics.totalCompleted')}
              </div>
              <p className="text-xl font-bold text-green-700">
                {data.items?.reduce((s: number, a: AgentPerformanceItem) => s + (a.conforme ?? 0), 0) ?? 0}
              </p>
            </Card>
            <Card className="p-3">
              <div className="text-xs text-muted-foreground flex items-center gap-1">
                <TrendingUp className="h-3 w-3" />{t('analytics.avgRate')}
              </div>
              <p className="text-xl font-bold">
                {data.items?.length
                  ? Math.round(data.items.reduce((s: number, a: AgentPerformanceItem) => s + (a.conformity_rate ?? 0), 0) / data.items.length)
                  : 0}%
              </p>
            </Card>
            <Card className="p-3">
              <div className="text-xs text-muted-foreground flex items-center gap-1">
                <Clock className="h-3 w-3" />{t('analytics.avgTime')}
              </div>
              <p className="text-xl font-bold">
                {data.items?.length
                  ? Math.round(data.items.reduce((s: number, a: AgentPerformanceItem) => s + (a.avg_duration_minutes ?? 0), 0) / data.items.length)
                  : 0} min
              </p>
            </Card>
          </div>

          {/* Table */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">{t('analytics.agentList')}</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="text-xs">{t('analytics.agent')}</TableHead>
                    <TableHead className="text-xs text-center">{t('analytics.assigned')}</TableHead>
                    <TableHead className="text-xs text-center">{t('analytics.completed')}</TableHead>
                    <TableHead className="text-xs text-center">{t('analytics.rate')}</TableHead>
                    <TableHead className="text-xs text-center">{t('analytics.avgTime')}</TableHead>
                    <TableHead className="text-xs">{t('analytics.status')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(!data.items || data.items.length === 0) ? (
                    <TableRow>
                      <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                        {t('analytics.noAgents')}
                      </TableCell>
                    </TableRow>
                  ) : data.items.map((agent) => (
                    <TableRow
                      key={agent.agent_id}
                      className="cursor-pointer hover:bg-muted/50"
                      onClick={() => router.push(`/${locale}/dashboard/supervisor/inspections/agents/${agent.agent_id}`)}
                    >
                      <TableCell className="text-sm font-medium">{agent.agent_name}</TableCell>
                      <TableCell className="text-sm text-center">{agent.inspections_total ?? 0}</TableCell>
                      <TableCell className="text-sm text-center font-mono">{agent.conforme ?? 0}</TableCell>
                      <TableCell className="text-sm text-center">
                        <Badge variant="outline" className={
                          (agent.conformity_rate ?? 0) >= 80 ? 'bg-green-50 text-green-700' :
                          (agent.conformity_rate ?? 0) >= 50 ? 'bg-yellow-50 text-yellow-700' :
                          'bg-red-50 text-red-700'
                        }>
                          {Math.round(agent.conformity_rate ?? 0)}%
                        </Badge>
                      </TableCell>
                      <TableCell className="text-sm text-center font-mono">
                        {Math.round(agent.avg_duration_minutes ?? 0)} min
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" className="text-xs">
                          {agent.days_active > 0 ? 'active' : 'inactive'}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  )
}
