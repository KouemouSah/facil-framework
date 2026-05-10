'use client'

/**
 * Push Templates Admin Page
 * CRUD management for push notification templates
 */

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useLocale, useTranslations } from 'next-intl'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
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
import { Bell, RefreshCw, Plus, Edit, Trash2, Search, Eye, Smartphone, Tablet, Monitor } from 'lucide-react'
import { useToast } from '@/hooks/use-toast'
import { usePushTemplates } from '@/modules/communications/hooks/usePushTemplates'
import { PushPreview } from '@/modules/communications/components/PushPreview'
import type { PushTemplateResponse, PushNotificationPreview } from '@/modules/communications/types'

const PLATFORMS = [
  { value: 'all', label: 'All Platforms', icon: Bell },
  { value: 'ios', label: 'iOS', icon: Smartphone },
  { value: 'android', label: 'Android', icon: Tablet },
  { value: 'web', label: 'Web', icon: Monitor },
]

export default function PushTemplatesPage() {
  const locale = useLocale()
  const router = useRouter()
  const t = useTranslations('admin.pushTemplates')
  const tCommon = useTranslations('common')
  const { toast } = useToast()

  const {
    templates,
    total,
    isLoading,
    error,
    stats,
    fetchTemplates,
    fetchStats,
    deleteTemplate,
    previewTemplate,
  } = usePushTemplates()

  // Filter states
  const [searchQuery, setSearchQuery] = useState('')
  const [platformFilter, setPlatformFilter] = useState<string>('all')
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'inactive'>('all')

  // Pagination
  const [currentPage, setCurrentPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)

  const handlePageSizeChange = (newSize: string) => {
    setPageSize(Number(newSize))
    setCurrentPage(1) // Reset to first page when changing page size
  }

  const totalPages = Math.ceil(total / pageSize)

  // Preview dialog
  const [isPreviewOpen, setIsPreviewOpen] = useState(false)
  const [previewData, setPreviewData] = useState<PushNotificationPreview | null>(null)
  const [previewLanguage, setPreviewLanguage] = useState('es')

  // Delete dialog
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false)
  const [selectedTemplate, setSelectedTemplate] = useState<PushTemplateResponse | null>(null)

  // Fetch data on mount and when filters change
  useEffect(() => {
    fetchTemplates({
      page: currentPage,
      pageSize,
      search: searchQuery || undefined,
      platform: platformFilter !== 'all' ? platformFilter as 'ios' | 'android' | 'web' | 'all' : undefined,
      isActive: statusFilter === 'all' ? undefined : statusFilter === 'active',
    })
  }, [currentPage, pageSize, searchQuery, platformFilter, statusFilter, fetchTemplates])

  // Fetch stats
  useEffect(() => {
    fetchStats()
  }, [fetchStats])

  const handleRefresh = () => {
    fetchTemplates({ page: currentPage, pageSize })
    fetchStats()
  }

  const handleCreate = () => {
    router.push(`/${locale}/dashboard/admin/communications/push-templates/new`)
  }

  const handleEdit = (template: PushTemplateResponse) => {
    router.push(`/${locale}/dashboard/admin/communications/push-templates/${template.id}/edit`)
  }

  const handleDeleteClick = (template: PushTemplateResponse) => {
    setSelectedTemplate(template)
    setIsDeleteDialogOpen(true)
  }

  const handleDelete = async () => {
    if (!selectedTemplate) return

    const success = await deleteTemplate(selectedTemplate.id)
    if (success) {
      toast({
        title: t('successTitle'),
        description: t('templateDeleted'),
      })
      setIsDeleteDialogOpen(false)
      handleRefresh()
    } else {
      toast({
        variant: 'destructive',
        title: t('errorTitle'),
        description: t('errorDeleting'),
      })
    }
  }

  const handlePreview = async (template: PushTemplateResponse) => {
    const preview = await previewTemplate(template.id, previewLanguage)
    if (preview) {
      setPreviewData(preview)
      setIsPreviewOpen(true)
    } else {
      toast({
        variant: 'destructive',
        title: t('errorTitle'),
        description: t('errorPreviewing'),
      })
    }
  }

  const getLocalizedName = (template: PushTemplateResponse) => {
    if (locale === 'fr' && template.nameFr) return template.nameFr
    if (locale === 'en' && template.nameEn) return template.nameEn
    return template.nameEs
  }

  const getPlatformIcon = (platform: string) => {
    const platformData = PLATFORMS.find(p => p.value === platform)
    return platformData ? platformData.icon : Bell
  }

  const getPlatformLabel = (platform: string) => {
    const platformData = PLATFORMS.find(p => p.value === platform)
    return platformData ? platformData.label : platform
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">{t('title')}</h1>
        <p className="text-muted-foreground mt-2">{t('subtitle')}</p>
      </div>

      {/* Statistics */}
      {stats && (
        <div className="grid gap-4 md:grid-cols-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">{t('statsTotal')}</CardTitle>
              <Bell className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.total}</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">{t('statsActive')}</CardTitle>
              <Bell className="h-4 w-4 text-green-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.active}</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">{t('statsInactive')}</CardTitle>
              <Bell className="h-4 w-4 text-gray-400" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.inactive}</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">{t('statsByPlatform')}</CardTitle>
              <Smartphone className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-xs space-y-1">
                <div>All: {stats.byPlatform.all}</div>
                <div>iOS: {stats.byPlatform.ios}</div>
                <div>Android: {stats.byPlatform.android}</div>
                <div>Web: {stats.byPlatform.web}</div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Templates Table */}
      <Card>
        <CardHeader>
          <div className="flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>{t('listTitle')}</CardTitle>
                <CardDescription>
                  {t('templatesFound', { count: total })}
                </CardDescription>
              </div>
              <div className="flex items-center gap-2">
                <Button size="sm" variant="outline" onClick={handleRefresh}>
                  <RefreshCw className="h-4 w-4 mr-2" />
                  {tCommon('refresh')}
                </Button>
                <Button size="sm" onClick={handleCreate}>
                  <Plus className="h-4 w-4 mr-2" />
                  {t('createTemplate')}
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
              <Select value={platformFilter} onValueChange={setPlatformFilter}>
                <SelectTrigger className="w-[180px]">
                  <SelectValue placeholder={t('filterByPlatform')} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t('allPlatforms')}</SelectItem>
                  {PLATFORMS.map((platform) => (
                    <SelectItem key={platform.value} value={platform.value}>
                      {platform.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select value={statusFilter} onValueChange={(v) => setStatusFilter(v as 'all' | 'active' | 'inactive')}>
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

          {error && (
            <div className="flex flex-col items-center justify-center py-8 text-destructive">
              <Bell className="h-12 w-12 mb-4 opacity-50" />
              <p className="font-medium">{t('errorTitle')}</p>
              <p className="text-sm text-muted-foreground mt-1">{error}</p>
              <Button variant="outline" size="sm" className="mt-4" onClick={handleRefresh}>
                <RefreshCw className="h-4 w-4 mr-2" />
                {tCommon('retry')}
              </Button>
            </div>
          )}

          {!isLoading && !error && templates.length === 0 && (
            <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
              <Bell className="h-12 w-12 mb-4 opacity-50" />
              <p>{t('noTemplatesFound')}</p>
            </div>
          )}

          {!isLoading && !error && templates.length > 0 && (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t('tableCode')}</TableHead>
                    <TableHead>{t('tableName')}</TableHead>
                    <TableHead>{t('tablePlatform')}</TableHead>
                    <TableHead>{t('tableVariables')}</TableHead>
                    <TableHead>{t('tableStatus')}</TableHead>
                    <TableHead className="text-right">{t('tableActions')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {templates.map((template) => {
                    const PlatformIcon = getPlatformIcon(template.platform)
                    return (
                      <TableRow key={template.id}>
                        <TableCell className="font-mono text-sm">
                          {template.templateCode}
                        </TableCell>
                        <TableCell>
                          <span className="font-medium">{getLocalizedName(template)}</span>
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <PlatformIcon className="h-4 w-4" />
                            <span className="text-sm">{getPlatformLabel(template.platform)}</span>
                          </div>
                        </TableCell>
                        <TableCell>
                          <Badge variant="secondary" className="text-xs">
                            {template.variables?.length || 0} vars
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <Badge
                            variant="outline"
                            className={template.isActive ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-700'}
                          >
                            {template.isActive ? t('statusActive') : t('statusInactive')}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex items-center justify-end gap-1">
                            <Button variant="ghost" size="sm" onClick={() => handlePreview(template)}>
                              <Eye className="h-4 w-4" />
                            </Button>
                            <Button variant="ghost" size="sm" onClick={() => handleEdit(template)}>
                              <Edit className="h-4 w-4" />
                            </Button>
                            <Button variant="ghost" size="sm" onClick={() => handleDeleteClick(template)}>
                              <Trash2 className="h-4 w-4 text-destructive" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>

              {/* Pagination */}
              <div className="flex items-center justify-between border-t p-4">
                <div className="flex items-center gap-4">
                  <div className="text-sm text-muted-foreground">
                    {tCommon('showing')} {(currentPage - 1) * pageSize + 1} - {Math.min(currentPage * pageSize, total)} {tCommon('of')} {total}
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-muted-foreground">{t('rows') || 'Rows'}:</span>
                    <Select value={String(pageSize)} onValueChange={handlePageSizeChange}>
                      <SelectTrigger className="w-[70px] h-8">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="10">10</SelectItem>
                        <SelectItem value="20">20</SelectItem>
                        <SelectItem value="50">50</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                {totalPages > 1 && (
                  <div className="flex items-center gap-1">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setCurrentPage(1)}
                      disabled={currentPage === 1}
                    >
                      {'<<'}
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                      disabled={currentPage === 1}
                    >
                      {tCommon('previous')}
                    </Button>
                    {/* Page Numbers */}
                    {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                      let pageNum: number
                      if (totalPages <= 5) {
                        pageNum = i + 1
                      } else if (currentPage <= 3) {
                        pageNum = i + 1
                      } else if (currentPage >= totalPages - 2) {
                        pageNum = totalPages - 4 + i
                      } else {
                        pageNum = currentPage - 2 + i
                      }
                      return (
                        <Button
                          key={pageNum}
                          variant={currentPage === pageNum ? 'default' : 'outline'}
                          size="sm"
                          className="w-9"
                          onClick={() => setCurrentPage(pageNum)}
                        >
                          {pageNum}
                        </Button>
                      )
                    })}
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                      disabled={currentPage === totalPages}
                    >
                      {tCommon('next')}
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setCurrentPage(totalPages)}
                      disabled={currentPage === totalPages}
                    >
                      {'>>'}
                    </Button>
                  </div>
                )}
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* Preview Dialog */}
      <Dialog open={isPreviewOpen} onOpenChange={setIsPreviewOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{t('previewTitle')}</DialogTitle>
            <DialogDescription>
              {t('previewDescription')}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <Select value={previewLanguage} onValueChange={setPreviewLanguage}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Language" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="es">Español</SelectItem>
                <SelectItem value="fr">Français</SelectItem>
                <SelectItem value="en">English</SelectItem>
              </SelectContent>
            </Select>

            {previewData && <PushPreview preview={previewData} />}
          </div>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={isDeleteDialogOpen} onOpenChange={setIsDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('deleteConfirmTitle')}</AlertDialogTitle>
            <AlertDialogDescription>
              {t('deleteConfirmDescription', { name: selectedTemplate ? getLocalizedName(selectedTemplate) : '' })}
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
