'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useLocale, useTranslations } from 'next-intl'
import { useToast } from '@/hooks/use-toast'
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  ClipboardCheck,
  DollarSign,
  QrCode,
  Search,
  Wallet,
  XCircle,
} from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { inspectionApi } from '@/modules/inspections/services/api'
import { INSPECTION_STATUS_CONFIG, fmtXAF } from '@/modules/inspections/utils/formatters'
import type {
  InspectionListResponse,
  InspectionResult,
  InspectionStats,
  InspectionStatus,
} from '@/modules/inspections/types'

/* ------------------------------------------------------------------ */
/* Result badge styling                                                */
/* ------------------------------------------------------------------ */
const RESULT_BADGE_CONFIG: Record<string, { color: string; bgColor: string }> = {
  conforme: { color: 'text-green-700', bgColor: 'bg-green-100' },
  non_conforme: { color: 'text-red-700', bgColor: 'bg-red-100' },
  pending: { color: 'text-gray-700', bgColor: 'bg-gray-100' },
}

const PAGE_SIZE = 20

export default function FieldDashboardPage() {
  const locale = useLocale()
  const router = useRouter()
  const { toast } = useToast()
  const t = useTranslations('inspection')

  /* ---- State ---- */
  const [stats, setStats] = useState<InspectionStats | null>(null)
  const [listData, setListData] = useState<InspectionListResponse | null>(null)
  const [loading, setLoading] = useState(true)

  // Filters
  const today = new Date().toISOString().split('T')[0]
  const [dateFrom, setDateFrom] = useState(today)
  const [dateTo, setDateTo] = useState(today)
  const [statusFilter, setStatusFilter] = useState('all')
  const [resultFilter, setResultFilter] = useState('all')
  const [searchInput, setSearchInput] = useState('')
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)

  // Debounce search
  const debounceRef = useRef<NodeJS.Timeout>()
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      setSearch(searchInput)
      setPage(1)
    }, 350)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [searchInput])

  // Sequence ref to avoid stale responses
  const seqRef = useRef(0)

  /* ---- Fetch ---- */
  const fetchData = useCallback(async () => {
    const seq = ++seqRef.current
    setLoading(true)
    try {
      const [statsData, listResult] = await Promise.all([
        inspectionApi.getStats({ date_from: dateFrom, date_to: dateTo }),
        inspectionApi.list({
          date_from: dateFrom,
          date_to: dateTo,
          status: statusFilter === 'all' ? undefined : statusFilter,
          result: resultFilter === 'all' ? undefined : resultFilter,
          search: search || undefined,
          page,
          page_size: PAGE_SIZE,
        }),
      ])
      if (seq === seqRef.current) {
        setStats(statsData)
        setListData(listResult)
      }
    } catch {
      if (seq === seqRef.current) {
        toast({
          title: t('common.error'),
          description: t('field.loadError'),
          variant: 'destructive',
        })
      }
    } finally {
      if (seq === seqRef.current) setLoading(false)
    }
  }, [dateFrom, dateTo, statusFilter, resultFilter, search, page, toast, t])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  /* ---- Derived ---- */
  const items = listData?.items ?? []
  const totalPages = listData ? Math.ceil(listData.total / PAGE_SIZE) : 0

  /* ---- Helpers ---- */
  const handleFilterChange = (setter: (v: string) => void) => (value: string) => {
    setter(value)
    setPage(1)
  }

  const navigateToInspection = (id: string) => {
    router.push(`/${locale}/dashboard/agent/oms/field/inspect?id=${id}`)
  }

  /* ---- Status options for filter ---- */
  const statusOptions: InspectionStatus[] = [
    'in_progress',
    'completed',
    'mise_en_demeure',
    'seal_proposed',
    'seal_approved',
  ]

  const resultOptions: InspectionResult[] = ['conforme', 'non_conforme', 'pending']

  /* ---- Stat cards config ---- */
  const statCards = [
    {
      label: t('field.inspectionsToday'),
      value: stats?.total ?? 0,
      icon: ClipboardCheck,
      color: 'text-blue-600',
    },
    {
      label: t('field.conforme'),
      value: stats?.conforme ?? 0,
      icon: CheckCircle2,
      color: 'text-green-600',
    },
    {
      label: t('field.nonConforme'),
      value: stats?.non_conforme ?? 0,
      icon: XCircle,
      color: 'text-red-600',
    },
    {
      label: t('field.collected'),
      value: fmtXAF(stats?.total_collected_amount ?? 0, locale),
      icon: DollarSign,
      color: 'text-amber-600',
    },
  ]

  return (
    <div className="flex flex-col gap-3 p-4">
      {/* ==================== Header ==================== */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity className="h-6 w-6 text-blue-600" />
          <h1 className="text-xl font-bold">{t('field.title')}</h1>
        </div>
        <div className="flex gap-2">
          <Button
            size="lg"
            className="gap-2"
            onClick={() =>
              router.push(`/${locale}/dashboard/agent/oms/field/scan`)
            }
          >
            <QrCode className="h-5 w-5" />
            {t('field.newInspection')}
          </Button>
          <Button
            variant="outline"
            size="lg"
            className="gap-2"
            onClick={() =>
              router.push(`/${locale}/dashboard/agent/oms/field/reconcile`)
            }
          >
            <Wallet className="h-5 w-5" />
            {t('field.reconciliation')}
          </Button>
        </div>
      </div>

      {/* ==================== Stats cards ==================== */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {loading && !stats
          ? Array.from({ length: 4 }).map((_, i) => (
              <Card key={i}>
                <CardContent className="p-4">
                  <Skeleton className="h-14 w-full" />
                </CardContent>
              </Card>
            ))
          : statCards.map((s) => (
              <Card key={s.label}>
                <CardContent className="p-4 flex items-center gap-3">
                  <s.icon className={`h-8 w-8 ${s.color}`} />
                  <div>
                    <p className="text-2xl font-bold">{s.value}</p>
                    <p className="text-xs text-muted-foreground">{s.label}</p>
                  </div>
                </CardContent>
              </Card>
            ))}
      </div>

      {/* ==================== Active MED alert ==================== */}
      {stats && stats.mise_en_demeure > 0 && (
        <Card className="border-orange-200 bg-orange-50">
          <CardContent className="p-3 flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-orange-600" />
            <span className="text-sm font-medium text-orange-800">
              {stats.mise_en_demeure} {t('field.activeMed')}
            </span>
          </CardContent>
        </Card>
      )}

      {/* ==================== Filters ==================== */}
      <div className="flex flex-wrap items-end gap-2">
        {/* Date from */}
        <div className="flex flex-col gap-1">
          <label className="text-[10px] font-medium text-muted-foreground">
            {t('filters.date_from')}
          </label>
          <Input
            type="date"
            value={dateFrom}
            onChange={(e) => {
              setDateFrom(e.target.value)
              setPage(1)
            }}
            className="h-8 w-[140px] text-xs"
          />
        </div>
        {/* Date to */}
        <div className="flex flex-col gap-1">
          <label className="text-[10px] font-medium text-muted-foreground">
            {t('filters.date_to')}
          </label>
          <Input
            type="date"
            value={dateTo}
            onChange={(e) => {
              setDateTo(e.target.value)
              setPage(1)
            }}
            className="h-8 w-[140px] text-xs"
          />
        </div>
        {/* Search */}
        <div className="flex flex-col gap-1 flex-1 min-w-[160px]">
          <label className="text-[10px] font-medium text-muted-foreground">
            {t('filters.search')}
          </label>
          <div className="relative">
            <Search className="absolute left-2.5 top-2 h-3.5 w-3.5 text-muted-foreground" />
            <Input
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder={t('filters.search_placeholder')}
              className="pl-8 h-8 text-xs"
            />
          </div>
        </div>
        {/* Status filter */}
        <div className="flex flex-col gap-1">
          <label className="text-[10px] font-medium text-muted-foreground">
            {t('filters.status')}
          </label>
          <Select
            value={statusFilter}
            onValueChange={handleFilterChange(setStatusFilter)}
          >
            <SelectTrigger className="w-[150px] h-8 text-xs">
              <SelectValue placeholder={t('filters.all_statuses')} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t('filters.all_statuses')}</SelectItem>
              {statusOptions.map((s) => (
                <SelectItem key={s} value={s}>
                  {t(`status.${s}`)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        {/* Result filter */}
        <div className="flex flex-col gap-1">
          <label className="text-[10px] font-medium text-muted-foreground">
            {t('filters.result')}
          </label>
          <Select
            value={resultFilter}
            onValueChange={handleFilterChange(setResultFilter)}
          >
            <SelectTrigger className="w-[140px] h-8 text-xs">
              <SelectValue placeholder={t('filters.all_results')} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t('filters.all_results')}</SelectItem>
              {resultOptions.map((r) => (
                <SelectItem key={r} value={r}>
                  {t(`result.${r}`)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* ==================== Inspection table ==================== */}
      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="text-xs">{t('field.date')}</TableHead>
                <TableHead className="text-xs">{t('field.company')}</TableHead>
                <TableHead className="text-xs w-[110px]">
                  {t('field.result')}
                </TableHead>
                <TableHead className="text-xs w-[130px]">
                  {t('field.status')}
                </TableHead>
                <TableHead className="text-xs w-[120px] text-right">
                  {t('field.amount')}
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                Array.from({ length: 5 }).map((_, i) => (
                  <TableRow key={i}>
                    <TableCell colSpan={5}>
                      <Skeleton className="h-10 w-full" />
                    </TableCell>
                  </TableRow>
                ))
              ) : items.length === 0 ? (
                <TableRow>
                  <TableCell
                    colSpan={5}
                    className="text-center py-12 text-muted-foreground"
                  >
                    <ClipboardCheck className="h-8 w-8 mx-auto mb-2 opacity-30" />
                    <p className="text-sm">{t('field.noInspectionsToday')}</p>
                  </TableCell>
                </TableRow>
              ) : (
                items.map((item) => {
                  const statusCfg =
                    INSPECTION_STATUS_CONFIG[item.status] ??
                    INSPECTION_STATUS_CONFIG.in_progress
                  const resultCfg = item.result
                    ? RESULT_BADGE_CONFIG[item.result] ?? RESULT_BADGE_CONFIG.pending
                    : RESULT_BADGE_CONFIG.pending

                  return (
                    <TableRow
                      key={item.id}
                      className="cursor-pointer hover:bg-muted/50"
                      onClick={() => navigateToInspection(item.id)}
                    >
                      {/* Date */}
                      <TableCell className="text-xs">
                        {new Date(item.inspection_date).toLocaleDateString(
                          locale === 'en' ? 'en-GQ' : locale === 'fr' ? 'fr-GQ' : 'es-GQ',
                          {
                            day: '2-digit',
                            month: 'short',
                            year: 'numeric',
                          }
                        )}
                      </TableCell>
                      {/* Company + NIF */}
                      <TableCell className="text-xs">
                        <div className="font-medium truncate max-w-[200px]">
                          {item.company_name || '—'}
                        </div>
                        <div className="text-[10px] text-muted-foreground font-mono">
                          {item.company_nif || ''}
                        </div>
                      </TableCell>
                      {/* Result badge */}
                      <TableCell>
                        <Badge
                          className={`text-[10px] ${resultCfg.bgColor} ${resultCfg.color}`}
                        >
                          {item.result
                            ? t(`result.${item.result}`)
                            : t('result.pending')}
                        </Badge>
                      </TableCell>
                      {/* Status badge */}
                      <TableCell>
                        <Badge
                          className={`text-[10px] ${statusCfg.bgColor} ${statusCfg.color}`}
                        >
                          {t(`status.${item.status}`)}
                        </Badge>
                      </TableCell>
                      {/* Amount */}
                      <TableCell className="text-xs text-right font-mono">
                        {item.payment_amount != null && item.payment_amount > 0
                          ? fmtXAF(item.payment_amount, locale)
                          : item.unpaid_obligations_amount > 0
                            ? (
                              <span className="text-red-600">
                                {fmtXAF(item.unpaid_obligations_amount, locale)}
                              </span>
                            )
                            : '—'}
                      </TableCell>
                    </TableRow>
                  )
                })
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* ==================== Pagination ==================== */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground text-xs">
            {t('field.pageOf', { current: page, total: totalPages })}
          </span>
          <div className="flex gap-1">
            <Button
              variant="outline"
              size="sm"
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            {/* Page number buttons — show up to 5 pages centered around current */}
            {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
              let pageNum: number
              if (totalPages <= 5) {
                pageNum = i + 1
              } else if (page <= 3) {
                pageNum = i + 1
              } else if (page >= totalPages - 2) {
                pageNum = totalPages - 4 + i
              } else {
                pageNum = page - 2 + i
              }
              return (
                <Button
                  key={pageNum}
                  variant={pageNum === page ? 'default' : 'outline'}
                  size="sm"
                  className="w-8 h-8 text-xs"
                  onClick={() => setPage(pageNum)}
                >
                  {pageNum}
                </Button>
              )
            })}
            <Button
              variant="outline"
              size="sm"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
