'use client'

/**
 * Company Detail — License, Obligations, Payments, Inspections
 *
 * Full company management for citizen: real-time obligation tracking,
 * payment history with receipts, inspection alerts (mise en demeure, scellé).
 * Sortable tables, status filters, quick actions.
 *
 * @route /[locale]/dashboard/empresas/[companyId]
 */

import { useCallback, useMemo, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import { useTranslations } from 'next-intl'
import { useLocale } from 'next-intl'
import { exportToExcel } from '@/core/utils/export'
import Link from 'next/link'
import {
  ArrowLeft, Archive, Building2, MapPin, Calendar, DollarSign, Shield,
  CheckCircle2, Clock, AlertTriangle, XCircle, Download,
  CreditCard, Eye, ArrowUpDown, RefreshCw, FileWarning,
  Lock, Receipt, ChevronLeft, ChevronRight, FolderOpen, Award,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table'
import { bundleWorkflowApi } from '@/modules/bundle-workflow/services/bundle-workflow-api'
import { useCompanyMembership } from '@/modules/companies/hooks/useCompanyArchive'
import { ArchiveCompanyDialog } from '@/modules/companies/components/ArchiveCompanyDialog'
import { getAuthData } from '@/core/auth/storage'
// Types inferred from bundleWorkflowApi return values

// ── Formatters ──

function fmtXAF(n: number | null | undefined, locale = 'es-GQ'): string {
  if (n == null || isNaN(n)) return '0 XAF'
  return new Intl.NumberFormat(locale, { maximumFractionDigits: 0 }).format(n) + ' XAF'
}

function fmtDate(d: string | null | undefined, locale = 'es-GQ'): string {
  if (!d) return '—'
  try { return new Date(d).toLocaleDateString(locale, { day: '2-digit', month: 'short', year: 'numeric' }) }
  catch { return d }
}

// ── Status configs ──

const OBL_STATUS: Record<string, { color: string; icon: typeof Clock }> = {
  pending:         { color: 'bg-yellow-100 text-yellow-800', icon: Clock },
  selected:        { color: 'bg-blue-50 text-blue-700', icon: Clock },
  payment_pending: { color: 'bg-orange-100 text-orange-800', icon: DollarSign },
  paid:            { color: 'bg-emerald-100 text-emerald-800', icon: DollarSign },
  processing:      { color: 'bg-blue-100 text-blue-800', icon: RefreshCw },
  completed:       { color: 'bg-green-100 text-green-800', icon: CheckCircle2 },
  overdue:         { color: 'bg-red-100 text-red-800', icon: AlertTriangle },
  waived:          { color: 'bg-gray-100 text-gray-600', icon: XCircle },
  cancelled:       { color: 'bg-gray-100 text-gray-500', icon: XCircle },
}

const LIC_STATUS: Record<string, { color: string; icon: typeof Clock }> = {
  open:     { color: 'bg-blue-100 text-blue-800', icon: Clock },
  partial:  { color: 'bg-yellow-100 text-yellow-800', icon: DollarSign },
  complete: { color: 'bg-green-100 text-green-800', icon: CheckCircle2 },
  overdue:  { color: 'bg-red-100 text-red-800', icon: AlertTriangle },
}

const PAY_STATUS: Record<string, string> = {
  completed: 'bg-green-100 text-green-800',
  submitted: 'bg-blue-100 text-blue-800',
  pending_agent_review: 'bg-yellow-100 text-yellow-800',
  rejected: 'bg-red-100 text-red-800',
}

const METHOD_LABELS: Record<string, string> = {
  cash: 'Efectivo', check: 'Cheque', bank_transfer: 'Transferencia',
  mobile_money: 'Mobile Money', card: 'Tarjeta', bange_wallet: 'BANGE',
}

// ── Component ──

export default function CompanyDetailPage() {
  const params = useParams()
  const router = useRouter()
  const locale = useLocale()
  const t = useTranslations('empresas')
  const companyId = params.companyId as string
  const [year] = useState(new Date().getFullYear())

  // All companies (for quick navigation dropdown)
  const { data: companiesData } = useQuery({
    queryKey: ['my-companies', year],
    queryFn: () => bundleWorkflowApi.getMyCompanies(year),
    staleTime: 120_000,
  })
  const allCompanies = companiesData?.companies ?? []

  // Data
  const { data, isLoading } = useQuery({
    queryKey: ['company-detail', companyId, year],
    queryFn: () => bundleWorkflowApi.getMyCompanyDetail(companyId, year),
    staleTime: 30_000,
  })

  const [payPage, setPayPage] = useState(1)
  const { data: paymentsData } = useQuery({
    queryKey: ['company-payments', companyId, payPage],
    queryFn: () => bundleWorkflowApi.getMyCompanyPayments(companyId, payPage),
    staleTime: 60_000,
  })

  // Archive (soft-delete) — citizen surface, owner-only.
  // The hook reads members + derives canArchive (= isOwner). Backend permission
  // checks remain authoritative; UI gating just hides the CTA.
  const currentUserId = getAuthData()?.user?.id ?? null
  const { canArchive } = useCompanyMembership(companyId, currentUserId)
  const [archiveOpen, setArchiveOpen] = useState(false)

  // Obligation filters + sort
  const [oblFilter, setOblFilter] = useState('all')
  const [oblSort, setOblSort] = useState<'amount' | 'status' | 'dueDate'>('status')
  const [oblSortDir, setOblSortDir] = useState<'asc' | 'desc'>('asc')

  const toggleSort = useCallback((col: typeof oblSort) => {
    if (oblSort === col) setOblSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setOblSort(col); setOblSortDir('asc') }
  }, [oblSort])

  const filteredObligations = useMemo(() => {
    if (!data?.obligations) return []
    let items = [...data.obligations]
    if (oblFilter !== 'all') items = items.filter(o => o.status === oblFilter)

    const statusOrder: Record<string, number> = {
      overdue: 0, pending: 1, payment_pending: 2, paid: 3, processing: 4, completed: 5, waived: 6, cancelled: 7,
    }

    items.sort((a, b) => {
      if (oblSort === 'amount') return oblSortDir === 'asc' ? a.amount - b.amount : b.amount - a.amount
      if (oblSort === 'dueDate') return oblSortDir === 'asc'
        ? (a.dueDate || '').localeCompare(b.dueDate || '')
        : (b.dueDate || '').localeCompare(a.dueDate || '')
      // status
      return oblSortDir === 'asc'
        ? (statusOrder[a.status] ?? 9) - (statusOrder[b.status] ?? 9)
        : (statusOrder[b.status] ?? 9) - (statusOrder[a.status] ?? 9)
    })
    return items
  }, [data?.obligations, oblFilter, oblSort, oblSortDir])

  const payments = paymentsData?.payments ?? []
  const payTotalPages = paymentsData ? Math.ceil(paymentsData.total / paymentsData.pageSize) : 0

  if (isLoading || !data) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  const { company: c, license: lic, inspections } = data
  const licCfg = lic ? (LIC_STATUS[lic.status] || LIC_STATUS.open) : LIC_STATUS.open
  const LicIcon = licCfg.icon
  const recoveryPct = lic && lic.totalAmount > 0 ? Math.round((lic.amountPaid / lic.totalAmount) * 100) : 0
  const hasMiseEnDemeure = inspections.some(i => i.miseEnDemeure)
  const hasSeal = inspections.some(i => i.sealApplied)

  return (
    <div className="space-y-5 p-4 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" onClick={() => router.push(`/${locale}/dashboard/empresas`)}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        {/* Quick navigation between companies */}
        {allCompanies.length > 1 && (
          <Select value={companyId} onValueChange={(v: string) => router.push(`/${locale}/dashboard/empresas/${v}`)}>
            <SelectTrigger className="w-[200px] h-8 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {allCompanies.map(item => (
                <SelectItem key={item.company.id} value={item.company.id} className="text-xs">
                  {item.company.legalName}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
        <div className="flex-1 min-w-0">
          <h1 className="text-xl font-bold flex items-center gap-2 flex-wrap">
            <Building2 className="h-5 w-5 shrink-0" />
            <span className="truncate">{c.legalName}</span>
            {lic && <Badge className={`text-xs ${licCfg.color}`}><LicIcon className="h-3 w-3 mr-1" />{t(lic.status)}</Badge>}
          </h1>
          <div className="flex flex-wrap gap-3 text-xs text-muted-foreground mt-1">
            {c.registrationNumber && <span className="font-mono">{t('registration')}: {c.registrationNumber}</span>}
            {c.nif && <span className="font-mono">{t('nif')}: {c.nif}</span>}
            {c.zoneCode && <span className="flex items-center gap-1"><MapPin className="h-3 w-3" />{c.zoneCode}</span>}
            {c.cityName && <span>{c.cityName}</span>}
            {c.commerceType && <Badge variant="secondary" className="text-[10px] h-4">{c.commerceType}</Badge>}
          </div>
        </div>
        <div className="flex gap-1.5 shrink-0 flex-wrap">
          <Link href={`/${locale}/dashboard/documents?tab=generated`}>
            <Button variant="outline" size="sm" className="h-8 text-xs gap-1">
              <FolderOpen className="h-3.5 w-3.5" /> {t('viewDocuments', { defaultValue: 'Documentos' })}
            </Button>
          </Link>
          {lic && lic.certificateUrl && (
            <Button variant="outline" size="sm" className="h-8 text-xs gap-1 text-green-700 border-green-300" asChild>
              <a href={lic.certificateUrl} target="_blank" rel="noopener noreferrer">
                <Award className="h-3.5 w-3.5" /> {t('downloadCertificate')}
              </a>
            </Button>
          )}
          {lic && (
            <Button variant="outline" size="sm" className="h-8 text-xs gap-1"
              onClick={() => bundleWorkflowApi.downloadLicensePdf(companyId, locale)}
            >
              <Download className="h-3.5 w-3.5" /> {t('downloadLicense')}
            </Button>
          )}
          <Link href={`/${locale}/dashboard/bundle-payment?companyId=${c.id}`}>
            <Button size="sm" className="h-8 text-xs gap-1">
              <DollarSign className="h-3.5 w-3.5" /> {t('payTaxes')}
            </Button>
          </Link>
          {canArchive && (
            <Button
              variant="outline"
              size="sm"
              className="h-8 text-xs gap-1 text-muted-foreground hover:text-orange-700 hover:border-orange-300"
              onClick={() => setArchiveOpen(true)}
              aria-label="Archivar empresa"
            >
              <Archive className="h-3.5 w-3.5" /> Archivar
            </Button>
          )}
        </div>
      </div>

      <ArchiveCompanyDialog
        companyId={companyId}
        companyName={c.legalName}
        open={archiveOpen}
        onOpenChange={setArchiveOpen}
        blockersTabHref={`/${locale}/dashboard/empresas/${companyId}#obligations`}
        onSuccess={() => router.push(`/${locale}/dashboard/empresas`)}
      />


      {/* Alert banners */}
      {hasMiseEnDemeure && (
        <div className="flex items-center gap-2 p-3 bg-amber-50 border border-amber-200 rounded-lg text-sm">
          <FileWarning className="h-5 w-5 text-amber-600 shrink-0" />
          <span className="text-amber-800 font-medium">{t('miseEnDemeureActive')}</span>
        </div>
      )}
      {hasSeal && (
        <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-sm">
          <Lock className="h-5 w-5 text-red-600 shrink-0" />
          <span className="text-red-800 font-medium">{t('sealApplied')}</span>
        </div>
      )}

      {/* License KPIs */}
      {lic && (
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
          <Card className="p-3">
            <p className="text-xs text-muted-foreground">{t('totalAmount')}</p>
            <p className="text-xl font-bold">{fmtXAF(lic.totalAmount, locale)}</p>
          </Card>
          <Card className="p-3">
            <p className="text-xs text-muted-foreground">{t('amountPaid')}</p>
            <p className="text-xl font-bold text-green-700">{fmtXAF(lic.amountPaid, locale)}</p>
          </Card>
          <Card className="p-3">
            <p className="text-xs text-muted-foreground">{t('amountRemaining')}</p>
            <p className={`text-xl font-bold ${lic.amountRemaining > 0 ? 'text-red-700' : 'text-green-700'}`}>
              {fmtXAF(lic.amountRemaining, locale)}
            </p>
          </Card>
          <Card className="p-3">
            <p className="text-xs text-muted-foreground">{t('recovery')}</p>
            <p className="text-xl font-bold">{recoveryPct}%</p>
            <Progress value={recoveryPct} className="h-1.5 mt-1" />
          </Card>
          <Card className="p-3">
            <p className="text-xs text-muted-foreground">{t('expiryDate')}</p>
            <p className="text-lg font-bold flex items-center gap-1">
              <Calendar className="h-4 w-4" /> 31/12/{lic.fiscalYear}
            </p>
          </Card>
        </div>
      )}

      {/* Tabs: Obligations / Payments / Inspections */}
      <Tabs defaultValue="obligations">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="obligations" className="gap-1.5 text-xs">
            <Shield className="h-3.5 w-3.5" /> {t('obligations')} ({data.obligations.length})
          </TabsTrigger>
          <TabsTrigger value="payments" className="gap-1.5 text-xs">
            <CreditCard className="h-3.5 w-3.5" /> {t('paymentHistory')} ({paymentsData?.total ?? 0})
          </TabsTrigger>
          <TabsTrigger value="inspections" className="gap-1.5 text-xs">
            <Eye className="h-3.5 w-3.5" /> {t('inspections')} ({inspections.length})
            {(hasMiseEnDemeure || hasSeal) && <span className="ml-1 h-2 w-2 rounded-full bg-red-500" />}
          </TabsTrigger>
        </TabsList>

        {/* ═══ OBLIGATIONS TAB ═══ */}
        <TabsContent value="obligations" className="space-y-3 mt-4">
          <div className="flex gap-2">
            <Select value={oblFilter} onValueChange={(v: string) => setOblFilter(v)}>
              <SelectTrigger className="w-[140px] h-8 text-xs"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('allStatuses')}</SelectItem>
                <SelectItem value="pending">{t('filterPending')}</SelectItem>
                <SelectItem value="paid">{t('filterPaid')}</SelectItem>
                <SelectItem value="processing">{t('filterProcessing')}</SelectItem>
                <SelectItem value="completed">{t('filterCompleted')}</SelectItem>
                <SelectItem value="overdue">{t('filterOverdue')}</SelectItem>
              </SelectContent>
            </Select>
            <Button variant="outline" size="sm" className="h-8 text-xs gap-1 ml-auto" onClick={() => {
              if (!filteredObligations.length) return
              exportToExcel(filteredObligations.map(o => ({
                Servicio: o.serviceName || '',
                Tipo: o.feeType,
                Entidad: o.ministryName || o.feeType || '',
                Monto: o.amount,
                Penalidad: o.penaltyAmount,
                Vencimiento: o.dueDate || '',
                Estado: o.status,
              })), { fileName: `${c.legalName.replace(/\s+/g, '_')}_obligaciones`, sheetName: 'Obligaciones' })
            }}>
              <Download className="h-3 w-3" /> Excel
            </Button>
            <span className="text-xs text-muted-foreground self-center">
              {filteredObligations.length}/{data.obligations.length}
            </span>
          </div>

          <Card>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="text-xs">{t('serviceName')}</TableHead>
                    <TableHead className="text-xs">{t('feeType')}</TableHead>
                    <TableHead className="text-xs cursor-pointer select-none" onClick={() => toggleSort('amount')}>
                      <span className="flex items-center gap-1">{t('amount')} <ArrowUpDown className="h-3 w-3" /></span>
                    </TableHead>
                    <TableHead className="text-xs cursor-pointer select-none" onClick={() => toggleSort('dueDate')}>
                      <span className="flex items-center gap-1">{t('dueDate')} <ArrowUpDown className="h-3 w-3" /></span>
                    </TableHead>
                    <TableHead className="text-xs cursor-pointer select-none" onClick={() => toggleSort('status')}>
                      <span className="flex items-center gap-1">{t('status')} <ArrowUpDown className="h-3 w-3" /></span>
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredObligations.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={5} className="text-center py-8 text-muted-foreground text-sm">
                        {t('noObligations')}
                      </TableCell>
                    </TableRow>
                  ) : filteredObligations.map(o => {
                    const cfg = OBL_STATUS[o.status] || OBL_STATUS.pending
                    const Icon = cfg.icon
                    return (
                      <TableRow key={o.id}>
                        <TableCell className="text-xs font-medium max-w-[200px] truncate">
                          {o.serviceName || o.serviceCode || '—'}
                          {o.ministryName && <p className="text-[10px] text-muted-foreground">{o.ministryName}</p>}
                        </TableCell>
                        <TableCell className="text-xs">
                          <Badge variant="secondary" className="text-[10px]">{o.feeType}</Badge>
                        </TableCell>
                        <TableCell className="text-xs text-right font-mono">
                          {fmtXAF(o.amount, locale)}
                          {o.penaltyAmount > 0 && (
                            <span className="block text-[10px] text-red-500">+{fmtXAF(o.penaltyAmount, locale)}</span>
                          )}
                        </TableCell>
                        <TableCell className="text-xs">{fmtDate(o.dueDate, locale)}</TableCell>
                        <TableCell>
                          <Badge className={`text-[10px] gap-1 ${cfg.color}`}>
                            <Icon className="h-3 w-3" />{o.status}
                          </Badge>
                        </TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ═══ PAYMENTS TAB ═══ */}
        <TabsContent value="payments" className="space-y-3 mt-4">
          <Card>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="text-xs">{t('reference')}</TableHead>
                    <TableHead className="text-xs">{t('method')}</TableHead>
                    <TableHead className="text-xs text-right">{t('amount')}</TableHead>
                    <TableHead className="text-xs">{t('date')}</TableHead>
                    <TableHead className="text-xs">{t('status')}</TableHead>
                    <TableHead className="text-xs">{t('receipt')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {payments.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={6} className="text-center py-8 text-muted-foreground text-sm">
                        {t('noPayments')}
                      </TableCell>
                    </TableRow>
                  ) : payments.map(p => (
                    <TableRow key={p.id}>
                      <TableCell className="text-xs font-mono">{p.reference}</TableCell>
                      <TableCell className="text-xs">
                        <span className="flex items-center gap-1">
                          <CreditCard className="h-3 w-3 text-muted-foreground" />
                          {METHOD_LABELS[p.method] || p.method}
                        </span>
                      </TableCell>
                      <TableCell className="text-xs text-right font-mono font-bold">{fmtXAF(p.amount, locale)}</TableCell>
                      <TableCell className="text-xs">{fmtDate(p.validatedAt || p.createdAt, locale)}</TableCell>
                      <TableCell>
                        <Badge className={`text-[10px] ${PAY_STATUS[p.status] || 'bg-gray-100'}`}>
                          {p.status === 'completed' ? '✓' : '⏳'} {p.status}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        {p.receiptUrl ? (
                          <a href={p.receiptUrl} target="_blank" rel="noopener noreferrer">
                            <Button variant="ghost" size="sm" className="h-7 text-xs gap-1">
                              <Download className="h-3 w-3" /> {p.receiptNumber || t('download')}
                            </Button>
                          </a>
                        ) : p.receiptNumber ? (
                          <span className="text-xs text-muted-foreground">{p.receiptNumber}</span>
                        ) : (
                          <span className="text-xs text-muted-foreground">—</span>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              {payTotalPages > 1 && (
                <div className="flex items-center justify-between px-3 py-2 border-t text-xs text-muted-foreground">
                  <span>{payPage}/{payTotalPages}</span>
                  <div className="flex gap-1">
                    <Button variant="outline" size="icon" className="h-7 w-7" disabled={payPage <= 1}
                      onClick={() => setPayPage(p => p - 1)}><ChevronLeft className="h-3.5 w-3.5" /></Button>
                    <Button variant="outline" size="icon" className="h-7 w-7" disabled={payPage >= payTotalPages}
                      onClick={() => setPayPage(p => p + 1)}><ChevronRight className="h-3.5 w-3.5" /></Button>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ═══ INSPECTIONS TAB ═══ */}
        <TabsContent value="inspections" className="space-y-3 mt-4">
          {inspections.length === 0 ? (
            <Card className="py-8">
              <CardContent className="text-center text-muted-foreground">
                <Eye className="h-8 w-8 mx-auto mb-2 opacity-30" />
                <p>{t('noInspections')}</p>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-3">
              {inspections.map(insp => (
                <Card key={insp.id} className={`border-l-4 ${
                  insp.sealApplied ? 'border-l-red-500' :
                  insp.miseEnDemeure ? 'border-l-amber-500' :
                  insp.conforme ? 'border-l-green-500' : 'border-l-gray-300'
                }`}>
                  <CardContent className="p-4">
                    <div className="flex items-start justify-between">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <Calendar className="h-4 w-4 text-muted-foreground" />
                          <span className="text-sm font-medium">{fmtDate(insp.date, locale)}</span>
                          <Badge className={`text-[10px] ${insp.conforme ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                            {insp.conforme ? t('conforme') : t('nonConforme')}
                          </Badge>
                          {insp.result && <span className="text-xs text-muted-foreground">{insp.result}</span>}
                        </div>
                        {insp.activityDeclared && (
                          <p className="text-xs text-muted-foreground">
                            {t('activity')}: {insp.activityDeclared}
                            {insp.activityObserved && insp.activityObserved !== insp.activityDeclared && (
                              <span className="text-amber-600"> → {insp.activityObserved}</span>
                            )}
                          </p>
                        )}
                      </div>
                      <div className="flex flex-col gap-1 items-end">
                        {insp.sealApplied && (
                          <Badge className="bg-red-100 text-red-800 text-[10px] gap-1">
                            <Lock className="h-3 w-3" /> {t('sealApplied')}
                          </Badge>
                        )}
                        {insp.miseEnDemeure && (
                          <Badge className="bg-amber-100 text-amber-800 text-[10px] gap-1">
                            <FileWarning className="h-3 w-3" /> {t('miseEnDemeure')}
                            {insp.miseEnDemeureDeadline && (
                              <span className="ml-1">→ {fmtDate(insp.miseEnDemeureDeadline, locale)}</span>
                            )}
                          </Badge>
                        )}
                        {insp.paymentCollected && (
                          <Badge className="bg-green-100 text-green-800 text-[10px] gap-1">
                            <Receipt className="h-3 w-3" /> {t('paymentCollected')}
                            {insp.paymentAmount && <span className="ml-1">{fmtXAF(insp.paymentAmount, locale)}</span>}
                          </Badge>
                        )}
                      </div>
                    </div>
                    {insp.notes && (
                      <p className="text-xs text-muted-foreground mt-2 italic">{insp.notes}</p>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}
