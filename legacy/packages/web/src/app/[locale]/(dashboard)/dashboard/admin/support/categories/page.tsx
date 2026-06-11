'use client'

import { useEffect, useState } from 'react'
import { useTranslations } from 'next-intl'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Checkbox } from '@/components/ui/checkbox'
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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { useToast } from '@/hooks/use-toast'
import { Plus, Pencil, Trash2, Loader2, AlertCircle, RefreshCw } from 'lucide-react'
import { useSupport } from '@/modules/support'
import type { SupportCategory, SupportCategoryCreate, SupportCategoryUpdate, TargetRole } from '@/modules/support'

export default function AdminSupportCategoriesPage() {
  const t = useTranslations('support')
  const { toast } = useToast()

  const {
    categories,
    isLoading,
    error,
    loadCategories,
    createCategory,
    updateCategory,
    deleteCategory,
    clearError,
  } = useSupport({ autoLoadCategories: false })

  // Form state
  const [isFormOpen, setIsFormOpen] = useState(false)
  const [isDeleteOpen, setIsDeleteOpen] = useState(false)
  const [editingCategory, setEditingCategory] = useState<SupportCategory | null>(null)
  const [deletingCategory, setDeletingCategory] = useState<SupportCategory | null>(null)
  const [formData, setFormData] = useState<SupportCategoryCreate>({
    code: '',
    nameEs: '',
    nameFr: '',
    nameEn: '',
    descriptionEs: '',
    descriptionFr: '',
    descriptionEn: '',
    targetRole: 'all',
    icon: '',
    isActive: true,
    sortOrder: 0,
  })
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    loadCategories()
  }, [loadCategories])

  const resetForm = () => {
    setFormData({
      code: '',
      nameEs: '',
      nameFr: '',
      nameEn: '',
      descriptionEs: '',
      descriptionFr: '',
      descriptionEn: '',
      targetRole: 'all',
      icon: '',
      isActive: true,
      sortOrder: 0,
    })
    setEditingCategory(null)
  }

  const handleOpenCreate = () => {
    resetForm()
    setIsFormOpen(true)
  }

  const handleOpenEdit = (category: SupportCategory) => {
    setEditingCategory(category)
    setFormData({
      code: category.code,
      nameEs: category.nameEs,
      nameFr: category.nameFr || '',
      nameEn: category.nameEn || '',
      descriptionEs: category.descriptionEs || '',
      descriptionFr: category.descriptionFr || '',
      descriptionEn: category.descriptionEn || '',
      targetRole: category.targetRole as TargetRole,
      icon: category.icon || '',
      isActive: category.isActive,
      sortOrder: category.sortOrder,
    })
    setIsFormOpen(true)
  }

  const handleOpenDelete = (category: SupportCategory) => {
    setDeletingCategory(category)
    setIsDeleteOpen(true)
  }

  const handleSubmit = async () => {
    if (!formData.code || !formData.nameEs) {
      toast({
        title: t('errorRequired'),
        description: t('codeAndNameRequired'),
        variant: 'destructive',
      })
      return
    }

    setSubmitting(true)
    try {
      if (editingCategory) {
        const updateData: SupportCategoryUpdate = {
          nameEs: formData.nameEs,
          nameFr: formData.nameFr || undefined,
          nameEn: formData.nameEn || undefined,
          descriptionEs: formData.descriptionEs || undefined,
          descriptionFr: formData.descriptionFr || undefined,
          descriptionEn: formData.descriptionEn || undefined,
          targetRole: formData.targetRole,
          icon: formData.icon || undefined,
          isActive: formData.isActive,
          sortOrder: formData.sortOrder,
        }
        const result = await updateCategory(editingCategory.id, updateData)
        if (result) {
          toast({
            title: t('categoryUpdated'),
            description: t('categoryUpdatedMessage'),
          })
          setIsFormOpen(false)
          resetForm()
        }
      } else {
        const result = await createCategory(formData)
        if (result) {
          toast({
            title: t('categoryCreated'),
            description: t('categoryCreatedMessage'),
          })
          setIsFormOpen(false)
          resetForm()
        }
      }
    } catch (error) {
      toast({
        title: t('errorRequired'),
        description: String(error),
        variant: 'destructive',
      })
    } finally {
      setSubmitting(false)
    }
  }

  const handleDelete = async () => {
    if (!deletingCategory) return

    setSubmitting(true)
    try {
      const success = await deleteCategory(deletingCategory.id)
      if (success) {
        toast({
          title: t('categoryDeleted'),
          description: t('categoryDeletedMessage'),
        })
        setIsDeleteOpen(false)
        setDeletingCategory(null)
      }
    } catch (error) {
      toast({
        title: t('errorRequired'),
        description: String(error),
        variant: 'destructive',
      })
    } finally {
      setSubmitting(false)
    }
  }

  const getTargetRoleLabel = (role: string) => {
    switch (role) {
      case 'admin':
        return t('targetRoles.admin')
      case 'agent':
        return t('targetRoles.agent')
      case 'all':
      default:
        return t('targetRoles.all')
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">{t('categoriesTitle')}</h1>
          <p className="text-muted-foreground mt-2">{t('categoriesDescription')}</p>
        </div>
        <Button onClick={handleOpenCreate}>
          <Plus className="h-4 w-4 mr-2" />
          {t('createCategory')}
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{t('categoryList')}</CardTitle>
          <CardDescription>{t('categoryListDescription')}</CardDescription>
        </CardHeader>
        <CardContent>
          {error && (
            <Alert variant="destructive" className="mb-4">
              <AlertCircle className="h-4 w-4" />
              <AlertTitle>{t('errorLoadingCategories')}</AlertTitle>
              <AlertDescription className="flex items-center justify-between">
                <span>{error}</span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    clearError()
                    loadCategories()
                  }}
                >
                  <RefreshCw className="h-4 w-4 mr-2" />
                  {t('retry')}
                </Button>
              </AlertDescription>
            </Alert>
          )}
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin" />
            </div>
          ) : categories.length === 0 && !error ? (
            <div className="text-center py-8 text-muted-foreground">
              {t('noCategories')}
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('tableCode')}</TableHead>
                  <TableHead>{t('tableName')}</TableHead>
                  <TableHead>{t('tableTargetRole')}</TableHead>
                  <TableHead>{t('tableSortOrder')}</TableHead>
                  <TableHead>{t('tableStatus')}</TableHead>
                  <TableHead className="text-right">{t('tableActions')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {categories.map((category) => (
                  <TableRow key={category.id}>
                    <TableCell className="font-mono">{category.code}</TableCell>
                    <TableCell>{category.nameEs}</TableCell>
                    <TableCell>
                      <Badge variant="outline">
                        {getTargetRoleLabel(category.targetRole as string)}
                      </Badge>
                    </TableCell>
                    <TableCell>{category.sortOrder}</TableCell>
                    <TableCell>
                      <Badge variant={category.isActive ? 'default' : 'secondary'}>
                        {category.isActive ? t('active') : t('inactive')}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-2">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleOpenEdit(category)}
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleOpenDelete(category)}
                        >
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Create/Edit Dialog */}
      <Dialog open={isFormOpen} onOpenChange={setIsFormOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              {editingCategory ? t('editCategory') : t('createCategory')}
            </DialogTitle>
            <DialogDescription>
              {editingCategory ? t('editCategoryDescription') : t('createCategoryDescription')}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">{t('categoryCode')} *</label>
                <Input
                  value={formData.code}
                  onChange={(e) => setFormData({ ...formData, code: e.target.value.toUpperCase() })}
                  placeholder="TECH_SUPPORT"
                  disabled={!!editingCategory}
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">{t('targetRole')}</label>
                <Select
                  value={formData.targetRole as string}
                  onValueChange={(value) => setFormData({ ...formData, targetRole: value as TargetRole })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">{t('targetRoles.all')}</SelectItem>
                    <SelectItem value="admin">{t('targetRoles.admin')}</SelectItem>
                    <SelectItem value="agent">{t('targetRoles.agent')}</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">{t('nameEs')} *</label>
              <Input
                value={formData.nameEs}
                onChange={(e) => setFormData({ ...formData, nameEs: e.target.value })}
                placeholder={t('nameEsPlaceholder')}
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">{t('nameFr')}</label>
                <Input
                  value={formData.nameFr}
                  onChange={(e) => setFormData({ ...formData, nameFr: e.target.value })}
                  placeholder={t('nameFrPlaceholder')}
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">{t('nameEn')}</label>
                <Input
                  value={formData.nameEn}
                  onChange={(e) => setFormData({ ...formData, nameEn: e.target.value })}
                  placeholder={t('nameEnPlaceholder')}
                />
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">{t('descriptionEs')}</label>
              <Textarea
                value={formData.descriptionEs}
                onChange={(e) => setFormData({ ...formData, descriptionEs: e.target.value })}
                placeholder={t('descriptionEsPlaceholder')}
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">{t('descriptionFr')}</label>
                <Textarea
                  value={formData.descriptionFr}
                  onChange={(e) => setFormData({ ...formData, descriptionFr: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">{t('descriptionEn')}</label>
                <Textarea
                  value={formData.descriptionEn}
                  onChange={(e) => setFormData({ ...formData, descriptionEn: e.target.value })}
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">{t('icon')}</label>
                <Input
                  value={formData.icon}
                  onChange={(e) => setFormData({ ...formData, icon: e.target.value })}
                  placeholder="help-circle"
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">{t('sortOrder')}</label>
                <Input
                  type="number"
                  value={formData.sortOrder}
                  onChange={(e) => setFormData({ ...formData, sortOrder: parseInt(e.target.value) || 0 })}
                />
              </div>
            </div>

            <div className="flex items-center space-x-2">
              <Checkbox
                id="isActive"
                checked={formData.isActive}
                onCheckedChange={(checked) => setFormData({ ...formData, isActive: checked === true })}
              />
              <label htmlFor="isActive" className="text-sm font-medium cursor-pointer">
                {t('categoryActive')}
              </label>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setIsFormOpen(false)}>
              {t('cancel')}
            </Button>
            <Button onClick={handleSubmit} disabled={submitting}>
              {submitting ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  {t('saving')}
                </>
              ) : editingCategory ? (
                t('updateCategory')
              ) : (
                t('createCategory')
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={isDeleteOpen} onOpenChange={setIsDeleteOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('deleteCategory')}</DialogTitle>
            <DialogDescription>
              {t('deleteCategoryConfirm', { name: deletingCategory?.nameEs })}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsDeleteOpen(false)}>
              {t('cancel')}
            </Button>
            <Button variant="destructive" onClick={handleDelete} disabled={submitting}>
              {submitting ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  {t('deleting')}
                </>
              ) : (
                t('delete')
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
