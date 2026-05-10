'use client'

/**
 * AgentBatchList - Table of batches for an entity
 * @module agent-dashboard/components/batch
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { useLocale, useTranslations } from 'next-intl'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
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
import { FileStack, Search, RefreshCw, ArrowLeft } from 'lucide-react'
import { toast } from 'sonner'
import Link from 'next/link'
import {
  agentRequestsApi,
  type AgentBatchSummary,
} from '../../services/agent-requests-api'

const STATUS_COLORS: Record<string, string> = {
  PAID: 'bg-emerald-100 text-emerald-800',
  IN_PROGRESS: 'bg-blue-100 text-blue-800',
  COMPLETED: 'bg-green-200 text-green-900',
}

interface AgentBatchListProps {
  entityCode: string
  basePath: string
}

export function AgentBatchList({ entityCode, basePath }: AgentBatchListProps) {
  const router = useRouter()
  const locale = useLocale()
  const t = useTranslations('agent')
  const tBatch = useTranslations('batch')

  const [batches, setBatches] = useState<AgentBatchSummary[]>([])
  const [total, setTotal] = useState(0)
  const [isLoading, setIsLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [page, setPage] = useState(1)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Debounce search input (300ms)
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      setDebouncedSearch(search)
      setPage(1)
    }, 300)
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current) }
  }, [search])

  const fetchBatches = useCallback(async () => {
    setIsLoading(true)
    try {
      const result = await agentRequestsApi.getEntityBatches(entityCode, {
        status: statusFilter !== 'all' ? statusFilter : undefined,
        search: debouncedSearch || undefined,
        page,
        pageSize: 20,
      })
      setBatches(result.batches)
      setTotal(result.total)
    } catch {
      toast.error(tBatch('loadError', { defaultValue: 'Error al cargar los lotes' }))
    } finally {
      setIsLoading(false)
    }
  }, [entityCode, statusFilter, debouncedSearch, page, tBatch])

  useEffect(() => { fetchBatches() }, [fetchBatches])

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return '-'
    return new Date(dateStr).toLocaleDateString(locale, {
      day: '2-digit', month: '2-digit', year: 'numeric',
    })
  }

  const formatAmount = (amount: number | null) => {
    if (amount == null || amount === 0) return '-'
    return new Intl.NumberFormat(locale === 'fr' ? 'fr-FR' : locale === 'en' ? 'en-US' : 'es-GQ', {
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(amount) + ' FCFA'
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href={`/${locale}${basePath}`}>
            <Button variant="ghost" size="sm">
              <ArrowLeft className="h-4 w-4 mr-1" />
            </Button>
          </Link>
          <FileStack className="h-6 w-6 text-indigo-600" />
          <div>
            <h1 className="text-2xl font-bold">{t('batch.title')}</h1>
            <p className="text-sm text-muted-foreground">
              {total} {t('batch.batchBadge').toLowerCase()}
              {total !== 1 ? 's' : ''}
            </p>
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={fetchBatches} disabled={isLoading}>
          <RefreshCw className={`h-4 w-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
        </Button>
      </div>

      {/* Filters */}
      <div className="flex gap-3">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder={t('batch.searchPlaceholder')}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-10"
          />
        </div>
        <Select value={statusFilter} onValueChange={(v) => { setStatusFilter(v); setPage(1) }}>
          <SelectTrigger className="w-[160px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t('batch.filterAll')}</SelectItem>
            <SelectItem value="PAID">{t('batch.filterPaid')}</SelectItem>
            <SelectItem value="IN_PROGRESS">{t('batch.filterInProgress')}</SelectItem>
            <SelectItem value="COMPLETED">{t('batch.filterCompleted')}</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t('batch.title')}</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => <Skeleton key={i} className="h-12 w-full" />)}
            </div>
          ) : batches.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">
              <FileStack className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p>{t('batch.noBatches')}</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('batch.colReference')}</TableHead>
                  <TableHead>{t('batch.colWorkflow')}</TableHead>
                  <TableHead>{t('batch.beneficiaries')}</TableHead>
                  <TableHead>{t('batch.progress')}</TableHead>
                  <TableHead>{t('batch.totalAmount')}</TableHead>
                  <TableHead>{t('batch.colStatus')}</TableHead>
                  <TableHead>{t('batch.colDate')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {batches.map((batch) => {
                  const progress = batch.total_items > 0
                    ? Math.round((batch.items_completed / batch.total_items) * 100)
                    : 0
                  return (
                    <TableRow
                      key={batch.id}
                      className="cursor-pointer hover:bg-muted/50"
                      onClick={() => router.push(`/${locale}${basePath}/batch-requests/${batch.id}`)}
                    >
                      <TableCell className="font-mono font-medium">
                        {batch.reference || batch.id.slice(0, 8)}
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" className="text-xs">
                          {batch.workflow_code.replace(/_/g, ' ')}
                        </Badge>
                      </TableCell>
                      <TableCell>{batch.total_items}</TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <div className="flex-1 h-2 bg-gray-100 rounded-full w-20">
                            <div
                              className="h-2 bg-indigo-500 rounded-full"
                              style={{ width: `${progress}%` }}
                            />
                          </div>
                          <span className="text-xs text-muted-foreground">{progress}%</span>
                        </div>
                      </TableCell>
                      <TableCell className="text-sm">{formatAmount(batch.total_amount)}</TableCell>
                      <TableCell>
                        <Badge className={STATUS_COLORS[batch.status] || 'bg-gray-100'}>
                          {tBatch(`status.${batch.status}` as Parameters<typeof tBatch>[0])}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {formatDate(batch.submitted_at || batch.created_at)}
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Pagination */}
      {!isLoading && total > 20 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            {t('batch.showing', { count: batches.length, total })}
          </p>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
            >
              &larr;
            </Button>
            <span className="text-sm text-muted-foreground">
              {page} / {Math.ceil(total / 20)}
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((p) => p + 1)}
              disabled={page >= Math.ceil(total / 20)}
            >
              &rarr;
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
