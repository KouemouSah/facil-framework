'use client'

/**
 * OMS Supervisor Dashboard — Entity-scoped overview
 *
 * For supervisors CAMARA, AYUNTAMIENTO, MIN_*. Uses OMS endpoints
 * that are automatically scoped by the supervisor's entity + city.
 *
 * Layout:
 *   Row 1: 6 StatCells (licences + queue + team)
 *   Row 2: Quick action buttons
 *   Row 3: Compliance summary (fee_type breakdown) + Team performance
 *   Row 4: Queue stats detail
 *
 * NO treasury admin endpoints — all data from OMS scoped APIs.
 */

import { useMemo } from 'react'
import { useRouter } from 'next/navigation'
import { useLocale, useTranslations } from 'next-intl'
import {
  Chart as ChartJS, ArcElement, Tooltip, Legend,
} from 'chart.js'
import { Doughnut } from 'react-chartjs-2'
import { useQuery } from '@tanstack/react-query'
import Link from 'next/link'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Progress } from '@/components/ui/progress'
import {
  Users, FileCheck, AlertTriangle, TrendingUp,
  ClipboardList, RefreshCw, ChevronRight,
  DollarSign, CheckCircle2, Clock, MapPin, Shield,
} from 'lucide-react'
import apiClient from '@/core/api/client'
import { omsQueueApi, omsLicensesApi } from '@/modules/oms/services/api'
import type {
  LicenseStats, AgentQueueStats, TeamPerformanceResponse,
  ComplianceSummaryResponse, ComplianceSummaryGroup,
} from '@/modules/oms/types'
import { fmtXAF } from '@/modules/oms/utils/formatters'

ChartJS.register(ArcElement, Tooltip, Legend)

// =============================================================================
// HELPERS
// =============================================================================

function StatCell({ icon, value, label, isLoading, highlight }: {
  icon: React.ReactNode; value: string | number; label: string
  isLoading?: boolean; highlight?: boolean
}) {
  if (isLoading) return <Skeleton className="h-16" />
  return (
    <Card className={`p-3 ${highlight ? 'border-orange-300 bg-orange-50/50' : ''}`}>
      <div className="flex items-center gap-2">
        {icon}
        <div>
          <p className="text-lg font-bold leading-tight">{value}</p>
          <p className="text-[10px] text-muted-foreground leading-tight">{label}</p>
        </div>
      </div>
    </Card>
  )
}

// =============================================================================
// PAGE
// =============================================================================

