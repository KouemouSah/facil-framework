'use client'

import { useState } from 'react'
import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

interface DataTablePaginationProps {
  currentPage: number
  totalPages: number
  totalItems: number
  pageSize: number
  onPageChange: (page: number) => void
  onPageSizeChange: (size: number) => void
  pageSizeOptions?: number[]
  labels?: {
    rowsPerPage?: string
    of?: string
    page?: string
    goToFirstPage?: string
    goToPreviousPage?: string
    goToNextPage?: string
    goToLastPage?: string
  }
}

export function DataTablePagination({
  currentPage,
  totalPages,
  totalItems,
  pageSize,
  onPageChange,
  onPageSizeChange,
  pageSizeOptions = [10, 20, 30, 50],
  labels = {},
}: DataTablePaginationProps) {
  const {
    rowsPerPage = 'Filas por página',
    of = 'de',
    page = 'Página',
    goToFirstPage = 'Ir a la primera página',
    goToPreviousPage = 'Ir a la página anterior',
    goToNextPage = 'Ir a la siguiente página',
    goToLastPage = 'Ir a la última página',
  } = labels

  const startItem = totalItems === 0 ? 0 : (currentPage - 1) * pageSize + 1
  const endItem = Math.min(currentPage * pageSize, totalItems)

  return (
    <div className="flex items-center justify-between px-2 py-4">
      <div className="flex-1 text-sm text-muted-foreground">
        {startItem}-{endItem} {of} {totalItems}
      </div>
      <div className="flex items-center space-x-6 lg:space-x-8">
        <div className="flex items-center space-x-2">
          <p className="text-sm font-medium">{rowsPerPage}</p>
          <Select
            value={`${pageSize}`}
            onValueChange={(value) => {
              onPageSizeChange(Number(value))
              onPageChange(1) // Reset to first page when changing page size
            }}
          >
            <SelectTrigger className="h-8 w-[70px]">
              <SelectValue placeholder={pageSize} />
            </SelectTrigger>
            <SelectContent side="top">
              {pageSizeOptions.map((size) => (
                <SelectItem key={size} value={`${size}`}>
                  {size}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="flex w-[100px] items-center justify-center text-sm font-medium">
          {page} {currentPage} {of} {totalPages || 1}
        </div>
        <div className="flex items-center space-x-2">
          <Button
            variant="outline"
            className="hidden h-8 w-8 p-0 lg:flex"
            onClick={() => onPageChange(1)}
            disabled={currentPage <= 1}
            title={goToFirstPage}
          >
            <span className="sr-only">{goToFirstPage}</span>
            <ChevronsLeft className="h-4 w-4" />
          </Button>
          <Button
            variant="outline"
            className="h-8 w-8 p-0"
            onClick={() => onPageChange(currentPage - 1)}
            disabled={currentPage <= 1}
            title={goToPreviousPage}
          >
            <span className="sr-only">{goToPreviousPage}</span>
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <Button
            variant="outline"
            className="h-8 w-8 p-0"
            onClick={() => onPageChange(currentPage + 1)}
            disabled={currentPage >= totalPages}
            title={goToNextPage}
          >
            <span className="sr-only">{goToNextPage}</span>
            <ChevronRight className="h-4 w-4" />
          </Button>
          <Button
            variant="outline"
            className="hidden h-8 w-8 p-0 lg:flex"
            onClick={() => onPageChange(totalPages)}
            disabled={currentPage >= totalPages}
            title={goToLastPage}
          >
            <span className="sr-only">{goToLastPage}</span>
            <ChevronsRight className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  )
}

// Hook for pagination state management
export function usePagination(initialPageSize = 10) {
  const [currentPage, setCurrentPage] = useState(1)
  const [pageSize, setPageSize] = useState(initialPageSize)

  const paginateData = <T,>(data: T[]): T[] => {
    const startIndex = (currentPage - 1) * pageSize
    return data.slice(startIndex, startIndex + pageSize)
  }

  const getTotalPages = (totalItems: number) => Math.ceil(totalItems / pageSize)

  const resetPage = () => setCurrentPage(1)

  return {
    currentPage,
    pageSize,
    setCurrentPage,
    setPageSize,
    paginateData,
    getTotalPages,
    resetPage,
  }
}
