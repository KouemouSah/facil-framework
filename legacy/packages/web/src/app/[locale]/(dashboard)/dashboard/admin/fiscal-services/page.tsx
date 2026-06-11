'use client'

/**
 * Fiscal Services Admin Page — Server-Side Pagination & Filtering
 *
 * Phase 2: All filters (search, ministry, sector, category, status) + sorting
 * are sent to the backend. No more pageSize=1000 client-side filtering.
 *
 * @module dashboard/admin/fiscal-services
 */

import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { useLocale, useTranslations } from 'next-intl'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  FileText, RefreshCw, AlertTriangle, Search, Plus, Upload, Eye, EyeOff, Edit, Trash2,
  TrendingUp, CheckCircle2, BarChart3, ChevronLeft, ChevronRight, Download,
  ArrowUpDown, ArrowUp, ArrowDown,
} from 'lucide-react'
import { useToast } from '@/hooks/use-toast'
import fiscalServicesAPI from '@/modules/fiscal-services/services/api'
import type {
  FiscalServiceResponse,
  FiscalServiceStats,
  Ministry,
  Sector,
  Category,
  ServiceTypeEnum,
  ServiceStatusEnum,
} from '@/types/fiscal-service'
import { BackendUnavailableAlert } from '@/modules/admin/components'
import FiscalServicesTabNav from '@/modules/fiscal-services/components/FiscalServicesTabNav'

