/**
 * DataTable Component
 * Reusable table with row selection, pagination, and bulk actions
 *
 * Features:
 * - Row selection (single/all)
 * - Bulk actions toolbar
 * - Client-side pagination (default 10 per page)
 * - Loading and empty states
 *
 * @module components/ui/data-table
 * @date 2025-01-17
 */

'use client'

import * as React from 'react'
import { useTranslations } from 'next-intl'
import { Checkbox } from '@/components/ui/checkbox'
import { Button } from '@/components/ui/button'
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
import {
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  Trash2,
  RefreshCw,
  X,
} from 'lucide-react'
import { useTableSelection } from '@/hooks/use-table-selection'
import { cn } from '@/core/utils'

// =============================================================================
// TYPES
// =============================================================================

export interface DataTableColumn<T> {
  id: string
  header: React.ReactNode
  cell: (item: T) => React.ReactNode
  className?: string
}

export interface BulkAction<T> {
  id: string
  label: string
  icon?: React.ReactNode
  variant?: 'default' | 'destructive' | 'outline' | 'secondary' | 'ghost' | 'link'
  /** If true, shows confirmation dialog */
  requiresConfirmation?: boolean
  confirmTitle?: string
  confirmDescription?: string
  confirmButtonLabel?: string
  onExecute: (selectedItems: T[]) => Promise<void> | void
}

export interface DataTableProps<T> {
  data: T[]
  columns: DataTableColumn<T>[]
  getRowId: (item: T) => string
  /** Bulk actions available when rows are selected */
  bulkActions?: BulkAction<T>[]
  /** Whether to show selection checkboxes */
  selectable?: boolean
  /** Loading state */
  isLoading?: boolean
  /** Empty state message */
  emptyMessage?: React.ReactNode
  /** Empty state icon */
  emptyIcon?: React.ReactNode
  /** Default page size */
  defaultPageSize?: number
  /** Page size options */
  pageSizeOptions?: number[]
  /** Callback when data needs refresh after bulk action */
  onRefresh?: () => void
  /** Table class name */
  className?: string
}

// =============================================================================
// COMPONENT
// =============================================================================

