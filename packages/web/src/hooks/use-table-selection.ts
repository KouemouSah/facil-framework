/**
 * useTableSelection Hook
 * Provides row selection functionality for tables
 *
 * @module hooks/use-table-selection
 * @date 2025-01-17
 */

import { useState, useMemo, useCallback } from 'react'

export interface UseTableSelectionOptions<T> {
  items: T[]
  getItemId: (item: T) => string
}

export interface UseTableSelectionReturn<T> {
  selectedIds: Set<string>
  selectedItems: T[]
  isSelected: (item: T) => boolean
  isAllSelected: boolean
  isPartiallySelected: boolean
  toggleSelection: (item: T) => void
  toggleAllSelection: () => void
  selectAll: () => void
  clearSelection: () => void
  selectItems: (items: T[]) => void
  selectedCount: number
}

export function useTableSelection<T>({
  items,
  getItemId,
}: UseTableSelectionOptions<T>): UseTableSelectionReturn<T> {
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())

  const isSelected = useCallback(
    (item: T) => selectedIds.has(getItemId(item)),
    [selectedIds, getItemId]
  )

  const selectedItems = useMemo(
    () => items.filter((item) => selectedIds.has(getItemId(item))),
    [items, selectedIds, getItemId]
  )

  const isAllSelected = useMemo(
    () => items.length > 0 && items.every((item) => selectedIds.has(getItemId(item))),
    [items, selectedIds, getItemId]
  )

  const isPartiallySelected = useMemo(
    () => selectedIds.size > 0 && !isAllSelected,
    [selectedIds.size, isAllSelected]
  )

  const toggleSelection = useCallback(
    (item: T) => {
      const id = getItemId(item)
      setSelectedIds((prev) => {
        const next = new Set(prev)
        if (next.has(id)) {
          next.delete(id)
        } else {
          next.add(id)
        }
        return next
      })
    },
    [getItemId]
  )

  const toggleAllSelection = useCallback(() => {
    if (isAllSelected) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(items.map(getItemId)))
    }
  }, [items, getItemId, isAllSelected])

  const selectAll = useCallback(() => {
    setSelectedIds(new Set(items.map(getItemId)))
  }, [items, getItemId])

  const clearSelection = useCallback(() => {
    setSelectedIds(new Set())
  }, [])

  const selectItems = useCallback(
    (itemsToSelect: T[]) => {
      setSelectedIds(new Set(itemsToSelect.map(getItemId)))
    },
    [getItemId]
  )

  return {
    selectedIds,
    selectedItems,
    isSelected,
    isAllSelected,
    isPartiallySelected,
    toggleSelection,
    toggleAllSelection,
    selectAll,
    clearSelection,
    selectItems,
    selectedCount: selectedIds.size,
  }
}

export default useTableSelection
