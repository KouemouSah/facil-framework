'use client'

/**
 * Service Requests Page - User Dashboard
 * List and manage service requests for citizens
 *
 * Dynamic filters from backend:
 * - Status: from /filter-options endpoint (backend enum)
 * - Category: from /filter-options endpoint (backend enum)
 * - Workflow: from /workflows endpoint (filtered by category)
 * - Search: server-side ILIKE on reference + workflow_code
 * - Pagination: server-side with total count
 */

import { useState, useMemo, useEffect, useCallback, useRef } from 'react'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  FilePlus,
  FileText,
  Search,
  Filter,
  Calendar,
  CheckCircle,
  Clock,
  AlertCircle,
  Loader2,
  Eye,
  XCircle,
  CreditCard,
  CalendarCheck,
  ArrowRight,
  RefreshCw,
  Trash2,
  MoreHorizontal,
} from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Checkbox } from '@/components/ui/checkbox'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { useTranslations } from 'next-intl'
import { useServiceRequests } from '@/modules/service-requests'
import type { ServiceRequestFilters, WorkflowConfig, WorkflowCategory } from '@/modules/service-requests'
import { serviceRequestsApi } from '@/modules/service-requests'
import { useWorkflowTranslations, workflowNameKey } from '@/hooks/use-workflow-translations'

// Status color mapping (kept for badge rendering)
const STATUS_COLORS: Record<string, { bg: string; text: string; icon: React.ElementType }> = {
  DRAFT: { bg: 'bg-slate-500', text: 'text-white', icon: FileText },
  TIMBRES_PENDING: { bg: 'bg-amber-500', text: 'text-white', icon: CreditCard },
  TIMBRES_PAID: { bg: 'bg-amber-600', text: 'text-white', icon: CheckCircle },
  SUBMITTED: { bg: 'bg-blue-500', text: 'text-white', icon: Clock },
  DOCUMENTS_REQUIRED: { bg: 'bg-orange-500', text: 'text-white', icon: AlertCircle },
  UNDER_REVIEW: { bg: 'bg-indigo-500', text: 'text-white', icon: Eye },
  DOSSIER_VALIDE: { bg: 'bg-teal-500', text: 'text-white', icon: CheckCircle },
  REJECTED: { bg: 'bg-red-500', text: 'text-white', icon: XCircle },
  PENDING_NOTA_INGRESO: { bg: 'bg-purple-500', text: 'text-white', icon: CreditCard },
  NOTA_UPLOADED: { bg: 'bg-purple-600', text: 'text-white', icon: FileText },
  PAYMENT_PENDING: { bg: 'bg-yellow-500', text: 'text-white', icon: CreditCard },
  PAYMENT_PROCESSING: { bg: 'bg-yellow-600', text: 'text-white', icon: Loader2 },
  PAID: { bg: 'bg-green-500', text: 'text-white', icon: CheckCircle },
  PAYMENT_FAILED: { bg: 'bg-red-600', text: 'text-white', icon: XCircle },
  CITA_SCHEDULED: { bg: 'bg-cyan-500', text: 'text-white', icon: CalendarCheck },
  IN_PROGRESS: { bg: 'bg-blue-600', text: 'text-white', icon: Clock },
  COMPLETED: { bg: 'bg-green-600', text: 'text-white', icon: CheckCircle },
  CANCELLED: { bg: 'bg-gray-500', text: 'text-white', icon: XCircle },
  EXPIRED: { bg: 'bg-gray-600', text: 'text-white', icon: Clock },
}

const PAGE_SIZE = 20