export function DataTable<T>({
  data,
  columns,
  getRowId,
  bulkActions = [],
  selectable = true,
  isLoading = false,
  emptyMessage,
  emptyIcon,
  defaultPageSize = 10,
  pageSizeOptions = [10, 20, 50, 100],
  onRefresh,
  className,
}: DataTableProps<T>) {
  const t = useTranslations('common')

  // Pagination state
  const [currentPage, setCurrentPage] = React.useState(1)
  const [pageSize, setPageSize] = React.useState(defaultPageSize)

  // Confirmation dialog state
  const [confirmAction, setConfirmAction] = React.useState<BulkAction<T> | null>(null)
  const [isExecuting, setIsExecuting] = React.useState(false)

  // Row selection
  const selection = useTableSelection({
    items: data,
    getItemId: getRowId,
  })

  // Pagination calculations
  const totalPages = Math.ceil(data.length / pageSize)
  const startIndex = (currentPage - 1) * pageSize
  const endIndex = Math.min(startIndex + pageSize, data.length)
  const paginatedData = data.slice(startIndex, endIndex)

  // Reset to page 1 when data changes significantly
  React.useEffect(() => {
    if (currentPage > Math.ceil(data.length / pageSize)) {
      setCurrentPage(1)
    }
  }, [data.length, pageSize, currentPage])

  // Reset selection when page changes
  React.useEffect(() => {
    selection.clearSelection()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentPage])

  // Handle page size change
  const handlePageSizeChange = (value: string) => {
    setPageSize(Number(value))
    setCurrentPage(1)
    selection.clearSelection()
  }

  // Handle bulk action execution
  const handleBulkAction = async (action: BulkAction<T>) => {
    if (action.requiresConfirmation) {
      setConfirmAction(action)
      return
    }

    await executeBulkAction(action)
  }

  const executeBulkAction = async (action: BulkAction<T>) => {
    setIsExecuting(true)
    try {
      await action.onExecute(selection.selectedItems)
      selection.clearSelection()
      onRefresh?.()
    } finally {
      setIsExecuting(false)
      setConfirmAction(null)
    }
  }

  // Selection for current page only
  const currentPageSelection = React.useMemo(() => {
    const pageIds = new Set(paginatedData.map(getRowId))
    const selectedOnPage = Array.from(selection.selectedIds).filter((id) => pageIds.has(id))
    return {
      isAllSelected: paginatedData.length > 0 && selectedOnPage.length === paginatedData.length,
      isPartiallySelected: selectedOnPage.length > 0 && selectedOnPage.length < paginatedData.length,
      toggleAll: () => {
        if (selectedOnPage.length === paginatedData.length) {
          // Deselect all on current page
          selection.selectItems(
            selection.selectedItems.filter((item) => !pageIds.has(getRowId(item)))
          )
        } else {
          // Select all on current page (keeping existing selections from other pages)
          const existingOtherPageSelections = selection.selectedItems.filter(
            (item) => !pageIds.has(getRowId(item))
          )
          selection.selectItems([...existingOtherPageSelections, ...paginatedData])
        }
      },
    }
  }, [paginatedData, selection, getRowId])

  return (
    <div className={cn('space-y-4', className)}>
      {/* Bulk Actions Toolbar */}
      {selectable && selection.selectedCount > 0 && (
        <div className="flex items-center justify-between rounded-lg border bg-muted/50 px-4 py-2">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">
              {selection.selectedCount} {t('selected')}
            </span>
            <Button
              variant="ghost"
              size="sm"
              onClick={selection.clearSelection}
              className="h-8 px-2"
            >
              <X className="h-4 w-4 mr-1" />
              {t('clearSelection')}
            </Button>
          </div>
          <div className="flex items-center gap-2">
            {bulkActions.map((action) => (
              <Button
                key={action.id}
                variant={action.variant || 'outline'}
                size="sm"
                onClick={() => handleBulkAction(action)}
                disabled={isExecuting}
              >
                {isExecuting ? (
                  <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  action.icon && <span className="mr-2">{action.icon}</span>
                )}
                {action.label}
              </Button>
            ))}
          </div>
        </div>
      )}

      {/* Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              {selectable && (
                <TableHead className="w-12">
                  <Checkbox
                    checked={
                      currentPageSelection.isAllSelected
                        ? true
                        : currentPageSelection.isPartiallySelected
                          ? 'indeterminate'
                          : false
                    }
                    onCheckedChange={currentPageSelection.toggleAll}
                    aria-label={t('selectAll')}
                  />
                </TableHead>
              )}
              {columns.map((column) => (
                <TableHead key={column.id} className={column.className}>
                  {column.header}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell
                  colSpan={columns.length + (selectable ? 1 : 0)}
                  className="h-32 text-center"
                >
                  <div className="flex items-center justify-center">
                    <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
                    <span className="ml-2 text-muted-foreground">{t('loading')}</span>
                  </div>
                </TableCell>
              </TableRow>
            ) : paginatedData.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={columns.length + (selectable ? 1 : 0)}
                  className="h-32 text-center"
                >
                  <div className="flex flex-col items-center justify-center text-muted-foreground">
                    {emptyIcon && <div className="mb-4 opacity-50">{emptyIcon}</div>}
                    <span>{emptyMessage || t('noData')}</span>
                  </div>
                </TableCell>
              </TableRow>
            ) : (
              paginatedData.map((item) => (
                <TableRow
                  key={getRowId(item)}
                  data-state={selection.isSelected(item) ? 'selected' : undefined}
                >
                  {selectable && (
                    <TableCell>
                      <Checkbox
                        checked={selection.isSelected(item)}
                        onCheckedChange={() => selection.toggleSelection(item)}
                        aria-label={t('selectRow')}
                      />
                    </TableCell>
                  )}
                  {columns.map((column) => (
                    <TableCell key={column.id} className={column.className}>
                      {column.cell(item)}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
      {data.length > 0 && (
        <div className="flex items-center justify-between px-2">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <span>
              {t('showing')} {startIndex + 1}-{endIndex} {t('of')} {data.length}
            </span>
          </div>
          <div className="flex items-center gap-6">
            {/* Page size selector */}
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">{t('rowsPerPage')}</span>
              <Select value={String(pageSize)} onValueChange={handlePageSizeChange}>
                <SelectTrigger className="h-8 w-[70px]">
                  <SelectValue placeholder={pageSize} />
                </SelectTrigger>
                <SelectContent side="top">
                  {pageSizeOptions.map((size) => (
                    <SelectItem key={size} value={String(size)}>
                      {size}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Page info */}
            <div className="flex items-center gap-1 text-sm text-muted-foreground">
              <span>
                {t('page')} {currentPage} {t('of')} {totalPages}
              </span>
            </div>

            {/* Navigation buttons */}
            <div className="flex items-center gap-1">
              <Button
                variant="outline"
                size="icon"
                className="h-8 w-8"
                onClick={() => setCurrentPage(1)}
                disabled={currentPage === 1}
              >
                <ChevronsLeft className="h-4 w-4" />
              </Button>
              <Button
                variant="outline"
                size="icon"
                className="h-8 w-8"
                onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                disabled={currentPage === 1}
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <Button
                variant="outline"
                size="icon"
                className="h-8 w-8"
                onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                disabled={currentPage === totalPages}
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
              <Button
                variant="outline"
                size="icon"
                className="h-8 w-8"
                onClick={() => setCurrentPage(totalPages)}
                disabled={currentPage === totalPages}
              >
                <ChevronsRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Confirmation Dialog */}
      <AlertDialog open={!!confirmAction} onOpenChange={() => setConfirmAction(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {confirmAction?.confirmTitle || t('confirmAction')}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {confirmAction?.confirmDescription ||
                t('confirmActionDescription', { count: selection.selectedCount })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isExecuting}>{t('cancel')}</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => confirmAction && executeBulkAction(confirmAction)}
              disabled={isExecuting}
              className={
                confirmAction?.variant === 'destructive'
                  ? 'bg-destructive text-destructive-foreground hover:bg-destructive/90'
                  : undefined
              }
            >
              {isExecuting && <RefreshCw className="h-4 w-4 mr-2 animate-spin" />}
              {confirmAction?.confirmButtonLabel || t('confirm')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

// =============================================================================
// HELPER: Bulk delete action factory
// =============================================================================

export function createBulkDeleteAction<T>(options: {
  label?: string
  onDelete: (items: T[]) => Promise<void>
  confirmTitle?: string
  confirmDescription?: string
}): BulkAction<T> {
  return {
    id: 'delete',
    label: options.label || 'Delete',
    icon: <Trash2 className="h-4 w-4" />,
    variant: 'destructive',
    requiresConfirmation: true,
    confirmTitle: options.confirmTitle,
    confirmDescription: options.confirmDescription,
    onExecute: options.onDelete,
  }
}

export default DataTable
