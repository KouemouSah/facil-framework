'use client'

import { useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { useLocale, useTranslations } from 'next-intl'
import {
  FileStack,
  Plus,
  Loader2,
  ChevronLeft,
  ChevronRight,
  Eye,
  Trash2,
  AlertCircle,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription } from '@/components/ui/alert'
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
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { batchApi } from '../services/batch-api'
import type { BatchRequest, BatchListResponse } from '../types'
import {
  BatchStatus,
  getBatchStatusColor,
  getBatchStatusKey,
} from '../types'

const DELETABLE_STATUSES = ['DRAFT', 'UPLOADING', 'REVIEW']

export function BatchList() {
  const router = useRouter()
  const locale = useLocale()
  const t = useTranslations('batch')

  const [isLoading, setIsLoading] = useState(true)
  const [data, setData] = useState<BatchListResponse | null>(null)
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState('__all__')
  const [deleteTarget, setDeleteTarget] = useState<BatchRequest | null>(null)
  const [error, setError] = useState<string | null>(null)

  const fetchBatches = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const result = await batchApi.listBatches({
        status: statusFilter === '__all__' ? undefined : statusFilter,
        page,
        pageSize: 20,
      })
      setData(result)
    } catch (err) {
      console.error('Failed to load batches:', err)
      setError((err as Error).message || t('list.loadError'))
    } finally {
      setIsLoading(false)
    }
  }, [page, statusFilter, t])

  useEffect(() => {
    fetchBatches()
  }, [fetchBatches])

  const handleConfirmDelete = async () => {
    if (!deleteTarget) return
    try {
      await batchApi.deleteBatch(deleteTarget.id)
      fetchBatches()
    } catch (err) {
      console.error('Failed to delete batch:', err)
      setError((err as Error).message || t('list.deleteError'))
    } finally {
      setDeleteTarget(null)
    }
  }

  const batches = data?.batches || []

  // Status filter options from enum + i18n
  const statusFilterOptions = [
    { value: '__all__', label: t('list.allStatuses') },
    ...Object.values(BatchStatus).map((s) => ({
      value: s,
      label: t(getBatchStatusKey(s)),
    })),
  ]

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <FileStack className="h-6 w-6 text-blue-600" />
          <h1 className="text-2xl font-bold">{t('title')}</h1>
        </div>
        <Button onClick={() => router.push(`/${locale}/dashboard/batch-requests/wizard`)}>
          <Plus className="h-4 w-4 mr-2" />
          {t('newBatch')}
        </Button>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3">
        <Select
          value={statusFilter}
          onValueChange={(val) => {
            setStatusFilter(val)
            setPage(1)
          }}
        >
          <SelectTrigger className="w-[200px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {statusFilterOptions.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Error banner */}
      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Table */}
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-blue-500" />
        </div>
      ) : batches.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <FileStack className="h-12 w-12 mx-auto mb-3 opacity-30" />
          <p>{t('noBatches')}</p>
          <Button
            variant="outline"
            className="mt-4"
            onClick={() => router.push(`/${locale}/dashboard/batch-requests/wizard`)}
          >
            {t('createFirst')}
          </Button>
        </div>
      ) : (
        <>
          <div className="border rounded-lg overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('reference')}</TableHead>
                  <TableHead>{t('workflow')}</TableHead>
                  <TableHead>{t('beneficiaries')}</TableHead>
                  <TableHead>{t('amount')}</TableHead>
                  <TableHead>{t('status')}</TableHead>
                  <TableHead>{t('date')}</TableHead>
                  <TableHead className="w-24">{t('actions')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {batches.map((batch) => (
                  <TableRow
                    key={batch.id}
                    className="cursor-pointer hover:bg-gray-50"
                    onClick={() =>
                      router.push(`/${locale}/dashboard/batch-requests/${batch.id}`)
                    }
                  >
                    <TableCell className="font-mono text-sm">
                      {batch.reference || batch.id.slice(0, 8)}
                    </TableCell>
                    <TableCell>
                      <span className="text-sm">{batch.workflowCode}</span>
                      <span className="text-xs text-gray-400 block">
                        {batch.solicitudType}
                      </span>
                    </TableCell>
                    <TableCell>
                      <div className="text-sm">
                        <span className="font-medium">{batch.totalItems}</span>
                        {batch.itemsReady > 0 && (
                          <span className="text-green-600 text-xs ml-1">
                            ({batch.itemsReady} {t('list.ready')})
                          </span>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      {batch.totalAmount ? (
                        <span className="text-sm font-medium">
                          {new Intl.NumberFormat('es-GQ', {
                            style: 'currency',
                            currency: batch.currency,
                            minimumFractionDigits: 0,
                          }).format(batch.totalAmount)}
                        </span>
                      ) : (
                        <span className="text-gray-300">{'\u2014'}</span>
                      )}
                    </TableCell>
                    <TableCell>
                      <Badge
                        className={`${getBatchStatusColor(batch.status)} text-xs`}
                      >
                        {t(getBatchStatusKey(batch.status))}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-sm text-gray-500">
                      {new Date(batch.createdAt).toLocaleDateString(locale)}
                    </TableCell>
                    <TableCell>
                      <div
                        className="flex gap-1"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7"
                          onClick={() =>
                            router.push(
                              `/${locale}/dashboard/batch-requests/${batch.id}`
                            )
                          }
                        >
                          <Eye className="h-3.5 w-3.5" />
                        </Button>
                        {DELETABLE_STATUSES.includes(batch.status) && (
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7 text-red-500"
                            onClick={() => setDeleteTarget(batch)}
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </Button>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          {/* Pagination */}
          {data && data.totalPages > 1 && (
            <div className="flex items-center justify-between">
              <p className="text-sm text-gray-500">
                {t('list.showing', { count: batches.length, total: data.total })}
              </p>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page <= 1}
                >
                  <ChevronLeft className="h-4 w-4" />
                </Button>
                <span className="text-sm text-gray-500">
                  {page} / {data.totalPages}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() =>
                    setPage((p) => Math.min(data.totalPages, p + 1))
                  }
                  disabled={page >= data.totalPages}
                >
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            </div>
          )}
        </>
      )}

      {/* Delete confirmation dialog */}
      <AlertDialog open={!!deleteTarget} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('confirmDelete')}</AlertDialogTitle>
            <AlertDialogDescription>
              {deleteTarget?.reference || deleteTarget?.id.slice(0, 8)}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('beneficiary.cancel')}</AlertDialogCancel>
            <AlertDialogAction onClick={handleConfirmDelete}>
              <Trash2 className="h-4 w-4 mr-1" />
              {t('list.delete')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