export default function OmsSupervisorDashboard() {
  const locale = useLocale()
  const router = useRouter()
  const t = useTranslations('oms')
  const tSup = useTranslations('supervisor')
  const currentYear = new Date().getFullYear()

  // Agent profile for entity info
  const { data: profile } = useQuery({
    queryKey: ['agent-profile-entity'],
    queryFn: () => apiClient.get('/agents/profiles/me').then(r => r.data),
    staleTime: 300_000,
  })

  // License stats (scoped by entity via AgentScope)
  const { data: licenseStats, isLoading: licLoading } = useQuery<LicenseStats>({
    queryKey: ['oms-sup-license-stats', currentYear],
    queryFn: () => omsLicensesApi.getStats(currentYear),
    staleTime: 60_000,
  })

  // Queue stats (scoped by OmsAgentService)
  const { data: queueStats, isLoading: queueLoading } = useQuery<AgentQueueStats>({
    queryKey: ['oms-sup-queue-stats'],
    queryFn: () => omsQueueApi.getStats(),
    staleTime: 60_000,
  })

  // Team performance (scoped by entity + fee_type + city)
  const { data: teamPerf, isLoading: teamLoading } = useQuery<TeamPerformanceResponse>({
    queryKey: ['oms-sup-team-perf'],
    queryFn: () => omsQueueApi.getTeamPerformance({ period_days: 30, fiscal_year: currentYear }),
    staleTime: 60_000,
  })

  // Compliance summary (scoped by entity)
  const { data: compliance, isLoading: compLoading } = useQuery<ComplianceSummaryResponse>({
    queryKey: ['oms-sup-compliance', currentYear],
    queryFn: () => omsLicensesApi.getComplianceSummary(currentYear),
    staleTime: 120_000,
  })

  const isLoading = licLoading || queueLoading
  const entityName = profile?.entity_name || profile?.entity_code || ''
  const locationName = profile?.location_name || ''

  const recoveryPct = licenseStats?.recovery_rate ?? 0

  // Donut chart data from compliance summary
  const donutData = useMemo(() => {
    if (!compliance?.items?.length) return null
    const paid = compliance.items.reduce((s, g) => s + g.paid, 0)
    const pending = compliance.items.reduce((s, g) => s + g.pending, 0)
    const overdue = compliance.items.reduce((s, g) => s + g.overdue, 0)
    if (paid + pending + overdue === 0) return null
    return {
      labels: [t('licenses.paidObligations'), t('licenses.pendingObligations'), t('licenses.overdueObligations')],
      datasets: [{
        data: [paid, pending, overdue],
        backgroundColor: ['#22c55e', '#eab308', '#ef4444'],
        borderWidth: 0,
      }],
    }
  }, [compliance, t])

  return (
    <div className="space-y-4 p-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold">{tSup('dashboard.title')}</h1>
          <p className="text-sm text-muted-foreground">{tSup('dashboard.welcome', { name: entityName })}</p>
        </div>
        <div className="flex items-center gap-2">
          {locationName && (
            <Badge variant="outline" className="flex items-center gap-1.5 px-3 py-1.5 text-sm">
              <MapPin className="h-3.5 w-3.5" />
              {locationName}
            </Badge>
          )}
          <Button variant="outline" size="sm" onClick={() => router.refresh()}>
            <RefreshCw className="h-3.5 w-3.5 mr-1" />
          </Button>
        </div>
      </div>

      {/* Row 1: Stats */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2">
        <StatCell
          icon={<FileCheck className="h-4 w-4 text-blue-500" />}
          value={licenseStats?.total_licenses ?? 0}
          label={t('licenses.totalLicenses')}
          isLoading={isLoading}
        />
        <StatCell
          icon={<AlertTriangle className="h-4 w-4 text-red-500" />}
          value={licenseStats?.overdue_licenses ?? 0}
          label={t('licenses.overdue')}
          isLoading={isLoading}
          highlight={(licenseStats?.overdue_licenses ?? 0) > 0}
        />
        <StatCell
          icon={<DollarSign className="h-4 w-4 text-green-600" />}
          value={fmtXAF(licenseStats?.total_paid ?? 0, locale)}
          label={t('licenses.paid')}
          isLoading={isLoading}
        />
        <StatCell
          icon={<Clock className="h-4 w-4 text-orange-500" />}
          value={queueStats?.pending_count ?? 0}
          label={t('queue.pending')}
          isLoading={queueLoading}
          highlight={(queueStats?.pending_count ?? 0) > 0}
        />
        <StatCell
          icon={<CheckCircle2 className="h-4 w-4 text-green-500" />}
          value={queueStats?.completed_today ?? 0}
          label={t('queue.completedToday')}
          isLoading={queueLoading}
        />
        <StatCell
          icon={<Users className="h-4 w-4 text-purple-500" />}
          value={teamPerf?.team_totals?.total_agents ?? 0}
          label={tSup('nav.team')}
          isLoading={teamLoading}
        />
      </div>

      {/* Recovery rate */}
      <Card className="p-3">
        <div className="flex items-center justify-between mb-1">
          <span className="text-sm font-medium flex items-center gap-1.5">
            <TrendingUp className="h-4 w-4 text-primary" />
            {t('licenses.recovery')}
          </span>
          <span className="text-sm font-bold">{recoveryPct}%</span>
        </div>
        <Progress value={recoveryPct} className="h-2" />
        <div className="flex justify-between text-xs text-muted-foreground mt-1">
          <span>{fmtXAF(licenseStats?.total_paid ?? 0, locale)} {t('licenses.paid')}</span>
          <span>{fmtXAF(licenseStats?.total_debt ?? 0, locale)} {t('licenses.debt')}</span>
        </div>
      </Card>

      {/* Row 2: Quick Actions */}
      <div className="flex flex-wrap gap-2">
        <Link href={`/${locale}/dashboard/supervisor/oms/team`}>
          <Button variant="outline" size="sm" className="gap-1.5 text-xs">
            <Users className="h-3.5 w-3.5" /> {tSup('nav.team')} <ChevronRight className="h-3 w-3" />
          </Button>
        </Link>
        <Link href={`/${locale}/dashboard/agent/oms/licenses`}>
          <Button variant="outline" size="sm" className="gap-1.5 text-xs">
            <FileCheck className="h-3.5 w-3.5" /> {t('nav.licenses')} <ChevronRight className="h-3 w-3" />
          </Button>
        </Link>
        <Link href={`/${locale}/dashboard/agent/oms/compliance`}>
          <Button variant="outline" size="sm" className="gap-1.5 text-xs">
            <Shield className="h-3.5 w-3.5" /> {t('nav.compliance')} <ChevronRight className="h-3 w-3" />
          </Button>
        </Link>
        <Link href={`/${locale}/dashboard/supervisor/inspections`}>
          <Button variant="outline" size="sm" className="gap-1.5 text-xs">
            <ClipboardList className="h-3.5 w-3.5" /> {t('nav.inspections') || 'Inspections'} <ChevronRight className="h-3 w-3" />
          </Button>
        </Link>
        <Link href={`/${locale}/dashboard/supervisor/escalations/pending`}>
          <Button variant="outline" size="sm" className="gap-1.5 text-xs">
            <AlertTriangle className="h-3.5 w-3.5" /> {tSup('nav.escalations') || 'Escalations'} <ChevronRight className="h-3 w-3" />
          </Button>
        </Link>
      </div>

      {/* Row 3: Donut + Compliance + Team */}
      <div className="grid gap-4 lg:grid-cols-3">
        {/* Donut Chart */}
        {donutData && (
          <Card>
            <CardHeader className="pb-1">
              <CardTitle className="text-sm">{t('licenses.distribution') || 'Distribution'}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="h-[200px] flex items-center justify-center">
                <Doughnut data={donutData} options={{
                  cutout: '55%', responsive: true, maintainAspectRatio: false,
                  plugins: { legend: { position: 'bottom', labels: { boxWidth: 10, font: { size: 11 } } } },
                }} />
              </div>
              <div className="text-center mt-2">
                <p className="text-2xl font-bold">{recoveryPct}%</p>
                <p className="text-xs text-muted-foreground">{t('licenses.recovery')}</p>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Compliance Summary */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <Shield className="h-4 w-4" />
              {t('nav.compliance')} {currentYear}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {compLoading ? (
              <div className="space-y-2">{[1, 2, 3].map(i => <Skeleton key={i} className="h-12" />)}</div>
            ) : !compliance?.items?.length ? (
              <p className="text-sm text-muted-foreground text-center py-4">{t('licenses.noData') || 'Aucune donnee'}</p>
            ) : (
              <div className="space-y-3">
                {compliance.items.map((group: ComplianceSummaryGroup) => (
                  <div key={group.fee_type} className="border rounded-lg p-3">
                    <div className="flex items-center justify-between mb-1">
                      <Badge variant="outline" className="text-xs capitalize">{group.fee_type}</Badge>
                      <span className="text-xs text-muted-foreground">{group.total_obligations} obligations</span>
                    </div>
                    <div className="flex items-center gap-3 text-xs">
                      <span className="text-green-600">{group.paid} {t('licenses.paidObligations')}</span>
                      <span className="text-yellow-600">{group.pending} {t('licenses.pendingObligations')}</span>
                      {group.overdue > 0 && <span className="text-red-600">{group.overdue} {t('licenses.overdueObligations')}</span>}
                    </div>
                    <Progress value={group.recovery_pct} className="h-1.5 mt-2" />
                    <p className="text-[10px] text-muted-foreground mt-0.5">{group.recovery_pct}% {t('licenses.recovery')}</p>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Team Performance */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center justify-between">
              <span className="flex items-center gap-2"><Users className="h-4 w-4" /> {tSup('nav.team')}</span>
              <Link href={`/${locale}/dashboard/supervisor/oms/team`}>
                <Button variant="ghost" size="sm" className="text-xs h-7">{tSup('nav.viewAll') || 'Ver todo' || 'Voir tout'} <ChevronRight className="h-3 w-3" /></Button>
              </Link>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {teamLoading ? (
              <div className="space-y-2">{[1, 2, 3].map(i => <Skeleton key={i} className="h-10" />)}</div>
            ) : !teamPerf?.agents?.length ? (
              <p className="text-sm text-muted-foreground text-center py-4">{tSup('nav.noAgents') || 'Aucun agent' || 'Aucun agent'}</p>
            ) : (
              <div className="space-y-2">
                {teamPerf.agents.slice(0, 5).map(agent => (
                  <div key={agent.agent_profile_id} className="flex items-center justify-between p-2 rounded border text-xs">
                    <div className="flex-1 min-w-0">
                      <p className="font-medium truncate">{agent.agent_name}</p>
                      <div className="flex gap-2 text-muted-foreground">
                        <span>{agent.obligations_completed ?? 0} {t('licenses.paidObligations')}</span>
                        <span>{agent.obligations_pending ?? 0} {t('licenses.pendingObligations')}</span>
                      </div>
                    </div>
                    <Badge variant="outline" className={
                      (agent.completion_rate ?? 0) >= 80 ? 'bg-green-50 text-green-700' :
                      (agent.completion_rate ?? 0) >= 50 ? 'bg-yellow-50 text-yellow-700' :
                      'bg-red-50 text-red-700'
                    }>
                      {Math.round(agent.completion_rate ?? 0)}%
                    </Badge>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Row 4: Queue details */}
      {queueStats && (
        <Card className="p-3">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-center">
            <div>
              <p className="text-2xl font-bold">{queueStats.pending_count}</p>
              <p className="text-xs text-muted-foreground">{t('queue.pending')}</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-green-700">{queueStats.completed_today}</p>
              <p className="text-xs text-muted-foreground">{t('queue.completedToday')}</p>
            </div>
            <div>
              <p className="text-2xl font-bold">{fmtXAF(queueStats.total_amount_pending, locale)}</p>
              <p className="text-xs text-muted-foreground">{t('queue.pendingAmount')}</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-green-700">{fmtXAF(queueStats.total_amount_completed_today, locale)}</p>
              <p className="text-xs text-muted-foreground">{t('queue.processedToday')}</p>
            </div>
          </div>
        </Card>
      )}
    </div>
  )
}
