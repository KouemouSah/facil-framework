'use client'

import { useState, useEffect, useMemo } from 'react'
import { useTranslations } from 'next-intl'
import { useRouter, useParams, useSearchParams } from 'next/navigation'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription } from '@/components/ui/alert'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  ArrowLeft,
  CalendarClock,
  Loader2,
  Save,
  Building,
  Clock,
  Users,
  MapPin,
  AlertCircle,
} from 'lucide-react'
import { TimePicker } from '@/components/ui/time-picker'
import { useSlotConfigs, useBatchUpdateSlotConfig, DAY_OF_WEEK_LABELS } from '@/modules/service-requests-admin'
import { toast } from 'sonner'
import { useEntityLocations } from '@/modules/entity-locations/hooks'
import { useCitiesSimple } from '@/modules/cities/hooks'

export default function EditSlotConfigPage() {
  const t = useTranslations('admin.serviceRequests.appointments.slots')
  const tCommon = useTranslations('common')
  const router = useRouter()
  const params = useParams()
  const searchParams = useSearchParams()
  const locale = params.locale as string
  const slotId = params.id as string

  // Get all group slot IDs from query params (fallback to single ID)
  const groupSlotIds = useMemo(() => {
    const idsParam = searchParams.get('ids')
    if (idsParam) {
      return idsParam.split(',').filter(Boolean)
    }
    return [slotId]
  }, [searchParams, slotId])

  // Load all slot configs to find the ones we're editing
  const { data: slotConfigs, isLoading: isLoadingSlot, error: loadError } = useSlotConfigs()

  // Find all slots in the group
  const groupSlots = useMemo(() => {
    if (!slotConfigs) return []
    return slotConfigs.filter((s) => groupSlotIds.includes(s.id))
  }, [slotConfigs, groupSlotIds])

  // Use the first slot as reference for initial form values
  const referenceSlot = groupSlots[0] ?? null

  // Fetch cities from database
  const { data: citiesData, isLoading: citiesLoading } = useCitiesSimple(true)
  const availableCities = useMemo(() => citiesData || [], [citiesData])

  // City filter state - initialized from existing slot
  const [selectedCity, setSelectedCity] = useState<string>('')
  const [selectedLocationId, setSelectedLocationId] = useState<string>('')

  // Multi-day selection state (batch mode)
  const [selectedDays, setSelectedDays] = useState<number[]>([])

  // Form state
  const [formData, setFormData] = useState({
    start_time: '08:00',
    end_time: '16:00',
    slot_duration_minutes: 30,
    max_appointments_per_slot: 1,
    is_active: true,
  })

  // Initialize form data when group slots load
  useEffect(() => {
    if (referenceSlot && groupSlots.length > 0) {
      // Set city from reference slot
      const city = referenceSlot.city || 'Malabo'
      setSelectedCity(city)
      setSelectedLocationId(referenceSlot.entity_location_id || '')

      // Pre-select all days in the group
      const days = groupSlots.map((s) => s.day_of_week).sort((a, b) => a - b)
      setSelectedDays(days)

      // Parse time (remove seconds if present)
      const formatTime = (time: string) => {
        if (!time) return '08:00'
        const parts = time.split(':')
        return `${parts[0]}:${parts[1]}`
      }

      setFormData({
        start_time: formatTime(referenceSlot.start_time),
        end_time: formatTime(referenceSlot.end_time),
        slot_duration_minutes: referenceSlot.slot_duration_minutes,
        max_appointments_per_slot: referenceSlot.max_appointments_per_slot,
        is_active: referenceSlot.is_active,
      })
    }
  }, [referenceSlot, groupSlots.length]) // eslint-disable-line react-hooks/exhaustive-deps

  // Fetch entity locations filtered by city
  const { data: locationsData, isLoading: locationsLoading } = useEntityLocations({
    city: selectedCity || undefined,
    is_active: true,
    page_size: 100,
  })

  // Filter locations by city
  const availableLocations = useMemo(() => {
    return locationsData?.items || []
  }, [locationsData])

  // Get selected location object
  const selectedLocation = useMemo(() => {
    return availableLocations.find((loc) => loc.id === selectedLocationId)
  }, [availableLocations, selectedLocationId])

  // Get selected city object (for region display)
  const selectedCityObj = useMemo(() => {
    return availableCities.find((c) => c.name === selectedCity)
  }, [availableCities, selectedCity])

  // Mutation — batch update (reconcile pattern)
  const batchUpdateMutation = useBatchUpdateSlotConfig()

  // Toggle day selection
  const toggleDay = (day: number) => {
    setSelectedDays((prev) =>
      prev.includes(day) ? prev.filter((d) => d !== day) : [...prev, day].sort((a, b) => a - b)
    )
  }

  // Select all weekdays
  const selectAllWeekdays = () => {
    setSelectedDays([0, 1, 2, 3, 4]) // Monday to Friday
  }

  // Clear selection
  const clearSelection = () => {
    setSelectedDays([])
  }

  // Compute change summary
  const changeSummary = useMemo(() => {
    const existingDays = new Set(groupSlots.map((s) => s.day_of_week))
    const desiredDays = new Set(selectedDays)
    const toUpdate = Array.from(existingDays).filter((d) => desiredDays.has(d)).length
    const toCreate = Array.from(desiredDays).filter((d) => !existingDays.has(d)).length
    const toDelete = Array.from(existingDays).filter((d) => !desiredDays.has(d)).length
    return { toUpdate, toCreate, toDelete }
  }, [groupSlots, selectedDays])

  // Navigate back
  const handleBack = () => {
    router.push(`/${locale}/dashboard/admin/service-requests/appointments?tab=slots`)
  }

  // Handle form submission — batch update
  const handleSubmit = async () => {
    if (!selectedLocationId || selectedDays.length === 0) {
      toast.error(t('validation.requiredFields'))
      return
    }

    try {
      await batchUpdateMutation.mutateAsync({
        slot_ids: groupSlotIds,
        entity_location_id: selectedLocationId,
        days_of_week: selectedDays,
        start_time: formData.start_time,
        end_time: formData.end_time,
        slot_duration_minutes: formData.slot_duration_minutes,
        max_appointments_per_slot: formData.max_appointments_per_slot,
        is_active: formData.is_active,
      })
      handleBack()
    } catch {
      // Error toast handled by hook
    }
  }

  // Loading state
  if (isLoadingSlot) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  // Error state - slot not found
  if (groupSlots.length === 0 && !isLoadingSlot) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={handleBack}>
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div>
            <h1 className="text-3xl font-bold tracking-tight">{t('editTitle')}</h1>
          </div>
        </div>
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            {loadError?.message || t('slotNotFound')}
          </AlertDescription>
        </Alert>
        <Button onClick={handleBack}>{tCommon('back')}</Button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={handleBack}>
          <ArrowLeft className="h-5 w-5" />
        </Button>
        <div>
          <h1 className="text-3xl font-bold tracking-tight">{t('editTitle')}</h1>
          <p className="text-muted-foreground">{t('editSubtitle')}</p>
        </div>
      </div>

      {/* Current Group Info */}
      {referenceSlot && (
        <Card className="border-blue-200 bg-blue-50/30">
          <CardContent className="pt-4">
            <div className="flex items-center gap-4 text-sm">
              <Badge variant="outline">{referenceSlot.entity_code}</Badge>
              <Badge variant="secondary">
                {groupSlots.length} {groupSlots.length === 1 ? 'día' : 'días'}
              </Badge>
              <span className="font-mono">
                {referenceSlot.start_time} - {referenceSlot.end_time}
              </span>
              {referenceSlot.location_name && (
                <span className="text-muted-foreground flex items-center gap-1">
                  <MapPin className="h-3 w-3" />
                  {referenceSlot.location_name}
                </span>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Form Card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <CalendarClock className="h-5 w-5" />
            {t('slotConfiguration')}
          </CardTitle>
          <CardDescription>{t('slotConfigDescription')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* City and Location Selection */}
          <div className="grid gap-4 sm:grid-cols-2">
            {/* City Selector */}
            <div className="grid gap-2">
              <Label htmlFor="city" className="flex items-center gap-2">
                <MapPin className="h-4 w-4" />
                {t('city')}
              </Label>
              <Select
                value={selectedCity}
                onValueChange={(v) => {
                  setSelectedCity(v)
                  setSelectedLocationId('')
                }}
                disabled={citiesLoading || availableCities.length === 0}
              >
                <SelectTrigger>
                  <SelectValue
                    placeholder={
                      citiesLoading
                        ? t('loadingCities')
                        : availableCities.length === 0
                          ? t('noCitiesAvailable')
                          : t('selectCity')
                    }
                  />
                </SelectTrigger>
                <SelectContent>
                  {availableCities.map((city) => (
                    <SelectItem key={city.id} value={city.name}>
                      <div className="flex items-center gap-2">
                        <span>{city.name}</span>
                        <Badge variant="outline" className="text-xs">
                          {city.region}
                        </Badge>
                        {city.is_capital && (
                          <Badge variant="secondary" className="text-xs">
                            Capital
                          </Badge>
                        )}
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-sm text-muted-foreground">
                {t('region')}: <span className="font-medium">{selectedCityObj?.region || '-'}</span>
              </p>
            </div>

            {/* Location Selector */}
            <div className="grid gap-2">
              <Label htmlFor="location" className="flex items-center gap-2">
                <Building className="h-4 w-4" />
                {t('location')}
              </Label>
              <Select
                value={selectedLocationId}
                onValueChange={setSelectedLocationId}
                disabled={locationsLoading || availableLocations.length === 0}
              >
                <SelectTrigger>
                  <SelectValue
                    placeholder={
                      locationsLoading
                        ? t('loadingLocations')
                        : availableLocations.length === 0
                          ? t('noLocationsForCity')
                          : t('selectLocation')
                    }
                  />
                </SelectTrigger>
                <SelectContent>
                  {availableLocations.map((loc) => (
                    <SelectItem key={loc.id} value={loc.id}>
                      <span className="font-medium">
                        {loc.entity_code} - {loc.location_name}
                      </span>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {selectedLocation && (
                <p className="text-sm text-muted-foreground">
                  {selectedLocation.location_address || t('noAddressProvided')}
                </p>
              )}
            </div>
          </div>

          {/* Day Selection (multi-day like create page) */}
          <div className="grid gap-2">
            <div className="flex items-center justify-between">
              <Label>{t('daysOfWeek')}</Label>
              <div className="flex gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={selectAllWeekdays}
                >
                  {t('selectWeekdays')}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={clearSelection}
                >
                  {t('clearSelection')}
                </Button>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              {Object.entries(DAY_OF_WEEK_LABELS).map(([day, label]) => {
                const dayNum = parseInt(day)
                const isSelected = selectedDays.includes(dayNum)
                return (
                  <Button
                    key={day}
                    type="button"
                    variant={isSelected ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => toggleDay(dayNum)}
                    className="min-w-[80px]"
                  >
                    {label}
                  </Button>
                )
              })}
            </div>
            {selectedDays.length === 0 && (
              <p className="text-sm text-destructive">{t('validation.selectDay')}</p>
            )}
            {selectedDays.length > 0 && (
              <p className="text-sm text-muted-foreground">
                {t('selectedDays', { count: selectedDays.length })}
              </p>
            )}
          </div>

          {/* Time Range */}
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="grid gap-2">
              <Label className="flex items-center gap-2">
                <Clock className="h-4 w-4" />
                {t('startTime')}
              </Label>
              <TimePicker
                value={formData.start_time}
                onChange={(v) => setFormData({ ...formData, start_time: v })}
                minuteStep={15}
              />
            </div>
            <div className="grid gap-2">
              <Label className="flex items-center gap-2">
                <Clock className="h-4 w-4" />
                {t('endTime')}
              </Label>
              <TimePicker
                value={formData.end_time}
                onChange={(v) => setFormData({ ...formData, end_time: v })}
                minuteStep={15}
              />
            </div>
          </div>
          {formData.start_time >= formData.end_time && (
            <div className="flex items-center gap-2 text-sm text-destructive">
              <AlertCircle className="h-4 w-4" />
              {t('validation.startBeforeEnd')}
            </div>
          )}

          {/* Duration and Capacity */}
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="grid gap-2">
              <Label htmlFor="duration" className="flex items-center gap-2">
                <Clock className="h-4 w-4" />
                {t('slotDuration')}
              </Label>
              <Select
                value={String(formData.slot_duration_minutes)}
                onValueChange={(v) =>
                  setFormData({ ...formData, slot_duration_minutes: parseInt(v) })
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="5">5 {t('minutes')}</SelectItem>
                  <SelectItem value="10">10 {t('minutes')}</SelectItem>
                  <SelectItem value="15">15 {t('minutes')}</SelectItem>
                  <SelectItem value="20">20 {t('minutes')}</SelectItem>
                  <SelectItem value="30">30 {t('minutes')}</SelectItem>
                  <SelectItem value="45">45 {t('minutes')}</SelectItem>
                  <SelectItem value="60">60 {t('minutes')}</SelectItem>
                  <SelectItem value="90">90 {t('minutes')}</SelectItem>
                  <SelectItem value="120">120 {t('minutes')}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="max_appointments" className="flex items-center gap-2">
                <Users className="h-4 w-4" />
                {t('maxAppointments')}
              </Label>
              <Input
                id="max_appointments"
                type="number"
                min={1}
                max={100}
                value={formData.max_appointments_per_slot}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    max_appointments_per_slot: Math.min(100, Math.max(1, parseInt(e.target.value) || 1)),
                  })
                }
              />
            </div>
          </div>

          {/* Is Active */}
          <div className="flex items-center justify-between rounded-lg border p-4">
            <div className="space-y-0.5">
              <Label htmlFor="is_active">{t('isActive')}</Label>
              <p className="text-sm text-muted-foreground">{t('isActiveDescription')}</p>
            </div>
            <Switch
              id="is_active"
              checked={formData.is_active}
              onCheckedChange={(checked) => setFormData({ ...formData, is_active: checked })}
            />
          </div>

          {/* Change Summary */}
          {(changeSummary.toCreate > 0 || changeSummary.toDelete > 0) && (
            <Alert>
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>
                <div className="flex flex-wrap gap-3">
                  {changeSummary.toUpdate > 0 && (
                    <Badge variant="secondary">{changeSummary.toUpdate} actualizado(s)</Badge>
                  )}
                  {changeSummary.toCreate > 0 && (
                    <Badge variant="default">{changeSummary.toCreate} nuevo(s)</Badge>
                  )}
                  {changeSummary.toDelete > 0 && (
                    <Badge variant="destructive">{changeSummary.toDelete} eliminado(s)</Badge>
                  )}
                </div>
              </AlertDescription>
            </Alert>
          )}

          {/* Actions */}
          <div className="flex justify-end gap-4 pt-4 border-t">
            <Button variant="outline" onClick={handleBack}>
              {tCommon('cancel')}
            </Button>
            <Button
              onClick={handleSubmit}
              disabled={!selectedLocationId || selectedDays.length === 0 || batchUpdateMutation.isPending}
            >
              {batchUpdateMutation.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  {t('saving')}
                </>
              ) : (
                <>
                  <Save className="mr-2 h-4 w-4" />
                  {tCommon('save')}
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
