'use client'

import { useCallback } from 'react'
import { useTranslations } from 'next-intl'
import { Columns3, Eye, EyeOff } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'
import { Separator } from '@/components/ui/separator'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ColumnDef {
  key: string
  label: string
  defaultVisible?: boolean
}

interface ColumnVisibilityToggleProps {
  columns: ColumnDef[]
  visibility: Record<string, boolean>
  onVisibilityChange: (visibility: Record<string, boolean>) => void
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ColumnVisibilityToggle({
  columns,
  visibility,
  onVisibilityChange,
}: ColumnVisibilityToggleProps) {
  const t = useTranslations('inspection')

  // -----------------------------------------------------------------------
  // Show all / Hide all
  // -----------------------------------------------------------------------

  const handleShowAll = useCallback(() => {
    const next: Record<string, boolean> = {}
    for (const col of columns) {
      next[col.key] = true
    }
    onVisibilityChange(next)
  }, [columns, onVisibilityChange])

  const handleHideAll = useCallback(() => {
    const next: Record<string, boolean> = {}
    // Keep first column visible to prevent empty table
    for (let i = 0; i < columns.length; i++) {
      next[columns[i].key] = i === 0
    }
    onVisibilityChange(next)
  }, [columns, onVisibilityChange])

  // -----------------------------------------------------------------------
  // Toggle single column
  // -----------------------------------------------------------------------

  const handleToggle = useCallback(
    (key: string, checked: boolean) => {
      onVisibilityChange({ ...visibility, [key]: checked })
    },
    [visibility, onVisibilityChange],
  )

  // -----------------------------------------------------------------------
  // Resolve visibility: explicit value > defaultVisible > true
  // -----------------------------------------------------------------------

  const isVisible = (col: ColumnDef): boolean => {
    if (visibility[col.key] !== undefined) return visibility[col.key]
    if (col.defaultVisible !== undefined) return col.defaultVisible
    return true
  }

  // -----------------------------------------------------------------------
  // Render
  // -----------------------------------------------------------------------

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="outline" size="sm" className="h-8 gap-1.5 text-xs">
          <Columns3 className="h-4 w-4" />
          {t('columns.toggle')}
        </Button>
      </PopoverTrigger>

      <PopoverContent align="end" className="w-[220px] p-3">
        {/* ---- Action buttons ---- */}
        <div className="flex items-center gap-1.5">
          <Button
            variant="ghost"
            size="sm"
            className="h-7 flex-1 gap-1 text-xs"
            onClick={handleShowAll}
          >
            <Eye className="h-3.5 w-3.5" />
            {t('columns.showAll')}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 flex-1 gap-1 text-xs"
            onClick={handleHideAll}
          >
            <EyeOff className="h-3.5 w-3.5" />
            {t('columns.hideAll')}
          </Button>
        </div>

        <Separator className="my-2" />

        {/* ---- Column list ---- */}
        <div className="max-h-64 space-y-1 overflow-y-auto">
          {columns.map((col) => {
            const checked = isVisible(col)
            return (
              <label
                key={col.key}
                className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-muted/50"
              >
                <Checkbox
                  checked={checked}
                  onCheckedChange={(v) => handleToggle(col.key, v === true)}
                />
                <span className="truncate">{col.label}</span>
              </label>
            )
          })}
        </div>
      </PopoverContent>
    </Popover>
  )
}
