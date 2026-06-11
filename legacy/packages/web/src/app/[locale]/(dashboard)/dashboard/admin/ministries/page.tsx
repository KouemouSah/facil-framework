'use client'

/**
 * Ministries Admin Page
 * Complete CRUD management for ministries hierarchy
 *
 * @module dashboard/admin/ministries
 * @author Claude Code
 * @date 2025-12-05
 */

import { useState, useEffect } from 'react'
import { useLocale, useTranslations } from 'next-intl'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { RichTextEditor } from '@/components/ui/rich-text-editor'
import { Switch } from '@/components/ui/switch'
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
import { Building2, RefreshCw, Plus, Edit, Trash2, Search, AlertTriangle, ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight, ArrowUpDown, ArrowUp, ArrowDown } from 'lucide-react'
import { useToast } from '@/hooks/use-toast'
import fiscalServicesAPI from '@/modules/fiscal-services/services/api'
import type { Ministry } from '@/types/fiscal-service'
import { getLocalizedName } from '@/types/fiscal-service'
import { BackendUnavailableAlert } from '@/modules/admin/components'
import { MinistryImageUpload } from '@/components/ui/ministry-image-upload'

interface MinistryFormData {
  ministry_code: string
  name_es: string
  description_es: string
  display_order: number
  icon: string
  color: string
  website_url: string
  contact_email: string
  contact_phone: string
  is_active: boolean
}

const defaultFormData: MinistryFormData = {
  ministry_code: '',
  name_es: '',
  description_es: '',
  display_order: 0,
  icon: '',
  color: '#3B82F6',
  website_url: '',
  contact_email: '',
  contact_phone: '',
  is_active: true,
}

