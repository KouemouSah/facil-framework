'use client'

import { useCallback, useState } from 'react'
import { useTranslations } from 'next-intl'
import { Save, Trash2, Star, SlidersHorizontal, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import { useToast } from '@/hooks/use-toast'
import { inspectionApi } from '../services/api'
import type { FilterPreset } from '../types'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface FilterPresetSelectorProps {
  tableKey: string
  currentFilters: Record<string, unknown>
  currentColumnVisibility?: Record<string, boolean>
  currentSortConfig?: { column: string; direction: 'asc' | 'desc' }
  onApplyPreset: (preset: FilterPreset) => void
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function FilterPresetSelector({
  tableKey,
  currentFilters,
  currentColumnVisibility,
  currentSortConfig,
  onApplyPreset,
}: FilterPresetSelectorProps) {
  const t = useTranslations('inspection')
  const { toast } = useToast()

  const [open, setOpen] = useState(false)
  const [presets, setPresets] = useState<FilterPreset[]>([])
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [newName, setNewName] = useState('')
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null)

  // -----------------------------------------------------------------------
  // Fetch presets when popover opens
  // -----------------------------------------------------------------------

  const fetchPresets = useCallback(async () => {
    setLoading(true)
    try {
      const res = await inspectionApi.listPresets(tableKey)
      setPresets(res.items)
    } catch {
      // Silently fail — empty list shown
    } finally {
      setLoading(false)
    }
  }, [tableKey])

  const handleOpenChange = useCallback(
    (nextOpen: boolean) => {
      setOpen(nextOpen)
      if (nextOpen) {
        setPendingDeleteId(null)
        fetchPresets()
      }
    },
    [fetchPresets],
  )

  // -----------------------------------------------------------------------
  // Apply preset
  // -----------------------------------------------------------------------

  const handleApply = useCallback(
    (preset: FilterPreset) => {
      onApplyPreset(preset)
      setOpen(false)
    },
    [onApplyPreset],
  )

  // -----------------------------------------------------------------------
  // Save new preset
  // -----------------------------------------------------------------------

  const handleSave = useCallback(async () => {
    const trimmed = newName.trim()
    if (!trimmed) return

    setSaving(true)
    try {
      const created = await inspectionApi.createPreset({
        preset_name: trimmed,
        table_key: tableKey,
        filters: currentFilters,
        column_visibility: currentColumnVisibility,
        sort_config: currentSortConfig,
        is_default: false,
      })
      setPresets((prev) => [...prev, created])
      setNewName('')
      toast({ title: t('presets.saved') })
    } catch {
      toast({ title: t('common.error'), variant: 'destructive' })
    } finally {
      setSaving(false)
    }
  }, [
    newName,
    tableKey,
    currentFilters,
    currentColumnVisibility,
    currentSortConfig,
    t,
    toast,
  ])

  // -----------------------------------------------------------------------
  // Toggle default
  // -----------------------------------------------------------------------

  const handleToggleDefault = useCallback(
    async (preset: FilterPreset) => {
      const nextDefault = !preset.is_default
      try {
        const updated = await inspectionApi.updatePreset(preset.id, {
          is_default: nextDefault,
        })
        setPresets((prev) =>
          prev.map((p) => {
            if (p.id === updated.id) return updated
            // If this preset became default, unset others
            if (nextDefault && p.is_default) return { ...p, is_default: false }
            return p
          }),
        )
      } catch {
        // Silently fail
      }
    },
    [],
  )

  // -----------------------------------------------------------------------
  // Delete preset (two-click confirm)
  // -----------------------------------------------------------------------

  const handleDelete = useCallback(
    async (presetId: string) => {
      if (pendingDeleteId !== presetId) {
        setPendingDeleteId(presetId)
        return
      }

      try {
        await inspectionApi.deletePreset(presetId)
        setPresets((prev) => prev.filter((p) => p.id !== presetId))
        setPendingDeleteId(null)
        toast({ title: t('presets.deleted') })
      } catch {
        // Silently fail
      }
    },
    [pendingDeleteId, t, toast],
  )

  // -----------------------------------------------------------------------
  // Active presets count (presets matching current filters)
  // -----------------------------------------------------------------------

  const activeCount = presets.filter((p) => p.is_default).length

  // -----------------------------------------------------------------------
  // Render
  // -----------------------------------------------------------------------

  return (
    <Popover open={open} onOpenChange={handleOpenChange}>
      <PopoverTrigger asChild>
        <Button variant="outline" size="sm" className="h-8 gap-1.5 text-xs">
          <SlidersHorizontal className="h-4 w-4" />
          {t('presets.title')}
          {activeCount > 0 && (
            <Badge variant="secondary" className="ml-1 h-5 px-1.5 text-[10px]">
              {activeCount}
            </Badge>
          )}
        </Button>
      </PopoverTrigger>

      <PopoverContent align="end" className="w-[300px] p-3">
        {/* ---- Preset list ---- */}
        <div className="max-h-80 overflow-y-auto">
          {loading ? (
            <div className="space-y-2">
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-3/4" />
            </div>
          ) : presets.length === 0 ? (
            <p className="py-4 text-center text-xs text-muted-foreground">
              {t('presets.noPresets')}
            </p>
          ) : (
            <ul className="space-y-1">
              {presets.map((preset) => {
                const isDeleting = pendingDeleteId === preset.id
                return (
                  <li
                    key={preset.id}
                    className="group flex items-center gap-1 rounded-md px-2 py-1.5 hover:bg-muted/50"
                  >
                    {/* Star (set default) */}
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation()
                        handleToggleDefault(preset)
                      }}
                      className="shrink-0 p-0.5"
                      title={t('presets.setDefault')}
                    >
                      <Star
                        className={`h-3.5 w-3.5 ${
                          preset.is_default
                            ? 'fill-yellow-400 text-yellow-500'
                            : 'text-muted-foreground/40 hover:text-yellow-400'
                        }`}
                      />
                    </button>

                    {/* Preset name — click to apply */}
                    <button
                      type="button"
                      onClick={() => handleApply(preset)}
                      className="min-w-0 flex-1 truncate text-left text-sm"
                    >
                      {preset.preset_name}
                    </button>

                    {/* Delete */}
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation()
                        handleDelete(preset.id)
                      }}
                      className="shrink-0 p-0.5 opacity-0 transition-opacity group-hover:opacity-100"
                      title={
                        isDeleting
                          ? t('presets.confirmDelete')
                          : t('presets.delete')
                      }
                    >
                      <Trash2
                        className={`h-3.5 w-3.5 ${
                          isDeleting
                            ? 'text-destructive'
                            : 'text-muted-foreground hover:text-destructive'
                        }`}
                      />
                    </button>
                  </li>
                )
              })}
            </ul>
          )}
        </div>

        <Separator className="my-2" />

        {/* ---- Save new preset ---- */}
        <div className="flex items-center gap-1.5">
          <Input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder={t('presets.enterName')}
            className="h-8 flex-1 text-xs"
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleSave()
            }}
            disabled={saving}
          />
          <Button
            variant="default"
            size="sm"
            className="h-8 gap-1 px-2.5 text-xs"
            onClick={handleSave}
            disabled={saving || !newName.trim()}
          >
            {saving ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Save className="h-3.5 w-3.5" />
            )}
            {t('presets.save')}
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  )
}