export default function FiscalServicesPage() {
  const locale = useLocale()
  const t = useTranslations('admin.fiscalServices')
  const router = useRouter()
  const { toast } = useToast()

  // Data states
  const [services, setServices] = useState<FiscalServiceResponse[]>([])
  const [totalServices, setTotalServices] = useState(0)
  const [totalPages, setTotalPages] = useState(0)
  const [stats, setStats] = useState<FiscalServiceStats | null>(null)
  const [ministries, setMinistries] = useState<Ministry[]>([])
  const [sectors, setSectors] = useState<Sector[]>([])
  const [categories, setCategories] = useState<Category[]>([])

  // UI states
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isBackendUnavailable, setIsBackendUnavailable] = useState(false)
  const [isExporting, setIsExporting] = useState(false)

  // Filter states — all sent to backend
  const [searchQuery, setSearchQuery] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [ministryFilter, setMinistryFilter] = useState<number | 'all'>('all')
  const [sectorFilter, setSectorFilter] = useState<number | 'all'>('all')
  const [categoryFilter, setCategoryFilter] = useState<number | 'all'>('all')
  const [statusFilter, setStatusFilter] = useState<ServiceStatusEnum | 'all'>('all')

  // Sort
  const [sortBy, setSortBy] = useState<string>('service_code')
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc')

  // Pagination
  const [currentPage, setCurrentPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)

  // Race condition protection
  const fetchSeq = useRef(0)

  // Debounce search input (400ms)
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchQuery)
      setCurrentPage(1) // Reset page on new search
    }, 400)
    return () => clearTimeout(timer)
  }, [searchQuery])

  // Fetch hierarchy data (for filter dropdowns — small, cacheable)
  useEffect(() => {
    const fetchHierarchy = async () => {
      try {
        const [m, s, c] = await Promise.all([
          fiscalServicesAPI.hierarchy.ministries.list(locale),
          fiscalServicesAPI.hierarchy.sectors.list(undefined, locale),
          fiscalServicesAPI.hierarchy.categories.list(undefined, locale),
        ])
        setMinistries(m)
        setSectors(s)
        setCategories(c)
      } catch (err) {
        console.error('Error fetching hierarchy:', err)
      }
    }
    fetchHierarchy()
  }, [locale])

  // Fetch stats once
  useEffect(() => {
    fiscalServicesAPI.admin.stats().then(setStats).catch(() => {})
  }, [])

  // SERVER-SIDE fetch — triggered by any filter/sort/page change
  const fetchServices = useCallback(async () => {
    const seq = ++fetchSeq.current
    setIsLoading(true)
    setError(null)

    try {
      const params: Record<string, unknown> = {
        page: currentPage,
        pageSize,
        language: locale,
        sortBy,
        sortOrder,
      }
      if (debouncedSearch) params.search = debouncedSearch
      if (categoryFilter !== 'all') params.categoryId = categoryFilter
      if (statusFilter !== 'all') params.status = statusFilter
      if (ministryFilter !== 'all') params.ministryId = ministryFilter
      if (sectorFilter !== 'all') params.sectorId = sectorFilter

      const response = await fiscalServicesAPI.services.list(params as Parameters<typeof fiscalServicesAPI.services.list>[0])

      // Guard against stale responses
      if (seq !== fetchSeq.current) return

      setServices(response.services || [])
      setTotalServices(response.total || 0)
      setTotalPages(response.totalPages || Math.ceil((response.total || 0) / pageSize))
      setIsBackendUnavailable(false)
    } catch (err) {
      if (seq !== fetchSeq.current) return
      const msg = err instanceof Error ? err.message : 'Error loading services'
      setError(msg)
      if (msg.includes('fetch') || msg.includes('Network') || msg.includes('Failed')) {
        setIsBackendUnavailable(true)
      }
      toast({ variant: 'destructive', title: t('errorTitle'), description: t('errorLoadingServices') })
    } finally {
      if (seq === fetchSeq.current) setIsLoading(false)
    }
  }, [currentPage, pageSize, debouncedSearch, categoryFilter, statusFilter, ministryFilter, sectorFilter, sortBy, sortOrder, locale, t, toast])

  useEffect(() => { fetchServices() }, [fetchServices])

  // Reset child filters on parent change
  useEffect(() => { setSectorFilter('all'); setCategoryFilter('all') }, [ministryFilter])
  useEffect(() => { setCategoryFilter('all') }, [sectorFilter])

  // Reset page on filter change (except search which is handled in debounce)
  useEffect(() => { setCurrentPage(1) }, [ministryFilter, sectorFilter, categoryFilter, statusFilter, pageSize])

  // Cascading filter options (client-side on small hierarchy data)
  const filteredSectors = useMemo(() => {
    if (ministryFilter === 'all') return sectors
    return sectors.filter(s => (s.ministryId ?? s.ministry_id) === ministryFilter)
  }, [sectors, ministryFilter])

  const filteredCategories = useMemo(() => {
    if (sectorFilter !== 'all') {
      return categories.filter(c => (c.sectorId ?? c.sector_id) === sectorFilter)
    }
    if (ministryFilter !== 'all') {
      const sectorIds = filteredSectors.map(s => s.id)
      return categories.filter(c =>
        (c.ministryId ?? c.ministry_id) === ministryFilter ||
        (sectorIds.includes(c.sectorId ?? c.sector_id ?? 0))
      )
    }
    return categories
  }, [categories, sectorFilter, ministryFilter, filteredSectors])

  // Actions
  const handleDelete = async (service: FiscalServiceResponse) => {
    if (!confirm(t('confirmDelete', { name: service.nameEs }))) return
    try {
      await fiscalServicesAPI.admin.delete(service.id)
      toast({ title: t('successTitle'), description: t('serviceDeleted') })
      fetchServices()
      fiscalServicesAPI.admin.stats().then(setStats).catch(() => {})
    } catch {
      toast({ variant: 'destructive', title: t('errorTitle'), description: t('errorDeleting') })
    }
  }

  const handleExportCsv = async () => {
    setIsExporting(true)
    try {
      const params: Record<string, unknown> = {}
      if (debouncedSearch) params.search = debouncedSearch
      if (categoryFilter !== 'all') params.categoryId = categoryFilter
      if (statusFilter !== 'all') params.status = statusFilter
      if (ministryFilter !== 'all') params.ministryId = ministryFilter
      if (sectorFilter !== 'all') params.sectorId = sectorFilter

      const blob = await fiscalServicesAPI.admin.exportCsv(params as Parameters<typeof fiscalServicesAPI.admin.exportCsv>[0])
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `fiscal_services_${new Date().toISOString().slice(0, 10)}.csv`
      a.click()
      URL.revokeObjectURL(url)
      toast({ title: t('successTitle'), description: `${totalServices} servicios exportados` })
    } catch {
      toast({ variant: 'destructive', title: t('errorTitle'), description: 'Error exporting CSV' })
    } finally {
      setIsExporting(false)
    }
  }

  const handleSort = (column: string) => {
    if (sortBy === column) {
      setSortOrder(prev => prev === 'asc' ? 'desc' : 'asc')
    } else {
      setSortBy(column)
      setSortOrder('asc')
    }
    setCurrentPage(1)
  }

  const SortIcon = ({ column }: { column: string }) => {
    if (sortBy !== column) return <ArrowUpDown className="h-3 w-3 ml-1 opacity-40" />
    return sortOrder === 'asc'
      ? <ArrowUp className="h-3 w-3 ml-1" />
      : <ArrowDown className="h-3 w-3 ml-1" />
  }

  // Badges
  const getStatusBadge = (status: ServiceStatusEnum) => {
    const cls: Record<string, string> = {
      active: 'bg-green-100 text-green-700',
      inactive: 'bg-gray-100 text-gray-700',
      draft: 'bg-blue-100 text-blue-700',
      deprecated: 'bg-red-100 text-red-700',
    }
    return (
      <Badge variant="outline" className={cls[status] || ''}>
        {t(`status${status.charAt(0).toUpperCase() + status.slice(1)}` as Parameters<typeof t>[0])}
      </Badge>
    )
  }

  const getTypeBadge = (type: ServiceTypeEnum) => (
    <Badge variant="outline" className="bg-purple-50 text-purple-700 text-xs">
      {t(`type${type.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join('')}` as Parameters<typeof t>[0])}
    </Badge>
  )

  const formatCurrency = (amount: number | undefined) => {
    if (!amount) return '-'
    return new Intl.NumberFormat(locale, { style: 'currency', currency: 'XAF', minimumFractionDigits: 0 }).format(amount)
  }

  return (
    <div className="space-y-4">
      <FiscalServicesTabNav activeTab="catalog" />

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{t('title')}</h1>
          <p className="text-muted-foreground text-sm">{t('subtitle')}</p>
        </div>
        <div className="flex items-center gap-2">
          <Button size="sm" variant="outline" onClick={handleExportCsv} disabled={isExporting}>
            <Download className="h-4 w-4 mr-1" />
            CSV
          </Button>
          <Button size="sm" variant="outline">
            <Upload className="h-4 w-4 mr-1" />
            {t('importServices')}
          </Button>
          <Button size="sm" onClick={() => router.push(`/${locale}/dashboard/admin/fiscal-services/new`)}>
            <Plus className="h-4 w-4 mr-1" />
            {t('createService')}
          </Button>
        </div>
      </div>

      {isBackendUnavailable && <BackendUnavailableAlert />}

      {/* Stats */}
      <div className="grid gap-3 md:grid-cols-4">
        <Card className="p-3">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-muted-foreground">{t('statsTotal')}</p>
              <p className="text-xl font-bold">{stats?.totalServices || 0}</p>
            </div>
            <FileText className="h-4 w-4 text-muted-foreground" />
          </div>
        </Card>
        <Card className="p-3">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-muted-foreground">{t('statsActive')}</p>
              <p className="text-xl font-bold">{stats?.activeServices || 0}</p>
            </div>
            <CheckCircle2 className="h-4 w-4 text-green-500" />
          </div>
        </Card>
        <Card className="p-3">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-muted-foreground">{t('statsByType')}</p>
              <p className="text-xl font-bold">{stats?.servicesByType ? Object.keys(stats.servicesByType).length : 0}</p>
            </div>
            <BarChart3 className="h-4 w-4 text-blue-500" />
          </div>
        </Card>
        <Card className="p-3">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-muted-foreground">{t('statsByMinistry')}</p>
              <p className="text-xl font-bold">{ministries.length}</p>
            </div>
            <TrendingUp className="h-4 w-4 text-purple-500" />
          </div>
        </Card>
      </div>

      {/* Services Table */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-base">{t('listTitle')}</CardTitle>
              <CardDescription className="text-xs">
                {totalServices} {t('servicesFound', { count: totalServices })}
              </CardDescription>
            </div>
            <Button size="sm" variant="ghost" onClick={fetchServices} disabled={isLoading}>
              <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
            </Button>
          </div>

          {/* Filters row */}
          <div className="grid gap-2 md:grid-cols-6 pt-2">
            <div className="relative md:col-span-2">
              <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder={t('searchPlaceholder')}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-8 h-9 text-sm"
              />
            </div>

            <Select value={String(ministryFilter)} onValueChange={(v) => setMinistryFilter(v === 'all' ? 'all' : Number(v))}>
              <SelectTrigger className="h-9 text-sm">
                <SelectValue placeholder={t('filterByMinistry')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('allMinistries')}</SelectItem>
                {ministries.map((m) => (
                  <SelectItem key={m.id} value={String(m.id)}>{m.nameEs || m.name_es}</SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select value={String(sectorFilter)} onValueChange={(v) => setSectorFilter(v === 'all' ? 'all' : Number(v))}>
              <SelectTrigger className="h-9 text-sm">
                <SelectValue placeholder={t('filterBySector')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('allSectors')}</SelectItem>
                {filteredSectors.map((s) => (
                  <SelectItem key={s.id} value={String(s.id)}>{s.nameEs || s.name_es}</SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select value={String(categoryFilter)} onValueChange={(v) => setCategoryFilter(v === 'all' ? 'all' : Number(v))}>
              <SelectTrigger className="h-9 text-sm">
                <SelectValue placeholder={t('filterByCategory')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('allCategories')}</SelectItem>
                {filteredCategories.map((c) => (
                  <SelectItem key={c.id} value={String(c.id)}>{c.nameEs || c.name_es}</SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select value={statusFilter} onValueChange={(v) => setStatusFilter(v as typeof statusFilter)}>
              <SelectTrigger className="h-9 text-sm">
                <SelectValue placeholder={t('filterByStatus')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('allStatuses')}</SelectItem>
                <SelectItem value="active">{t('statusActive')}</SelectItem>
                <SelectItem value="inactive">{t('statusInactive')}</SelectItem>
                <SelectItem value="draft">{t('statusDraft')}</SelectItem>
                <SelectItem value="deprecated">{t('statusDeprecated')}</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardHeader>

        <CardContent className="p-0">
          {isLoading && (
            <div className="flex items-center justify-center py-12">
              <RefreshCw className="h-5 w-5 animate-spin text-muted-foreground" />
              <span className="ml-2 text-sm text-muted-foreground">{t('loading')}</span>
            </div>
          )}

          {error && !isBackendUnavailable && (
            <div className="flex items-center justify-center py-12 text-red-500 text-sm">
              <AlertTriangle className="h-4 w-4 mr-2" />
              {error}
            </div>
          )}

          {!isLoading && !error && services.length === 0 && (
            <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
              <FileText className="h-10 w-10 mb-3 opacity-50" />
              <p className="text-sm">{t('noServicesFound')}</p>
            </div>
          )}

          {!isLoading && !error && services.length > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="cursor-pointer select-none" onClick={() => handleSort('service_code')}>
                    <span className="flex items-center">{t('tableCode')}<SortIcon column="service_code" /></span>
                  </TableHead>
                  <TableHead className="cursor-pointer select-none" onClick={() => handleSort('name')}>
                    <span className="flex items-center">{t('tableName')}<SortIcon column="name" /></span>
                  </TableHead>
                  <TableHead>{t('tableType')}</TableHead>
                  <TableHead className="cursor-pointer select-none" onClick={() => handleSort('status')}>
                    <span className="flex items-center">{t('tableStatus')}<SortIcon column="status" /></span>
                  </TableHead>
                  <TableHead className="cursor-pointer select-none" onClick={() => handleSort('price')}>
                    <span className="flex items-center">{t('tableExpeditionAmount')}<SortIcon column="price" /></span>
                  </TableHead>
                  <TableHead>{t('tableRenewalAmount')}</TableHead>
                  <TableHead className="text-right w-[160px]">{t('tableActions')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {services.map((service) => (
                  <TableRow key={service.id} className="cursor-pointer hover:bg-muted/50"
                    onClick={() => router.push(`/${locale}/dashboard/admin/fiscal-services/${service.id}`)}>
                    <TableCell className="font-mono text-xs">{service.serviceCode}</TableCell>
                    <TableCell className="font-medium text-sm max-w-[300px]">
                      <span className="flex items-center gap-1.5 truncate">
                        {service.nameEs}
                        {service.descriptionEs && service.descriptionVisible === false && (
                          <span title={t('descriptionHidden')}>
                            <EyeOff className="h-3 w-3 text-yellow-500 flex-shrink-0" />
                          </span>
                        )}
                      </span>
                    </TableCell>
                    <TableCell>{getTypeBadge(service.serviceType)}</TableCell>
                    <TableCell>{getStatusBadge(service.status)}</TableCell>
                    <TableCell className="text-sm">{formatCurrency(service.tasaExpedicion)}</TableCell>
                    <TableCell className="text-sm">{formatCurrency(service.tasaRenovacion)}</TableCell>
                    <TableCell className="text-right" onClick={(e) => e.stopPropagation()}>
                      <div className="flex items-center justify-end gap-1">
                        <Button variant="ghost" size="icon" className="h-7 w-7"
                          onClick={() => router.push(`/${locale}/dashboard/admin/fiscal-services/${service.id}`)}>
                          <Eye className="h-3.5 w-3.5" />
                        </Button>
                        <Button variant="ghost" size="icon" className="h-7 w-7"
                          onClick={() => router.push(`/${locale}/dashboard/admin/fiscal-services/${service.id}/edit`)}>
                          <Edit className="h-3.5 w-3.5" />
                        </Button>
                        <Button variant="ghost" size="icon" className="h-7 w-7 text-destructive hover:text-destructive"
                          onClick={() => handleDelete(service)}>
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}

          {/* Pagination — server-side */}
          {!isLoading && totalPages > 0 && (
            <div className="flex items-center justify-between px-4 py-3 border-t">
              <div className="flex items-center gap-2">
                <span className="text-xs text-muted-foreground">{t('rowsPerPage')}</span>
                <Select value={String(pageSize)} onValueChange={(v) => { setPageSize(Number(v)); setCurrentPage(1) }}>
                  <SelectTrigger className="w-[60px] h-7 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="10">10</SelectItem>
                    <SelectItem value="20">20</SelectItem>
                    <SelectItem value="50">50</SelectItem>
                    <SelectItem value="100">100</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="flex items-center gap-2">
                <span className="text-xs text-muted-foreground">
                  {t('page')} {currentPage} {t('of')} {totalPages}
                </span>
                <Button variant="outline" size="sm" className="h-7 px-2"
                  onClick={() => setCurrentPage(p => Math.max(1, p - 1))} disabled={currentPage === 1}>
                  <ChevronLeft className="h-3.5 w-3.5" />
                </Button>
                <Button variant="outline" size="sm" className="h-7 px-2"
                  onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))} disabled={currentPage >= totalPages}>
                  <ChevronRight className="h-3.5 w-3.5" />
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
