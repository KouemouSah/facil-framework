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
import { useCreateSlotConfigBatch } from '@/modules/service-requests-admin'
import { DAY_OF_WEEK_LABELS } from '@/modules/service-requests-admin'
import type { AppointmentSlotConfigBatchCreate } from '@/modules/service-requests-admin'
import { toast } from 'sonner'
import { useEntityLocations } from '@/modules/entity-locations/hooks'
import { useCitiesSimple } from '@/modules/cities/hooks'

export default function NewSlotConfigPage() {
  const t = useTranslations('admin.serviceRequests.appointments.slots')
  const tCommon = useTranslations('common')
  const router = useRouter()
  const params = useParams()
  const searchParams = useSearchParams()
  const locale = params.locale as string

  // Get URL params for auto-fill
  const urlCity = searchParams.get('city')
  const urlEntity = searchParams.get('entity')

  // Multi-day selection state
  const [selectedDays, setSelectedDays] = useState<number[]>([0])

  // Fetch cities from database
  const { data: citiesData, isLoading: citiesLoading } = useCitiesSimple(true)
  const availableCities = useMemo(() => citiesData || [], [citiesData])

  // City filter state - default to first available city or URL param
  const [selectedCity, setSelectedCity] = useState<string>(urlCity || '')
  const [selectedLocationId, setSelectedLocationId] = useState<string>('')

  // Fetch entity locations filtered by city
  const { data: locationsData, isLoading: locationsLoading } = useEntityLocations({
    city: selectedCity,
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

  // Set default city when cities are loaded
  useEffect(() => {
    if (availableCities.length > 0 && !selectedCity) {
      // Prefer URL param, then first available city
      const defaultCity = urlCity || availableCities[0]?.name || ''
      setSelectedCity(defaultCity)
    }
  }, [availableCities, selectedCity, urlCity])

  // Form state (entity_code is resolved on backend from entity_location_id)
  const [formData, setFormData] = useState<Omit<AppointmentSlotConfigBatchCreate, 'days_of_week'>>({
    entity_location_id: '',
    start_time: '08:00',
    end_time: '16:00',
    slot_duration_minutes: 30,
    max_appointments_per_slot: 1,
    is_active: true,
  })

  // Auto-select location from URL params
  useEffect(() => {
    if (urlCity && urlEntity && availableLocations.length > 0) {
      const matchingLocation = availableLocations.find(
        (loc) => loc.city === urlCity && loc.entity_code === urlEntity
      )
      if (matchingLocation) {
        setSelectedLocationId(matchingLocation.id)
        setFormData((prev) => ({
          ...prev,
          entity_location_id: matchingLocation.id,
        }))
      }
    }
  }, [urlCity, urlEntity, availableLocations])

  // Update form data when location changes (entity_code resolved on backend)
  useEffect(() => {
    if (selectedLocation) {
      setFormData((prev) => ({
        ...prev,
        entity_location_id: selectedLocation.id,
      }))
    }
  }, [selectedLocation])

  // Batch mutation (creates all days in one request)
  const createMutation = useCreateSlotConfigBatch()

  // Toggle day selection
  const toggleDay = (day: number) => {
    setSelectedDays((prev) =>
      prev.includes(day) ? prev.filter((d) => d !== day) : [...prev, day]
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

  // Navigate back
  const handleBack = () => {
    router.push(`/${locale}/dashboard/admin/service-requests/appointments?tab=slots`)
  }

  // Handle form submission - creates all slots in one batch request
  const handleSubmit = async () => {
    if (!selectedLocationId || selectedDays.length === 0) {
      toast.error(t('validation.requiredFields'))
      return
    }

    try {
      // Create all slots in one batch request
      await createMutation.mutateAsync({
        ...formData,
        entity_location_id: selectedLocationId,
        days_of_week: selectedDays,
      })
      // Toast handled by useCreateSlotConfigBatch hook
      handleBack()
    } catch {
      // Error toast handled by useCreateSlotConfigBatch hook
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={handleBack}>
          <ArrowLeft className="h-5 w-5" />
        </Button>
        <div>
          <h1 className="text-3xl font-bold tracking-tight">{t('createTitle')}</h1>
          <p className="text-muted-foreground">{t('createSubtitle')}</p>
        </div>
      </div>

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

          {/* Day Selection */}
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

          {/* Actions */}
          <div className="flex justify-end gap-4 pt-4 border-t">
            <Button variant="outline" onClick={handleBack}>
              {tCommon('cancel')}
            </Button>
            <Button
              onClick={handleSubmit}
              disabled={!selectedLocationId || selectedDays.length === 0 || createMutation.isPending}
            >
              {createMutation.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  {t('creating')}
                </>
              ) : (
                <>
                  <Save className="mr-2 h-4 w-4" />
                  {selectedDays.length > 1
                    ? t('createMultiple', { count: selectedDays.length })
                    : tCommon('create')}
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
