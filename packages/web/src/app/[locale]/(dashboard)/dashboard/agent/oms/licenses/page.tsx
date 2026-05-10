'use client'

/**
 * OMS Licenses Overview — Commercial licenses scoped by ministry
 *
 * Table with stats cards, filters, badge status, PDF download.
 * Uses /licenses/ backend endpoints.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useLocale, useTranslations } from 'next-intl'
import { exportToExcel } from '@/core/utils/export'
import {
  FileCheck, Search, ChevronLeft, ChevronRight, RefreshCw,
  TrendingUp, AlertTriangle, DollarSign, Download, Eye,
  Building2, ArrowUpDown, ArrowUp, ArrowDown,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table'
import { useToast } from '@/hooks/use-toast'
import { omsLicensesApi } from '@/modules/oms/services/api'
import type { LicenseResponse, LicenseStats } from '@/modules/oms/types'
import { LICENSE_STATUS_CONFIG, fmtXAF, fmtK } from '@/modules/oms/utils/formatters'

export default function OMSLicensesPage() {
  const router = useRouter()
  const locale = useLocale()
  const t = useTranslations('oms.licenses')
  const { toast } = useToast()

  const [stats, setStats] = useState<LicenseStats | null>(null)
  const [licenses, setLicenses] = useState<{ items: LicenseResponse[]; total: number } | null>(null)
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState('all')
  const [yearFilter, setYearFilter] = useState<number>(new Date().getFullYear())
  const [sortCol, setSortCol] = useState<'balance' | 'total_amount' | 'company_name' | null>(null)
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')
  const [search, setSearch] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const seqRef = useRef(0)
  const debounceRef = useRef<NodeJS.Timeout>()
  const PAGE_SIZE = 20

  const fetchAll = useCallback(async () => {
    const seq = ++seqRef.current
    setLoading(true)
    try {
      const [s, l] = await Promise.all([
        omsLicensesApi.getStats(yearFilter),
        omsLicensesApi.list({
          status: statusFilter === 'all' ? undefined : statusFilter,
          fiscal_year: yearFilter,
          search: search || undefined,
          page,
          page_size: PAGE_SIZE,
        }),
      ])
      if (seq === seqRef.current) { setStats(s); setLicenses(l) }
    } catch (err: unknown) {
      if (seq === seqRef.current) {
        const status = (err as { response?: { status?: number } })?.response?.status
        toast({
          title: status === 403 ? t('accessDenied') : t('loadError'),
          variant: 'destructive',
        })
      }
    } finally {
      if (seq === seqRef.current) setLoading(false)
    }
  }, [page, statusFilter, yearFilter, search, toast, t])

  useEffect(() => { fetchAll() }, [fetchAll])

  // Debounce search input → triggers server-side search via fetchAll dependency
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      setSearch(searchInput)
      setPage(1) // Reset to page 1 on new search
    }, 300)
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current) }
  }, [searchInput])

  // Client-side sort only (search is server-side, sort on current page)
  const filteredItems = (() => {
    let items = licenses?.items ?? []
    if (sortCol) {
      items = [...items].sort((a, b) => {
        let va: number | string = 0, vb: number | string = 0
        if (sortCol === 'balance') { va = a.total_amount - a.amount_paid; vb = b.total_amount - b.amount_paid }
        else if (sortCol === 'total_amount') { va = a.total_amount; vb = b.total_amount }
        else if (sortCol === 'company_name') { va = a.company_name || ''; vb = b.company_name || '' }
        if (typeof va === 'string') return sortDir === 'asc' ? va.localeCompare(vb as string) : (vb as string).localeCompare(va)
        return sortDir === 'asc' ? va - (vb as number) : (vb as number) - va
      })
    }
    return items
  })()

  const totalPages = licenses ? Math.ceil(licenses.total / PAGE_SIZE) : 0
  const recoveryPct = stats && stats.total_amount > 0
    ? Math.round((stats.total_paid / stats.total_amount) * 100) : 0

  const toggleSort = (col: 'balance' | 'total_amount' | 'company_name') => {
    if (sortCol === col) setSortDir(prev => prev === 'asc' ? 'desc' : 'asc')
    else { setSortCol(col); setSortDir('desc') }
  }

  const handleExportCSV = () => {
    if (!filteredItems.length) return
    const headers = [t('company'), 'NIF', t('zone'), t('year'), t('totalAmount'), t('paidAmount'), t('balance'), t('status')]
    const rows = filteredItems.map(l => [
      l.company_name || '', l.company_nif || '', l.zone_code || '',
      String(l.fiscal_year), String(l.total_amount), String(l.amount_paid),
      String(l.total_amount - l.amount_paid), l.status,
    ])
    const csv = [headers.join(','), ...rows.map(r => r.map(v => `"${v}"`).join(','))].join('\n')
    const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `licencias_${yearFilter}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleDownloadPDF = async (licenseId: string) => {
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

  return (
    <div className="space-y-4 p-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold flex items-center gap-2">
            <FileCheck className="h-5 w-5" />
            {t('title')}
          </h1>
          <p className="text-sm text-muted-foreground">{t('subtitle')}</p>
        </div>
        <div className="flex gap-1">
          <Button variant="outline" size="sm" onClick={() => {
            if (!licenses?.items?.length) return
            exportToExcel(licenses.items.map(l => ({
              Empresa: l.company_name || '',
              NIF_Registro: l.company_nif || l.company_registration_number || '',
              Zona: l.zone_code || '',
              'Año Fiscal': l.fiscal_year,
              'Total Obligaciones': l.total_amount,
              Pagado: l.amount_paid,
              Pendiente: (l.total_amount || 0) - (l.amount_paid || 0),
              'Obl. Total': l.obligations_count,
              'Obl. Pagadas': l.paid_count,
              Estado: l.status,
            })), { fileName: `licencias_oms_${new Date().toISOString().slice(0,10)}`, sheetName: 'Licencias' })
          }} disabled={!licenses?.items?.length}>
            <FileCheck className="h-3.5 w-3.5 mr-1" /> Excel
          </Button>
          <Button variant="outline" size="sm" onClick={fetchAll} disabled={loading}>
            <RefreshCw className={`h-3.5 w-3.5 mr-1 ${loading ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {loading && !stats ? (
          Array.from({ length: 4 }).map((_, i) => (
            <Card key={i} className="p-3"><Skeleton className="h-14 w-full" /></Card>
          ))
        ) : stats ? (<>
          <Card className="p-3">
            <div className="flex items-center gap-2">
              <FileCheck className="h-5 w-5 text-blue-500" />
              <div>
                <p className="text-xs text-muted-foreground">{t('total')}</p>
                <p className="text-2xl font-bold">{stats.total_licenses}</p>
                <p className="text-[10px] text-muted-foreground">{stats.active_licenses} {t('active')}</p>
              </div>
            </div>
          </Card>
          <Card className="p-3">
            <div className="flex items-center gap-2">
              <AlertTriangle className={`h-5 w-5 ${stats.overdue_licenses > 0 ? 'text-red-500' : 'text-gray-300'}`} />
              <div>
                <p className="text-xs text-muted-foreground">{t('overdueCount')}</p>
                <p className="text-2xl font-bold text-red-700">{stats.overdue_licenses}</p>
              </div>
            </div>
          </Card>
          <Card className="p-3">
            <div className="flex items-center gap-2">
              <DollarSign className="h-5 w-5 text-amber-500" />
              <div>
                <p className="text-xs text-muted-foreground">{t('totalDebt')}</p>
                <p className="text-lg font-bold">{fmtK(stats.total_debt)} XAF</p>
              </div>
            </div>
          </Card>
          <Card className="p-3">
            <div className="flex items-center gap-2">
              <TrendingUp className="h-5 w-5 text-green-500" />
              <div>
                <p className="text-xs text-muted-foreground">{t('recovery')}</p>
                <p className="text-2xl font-bold">{recoveryPct}%</p>
                <div className="h-1.5 w-full bg-gray-100 rounded-full mt-1 overflow-hidden">
                  <div className="h-full rounded-full transition-all duration-500"
                    style={{
                      width: `${recoveryPct}%`,
                      backgroundColor: recoveryPct >= 70 ? '#22c55e' : recoveryPct >= 40 ? '#eab308' : '#ef4444',
                    }} />
                </div>
              </div>
            </div>
          </Card>
        </>) : null}
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-2">
        <div className="relative flex-1 min-w-[160px]">
          <Search className="absolute left-2.5 top-2 h-3.5 w-3.5 text-muted-foreground" />
          <Input value={searchInput} onChange={e => setSearchInput(e.target.value)}
            placeholder={t('searchPlaceholder')} className="pl-8 h-8 text-xs" />
        </div>
        <Select value={statusFilter} onValueChange={v => { setStatusFilter(v); setPage(1) }}>
          <SelectTrigger className="w-[120px] h-8 text-xs"><SelectValue placeholder={t('status')} /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t('allStatuses')}</SelectItem>
            <SelectItem value="open">{t('open')}</SelectItem>
            <SelectItem value="partial">{t('partial')}</SelectItem>
            <SelectItem value="overdue">{t('overdue')}</SelectItem>
            <SelectItem value="complete">{t('complete')}</SelectItem>
          </SelectContent>
        </Select>
        <Select value={String(yearFilter)} onValueChange={v => { setYearFilter(Number(v)); setPage(1) }}>
          <SelectTrigger className="w-[90px] h-8 text-xs"><SelectValue placeholder={t('year')} /></SelectTrigger>
          <SelectContent>
            {Array.from({ length: 5 }, (_, i) => new Date().getFullYear() - i).map(y => (
              <SelectItem key={y} value={String(y)}>{y}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button variant="outline" size="sm" className="h-8 gap-1 text-xs" onClick={handleExportCSV}>
          <Download className="h-3.5 w-3.5" /> CSV
        </Button>
        <span className="text-xs text-muted-foreground self-center">{filteredItems.length}/{licenses?.total ?? 0}</span>
      </div>

      {/* Table */}
      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="text-xs">
                  <button onClick={() => toggleSort('company_name')} className="flex items-center gap-1 hover:text-foreground">
                    {t('company')}
                    {sortCol === 'company_name' ? (sortDir === 'asc' ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />) : <ArrowUpDown className="h-3 w-3 opacity-30" />}
                  </button>
                </TableHead>
                <TableHead className="text-xs w-[80px]">Identificador</TableHead>
                <TableHead className="text-xs w-[60px]">{t('zone')}</TableHead>
                <TableHead className="text-xs w-[70px]">{t('year')}</TableHead>
                <TableHead className="text-xs w-[90px] text-right">
                  <button onClick={() => toggleSort('total_amount')} className="flex items-center gap-1 ml-auto hover:text-foreground">
                    {t('totalAmount')}
                    {sortCol === 'total_amount' ? (sortDir === 'asc' ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />) : <ArrowUpDown className="h-3 w-3 opacity-30" />}
                  </button>
                </TableHead>
                <TableHead className="text-xs w-[90px] text-right">{t('paidAmount')}</TableHead>
                <TableHead className="text-xs w-[90px] text-right">
                  <button onClick={() => toggleSort('balance')} className="flex items-center gap-1 ml-auto hover:text-foreground">
                    {t('balance')}
                    {sortCol === 'balance' ? (sortDir === 'asc' ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />) : <ArrowUpDown className="h-3 w-3 opacity-30" />}
                  </button>
                </TableHead>
                <TableHead className="text-xs w-[80px]">{t('status')}</TableHead>
                <TableHead className="text-xs w-[80px]"></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                <TableRow><TableCell colSpan={9} className="text-center py-8 text-muted-foreground">...</TableCell></TableRow>
              ) : filteredItems.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={9} className="text-center py-12 text-muted-foreground">
                    <FileCheck className="h-8 w-8 mx-auto mb-2 opacity-30" />
                    <p>{t('noLicenses')}</p>
                  </TableCell>
                </TableRow>
              ) : filteredItems.map(lic => {
                const balance = lic.total_amount - lic.amount_paid
                const cfg = LICENSE_STATUS_CONFIG[lic.status] || LICENSE_STATUS_CONFIG.open
                return (
                  <TableRow key={lic.id} className="cursor-pointer hover:bg-muted/50"
                    onClick={() => router.push(`/${locale}/dashboard/agent/oms/licenses/${lic.id}`)}>
                    <TableCell className="text-xs font-medium">
                      <div className="flex items-center gap-1.5">
                        <Building2 className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                        <span className="truncate max-w-[180px]">{lic.company_name || '—'}</span>
                      </div>
                    </TableCell>
                    <TableCell className="text-xs font-mono">{lic.company_registration_number || lic.company_nif || '—'}</TableCell>
                    <TableCell className="text-xs">
                      {lic.zone_code && <Badge variant="outline" className="text-[10px]">{lic.zone_code}</Badge>}
                    </TableCell>
                    <TableCell className="text-xs">{lic.fiscal_year}</TableCell>
                    <TableCell className="text-xs text-right font-mono">{fmtXAF(lic.total_amount, locale)}</TableCell>
                    <TableCell className="text-xs text-right font-mono text-green-700">{fmtXAF(lic.amount_paid, locale)}</TableCell>
                    <TableCell className="text-xs text-right font-mono">
                      <span className={balance > 0 ? 'text-red-700' : 'text-green-700'}>{fmtXAF(balance, locale)}</span>
                    </TableCell>
                    <TableCell>
                      <Badge className={`text-[10px] gap-1 ${cfg.color}`}>
                        <cfg.icon className="h-3 w-3" />
                        {cfg.label}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-0.5" onClick={e => e.stopPropagation()}>
                        <Button variant="ghost" size="icon" className="h-7 w-7"
                          onClick={() => router.push(`/${locale}/dashboard/agent/oms/licenses/${lic.id}`)}>
                          <Eye className="h-3.5 w-3.5" />
                        </Button>
                        <Button variant="ghost" size="icon" className="h-7 w-7"
                          onClick={() => handleDownloadPDF(lic.id)}>
                          <Download className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground text-xs">{licenses?.total ?? 0} — {page}/{totalPages}</span>
          <div className="flex gap-1">
            <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
