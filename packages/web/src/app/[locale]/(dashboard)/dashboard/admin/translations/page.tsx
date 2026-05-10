'use client'

/**
 * Translations Admin Page
 * Centralized translation management with 3 tabs:
 * 1. Entity Translations - ministry, sector, category translations
 * 2. System Translations - ENUMs, UI labels, forms, messages
 * 3. Frontend UI - next-intl JSON translations
 *
 * @page /dashboard/admin/translations
 */

import { useState } from 'react'
import { useLocale, useTranslations } from 'next-intl'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Languages,
  RefreshCw,
  Search,
  Building2,
  FileText,
  Globe,
  Trash2,
  CheckCircle,
  Loader2,
  Plus,
  Pencil,
  Wrench,
  Database,
  Archive,
  RotateCcw,
  AlertTriangle,
  Github,
} from 'lucide-react'
import { useToast } from '@/hooks/use-toast'
import {
  useEntityTranslations,
  useEntityTranslationStats,
  useSystemTranslations,
  useSystemCategories,
  useSystemGroups,
  useFrontendTranslations,
  useFrontendTranslationStats,
  useFrontendNamespaces,
  useDeleteEntityTranslation,
  useDeleteSystemTranslation,
  useDeleteFrontendTranslation,
  useUpsertEntityTranslation,
  useCreateSystemTranslation,
  useUpdateSystemTranslation,
  useUpdateFrontendTranslation,
  useCreateFrontendTranslation,
  useSyncFrontendFromJson,
  usePublishToGithub,
  useSourceEntities,
  useSourceContent,
  useEntityGroupedTranslations,
  useBulkUpsertEntityTranslations,
  useModifiableEnums,
  useEnumValues,
  useAddEnumValue,
  useUpdateEnumTranslation,
  useArchiveEnumValue,
  useRestoreEnumValue,
} from '@/modules/translations/hooks'
import type {
  TranslatableEntityType,
  LanguageCode,
  EntityTranslation,
  SystemTranslation,
  SystemCategory,
  TranslationGroup,
  ModifiableEnumType,
  EnumValueWithTranslation,
} from '@/modules/translations/types'
import { ENTITY_TYPE_OPTIONS, LANGUAGE_OPTIONS, MODIFIABLE_ENUM_OPTIONS } from '@/modules/translations/types'

// =============================================================================
// ENTITY TRANSLATIONS TAB
// =============================================================================

