'use client'

/**
 * OMS Queue — Completed obligations (history view)
 *
 * Pre-filters the OMS queue to show only completed obligations.
 * Gives agents a dedicated view to review their past work without
 * needing to toggle the filter dropdown on the main queue page.
 *
 * @route /[locale]/dashboard/agent/oms/queue/completed
 */

import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  ClipboardList, CheckCircle2, Search,
  ChevronLeft, ChevronRight, Building2, RefreshCw, Eye,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table'
import {
  Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription,
} from '@/components/ui/sheet'
import { useToast } from '@/hooks/use-toast'
import { omsQueueApi } from '@/modules/oms/services/api'
import type { AgentQueueItem, ComplianceEvent } from '@/modules/oms/types'

import { useTranslations } from 'next-intl'
import { useLocale } from 'next-intl'
import { OBLIGATION_STATUS_CONFIG as STATUS_CONFIG, fmtXAF } from '@/modules/oms/utils/formatters'

export default function OMSQueueCompletedPage() {
  const { toast } = useToast()
  const t = useTranslations('oms')
  const locale = useLocale()

  const [queue, setQueue] = useState<{ items: AgentQueueItem[]; total: number } | null>(null)
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const PAGE_SIZE = 20

  const debounceRef = useRef<NodeJS.Timeout>()
  const seqRef = useRef(0)
  const [searchInput, setSearchInput] = useState('')
  const [search, setSearch] = useState('')
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => { setSearch(searchInput); setPage(1) }, 300)
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current) }
  }, [searchInput])

  // Detail panel
  const [detailItem, setDetailItem] = useState<AgentQueueItem | null>(null)
  const [detailEvents, setDetailEvents] = useState<ComplianceEvent[]>([])

  const fetchAll = useCallback(async () => {
    const seq = ++seqRef.current
    setLoading(true)
    try {
      const q = await omsQueueApi.getQueue({
        status: 'completed',
        search: search || undefined,
        page,
        page_size: PAGE_SIZE,
      })
      if (seq === seqRef.current) setQueue(q)
    } catch {
      if (seq === seqRef.current) toast({ title: t('queue.loadError'), variant: 'destructive' })
    } finally {
      if (seq === seqRef.current) setLoading(false)
    }
  }, [page, search, toast, t])

  useEffect(() => { fetchAll() }, [fetchAll])

  const items = queue?.items ?? []
  const totalPages = queue ? Math.ceil(queue.total / PAGE_SIZE) : 0

  // Group by license (same pattern as main queue)
  const groupedItems = useMemo(() => {
    const groups: { key: string; company: string; reg: string; zone: string; items: AgentQueueItem[]; totalAmount: number }[] = []
    const map = new Map<string, typeof groups[0]>()
    for (const item of items) {
      const key = item.license_id || item.id
      let group = map.get(key)
      if (!group) {
        group = { key, company: item.company_name || '—', reg: item.company_registration_number || item.company_nif || '', zone: item.zone_code || '', items: [], totalAmount: 0 }
        map.set(key, group)
        groups.push(group)
      }
      group.items.push(item)
      group.totalAmount += Number(item.amount || 0) + Number(item.penalty_amount || 0)
    }
    return groups
  }, [items])

  const openDetail = async (item: AgentQueueItem) => {
    setDetailItem(item)
    try {
      const [detail, evts] = await Promise.all([
        omsQueueApi.getObligation(item.id).catch(() => null),
        omsQueueApi.getObligationEvents(item.id),
      ])
      if (detail) setDetailItem({ ...item, ...detail })
      setDetailEvents(evts.items ?? [])
    } catch { setDetailEvents([]) }
  }

  return (
    <div className="space-y-4 p-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold flex items-center gap-2">
            <CheckCircle2 className="h-5 w-5 text-green-600" />
            {t('queue.completedTitle', { defaultValue: t('queue.completed') })}
          </h1>
          <p className="text-sm text-muted-foreground">{t('queue.completedSubtitle', { defaultValue: '' })}</p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="secondary" className="text-xs">{queue?.total ?? 0} {t('queue.total', { defaultValue: 'total' })}</Badge>
          <Button variant="outline" size="sm" onClick={fetchAll} disabled={loading}>
            <RefreshCw className={`h-3.5 w-3.5 mr-1 ${loading ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </div>

      {/* Search */}
      <div className="relative max-w-sm">
        <Search className="absolute left-2.5 top-2 h-3.5 w-3.5 text-muted-foreground" />
        <Input value={searchInput} onChange={e => setSearchInput(e.target.value)}
          placeholder={t('queue.searchPlaceholder')} className="pl-8 h-8 text-xs" />
      </div>

      {/* Table */}
      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="text-xs">{t('queue.company')}</TableHead>
                <TableHead className="text-xs w-[110px] text-right">{t('queue.amount')}</TableHead>
                <TableHead className="text-xs w-[95px]">{t('queue.dueDate')}</TableHead>
                <TableHead className="text-xs w-[95px]">{t('queue.status')}</TableHead>
                <TableHead className="text-xs w-[60px]" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                <TableRow><TableCell colSpan={5} className="text-center py-8">...</TableCell></TableRow>
              ) : groupedItems.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} className="text-center py-12 text-muted-foreground">
                    <ClipboardList className="h-8 w-8 mx-auto mb-2 opacity-30" />
                    <p>{t('queue.noObligations')}</p>
                  </TableCell>
                </TableRow>
              ) : groupedItems.map(group => (
                <Fragment key={group.key}>
                  {group.items.map((item, idx) => {
                    const cfg = STATUS_CONFIG[item.status] || STATUS_CONFIG.completed
                    return (
                      <TableRow key={item.id}>
                        <TableCell className="text-xs">
                          {idx === 0 && (
                            <div className="flex items-center gap-1.5 font-medium">
                              <Building2 className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                              <span className="truncate">{group.company}</span>
                              <span className="text-[10px] text-muted-foreground font-mono">{group.reg}</span>
                              {group.zone && <Badge variant="secondary" className="text-[10px] h-4 px-1">{group.zone}</Badge>}
                            </div>
                          )}
                          <p className={`text-[10px] text-muted-foreground ${idx === 0 ? 'mt-0.5 pl-5' : 'pl-5'}`}>{item.service_name || '—'}</p>
                        </TableCell>
                        <TableCell className="text-xs text-right font-mono">{fmtXAF(Number(item.amount), locale)}</TableCell>
                        <TableCell className="text-xs">{item.due_date || '—'}</TableCell>
                        <TableCell>
                          <Badge className={`text-[10px] gap-1 ${cfg.color}`}>
                            <cfg.icon className="h-3 w-3" />{t(cfg.labelKey, { defaultValue: cfg.label })}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => openDetail(item)}>
                            <Eye className="h-3.5 w-3.5" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    )
                  })}
                </Fragment>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

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

      {/* Detail Sheet */}
      <Sheet open={!!detailItem} onOpenChange={open => { if (!open) setDetailItem(null) }}>
        <SheetContent side="right" className="w-[400px] sm:w-[480px] overflow-y-auto">
          {detailItem && (
            <>
              <SheetHeader>
                <SheetTitle>{detailItem.company_name || '—'}</SheetTitle>
                <SheetDescription>{detailItem.service_name || detailItem.fee_type}</SheetDescription>
              </SheetHeader>
              <div className="space-y-3 mt-4 text-xs">
                <div className="grid grid-cols-2 gap-3">
                  <div><span className="text-muted-foreground">{t('queue.amount')}:</span><br/><strong>{fmtXAF(detailItem.amount, locale)}</strong></div>
                  <div><span className="text-muted-foreground">{t('queue.dueDate')}:</span><br/><strong>{detailItem.due_date || '—'}</strong></div>
                </div>
                {detailEvents.length > 0 && (
                  <div className="space-y-1.5 pt-2 border-t">
                    <p className="font-medium">{t('queue.history')} ({detailEvents.length})</p>
                    {detailEvents.map(evt => (
                      <div key={evt.id} className="flex items-center gap-2 text-[10px]">
                        <Badge variant="outline" className="text-[9px] font-mono">{evt.event_type}</Badge>
                        <span className="text-muted-foreground">
                          {new Date(evt.created_at).toLocaleDateString(locale, { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          )}
        </SheetContent>
      </Sheet>
    </div>
  )
}
