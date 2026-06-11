'use client'

import { useState } from 'react'
import { useTranslations } from 'next-intl'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
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
  DialogTrigger,
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
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import {
  Receipt,
  Plus,
  Search,
  Pencil,
  Trash2,
  Loader2,
  AlertCircle,
  CheckCircle,
  XCircle,
} from 'lucide-react'
import {
  useSupplements,
  useCreateSupplement,
  useUpdateSupplement,
  useDeleteSupplement,
} from '@/modules/service-requests-admin'
import type {
  TariffSupplement,
  TariffSupplementCreate,
  TariffSupplementUpdate,
} from '@/modules/service-requests-admin'

export default function SupplementsTabContent() {
  const t = useTranslations('admin.serviceRequests.tariffs.supplements')
  const tCommon = useTranslations('common')

  // State
  const [searchQuery, setSearchQuery] = useState('')
  const [showActiveOnly, setShowActiveOnly] = useState(false)
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false)
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false)
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false)
  const [selectedSupplement, setSelectedSupplement] = useState<TariffSupplement | null>(null)

  // Form state
  const [formData, setFormData] = useState<TariffSupplementCreate>({
    code: '',
    name_es: '',
    amount: 0,
    currency: 'XAF',
    legal_reference: '',
    effective_from: new Date().toISOString().split('T')[0],
    effective_to: null,
    is_active: true,
  })

  // Queries
  const {
    data: supplements,
    isLoading,
    error,
    refetch,
  } = useSupplements(showActiveOnly ? true : undefined)

  // Mutations
  const createMutation = useCreateSupplement()
  const updateMutation = useUpdateSupplement()
  const deleteMutation = useDeleteSupplement()

  // Filter supplements by search
  const filteredSupplements = supplements?.filter((s) => {
    if (!searchQuery) return true
    const query = searchQuery.toLowerCase()
    return (
      s.code.toLowerCase().includes(query) ||
      s.name_es.toLowerCase().includes(query)
    )
  }) || []

  // Handlers
  const handleCreateSupplement = async () => {
    try {
      await createMutation.mutateAsync(formData)
      setIsCreateDialogOpen(false)
      resetForm()
    } catch {
      // Error handled by mutation
    }
  }

  const handleUpdateSupplement = async () => {
    if (!selectedSupplement) return

    try {
      const updateData: TariffSupplementUpdate = {
        name_es: formData.name_es,
        amount: formData.amount,
        currency: formData.currency,
        legal_reference: formData.legal_reference || null,
        effective_from: formData.effective_from,
        effective_to: formData.effective_to,
        is_active: formData.is_active,
      }
      await updateMutation.mutateAsync({ code: selectedSupplement.code, data: updateData })
      setIsEditDialogOpen(false)
      resetForm()
    } catch {
      // Error handled by mutation
    }
  }

  const handleDeleteSupplement = async () => {
    if (!selectedSupplement) return

    try {
      await deleteMutation.mutateAsync(selectedSupplement.code)
      setIsDeleteDialogOpen(false)
      setSelectedSupplement(null)
    } catch {
      // Error handled by mutation
    }
  }

  const openEditDialog = (supplement: TariffSupplement) => {
    setSelectedSupplement(supplement)
    setFormData({
      code: supplement.code,
      name_es: supplement.name_es,
      amount: supplement.amount,
      currency: supplement.currency,
      legal_reference: supplement.legal_reference || '',
      effective_from: supplement.effective_from,
      effective_to: supplement.effective_to,
      is_active: supplement.is_active,
    })
    setIsEditDialogOpen(true)
  }

  const openDeleteDialog = (supplement: TariffSupplement) => {
    setSelectedSupplement(supplement)
    setIsDeleteDialogOpen(true)
  }

  const resetForm = () => {
    setFormData({
      code: '',
      name_es: '',
      amount: 0,
      currency: 'XAF',
      legal_reference: '',
      effective_from: new Date().toISOString().split('T')[0],
      effective_to: null,
      is_active: true,
    })
    setSelectedSupplement(null)
  }

  const formatCurrency = (amount: number, currency: string = 'XAF') => {
    return new Intl.NumberFormat('es-GQ', {
      style: 'currency',
      currency: currency,
      minimumFractionDigits: 0,
    }).format(amount)
  }

  // Render loading state
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  // Render error state
  if (error) {
    return (
      <Card className="border-destructive">
        <CardContent className="pt-6">
          <div className="flex items-center gap-2 text-destructive">
            <AlertCircle className="h-5 w-5" />
            <span>{error instanceof Error ? error.message : 'Error loading supplements'}</span>
          </div>
          <Button variant="outline" className="mt-4" onClick={() => refetch()}>
            {tCommon('retry')}
          </Button>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-4">
      {/* Actions Bar */}
      <div className="flex justify-end">
        <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
          <DialogTrigger asChild>
            <Button onClick={() => resetForm()}>
              <Plus className="mr-2 h-4 w-4" />
              {t('create')}
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle>{t('create')}</DialogTitle>
              <DialogDescription>{t('createDescription')}</DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 py-4">
              <div className="grid gap-2">
                <Label htmlFor="code">{t('code')}</Label>
                <Input
                  id="code"
                  value={formData.code}
                  onChange={(e) => setFormData({ ...formData, code: e.target.value.toUpperCase() })}
                  placeholder="CEDULA_PERSONAL"
                  pattern="^[A-Z][A-Z0-9_]*$"
                />
                <p className="text-xs text-muted-foreground">{t('codeHint')}</p>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="name">{t('name')}</Label>
                <Input
                  id="name"
                  value={formData.name_es}
                  onChange={(e) => setFormData({ ...formData, name_es: e.target.value })}
                  placeholder="Cédula Personal"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="grid gap-2">
                  <Label htmlFor="amount">{t('amount')} (XAF)</Label>
                  <Input
                    id="amount"
                    type="number"
                    value={formData.amount}
                    onChange={(e) => setFormData({ ...formData, amount: parseFloat(e.target.value) || 0 })}
                    min={0}
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="currency">{t('currency')}</Label>
                  <Input
                    id="currency"
                    value={formData.currency}
                    onChange={(e) => setFormData({ ...formData, currency: e.target.value.toUpperCase() })}
                    maxLength={3}
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="grid gap-2">
                  <Label htmlFor="effective_from">{t('effectiveFrom')}</Label>
                  <Input
                    id="effective_from"
                    type="date"
                    value={formData.effective_from || ''}
                    onChange={(e) => setFormData({ ...formData, effective_from: e.target.value })}
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="effective_to">{t('effectiveTo')}</Label>
                  <Input
                    id="effective_to"
                    type="date"
                    value={formData.effective_to || ''}
                    onChange={(e) => setFormData({ ...formData, effective_to: e.target.value || null })}
                  />
                </div>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="legal_reference">{t('legalReference')}</Label>
                <Input
                  id="legal_reference"
                  value={formData.legal_reference || ''}
                  onChange={(e) => setFormData({ ...formData, legal_reference: e.target.value })}
                  placeholder="Decreto XX/2024"
                />
              </div>
              <div className="flex items-center justify-between">
                <Label htmlFor="is_active">{t('isActive')}</Label>
                <Switch
                  id="is_active"
                  checked={formData.is_active}
                  onCheckedChange={(checked) => setFormData({ ...formData, is_active: checked })}
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setIsCreateDialogOpen(false)}>
                {tCommon('cancel')}
              </Button>
              <Button
                onClick={handleCreateSupplement}
                disabled={!formData.code || !formData.name_es || !formData.amount || createMutation.isPending}
              >
                {createMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {tCommon('create')}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {/* Supplements Card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Receipt className="h-5 w-5" />
            {t('title')}
          </CardTitle>
          <CardDescription>{t('total', { count: supplements?.length || 0 })}</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col sm:flex-row gap-4 mb-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder={t('searchPlaceholder')}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
              />
            </div>
            <div className="flex items-center gap-2">
              <Switch
                id="filter-active"
                checked={showActiveOnly}
                onCheckedChange={setShowActiveOnly}
              />
              <Label htmlFor="filter-active" className="text-sm">
                {t('showActiveOnly')}
              </Label>
            </div>
          </div>

          {/* Supplements Table */}
          <div className="border rounded-md">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('code')}</TableHead>
                  <TableHead>{t('name')}</TableHead>
                  <TableHead className="text-right">{t('amount')}</TableHead>
                  <TableHead>{t('legalReference')}</TableHead>
                  <TableHead className="text-center">{t('status')}</TableHead>
                  <TableHead className="text-right">{t('actions')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredSupplements.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center text-muted-foreground py-8">
                      {t('noSupplementsFound')}
                    </TableCell>
                  </TableRow>
                ) : (
                  filteredSupplements.map((supplement) => (
                    <TableRow key={supplement.id}>
                      <TableCell>
                        <code className="text-sm bg-muted px-2 py-1 rounded">{supplement.code}</code>
                      </TableCell>
                      <TableCell>
                        <div className="font-medium">{supplement.name_es}</div>
                        <div className="text-xs text-muted-foreground">
                          {supplement.effective_from}
                          {supplement.effective_to && ` → ${supplement.effective_to}`}
                        </div>
                      </TableCell>
                      <TableCell className="text-right font-mono">
                        {formatCurrency(supplement.amount, supplement.currency)}
                      </TableCell>
                      <TableCell>
                        {supplement.legal_reference ? (
                          <Badge variant="outline">{supplement.legal_reference}</Badge>
                        ) : (
                          <span className="text-muted-foreground">-</span>
                        )}
                      </TableCell>
                      <TableCell className="text-center">
                        {supplement.is_active ? (
                          <CheckCircle className="h-5 w-5 text-green-500 mx-auto" />
                        ) : (
                          <XCircle className="h-5 w-5 text-red-500 mx-auto" />
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button variant="ghost" size="icon" onClick={() => openEditDialog(supplement)}>
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => openDeleteDialog(supplement)}
                          className="text-destructive hover:text-destructive"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      {/* Edit Dialog */}
      <Dialog open={isEditDialogOpen} onOpenChange={setIsEditDialogOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>{t('edit')}</DialogTitle>
            <DialogDescription>{t('editDescription')}</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label>{t('code')}</Label>
              <Input value={formData.code} disabled className="bg-muted" />
              <p className="text-xs text-muted-foreground">{t('codeReadOnly')}</p>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="edit_name">{t('name')}</Label>
              <Input
                id="edit_name"
                value={formData.name_es}
                onChange={(e) => setFormData({ ...formData, name_es: e.target.value })}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label htmlFor="edit_amount">{t('amount')} (XAF)</Label>
                <Input
                  id="edit_amount"
                  type="number"
                  value={formData.amount}
                  onChange={(e) => setFormData({ ...formData, amount: parseFloat(e.target.value) || 0 })}
                  min={0}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="edit_currency">{t('currency')}</Label>
                <Input
                  id="edit_currency"
                  value={formData.currency}
                  onChange={(e) => setFormData({ ...formData, currency: e.target.value.toUpperCase() })}
                  maxLength={3}
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label htmlFor="edit_effective_from">{t('effectiveFrom')}</Label>
                <Input
                  id="edit_effective_from"
                  type="date"
                  value={formData.effective_from || ''}
                  onChange={(e) => setFormData({ ...formData, effective_from: e.target.value })}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="edit_effective_to">{t('effectiveTo')}</Label>
                <Input
                  id="edit_effective_to"
                  type="date"
                  value={formData.effective_to || ''}
                  onChange={(e) => setFormData({ ...formData, effective_to: e.target.value || null })}
                />
              </div>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="edit_legal">{t('legalReference')}</Label>
              <Input
                id="edit_legal"
                value={formData.legal_reference || ''}
                onChange={(e) => setFormData({ ...formData, legal_reference: e.target.value })}
              />
            </div>
            <div className="flex items-center justify-between">
              <Label htmlFor="edit_is_active">{t('isActive')}</Label>
              <Switch
                id="edit_is_active"
                checked={formData.is_active}
                onCheckedChange={(checked) => setFormData({ ...formData, is_active: checked })}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsEditDialogOpen(false)}>
              {tCommon('cancel')}
            </Button>
            <Button onClick={handleUpdateSupplement} disabled={updateMutation.isPending}>
              {updateMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {tCommon('save')}
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
              {t('deleteConfirmDescription', { code: selectedSupplement?.code })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{tCommon('cancel')}</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteSupplement}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleteMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {tCommon('delete')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
