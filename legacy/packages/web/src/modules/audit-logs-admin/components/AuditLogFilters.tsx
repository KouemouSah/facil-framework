/**
 * AuditLogFilters Component
 * Filter controls for audit log lists
 *
 * @module audit-logs-admin/components
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
import { Search, X, Calendar } from 'lucide-react'
import type { AuditAction } from '../types'

interface AuditLogFiltersState {
  action?: AuditAction
  success?: boolean
  start_date?: string
  end_date?: string
  search?: string
}

interface AuditLogFiltersProps {
  filters: AuditLogFiltersState
  onFiltersChange: (filters: AuditLogFiltersState) => void
}

const actions: AuditAction[] = [
  'user.login',
  'user.logout',
  'user.register',
  'user.update',
  'user.delete',
  'role.create',
  'role.update',
  'role.delete',
  'permission.grant',
  'permission.revoke',
  'settings.update',
  'declaration.create',
  'declaration.update',
  'declaration.submit',
  'declaration.approve',
  'declaration.reject',
]

export function AuditLogFilters({
  filters,
  onFiltersChange,
}: AuditLogFiltersProps) {
  const t = useTranslations('auditLogs')

  const handleSearchChange = (value: string) => {
    onFiltersChange({ ...filters, search: value })
  }

  const handleActionChange = (value: string) => {
    onFiltersChange({
      ...filters,
      action: value === 'all' ? undefined : (value as AuditAction),
    })
  }

  const handleSuccessChange = (value: string) => {
    onFiltersChange({
      ...filters,
      success: value === 'all' ? undefined : value === 'success',
    })
  }

  const handleDateChange = (field: 'start_date' | 'end_date', value: string) => {
    onFiltersChange({ ...filters, [field]: value || undefined })
  }

  const clearFilters = () => {
    onFiltersChange({})
  }

  const hasFilters =
    filters.search ||
    filters.action ||
    filters.success !== undefined ||
    filters.start_date ||
    filters.end_date

  return (
    <div className="space-y-4">
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
          value={filters.action || 'all'}
          onValueChange={handleActionChange}
        >
          <SelectTrigger className="w-full md:w-[200px]">
            <SelectValue placeholder={t('filters.action')} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t('filters.allActions')}</SelectItem>
            {actions.map((action) => (
              <SelectItem key={action} value={action}>
                {t(`actions.${action.replace('.', '_')}`)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select
          value={
            filters.success === undefined
              ? 'all'
              : filters.success
              ? 'success'
              : 'failure'
          }
          onValueChange={handleSuccessChange}
        >
          <SelectTrigger className="w-full md:w-[150px]">
            <SelectValue placeholder={t('filters.result')} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t('filters.allResults')}</SelectItem>
            <SelectItem value="success">{t('filters.successOnly')}</SelectItem>
            <SelectItem value="failure">{t('filters.failureOnly')}</SelectItem>
          </SelectContent>
        </Select>

        {hasFilters && (
          <Button variant="ghost" size="sm" onClick={clearFilters}>
            <X className="h-4 w-4 mr-1" />
            {t('filters.clear')}
          </Button>
        )}
      </div>

      <div className="flex flex-col gap-4 md:flex-row md:items-center">
        <div className="flex items-center gap-2">
          <Calendar className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm text-muted-foreground">{t('filters.from')}</span>
          <Input
            type="date"
            value={filters.start_date || ''}
            onChange={(e) => handleDateChange('start_date', e.target.value)}
            className="w-auto"
          />
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">{t('filters.to')}</span>
          <Input
            type="date"
            value={filters.end_date || ''}
            onChange={(e) => handleDateChange('end_date', e.target.value)}
            className="w-auto"
          />
        </div>
      </div>
    </div>
  )
}
