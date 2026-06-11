/**
 * AssignmentFilters Component
 * Filter controls for assignment lists
 *
 * @module assignments-admin/components
 * @date 2026-01-20
 *
 * BACKEND ALIGNMENT:
 * - Migration 053: item_id, item_type
 * - Migration 054: agent_profile_id
 */

'use client'

import { useTranslations } from 'next-intl'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Search, X } from 'lucide-react'
import type { AssignmentStatus } from '../types'

interface AssignmentFiltersState {
  status?: AssignmentStatus
  agent_profile_id?: string
  search?: string
}

interface AssignmentFiltersProps {
  filters: AssignmentFiltersState
  onFiltersChange: (filters: AssignmentFiltersState) => void
}

// Valid statuses from assignment_status_enum (DATABASE_SCHEMA_REFERENCE.md)
const statuses: AssignmentStatus[] = [
  'assigned',
  'in_progress',
  'pending_review',
  'completed',
  'reassigned',
  'cancelled',
  'rejected',
]

export function AssignmentFilters({
  filters,
  onFiltersChange,
}: AssignmentFiltersProps) {
  const t = useTranslations('assignments')

  const handleSearchChange = (value: string) => {
    onFiltersChange({ ...filters, search: value })
  }

  const handleStatusChange = (value: string) => {
    onFiltersChange({
      ...filters,
      status: value === 'all' ? undefined : (value as AssignmentStatus),
    })
  }

  const clearFilters = () => {
    onFiltersChange({})
  }

  const hasFilters = filters.search || filters.status || filters.agent_profile_id

  return (
    <div className="flex flex-col gap-4 md:flex-row md:items-center">
      <div className="relative flex-1">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          placeholder={t('filters.searchPlaceholder')}
          value={filters.search || ''}
          onChange={(e) => handleSearchChange(e.target.value)}
          className="pl-10"
        />
      </div>

      <Select
        value={filters.status || 'all'}
        onValueChange={handleStatusChange}
      >
        <SelectTrigger className="w-full md:w-[180px]">
          <SelectValue placeholder={t('filters.status')} />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">{t('filters.allStatuses')}</SelectItem>
          {statuses.map((status) => (
            <SelectItem key={status} value={status}>
              {t(`status.${status}`)}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {hasFilters && (
        <Button variant="ghost" size="sm" onClick={clearFilters}>
          <X className="h-4 w-4 mr-1" />
          {t('filters.clear')}
        </Button>
      )}
    </div>
  )
}
