'use client'

/**
 * OMS Agent Dashboard — Obligations processing queue
 *
 * Full agent workflow: view queue, process/reject with notes,
 * mark paid manually, view obligation detail panel, events timeline,
 * batch operations, filter by status + fee_type.
 */

import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  ClipboardList, Clock, CheckCircle2, Search,
  ChevronLeft, ChevronRight, ChevronDown, RefreshCw, XCircle, DollarSign,
  Building2, FileCheck, Eye, History, AlertTriangle,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { Textarea } from '@/components/ui/textarea'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table'
import {
  Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription,
} from '@/components/ui/sheet'
import { useToast } from '@/hooks/use-toast'
import { omsQueueApi } from '@/modules/oms/services/api'
import type { AgentQueueItem, AgentQueueStats, ComplianceEvent } from '@/modules/oms/types'

import { useTranslations } from 'next-intl'
import { useLocale } from 'next-intl'
import { exportToExcel } from '@/core/utils/export'
import { OBLIGATION_STATUS_CONFIG as STATUS_CONFIG, fmtXAF } from '@/modules/oms/utils/formatters'

export default function OMSAgentDashboardPage() {
  const { toast } = useToast()
  const t = useTranslations('oms')
  const locale = useLocale()

  const [stats, setStats] = useState<AgentQueueStats | null>(null)
  const [queue, setQueue] = useState<{ items: AgentQueueItem[]; total: number } | null>(null)
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState('all')
  const [feeTypeFilter, setFeeTypeFilter] = useState('all')
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [processing, setProcessing] = useState(false)
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set())

  // Detail panel
  const [detailItem, setDetailItem] = useState<AgentQueueItem | null>(null)
  const [detailEvents, setDetailEvents] = useState<ComplianceEvent[]>([])
  const [processNotes, setProcessNotes] = useState('')

  const debounceRef = useRef<NodeJS.Timeout>()
  const seqRef = useRef(0)
  const PAGE_SIZE = 20

  // Debounced search — sends to backend server-side
  const [searchInput, setSearchInput] = useState('')
  const [search, setSearch] = useState('')
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => { setSearch(searchInput); setPage(1) }, 300)
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current) }
  }, [searchInput])

  const fetchAll = useCallback(async () => {
    const seq = ++seqRef.current
    setLoading(true)
    try {
      const [s, q] = await Promise.all([
        omsQueueApi.getStats(),
        omsQueueApi.getQueue({
          status: statusFilter === 'all' ? undefined : statusFilter,
          fee_type: feeTypeFilter === 'all' ? undefined : feeTypeFilter,
          search: search || undefined,
          page,
          page_size: PAGE_SIZE,
        }),
      ])
      if (seq === seqRef.current) { setStats(s); setQueue(q) }
    } catch {
      if (seq === seqRef.current) toast({ title: t('queue.loadError'), variant: 'destructive' })
    } finally {
      if (seq === seqRef.current) setLoading(false)
    }
  }, [page, statusFilter, feeTypeFilter, search, toast, t])

  useEffect(() => { fetchAll() }, [fetchAll])

  // Items are already server-side filtered — no client-side filtering needed
  const filteredItems = queue?.items ?? []

  // Group by license (company) for compact display — agents process per company
  const groupedItems = useMemo(() => {
    const groups: { key: string; company: string; reg: string; zone: string; items: AgentQueueItem[]; totalAmount: number }[] = []
    const map = new Map<string, typeof groups[0]>()
    for (const item of filteredItems) {
      const key = item.license_id || item.id
      let group = map.get(key)
      if (!group) {
        group = {
          key,
          company: item.company_name || '—',
          reg: item.company_registration_number || item.company_nif || '',
          zone: item.zone_code || '',
          items: [],
          totalAmount: 0,
        }
        map.set(key, group)
        groups.push(group)
      }
      group.items.push(item)
      group.totalAmount += Number(item.amount || 0) + Number(item.penalty_amount || 0)
    }
    return groups
  }, [filteredItems])

  const totalPages = queue ? Math.ceil(queue.total / PAGE_SIZE) : 0

  // Selection
  const allSelected = filteredItems.length > 0 && filteredItems.every(i => selected.has(i.id))
  const toggleSelectAll = () => {
    const next = new Set(selected)
    if (allSelected) filteredItems.forEach(i => next.delete(i.id))
    else filteredItems.forEach(i => next.add(i.id))
    setSelected(next)
  }

  // ========== ACTIONS ==========

  const handleProcess = async (id: string, notes?: string) => {
    // If called from table row (no notes), prompt for optional notes
    const finalNotes = notes ?? window.prompt(t('queue.notesPlaceholder')) ?? undefined
    try {
      await omsQueueApi.processObligation(id, { notes: finalNotes || undefined })
      toast({ title: t('queue.processed') })
      setDetailItem(null)
      setProcessNotes('')
      fetchAll()
    } catch {
      toast({ title: t('queue.error'), variant: 'destructive' })
    }
  }

  const handleReject = async (id: string) => {
    const reason = window.prompt(t('queue.rejectReason'))
    if (!reason || reason.length < 5) return
    try {
      await omsQueueApi.rejectObligation(id, { reason })
      toast({ title: t('queue.rejected') })
      setDetailItem(null)
      fetchAll()
    } catch {
      toast({ title: t('queue.error'), variant: 'destructive' })
    }
  }

  const handleEscalate = async (item: AgentQueueItem) => {
    const reason = window.prompt(t('queue.escalateReason', { defaultValue: 'Motivo de la escalación (min 10 caracteres):' }))
    if (!reason || reason.length < 10) return
    // Escalate the service_request linked to this obligation's license
    try {
      const { default: apiClient } = await import('@/core/api/client')
      // Find the SR from the obligation's license
      const licenseData = await apiClient.get(`/licenses/${item.license_id}`).then(r => r.data)
      const srId = licenseData?.service_request_id
      if (!srId) {
        toast({ title: t('queue.error'), variant: 'destructive' })
        return
      }
      await apiClient.post(`/agent/requests/${srId}/escalate`, {
        reason,
        level: 'medium',
      })
      toast({ title: t('queue.escalated', { defaultValue: 'Escalada enviada al supervisor' }) })
      fetchAll()
    } catch {
      toast({ title: t('queue.error'), variant: 'destructive' })
    }
  }

  const handleBatchProcess = async () => {
    if (selected.size === 0) return
    if (!window.confirm(t('queue.batchConfirm', { count: selected.size }))) return
    setProcessing(true)
    try {
      await omsQueueApi.batchProcess(Array.from(selected))
      toast({ title: `${selected.size} ${t('queue.batchProcessed')}` })
      setSelected(new Set())
      fetchAll()
    } catch {
      toast({ title: t('queue.error'), variant: 'destructive' })
    } finally {
      setProcessing(false)
    }
  }

  // Open detail panel — fetch obligation detail + all events
  const openDetail = async (item: AgentQueueItem) => {
    setDetailItem(item)
    setProcessNotes('')
    try {
      // Fetch full obligation detail (enriched with all fields from backend)
      const [detail, evts] = await Promise.all([
        omsQueueApi.getObligation(item.id).catch(() => null),
        omsQueueApi.getObligationEvents(item.id),
      ])
      // Merge detail fields into item if available
      if (detail) {
        setDetailItem({ ...item, ...detail })
      }
      setDetailEvents(evts.items ?? [])
    } catch {
      setDetailEvents([])
    }
  }

  return (
    <div className="space-y-4 p-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold flex items-center gap-2">
            <ClipboardList className="h-5 w-5" />
            {t('queue.title')}
          </h1>
          <p className="text-sm text-muted-foreground">{t('queue.subtitle')}</p>
        </div>
        <div className="flex gap-1">
        <Button variant="outline" size="sm" onClick={() => {
          if (!queue?.items?.length) return
          exportToExcel(queue.items.map(i => ({
            Empresa: i.company_name || '',
            NIF: i.company_nif || i.company_registration_number || '',
            Servicio: i.service_name || '',
            Tipo: i.fee_type || '',
            Entidad: i.ministry_name || i.fee_type || '',
            Monto: i.amount,
            Penalidad: i.penalty_amount || 0,
            Vencimiento: i.due_date || '',
            Estado: i.status,
          })), { fileName: `obligaciones_oms_${new Date().toISOString().slice(0,10)}`, sheetName: 'Obligaciones' })
        }} disabled={!queue?.items?.length}>
          <FileCheck className="h-3.5 w-3.5 mr-1" /> Excel
        </Button>
        <Button variant="outline" size="sm" onClick={fetchAll} disabled={loading}>
          <RefreshCw className={`h-3.5 w-3.5 mr-1 ${loading ? 'animate-spin' : ''}`} />
        </Button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {loading && !stats ? (
          Array.from({ length: 4 }).map((_, i) => (
            <Card key={i} className="p-3"><Skeleton className="h-14 w-full" /></Card>
          ))
        ) : stats ? (<>
          <Card className="p-3">
            <div className="flex items-center gap-2">
              <Clock className="h-5 w-5 text-yellow-500" />
              <div>
                <p className="text-xs text-muted-foreground">{t('queue.pending')}</p>
                <p className="text-2xl font-bold">{stats.pending_count}</p>
              </div>
            </div>
          </Card>
          <Card className="p-3">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-5 w-5 text-green-500" />
              <div>
                <p className="text-xs text-muted-foreground">{t('queue.completedToday')}</p>
                <p className="text-2xl font-bold">{stats.completed_today}</p>
              </div>
            </div>
          </Card>
          <Card className="p-3">
            <div className="flex items-center gap-2">
              <DollarSign className="h-5 w-5 text-amber-500" />
              <div>
                <p className="text-xs text-muted-foreground">{t('queue.pendingAmount')}</p>
                <p className="text-lg font-bold">{fmtXAF(stats.total_amount_pending, locale)}</p>
              </div>
            </div>
          </Card>
          <Card className="p-3">
            <div className="flex items-center gap-2">
              <FileCheck className="h-5 w-5 text-blue-500" />
              <div>
                <p className="text-xs text-muted-foreground">{t('queue.processedToday')}</p>
                <p className="text-lg font-bold">{fmtXAF(stats.total_amount_completed_today, locale)}</p>
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
            placeholder={t('queue.searchPlaceholder')} className="pl-8 h-8 text-xs" />
        </div>
        <Select value={statusFilter} onValueChange={v => { setStatusFilter(v); setPage(1) }}>
          <SelectTrigger className="w-[120px] h-8 text-xs"><SelectValue placeholder={t('queue.status')} /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t('queue.allStatuses')}</SelectItem>
            <SelectItem value="processing">{t('queue.processing')}</SelectItem>
            <SelectItem value="paid">{t('queue.paid')}</SelectItem>
            <SelectItem value="completed">{t('queue.completed')}</SelectItem>
          </SelectContent>
        </Select>
        <Select value={feeTypeFilter} onValueChange={v => { setFeeTypeFilter(v); setPage(1) }}>
          <SelectTrigger className="w-[120px] h-8 text-xs"><SelectValue placeholder={t('queue.allFeeTypes')} /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t('queue.allFeeTypes')}</SelectItem>
            <SelectItem value="tesoro">{t('queue.feeTypeTesoro', { defaultValue: 'Tesoro' })}</SelectItem>
            <SelectItem value="municipal">{t('queue.feeTypeMunicipal', { defaultValue: 'Municipal' })}</SelectItem>
            <SelectItem value="chamber">{t('queue.feeTypeChamber', { defaultValue: 'Cámara' })}</SelectItem>
          </SelectContent>
        </Select>
        <span className="text-xs text-muted-foreground self-center">{filteredItems.length}/{queue?.total ?? 0}</span>
      </div>

      {/* Bulk action bar — shows payment verification status */}
      {selected.size > 0 && (() => {
        const selectedItems = filteredItems.filter(i => selected.has(i.id))
        const allPaid = selectedItems.every(i => i.status === 'paid' || i.status === 'processing')
        const totalSelected = selectedItems.reduce((sum, i) => sum + Number(i.amount || 0), 0)
        return (
          <div className="flex items-center gap-2 p-2 bg-blue-50 border border-blue-200 rounded-lg">
            <span className="text-xs font-medium text-blue-700">{selected.size} {t('queue.selected')}</span>
            <span className="text-[10px] text-muted-foreground font-mono">{fmtXAF(totalSelected, locale)}</span>
            {allPaid && (
              <span className="flex items-center gap-0.5 text-[10px] text-green-700">
                <DollarSign className="h-3 w-3" />{t('queue.allPaidVerified', { defaultValue: 'Pago verificado' })}
              </span>
            )}
            <Button size="sm" variant="outline" className="h-7 text-xs gap-1 ml-auto"
              onClick={handleBatchProcess} disabled={processing}>
              <CheckCircle2 className="h-3 w-3" /> {t('queue.batchProcess')}
            </Button>
            <Button size="sm" variant="ghost" className="h-7 text-xs" onClick={() => setSelected(new Set())}>
              {t('queue.cancel')}
            </Button>
          </div>
        )
      })()}

      {/* Queue Table — grouped by license (company) */}
      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[40px]">
                  <Checkbox checked={allSelected && filteredItems.length > 0} onCheckedChange={toggleSelectAll} />
                </TableHead>
                <TableHead className="text-xs">{t('queue.company')}</TableHead>
                <TableHead className="text-xs w-[110px] text-right">{t('queue.amount')}</TableHead>
                <TableHead className="text-xs w-[95px]">{t('queue.dueDate')}</TableHead>
                <TableHead className="text-xs w-[95px]">{t('queue.status')}</TableHead>
                <TableHead className="text-xs w-[120px]">{t('queue.actions')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                <TableRow><TableCell colSpan={6} className="text-center py-8 text-muted-foreground">...</TableCell></TableRow>
              ) : groupedItems.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-12 text-muted-foreground">
                    <ClipboardList className="h-8 w-8 mx-auto mb-2 opacity-30" />
                    <p>{t('queue.noObligations')}</p>
                  </TableCell>
                </TableRow>
              ) : groupedItems.map(group => {
                const groupAllSelected = group.items.every(i => selected.has(i.id))
                const isSingle = group.items.length === 1

                // Single obligation: flat row (no collapse, no header/sub-row split)
                if (isSingle) {
                  const item = group.items[0]
                  const cfg = STATUS_CONFIG[item.status] || STATUS_CONFIG.pending
                  return (
                    <TableRow key={group.key} className="hover:bg-muted/30">
                      <TableCell>
                        <Checkbox checked={selected.has(item.id)}
                          onCheckedChange={() => {
                            const next = new Set(selected)
                            next.has(item.id) ? next.delete(item.id) : next.add(item.id)
                            setSelected(next)
                          }} />
                      </TableCell>
                      <TableCell className="text-xs">
                        <div className="flex items-center gap-1.5">
                          <Building2 className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                          <span className="font-medium truncate">{group.company}</span>
                          <span className="text-[10px] text-muted-foreground font-mono">{group.reg}</span>
                          {group.zone && <Badge variant="secondary" className="text-[10px] h-4 px-1">{group.zone}</Badge>}
                        </div>
                        <p className="text-[10px] text-muted-foreground pl-5 mt-0.5">{item.service_name || '—'}</p>
                      </TableCell>
                      <TableCell className="text-xs text-right font-mono font-bold">
                        {fmtXAF(Number(item.amount), locale)}
                        {Number(item.penalty_amount) > 0 && (
                          <span className="block text-[10px] text-red-500">+{fmtXAF(Number(item.penalty_amount), locale)}</span>
                        )}
                      </TableCell>
                      <TableCell className="text-xs">{item.due_date || '—'}</TableCell>
                      <TableCell>
                        <Badge className={`text-[10px] gap-1 ${cfg.color}`}>
                          <cfg.icon className="h-3 w-3" />{t(cfg.labelKey, { defaultValue: cfg.label })}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex gap-0.5">
                          <Button variant="ghost" size="icon" className="h-7 w-7" title={t('queue.viewDetail')}
                            onClick={() => openDetail(item)}>
                            <Eye className="h-3.5 w-3.5" />
                          </Button>
                          <Button variant="ghost" size="icon" className="h-7 w-7" title={t('queue.process')}
                            onClick={() => handleProcess(item.id)}>
                            <CheckCircle2 className="h-3.5 w-3.5 text-green-600" />
                          </Button>
                          <Button variant="ghost" size="icon" className="h-7 w-7" title={t('queue.reject')}
                            onClick={() => handleReject(item.id)}>
                            <XCircle className="h-3.5 w-3.5 text-red-500" />
                          </Button>
                          <Button variant="ghost" size="icon" className="h-7 w-7" title={t('queue.escalate', { defaultValue: 'Escalar' })}
                            onClick={() => openDetail(item)}>
                            <AlertTriangle className="h-3.5 w-3.5 text-amber-500" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  )
                }

                // Multiple obligations: collapsible group
                const isCollapsed = collapsedGroups.has(group.key)
                const toggleCollapse = () => {
                  const next = new Set(collapsedGroups)
                  next.has(group.key) ? next.delete(group.key) : next.add(group.key)
                  setCollapsedGroups(next)
                }
                const toggleGroupSelect = () => {
                  const next = new Set(selected)
                  if (groupAllSelected) group.items.forEach(i => next.delete(i.id))
                  else group.items.forEach(i => next.add(i.id))
                  setSelected(next)
                }
                return (
                  <Fragment key={group.key}>
                    {/* Company header row — clickable collapse */}
                    <TableRow className="bg-muted/30 hover:bg-muted/50 cursor-pointer" onClick={toggleCollapse}>
                      <TableCell onClick={e => e.stopPropagation()}>
                        <Checkbox checked={groupAllSelected} onCheckedChange={toggleGroupSelect} />
                      </TableCell>
                      <TableCell className="text-xs font-medium">
                        <div className="flex items-center gap-1.5">
                          {isCollapsed ? <ChevronRight className="h-3.5 w-3.5 text-muted-foreground shrink-0" /> : <ChevronDown className="h-3.5 w-3.5 text-muted-foreground shrink-0" />}
                          <Building2 className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                          <span className="truncate">{group.company}</span>
                          <span className="text-[10px] text-muted-foreground font-mono">{group.reg}</span>
                          {group.zone && <Badge variant="secondary" className="text-[10px] h-4 px-1">{group.zone}</Badge>}
                        </div>
                      </TableCell>
                      <TableCell className="text-xs text-right font-mono font-bold">
                        {fmtXAF(group.totalAmount, locale)}
                      </TableCell>
                      <TableCell />
                      <TableCell className="text-xs text-muted-foreground">
                        {group.items.length} obl.
                      </TableCell>
                      <TableCell onClick={e => e.stopPropagation()}>
                        <Button variant="ghost" size="sm" className="h-6 text-[10px] gap-1"
                          onClick={() => {
                            const next = new Set(selected)
                            group.items.forEach(it => next.add(it.id))
                            setSelected(next)
                          }}>
                          <CheckCircle2 className="h-3 w-3" /> {t('queue.batchProcess')}
                        </Button>
                      </TableCell>
                    </TableRow>
                    {/* Obligation sub-rows — collapsible */}
                    {!isCollapsed && group.items.map(item => {
                      const cfg = STATUS_CONFIG[item.status] || STATUS_CONFIG.pending
                      return (
                        <TableRow key={item.id} className="border-l-2 border-l-muted">
                          <TableCell onClick={e => e.stopPropagation()}>
                            <Checkbox checked={selected.has(item.id)}
                              onCheckedChange={() => {
                                const next = new Set(selected)
                                next.has(item.id) ? next.delete(item.id) : next.add(item.id)
                                setSelected(next)
                              }} />
                          </TableCell>
                          <TableCell className="text-xs pl-10 text-muted-foreground">
                            {item.service_name || '—'}
                          </TableCell>
                          <TableCell className="text-xs text-right font-mono">
                            {fmtXAF(Number(item.amount), locale)}
                            {Number(item.penalty_amount) > 0 && (
                              <span className="block text-[10px] text-red-500">+{fmtXAF(Number(item.penalty_amount), locale)}</span>
                            )}
                          </TableCell>
                          <TableCell className="text-xs">{item.due_date || '—'}</TableCell>
                          <TableCell>
                            <Badge className={`text-[10px] gap-1 ${cfg.color}`}>
                              <cfg.icon className="h-3 w-3" />{t(cfg.labelKey, { defaultValue: cfg.label })}
                            </Badge>
                          </TableCell>
                          <TableCell>
                            <div className="flex gap-0.5">
                              <Button variant="ghost" size="icon" className="h-7 w-7" title={t('queue.viewDetail')}
                                onClick={() => openDetail(item)}>
                                <Eye className="h-3.5 w-3.5" />
                              </Button>
                              <Button variant="ghost" size="icon" className="h-7 w-7" title={t('queue.process')}
                                onClick={() => handleProcess(item.id)}>
                                <CheckCircle2 className="h-3.5 w-3.5 text-green-600" />
                              </Button>
                              <Button variant="ghost" size="icon" className="h-7 w-7" title={t('queue.reject')}
                                onClick={() => handleReject(item.id)}>
                                <XCircle className="h-3.5 w-3.5 text-red-500" />
                              </Button>
                              <Button variant="ghost" size="icon" className="h-7 w-7" title={t('queue.escalate', { defaultValue: 'Escalar' })}
                                onClick={() => handleEscalate(item)}>
                                <AlertTriangle className="h-3.5 w-3.5 text-amber-500" />
                              </Button>
                            </div>
                          </TableCell>
                        </TableRow>
                      )
                    })}
                  </Fragment>
                )
              })}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground text-xs">{page}/{totalPages}</span>
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

      {/* ========== DETAIL PANEL (Sheet) ========== */}
      <Sheet open={!!detailItem} onOpenChange={open => { if (!open) setDetailItem(null) }}>
        <SheetContent side="right" className="w-[400px] sm:w-[480px] overflow-y-auto">
          {detailItem && (
            <>
              <SheetHeader>
                <SheetTitle className="flex items-center gap-2">
                  <Building2 className="h-4 w-4" />
                  {detailItem.company_name || 'Obligación'}
                </SheetTitle>
                <SheetDescription>
                  {detailItem.fee_type} · {detailItem.service_name || 'Servicio'} · {detailItem.zone_code || ''}
                </SheetDescription>
              </SheetHeader>

              <div className="space-y-4 mt-4">
                {/* Detail fields */}
                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div><span className="text-muted-foreground">{t('queue.amount')}:</span><br/><strong className="text-base">{fmtXAF(detailItem.amount, locale)}</strong></div>
                  <div><span className="text-muted-foreground">{t('queue.penalty')}:</span><br/><strong className={`text-base ${detailItem.penalty_amount > 0 ? 'text-red-700' : ''}`}>{fmtXAF(detailItem.penalty_amount, locale)}</strong></div>
                  <div><span className="text-muted-foreground">{t('queue.dueDate')}:</span><br/><strong>{detailItem.due_date || 'N/A'}</strong></div>
                  <div><span className="text-muted-foreground">{t('queue.status')}:</span><br/>
                    <Badge className={`text-xs ${(STATUS_CONFIG[detailItem.status] || STATUS_CONFIG.pending).color}`}>
                      {(STATUS_CONFIG[detailItem.status] || STATUS_CONFIG.pending).label}
                    </Badge>
                  </div>
                  <div><span className="text-muted-foreground">{t('queue.feeType')}:</span><br/><strong>{detailItem.fiscal_year || 'N/A'}</strong></div>
                  <div><span className="text-muted-foreground">{t('queue.company')}:</span><br/><strong className="text-[11px]">{detailItem.ministry_name || 'N/A'}</strong></div>
                </div>

                {/* Notes + Process */}
                <div className="space-y-2 p-3 bg-muted/30 rounded-lg border">
                  <p className="text-xs font-medium">{t('queue.processWithNotes')}:</p>
                  <Textarea
                    value={processNotes}
                    onChange={e => setProcessNotes(e.target.value)}
                    placeholder={t('queue.notesPlaceholder')}
                    className="text-xs h-20 resize-none"
                  />
                  <div className="flex gap-2">
                    <Button size="sm" className="flex-1 h-8 text-xs gap-1"
                      onClick={() => handleProcess(detailItem.id, processNotes)}>
                      <CheckCircle2 className="h-3.5 w-3.5" /> {t('queue.process')}
                    </Button>
                    <Button size="sm" variant="destructive" className="h-8 text-xs gap-1"
                      onClick={() => handleReject(detailItem.id)}>
                      <XCircle className="h-3.5 w-3.5" /> {t('queue.reject')}
                    </Button>
                    <Button size="sm" variant="outline" className="h-8 text-xs gap-1 text-amber-600 border-amber-300"
                      onClick={() => handleEscalate(detailItem)}>
                      <AlertTriangle className="h-3.5 w-3.5" /> {t('queue.escalate', { defaultValue: 'Escalar' })}
                    </Button>
                  </div>
                </div>

                {/* Events timeline */}
                <div>
                  <p className="text-xs font-medium flex items-center gap-1 mb-2">
                    <History className="h-3.5 w-3.5" /> {t('queue.history')} ({detailEvents.length})
                  </p>
                  {detailEvents.length === 0 ? (
                    <p className="text-[10px] text-muted-foreground">{t('queue.noEvents')}</p>
                  ) : (
                    <div className="relative pl-5 space-y-2">
                      <div className="absolute left-[7px] top-1 bottom-1 w-px bg-gray-200" />
                      {detailEvents.map(evt => (
                        <div key={evt.id} className="relative">
                          <div className={`absolute -left-5 top-1 h-3 w-3 rounded-full border-2 ${
                            evt.event_type.includes('PAID') || evt.event_type.includes('COMPLETED') ? 'border-green-500 bg-green-100' :
                            evt.event_type.includes('OVERDUE') ? 'border-red-500 bg-red-100' :
                            'border-gray-400 bg-gray-100'
                          }`} />
                          <div className="text-[10px]">
                            <Badge variant="outline" className="text-[9px] font-mono">{evt.event_type}</Badge>
                            <span className="text-muted-foreground ml-1">
                              {new Date(evt.created_at).toLocaleDateString(locale, { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </>
          )}
        </SheetContent>
      </Sheet>
    </div>
  )
}