export default function ServiceRequestsPage() {
  const params = useParams()
  const locale = params.locale as string
  const t = useTranslations('service_requests')
  const { tw } = useWorkflowTranslations()

  // Filter state
  const [filterStatus, setFilterStatus] = useState('all')
  const [filterCategory, setFilterCategory] = useState('all')
  const [filterWorkflow, setFilterWorkflow] = useState('all')
  const [searchQuery, setSearchQuery] = useState('')
  const searchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Delete state
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [requestToDelete, setRequestToDelete] = useState<{ id: string; reference: string } | null>(null)
  const [isDeleting, setIsDeleting] = useState(false)

  // Bulk selection state
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [bulkDeleteDialogOpen, setBulkDeleteDialogOpen] = useState(false)
  const [isBulkDeleting, setIsBulkDeleting] = useState(false)

  // Dynamic filter data (loaded from backend)
  const [workflows, setWorkflows] = useState<WorkflowConfig[]>([])
  const [filtersReady, setFiltersReady] = useState(false)

  // Use the service requests hook
  const {
    requests,
    isLoading,
    error,
    pagination,
    filterOptions,
    loadMyRequests,
    loadFilterOptions,
    setFilters,
    clearError,
    deleteRequestById,
  } = useServiceRequests()

  // Stable ref for current filters to avoid circular deps
  const currentFiltersRef = useRef<ServiceRequestFilters>({})

  // =========================================================================
  // INITIALIZATION
  // =========================================================================

  const loadDynamicFilters = useCallback(async () => {
    try {
      await loadFilterOptions()
    } catch (err) {
      console.error('[ServiceRequests] Failed to load filter options:', err)
    }
    try {
      const wf = await serviceRequestsApi.getWorkflows()
      setWorkflows(wf)
    } catch (err) {
      console.error('[ServiceRequests] Failed to load workflows:', err)
    }
    setFiltersReady(true)
  }, [loadFilterOptions])

  // Load filter options + workflows + first page on mount
  useEffect(() => {
    loadDynamicFilters()
    loadMyRequests(1, PAGE_SIZE)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // =========================================================================
  // FILTER HANDLERS (all trigger server-side reload → page 1)
  // =========================================================================

  const reloadWithFilters = useCallback((newFilters: ServiceRequestFilters) => {
    currentFiltersRef.current = newFilters
    setFilters(newFilters)
    // Pass filters directly to avoid stale closure issue
    loadMyRequests(1, PAGE_SIZE, newFilters)
  }, [setFilters, loadMyRequests])

  const handleStatusChange = useCallback((value: string) => {
    setFilterStatus(value)
    const updated = {
      ...currentFiltersRef.current,
      status: value === 'all' ? undefined : value,
    }
    reloadWithFilters(updated)
  }, [reloadWithFilters])

  const handleCategoryChange = useCallback((value: string) => {
    setFilterCategory(value)
    setFilterWorkflow('all') // Reset workflow when category changes
    const updated = {
      ...currentFiltersRef.current,
      category: value === 'all' ? undefined : value as WorkflowCategory,
      workflowCode: undefined, // Reset workflow filter
    }
    reloadWithFilters(updated)
  }, [reloadWithFilters])

  const handleWorkflowChange = useCallback((value: string) => {
    setFilterWorkflow(value)
    const updated = {
      ...currentFiltersRef.current,
      workflowCode: value === 'all' ? undefined : value,
    }
    reloadWithFilters(updated)
  }, [reloadWithFilters])

  const handleSearchChange = useCallback((value: string) => {
    setSearchQuery(value)
    // Debounce search: wait 400ms after last keystroke
    if (searchTimerRef.current) {
      clearTimeout(searchTimerRef.current)
    }
    searchTimerRef.current = setTimeout(() => {
      const updated = {
        ...currentFiltersRef.current,
        search: value.trim() || undefined,
      }
      reloadWithFilters(updated)
    }, 400)
  }, [reloadWithFilters])

  // Cleanup debounce timer on unmount
  useEffect(() => {
    return () => {
      if (searchTimerRef.current) clearTimeout(searchTimerRef.current)
    }
  }, [])

  // =========================================================================
  // DERIVED DATA
  // =========================================================================

  // Workflows filtered by selected category (for 2nd-level dropdown)
  const filteredWorkflows = useMemo(() => {
    if (filterCategory === 'all') return []
    return workflows.filter(w => w.category === filterCategory)
  }, [workflows, filterCategory])

  // =========================================================================
  // DELETE HANDLERS
  // =========================================================================

  const handleDeleteClick = (id: string, reference: string) => {
    setRequestToDelete({ id, reference })
    setDeleteDialogOpen(true)
  }

  const handleDeleteConfirm = async () => {
    if (!requestToDelete) return

    setIsDeleting(true)
    const success = await deleteRequestById(requestToDelete.id)
    setIsDeleting(false)
    setDeleteDialogOpen(false)
    setRequestToDelete(null)

    if (success) {
      loadMyRequests(pagination.page, PAGE_SIZE)
    }
  }

  const handleDeleteCancel = () => {
    setDeleteDialogOpen(false)
    setRequestToDelete(null)
  }

  // =========================================================================
  // BULK SELECTION HANDLERS
  // =========================================================================

  const selectableRequests = useMemo(() => {
    return requests.filter(req => req.status === 'DRAFT')
  }, [requests])

  const isAllSelected = useMemo(() => {
    return selectableRequests.length > 0 && selectableRequests.every(req => selectedIds.has(req.id))
  }, [selectableRequests, selectedIds])

  const isSomeSelected = useMemo(() => {
    return selectableRequests.some(req => selectedIds.has(req.id))
  }, [selectableRequests, selectedIds])

  const handleToggleSelect = (id: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  const handleSelectAll = () => {
    if (isAllSelected) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(selectableRequests.map(req => req.id)))
    }
  }

  const clearSelection = () => {
    setSelectedIds(new Set())
  }

  const handleBulkDeleteConfirm = async () => {
    if (selectedIds.size === 0) return

    setIsBulkDeleting(true)
    const idsToDelete = Array.from(selectedIds)
    for (const id of idsToDelete) {
      try {
        await deleteRequestById(id)
      } catch {
        // Continue with other deletions even if one fails
      }
    }

    setIsBulkDeleting(false)
    setBulkDeleteDialogOpen(false)
    clearSelection()
    loadMyRequests(pagination.page, PAGE_SIZE)
  }

  const handleBulkDeleteCancel = () => {
    setBulkDeleteDialogOpen(false)
  }

  // =========================================================================
  // RENDERING HELPERS
  // =========================================================================

  const getStatusBadge = (status: string) => {
    const config = STATUS_COLORS[status] || STATUS_COLORS.DRAFT
    const Icon = config.icon
    const statusKey = `status.${status.toLowerCase()}`
    let label: string
    try {
      label = t(statusKey)
    } catch {
      label = status.replace(/_/g, ' ')
    }

    return (
      <Badge className={`${config.bg} ${config.text} flex items-center gap-1`}>
        <Icon className="h-3 w-3" />
        {label}
      </Badge>
    )
  }

  const getProgress = (status: string): number => {
    const progressMap: Record<string, number> = {
      DRAFT: 10,
      TIMBRES_PENDING: 15,
      TIMBRES_PAID: 20,
      SUBMITTED: 30,
      DOCUMENTS_REQUIRED: 35,
      UNDER_REVIEW: 50,
      DOSSIER_VALIDE: 60,
      PENDING_NOTA_INGRESO: 65,
      NOTA_UPLOADED: 70,
      PAYMENT_PENDING: 75,
      PAYMENT_PROCESSING: 80,
      PAID: 85,
      CITA_SCHEDULED: 90,
      IN_PROGRESS: 95,
      COMPLETED: 100,
      REJECTED: 100,
      CANCELLED: 100,
      EXPIRED: 100,
    }
    return progressMap[status] || 0
  }

  const canContinue = (status: string): boolean => {
    return ['DRAFT', 'DOCUMENTS_REQUIRED', 'TIMBRES_PENDING'].includes(status)
  }

  const formatAmount = (amount?: number): string => {
    if (!amount) return '-'
    return new Intl.NumberFormat(locale === 'es' ? 'es-GQ' : locale, {
      style: 'currency',
      currency: 'XAF',
      minimumFractionDigits: 0,
    }).format(amount)
  }

  const formatDate = (dateString?: string): string => {
    if (!dateString) return '-'
    return new Date(dateString).toLocaleDateString(locale, {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
    })
  }

  const getWorkflowName = (code: string, fallbackEs?: string): string => {
    return tw(workflowNameKey(code), fallbackEs || code
      .split('_')
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
      .join(' '))
  }

  const getStatusLabel = (value: string): string => {
    const key = `status.${value.toLowerCase()}`
    try {
      const translated = t(key)
      if (translated && translated !== key) return translated
    } catch {
      // fallback
    }
    return value.replace(/_/g, ' ')
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">{t('title')}</h1>
          <p className="text-muted-foreground mt-2">{t('subtitle')}</p>
        </div>
        <Button asChild>
          <Link href={`/${locale}/dashboard/service-requests/new`}>
            <FilePlus className="mr-2 h-4 w-4" />
            {t('newRequest')}
          </Link>
        </Button>
      </div>

      {/* Quick Stats Cards */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card className="hover:shadow-lg transition-shadow cursor-pointer border-2 border-primary/20">
          <Link href={`/${locale}/dashboard/service-requests/new`}>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">{t('newRequest')}</CardTitle>
              <FilePlus className="h-6 w-6 text-primary" />
            </CardHeader>
            <CardContent>
              <p className="text-xs text-muted-foreground">
                {t('wizard.step_content_placeholder') || 'Iniciar una nueva solicitud de servicio'}
              </p>
            </CardContent>
          </Link>
        </Card>

        <Card className="hover:shadow-lg transition-shadow">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">{t('myRequests')}</CardTitle>
            <FileText className="h-6 w-6 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{pagination.total || 0}</div>
            <p className="text-xs text-muted-foreground">
              {t('page_of', { page: pagination.page, total: pagination.totalPages || 1 })}
            </p>
          </CardContent>
        </Card>

        <Card className="hover:shadow-lg transition-shadow cursor-pointer"
          onClick={() => handleStatusChange('DRAFT')}
        >
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">{t('filters.pending') || 'Pendientes'}</CardTitle>
            <Clock className="h-6 w-6 text-yellow-500" />
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              {locale === 'es' ? 'Clic para filtrar borradores' : locale === 'fr' ? 'Cliquer pour filtrer brouillons' : 'Click to filter drafts'}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Requests Table */}
      <Card>
        <CardHeader>
          <div className="flex flex-col gap-4">
            <div>
              <CardTitle>{t('allRequests') || 'Todas las Solicitudes'}</CardTitle>
              <CardDescription>
                {pagination.total > 0
                  ? (t('showing_of', {
                      start: (pagination.page - 1) * PAGE_SIZE + 1,
                      end: Math.min(pagination.page * PAGE_SIZE, pagination.total),
                      total: pagination.total,
                    }))
                  : (t('table.loading') || 'Historial de tus solicitudes de servicio')}
              </CardDescription>
            </div>

            {/* Filters Row */}
            <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
              {/* Search */}
              <div className="relative flex-1 sm:min-w-[200px] sm:max-w-[280px]">
                <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  type="search"
                  placeholder={t('search_placeholder') || 'Buscar...'}
                  className="pl-8"
                  value={searchQuery}
                  onChange={(e) => handleSearchChange(e.target.value)}
                />
              </div>

              {/* Category filter (dynamic from /filter-options) */}
              <Select value={filterCategory} onValueChange={handleCategoryChange} disabled={!filtersReady}>
                <SelectTrigger className="w-full sm:w-48">
                  <FileText className="h-4 w-4 mr-2" />
                  <SelectValue placeholder={!filtersReady
                    ? (locale === 'es' ? 'Cargando...' : 'Loading...')
                    : (locale === 'es' ? 'Categoría' : 'Category')
                  } />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">
                    {locale === 'es' ? 'Todas las categorías' : locale === 'fr' ? 'Toutes les catégories' : 'All categories'}
                  </SelectItem>
                  {filterOptions?.categories.map((c) => (
                    <SelectItem key={c.value} value={c.value}>
                      {c.label_es}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              {/* Workflow filter (conditional on category) */}
              {filteredWorkflows.length > 0 && (
                <Select value={filterWorkflow} onValueChange={handleWorkflowChange}>
                  <SelectTrigger className="w-full sm:w-52">
                    <FileText className="h-4 w-4 mr-2" />
                    <SelectValue placeholder={t('allTypes') || 'Tipo'} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">{t('allTypes') || 'Todos los tipos'}</SelectItem>
                    {filteredWorkflows.map((w) => (
                      <SelectItem key={w.workflowCode} value={w.workflowCode}>
                        {getWorkflowName(w.workflowCode, w.serviceNameEs)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}

              {/* Status filter (dynamic from /filter-options) */}
              <Select value={filterStatus} onValueChange={handleStatusChange} disabled={!filtersReady}>
                <SelectTrigger className="w-full sm:w-48">
                  <Filter className="h-4 w-4 mr-2" />
                  <SelectValue placeholder={!filtersReady
                    ? (locale === 'es' ? 'Cargando...' : 'Loading...')
                    : (t('filter_status') || 'Estado')
                  } />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t('allStatuses') || 'Todos los estados'}</SelectItem>
                  {filterOptions?.statuses.map((s) => (
                    <SelectItem key={s.value} value={s.value}>
                      {getStatusLabel(s.value)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {/* Bulk Actions Bar - Shows when items are selected */}
          {selectedIds.size > 0 && (
            <div className="mb-4 p-3 bg-primary/5 border border-primary/20 rounded-lg flex items-center justify-between">
              <div className="flex items-center gap-3">
                <span className="text-sm font-medium">
                  {selectedIds.size} {selectedIds.size === 1
                    ? (locale === 'es' ? 'seleccionado' : locale === 'fr' ? 'selectionne' : 'selected')
                    : (locale === 'es' ? 'seleccionados' : locale === 'fr' ? 'selectionnes' : 'selected')}
                </span>
                <Button variant="ghost" size="sm" onClick={clearSelection}>
                  {locale === 'es' ? 'Limpiar seleccion' : locale === 'fr' ? 'Effacer la selection' : 'Clear selection'}
                </Button>
              </div>
              <div className="flex items-center gap-2">
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="outline" size="sm">
                      <MoreHorizontal className="h-4 w-4 mr-2" />
                      {locale === 'es' ? 'Acciones' : locale === 'fr' ? 'Actions' : 'Actions'}
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem
                      className="text-destructive focus:text-destructive"
                      onClick={() => setBulkDeleteDialogOpen(true)}
                    >
                      <Trash2 className="h-4 w-4 mr-2" />
                      {locale === 'es'
                        ? `Eliminar ${selectedIds.size} solicitud(es)`
                        : locale === 'fr'
                          ? `Supprimer ${selectedIds.size} demande(s)`
                          : `Delete ${selectedIds.size} request(s)`}
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            </div>
          )}

          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[40px]">
                    <Checkbox
                      checked={isAllSelected}
                      onCheckedChange={handleSelectAll}
                      aria-label={locale === 'es' ? 'Seleccionar todo' : locale === 'fr' ? 'Tout selectionner' : 'Select all'}
                      disabled={selectableRequests.length === 0}
                      className={isSomeSelected && !isAllSelected ? 'data-[state=checked]:bg-primary/50' : ''}
                    />
                  </TableHead>
                  <TableHead>{t('request_number') || 'Referencia'}</TableHead>
                  <TableHead>{t('workflow') || 'Tipo'}</TableHead>
                  <TableHead>{t('created') || 'Fecha'}</TableHead>
                  <TableHead>{t('tariff') || 'Monto'}</TableHead>
                  <TableHead>{t('table.status') || 'Estado'}</TableHead>
                  <TableHead>{t('table.priority') || 'Progreso'}</TableHead>
                  <TableHead className="text-right">{t('table.actions') || 'Acciones'}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {isLoading ? (
                  <TableRow>
                    <TableCell colSpan={8} className="text-center py-8">
                      <div className="flex items-center justify-center gap-2 text-muted-foreground">
                        <Loader2 className="h-5 w-5 animate-spin" />
                        {t('loading')}
                      </div>
                    </TableCell>
                  </TableRow>
                ) : error ? (
                  <TableRow>
                    <TableCell colSpan={8} className="text-center py-8">
                      <div className="text-destructive">
                        <AlertCircle className="h-5 w-5 mx-auto mb-2" />
                        <p>{error}</p>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            clearError()
                            loadMyRequests(1, PAGE_SIZE)
                          }}
                          className="mt-2"
                        >
                          <RefreshCw className="mr-2 h-4 w-4" />
                          {t('retry')}
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ) : requests.length > 0 ? (
                  requests.map((req) => {
                    const progress = getProgress(req.status)
                    const isSelectable = req.status === 'DRAFT'
                    const isSelected = selectedIds.has(req.id)
                    return (
                      <TableRow key={req.id} className={isSelected ? 'bg-primary/5' : ''}>
                        <TableCell>
                          {isSelectable ? (
                            <Checkbox
                              checked={isSelected}
                              onCheckedChange={() => handleToggleSelect(req.id)}
                              aria-label={`${locale === 'es' ? 'Seleccionar' : 'Select'} ${req.requestNumber || req.id}`}
                            />
                          ) : (
                            <span className="w-4 h-4 block" />
                          )}
                        </TableCell>
                        <TableCell className="font-medium font-mono">
                          {req.requestNumber || req.id?.slice(0, 8)}
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <FileText className="h-4 w-4 text-muted-foreground" />
                            <span className="truncate max-w-[150px]">
                              {getWorkflowName(req.workflowCode)}
                            </span>
                          </div>
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-1 text-sm">
                            <Calendar className="h-3 w-3 text-muted-foreground" />
                            {formatDate(req.createdAt)}
                          </div>
                        </TableCell>
                        <TableCell className="font-semibold">
                          {formatAmount(req.tariffAmount)}
                        </TableCell>
                        <TableCell>{getStatusBadge(req.status)}</TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <div className="w-full bg-secondary rounded-full h-2 max-w-[80px]">
                              <div
                                className={`h-2 rounded-full transition-all ${
                                  progress === 100
                                    ? req.status === 'COMPLETED'
                                      ? 'bg-green-500'
                                      : 'bg-red-500'
                                    : 'bg-primary'
                                }`}
                                style={{ width: `${progress}%` }}
                              />
                            </div>
                            <span className="text-xs text-muted-foreground min-w-[35px]">
                              {progress}%
                            </span>
                          </div>
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex items-center justify-end gap-1">
                            <Button variant="ghost" size="icon" className="h-8 w-8" asChild title={t('view_details') || 'Ver'}>
                              <Link href={`/${locale}/dashboard/service-requests/${req.id}`}>
                                <Eye className="h-4 w-4" />
                              </Link>
                            </Button>
                            {canContinue(req.status) && (
                              <Button size="icon" className="h-8 w-8" asChild title={t('next') || 'Continuar'}>
                                <Link href={`/${locale}/dashboard/service-requests/${req.id}`}>
                                  <ArrowRight className="h-4 w-4" />
                                </Link>
                              </Button>
                            )}
                            {req.status === 'DRAFT' && (
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-8 w-8 text-destructive hover:text-destructive hover:bg-destructive/10"
                                title={t('delete') || 'Eliminar'}
                                onClick={() => handleDeleteClick(req.id, req.requestNumber || req.id?.slice(0, 8) || '')}
                              >
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            )}
                          </div>
                        </TableCell>
                      </TableRow>
                    )
                  })
                ) : (
                  <TableRow>
                    <TableCell colSpan={8} className="text-center py-12 text-muted-foreground">
                      <FileText className="h-12 w-12 mx-auto mb-4 opacity-50" />
                      <p className="text-lg font-medium mb-2">{t('no_requests_found') || 'No tienes solicitudes'}</p>
                      <p className="text-sm mb-4">
                        {t('wizard.step_content_placeholder') || 'Comienza creando tu primera solicitud de servicio'}
                      </p>
                      <Button asChild>
                        <Link href={`/${locale}/dashboard/service-requests/new`}>
                          <FilePlus className="mr-2 h-4 w-4" />
                          {t('newRequest')}
                        </Link>
                      </Button>
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>

          {/* Pagination */}
          {pagination.totalPages > 1 && (
            <div className="flex flex-col sm:flex-row items-center justify-between gap-4 mt-4">
              <p className="text-sm text-muted-foreground">
                {t('showing_of', {
                  start: (pagination.page - 1) * PAGE_SIZE + 1,
                  end: Math.min(pagination.page * PAGE_SIZE, pagination.total),
                  total: pagination.total,
                })}
              </p>
              <div className="flex items-center gap-1">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={pagination.page <= 1}
                  onClick={() => loadMyRequests(1, PAGE_SIZE)}
                  className="hidden sm:flex"
                >
                  {'<<'}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={pagination.page <= 1}
                  onClick={() => loadMyRequests(pagination.page - 1, PAGE_SIZE)}
                >
                  {t('previous')}
                </Button>

                {/* Page Numbers */}
                <div className="flex items-center gap-1">
                  {(() => {
                    const pages: (number | string)[] = []
                    const current = pagination.page
                    const total = pagination.totalPages

                    pages.push(1)

                    if (current > 3) {
                      pages.push('...')
                    }

                    for (let i = Math.max(2, current - 1); i <= Math.min(total - 1, current + 1); i++) {
                      if (!pages.includes(i)) {
                        pages.push(i)
                      }
                    }

                    if (current < total - 2) {
                      pages.push('...')
                    }

                    if (total > 1 && !pages.includes(total)) {
                      pages.push(total)
                    }

                    return pages.map((page, idx) => (
                      typeof page === 'string' ? (
                        <span key={`ellipsis-${idx}`} className="px-2 text-muted-foreground">
                          {page}
                        </span>
                      ) : (
                        <Button
                          key={page}
                          variant={page === current ? 'default' : 'outline'}
                          size="sm"
                          className="min-w-[36px]"
                          onClick={() => loadMyRequests(page, PAGE_SIZE)}
                        >
                          {page}
                        </Button>
                      )
                    ))
                  })()}
                </div>

                <Button
                  variant="outline"
                  size="sm"
                  disabled={pagination.page >= pagination.totalPages}
                  onClick={() => loadMyRequests(pagination.page + 1, PAGE_SIZE)}
                >
                  {t('next')}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={pagination.page >= pagination.totalPages}
                  onClick={() => loadMyRequests(pagination.totalPages, PAGE_SIZE)}
                  className="hidden sm:flex"
                >
                  {'>>'}
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Delete Confirmation Dialog (Single) */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {locale === 'es'
                ? 'Eliminar Solicitud'
                : locale === 'fr'
                  ? 'Supprimer la Demande'
                  : 'Delete Request'}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {locale === 'es'
                ? `Esta seguro de que desea eliminar la solicitud ${requestToDelete?.reference}? Esta accion no se puede deshacer.`
                : locale === 'fr'
                  ? `Etes-vous sur de vouloir supprimer la demande ${requestToDelete?.reference} ? Cette action est irreversible.`
                  : `Are you sure you want to delete request ${requestToDelete?.reference}? This action cannot be undone.`}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={handleDeleteCancel} disabled={isDeleting}>
              {locale === 'es' ? 'Cancelar' : locale === 'fr' ? 'Annuler' : 'Cancel'}
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteConfirm}
              disabled={isDeleting}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {isDeleting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  {locale === 'es' ? 'Eliminando...' : locale === 'fr' ? 'Suppression...' : 'Deleting...'}
                </>
              ) : (
                <>
                  <Trash2 className="mr-2 h-4 w-4" />
                  {locale === 'es' ? 'Eliminar' : locale === 'fr' ? 'Supprimer' : 'Delete'}
                </>
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Bulk Delete Confirmation Dialog */}
      <AlertDialog open={bulkDeleteDialogOpen} onOpenChange={setBulkDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {locale === 'es'
                ? 'Eliminar Solicitudes Seleccionadas'
                : locale === 'fr'
                  ? 'Supprimer les Demandes Selectionnees'
                  : 'Delete Selected Requests'}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {locale === 'es'
                ? `Esta seguro de que desea eliminar ${selectedIds.size} solicitud(es)? Esta accion no se puede deshacer.`
                : locale === 'fr'
                  ? `Etes-vous sur de vouloir supprimer ${selectedIds.size} demande(s) ? Cette action est irreversible.`
                  : `Are you sure you want to delete ${selectedIds.size} request(s)? This action cannot be undone.`}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={handleBulkDeleteCancel} disabled={isBulkDeleting}>
              {locale === 'es' ? 'Cancelar' : locale === 'fr' ? 'Annuler' : 'Cancel'}
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={handleBulkDeleteConfirm}
              disabled={isBulkDeleting}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {isBulkDeleting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  {locale === 'es' ? 'Eliminando...' : locale === 'fr' ? 'Suppression...' : 'Deleting...'}
                </>
              ) : (
                <>
                  <Trash2 className="mr-2 h-4 w-4" />
                  {locale === 'es'
                    ? `Eliminar ${selectedIds.size} solicitud(es)`
                    : locale === 'fr'
                      ? `Supprimer ${selectedIds.size} demande(s)`
                      : `Delete ${selectedIds.size} request(s)`}
                </>
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
