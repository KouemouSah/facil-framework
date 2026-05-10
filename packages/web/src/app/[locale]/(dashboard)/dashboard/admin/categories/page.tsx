'use client'

/**
 * Categories Admin Page
 * CRUD management for categories hierarchy
 */

import { useState, useEffect } from 'react'
import { useLocale, useTranslations } from 'next-intl'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Switch } from '@/components/ui/switch'
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
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { FolderTree, RefreshCw, Plus, Edit, Trash2, Search, AlertTriangle, ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight, ArrowUpDown, ArrowUp, ArrowDown } from 'lucide-react'
import { useToast } from '@/hooks/use-toast'
import fiscalServicesAPI from '@/modules/fiscal-services/services/api'
import type { Category, Sector, Ministry, ServiceTypeEnum } from '@/types/fiscal-service'
import { getLocalizedName } from '@/types/fiscal-service'
import { BackendUnavailableAlert } from '@/modules/admin/components'

interface CategoryFormData {
  category_code: string
  sector_id: number | null
  ministry_id: number | null
  service_type: ServiceTypeEnum | null
  name_es: string
  description_es: string
  display_order: number
  icon: string
  color: string
  is_active: boolean
}

const defaultFormData: CategoryFormData = {
  category_code: '',
  sector_id: null,
  ministry_id: null,
  service_type: null,
  name_es: '',
  description_es: '',
  display_order: 0,
  icon: '',
  color: '#3B82F6',
  is_active: true,
}

const SERVICE_TYPES: ServiceTypeEnum[] = [
  'document_processing' as ServiceTypeEnum,
  'license_permit' as ServiceTypeEnum,
  'residence_permit' as ServiceTypeEnum,
  'registration_fee' as ServiceTypeEnum,
  'inspection_fee' as ServiceTypeEnum,
  'administrative_tax' as ServiceTypeEnum,
  'customs_duty' as ServiceTypeEnum,
  'declaration_tax' as ServiceTypeEnum,
]

