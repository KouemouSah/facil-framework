/**
 * TemplateFilters Component
 * Filter controls for template lists
 *
 * @module templates/components
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
import type { TemplateFilters as FilterType } from '../types'

interface TemplateFiltersProps {
  filters: FilterType
  onFiltersChange: (filters: FilterType) => void
  categories?: string[]
}

export function TemplateFilters({
  filters,
  onFiltersChange,
  categories = [],
}: TemplateFiltersProps) {
  const t = useTranslations('templates')

  const handleSearchChange = (value: string) => {
    onFiltersChange({ ...filters, search: value })
  }

  const handleCategoryChange = (value: string) => {
    onFiltersChange({
      ...filters,
      category: value === 'all' ? undefined : value,
    })
  }

  const handleActiveChange = (value: string) => {
    onFiltersChange({
      ...filters,
      isActive: value === 'all' ? undefined : value === 'active',
    })
  }

  const clearFilters = () => {
    onFiltersChange({})
  }

  const hasFilters =
    filters.search || filters.category || filters.isActive !== undefined

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
        value={filters.category || 'all'}
        onValueChange={handleCategoryChange}
      >
        <SelectTrigger className="w-full md:w-[180px]">
          <SelectValue placeholder={t('filters.category')} />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">{t('filters.allCategories')}</SelectItem>
          {categories.map((cat) => (
            <SelectItem key={cat} value={cat}>
              {cat}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Select
        value={
          filters.isActive === undefined
            ? 'all'
            : filters.isActive
            ? 'active'
            : 'inactive'
        }
        onValueChange={handleActiveChange}
      >
        <SelectTrigger className="w-full md:w-[150px]">
          <SelectValue placeholder={t('filters.status')} />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">{t('filters.allStatus')}</SelectItem>
          <SelectItem value="active">{t('filters.activeOnly')}</SelectItem>
          <SelectItem value="inactive">{t('filters.inactiveOnly')}</SelectItem>
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
