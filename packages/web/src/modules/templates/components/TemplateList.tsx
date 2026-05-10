/**
 * TemplateList Component
 * Displays a grid of templates
 *
 * @module templates/components
 */

'use client'

import { useTranslations } from 'next-intl'
import { Loader2, AlertCircle } from 'lucide-react'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { TemplateCard } from './TemplateCard'
import { useDocumentTemplates } from '../hooks/useDocumentTemplates'
import { useProcedureTemplates } from '../hooks/useProcedureTemplates'
import type { TemplateListProps } from '../types'

export function TemplateList({
  type,
  filters,
  onSelect,
}: TemplateListProps) {
  const t = useTranslations('templates')

  const documentQuery = useDocumentTemplates(
    type === 'document'
      ? {
          category: filters?.category,
          isActive: filters?.isActive,
        }
      : undefined
  )

  const procedureQuery = useProcedureTemplates(
    type === 'procedure'
      ? {
          category: filters?.category,
          isActive: filters?.isActive,
        }
      : undefined
  )

  const { data, isLoading, error } =
    type === 'document' ? documentQuery : procedureQuery

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
        <span className="ml-3 text-muted-foreground">{t('loading')}</span>
      </div>
    )
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>
          {t('errorLoading')}: {error.message}
        </AlertDescription>
      </Alert>
    )
  }

  if (!data || data.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-muted-foreground">{t('noTemplates')}</p>
      </div>
    )
  }

  // Filter by search if provided
  // Cast to any[] to handle union type filtering
  let filteredData: any[] = data as any[]
  if (filters?.search) {
    const searchLower = filters.search.toLowerCase()
    filteredData = filteredData.filter(
      (template) =>
        template.name?.toLowerCase().includes(searchLower) ||
        template.description?.toLowerCase().includes(searchLower)
    )
  }

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      {filteredData.map((template: any) => (
        <TemplateCard
          key={template.id}
          id={template.id}
          name={template.name || template.title}
          description={template.description}
          category={template.category}
          isActive={template.is_active ?? true}
          type={type}
          onClick={() => onSelect?.(template.id)}
        />
      ))}
    </div>
  )
}
