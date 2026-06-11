'use client'

import { useCallback, useMemo, useState } from 'react'
import { useTranslations } from 'next-intl'
import { AlertTriangle, ArrowDown, ArrowUp, ArrowUpDown, MapPin, ShieldCheck } from 'lucide-react'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/core/utils'
import type { ZoneAnalyticsItem } from '../types'
import { fmtXAF } from '../utils/formatters'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ZoneAnalyticsTableProps {
  data: ZoneAnalyticsItem[]
  loading?: boolean
  summary?: { total_zones: number; covered_zones: number; stale_zones: number }
}

type SortField = keyof ZoneAnalyticsItem
type SortDir = 'asc' | 'desc'

interface ColumnDef {
  key: SortField
  labelKey: string
  align?: 'left' | 'right' | 'center'
  minW?: string
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const COLUMNS: ColumnDef[] = [
  { key: 'zone_code', labelKey: 'zone.zone', align: 'left', minW: 'min-w-[140px]' },
  { key: 'zone_tier', labelKey: 'zone.tier', align: 'center' },
  { key: 'inspections', labelKey: 'zone.inspections', align: 'right' },
  { key: 'conformity_rate', labelKey: 'zone.conformity', align: 'right', minW: 'min-w-[120px]' },
  { key: 'collections', labelKey: 'zone.collections', align: 'right' },
  { key: 'collected_amount', labelKey: 'zone.amount', align: 'right', minW: 'min-w-[100px]' },
  { key: 'med_count', labelKey: 'zone.med', align: 'right' },
  { key: 'seal_count', labelKey: 'zone.seals', align: 'right' },
  { key: 'agents_active', labelKey: 'zone.agents', align: 'right' },
  { key: 'days_since_last_inspection', labelKey: 'zone.last_inspection', align: 'right', minW: 'min-w-[120px]' },
]

const SKELETON_ROWS = 8

const TIER_COLORS: Record<string, { dot: string; text: string }> = {
  A: { dot: 'bg-blue-500', text: 'text-blue-700' },
  B: { dot: 'bg-green-500', text: 'text-green-700' },
  C: { dot: 'bg-yellow-500', text: 'text-yellow-700' },
  D: { dot: 'bg-red-500', text: 'text-red-700' },
}

const COVERAGE_CONFIG: Record<
  string,
  { variant: 'default' | 'secondary' | 'destructive' | 'outline'; labelKey: string }
> = {
  ok: { variant: 'default', labelKey: 'zone.coverage_ok' },
  warning: { variant: 'secondary', labelKey: 'zone.coverage_warning' },
  critical: { variant: 'destructive', labelKey: 'zone.coverage_critical' },
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function compare(
  a: ZoneAnalyticsItem,
  b: ZoneAnalyticsItem,
  field: SortField,
  dir: SortDir,
): number {
  const va = a[field]
  const vb = b[field]
  let cmp = 0
  if (typeof va === 'string' && typeof vb === 'string') {
    cmp = va.localeCompare(vb)
  } else {
    cmp = ((va as number) ?? 9999) - ((vb as number) ?? 9999)
  }
  return dir === 'asc' ? cmp : -cmp
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function SummaryCards({
  summary,
  t,
}: {
  summary: { total_zones: number; covered_zones: number; stale_zones: number }
  t: (key: string) => string
}) {
  return (
    <div className="mb-3 grid grid-cols-3 gap-3">
      {/* Total zones */}
      <div className="flex items-center gap-2 rounded-lg border bg-card p-3">
        <MapPin className="h-5 w-5 text-muted-foreground" />
        <div>
          <p className="text-xs text-muted-foreground">{t('zone.total_zones')}</p>
          <p className="text-lg font-bold tabular-nums">{summary.total_zones}</p>
        </div>
      </div>

      {/* Covered */}
      <div className="flex items-center gap-2 rounded-lg border bg-card p-3">
        <ShieldCheck className="h-5 w-5 text-green-600" />
        <div>
          <p className="text-xs text-muted-foreground">{t('zone.covered_zones')}</p>
          <p className="text-lg font-bold tabular-nums text-green-700">
            {summary.covered_zones}
          </p>
        </div>
      </div>

      {/* Stale */}
      <div
        className={cn(
          'flex items-center gap-2 rounded-lg border p-3',
          summary.stale_zones > 0 ? 'border-red-200 bg-red-50' : 'bg-card',
        )}
      >
        <AlertTriangle
          className={cn(
            'h-5 w-5',
            summary.stale_zones > 0 ? 'text-red-600' : 'text-muted-foreground',
          )}
        />
        <div>
          <p className="text-xs text-muted-foreground">{t('zone.stale_zones')}</p>
          <p
            className={cn(
              'text-lg font-bold tabular-nums',
              summary.stale_zones > 0 ? 'text-red-700' : '',
            )}
          >
            {summary.stale_zones}
          </p>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ZoneAnalyticsTable({
  data,
  loading,
  summary,
}: ZoneAnalyticsTableProps) {
  const t = useTranslations('inspection')
  const [sortField, setSortField] = useState<SortField>('inspections')
  const [sortDir, setSortDir] = useState<SortDir>('desc')

  const toggleSort = useCallback(
    (field: SortField) => {
      if (sortField === field) {
        setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
      } else {
        setSortField(field)
        setSortDir('desc')
      }
    },
    [sortField],
  )

  const sorted = useMemo(
    () => [...data].sort((a, b) => compare(a, b, sortField, sortDir)),
    [data, sortField, sortDir],
  )

  const SortIcon = useCallback(
    ({ field }: { field: SortField }) => {
      if (sortField !== field)
        return <ArrowUpDown className="ml-1 inline h-3 w-3 text-muted-foreground/50" />
      return sortDir === 'asc' ? (
        <ArrowUp className="ml-1 inline h-3 w-3" />
      ) : (
        <ArrowDown className="ml-1 inline h-3 w-3" />
      )
    },
    [sortField, sortDir],
  )

  // -- Loading skeleton
  if (loading) {
    return (
      <div>
        {summary && (
          <div className="mb-3 grid grid-cols-3 gap-3">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-[72px] rounded-lg" />
            ))}
          </div>
        )}
        <div className="w-full overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                {COLUMNS.map((col) => (
                  <TableHead key={col.key} className="text-xs">
                    {t(col.labelKey)}
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {Array.from({ length: SKELETON_ROWS }).map((_, i) => (
                <TableRow key={i}>
                  {COLUMNS.map((col) => (
                    <TableCell key={col.key}>
                      <Skeleton className="h-4 w-full" />
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </div>
    )
  }

  // -- Empty state
  if (data.length === 0) {
    return (
      <div>
        {summary && <SummaryCards summary={summary} t={t} />}
        <div className="flex h-32 items-center justify-center text-sm text-muted-foreground">
          {t('zone.empty')}
        </div>
      </div>
    )
  }

  return (
    <div>
      {summary && <SummaryCards summary={summary} t={t} />}

      <div className="w-full overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              {COLUMNS.map((col) => (
                <TableHead
                  key={col.key}
                  className={cn(
                    'cursor-pointer select-none whitespace-nowrap text-xs',
                    col.minW,
                    col.align === 'right' && 'text-right',
                    col.align === 'center' && 'text-center',
                  )}
                  onClick={() => toggleSort(col.key)}
                >
                  {t(col.labelKey)}
                  <SortIcon field={col.key} />
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {sorted.map((row, idx) => {
              const tier = TIER_COLORS[row.zone_tier] ?? TIER_COLORS.D
              const coverage = COVERAGE_CONFIG[row.coverage_status] ?? COVERAGE_CONFIG.critical

              return (
                <TableRow key={row.zone_id ?? `zone-${idx}`}>
                  {/* Zone code + name */}
                  <TableCell className="whitespace-nowrap text-sm">
                    <span className="font-medium">{row.zone_code}</span>
                    {row.zone_name && (
                      <span className="ml-1.5 text-muted-foreground">
                        {row.zone_name}
                      </span>
                    )}
                  </TableCell>

                  {/* Tier */}
                  <TableCell className="text-center">
                    <div className="flex items-center justify-center gap-1.5">
                      <span
                        className={cn(
                          'inline-block h-2.5 w-2.5 rounded-full',
                          tier.dot,
                        )}
                      />
                      <span className={cn('text-xs font-semibold', tier.text)}>
                        {row.zone_tier}
                      </span>
                    </div>
                  </TableCell>

                  {/* Inspections */}
                  <TableCell className="text-right text-sm tabular-nums">
                    {row.inspections}
                  </TableCell>

                  {/* Conformity rate with progress bar */}
                  <TableCell className="text-right text-sm">
                    <div className="flex items-center justify-end gap-2">
                      <div className="h-2 w-16 rounded-full bg-muted">
                        <div
                          className={cn(
                            'h-full rounded-full',
                            row.conformity_rate >= 80
                              ? 'bg-green-500'
                              : row.conformity_rate >= 60
                                ? 'bg-yellow-500'
                                : 'bg-red-500',
                          )}
                          style={{ width: `${Math.min(row.conformity_rate, 100)}%` }}
                        />
                      </div>
                      <span className="tabular-nums">
                        {row.conformity_rate.toFixed(1)}%
                      </span>
                    </div>
                  </TableCell>

                  {/* Collections */}
                  <TableCell className="text-right text-sm tabular-nums">
                    {row.collections}
                  </TableCell>

                  {/* Amount */}
                  <TableCell className="whitespace-nowrap text-right text-sm tabular-nums">
                    {fmtXAF(row.collected_amount)}
                  </TableCell>

                  {/* MED / Seals combined */}
                  <TableCell className="text-right text-sm tabular-nums">
                    {row.med_count}
                  </TableCell>
                  <TableCell className="text-right text-sm tabular-nums">
                    {row.seal_count}
                  </TableCell>

                  {/* Agents active */}
                  <TableCell className="text-right text-sm tabular-nums">
                    {row.agents_active}
                  </TableCell>

                  {/* Last inspection (days ago + coverage badge) */}
                  <TableCell className="text-right text-sm">
                    <div className="flex items-center justify-end gap-2">
                      <span className="tabular-nums">
                        {row.days_since_last_inspection != null
                          ? `${row.days_since_last_inspection}d`
                          : '-'}
                      </span>
                      <Badge
                        variant={coverage.variant}
                        className={cn(
                          'text-[10px] px-1.5 py-0',
                          coverage.variant === 'default' &&
                            'bg-green-100 text-green-800 hover:bg-green-100',
                          coverage.variant === 'secondary' &&
                            'bg-yellow-100 text-yellow-800 hover:bg-yellow-100',
                        )}
                      >
                        {t(coverage.labelKey)}
                      </Badge>
                    </div>
                  </TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
