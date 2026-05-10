'use client'

/**
 * OMS Compliance — Track overdue obligations by fee type
 *
 * Uses pre-aggregated backend endpoint (GET /licenses/compliance-summary)
 * instead of N+1 client-side fetching. 1 API call for all data.
 */

import { useCallback, useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useLocale, useTranslations } from 'next-intl'
import {
  ShieldCheck, AlertTriangle, CheckCircle2, RefreshCw,
  Building2, DollarSign, TrendingUp, ChevronDown, Eye,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { useToast } from '@/hooks/use-toast'
import { omsLicensesApi } from '@/modules/oms/services/api'
import type { ComplianceSummaryGroup } from '@/modules/oms/types'
import { fmtXAF } from '@/modules/oms/utils/formatters'

export default function OMSCompliancePage() {
  const router = useRouter()
  const locale = useLocale()
  const { toast } = useToast()
  const t = useTranslations('oms.compliance')
  const [groups, setGroups] = useState<ComplianceSummaryGroup[]>([])
  const [loading, setLoading] = useState(true)
  const [expandedFee, setExpandedFee] = useState<string | null>(null)
  const currentYear = new Date().getFullYear()

  const fetchData = useCallback(async () => {
    setLoading(true)
    try {
      // Single API call — pre-aggregated by fee_type on backend
      const res = await omsLicensesApi.getComplianceSummary(currentYear)
      setGroups(res.items)
    } catch {
      toast({ title: t('loadError'), variant: 'destructive' })
    } finally {
      setLoading(false)
    }
  }, [currentYear, toast, t])

  useEffect(() => { fetchData() }, [fetchData])

  const totalOverdue = groups.reduce((s, g) => s + g.overdue, 0)
  const totalOverdueAmount = groups.reduce((s, g) => s + g.overdue_amount, 0)
  const totalRecovery = (() => {
    const total = groups.reduce((s, g) => s + g.total_amount, 0)
    const paid = groups.reduce((s, g) => s + g.paid_amount, 0)
    return total > 0 ? Math.round((paid / total) * 100) : 0
  })()

  return (
    <div className="space-y-4 p-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold flex items-center gap-2">
            <ShieldCheck className="h-5 w-5" />
            {t('title')}
          </h1>
          <p className="text-sm text-muted-foreground">
            {t('subtitle')} — {currentYear}
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={fetchData} disabled={loading}>
          <RefreshCw className={`h-3.5 w-3.5 mr-1 ${loading ? 'animate-spin' : ''}`} />
        </Button>
      </div>

      {/* Summary KPIs */}
      <div className="grid grid-cols-3 gap-3">
        <Card className="p-3">
          <div className="flex items-center gap-2">
            <AlertTriangle className={`h-5 w-5 ${totalOverdue > 0 ? 'text-red-500' : 'text-gray-300'}`} />
            <div>
              <p className="text-xs text-muted-foreground">{t('overdueObligations')}</p>
              <p className="text-2xl font-bold text-red-700">{totalOverdue}</p>
              <p className="text-[10px] text-muted-foreground">{fmtXAF(totalOverdueAmount, locale)}</p>
            </div>
          </div>
        </Card>
        <Card className="p-3">
          <div className="flex items-center gap-2">
            <TrendingUp className="h-5 w-5 text-blue-500" />
            <div>
              <p className="text-xs text-muted-foreground">{t('globalRecovery')}</p>
              <p className="text-2xl font-bold">{totalRecovery}%</p>
              <Progress value={totalRecovery} className="h-1.5 mt-1" />
            </div>
          </div>
        </Card>
        <Card className="p-3">
          <div className="flex items-center gap-2">
            <DollarSign className="h-5 w-5 text-green-500" />
            <div>
              <p className="text-xs text-muted-foreground">{t('feeTypes')}</p>
              <p className="text-2xl font-bold">{groups.length}</p>
            </div>
          </div>
        </Card>
      </div>

      {/* Fee type groups */}
      {loading ? (
        <div className="flex items-center justify-center py-12 text-muted-foreground">
          <RefreshCw className="h-5 w-5 animate-spin mr-2" /> {t('analyzing')}
        </div>
      ) : groups.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">
          <CheckCircle2 className="h-8 w-8 mx-auto mb-2 text-green-500" />
          <p>{t('noObligations')}</p>
        </div>
      ) : (
        <div className="space-y-3">
          {groups.map(g => {
            const isExpanded = expandedFee === g.fee_type
            return (
              <Card key={g.fee_type}>
                <CardHeader className="pb-2 cursor-pointer" onClick={() => setExpandedFee(isExpanded ? null : g.fee_type)}>
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-sm flex items-center gap-2">
                      <Badge variant="outline" className="font-mono text-xs uppercase">{g.fee_type}</Badge>
                      <span className="text-muted-foreground font-normal">{g.total_obligations} {t('obligations')}</span>
                    </CardTitle>
                    <div className="flex items-center gap-3">
                      <div className="flex items-center gap-1.5 text-xs">
                        <span className="text-green-600">{g.paid} {t('paidShort')}</span>
                        <span className="text-yellow-600">{g.pending} {t('pendingShort')}</span>
                        {g.overdue > 0 && <span className="text-red-600 font-semibold">{g.overdue} {t('overdueShort')}</span>}
                      </div>
                      <div className="flex items-center gap-2">
                        <span className={`text-xs font-bold ${g.recovery_pct >= 70 ? 'text-green-700' : g.recovery_pct >= 40 ? 'text-yellow-700' : 'text-red-700'}`}>
                          {g.recovery_pct}%
                        </span>
                        <div className="w-16 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                          <div className="h-full rounded-full" style={{
                            width: `${g.recovery_pct}%`,
                            backgroundColor: g.recovery_pct >= 70 ? '#22c55e' : g.recovery_pct >= 40 ? '#eab308' : '#ef4444',
                          }} />
                        </div>
                        <ChevronDown className={`h-4 w-4 text-muted-foreground transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
                      </div>
                    </div>
                  </div>
                </CardHeader>

                {isExpanded && (
                  <CardContent className="pt-0">
                    {/* Summary bar */}
                    <div className="flex items-center gap-4 text-xs text-muted-foreground mb-3 p-2 bg-muted/30 rounded">
                      <span>{t('total')}: <strong className="text-foreground">{fmtXAF(g.total_amount, locale)}</strong></span>
                      <span>{t('paid')}: <strong className="text-green-700">{fmtXAF(g.paid_amount, locale)}</strong></span>
                      {g.overdue_amount > 0 && <span>{t('overdueAmount')}: <strong className="text-red-700">{fmtXAF(g.overdue_amount, locale)}</strong></span>}
                    </div>

                    {/* Overdue companies */}
                    {g.overdue_companies.length > 0 ? (
                      <div className="space-y-2">
                        <p className="text-xs font-medium text-red-700">{t('overdueCompanies')}:</p>
                        {g.overdue_companies.map((c, i) => (
                          <div key={`${c.license_id}-${i}`} className="flex items-center justify-between p-2.5 bg-red-50/50 rounded border border-red-100">
                            <div className="flex items-center gap-2 min-w-0">
                              <Building2 className="h-3.5 w-3.5 text-red-400 shrink-0" />
                              <div className="min-w-0">
                                <p className="text-xs font-medium truncate">{c.company_name}</p>
                                <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
                                  {c.company_nif && <span className="font-mono">{c.company_nif}</span>}
                                  {c.zone && <Badge variant="outline" className="text-[9px] px-1 py-0">{c.zone}</Badge>}
                                </div>
                              </div>
                            </div>
                            <div className="flex items-center gap-2 shrink-0">
                              <div className="text-right">
                                <p className="text-xs font-bold text-red-700">{fmtXAF(c.amount, locale)}</p>
                                {c.penalty > 0 && <p className="text-[10px] text-amber-600">+{fmtXAF(c.penalty, locale)} pen.</p>}
                              </div>
                              <Button variant="ghost" size="icon" className="h-7 w-7" title={t('viewLicense')}
                                onClick={() => router.push(`/${locale}/dashboard/agent/oms/licenses/${c.license_id}`)}>
                                <Eye className="h-3.5 w-3.5" />
                              </Button>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="text-center py-4 text-sm text-muted-foreground">
                        <CheckCircle2 className="h-5 w-5 mx-auto mb-1 text-green-500" />
                        {t('noOverdue')}
                      </div>
                    )}
                  </CardContent>
                )}
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}
