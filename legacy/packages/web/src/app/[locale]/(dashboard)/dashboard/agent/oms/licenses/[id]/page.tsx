'use client'

/**
 * OMS License Detail — Obligations, donut, timeline, actions
 *
 * Shows a single commercial license with all its obligations,
 * compliance events, donut paid/pending/overdue, and actions.
 */

import { useCallback, useEffect, useMemo, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { useLocale, useTranslations } from 'next-intl'
import { exportToExcel } from '@/core/utils/export'
import {
  ArrowLeft, Building2, FileCheck,
  CheckCircle2, Download, RefreshCw,
  XCircle, MapPin, Calendar, History, RotateCcw, Search,
  ChevronLeft, ChevronRight,
} from 'lucide-react'
import {
  Chart as ChartJS, ArcElement, Tooltip, Legend,
} from 'chart.js'
import { Doughnut } from 'react-chartjs-2'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table'
import { useToast } from '@/hooks/use-toast'
import apiClient from '@/core/api/client'
import { omsLicensesApi, omsQueueApi } from '@/modules/oms/services/api'
import type { LicenseResponse, ObligationResponse, ComplianceEvent } from '@/modules/oms/types'
import { OBLIGATION_STATUS_CONFIG as OB_STATUS, LICENSE_STATUS_CONFIG as LIC_STATUS, fmtXAF } from '@/modules/oms/utils/formatters'
import { PrintHeader, PrintFooter } from '@/components/shared/PrintHeader'

ChartJS.register(ArcElement, Tooltip, Legend)

export default function LicenseDetailPage() {
  const params = useParams()
  const router = useRouter()
  const locale = useLocale()
  const t = useTranslations('oms.licenses')
  const { toast } = useToast()
  const licenseId = params.id as string

  const OB_PAGE_SIZE = 50

  const [license, setLicense] = useState<LicenseResponse | null>(null)
  const [obligations, setObligations] = useState<ObligationResponse[]>([])
  const [obTotal, setObTotal] = useState(0)
  const [obPage, setObPage] = useState(1)
  const [obligationKpis, setObligationKpis] = useState<{
    total_amount: number; paid_amount: number; penalty_amount: number
    paid_count: number; pending_count: number; overdue_count: number
  }>({ total_amount: 0, paid_amount: 0, penalty_amount: 0, paid_count: 0, pending_count: 0, overdue_count: 0 })
  const [events, setEvents] = useState<ComplianceEvent[]>([])
  const [loading, setLoading] = useState(true)
  const [showTimeline, setShowTimeline] = useState(false)

  // Fetch obligations page (independent of license/events)
  const fetchObligations = useCallback(async (pg: number) => {
    try {
      const obs = await omsLicensesApi.getObligations(licenseId, { page: pg, page_size: OB_PAGE_SIZE })
      setObligations(obs.items)
      setObTotal(obs.total)
      setObligationKpis({
        total_amount: Number(obs.total_amount) || 0,
        paid_amount: Number(obs.paid_amount) || 0,
        penalty_amount: Number(obs.penalty_amount) || 0,
        paid_count: obs.paid_count ?? 0,
        pending_count: obs.pending_count ?? 0,
        overdue_count: obs.overdue_count ?? 0,
      })
    } catch {
      // Silent — main fetchAll handles error display
    }
  }, [licenseId])

  const fetchAll = useCallback(async () => {
    setLoading(true)
    try {
      const [lic, obs, evts] = await Promise.all([
        omsLicensesApi.get(licenseId),
        omsLicensesApi.getObligations(licenseId, { page: obPage, page_size: OB_PAGE_SIZE }),
        omsLicensesApi.getEvents(licenseId).catch(() => ({ items: [] })),
      ])
      setLicense(lic)
      setObligations(obs.items)
      setObTotal(obs.total)
      setObligationKpis({
        total_amount: Number(obs.total_amount) || 0,
        paid_amount: Number(obs.paid_amount) || 0,
        penalty_amount: Number(obs.penalty_amount) || 0,
        paid_count: obs.paid_count ?? 0,
        pending_count: obs.pending_count ?? 0,
        overdue_count: obs.overdue_count ?? 0,
      })
      setEvents(evts.items ?? [])
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status
      toast({
        title: status === 403 ? t('accessDenied') : t('loadError'),
        variant: 'destructive',
      })
    } finally {
      setLoading(false)
    }
  }, [licenseId, obPage, toast, t])

  useEffect(() => { fetchAll() }, [fetchAll])

  // Page change — only refetch obligations (not license/events)
  const handleObPageChange = useCallback((pg: number) => {
    setObPage(pg)
    fetchObligations(pg)
  }, [fetchObligations])

  const obTotalPages = Math.ceil(obTotal / OB_PAGE_SIZE)

  // KPIs from backend — aggregated from ALL scoped obligations (no page_size limit)
  const totalAmount = obligationKpis.total_amount
  const paidAmount = obligationKpis.paid_amount
  const balance = totalAmount - paidAmount
  const recoveryPct = totalAmount > 0
    ? Math.round((paidAmount / totalAmount) * 100) : 0

  const paidCount = obligationKpis.paid_count
  const pendingCount = obligationKpis.pending_count
  const overdueCount = obligationKpis.overdue_count
  const totalPenalties = obligationKpis.penalty_amount

  // Donut
  const donutData = useMemo(() => {
    if (!obligations.length) return null
    return {
      labels: [t('paidObligations'), t('pendingObligations'), t('overdueObligations')],
      datasets: [{
        data: [paidCount, pendingCount, overdueCount],
        backgroundColor: ['#22c55e', '#eab308', '#ef4444'],
        borderWidth: 0,
      }],
    }
  }, [paidCount, pendingCount, overdueCount, obligations.length])

  // Actions
  const handleProcess = async (obId: string) => {
    try {
      await omsQueueApi.processObligation(obId)
      toast({ title: t('processed') })
      fetchAll()
    } catch {
      toast({ title: t('error'), variant: 'destructive' })
    }
  }

  const handleReject = async (obId: string) => {
    const reason = window.prompt(t('rejectReason'))
    if (!reason || reason.length < 5) return
    try {
      await omsQueueApi.rejectObligation(obId, { reason })
      toast({ title: t('rejected') })
      fetchAll()
    } catch {
      toast({ title: t('error'), variant: 'destructive' })
    }
  }

  const handleDownloadPDF = async () => {
    try {
      const blob = await omsLicensesApi.downloadPDF(licenseId)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `licencia_${licenseId.slice(0, 8)}.pdf`
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      toast({ title: t('downloadError'), variant: 'destructive' })
    }
  }

  const handleRenew = async () => {
    const nextYear = (license?.fiscal_year ?? new Date().getFullYear()) + 1
    if (!window.confirm(`${t('renewConfirm')} ${nextYear}?`)) return
    try {
      const newLicense = await omsLicensesApi.renew(licenseId, { fiscal_year: nextYear })
      toast({ title: `${t('renewed')} ${nextYear}` })
      router.push(`/${locale}/dashboard/agent/oms/licenses/${newLicense.id}`)
    } catch {
      toast({ title: t('renewError'), variant: 'destructive' })
    }
  }

  const handleCheckPreviousYear = async () => {
    try {
      const res = await apiClient.post(`/licenses/${licenseId}/check-previous-year`).then(r => r.data)
      toast({ title: `${t('checkN1')}: ${res.checked} ${t('checkN1Result')}` })
      fetchAll()
    } catch {
      toast({ title: t('checkN1Error'), variant: 'destructive' })
    }
  }

  const licStatus = license ? (LIC_STATUS[license.status] || LIC_STATUS.open) : LIC_STATUS.open

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (!license) {
    return (
      <div className="p-6 text-center text-muted-foreground">
        <FileCheck className="h-10 w-10 mx-auto mb-3 opacity-30" />
        <p>{t('notFound')}</p>
        <Button variant="outline" size="sm" className="mt-3" onClick={() => router.back()}>
          <ArrowLeft className="h-4 w-4 mr-1" /> {t('back')}
        </Button>
      </div>
    )
  }

  return (
    <>
      {/* Print layout */}
      <div className="hidden print:block p-4 max-w-2xl mx-auto">
        <PrintHeader title="Licencia Comercial" subtitle="Detalle"
          meta={[
            { label: 'Empresa', value: license.company_name || '—' },
            ...(license.company_nif ? [{ label: 'NIF', value: license.company_nif }] : []),
            { label: 'Año', value: String(license.fiscal_year) },
          ]} />
        <div className="grid grid-cols-4 gap-2 text-[9pt] my-3 bg-gray-50 p-2 rounded">
          <div><span className="font-medium">{t('totalAmount')}:</span><br/>{fmtXAF(totalAmount, locale)}</div>
          <div><span className="font-medium">{t('paidAmount')}:</span><br/>{fmtXAF(paidAmount, locale)}</div>
          <div><span className="font-medium">{t('balance')}:</span><br/>{fmtXAF(balance, locale)}</div>
          <div><span className="font-medium">{t('recovery')}:</span><br/>{recoveryPct}%</div>
        </div>
        <table className="w-full text-[8pt] border-collapse">
          <thead><tr className="border-b">
            <th className="text-left p-1">Tipo</th><th className="text-left p-1">Ministerio</th>
            <th className="text-right p-1">Monto</th>
            {totalPenalties > 0 && <th className="text-right p-1">Penalidad</th>}
            <th className="text-left p-1">Vence</th><th className="text-left p-1">Estado</th>
          </tr></thead>
          <tbody>
            {obligations.map(ob => (
              <tr key={ob.id} className="border-b">
                <td className="p-1">{ob.fee_type}</td>
                <td className="p-1 text-[7pt]">{ob.ministry_name || '—'}</td>
                <td className="text-right p-1 font-mono">{fmtXAF(ob.amount, locale)}</td>
                {totalPenalties > 0 && <td className="text-right p-1 font-mono">{ob.penalty_amount > 0 ? fmtXAF(ob.penalty_amount, locale) : '—'}</td>}
                <td className="p-1">{ob.due_date || '—'}</td>
                <td className="p-1">{OB_STATUS[ob.status]?.label || ob.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <PrintFooter />
      </div>

      {/* Screen content */}
      <div className="space-y-4 p-4 print:hidden">
        {/* Header */}
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => router.push(`/${locale}/dashboard/agent/oms/licenses`)}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div className="flex-1 min-w-0">
            <h1 className="text-lg font-bold flex items-center gap-2 flex-wrap">
              <Building2 className="h-5 w-5 shrink-0" />
              <span className="truncate">{license.company_name || 'Licencia'}</span>
              <Badge className={`text-xs ${licStatus.color}`}>{licStatus.label}</Badge>
            </h1>
            <div className="flex items-center gap-3 text-xs text-muted-foreground mt-0.5">
              {license.company_nif && <span className="font-mono">NIF: {license.company_nif}</span>}
              {license.company_registration_number && <span className="font-mono">N°: {license.company_registration_number}</span>}
              {license.zone_code && <span className="flex items-center gap-1"><MapPin className="h-3 w-3" />{license.zone_code}</span>}
              <span className="flex items-center gap-1"><Calendar className="h-3 w-3" />{t('yearLabel')} {license.fiscal_year}</span>
            </div>
          </div>
          <div className="flex gap-1 shrink-0 flex-wrap">
            <Button variant="outline" size="sm" className="h-8 gap-1 text-xs" onClick={handleRenew}>
              <RotateCcw className="h-3.5 w-3.5" /> {t('renew')}
            </Button>
            <Button variant="outline" size="sm" className="h-8 gap-1 text-xs" onClick={handleCheckPreviousYear}>
              <Search className="h-3.5 w-3.5" /> {t('checkN1')}
            </Button>
            <Button variant="outline" size="sm" className="h-8 gap-1 text-xs" onClick={handleDownloadPDF}>
              <Download className="h-3.5 w-3.5" /> PDF
            </Button>
            <Button variant="outline" size="sm" className="h-8 gap-1 text-xs" onClick={() => {
              if (!obligations.length) return
              exportToExcel(obligations.map(ob => ({
                Servicio: ob.service_name || ob.fee_type,
                Entidad: ob.ministry_name || ob.fee_type || '',
                Monto: ob.amount,
                Penalidad: ob.penalty_amount || 0,
                Vencimiento: ob.due_date || '',
                Estado: ob.status,
              })), { fileName: `licencia_${licenseId.slice(0, 8)}_obligaciones`, sheetName: 'Obligaciones' })
            }}>
              <FileCheck className="h-3.5 w-3.5" /> Excel
            </Button>
            <Button variant="outline" size="sm" className="h-8 gap-1 text-xs" onClick={() => setShowTimeline(!showTimeline)}>
              <History className="h-3.5 w-3.5" /> {showTimeline ? '—' : t('history')}
            </Button>
            <Button variant="outline" size="icon" className="h-8 w-8" onClick={fetchAll}>
              <RefreshCw className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>

        {/* KPIs */}
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
          <Card className="p-3">
            <div className="text-xs text-muted-foreground">{t('totalAmount')}</div>
            <p className="text-xl font-bold">{fmtXAF(totalAmount, locale)}</p>
          </Card>
          <Card className="p-3">
            <div className="text-xs text-muted-foreground">{t('paidAmount')}</div>
            <p className="text-xl font-bold text-green-700">{fmtXAF(paidAmount, locale)}</p>
          </Card>
          <Card className="p-3">
            <div className="text-xs text-muted-foreground">{t('balance')}</div>
            <p className={`text-xl font-bold ${balance > 0 ? 'text-red-700' : 'text-green-700'}`}>{fmtXAF(balance, locale)}</p>
          </Card>
          <Card className="p-3">
            <div className="text-xs text-muted-foreground">{t('recovery')}</div>
            <p className="text-xl font-bold">{recoveryPct}%</p>
            <Progress value={recoveryPct} className="h-1.5 mt-1" />
          </Card>
          {totalPenalties > 0 && (
            <Card className="p-3">
              <div className="text-xs text-muted-foreground">{t('penalties')}</div>
              <p className="text-xl font-bold text-amber-700">{fmtXAF(totalPenalties, locale)}</p>
            </Card>
          )}
        </div>

        {/* Donut + Obligations summary */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {donutData && (
            <Card>
              <CardHeader className="pb-1"><CardTitle className="text-sm">{t('distribution')}</CardTitle></CardHeader>
              <CardContent>
                <div className="h-[180px] flex items-center justify-center">
                  <Doughnut data={donutData} options={{
                    cutout: '55%', responsive: true, maintainAspectRatio: false,
                    plugins: { legend: { position: 'right', labels: { boxWidth: 10, font: { size: 11 } } } },
                  }} />
                </div>
              </CardContent>
            </Card>
          )}

          <Card className={donutData ? 'lg:col-span-2' : 'lg:col-span-3'}>
            <CardHeader className="pb-1">
              <CardTitle className="text-sm flex items-center justify-between">
                <span>{t('obligations')} ({obTotal})</span>
                <div className="flex gap-2 text-[10px] font-normal">
                  <span className="text-green-600">{paidCount} {t('paidObligations')}</span>
                  <span className="text-yellow-600">{pendingCount} {t('pendingObligations')}</span>
                  {overdueCount > 0 && <span className="text-red-600">{overdueCount} {t('overdueObligations')}</span>}
                </div>
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="text-xs">{t('obligationName', { defaultValue: 'Obligación' })}</TableHead>
                    <TableHead className="text-xs w-[110px] text-right">{t('amount', { defaultValue: 'Monto' })}</TableHead>
                    {totalPenalties > 0 && <TableHead className="text-xs w-[80px] text-right">{t('penalty', { defaultValue: 'Penalidad' })}</TableHead>}
                    <TableHead className="text-xs w-[90px]">{t('dueDate', { defaultValue: 'Vence' })}</TableHead>
                    <TableHead className="text-xs w-[95px]">{t('statusCol', { defaultValue: 'Estado' })}</TableHead>
                    <TableHead className="text-xs w-[80px]">{t('actionsCol', { defaultValue: 'Acciones' })}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {obligations.length === 0 ? (
                    <TableRow><TableCell colSpan={6} className="text-center py-6 text-muted-foreground text-sm">{t('noObligations', { defaultValue: 'Sin obligaciones' })}</TableCell></TableRow>
                  ) : obligations.map(ob => {
                    const cfg = OB_STATUS[ob.status] || OB_STATUS.pending
                    const Icon = cfg.icon
                    const canProcess = ob.status === 'processing' || ob.status === 'paid'
                    return (
                      <TableRow key={ob.id}>
                        <TableCell className="text-xs font-medium truncate max-w-[200px]">{ob.service_name || ob.fee_type}</TableCell>
                        <TableCell className="text-xs text-right font-mono">{fmtXAF(ob.amount, locale)}</TableCell>
                        {totalPenalties > 0 && (
                          <TableCell className="text-xs text-right font-mono text-amber-600">
                            {ob.penalty_amount > 0 ? fmtXAF(ob.penalty_amount, locale) : '—'}
                          </TableCell>
                        )}
                        <TableCell className="text-xs">{ob.due_date || '—'}</TableCell>
                        <TableCell>
                          <Badge className={`text-[10px] gap-1 ${cfg.color}`}>
                            <Icon className="h-3 w-3" />{cfg.label}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          {canProcess && (
                            <div className="flex gap-0.5">
                              <Button variant="ghost" size="icon" className="h-7 w-7" title={t('process')}
                                onClick={() => handleProcess(ob.id)}>
                                <CheckCircle2 className="h-3.5 w-3.5 text-green-600" />
                              </Button>
                              <Button variant="ghost" size="icon" className="h-7 w-7" title={t('reject')}
                                onClick={() => handleReject(ob.id)}>
                                <XCircle className="h-3.5 w-3.5 text-red-500" />
                              </Button>
                            </div>
                          )}
                          {ob.status === 'completed' && <CheckCircle2 className="h-4 w-4 text-green-500" />}
                        </TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
              {/* Obligation pagination */}
              {obTotalPages > 1 && (
                <div className="flex items-center justify-between px-3 py-2 border-t text-xs text-muted-foreground">
                  <span>{obTotal} {t('paginationObligations')} — {obPage}/{obTotalPages}</span>
                  <div className="flex gap-1">
                    <Button variant="outline" size="icon" className="h-7 w-7"
                      disabled={obPage <= 1} onClick={() => handleObPageChange(obPage - 1)}>
                      <ChevronLeft className="h-3.5 w-3.5" />
                    </Button>
                    <Button variant="outline" size="icon" className="h-7 w-7"
                      disabled={obPage >= obTotalPages} onClick={() => handleObPageChange(obPage + 1)}>
                      <ChevronRight className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Timeline événements */}
        {showTimeline && (
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm flex items-center gap-2">
                <History className="h-4 w-4" />
                {t('timeline')} ({events.length})
              </CardTitle>
            </CardHeader>
            <CardContent>
              {events.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-4">{t('noEvents')}</p>
              ) : (
                <div className="relative pl-6 space-y-3">
                  {/* Vertical line */}
                  <div className="absolute left-[9px] top-2 bottom-2 w-px bg-gray-200" />
                  {events.map((evt) => (
                    <div key={evt.id} className="relative">
                      {/* Dot */}
                      <div className={`absolute -left-6 top-1 h-[14px] w-[14px] rounded-full border-2 ${
                        evt.event_type.includes('PAID') || evt.event_type.includes('COMPLETED') ? 'border-green-500 bg-green-100' :
                        evt.event_type.includes('OVERDUE') || evt.event_type.includes('PENALTY') ? 'border-red-500 bg-red-100' :
                        evt.event_type.includes('CREATED') || evt.event_type.includes('ISSUED') ? 'border-blue-500 bg-blue-100' :
                        'border-gray-400 bg-gray-100'
                      }`} />
                      <div className="text-xs">
                        <div className="flex items-center gap-2">
                          <Badge variant="outline" className="text-[10px] font-mono">{evt.event_type}</Badge>
                          <span className="text-muted-foreground">
                            {new Date(evt.created_at).toLocaleDateString(locale, { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })}
                          </span>
                        </div>
                        {evt.event_data && Object.keys(evt.event_data).length > 0 && (
                          <div className="mt-0.5 text-[10px] text-muted-foreground">
                            {Object.entries(evt.event_data).slice(0, 3).map(([k, v]) => (
                              <span key={k} className="mr-2">{k}: <strong>{String(v)}</strong></span>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        )}
      </div>
    </>
  )
}
