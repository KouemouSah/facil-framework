'use client'

import { ArrowUpDown, ArrowUp, ArrowDown } from 'lucide-react'
import { TableHead } from '@/components/ui/table'
import { cn } from '@/lib/utils'

export interface SortState {
  column: string | null
  direction: 'asc' | 'desc'
}

interface SortableHeaderProps {
  column: string
  label: string
  sort: SortState
  onSort: (column: string) => void
  className?: string
}

export function SortableHeader({ column, label, sort, onSort, className }: SortableHeaderProps) {
  const isActive = sort.column === column
  return (
    <TableHead
      className={cn('cursor-pointer select-none hover:bg-muted/50 transition-colors', isActive && 'text-foreground', className)}
      onClick={() => onSort(column)}
    >
      <div className="flex items-center gap-1">
        <span>{label}</span>
        {isActive
          ? sort.direction === 'asc' ? <ArrowUp className="h-3.5 w-3.5 shrink-0" /> : <ArrowDown className="h-3.5 w-3.5 shrink-0" />
          : <ArrowUpDown className="h-3.5 w-3.5 shrink-0 opacity-40" />}
      </div>
    </TableHead>
  )
}
