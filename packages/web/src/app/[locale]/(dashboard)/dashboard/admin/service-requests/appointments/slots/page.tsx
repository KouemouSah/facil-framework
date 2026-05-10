'use client'

import { useState } from 'react'
import { useTranslations } from 'next-intl'
import { useRouter, useParams } from 'next/navigation'
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
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  CalendarClock,
  Plus,
  Search,
  Pencil,
  Trash2,
  Loader2,
  AlertCircle,
  CheckCircle,
  XCircle,
  MapPin,
} from 'lucide-react'
import { useSlotConfigs, useDeleteSlotConfig } from '@/modules/service-requests-admin'
import type { AppointmentSlotConfig } from '@/modules/service-requests-admin'
import { DAY_OF_WEEK_LABELS } from '@/modules/service-requests-admin'

export default function SlotConfigsPage() {
  const t = useTranslations('admin.serviceRequests.appointments.slots')
  const tCommon = useTranslations('common')
  const router = useRouter()
  const params = useParams()
  const locale = params.locale as string

  // State
  const [searchQuery, setSearchQuery] = useState('')
  const [entityFilter, setEntityFilter] = useState<string>('all')
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false)
  const [selectedSlot, setSelectedSlot] = useState<AppointmentSlotConfig | null>(null)

  // Queries
  const {
    data: slotConfigs,
    isLoading,
    error,
    refetch,
  } = useSlotConfigs({
    entity_code: entityFilter === 'all' ? undefined : entityFilter,
  })

  // Mutations
  const deleteMutation = useDeleteSlotConfig()

  // Get unique entity codes for filter
  const entities = Array.from(new Set(slotConfigs?.map((s) => s.entity_code) || []))

  // Filter slots
  const filteredSlots =
    slotConfigs?.filter((s) => {
      if (!searchQuery) return true
      const query = searchQuery.toLowerCase()
      return (
        s.entity_code.toLowerCase().includes(query) ||
        s.location_name?.toLowerCase().includes(query) ||
        s.location_address?.toLowerCase().includes(query)
      )
    }) || []

  // Handlers
  const handleCreateNew = () => {
    router.push(`/${locale}/dashboard/admin/service-requests/appointments/slots/new`)
  }

  const handleEditSlot = (slot: AppointmentSlotConfig) => {
    router.push(`/${locale}/dashboard/admin/service-requests/appointments/slots/${slot.id}/edit`)
  }

  const handleDeleteSlot = async () => {
    if (!selectedSlot) return

    try {
      await deleteMutation.mutateAsync(selectedSlot.id)
      setIsDeleteDialogOpen(false)
      setSelectedSlot(null)
    } catch {
      // Error handled by mutation
    }
  }

  const openDeleteDialog = (slot: AppointmentSlotConfig) => {
    setSelectedSlot(slot)
    setIsDeleteDialogOpen(true)
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
              <span>{error instanceof Error ? error.message : 'Error loading slot configs'}</span>
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
        <Button onClick={handleCreateNew}>
          <Plus className="mr-2 h-4 w-4" />
          {t('create')}
        </Button>
      </div>

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <CalendarClock className="h-5 w-5" />
            {t('title')}
          </CardTitle>
          <CardDescription>{t('total', { count: slotConfigs?.length || 0 })}</CardDescription>
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
            <Select value={entityFilter} onValueChange={setEntityFilter}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder={t('filterByEntity')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('allEntities')}</SelectItem>
                {entities.map((entity) => (
                  <SelectItem key={entity} value={entity}>
                    {entity}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Slots Table */}
          <div className="border rounded-md">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('entity')}</TableHead>
                  <TableHead>{t('day')}</TableHead>
                  <TableHead>{t('hours')}</TableHead>
                  <TableHead className="text-center">{t('duration')}</TableHead>
                  <TableHead className="text-center">{t('capacity')}</TableHead>
                  <TableHead>{t('location')}</TableHead>
                  <TableHead className="text-center">{t('status')}</TableHead>
                  <TableHead className="text-right">{t('actions')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredSlots.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={8} className="text-center text-muted-foreground py-8">
                      {t('noSlotsFound')}
                    </TableCell>
                  </TableRow>
                ) : (
                  filteredSlots.map((slot) => (
                    <TableRow key={slot.id}>
                      <TableCell>
                        <Badge variant="outline">{slot.entity_code}</Badge>
                      </TableCell>
                      <TableCell>
                        <Badge variant="secondary">{DAY_OF_WEEK_LABELS[slot.day_of_week]}</Badge>
                      </TableCell>
                      <TableCell>
                        <span className="font-mono text-sm">
                          {slot.start_time} - {slot.end_time}
                        </span>
                      </TableCell>
                      <TableCell className="text-center">{slot.slot_duration_minutes} min</TableCell>
                      <TableCell className="text-center">{slot.max_appointments_per_slot}</TableCell>
                      <TableCell>
                        {slot.location_name ? (
                          <div className="flex flex-col">
                            <div className="flex items-center gap-1">
                              <MapPin className="h-3 w-3 text-muted-foreground" />
                              <span className="text-sm truncate max-w-[150px]">{slot.location_name}</span>
                            </div>
                            {slot.city && (
                              <span className="text-xs text-muted-foreground">
                                {slot.city} - {slot.region}
                              </span>
                            )}
                          </div>
                        ) : (
                          <span className="text-muted-foreground">-</span>
                        )}
                      </TableCell>
                      <TableCell className="text-center">
                        {slot.is_active ? (
                          <CheckCircle className="h-5 w-5 text-green-500 mx-auto" />
                        ) : (
                          <XCircle className="h-5 w-5 text-red-500 mx-auto" />
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-1">
                          <Button variant="ghost" size="icon" onClick={() => handleEditSlot(slot)}>
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => openDeleteDialog(slot)}
                            className="text-destructive hover:text-destructive"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
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
                entity: selectedSlot?.entity_code,
                day: DAY_OF_WEEK_LABELS[selectedSlot?.day_of_week || 0],
              })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{tCommon('cancel')}</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteSlot}
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
