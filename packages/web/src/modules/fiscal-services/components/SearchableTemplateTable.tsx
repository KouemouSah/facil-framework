'use client'

/**
 * SearchableTemplateTable Component
 * Reusable table for searching and selecting document/procedure templates
 * with pagination, filtering, and multi-select functionality
 *
 * IMPORTANT: Table only shows AFTER user performs a search (text or category filter)
 * This prevents showing 700+ results immediately on load
 */

import { useState, useMemo, useCallback, useEffect } from 'react'
import { useTranslations } from 'next-intl'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Search,
  FileText,
  Link2,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  Plus,
  X,
} from 'lucide-react'
import type { DocumentTemplate, ProcedureTemplate } from '@/types/fiscal-service'

interface SearchableTemplateTableProps {
  type: 'document' | 'procedure'
  templates: DocumentTemplate[] | ProcedureTemplate[]
  excludeIds: number[]
  onAssign: (selectedIds: number[], options?: Record<string, boolean | string>) => void
  locale?: string // Reserved for future i18n support
  isAssigning?: boolean
}

const ITEMS_PER_PAGE = 10

export function SearchableTemplateTable({
  type,
  templates,
  excludeIds,
  onAssign,
  locale: _locale,
  isAssigning = false,
}: SearchableTemplateTableProps) {
  const t = useTranslations('admin.fiscalServices')

  // Search and filter state
  const [searchQuery, setSearchQuery] = useState('')
  const [categoryFilter, setCategoryFilter] = useState<string>('all')
  const [currentPage, setCurrentPage] = useState(1)
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())

  // Document-specific assignment options
  const [isRequiredExpedition, setIsRequiredExpedition] = useState(true)
  const [isRequiredRenewal, setIsRequiredRenewal] = useState(false)

  // Procedure-specific assignment options
  const [appliesTo, setAppliesTo] = useState<string>('both')

  // Determine if user has started searching (text or category)
  const hasSearched = searchQuery.trim().length > 0 || categoryFilter !== 'all'

  // Get available templates (excluding already assigned)
  const availableTemplates = useMemo(() => {
    return templates.filter(t => !excludeIds.includes(t.id))
  }, [templates, excludeIds])

  // Get unique categories for filter dropdown
  const categories = useMemo(() => {
    const cats = new Set<string>()
    availableTemplates.forEach(t => {
      const category = t.category
      if (category) cats.add(category)
    })
    return Array.from(cats).sort()
  }, [availableTemplates])

  // Filter templates by search query and category
  const filteredTemplates = useMemo(() => {
    // If no search performed yet, return empty array
    if (!hasSearched) return []

    const query = searchQuery.toLowerCase().trim()

    return availableTemplates.filter(template => {
      // Category filter
      if (categoryFilter !== 'all' && template.category !== categoryFilter) {
        return false
      }

      // Search filter
      if (query) {
        const code = (template.templateCode || '').toLowerCase()
        const name = type === 'document'
          ? ((template as DocumentTemplate).documentNameEs || '').toLowerCase()
          : ((template as ProcedureTemplate).nameEs || '').toLowerCase()
        const description = type === 'document'
          ? ((template as DocumentTemplate).descriptionEs || '').toLowerCase()
          : ((template as ProcedureTemplate).descriptionEs || '').toLowerCase()
        const category = (template.category || '').toLowerCase()

        const matches = code.includes(query) ||
          name.includes(query) ||
          description.includes(query) ||
          category.includes(query)

        if (!matches) return false
      }

      return true
    })
  }, [availableTemplates, searchQuery, categoryFilter, type, hasSearched])

  // Pagination calculations
  const totalPages = Math.ceil(filteredTemplates.length / ITEMS_PER_PAGE)
  const startIndex = (currentPage - 1) * ITEMS_PER_PAGE
  const endIndex = startIndex + ITEMS_PER_PAGE
  const paginatedTemplates = filteredTemplates.slice(startIndex, endIndex)

  // Reset page when filters change
  useEffect(() => {
    setCurrentPage(1)
  }, [searchQuery, categoryFilter])

  // Toggle single item selection
  const toggleSelection = useCallback((id: number) => {
    setSelectedIds(prev => {
      const newSet = new Set(prev)
      if (newSet.has(id)) {
        newSet.delete(id)
      } else {
        newSet.add(id)
      }
      return newSet
    })
  }, [])

  // Toggle all items on current page
  const toggleAllOnPage = useCallback(() => {
    const pageIds = paginatedTemplates.map(t => t.id)
    const allSelected = pageIds.every(id => selectedIds.has(id))

    setSelectedIds(prev => {
      const newSet = new Set(prev)
      if (allSelected) {
        pageIds.forEach(id => newSet.delete(id))
      } else {
        pageIds.forEach(id => newSet.add(id))
      }
      return newSet
    })
  }, [paginatedTemplates, selectedIds])

  // Clear selection
  const clearSelection = useCallback(() => {
    setSelectedIds(new Set())
  }, [])

  // Handle assignment
  const handleAssign = useCallback(() => {
    if (selectedIds.size === 0) return

    const options: Record<string, boolean | string> = type === 'document'
      ? { isRequiredExpedition, isRequiredRenewal }
      : { appliesTo }

    onAssign(Array.from(selectedIds), options)
    setSelectedIds(new Set())
  }, [selectedIds, type, isRequiredExpedition, isRequiredRenewal, appliesTo, onAssign])

  // Get template display name
  const getTemplateName = (template: DocumentTemplate | ProcedureTemplate): string => {
    if (type === 'document') {
      return (template as DocumentTemplate).documentNameEs || template.templateCode || `Doc #${template.id}`
    }
    return (template as ProcedureTemplate).nameEs || template.templateCode || `Proc #${template.id}`
  }

  // Get template description
  const getTemplateDescription = (template: DocumentTemplate | ProcedureTemplate): string => {
    if (type === 'document') {
      return (template as DocumentTemplate).descriptionEs || ''
    }
    return (template as ProcedureTemplate).descriptionEs || ''
  }

  const allOnPageSelected = paginatedTemplates.length > 0 &&
    paginatedTemplates.every(t => selectedIds.has(t.id))
  const someOnPageSelected = paginatedTemplates.some(t => selectedIds.has(t.id))

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          {type === 'document' ? (
            <FileText className="h-4 w-4" />
          ) : (
            <Link2 className="h-4 w-4" />
          )}
          {type === 'document' ? t('searchDocuments') : t('searchProcedures')}
          <Badge variant="outline" className="ml-2 font-normal">
            {availableTemplates.length} {t('available') || 'disponibles'}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Search and Filter Row */}
        <div className="flex gap-3 flex-wrap">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder={t('searchPlaceholder') || 'Código, nombre, palabra clave...'}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9"
            />
          </div>
          <Select value={categoryFilter} onValueChange={setCategoryFilter}>
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder={t('filterByCategory')} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t('allCategories')}</SelectItem>
              {categories.map(cat => (
                <SelectItem key={cat} value={cat}>{cat}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Initial State - Before Search */}
        {!hasSearched ? (
          <div className="flex flex-col items-center justify-center py-12 text-muted-foreground border-2 border-dashed rounded-lg">
            <Search className="h-12 w-12 mb-4 opacity-30" />
            <p className="text-sm font-medium">
              {t('searchToShowResults') || 'Escribe para buscar'}
            </p>
            <p className="text-xs mt-1">
              {type === 'document'
                ? (t('searchDocumentsHint', { count: availableTemplates.length }) || `${availableTemplates.length} documentos disponibles`)
                : (t('searchProceduresHint', { count: availableTemplates.length }) || `${availableTemplates.length} procedimientos disponibles`)
              }
            </p>
          </div>
        ) : filteredTemplates.length === 0 ? (
          /* No Results After Search */
          <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
            {type === 'document' ? (
              <FileText className="h-10 w-10 mb-2 opacity-50" />
            ) : (
              <Link2 className="h-10 w-10 mb-2 opacity-50" />
            )}
            <p className="text-sm">{t('noResults')}</p>
          </div>
        ) : (
          /* Results Table */
          <>
            <div className="border rounded-lg overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[40px]">
                      <Checkbox
                        checked={allOnPageSelected}
                        // @ts-expect-error - indeterminate is a valid prop
                        indeterminate={someOnPageSelected && !allOnPageSelected}
                        onCheckedChange={toggleAllOnPage}
                      />
                    </TableHead>
                    <TableHead className="w-[100px]">{t('tableCode') || 'Código'}</TableHead>
                    <TableHead>{t('tableName') || 'Nombre'}</TableHead>
                    <TableHead className="w-[120px]">{t('tableCategory') || 'Categoría'}</TableHead>
                    <TableHead className="hidden md:table-cell">{t('tableDescription') || 'Descripción'}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {paginatedTemplates.map(template => (
                    <TableRow
                      key={template.id}
                      className={`cursor-pointer ${selectedIds.has(template.id) ? 'bg-primary/5' : ''}`}
                      onClick={() => toggleSelection(template.id)}
                    >
                      <TableCell onClick={(e) => e.stopPropagation()}>
                        <Checkbox
                          checked={selectedIds.has(template.id)}
                          onCheckedChange={() => toggleSelection(template.id)}
                        />
                      </TableCell>
                      <TableCell className="font-mono text-xs">
                        {template.templateCode}
                      </TableCell>
                      <TableCell className="font-medium">
                        {getTemplateName(template)}
                      </TableCell>
                      <TableCell>
                        {template.category && (
                          <Badge variant="outline" className="text-xs">
                            {template.category}
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell className="hidden md:table-cell text-sm text-muted-foreground max-w-[200px] truncate">
                        {getTemplateDescription(template)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>

            {/* Pagination */}
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">
                {t('showingResults', {
                  start: filteredTemplates.length === 0 ? 0 : startIndex + 1,
                  end: Math.min(endIndex, filteredTemplates.length),
                  total: filteredTemplates.length,
                }) || `${startIndex + 1}-${Math.min(endIndex, filteredTemplates.length)} de ${filteredTemplates.length}`}
              </span>

              <div className="flex items-center gap-1">
                <Button
                  variant="outline"
                  size="sm"
                  className="h-8 w-8 p-0"
                  onClick={() => setCurrentPage(1)}
                  disabled={currentPage === 1}
                >
                  <ChevronsLeft className="h-4 w-4" />
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-8 w-8 p-0"
                  onClick={() => setCurrentPage(p => p - 1)}
                  disabled={currentPage === 1}
                >
                  <ChevronLeft className="h-4 w-4" />
                </Button>
                <span className="px-2 min-w-[80px] text-center">
                  {currentPage} / {totalPages || 1}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-8 w-8 p-0"
                  onClick={() => setCurrentPage(p => p + 1)}
                  disabled={currentPage >= totalPages}
                >
                  <ChevronRight className="h-4 w-4" />
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-8 w-8 p-0"
                  onClick={() => setCurrentPage(totalPages)}
                  disabled={currentPage >= totalPages}
                >
                  <ChevronsRight className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </>
        )}

        {/* Selection and Assignment Options */}
        {selectedIds.size > 0 && (
          <div className="border-t pt-4 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Badge variant="secondary">
                  {selectedIds.size} {t('selected')}
                </Badge>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={clearSelection}
                  className="h-7 px-2 text-muted-foreground"
                >
                  <X className="h-3 w-3 mr-1" />
                  {t('clearSelection') || 'Limpiar'}
                </Button>
              </div>
            </div>

            {/* Document assignment options */}
            {type === 'document' && (
              <div className="flex items-center gap-4 text-sm">
                <label className="flex items-center gap-2">
                  <Checkbox
                    checked={isRequiredExpedition}
                    onCheckedChange={(checked) => setIsRequiredExpedition(checked === true)}
                  />
                  <span>{t('requiredForExpedition')}</span>
                </label>
                <label className="flex items-center gap-2">
                  <Checkbox
                    checked={isRequiredRenewal}
                    onCheckedChange={(checked) => setIsRequiredRenewal(checked === true)}
                  />
                  <span>{t('requiredForRenewal')}</span>
                </label>
              </div>
            )}

            {/* Procedure assignment options */}
            {type === 'procedure' && (
              <div className="flex items-center gap-2 text-sm">
                <span className="text-muted-foreground">{t('appliesTo')}:</span>
                <Select value={appliesTo} onValueChange={setAppliesTo}>
                  <SelectTrigger className="w-[150px] h-8">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="expedition">{t('expedition')}</SelectItem>
                    <SelectItem value="renewal">{t('renewal')}</SelectItem>
                    <SelectItem value="both">{t('both')}</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            )}

            <Button
              onClick={handleAssign}
              disabled={isAssigning || selectedIds.size === 0}
              className="w-full"
            >
              <Plus className="h-4 w-4 mr-2" />
              {t('assignSelected')} ({selectedIds.size})
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
