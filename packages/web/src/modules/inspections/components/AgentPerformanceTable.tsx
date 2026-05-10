'use client'

import { useCallback, useMemo, useState } from 'react'
import { useTranslations } from 'next-intl'
import { ArrowDown, ArrowUp, ArrowUpDown } from 'lucide-react'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/core/utils'
import type { AgentPerformanceItem } from '../types'
import { fmtXAF } from '../utils/formatters'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface AgentPerformanceTableProps {
  data: AgentPerformanceItem[]
  loading?: boolean
  onAgentClick?: (agentId: string) => void
  dateRange?: { from: string; to: string }
}

type SortField = keyof AgentPerformanceItem
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
  { key: 'agent_name', labelKey: 'perf.agent', align: 'left', minW: 'min-w-[120px]' },
  { key: 'inspections_total', labelKey: 'perf.inspections', align: 'right' },
  { key: 'conforme', labelKey: 'perf.conforme', align: 'right' },
  { key: 'non_conforme', labelKey: 'perf.non_conforme', align: 'right' },
  { key: 'conformity_rate', labelKey: 'perf.conformity_rate', align: 'right' },
  { key: 'collections_count', labelKey: 'perf.collections', align: 'right' },
  { key: 'collected_amount', labelKey: 'perf.amount', align: 'right', minW: 'min-w-[100px]' },
  { key: 'med_count', labelKey: 'perf.med', align: 'right' },
  { key: 'seal_count', labelKey: 'perf.seals', align: 'right' },
  { key: 'avg_duration_minutes', labelKey: 'perf.avg_duration', align: 'right' },
  { key: 'zones_covered', labelKey: 'perf.zones', align: 'right' },
  { key: 'days_active', labelKey: 'perf.days_active', align: 'right' },
]

const SKELETON_ROWS = 8

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function conformityColor(rate: number): string {
  if (rate >= 80) return 'text-green-700'
  if (rate >= 60) return 'text-yellow-700'
  return 'text-red-700'
}

function conformityBg(rate: number): string {
  if (rate >= 80) return 'bg-green-500'
  if (rate >= 60) return 'bg-yellow-500'
  return 'bg-red-500'
}

function compare(
  a: AgentPerformanceItem,
  b: AgentPerformanceItem,
  field: SortField,
  dir: SortDir,
): number {
  const va = a[field]
  const vb = b[field]
  let cmp = 0
  if (typeof va === 'string' && typeof vb === 'string') {
    cmp = va.localeCompare(vb)
  } else {
    cmp = ((va as number) ?? 0) - ((vb as number) ?? 0)
  }
  return dir === 'asc' ? cmp : -cmp
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function AgentPerformanceTable({
  data,
  loading,
  onAgentClick,
}: AgentPerformanceTableProps) {
  const t = useTranslations('inspection')
  const [sortField, setSortField] = useState<SortField>('inspections_total')
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

  // -- Sort icon
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
    )
  }

  // -- Empty state
  if (data.length === 0) {
    return (
      <div className="flex h-32 items-center justify-center text-sm text-muted-foreground">
        {t('perf.empty')}
      </div>
    )
  }

  return (
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
          {sorted.map((row) => (
            <TableRow key={row.agent_id}>
              {/* Agent name (clickable) */}
              <TableCell className="whitespace-nowrap text-sm font-medium">
                {onAgentClick ? (
                  <button
                    type="button"
                    onClick={() => onAgentClick(row.agent_id)}
                    className="text-left text-primary underline-offset-2 hover:underline"
                  >
                    {row.agent_name}
                  </button>
                ) : (
                  row.agent_name
                )}
              </TableCell>

              {/* Inspections total */}
              <TableCell className="text-right text-sm tabular-nums">
                {row.inspections_total}
              </TableCell>

              {/* Conforme with bar */}
              <TableCell className="text-right text-sm">
                <div className="flex items-center justify-end gap-1.5">
                  <span className="tabular-nums">{row.conforme}</span>
                  {row.inspections_total > 0 && (
                    <div className="h-2 w-12 rounded-full bg-muted">
                      <div
                        className="h-full rounded-full bg-green-500"
                        style={{
                          width: `${Math.round((row.conforme / row.inspections_total) * 100)}%`,
                        }}
                      />
                    </div>
                  )}
                </div>
              </TableCell>

              {/* Non conforme */}
              <TableCell className="text-right text-sm tabular-nums">
                {row.non_conforme}
              </TableCell>

              {/* Conformity rate */}
              <TableCell
                className={cn(
                  'text-right text-sm font-semibold tabular-nums',
                  conformityColor(row.conformity_rate),
                )}
              >
                <div className="flex items-center justify-end gap-1.5">
                  <span
                    className={cn(
                      'inline-block h-2 w-2 rounded-full',
                      conformityBg(row.conformity_rate),
                    )}
                  />
                  {row.conformity_rate.toFixed(1)}%
                </div>
              </TableCell>

              {/* Collections */}
              <TableCell className="text-right text-sm tabular-nums">
                {row.collections_count}
              </TableCell>

              {/* Amount */}
              <TableCell className="whitespace-nowrap text-right text-sm tabular-nums">
                {fmtXAF(row.collected_amount)}
              </TableCell>

              {/* MED */}
              <TableCell className="text-right text-sm tabular-nums">
                {row.med_count}
              </TableCell>

              {/* Seals */}
              <TableCell className="text-right text-sm tabular-nums">
                {row.seal_count}
              </TableCell>

              {/* Avg duration */}
              <TableCell className="text-right text-sm tabular-nums">
                {row.avg_duration_minutes != null
                  ? `${Math.round(row.avg_duration_minutes)} min`
                  : '-'}
              </TableCell>

              {/* Zones */}
              <TableCell className="text-right text-sm tabular-nums">
                {row.zones_covered}
              </TableCell>

              {/* Days active */}
              <TableCell className="text-right text-sm tabular-nums">
                {row.days_active}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