export default function MinistriesPage() {
  const locale = useLocale()
  const t = useTranslations('admin.ministries')
  const tCommon = useTranslations('common')
  const { toast } = useToast()

  // Data states
  const [ministries, setMinistries] = useState<Ministry[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isBackendUnavailable, setIsBackendUnavailable] = useState(false)

  // Filter states
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'inactive'>('all')

  // Pagination states
  const [currentPage, setCurrentPage] = useState(1)
  const [rowsPerPage, setRowsPerPage] = useState(20)

  // Sorting states
  type SortColumn = 'ministry_code' | 'name_es' | 'display_order' | 'is_active'
  const [sortColumn, setSortColumn] = useState<SortColumn | null>(null)
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc')

  // Modal states
  const [isDialogOpen, setIsDialogOpen] = useState(false)
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false)
  const [selectedMinistry, setSelectedMinistry] = useState<Ministry | null>(null)
  const [formData, setFormData] = useState<MinistryFormData>(defaultFormData)
  const [isSubmitting, setIsSubmitting] = useState(false)

  // Fetch ministries
  const fetchMinistries = async () => {
    setIsLoading(true)
    setError(null)

    try {
      const data = await fiscalServicesAPI.hierarchy.ministries.list(locale)
      setMinistries(data)
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
    fetchMinistries()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [locale])

  const handleRefresh = () => {
    fetchMinistries()
  }

  // Open create dialog
  const handleCreate = () => {
    setSelectedMinistry(null)
    setFormData(defaultFormData)
    setIsDialogOpen(true)
  }

  // Open edit dialog
  const handleEdit = (ministry: Ministry) => {
    setSelectedMinistry(ministry)
    setFormData({
      ministry_code: ministry.ministryCode || ministry.ministry_code || '',
      name_es: ministry.nameEs || ministry.name_es || '',
      description_es: ministry.descriptionEs || ministry.description_es || '',
      display_order: ministry.displayOrder ?? ministry.display_order ?? 0,
      icon: ministry.icon || '',
      color: ministry.color || '#3B82F6',
      website_url: ministry.websiteUrl || ministry.website_url || '',
      contact_email: ministry.contactEmail || ministry.contact_email || '',
      contact_phone: ministry.contactPhone || ministry.contact_phone || '',
      is_active: (ministry.isActive ?? ministry.is_active) !== false,
    })
    setIsDialogOpen(true)
  }

  // Open delete confirmation
  const handleDeleteClick = (ministry: Ministry) => {
    setSelectedMinistry(ministry)
    setIsDeleteDialogOpen(true)
  }

  // Submit form (create or update)
  const handleSubmit = async () => {
    setIsSubmitting(true)

    try {
      if (!formData.ministry_code || !formData.name_es) {
        toast({
          variant: 'destructive',
          title: t('errorTitle'),
          description: t('requiredFields'),
        })
        setIsSubmitting(false)
        return
      }

      if (selectedMinistry) {
        // Update
        await fiscalServicesAPI.hierarchy.ministries.update(selectedMinistry.id, formData)
        toast({
          title: t('successTitle'),
          description: t('ministryUpdated'),
        })
      } else {
        // Create
        await fiscalServicesAPI.hierarchy.ministries.create(formData as unknown as Omit<Ministry, 'id' | 'createdAt' | 'updatedAt'>)
        toast({
          title: t('successTitle'),
          description: t('ministryCreated'),
        })
      }

      setIsDialogOpen(false)
      fetchMinistries()
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

  // Delete ministry
  const handleDelete = async () => {
    if (!selectedMinistry) return

    try {
      await fiscalServicesAPI.hierarchy.ministries.delete(selectedMinistry.id)
      toast({
        title: t('successTitle'),
        description: t('ministryDeleted'),
      })
      setIsDeleteDialogOpen(false)
      fetchMinistries()
    } catch (err) {
      toast({
        variant: 'destructive',
        title: t('errorTitle'),
        description: err instanceof Error ? err.message : t('errorDeleting'),
      })
    }
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

  // Filter ministries
  const filteredMinistries = ministries.filter(m => {
    const name = getLocalizedName(m, locale)
    const code = m.ministryCode || m.ministry_code || ''
    const matchesSearch = searchQuery === '' ||
      name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      code.toLowerCase().includes(searchQuery.toLowerCase())

    const isActive = (m.isActive ?? m.is_active) !== false
    const matchesStatus = statusFilter === 'all' ||
      (statusFilter === 'active' && isActive) ||
      (statusFilter === 'inactive' && !isActive)

    return matchesSearch && matchesStatus
  })

  // Sort ministries
  const sortedMinistries = [...filteredMinistries].sort((a, b) => {
    if (!sortColumn) return 0

    let aValue: string | number | boolean
    let bValue: string | number | boolean

    switch (sortColumn) {
      case 'ministry_code':
        aValue = a.ministryCode || a.ministry_code || ''
        bValue = b.ministryCode || b.ministry_code || ''
        break
      case 'name_es':
        aValue = a.nameEs || a.name_es || ''
        bValue = b.nameEs || b.name_es || ''
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
  const totalPages = Math.ceil(sortedMinistries.length / rowsPerPage)
  const startIndex = (currentPage - 1) * rowsPerPage
  const endIndex = startIndex + rowsPerPage
  const paginatedMinistries = sortedMinistries.slice(startIndex, endIndex)

  // Reset to first page when filters change
  useEffect(() => {
    setCurrentPage(1)
  }, [searchQuery, statusFilter, rowsPerPage])

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
            <Building2 className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{ministries.length}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">{t('statsActive')}</CardTitle>
            <Building2 className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {ministries.filter(m => (m.isActive ?? m.is_active) !== false).length}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">{t('statsInactive')}</CardTitle>
            <Building2 className="h-4 w-4 text-gray-400" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {ministries.filter(m => (m.isActive ?? m.is_active) === false).length}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Ministries Table */}
      <Card>
        <CardHeader>
          <div className="flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>{t('listTitle')}</CardTitle>
                <CardDescription>
                  {t('ministriesFound', { count: filteredMinistries.length })}
                </CardDescription>
              </div>
              <div className="flex items-center gap-2">
                <Button size="sm" variant="outline" onClick={handleRefresh}>
                  <RefreshCw className="h-4 w-4 mr-2" />
                  {tCommon('refresh')}
                </Button>
                <Button size="sm" onClick={handleCreate}>
                  <Plus className="h-4 w-4 mr-2" />
                  {t('createMinistry')}
                </Button>
              </div>
            </div>

            {/* Filters */}
            <div className="flex gap-4">
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

          {!isLoading && !error && sortedMinistries.length === 0 && (
            <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
              <Building2 className="h-12 w-12 mb-4 opacity-50" />
              <p>{t('noMinistriesFound')}</p>
            </div>
          )}

          {!isLoading && !error && sortedMinistries.length > 0 && (
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
                        onClick={() => handleSort('ministry_code')}
                      >
                        {t('tableCode')}
                        {getSortIcon('ministry_code')}
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
                  {paginatedMinistries.map((ministry) => (
                    <TableRow key={ministry.id}>
                      <TableCell className="font-mono text-sm">
                        {ministry.ministryCode || ministry.ministry_code}
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          {ministry.color && (
                            <div
                              className="w-3 h-3 rounded-full"
                              style={{ backgroundColor: ministry.color }}
                            />
                          )}
                          <span className="font-medium">{getLocalizedName(ministry, locale)}</span>
                        </div>
                      </TableCell>
                      <TableCell className="hidden md:table-cell">{ministry.displayOrder ?? ministry.display_order ?? 0}</TableCell>
                      <TableCell>
                        <Badge
                          variant="outline"
                          className={(ministry.isActive ?? ministry.is_active) !== false ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-700'}
                        >
                          {(ministry.isActive ?? ministry.is_active) !== false ? t('statusActive') : t('statusInactive')}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-2">
                          <Button variant="ghost" size="sm" onClick={() => handleEdit(ministry)}>
                            <Edit className="h-4 w-4 mr-1" />
                            {t('edit')}
                          </Button>
                          <Button variant="ghost" size="sm" onClick={() => handleDeleteClick(ministry)}>
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
                      start: sortedMinistries.length === 0 ? 0 : startIndex + 1,
                      end: Math.min(endIndex, sortedMinistries.length),
                      total: sortedMinistries.length
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
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              {selectedMinistry ? t('editMinistry') : t('createMinistry')}
            </DialogTitle>
            <DialogDescription>
              {selectedMinistry ? t('editMinistryDescription') : t('createMinistryDescription')}
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 py-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="ministry_code">{t('fieldCode')} *</Label>
                <Input
                  id="ministry_code"
                  value={formData.ministry_code}
                  onChange={(e) => setFormData({ ...formData, ministry_code: e.target.value })}
                  placeholder="e.g., MHAP"
                  maxLength={10}
                  disabled={!!selectedMinistry}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="display_order">{t('fieldOrder')}</Label>
                <Input
                  id="display_order"
                  type="number"
                  value={formData.display_order}
                  onChange={(e) => setFormData({ ...formData, display_order: Number(e.target.value) })}
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="name_es">{t('fieldName')} *</Label>
              <Input
                id="name_es"
                value={formData.name_es}
                onChange={(e) => setFormData({ ...formData, name_es: e.target.value })}
                placeholder="e.g., Ministerio de Hacienda y Presupuestos"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="description_es">{t('fieldDescription')}</Label>
              <RichTextEditor
                value={formData.description_es}
                onChange={(value) => setFormData({ ...formData, description_es: value })}
                placeholder={t('descriptionPlaceholder') || 'Describe the ministry...'}
              />
            </div>

            {/* Ministry Image Upload */}
            <MinistryImageUpload
              ministryId={selectedMinistry?.id}
              onUploadSuccess={() => {
                toast({
                  title: t('successTitle'),
                  description: t('imageUploaded') || 'Imagen subida correctamente',
                })
              }}
              onUploadError={(error) => {
                toast({
                  variant: 'destructive',
                  title: t('errorTitle'),
                  description: error,
                })
              }}
              onDelete={() => {
                toast({
                  title: t('successTitle'),
                  description: t('imageDeleted') || 'Imagen eliminada',
                })
              }}
              disabled={!selectedMinistry?.id}
              labels={{
                upload: t('uploadImage') || 'Subir imagen',
                change: t('changeImage') || 'Cambiar imagen',
                delete: t('deleteImage') || 'Eliminar',
                preview: t('imagePreview') || 'Vista previa',
                dimensions: '800 x 600 px',
                uploading: t('uploading') || 'Subiendo...',
                dropHere: t('dropHere') || 'Arrastra la imagen aquí',
                orClickToSelect: t('orClickToSelect') || 'o haz clic para seleccionar',
                error: t('errorTitle') || 'Error',
              }}
            />

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="icon">{t('fieldIcon')}</Label>
                <Input
                  id="icon"
                  value={formData.icon}
                  onChange={(e) => setFormData({ ...formData, icon: e.target.value })}
                  placeholder="e.g., building-columns"
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

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="contact_email">{t('fieldEmail')}</Label>
                <Input
                  id="contact_email"
                  type="email"
                  value={formData.contact_email}
                  onChange={(e) => setFormData({ ...formData, contact_email: e.target.value })}
                  placeholder="info@ministry.gq"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="contact_phone">{t('fieldPhone')}</Label>
                <Input
                  id="contact_phone"
                  value={formData.contact_phone}
                  onChange={(e) => setFormData({ ...formData, contact_phone: e.target.value })}
                  placeholder="+240 222 123 456"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="website_url">{t('fieldWebsite')}</Label>
              <Input
                id="website_url"
                type="url"
                value={formData.website_url}
                onChange={(e) => setFormData({ ...formData, website_url: e.target.value })}
                placeholder="https://www.ministry.gq"
              />
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
              {selectedMinistry ? t('saveChanges') : t('create')}
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
              {t('deleteConfirmDescription', { name: selectedMinistry ? getLocalizedName(selectedMinistry, locale) : '' })}
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
