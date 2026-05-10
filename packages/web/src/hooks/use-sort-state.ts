import { useState, useCallback } from 'react'
import type { SortState } from '@/components/ui/sortable-header'

/**
 * Reusable sort state hook.
 *
 * Server-side: pass sort.column/sort.direction to API params.
 * Client-side: use sortData() for in-memory sorting (small tables only).
 */
export function useSortState(defaultColumn: string | null = null, defaultDirection: 'asc' | 'desc' = 'asc') {
  const [sort, setSort] = useState<SortState>({ column: defaultColumn, direction: defaultDirection })

  const handleSort = useCallback((column: string) => {
    setSort(prev => prev.column === column
      ? { column, direction: prev.direction === 'asc' ? 'desc' : 'asc' }
      : { column, direction: 'asc' })
  }, [])

  const sortData = useCallback(<T extends Record<string, unknown>>(
    data: T[],
    types: Record<string, 'string' | 'number' | 'boolean' | 'date'>,
  ): T[] => {
    if (!sort.column) return data
    const col = sort.column, type = types[col] || 'string', dir = sort.direction === 'asc' ? 1 : -1
    return [...data].sort((a, b) => {
      const va = a[col], vb = b[col]
      if (va == null && vb == null) return 0
      if (va == null) return 1
      if (vb == null) return -1
      switch (type) {
        case 'number': return (Number(va) - Number(vb)) * dir
        case 'boolean': return ((va ? 1 : 0) - (vb ? 1 : 0)) * dir
        case 'date': return (new Date(String(va)).getTime() - new Date(String(vb)).getTime()) * dir
        default: return String(va).localeCompare(String(vb)) * dir
      }
    })
  }, [sort])

  return [sort, handleSort, sortData] as const
}