export default function CategoriesPage() {
  const locale = useLocale()
  const t = useTranslations('admin.categories')
  const tCommon = useTranslations('common')
  const { toast } = useToast()

  // Data states
  const [categories, setCategories] = useState<Category[]>([])
  const [sectors, setSectors] = useState<Sector[]>([])
  const [ministries, setMinistries] = useState<Ministry[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isBackendUnavailable, setIsBackendUnavailable] = useState(false)

  // Filter states
  const [searchQuery, setSearchQuery] = useState('')
  const [sectorFilter, setSectorFilter] = useState<number | 'all'>('all')
  const [ministryFilter, setMinistryFilter] = useState<number | 'all'>('all')
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'inactive'>('all')

  // Pagination states
  const [currentPage, setCurrentPage] = useState(1)
  const [rowsPerPage, setRowsPerPage] = useState(20)

  // Sorting states
  type SortColumn = 'category_code' | 'name_es' | 'sector_id' | 'ministry_id' | 'display_order' | 'is_active'
  const [sortColumn, setSortColumn] = useState<SortColumn | null>(null)
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc')

  // Modal states
  const [isDialogOpen, setIsDialogOpen] = useState(false)
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false)
  const [selectedCategory, setSelectedCategory] = useState<Category | null>(null)
  const [formData, setFormData] = useState<CategoryFormData>(defaultFormData)
  const [isSubmitting, setIsSubmitting] = useState(false)

  // Fetch data
  const fetchData = async () => {
    setIsLoading(true)
    setError(null)

    try {
      const [categoriesData, sectorsData, ministriesData] = await Promise.all([
        fiscalServicesAPI.hierarchy.categories.list(undefined, locale),
        fiscalServicesAPI.hierarchy.sectors.list(undefined, locale),
        fiscalServicesAPI.hierarchy.ministries.list(locale),
      ])
      setCategories(categoriesData)
      setSectors(sectorsData)
      setMinistries(ministriesData)
      setIsBackendUnavailable(false)
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : t('errorLoading')
      setError(errorMessage)

      if (errorMessage.includes('fetch') || errorMessage.includes('Network') || errorMessage.includes('Failed')) {
        setIsBackendUnavailable(true)
      }

      toast({
        variant: 'destructive',
        title: t('errorTitle'),
        description: t('errorLoading'),
      })
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [locale])

  const handleRefresh = () => {
    fetchData()
  }

  // Open create dialog
  const handleCreate = () => {
    setSelectedCategory(null)
    setFormData(defaultFormData)
    setIsDialogOpen(true)
  }

  // Open edit dialog
  const handleEdit = (category: Category) => {
    setSelectedCategory(category)
    setFormData({
      category_code: category.categoryCode || category.category_code || '',
      sector_id: category.sectorId ?? category.sector_id ?? null,
      ministry_id: category.ministryId ?? category.ministry_id ?? null,
      service_type: category.serviceType || category.service_type || null,
      name_es: category.nameEs || category.name_es || '',
      description_es: category.descriptionEs || category.description_es || '',
      display_order: category.displayOrder ?? category.display_order ?? 0,
      icon: category.icon || '',
      color: category.color || '#3B82F6',
      is_active: (category.isActive ?? category.is_active) !== false,
    })
    setIsDialogOpen(true)
  }

  // Open delete confirmation
  const handleDeleteClick = (category: Category) => {
    setSelectedCategory(category)
    setIsDeleteDialogOpen(true)
  }

  // Submit form (create or update)
  const handleSubmit = async () => {
    setIsSubmitting(true)

    try {
      if (!formData.category_code || !formData.name_es) {
        toast({
          variant: 'destructive',
          title: t('errorTitle'),
          description: t('requiredFields'),
        })
        setIsSubmitting(false)
        return
      }

      // Convert null to undefined for API compatibility
      const apiData = {
        ...formData,
        sector_id: formData.sector_id ?? undefined,
        ministry_id: formData.ministry_id ?? undefined,
        service_type: formData.service_type ?? undefined,
      }

      if (selectedCategory) {
        await fiscalServicesAPI.hierarchy.categories.update(selectedCategory.id, apiData)
        toast({
          title: t('successTitle'),
          description: t('categoryUpdated'),
        })
      } else {
        await fiscalServicesAPI.hierarchy.categories.create(apiData as Omit<Category, 'id' | 'created_at' | 'updated_at'>)
        toast({
          title: t('successTitle'),
          description: t('categoryCreated'),
        })
      }

      setIsDialogOpen(false)
      fetchData()
    } catch (err) {
      toast({
        variant: 'destructive',
        title: t('errorTitle'),
        description: err instanceof Error ? err.message : t('errorSaving'),
      })
    } finally {
      setIsSubmitting(false)
    }
  }

  // Delete category
  const handleDelete = async () => {
    if (!selectedCategory) return

    try {
      await fiscalServicesAPI.hierarchy.categories.delete(selectedCategory.id)
      toast({
        title: t('successTitle'),
        description: t('categoryDeleted'),
      })
      setIsDeleteDialogOpen(false)
      fetchData()
    } catch (err) {
      toast({
        variant: 'destructive',
        title: t('errorTitle'),
        description: err instanceof Error ? err.message : t('errorDeleting'),
      })
    }
  }

  // Get sector name by ID
  const getSectorName = (sectorId: number | undefined) => {
    if (!sectorId) return '-'
    const sector = sectors.find(s => s.id === sectorId)
    return sector ? getLocalizedName(sector, locale) : '-'
  }

  // Get ministry name by ID
  const getMinistryName = (ministryId: number | undefined) => {
    if (!ministryId) return '-'
    const ministry = ministries.find(m => m.id === ministryId)
    return ministry ? getLocalizedName(ministry, locale) : '-'
  }

  // Get the ministry ID for a category (directly or via sector)
  const getCategoryMinistryId = (category: Category): number | undefined => {
    // Direct ministry link - check both camelCase and snake_case
    const directMinistryId = category.ministryId ?? category.ministry_id
    if (directMinistryId) {
      return directMinistryId
    }
    // Via sector - check both camelCase and snake_case
    const sectorId = category.sectorId ?? category.sector_id
    if (sectorId) {
      const sector = sectors.find(s => s.id === sectorId)
      return sector?.ministryId ?? sector?.ministry_id
    }
    return undefined
  }

  // Handle sort column click
  const handleSort = (column: SortColumn) => {
    if (sortColumn === column) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc')
    } else {
      setSortColumn(column)
      setSortDirection('asc')
    }
  }

  // Get sort icon for column
  const getSortIcon = (column: SortColumn) => {
    if (sortColumn !== column) {
      return <ArrowUpDown className="h-4 w-4 ml-1 opacity-50" />
    }
    return sortDirection === 'asc'
      ? <ArrowUp className="h-4 w-4 ml-1" />
      : <ArrowDown className="h-4 w-4 ml-1" />
  }

  // Filter categories
  const filteredCategories = categories.filter(c => {
    const name = getLocalizedName(c, locale)
    const code = c.categoryCode || c.category_code || ''
    const matchesSearch = searchQuery === '' ||
      name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      code.toLowerCase().includes(searchQuery.toLowerCase())

    // Sector filter - check both camelCase and snake_case
    const categorySectorId = c.sectorId ?? c.sector_id
    const matchesSector = sectorFilter === 'all' || categorySectorId === sectorFilter

    // Ministry filter - check both direct ministry_id and via sector
    let matchesMinistry = true
    if (ministryFilter !== 'all') {
      const categoryMinistryId = getCategoryMinistryId(c)
      matchesMinistry = categoryMinistryId === ministryFilter
    }

    // Status filter - check both camelCase and snake_case
    const isActive = (c.isActive ?? c.is_active) !== false
    const matchesStatus = statusFilter === 'all' ||
      (statusFilter === 'active' && isActive) ||
      (statusFilter === 'inactive' && !isActive)

    return matchesSearch && matchesSector && matchesMinistry && matchesStatus
  })

  // Sort categories
  const sortedCategories = [...filteredCategories].sort((a, b) => {
    if (!sortColumn) return 0

    let aValue: string | number | boolean
    let bValue: string | number | boolean

    switch (sortColumn) {
      case 'category_code':
        aValue = a.categoryCode || a.category_code || ''
        bValue = b.categoryCode || b.category_code || ''
        break
      case 'name_es':
        aValue = getLocalizedName(a, locale)
        bValue = getLocalizedName(b, locale)
        break
      case 'sector_id':
        aValue = getSectorName(a.sectorId ?? a.sector_id)
        bValue = getSectorName(b.sectorId ?? b.sector_id)
        break
      case 'ministry_id':
        aValue = getMinistryName(a.ministryId ?? a.ministry_id)
        bValue = getMinistryName(b.ministryId ?? b.ministry_id)
        break
      case 'display_order':
        aValue = a.displayOrder ?? a.display_order ?? 0
        bValue = b.displayOrder ?? b.display_order ?? 0
        break
      case 'is_active':
        aValue = (a.isActive ?? a.is_active) !== false
        bValue = (b.isActive ?? b.is_active) !== false
        break
      default:
        return 0
    }

    if (typeof aValue === 'string' && typeof bValue === 'string') {
      return sortDirection === 'asc'
        ? aValue.localeCompare(bValue)
        : bValue.localeCompare(aValue)
    }

    if (aValue < bValue) return sortDirection === 'asc' ? -1 : 1
    if (aValue > bValue) return sortDirection === 'asc' ? 1 : -1
    return 0
  })

  // Pagination calculations
  const totalPages = Math.ceil(sortedCategories.length / rowsPerPage)
  const startIndex = (currentPage - 1) * rowsPerPage
  const endIndex = startIndex + rowsPerPage
  const paginatedCategories = sortedCategories.slice(startIndex, endIndex)

  // Reset to first page when filters change
  useEffect(() => {
    setCurrentPage(1)
  }, [searchQuery, statusFilter, ministryFilter, sectorFilter, rowsPerPage])

  // Get filtered sectors based on ministry selection
  const filteredSectorsForSelect = ministryFilter !== 'all'
    ? sectors.filter(s => (s.ministryId ?? s.ministry_id) === ministryFilter)
    : sectors

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">{t('title')}</h1>
        <p className="text-muted-foreground mt-2">{t('subtitle')}</p>
      </div>

      {/* Backend Unavailable Alert */}
      {isBackendUnavailable && <BackendUnavailableAlert />}

      {/* Statistics */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">{t('statsTotal')}</CardTitle>
            <FolderTree className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{categories.length}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">{t('statsActive')}</CardTitle>
            <FolderTree className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {categories.filter(c => (c.isActive ?? c.is_active) !== false).length}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">{t('statsInactive')}</CardTitle>
            <FolderTree className="h-4 w-4 text-gray-400" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {categories.filter(c => (c.isActive ?? c.is_active) === false).length}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Categories Table */}
      <Card>
        <CardHeader>
          <div className="flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>{t('listTitle')}</CardTitle>
                <CardDescription>
                  {t('categoriesFound', { count: filteredCategories.length })}
                </CardDescription>
              </div>
              <div className="flex items-center gap-2">
                <Button size="sm" variant="outline" onClick={handleRefresh}>
                  <RefreshCw className="h-4 w-4 mr-2" />
                  {tCommon('refresh')}
                </Button>
                <Button size="sm" onClick={handleCreate}>
                  <Plus className="h-4 w-4 mr-2" />
                  {t('createCategory')}
                </Button>
              </div>
            </div>

            {/* Filters */}
            <div className="flex gap-4 flex-wrap">
              <div className="relative max-w-sm">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  placeholder={t('searchPlaceholder')}
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-9"
                />
              </div>
              <Select
                value={String(ministryFilter)}
                onValueChange={(v) => {
                  setMinistryFilter(v === 'all' ? 'all' : Number(v))
                  setSectorFilter('all')
                }}
              >
                <SelectTrigger className="w-[200px]">
                  <SelectValue placeholder={t('filterByMinistry')} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t('allMinistries')}</SelectItem>
                  {ministries.map((m) => (
                    <SelectItem key={m.id} value={String(m.id)}>{getLocalizedName(m, locale)}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select
                value={String(sectorFilter)}
                onValueChange={(v) => setSectorFilter(v === 'all' ? 'all' : Number(v))}
              >
                <SelectTrigger className="w-[200px]">
                  <SelectValue placeholder={t('filterBySector')} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t('allSectors')}</SelectItem>
                  {filteredSectorsForSelect.map((s) => (
                    <SelectItem key={s.id} value={String(s.id)}>{getLocalizedName(s, locale)}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select
                value={statusFilter}
                onValueChange={(v) => setStatusFilter(v as 'all' | 'active' | 'inactive')}
              >
                <SelectTrigger className="w-[180px]">
                  <SelectValue placeholder={t('filterByStatus')} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t('allStatuses')}</SelectItem>
                  <SelectItem value="active">{t('statusActive')}</SelectItem>
                  <SelectItem value="inactive">{t('statusInactive')}</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {isLoading && (
            <div className="flex items-center justify-center py-8">
              <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
              <span className="ml-2 text-muted-foreground">{t('loading')}</span>
            </div>
          )}

          {error && !isBackendUnavailable && (
            <div className="flex items-center justify-center py-8 text-red-500">
              <AlertTriangle className="h-5 w-5 mr-2" />
              {error}
            </div>
          )}

          {!isLoading && !error && sortedCategories.length === 0 && (
            <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
              <FolderTree className="h-12 w-12 mb-4 opacity-50" />
              <p>{t('noCategoriesFound')}</p>
            </div>
          )}

          {!isLoading && !error && sortedCategories.length > 0 && (
            <>
              <div className="border rounded-md overflow-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-8 px-2 -ml-2 font-medium"
                        onClick={() => handleSort('category_code')}
                      >
                        {t('tableCode')}
                        {getSortIcon('category_code')}
                      </Button>
                    </TableHead>
                    <TableHead>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-8 px-2 -ml-2 font-medium"
                        onClick={() => handleSort('name_es')}
                      >
                        {t('tableName')}
                        {getSortIcon('name_es')}
                      </Button>
                    </TableHead>
                    <TableHead className="hidden lg:table-cell">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-8 px-2 -ml-2 font-medium"
                        onClick={() => handleSort('sector_id')}
                      >
                        {t('tableSector')}
                        {getSortIcon('sector_id')}
                      </Button>
                    </TableHead>
                    <TableHead className="hidden lg:table-cell">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-8 px-2 -ml-2 font-medium"
                        onClick={() => handleSort('ministry_id')}
                      >
                        {t('tableMinistry')}
                        {getSortIcon('ministry_id')}
                      </Button>
                    </TableHead>
                    <TableHead className="hidden md:table-cell">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-8 px-2 -ml-2 font-medium"
                        onClick={() => handleSort('display_order')}
                      >
                        {t('tableOrder')}
                        {getSortIcon('display_order')}
                      </Button>
                    </TableHead>
                    <TableHead>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-8 px-2 -ml-2 font-medium"
                        onClick={() => handleSort('is_active')}
                      >
                        {t('tableStatus')}
                        {getSortIcon('is_active')}
                      </Button>
                    </TableHead>
                    <TableHead className="text-right">{t('tableActions')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {paginatedCategories.map((category) => (
                    <TableRow key={category.id}>
                      <TableCell className="font-mono text-sm">
                        {category.categoryCode || category.category_code}
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          {category.color && (
                            <div
                              className="w-3 h-3 rounded-full"
                              style={{ backgroundColor: category.color }}
                            />
                          )}
                          <span className="font-medium">{getLocalizedName(category, locale)}</span>
                        </div>
                      </TableCell>
                      <TableCell className="hidden lg:table-cell">{getSectorName(category.sectorId ?? category.sector_id)}</TableCell>
                      <TableCell className="hidden lg:table-cell">{getMinistryName(category.ministryId ?? category.ministry_id)}</TableCell>
                      <TableCell className="hidden md:table-cell">{category.displayOrder ?? category.display_order ?? 0}</TableCell>
                      <TableCell>
                        <Badge
                          variant="outline"
                          className={(category.isActive ?? category.is_active) !== false ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-700'}
                        >
                          {(category.isActive ?? category.is_active) !== false ? t('statusActive') : t('statusInactive')}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-2">
                          <Button variant="ghost" size="sm" onClick={() => handleEdit(category)}>
                            <Edit className="h-4 w-4 mr-1" />
                            {t('edit')}
                          </Button>
                          <Button variant="ghost" size="sm" onClick={() => handleDeleteClick(category)}>
                            <Trash2 className="h-4 w-4 mr-1" />
                            {t('delete')}
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              </div>

              {/* Pagination Controls */}
              <div className="flex items-center justify-between px-2 py-4 border-t">
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <span>{t('rowsPerPage')}:</span>
                  <Select
                    value={String(rowsPerPage)}
                    onValueChange={(v) => setRowsPerPage(Number(v))}
                  >
                    <SelectTrigger className="h-8 w-[70px]">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="10">10</SelectItem>
                      <SelectItem value="20">20</SelectItem>
                      <SelectItem value="50">50</SelectItem>
                      <SelectItem value="100">100</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="flex items-center gap-2">
                  <span className="text-sm text-muted-foreground">
                    {t('pageInfo', {
                      start: sortedCategories.length === 0 ? 0 : startIndex + 1,
                      end: Math.min(endIndex, sortedCategories.length),
                      total: sortedCategories.length
                    })}
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
                      onClick={() => setCurrentPage(currentPage - 1)}
                      disabled={currentPage === 1}
                    >
                      <ChevronLeft className="h-4 w-4" />
                    </Button>
                    <span className="text-sm px-2">
                      {t('pageOf', { current: currentPage, total: totalPages || 1 })}
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-8 w-8 p-0"
                      onClick={() => setCurrentPage(currentPage + 1)}
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
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* Create/Edit Dialog */}
      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>
              {selectedCategory ? t('editCategory') : t('createCategory')}
            </DialogTitle>
            <DialogDescription>
              {selectedCategory ? t('editCategoryDescription') : t('createCategoryDescription')}
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 py-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="category_code">{t('fieldCode')} *</Label>
                <Input
                  id="category_code"
                  value={formData.category_code}
                  onChange={(e) => setFormData({ ...formData, category_code: e.target.value })}
                  placeholder="e.g., CAT-001"
                  maxLength={20}
                  disabled={!!selectedCategory}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="service_type">{t('fieldServiceType')}</Label>
                <Select
                  value={formData.service_type || 'none'}
                  onValueChange={(v) => setFormData({ ...formData, service_type: v === 'none' ? null : v as ServiceTypeEnum })}
                >
                  <SelectTrigger>
                    <SelectValue placeholder={t('selectServiceType')} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">{t('noServiceType')}</SelectItem>
                    {SERVICE_TYPES.map((type) => (
                      <SelectItem key={type} value={type}>{type.replace(/_/g, ' ')}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="ministry_id">{t('fieldMinistry')}</Label>
                <Select
                  value={formData.ministry_id ? String(formData.ministry_id) : 'none'}
                  onValueChange={(v) => {
                    setFormData({
                      ...formData,
                      ministry_id: v === 'none' ? null : Number(v),
                      sector_id: null
                    })
                  }}
                >
                  <SelectTrigger>
                    <SelectValue placeholder={t('selectMinistry')} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">{t('noMinistry')}</SelectItem>
                    {ministries.map((m) => (
                      <SelectItem key={m.id} value={String(m.id)}>{getLocalizedName(m, locale)}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="sector_id">{t('fieldSector')}</Label>
                <Select
                  value={formData.sector_id ? String(formData.sector_id) : 'none'}
                  onValueChange={(v) => setFormData({ ...formData, sector_id: v === 'none' ? null : Number(v) })}
                >
                  <SelectTrigger>
                    <SelectValue placeholder={t('selectSector')} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">{t('noSector')}</SelectItem>
                    {(formData.ministry_id
                      ? sectors.filter(s => (s.ministryId ?? s.ministry_id) === formData.ministry_id)
                      : sectors
                    ).map((s) => (
                      <SelectItem key={s.id} value={String(s.id)}>{getLocalizedName(s, locale)}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="name_es">{t('fieldName')} *</Label>
              <Input
                id="name_es"
                value={formData.name_es}
                onChange={(e) => setFormData({ ...formData, name_es: e.target.value })}
                placeholder="e.g., Impuestos sobre la Renta"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="description_es">{t('fieldDescription')}</Label>
              <Textarea
                id="description_es"
                value={formData.description_es}
                onChange={(e) => setFormData({ ...formData, description_es: e.target.value })}
                rows={3}
              />
            </div>

            <div className="grid grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label htmlFor="display_order">{t('fieldOrder')}</Label>
                <Input
                  id="display_order"
                  type="number"
                  value={formData.display_order}
                  onChange={(e) => setFormData({ ...formData, display_order: Number(e.target.value) })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="icon">{t('fieldIcon')}</Label>
                <Input
                  id="icon"
                  value={formData.icon}
                  onChange={(e) => setFormData({ ...formData, icon: e.target.value })}
                  placeholder="e.g., folder"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="color">{t('fieldColor')}</Label>
                <div className="flex gap-2">
                  <Input
                    id="color"
                    type="color"
                    value={formData.color}
                    onChange={(e) => setFormData({ ...formData, color: e.target.value })}
                    className="w-12 h-10 p-1"
                  />
                  <Input
                    value={formData.color}
                    onChange={(e) => setFormData({ ...formData, color: e.target.value })}
                    className="flex-1"
                  />
                </div>
              </div>
            </div>

            <div className="flex items-center space-x-2">
              <Switch
                id="is_active"
                checked={formData.is_active}
                onCheckedChange={(checked) => setFormData({ ...formData, is_active: checked })}
              />
              <Label htmlFor="is_active">{t('fieldActive')}</Label>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setIsDialogOpen(false)}>
              {tCommon('cancel')}
            </Button>
            <Button onClick={handleSubmit} disabled={isSubmitting}>
              {isSubmitting ? (
                <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
              ) : null}
              {selectedCategory ? t('saveChanges') : t('create')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={isDeleteDialogOpen} onOpenChange={setIsDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('deleteConfirmTitle')}</AlertDialogTitle>
            <AlertDialogDescription>
              {t('deleteConfirmDescription', { name: selectedCategory ? getLocalizedName(selectedCategory, locale) : '' })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{tCommon('cancel')}</AlertDialogCancel>
            <AlertDialogAction onClick={handleDelete} className="bg-red-600 hover:bg-red-700">
              {t('delete')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
