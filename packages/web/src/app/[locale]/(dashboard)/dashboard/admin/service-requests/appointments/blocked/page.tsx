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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  CalendarX,
  Plus,
  Trash2,
  Loader2,
  AlertCircle,
  RefreshCw,
  Calendar,
} from 'lucide-react'
import {
  useBlockedDates,
  useAddBlockedDate,
  useRemoveBlockedDate,
  useSlotConfigs,
} from '@/modules/service-requests-admin'
import type {
  AppointmentBlockedDate,
  AppointmentBlockedDateCreate,
} from '@/modules/service-requests-admin'

export default function BlockedDatesPage() {
  const t = useTranslations('admin.serviceRequests.appointments.blocked')
  const tCommon = useTranslations('common')

  // State
  const [entityFilter, setEntityFilter] = useState<string>('all')
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false)
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false)
  const [selectedDate, setSelectedDate] = useState<AppointmentBlockedDate | null>(null)

  // Form state
  const [formData, setFormData] = useState<AppointmentBlockedDateCreate>({
    entity_code: null,
    blocked_date: new Date().toISOString().split('T')[0],
    reason: '',
    is_recurring: false,
  })

  // Queries
  const { data: slotConfigs } = useSlotConfigs()
  const {
    data: blockedDates,
    isLoading,
    error,
    refetch,
  } = useBlockedDates({
    entity_code: entityFilter === 'all' ? undefined : entityFilter === 'global' ? undefined : entityFilter,
  })

  // Mutations
  const addMutation = useAddBlockedDate()
  const removeMutation = useRemoveBlockedDate()

  // Get unique entity codes
  const entities = Array.from(new Set(slotConfigs?.map((s) => s.entity_code) || []))

  // Sort blocked dates by date
  const sortedDates = [...(blockedDates || [])].sort(
    (a, b) => new Date(a.blocked_date).getTime() - new Date(b.blocked_date).getTime()
  )

  // Handlers
  const handleAddBlockedDate = async () => {
    try {
      await addMutation.mutateAsync(formData)
      setIsCreateDialogOpen(false)
      resetForm()
    } catch {
      // Error handled by mutation
    }
  }

  const handleRemoveBlockedDate = async () => {
    if (!selectedDate) return

    try {
      await removeMutation.mutateAsync(selectedDate.id)
      setIsDeleteDialogOpen(false)
      setSelectedDate(null)
    } catch {
      // Error handled by mutation
    }
  }

  const openDeleteDialog = (date: AppointmentBlockedDate) => {
    setSelectedDate(date)
    setIsDeleteDialogOpen(true)
  }

  const resetForm = () => {
    setFormData({
      entity_code: null,
      blocked_date: new Date().toISOString().split('T')[0],
      reason: '',
      is_recurring: false,
    })
    setSelectedDate(null)
  }

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr)
    return date.toLocaleDateString('es-GQ', {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    })
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
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">{t('title')}</h1>
          <p className="text-muted-foreground">{t('subtitle')}</p>
        </div>
        <Card className="border-destructive">
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-destructive">
              <AlertCircle className="h-5 w-5" />
              <span>{error instanceof Error ? error.message : 'Error loading blocked dates'}</span>
            </div>
            <Button variant="outline" className="mt-4" onClick={() => refetch()}>
              {tCommon('retry')}
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">{t('title')}</h1>
          <p className="text-muted-foreground">{t('subtitle')}</p>
        </div>
        <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
          <DialogTrigger asChild>
            <Button onClick={() => resetForm()}>
              <Plus className="mr-2 h-4 w-4" />
              {t('add')}
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{t('add')}</DialogTitle>
              <DialogDescription>{t('addDescription')}</DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 py-4">
              <div className="grid gap-2">
                <Label htmlFor="entity">{t('entityCode')}</Label>
                <Select
                  value={formData.entity_code || 'global'}
                  onValueChange={(value) =>
                    setFormData({ ...formData, entity_code: value === 'global' ? null : value })
                  }
                >
                  <SelectTrigger>
                    <SelectValue placeholder={t('selectEntity')} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="global">{t('allEntities')}</SelectItem>
                    {entities.map((entity) => (
                      <SelectItem key={entity} value={entity}>
                        {entity}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">{t('entityHint')}</p>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="date">{t('date')}</Label>
                <Input
                  id="date"
                  type="date"
                  value={formData.blocked_date}
                  onChange={(e) => setFormData({ ...formData, blocked_date: e.target.value })}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="reason">{t('reason')}</Label>
                <Input
                  id="reason"
                  value={formData.reason || ''}
                  onChange={(e) => setFormData({ ...formData, reason: e.target.value })}
                  placeholder="Día festivo nacional"
                />
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <Label htmlFor="recurring">{t('isRecurring')}</Label>
                  <p className="text-xs text-muted-foreground">{t('recurringHint')}</p>
                </div>
                <Switch
                  id="recurring"
                  checked={formData.is_recurring}
                  onCheckedChange={(checked) => setFormData({ ...formData, is_recurring: checked })}
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setIsCreateDialogOpen(false)}>
                {tCommon('cancel')}
              </Button>
              <Button
                onClick={handleAddBlockedDate}
                disabled={!formData.blocked_date || addMutation.isPending}
              >
                {addMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {tCommon('add')}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <CalendarX className="h-5 w-5" />
            {t('title')}
          </CardTitle>
          <CardDescription>{t('total', { count: blockedDates?.length || 0 })}</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex gap-4 mb-4">
            <Select value={entityFilter} onValueChange={setEntityFilter}>
              <SelectTrigger className="w-[200px]">
                <SelectValue placeholder={t('filterByEntity')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('allDates')}</SelectItem>
                <SelectItem value="global">{t('globalOnly')}</SelectItem>
                {entities.map((entity) => (
                  <SelectItem key={entity} value={entity}>
                    {entity}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Blocked Dates Table */}
          <div className="border rounded-md">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('date')}</TableHead>
                  <TableHead>{t('entity')}</TableHead>
                  <TableHead>{t('reason')}</TableHead>
                  <TableHead className="text-center">{t('recurring')}</TableHead>
                  <TableHead className="text-right">{t('actions')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sortedDates.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center text-muted-foreground py-8">
                      {t('noDatesFound')}
                    </TableCell>
                  </TableRow>
                ) : (
                  sortedDates.map((date) => (
                    <TableRow key={date.id}>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <Calendar className="h-4 w-4 text-muted-foreground" />
                          <div>
                            <div className="font-medium">{formatDate(date.blocked_date)}</div>
                            <div className="text-xs text-muted-foreground font-mono">{date.blocked_date}</div>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>
                        {date.entity_code ? (
                          <Badge variant="outline">{date.entity_code}</Badge>
                        ) : (
                          <Badge variant="default">{t('global')}</Badge>
                        )}
                      </TableCell>
                      <TableCell>
                        {date.reason || <span className="text-muted-foreground">-</span>}
                      </TableCell>
                      <TableCell className="text-center">
                        {date.is_recurring && (
                          <Badge variant="secondary" className="gap-1">
                            <RefreshCw className="h-3 w-3" />
                            {t('yearly')}
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => openDeleteDialog(date)}
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

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={isDeleteDialogOpen} onOpenChange={setIsDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('deleteConfirmTitle')}</AlertDialogTitle>
            <AlertDialogDescription>
              {t('deleteConfirmDescription', {
                date: selectedDate ? formatDate(selectedDate.blocked_date) : '',
              })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{tCommon('cancel')}</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleRemoveBlockedDate}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {removeMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {tCommon('delete')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
