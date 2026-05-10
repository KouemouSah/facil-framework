'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { useTranslations } from 'next-intl'
import { Search, X } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { cn } from '@/core/utils'
import type { InspectionStatus, InspectionResult } from '../types'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface InspectionFiltersProps {
  filters: Record<string, string | boolean | undefined>
  onFiltersChange: (filters: Record<string, string | boolean | undefined>) => void
  agents?: Array<{ id: string; name: string }>
  zones?: Array<{ code: string; name: string }>
  loading?: boolean
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const ALL_STATUSES: InspectionStatus[] = [
  'in_progress',
  'completed',
  'mise_en_demeure',
  'seal_proposed',
  'seal_approved',
  'seal_rejected',
  'cancelled',
]

const ALL_RESULTS: InspectionResult[] = ['conforme', 'non_conforme', 'pending']

const BOOLEAN_TOGGLES: Array<{ key: string; labelKey: string }> = [
  { key: 'has_payment', labelKey: 'filters.has_payment' },
  { key: 'has_med', labelKey: 'filters.has_med' },
  { key: 'has_seal', labelKey: 'filters.has_seal' },
]

const SENTINEL_ALL = '__all__'

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function InspectionFilters({
  filters,
  onFiltersChange,
  agents,
  zones,
  loading,
}: InspectionFiltersProps) {
  const t = useTranslations('inspection')

  // -- Debounced search
  const [searchValue, setSearchValue] = useState<string>(
    (filters.search as string) ?? '',
  )
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    // Sync external filter changes back into local state
    setSearchValue((filters.search as string) ?? '')
  }, [filters.search])

  const handleSearchChange = useCallback(
    (value: string) => {
      setSearchValue(value)
      if (debounceRef.current) clearTimeout(debounceRef.current)
      debounceRef.current = setTimeout(() => {
        onFiltersChange({ ...filters, search: value || undefined })
      }, 300)
    },
    [filters, onFiltersChange],
  )

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [])

  // -- Helpers
  const setFilter = useCallback(
    (key: string, value: string | boolean | undefined) => {
      onFiltersChange({ ...filters, [key]: value })
    },
    [filters, onFiltersChange],
  )

  const toggleBoolean = useCallback(
    (key: string) => {
      const current = filters[key]
      onFiltersChange({
        ...filters,
        [key]: current === true ? undefined : true,
      })
    },
    [filters, onFiltersChange],
  )

  const clearAll = useCallback(() => {
    setSearchValue('')
    onFiltersChange({})
  }, [onFiltersChange])

  // -- Active count
  const activeCount = Object.values(filters).filter(
    (v) => v !== undefined && v !== '' && v !== false,
  ).length

  return (
    <div className="flex flex-wrap items-end gap-2">
      {/* Date From */}
      <div className="flex flex-col gap-1">
        <label className="text-xs text-muted-foreground">
          {t('filters.date_from')}
        </label>
        <Input
          type="date"
          value={(filters.date_from as string) ?? ''}
          onChange={(e) => setFilter('date_from', e.target.value || undefined)}
          className="h-8 w-[140px] text-xs"
          disabled={loading}
        />
      </div>

      {/* Date To */}
      <div className="flex flex-col gap-1">
        <label className="text-xs text-muted-foreground">
          {t('filters.date_to')}
        </label>
        <Input
          type="date"
          value={(filters.date_to as string) ?? ''}
          onChange={(e) => setFilter('date_to', e.target.value || undefined)}
          className="h-8 w-[140px] text-xs"
          disabled={loading}
        />
      </div>

      {/* Agent */}
      {agents && agents.length > 0 && (
        <div className="flex flex-col gap-1">
          <label className="text-xs text-muted-foreground">
            {t('filters.agent')}
          </label>
          <Select
            value={(filters.agent_id as string) ?? SENTINEL_ALL}
            onValueChange={(v) =>
              setFilter('agent_id', v === SENTINEL_ALL ? undefined : v)
            }
            disabled={loading}
          >
            <SelectTrigger className="h-8 w-[160px] text-xs">
              <SelectValue placeholder={t('filters.all_agents')} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={SENTINEL_ALL}>{t('filters.all_agents')}</SelectItem>
              {agents.map((a) => (
                <SelectItem key={a.id} value={a.id}>
                  {a.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}

      {/* Zone */}
      {zones && zones.length > 0 && (
        <div className="flex flex-col gap-1">
          <label className="text-xs text-muted-foreground">
            {t('filters.zone')}
          </label>
          <Select
            value={(filters.zone as string) ?? SENTINEL_ALL}
            onValueChange={(v) =>
              setFilter('zone', v === SENTINEL_ALL ? undefined : v)
            }
            disabled={loading}
          >
            <SelectTrigger className="h-8 w-[140px] text-xs">
              <SelectValue placeholder={t('filters.all_zones')} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={SENTINEL_ALL}>{t('filters.all_zones')}</SelectItem>
              {zones.map((z) => (
                <SelectItem key={z.code} value={z.code}>
                  {z.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}

      {/* Result */}
      <div className="flex flex-col gap-1">
        <label className="text-xs text-muted-foreground">
          {t('filters.result')}
        </label>
        <Select
          value={(filters.result as string) ?? SENTINEL_ALL}
          onValueChange={(v) =>
            setFilter('result', v === SENTINEL_ALL ? undefined : v)
          }
          disabled={loading}
        >
          <SelectTrigger className="h-8 w-[140px] text-xs">
            <SelectValue placeholder={t('filters.all_results')} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={SENTINEL_ALL}>{t('filters.all_results')}</SelectItem>
            {ALL_RESULTS.map((r) => (
              <SelectItem key={r} value={r}>
                {t(`result.${r}`)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Status */}
      <div className="flex flex-col gap-1">
        <label className="text-xs text-muted-foreground">
          {t('filters.status')}
        </label>
        <Select
          value={(filters.status as string) ?? SENTINEL_ALL}
          onValueChange={(v) =>
            setFilter('status', v === SENTINEL_ALL ? undefined : v)
          }
          disabled={loading}
        >
          <SelectTrigger className="h-8 w-[150px] text-xs">
            <SelectValue placeholder={t('filters.all_statuses')} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={SENTINEL_ALL}>{t('filters.all_statuses')}</SelectItem>
            {ALL_STATUSES.map((s) => (
              <SelectItem key={s} value={s}>
                {t(`status.${s}`)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Search */}
      <div className="flex flex-col gap-1">
        <label className="text-xs text-muted-foreground">
          {t('filters.search')}
        </label>
        <div className="relative">
          <Search className="absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={searchValue}
            onChange={(e) => handleSearchChange(e.target.value)}
            placeholder={t('filters.search_placeholder')}
            className="h-8 w-[180px] pl-7 text-xs"
            disabled={loading}
          />
        </div>
      </div>

      {/* Boolean toggles */}
      <div className="flex items-end gap-1">
        {BOOLEAN_TOGGLES.map(({ key, labelKey }) => (
          <Button
            key={key}
            type="button"
            variant={filters[key] === true ? 'default' : 'outline'}
            size="sm"
            className={cn(
              'h-8 px-2 text-xs',
              filters[key] === true && 'bg-primary text-primary-foreground',
            )}
            onClick={() => toggleBoolean(key)}
            disabled={loading}
          >
            {t(labelKey)}
          </Button>
        ))}
      </div>

      {/* Clear + badge */}
      <div className="flex items-end gap-1.5">
        {activeCount > 0 && (
          <>
            <Badge variant="secondary" className="h-6 text-xs">
              {activeCount}
            </Badge>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-8 px-2 text-xs text-muted-foreground"
              onClick={clearAll}
              disabled={loading}
            >
              <X className="mr-1 h-3.5 w-3.5" />
              {t('filters.clear')}
            </Button>
          </>
        )}
      </div>
    </div>
  )
}