function EntityTranslationsTab() {
  const locale = useLocale() as LanguageCode
  const t = useTranslations('admin.translations')
  const { toast } = useToast()

  const [entityTypeFilter, setEntityTypeFilter] = useState<TranslatableEntityType | 'all'>('all')
  const [languageFilter, setLanguageFilter] = useState<LanguageCode | 'all'>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [page, setPage] = useState(0)
  const pageSize = 50

  // Edit modal state
  const [editModalOpen, setEditModalOpen] = useState(false)
  const [editingTranslation, setEditingTranslation] = useState<EntityTranslation | null>(null)
  const [editText, setEditText] = useState('')

  // Workbench modal state
  const [workbenchOpen, setWorkbenchOpen] = useState(false)
  const [workbenchEntityType, setWorkbenchEntityType] = useState<TranslatableEntityType | ''>('')
  const [workbenchEntityCode, setWorkbenchEntityCode] = useState('')
  const [workbenchSearch, setWorkbenchSearch] = useState('')
  const [workbenchTranslations, setWorkbenchTranslations] = useState<Record<string, { fr: string; en: string }>>({})
  const [workbenchUntranslatedOnly, setWorkbenchUntranslatedOnly] = useState(true) // Default to showing only untranslated

  // Workbench data fetching
  const { data: sourceEntitiesData, isLoading: loadingSourceEntities } = useSourceEntities(
    workbenchEntityType as TranslatableEntityType,
    workbenchSearch || undefined,
    100,
    0,
    workbenchUntranslatedOnly
  )

  const { data: sourceContentData, isLoading: loadingSourceContent } = useSourceContent(
    workbenchEntityType as TranslatableEntityType,
    workbenchEntityCode
  )

  const { data: existingTranslationsData, isLoading: loadingExisting } = useEntityGroupedTranslations(
    workbenchEntityType as TranslatableEntityType,
    workbenchEntityCode
  )

  const bulkUpsertMutation = useBulkUpsertEntityTranslations()

  const { data: statsData, isLoading: statsLoading } = useEntityTranslationStats()
  const { data: translationsData, isLoading, refetch } = useEntityTranslations({
    entity_type: entityTypeFilter === 'all' ? undefined : entityTypeFilter,
    language_code: languageFilter === 'all' ? undefined : languageFilter,
    search_term: searchQuery || undefined,
    limit: pageSize,
    offset: page * pageSize,
  })

  const deleteMutation = useDeleteEntityTranslation()
  const upsertMutation = useUpsertEntityTranslation()

  const handleDelete = async (tr: EntityTranslation) => {
    if (!confirm(t('common.deleteConfirm', { entity: `${tr.entity_type}/${tr.entity_code}/${tr.language_code}` }))) return

    try {
      await deleteMutation.mutateAsync({
        entityType: tr.entity_type,
        entityCode: tr.entity_code,
        languageCode: tr.language_code,
        fieldName: tr.field_name,
      })
      toast({ title: t('common.success'), description: t('common.translationDeleted') })
      refetch()
    } catch (err) {
      toast({ variant: 'destructive', title: t('common.error'), description: String(err) })
    }
  }

  const handleEdit = (tr: EntityTranslation) => {
    setEditingTranslation(tr)
    setEditText(tr.translation_text)
    setEditModalOpen(true)
  }

  const handleSaveEdit = async () => {
    if (!editingTranslation) return

    try {
      await upsertMutation.mutateAsync({
        entity_type: editingTranslation.entity_type,
        entity_code: editingTranslation.entity_code,
        language_code: editingTranslation.language_code,
        field_name: editingTranslation.field_name,
        translation_text: editText,
      })
      toast({ title: t('common.success'), description: t('common.translationSaved') })
      setEditModalOpen(false)
      setEditingTranslation(null)
      refetch()
    } catch (err) {
      toast({ variant: 'destructive', title: t('common.error'), description: String(err) })
    }
  }

  const getEntityTypeLabel = (type: TranslatableEntityType) => {
    const option = ENTITY_TYPE_OPTIONS.find(o => o.value === type)
    if (!option) return type
    return locale === 'fr' ? option.label_fr : locale === 'en' ? option.label_en : option.label
  }

  const getLanguageFlag = (code: LanguageCode) => {
    const opt = LANGUAGE_OPTIONS.find(o => o.value === code)
    return opt?.flag || code
  }

  // Workbench handlers
  const handleSelectWorkbenchEntity = (code: string) => {
    setWorkbenchEntityCode(code)
    setWorkbenchTranslations({})
  }

  // Initialize workbench translations from existing data
  const initializeWorkbenchTranslations = () => {
    if (!sourceContentData?.fields) return

    const newTranslations: Record<string, { fr: string; en: string }> = {}
    Object.keys(sourceContentData.fields).forEach((field) => {
      const existing = existingTranslationsData?.translations?.[field]
      newTranslations[field] = {
        fr: existing?.fr || '',
        en: existing?.en || '',
      }
    })
    setWorkbenchTranslations(newTranslations)
  }

  // Effect to initialize translations when source content loads
  if (sourceContentData?.fields && Object.keys(workbenchTranslations).length === 0 && !loadingExisting) {
    initializeWorkbenchTranslations()
  }

  const handleSaveWorkbenchTranslations = async () => {
    if (!workbenchEntityType || !workbenchEntityCode || !sourceContentData?.fields) return

    const translations = Object.entries(workbenchTranslations)
      .filter(([, trans]) => trans.fr || trans.en)
      .map(([fieldName, trans]) => ({
        entity_type: workbenchEntityType as TranslatableEntityType,
        entity_code: workbenchEntityCode,
        field_name: fieldName,
        es: sourceContentData.fields[fieldName] || '',
        fr: trans.fr,
        en: trans.en,
        translation_source: 'manual' as const,
      }))

    if (translations.length === 0) {
      toast({ variant: 'destructive', title: t('common.error'), description: 'No translations to save' })
      return
    }

    try {
      await bulkUpsertMutation.mutateAsync({ translations })
      toast({ title: t('common.success'), description: t('workbench.translationsSaved') })
      refetch()
    } catch (err) {
      toast({ variant: 'destructive', title: t('common.error'), description: String(err) })
    }
  }

  const handleOpenWorkbench = () => {
    setWorkbenchOpen(true)
    setWorkbenchEntityType('')
    setWorkbenchEntityCode('')
    setWorkbenchSearch('')
    setWorkbenchTranslations({})
  }

  return (
    <div className="space-y-6">
      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">{t('entity.total')}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {statsLoading ? <Loader2 className="h-5 w-5 animate-spin" /> : statsData?.total_translations || 0}
            </div>
          </CardContent>
        </Card>
        {(['ministry', 'sector', 'category'] as const).map(type => (
          <Card key={type}>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">{t(`entity.${type}`)}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {statsLoading ? <Loader2 className="h-5 w-5 animate-spin" /> : statsData?.by_entity_type?.[type] || 0}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Filters */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>{t('entity.title')}</CardTitle>
              <CardDescription>{t('entity.description')}</CardDescription>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="default" size="sm" onClick={handleOpenWorkbench}>
                <Wrench className="h-4 w-4 mr-2" />
                {t('workbench.openWorkbench')}
              </Button>
              <Button variant="outline" size="sm" onClick={() => refetch()}>
                <RefreshCw className="h-4 w-4 mr-2" />
                {t('common.refresh')}
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4 mb-4 flex-wrap">
            <div className="relative flex-1 max-w-sm">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder={t('entity.searchPlaceholder')}
                value={searchQuery}
                onChange={(e) => { setSearchQuery(e.target.value); setPage(0); }}
                className="pl-9"
              />
            </div>
            <Select
              value={entityTypeFilter}
              onValueChange={(v) => { setEntityTypeFilter(v as TranslatableEntityType | 'all'); setPage(0); }}
            >
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder={t('entity.entityType')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('entity.allTypes')}</SelectItem>
                {ENTITY_TYPE_OPTIONS.map(opt => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {locale === 'fr' ? opt.label_fr : locale === 'en' ? opt.label_en : opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select
              value={languageFilter}
              onValueChange={(v) => { setLanguageFilter(v as LanguageCode | 'all'); setPage(0); }}
            >
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder={t('common.languageFilter')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('common.allLanguages')}</SelectItem>
                {LANGUAGE_OPTIONS.map(opt => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.flag} {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin mr-2" />
              {t('common.loading')}
            </div>
          ) : !translationsData?.translations?.length ? (
            <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
              <Building2 className="h-12 w-12 mb-4 opacity-50" />
              <p>{t('entity.noTranslations')}</p>
            </div>
          ) : (
            <>
              <div className="border rounded-md overflow-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t('entity.tableHeaders.type')}</TableHead>
                    <TableHead>{t('entity.tableHeaders.entityCode')}</TableHead>
                    <TableHead className="hidden md:table-cell">{t('entity.tableHeaders.field')}</TableHead>
                    <TableHead>{t('entity.tableHeaders.language')}</TableHead>
                    <TableHead className="hidden lg:table-cell">{t('entity.tableHeaders.translation')}</TableHead>
                    <TableHead className="text-right">{t('entity.tableHeaders.actions')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {translationsData.translations.map((tr) => (
                    <TableRow key={tr.id}>
                      <TableCell>
                        <Badge variant="outline">{getEntityTypeLabel(tr.entity_type)}</Badge>
                      </TableCell>
                      <TableCell className="font-mono text-sm">{tr.entity_code}</TableCell>
                      <TableCell className="hidden md:table-cell">{tr.field_name}</TableCell>
                      <TableCell>{getLanguageFlag(tr.language_code)} {tr.language_code.toUpperCase()}</TableCell>
                      <TableCell className="hidden lg:table-cell max-w-[300px] truncate">{tr.translation_text}</TableCell>
                      <TableCell className="text-right">
                        <Button variant="ghost" size="sm" onClick={() => handleEdit(tr)}>
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => handleDelete(tr)}>
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              </div>

              <div className="flex items-center justify-between mt-4">
                <p className="text-sm text-muted-foreground">
                  {t('common.showing', { start: page * pageSize + 1, end: Math.min((page + 1) * pageSize, translationsData.total), total: translationsData.total })}
                </p>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" disabled={page === 0} onClick={() => setPage(p => p - 1)}>
                    {t('common.previous')}
                  </Button>
                  <Button variant="outline" size="sm" disabled={(page + 1) * pageSize >= translationsData.total} onClick={() => setPage(p => p + 1)}>
                    {t('common.next')}
                  </Button>
                </div>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* Edit Modal */}
      <Dialog open={editModalOpen} onOpenChange={setEditModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('common.editTranslation')}</DialogTitle>
            <DialogDescription>
              {editingTranslation && `${editingTranslation.entity_type} / ${editingTranslation.entity_code} / ${editingTranslation.language_code}`}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label>{t('entity.tableHeaders.field')}</Label>
              <Input value={editingTranslation?.field_name || ''} disabled />
            </div>
            <div>
              <Label>{t('entity.tableHeaders.translation')}</Label>
              <Textarea
                value={editText}
                onChange={(e) => setEditText(e.target.value)}
                rows={4}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditModalOpen(false)}>
              {t('common.cancel')}
            </Button>
            <Button onClick={handleSaveEdit} disabled={upsertMutation.isPending}>
              {upsertMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
              {t('common.save')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Translation Workbench Modal */}
      <Dialog open={workbenchOpen} onOpenChange={setWorkbenchOpen}>
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Wrench className="h-5 w-5" />
              {t('workbench.title')}
            </DialogTitle>
            <DialogDescription>{t('workbench.description')}</DialogDescription>
          </DialogHeader>

          <div className="space-y-6">
            {/* Entity Type Selection */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>{t('workbench.selectEntityType')}</Label>
                <Select
                  value={workbenchEntityType}
                  onValueChange={(v) => {
                    setWorkbenchEntityType(v as TranslatableEntityType)
                    setWorkbenchEntityCode('')
                    setWorkbenchTranslations({})
                  }}
                >
                  <SelectTrigger>
                    <SelectValue placeholder={t('workbench.selectEntityType')} />
                  </SelectTrigger>
                  <SelectContent>
                    {ENTITY_TYPE_OPTIONS.map((opt) => (
                      <SelectItem key={opt.value} value={opt.value}>
                        {locale === 'fr' ? opt.label_fr : locale === 'en' ? opt.label_en : opt.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {workbenchEntityType && (
                <div>
                  <Label>{t('workbench.searchEntities')}</Label>
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                    <Input
                      placeholder={t('workbench.searchEntities')}
                      value={workbenchSearch}
                      onChange={(e) => setWorkbenchSearch(e.target.value)}
                      className="pl-9"
                    />
                  </div>
                </div>
              )}
            </div>

            {/* Untranslated Only Filter */}
            {workbenchEntityType && (
              <div className="flex items-center space-x-2">
                <Checkbox
                  id="untranslated-only"
                  checked={workbenchUntranslatedOnly}
                  onCheckedChange={(checked) => setWorkbenchUntranslatedOnly(checked === true)}
                />
                <Label htmlFor="untranslated-only" className="text-sm cursor-pointer">
                  {t('workbench.untranslatedOnly')}
                </Label>
                {sourceEntitiesData?.total !== undefined && (
                  <Badge variant="secondary" className="ml-2">
                    {sourceEntitiesData.total} {t('workbench.entitiesCount')}
                  </Badge>
                )}
              </div>
            )}

            {/* Entity List */}
            {workbenchEntityType && (
              <div>
                <Label>{t('workbench.selectEntity')}</Label>
                <div className="border rounded-md max-h-48 overflow-y-auto mt-2">
                  {loadingSourceEntities ? (
                    <div className="flex items-center justify-center py-4">
                      <Loader2 className="h-4 w-4 animate-spin mr-2" />
                      {t('common.loading')}
                    </div>
                  ) : !sourceEntitiesData?.entities?.length ? (
                    <div className="text-center text-muted-foreground py-4">
                      {t('workbench.noEntitiesFound')}
                    </div>
                  ) : (
                    <div className="divide-y">
                      {sourceEntitiesData.entities.map((entity) => (
                        <div
                          key={entity.entity_code}
                          className={`p-3 cursor-pointer hover:bg-muted transition-colors ${
                            workbenchEntityCode === entity.entity_code ? 'bg-primary/10 border-l-2 border-primary' : ''
                          }`}
                          onClick={() => handleSelectWorkbenchEntity(entity.entity_code)}
                        >
                          <div className="font-mono text-sm font-medium">{entity.entity_code}</div>
                          <div className="text-sm text-muted-foreground truncate">{entity.name_es}</div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Translation Form */}
            {workbenchEntityCode && sourceContentData?.fields && (
              <div className="space-y-4">
                <div className="grid grid-cols-4 gap-4 font-medium text-sm border-b pb-2">
                  <div>{t('workbench.field')}</div>
                  <div>{t('workbench.spanish')}</div>
                  <div>{t('workbench.french')}</div>
                  <div>{t('workbench.english')}</div>
                </div>

                {loadingSourceContent || loadingExisting ? (
                  <div className="flex items-center justify-center py-4">
                    <Loader2 className="h-4 w-4 animate-spin mr-2" />
                    {t('workbench.loadingSource')}
                  </div>
                ) : (
                  Object.entries(sourceContentData.fields).map(([fieldName, spanishValue]) => (
                    <div key={fieldName} className="grid grid-cols-4 gap-4 items-start">
                      <div className="font-mono text-sm py-2">{fieldName}</div>
                      <div className="bg-muted p-2 rounded text-sm min-h-[60px]">
                        {spanishValue || <span className="text-muted-foreground italic">-</span>}
                      </div>
                      <div>
                        <Textarea
                          value={workbenchTranslations[fieldName]?.fr || ''}
                          onChange={(e) =>
                            setWorkbenchTranslations((prev) => ({
                              ...prev,
                              [fieldName]: { ...prev[fieldName], fr: e.target.value, en: prev[fieldName]?.en || '' },
                            }))
                          }
                          placeholder={t('workbench.french')}
                          rows={2}
                          className="text-sm"
                        />
                      </div>
                      <div>
                        <Textarea
                          value={workbenchTranslations[fieldName]?.en || ''}
                          onChange={(e) =>
                            setWorkbenchTranslations((prev) => ({
                              ...prev,
                              [fieldName]: { ...prev[fieldName], en: e.target.value, fr: prev[fieldName]?.fr || '' },
                            }))
                          }
                          placeholder={t('workbench.english')}
                          rows={2}
                          className="text-sm"
                        />
                      </div>
                    </div>
                  ))
                )}
              </div>
            )}

            {!workbenchEntityCode && workbenchEntityType && (
              <div className="text-center text-muted-foreground py-8">
                {t('workbench.selectEntityFirst')}
              </div>
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setWorkbenchOpen(false)}>
              {t('common.cancel')}
            </Button>
            <Button
              onClick={handleSaveWorkbenchTranslations}
              disabled={!workbenchEntityCode || bulkUpsertMutation.isPending}
            >
              {bulkUpsertMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
              {t('workbench.saveTranslations')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

// =============================================================================
// SYSTEM TRANSLATIONS TAB
// =============================================================================

function SystemTranslationsTab() {
  const locale = useLocale() as LanguageCode
  const t = useTranslations('admin.translations')
  const { toast } = useToast()

  const [groupFilter, setGroupFilter] = useState<string>('all')
  const [categoryFilter, setCategoryFilter] = useState<string>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [page, setPage] = useState(0)
  const pageSize = 50

  // Add/Edit modal state
  const [modalOpen, setModalOpen] = useState(false)
  const [editingTranslation, setEditingTranslation] = useState<SystemTranslation | null>(null)
  const [formData, setFormData] = useState({ category: '', key_code: '', es: '', fr: '', en: '', description: '' })

  // Pass locale to get localized category and group labels
  const { data: categoriesData } = useSystemCategories(locale)
  const { data: groupsData } = useSystemGroups(locale)

  // Filter categories by selected group
  const filteredCategories = categoriesData?.categories?.filter((cat: SystemCategory) => {
    if (groupFilter === 'all') return true
    return cat.group === groupFilter
  }) || []

  // Helper to get category label from code
  const getCategoryLabel = (code: string): string => {
    const category = categoriesData?.categories?.find((c: SystemCategory) => c.code === code)
    return category?.label || code
  }

  // Helper to get category info (table/enum/group)
  const getCategoryInfo = (code: string): { table?: string | null; enum?: string | null; group?: string; groupLabel?: string } => {
    const category = categoriesData?.categories?.find((c: SystemCategory) => c.code === code)
    return {
      table: category?.db_table,
      enum: category?.db_enum,
      group: category?.group,
      groupLabel: category?.group_label
    }
  }

  // Reset category filter when group changes
  const handleGroupChange = (group: string) => {
    setGroupFilter(group)
    setCategoryFilter('all')
    setPage(0)
  }
  const { data: translationsData, isLoading, refetch } = useSystemTranslations({
    category: categoryFilter === 'all' ? undefined : categoryFilter,
    group: groupFilter === 'all' ? undefined : groupFilter,
    search_term: searchQuery || undefined,
    limit: pageSize,
    offset: page * pageSize,
  })

  const deleteMutation = useDeleteSystemTranslation()
  const createMutation = useCreateSystemTranslation()
  const updateMutation = useUpdateSystemTranslation()

  const handleDelete = async (tr: SystemTranslation) => {
    if (!confirm(t('common.deleteConfirm', { entity: `${tr.category}/${tr.key_code}` }))) return

    try {
      await deleteMutation.mutateAsync(tr.id)
      toast({ title: t('common.success'), description: t('common.translationDeleted') })
      refetch()
    } catch (err) {
      toast({ variant: 'destructive', title: t('common.error'), description: String(err) })
    }
  }

  const handleAdd = () => {
    setEditingTranslation(null)
    setFormData({ category: '', key_code: '', es: '', fr: '', en: '', description: '' })
    setModalOpen(true)
  }

  const handleEdit = (tr: SystemTranslation) => {
    setEditingTranslation(tr)
    setFormData({
      category: tr.category,
      key_code: tr.key_code,
      es: tr.es,
      fr: tr.fr,
      en: tr.en,
      description: tr.description || '',
    })
    setModalOpen(true)
  }

  const handleSave = async () => {
    try {
      if (editingTranslation) {
        await updateMutation.mutateAsync({
          id: editingTranslation.id,
          data: { es: formData.es, fr: formData.fr, en: formData.en, description: formData.description },
        })
        toast({ title: t('common.success'), description: t('common.translationSaved') })
      } else {
        await createMutation.mutateAsync(formData)
        toast({ title: t('common.success'), description: t('common.translationCreated') })
      }
      setModalOpen(false)
      refetch()
    } catch (err) {
      toast({ variant: 'destructive', title: t('common.error'), description: String(err) })
    }
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>{t('system.title')}</CardTitle>
              <CardDescription>{t('system.description')}</CardDescription>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={handleAdd}>
                <Plus className="h-4 w-4 mr-2" />
                {t('common.add')}
              </Button>
              <Button variant="outline" size="sm" onClick={() => refetch()}>
                <RefreshCw className="h-4 w-4 mr-2" />
                {t('common.refresh')}
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4 mb-4 flex-wrap">
            <div className="relative flex-1 max-w-sm">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder={t('system.searchPlaceholder')}
                value={searchQuery}
                onChange={(e) => { setSearchQuery(e.target.value); setPage(0); }}
                className="pl-9"
              />
            </div>
            {/* Group filter (ENUM types + functional groups) */}
            <Select
              value={groupFilter}
              onValueChange={handleGroupChange}
            >
              <SelectTrigger className="w-[240px]">
                <SelectValue placeholder={t('system.group')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('system.allGroups')}</SelectItem>
                {/* Enum groups */}
                {groupsData?.groups?.filter((g: TranslationGroup) => g.type === 'enum').map((group: TranslationGroup) => (
                  <SelectItem key={group.code} value={group.code}>
                    <span className="flex items-center gap-2">
                      <Badge variant="outline" className="text-xs px-1">ENUM</Badge>
                      <span>{group.label}</span>
                    </span>
                  </SelectItem>
                ))}
                {/* Separator if we have both types */}
                {groupsData?.groups?.some((g: TranslationGroup) => g.type === 'enum') &&
                 groupsData?.groups?.some((g: TranslationGroup) => g.type === 'functional') && (
                  <SelectItem value="_separator" disabled className="opacity-30">
                    ─────────────
                  </SelectItem>
                )}
                {/* Functional groups */}
                {groupsData?.groups?.filter((g: TranslationGroup) => g.type === 'functional').map((group: TranslationGroup) => (
                  <SelectItem key={group.code} value={group.code}>
                    <span className="flex items-center gap-2">
                      <Badge variant="secondary" className="text-xs px-1">UI</Badge>
                      <span>{group.label}</span>
                    </span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {/* Category filter (filtered by selected group) */}
            <Select
              value={categoryFilter}
              onValueChange={(v) => { setCategoryFilter(v); setPage(0); }}
            >
              <SelectTrigger className="w-[280px]">
                <SelectValue placeholder={t('system.category')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('system.allCategories')}</SelectItem>
                {filteredCategories.map((cat: SystemCategory) => (
                  <SelectItem key={cat.code} value={cat.code}>
                    <span className="flex items-center gap-2">
                      <span>{cat.label}</span>
                      {cat.db_enum && (
                        <span className="text-xs text-muted-foreground">({cat.db_enum})</span>
                      )}
                    </span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin mr-2" />
              {t('common.loading')}
            </div>
          ) : !translationsData?.translations?.length ? (
            <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
              <FileText className="h-12 w-12 mb-4 opacity-50" />
              <p>{t('system.noTranslations')}</p>
            </div>
          ) : (
            <>
              <div className="border rounded-md overflow-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t('system.tableHeaders.category')}</TableHead>
                    <TableHead>{t('system.tableHeaders.key')}</TableHead>
                    <TableHead>{t('system.tableHeaders.es')}</TableHead>
                    <TableHead className="hidden md:table-cell">{t('system.tableHeaders.fr')}</TableHead>
                    <TableHead className="hidden lg:table-cell">{t('system.tableHeaders.en')}</TableHead>
                    <TableHead className="text-right">{t('system.tableHeaders.actions')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {translationsData.translations.map((tr) => {
                    const catInfo = getCategoryInfo(tr.category)
                    return (
                    <TableRow key={tr.id}>
                      <TableCell>
                        <div className="flex flex-col gap-1">
                          <Badge variant="secondary" title={tr.category}>
                            {getCategoryLabel(tr.category)}
                          </Badge>
                          <div className="flex flex-col gap-0.5 text-xs text-muted-foreground">
                            {catInfo.groupLabel && (
                              <span className="text-primary/70">{catInfo.groupLabel}</span>
                            )}
                            {catInfo.enum && <span className="font-mono">{catInfo.enum}</span>}
                            {catInfo.table && !catInfo.enum && <span>{catInfo.table}</span>}
                          </div>
                        </div>
                      </TableCell>
                      <TableCell className="font-mono text-sm">{tr.key_code}</TableCell>
                      <TableCell className="max-w-[150px] truncate" title={tr.es}>{tr.es}</TableCell>
                      <TableCell className="hidden md:table-cell max-w-[150px] truncate" title={tr.fr}>{tr.fr}</TableCell>
                      <TableCell className="hidden lg:table-cell max-w-[150px] truncate" title={tr.en}>{tr.en}</TableCell>
                      <TableCell className="text-right">
                        <Button variant="ghost" size="sm" onClick={() => handleEdit(tr)}>
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => handleDelete(tr)}>
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  )})}
                </TableBody>
              </Table>
              </div>

              <div className="flex items-center justify-between mt-4">
                <p className="text-sm text-muted-foreground">
                  {t('common.showing', { start: page * pageSize + 1, end: Math.min((page + 1) * pageSize, translationsData.total), total: translationsData.total })}
                </p>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" disabled={page === 0} onClick={() => setPage(p => p - 1)}>
                    {t('common.previous')}
                  </Button>
                  <Button variant="outline" size="sm" disabled={(page + 1) * pageSize >= translationsData.total} onClick={() => setPage(p => p + 1)}>
                    {t('common.next')}
                  </Button>
                </div>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* Add/Edit Modal */}
      <Dialog open={modalOpen} onOpenChange={setModalOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{editingTranslation ? t('common.editTranslation') : t('common.addTranslation')}</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>{t('system.tableHeaders.category')}</Label>
                <Input
                  value={formData.category}
                  onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                  disabled={!!editingTranslation}
                />
              </div>
              <div>
                <Label>{t('system.tableHeaders.key')}</Label>
                <Input
                  value={formData.key_code}
                  onChange={(e) => setFormData({ ...formData, key_code: e.target.value })}
                  disabled={!!editingTranslation}
                />
              </div>
            </div>
            <div>
              <Label>ES (Español)</Label>
              <Textarea
                value={formData.es}
                onChange={(e) => setFormData({ ...formData, es: e.target.value })}
                rows={2}
              />
            </div>
            <div>
              <Label>FR (Français)</Label>
              <Textarea
                value={formData.fr}
                onChange={(e) => setFormData({ ...formData, fr: e.target.value })}
                rows={2}
              />
            </div>
            <div>
              <Label>EN (English)</Label>
              <Textarea
                value={formData.en}
                onChange={(e) => setFormData({ ...formData, en: e.target.value })}
                rows={2}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setModalOpen(false)}>
              {t('common.cancel')}
            </Button>
            <Button onClick={handleSave} disabled={createMutation.isPending || updateMutation.isPending}>
              {(createMutation.isPending || updateMutation.isPending) ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
              {t('common.save')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

// =============================================================================
// ENUM MANAGEMENT TAB
// =============================================================================

function EnumManagementTab() {
  const locale = useLocale() as LanguageCode
  const t = useTranslations('admin.translations')
  const { toast } = useToast()

  const [selectedEnum, setSelectedEnum] = useState<ModifiableEnumType | ''>('')
  const [showArchived, setShowArchived] = useState(false)

  // Add modal state
  const [addModalOpen, setAddModalOpen] = useState(false)
  const [addFormData, setAddFormData] = useState({ value: '', es: '', fr: '', en: '' })

  // Edit modal state
  const [editModalOpen, setEditModalOpen] = useState(false)
  const [editingValue, setEditingValue] = useState<EnumValueWithTranslation | null>(null)
  const [editFormData, setEditFormData] = useState({ es: '', fr: '', en: '' })

  const { data: enumsData, isLoading: enumsLoading } = useModifiableEnums(locale)
  const { data: valuesData, isLoading: valuesLoading, refetch } = useEnumValues(
    selectedEnum as ModifiableEnumType,
    locale
  )

  const addMutation = useAddEnumValue()
  const updateMutation = useUpdateEnumTranslation()
  const archiveMutation = useArchiveEnumValue()
  const restoreMutation = useRestoreEnumValue()

  const getEnumLabel = (enumName: string) => {
    const opt = MODIFIABLE_ENUM_OPTIONS.find(o => o.value === enumName)
    if (!opt) return enumName
    return locale === 'fr' ? opt.label_fr : locale === 'en' ? opt.label_en : opt.label_es
  }

  const handleAdd = () => {
    setAddFormData({ value: '', es: '', fr: '', en: '' })
    setAddModalOpen(true)
  }

  const handleSaveAdd = async () => {
    if (!selectedEnum) return

    try {
      await addMutation.mutateAsync({
        enumName: selectedEnum as ModifiableEnumType,
        data: addFormData,
      })
      toast({ title: t('common.success'), description: t('enums.valueAdded') })
      setAddModalOpen(false)
      refetch()
    } catch (err) {
      toast({ variant: 'destructive', title: t('common.error'), description: String(err) })
    }
  }

  const handleEdit = (val: EnumValueWithTranslation) => {
    setEditingValue(val)
    setEditFormData({
      es: val.es || '',
      fr: val.fr || '',
      en: val.en || '',
    })
    setEditModalOpen(true)
  }

  const handleSaveEdit = async () => {
    if (!selectedEnum || !editingValue) return

    try {
      await updateMutation.mutateAsync({
        enumName: selectedEnum as ModifiableEnumType,
        value: editingValue.value,
        data: editFormData,
      })
      toast({ title: t('common.success'), description: t('common.translationSaved') })
      setEditModalOpen(false)
      refetch()
    } catch (err) {
      toast({ variant: 'destructive', title: t('common.error'), description: String(err) })
    }
  }

  const handleArchive = async (val: EnumValueWithTranslation) => {
    if (!selectedEnum) return
    if (!val.can_archive) {
      toast({
        variant: 'destructive',
        title: t('common.error'),
        description: t('enums.cannotArchive', { count: val.usage_count }),
      })
      return
    }
    if (!confirm(t('enums.archiveConfirm', { value: val.display_value }))) return

    try {
      await archiveMutation.mutateAsync({
        enumName: selectedEnum as ModifiableEnumType,
        value: val.value,
      })
      toast({ title: t('common.success'), description: t('enums.valueArchived') })
      refetch()
    } catch (err) {
      toast({ variant: 'destructive', title: t('common.error'), description: String(err) })
    }
  }

  const handleRestore = async (val: EnumValueWithTranslation) => {
    if (!selectedEnum) return
    if (!confirm(t('enums.restoreConfirm', { value: val.display_value }))) return

    try {
      await restoreMutation.mutateAsync({
        enumName: selectedEnum as ModifiableEnumType,
        value: val.value,
      })
      toast({ title: t('common.success'), description: t('enums.valueRestored') })
      refetch()
    } catch (err) {
      toast({ variant: 'destructive', title: t('common.error'), description: String(err) })
    }
  }

  const filteredValues = valuesData?.values?.filter((v: EnumValueWithTranslation) =>
    showArchived ? true : !v.is_archived
  ) || []

  return (
    <div className="space-y-6">
      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-3">
        {enumsLoading ? (
          <Card>
            <CardContent className="flex items-center justify-center py-6">
              <Loader2 className="h-5 w-5 animate-spin" />
            </CardContent>
          </Card>
        ) : (
          <>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">{t('enums.totalEnums')}</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{enumsData?.count || 0}</div>
              </CardContent>
            </Card>
            {selectedEnum && valuesData && (
              <>
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium">{t('enums.totalValues')}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold">{valuesData.total}</div>
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium">{t('enums.withoutTranslation')}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="flex items-center gap-2">
                      <div className="text-2xl font-bold">{valuesData.without_translation}</div>
                      {valuesData.without_translation > 0 && (
                        <Badge variant="destructive">{t('enums.needsTranslation')}</Badge>
                      )}
                    </div>
                  </CardContent>
                </Card>
              </>
            )}
          </>
        )}
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>{t('enums.title')}</CardTitle>
              <CardDescription>{t('enums.description')}</CardDescription>
            </div>
            <div className="flex items-center gap-2">
              {selectedEnum && (
                <Button variant="default" size="sm" onClick={handleAdd}>
                  <Plus className="h-4 w-4 mr-2" />
                  {t('enums.addValue')}
                </Button>
              )}
              <Button variant="outline" size="sm" onClick={() => refetch()}>
                <RefreshCw className="h-4 w-4 mr-2" />
                {t('common.refresh')}
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4 mb-4 flex-wrap">
            <Select
              value={selectedEnum}
              onValueChange={(v) => setSelectedEnum(v as ModifiableEnumType | '')}
            >
              <SelectTrigger className="w-[280px]">
                <SelectValue placeholder={t('enums.selectEnum')} />
              </SelectTrigger>
              <SelectContent>
                {enumsData?.enums?.map((enumItem: { enum_name: string; label: string; total_values: number }) => (
                  <SelectItem key={enumItem.enum_name} value={enumItem.enum_name}>
                    <span className="flex items-center gap-2">
                      <span>{enumItem.label}</span>
                      <Badge variant="secondary" className="text-xs">{enumItem.total_values}</Badge>
                    </span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            {selectedEnum && (
              <div className="flex items-center space-x-2">
                <Checkbox
                  id="show-archived"
                  checked={showArchived}
                  onCheckedChange={(checked) => setShowArchived(checked === true)}
                />
                <Label htmlFor="show-archived" className="text-sm cursor-pointer">
                  {t('enums.showArchived')}
                </Label>
              </div>
            )}
          </div>

          {!selectedEnum ? (
            <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
              <Database className="h-12 w-12 mb-4 opacity-50" />
              <p>{t('enums.selectEnumFirst')}</p>
            </div>
          ) : valuesLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin mr-2" />
              {t('common.loading')}
            </div>
          ) : !filteredValues.length ? (
            <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
              <Database className="h-12 w-12 mb-4 opacity-50" />
              <p>{t('enums.noValues')}</p>
            </div>
          ) : (
            <div className="border rounded-md overflow-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('enums.tableHeaders.value')}</TableHead>
                  <TableHead>{t('enums.tableHeaders.status')}</TableHead>
                  <TableHead>{t('system.tableHeaders.es')}</TableHead>
                  <TableHead className="hidden md:table-cell">{t('system.tableHeaders.fr')}</TableHead>
                  <TableHead className="hidden lg:table-cell">{t('system.tableHeaders.en')}</TableHead>
                  <TableHead className="hidden md:table-cell">{t('enums.tableHeaders.usage')}</TableHead>
                  <TableHead className="text-right">{t('system.tableHeaders.actions')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredValues.map((val: EnumValueWithTranslation) => (
                  <TableRow key={val.value} className={val.is_archived ? 'opacity-60' : ''}>
                    <TableCell className="font-mono text-sm">{val.display_value}</TableCell>
                    <TableCell>
                      {val.is_archived ? (
                        <Badge variant="secondary">
                          <Archive className="h-3 w-3 mr-1" />
                          {t('enums.archived')}
                        </Badge>
                      ) : val.has_translation ? (
                        <Badge variant="default">
                          <CheckCircle className="h-3 w-3 mr-1" />
                          {t('enums.translated')}
                        </Badge>
                      ) : (
                        <Badge variant="destructive">
                          <AlertTriangle className="h-3 w-3 mr-1" />
                          {t('enums.untranslated')}
                        </Badge>
                      )}
                    </TableCell>
                    <TableCell className="max-w-[120px] truncate" title={val.es || ''}>
                      {val.es || <span className="text-muted-foreground italic">-</span>}
                    </TableCell>
                    <TableCell className="hidden md:table-cell max-w-[120px] truncate" title={val.fr || ''}>
                      {val.fr || <span className="text-muted-foreground italic">-</span>}
                    </TableCell>
                    <TableCell className="hidden lg:table-cell max-w-[120px] truncate" title={val.en || ''}>
                      {val.en || <span className="text-muted-foreground italic">-</span>}
                    </TableCell>
                    <TableCell className="hidden md:table-cell">
                      <Badge variant="outline">{val.usage_count}</Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <Button variant="ghost" size="sm" onClick={() => handleEdit(val)}>
                        <Pencil className="h-4 w-4" />
                      </Button>
                      {val.is_archived ? (
                        <Button variant="ghost" size="sm" onClick={() => handleRestore(val)}>
                          <RotateCcw className="h-4 w-4" />
                        </Button>
                      ) : (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleArchive(val)}
                          disabled={!val.can_archive}
                          title={!val.can_archive ? t('enums.cannotArchiveTooltip') : ''}
                        >
                          <Archive className="h-4 w-4" />
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Add Value Modal */}
      <Dialog open={addModalOpen} onOpenChange={setAddModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('enums.addValueTitle')}</DialogTitle>
            <DialogDescription>
              {selectedEnum && getEnumLabel(selectedEnum)}
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4">
            <div>
              <Label>{t('enums.valueCode')}</Label>
              <Input
                value={addFormData.value}
                onChange={(e) => setAddFormData({ ...addFormData, value: e.target.value.toLowerCase().replace(/\s+/g, '_') })}
                placeholder="new_value"
                className="font-mono"
              />
              <p className="text-xs text-muted-foreground mt-1">{t('enums.valueCodeHint')}</p>
            </div>
            <div>
              <Label>ES (Español)</Label>
              <Input
                value={addFormData.es}
                onChange={(e) => setAddFormData({ ...addFormData, es: e.target.value })}
              />
            </div>
            <div>
              <Label>FR (Français)</Label>
              <Input
                value={addFormData.fr}
                onChange={(e) => setAddFormData({ ...addFormData, fr: e.target.value })}
              />
            </div>
            <div>
              <Label>EN (English)</Label>
              <Input
                value={addFormData.en}
                onChange={(e) => setAddFormData({ ...addFormData, en: e.target.value })}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAddModalOpen(false)}>
              {t('common.cancel')}
            </Button>
            <Button onClick={handleSaveAdd} disabled={addMutation.isPending || !addFormData.value}>
              {addMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
              {t('common.save')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Translation Modal */}
      <Dialog open={editModalOpen} onOpenChange={setEditModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('common.editTranslation')}</DialogTitle>
            <DialogDescription>
              {editingValue?.display_value}
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4">
            <div>
              <Label>ES (Español)</Label>
              <Input
                value={editFormData.es}
                onChange={(e) => setEditFormData({ ...editFormData, es: e.target.value })}
              />
            </div>
            <div>
              <Label>FR (Français)</Label>
              <Input
                value={editFormData.fr}
                onChange={(e) => setEditFormData({ ...editFormData, fr: e.target.value })}
              />
            </div>
            <div>
              <Label>EN (English)</Label>
              <Input
                value={editFormData.en}
                onChange={(e) => setEditFormData({ ...editFormData, en: e.target.value })}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditModalOpen(false)}>
              {t('common.cancel')}
            </Button>
            <Button onClick={handleSaveEdit} disabled={updateMutation.isPending}>
              {updateMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
              {t('common.save')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

// =============================================================================
// FRONTEND UI TRANSLATIONS TAB
// =============================================================================

// Namespace groups for organization by pages/blocks
const NAMESPACE_GROUPS = {
  pages: {
    label: 'Pages',
    namespaces: ['hero', 'stats', 'features', 'directory', 'home', 'services', 'guide', 'about', 'calculator'],
  },
  layout: {
    label: 'Layout',
    namespaces: ['nav', 'footer', 'common', 'metadata'],
  },
  admin: {
    label: 'Admin Panel',
    namespaces: ['admin', 'dashboard'],
  },
  auth: {
    label: 'Authentication',
    namespaces: ['auth', 'profile'],
  },
  features: {
    label: 'Features',
    namespaces: ['chat', 'declarations', 'documents', 'notifications', 'payments'],
  },
  errors: {
    label: 'Errors & Messages',
    namespaces: ['errors', 'validation'],
  },
}

function FrontendTranslationsTab() {
  const _locale = useLocale() as LanguageCode
  const t = useTranslations('admin.translations')
  const tCommon = useTranslations('common')
  const { toast } = useToast()

  const [namespaceFilter, setNamespaceFilter] = useState<string>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [page, setPage] = useState(0)
  const pageSize = 50

  // Edit modal state
  const [editModalOpen, setEditModalOpen] = useState(false)
  const [editingTranslation, setEditingTranslation] = useState<SystemTranslation | null>(null)
  const [editFormData, setEditFormData] = useState({ es: '', fr: '', en: '' })

  // Add modal state
  const [addModalOpen, setAddModalOpen] = useState(false)
  const [addFormData, setAddFormData] = useState({
    namespace: '',
    key_code: '',
    es: '',
    fr: '',
    en: '',
  })

  const { data: statsData, isLoading: statsLoading, refetch: refetchStats } = useFrontendTranslationStats()
  const { data: namespacesData, refetch: refetchNamespaces } = useFrontendNamespaces()
  const { data: translationsData, isLoading, refetch } = useFrontendTranslations({
    namespace: namespaceFilter === 'all' ? undefined : namespaceFilter,
    search_term: searchQuery || undefined,
    limit: pageSize,
    offset: page * pageSize,
  })

  const deleteMutation = useDeleteFrontendTranslation()
  const updateMutation = useUpdateFrontendTranslation()
  const createMutation = useCreateFrontendTranslation()
  const syncMutation = useSyncFrontendFromJson()
  const publishMutation = usePublishToGithub()

  const handleDelete = async (tr: SystemTranslation) => {
    if (!confirm(t('common.deleteConfirm', { entity: tr.key_code }))) return

    try {
      await deleteMutation.mutateAsync(tr.id)
      toast({ title: t('common.success'), description: t('common.translationDeleted') })
      refetch()
    } catch (err) {
      toast({ variant: 'destructive', title: t('common.error'), description: String(err) })
    }
  }

  const handleEdit = (tr: SystemTranslation) => {
    setEditingTranslation(tr)
    setEditFormData({ es: tr.es || '', fr: tr.fr || '', en: tr.en || '' })
    setEditModalOpen(true)
  }

  const handleSaveEdit = async () => {
    if (!editingTranslation) return

    try {
      await updateMutation.mutateAsync({
        id: editingTranslation.id,
        data: editFormData,
      })
      toast({ title: t('common.success'), description: t('common.translationUpdated') })
      setEditModalOpen(false)
      refetch()
    } catch (err) {
      toast({ variant: 'destructive', title: t('common.error'), description: String(err) })
    }
  }

  const handleAdd = async () => {
    if (!addFormData.namespace || !addFormData.key_code) {
      toast({ variant: 'destructive', title: t('common.error'), description: 'Namespace and key are required' })
      return
    }

    try {
      await createMutation.mutateAsync({
        namespace: addFormData.namespace,
        keyCode: addFormData.key_code,
        es: addFormData.es,
        fr: addFormData.fr,
        en: addFormData.en,
      })
      toast({ title: t('common.success'), description: t('common.translationCreated') })
      setAddModalOpen(false)
      setAddFormData({ namespace: '', key_code: '', es: '', fr: '', en: '' })
      refetch()
      refetchStats()
    } catch (err) {
      toast({ variant: 'destructive', title: t('common.error'), description: String(err) })
    }
  }

  const handleSyncFromJson = async () => {
    if (!confirm(t('frontend.syncConfirm') || 'Sync all translations from JSON files? This will update existing translations and create new ones.')) {
      return
    }

    try {
      const result = await syncMutation.mutateAsync()
      toast({
        title: t('common.success'),
        description: `${t('frontend.syncComplete') || 'Sync complete'}: ${result.stats.created} ${t('frontend.created') || 'created'}, ${result.stats.updated} ${t('frontend.updated') || 'updated'}`,
      })
      refetch()
      refetchStats()
      refetchNamespaces()
    } catch (err) {
      toast({ variant: 'destructive', title: t('common.error'), description: String(err) })
    }
  }

  const handlePublishToGithub = async () => {
    if (!confirm(t('frontend.publishConfirm') || 'Publish all translations to GitHub? This will commit changes and trigger a deployment.')) {
      return
    }

    try {
      const result = await publishMutation.mutateAsync()
      const successCount = result.files.filter(f => f.status === 'updated' || f.status === 'created').length
      const failedCount = result.files.filter(f => f.status === 'failed').length

      if (result.status === 'success') {
        toast({
          title: t('common.success'),
          description: `${t('frontend.publishComplete') || 'Published to GitHub'}: ${successCount} ${t('frontend.filesUpdated') || 'files updated'}`,
        })
      } else if (result.status === 'partial') {
        toast({
          variant: 'destructive',
          title: t('frontend.publishPartial') || 'Partial publish',
          description: `${successCount} ${t('frontend.filesUpdated') || 'files updated'}, ${failedCount} ${t('frontend.filesFailed') || 'files failed'}`,
        })
      } else {
        toast({
          variant: 'destructive',
          title: t('common.error'),
          description: result.files[0]?.error || t('frontend.publishFailed') || 'Publish failed',
        })
      }
    } catch (err) {
      toast({ variant: 'destructive', title: t('common.error'), description: String(err) })
    }
  }

  return (
    <div className="space-y-6">
      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">{t('frontend.totalKeys')}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {statsLoading ? <Loader2 className="h-5 w-5 animate-spin" /> : statsData?.total_keys || 0}
            </div>
          </CardContent>
        </Card>
        {LANGUAGE_OPTIONS.map(lang => (
          <Card key={lang.value}>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">{lang.flag} {lang.label}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-2">
                <div className="text-2xl font-bold">
                  {statsLoading ? <Loader2 className="h-5 w-5 animate-spin" /> : `${statsData?.coverage?.[lang.value] || 0}%`}
                </div>
                {statsData?.coverage?.[lang.value] === 100 ? (
                  <CheckCircle className="h-5 w-5 text-green-500" />
                ) : statsData?.missing_translations?.[lang.value] ? (
                  <Badge variant="destructive">{statsData.missing_translations[lang.value]} {t('frontend.missing')}</Badge>
                ) : null}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>{t('frontend.title')}</CardTitle>
              <CardDescription>{t('frontend.description')}</CardDescription>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="default"
                size="sm"
                onClick={handlePublishToGithub}
                disabled={publishMutation.isPending}
                className="bg-[#24292e] hover:bg-[#1a1e22] text-white"
              >
                {publishMutation.isPending ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <Github className="h-4 w-4 mr-2" />
                )}
                {t('frontend.publishToGithub') || 'Publish to GitHub'}
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={handleSyncFromJson}
                disabled={syncMutation.isPending}
              >
                {syncMutation.isPending ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <RefreshCw className="h-4 w-4 mr-2" />
                )}
                {t('frontend.syncFromJson') || 'Sync from JSON'}
              </Button>
              <Button size="sm" onClick={() => setAddModalOpen(true)}>
                <Plus className="h-4 w-4 mr-2" />
                {t('common.add') || tCommon('save').replace('Guardar', 'Agregar')}
              </Button>
              <Button variant="outline" size="sm" onClick={() => refetch()}>
                <RefreshCw className="h-4 w-4 mr-2" />
                {t('common.refresh')}
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4 mb-4">
            <div className="relative flex-1 max-w-sm">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder={t('system.searchPlaceholder')}
                value={searchQuery}
                onChange={(e) => { setSearchQuery(e.target.value); setPage(0); }}
                className="pl-9"
              />
            </div>
            <Select
              value={namespaceFilter}
              onValueChange={(v) => { setNamespaceFilter(v); setPage(0); }}
            >
              <SelectTrigger className="w-[200px]">
                <SelectValue placeholder={t('frontend.namespace')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('frontend.allNamespaces')}</SelectItem>
                {/* Group namespaces by category */}
                {Object.entries(NAMESPACE_GROUPS).map(([groupKey, group]) => {
                  const groupNamespaces = namespacesData?.namespaces?.filter(ns => group.namespaces.includes(ns)) || []
                  if (groupNamespaces.length === 0) return null
                  return (
                    <div key={groupKey}>
                      <div className="px-2 py-1.5 text-xs font-semibold text-muted-foreground bg-muted/50">
                        {group.label}
                      </div>
                      {groupNamespaces.map(ns => (
                        <SelectItem key={ns} value={ns}>{ns}</SelectItem>
                      ))}
                    </div>
                  )
                })}
                {/* Other namespaces not in any group */}
                {namespacesData?.namespaces?.filter(ns =>
                  !Object.values(NAMESPACE_GROUPS).some(g => g.namespaces.includes(ns))
                ).map(ns => (
                  <SelectItem key={ns} value={ns}>{ns}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin mr-2" />
              {t('common.loading')}
            </div>
          ) : !translationsData?.translations?.length ? (
            <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
              <Globe className="h-12 w-12 mb-4 opacity-50" />
              <p>{t('frontend.noTranslations')}</p>
              <p className="text-sm mt-2">{t('frontend.clickSyncToImport') || 'Click "Sync from JSON" to import translations from message files'}</p>
            </div>
          ) : (
            <>
              <div className="border rounded-md overflow-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t('frontend.tableHeaders.namespace')}</TableHead>
                    <TableHead>{t('frontend.tableHeaders.key')}</TableHead>
                    <TableHead>{t('system.tableHeaders.es')}</TableHead>
                    <TableHead className="hidden md:table-cell">{t('system.tableHeaders.fr')}</TableHead>
                    <TableHead className="hidden lg:table-cell">{t('system.tableHeaders.en')}</TableHead>
                    <TableHead className="text-right">{t('system.tableHeaders.actions')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {translationsData.translations.map((tr) => (
                    <TableRow key={tr.id} className="group">
                      <TableCell>
                        <Badge variant="outline">{tr.category.replace('frontend.', '')}</Badge>
                      </TableCell>
                      <TableCell className="font-mono text-sm">{tr.key_code}</TableCell>
                      <TableCell className="max-w-[150px] truncate" title={tr.es}>{tr.es}</TableCell>
                      <TableCell className="hidden md:table-cell max-w-[150px] truncate" title={tr.fr}>{tr.fr}</TableCell>
                      <TableCell className="hidden lg:table-cell max-w-[150px] truncate" title={tr.en}>{tr.en}</TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                          <Button variant="ghost" size="sm" onClick={() => handleEdit(tr)}>
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button variant="ghost" size="sm" onClick={() => handleDelete(tr)}>
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              </div>

              <div className="flex items-center justify-between mt-4">
                <p className="text-sm text-muted-foreground">
                  {t('common.showing', { start: page * pageSize + 1, end: Math.min((page + 1) * pageSize, translationsData.total), total: translationsData.total })}
                </p>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" disabled={page === 0} onClick={() => setPage(p => p - 1)}>
                    {t('common.previous')}
                  </Button>
                  <Button variant="outline" size="sm" disabled={(page + 1) * pageSize >= translationsData.total} onClick={() => setPage(p => p + 1)}>
                    {t('common.next')}
                  </Button>
                </div>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* Edit Translation Modal */}
      <Dialog open={editModalOpen} onOpenChange={setEditModalOpen}>
        <DialogContent className="sm:max-w-[600px]">
          <DialogHeader>
            <DialogTitle>{t('common.editTranslation') || 'Edit Translation'}</DialogTitle>
            <DialogDescription>
              {editingTranslation && (
                <span className="font-mono text-sm">
                  {editingTranslation.category.replace('frontend.', '')}.{editingTranslation.key_code}
                </span>
              )}
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="edit-es">ES - Spanish</Label>
              <Textarea
                id="edit-es"
                value={editFormData.es}
                onChange={(e) => setEditFormData(prev => ({ ...prev, es: e.target.value }))}
                rows={2}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="edit-fr">FR - French</Label>
              <Textarea
                id="edit-fr"
                value={editFormData.fr}
                onChange={(e) => setEditFormData(prev => ({ ...prev, fr: e.target.value }))}
                rows={2}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="edit-en">EN - English</Label>
              <Textarea
                id="edit-en"
                value={editFormData.en}
                onChange={(e) => setEditFormData(prev => ({ ...prev, en: e.target.value }))}
                rows={2}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditModalOpen(false)}>
              {t('common.cancel')}
            </Button>
            <Button onClick={handleSaveEdit} disabled={updateMutation.isPending}>
              {updateMutation.isPending && <Loader2 className="h-4 w-4 animate-spin mr-2" />}
              {t('common.save')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Add Translation Modal */}
      <Dialog open={addModalOpen} onOpenChange={setAddModalOpen}>
        <DialogContent className="sm:max-w-[600px]">
          <DialogHeader>
            <DialogTitle>{t('common.addTranslation') || 'Add Translation'}</DialogTitle>
            <DialogDescription>
              {t('frontend.addTranslationDesc') || 'Add a new translation key with values for all languages'}
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label htmlFor="add-namespace">{t('frontend.namespace')}</Label>
                <Select
                  value={addFormData.namespace}
                  onValueChange={(v) => setAddFormData(prev => ({ ...prev, namespace: v }))}
                >
                  <SelectTrigger>
                    <SelectValue placeholder={t('frontend.selectNamespace') || 'Select namespace'} />
                  </SelectTrigger>
                  <SelectContent>
                    {namespacesData?.namespaces?.map(ns => (
                      <SelectItem key={ns} value={ns}>{ns}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="add-key">{t('frontend.tableHeaders.key')}</Label>
                <Input
                  id="add-key"
                  value={addFormData.key_code}
                  onChange={(e) => setAddFormData(prev => ({ ...prev, key_code: e.target.value }))}
                  placeholder="button.submit"
                />
              </div>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="add-es">ES - Spanish</Label>
              <Textarea
                id="add-es"
                value={addFormData.es}
                onChange={(e) => setAddFormData(prev => ({ ...prev, es: e.target.value }))}
                rows={2}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="add-fr">FR - French</Label>
              <Textarea
                id="add-fr"
                value={addFormData.fr}
                onChange={(e) => setAddFormData(prev => ({ ...prev, fr: e.target.value }))}
                rows={2}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="add-en">EN - English</Label>
              <Textarea
                id="add-en"
                value={addFormData.en}
                onChange={(e) => setAddFormData(prev => ({ ...prev, en: e.target.value }))}
                rows={2}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAddModalOpen(false)}>
              {t('common.cancel')}
            </Button>
            <Button onClick={handleAdd} disabled={createMutation.isPending}>
              {createMutation.isPending && <Loader2 className="h-4 w-4 animate-spin mr-2" />}
              {t('common.save')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

// =============================================================================
// MAIN PAGE
// =============================================================================

export default function TranslationsAdminPage() {
  const t = useTranslations('admin.translations')

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
            <Languages className="h-8 w-8" />
            {t('title')}
          </h1>
          <p className="text-muted-foreground">
            {t('subtitle')}
          </p>
        </div>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="entity" className="w-full">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="entity" className="flex items-center gap-2">
            <Building2 className="h-4 w-4" />
            {t('tabs.entity')}
          </TabsTrigger>
          <TabsTrigger value="system" className="flex items-center gap-2">
            <FileText className="h-4 w-4" />
            {t('tabs.system')}
          </TabsTrigger>
          <TabsTrigger value="enums" className="flex items-center gap-2">
            <Database className="h-4 w-4" />
            {t('tabs.enums')}
          </TabsTrigger>
          <TabsTrigger value="frontend" className="flex items-center gap-2">
            <Globe className="h-4 w-4" />
            {t('tabs.frontend')}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="entity" className="mt-6">
          <EntityTranslationsTab />
        </TabsContent>

        <TabsContent value="system" className="mt-6">
          <SystemTranslationsTab />
        </TabsContent>

        <TabsContent value="enums" className="mt-6">
          <EnumManagementTab />
        </TabsContent>

        <TabsContent value="frontend" className="mt-6">
          <FrontendTranslationsTab />
        </TabsContent>
      </Tabs>
    </div>
  )
}
