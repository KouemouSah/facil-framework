'use client'

/**
 * AppointmentSelection Component
 * Citizen-first appointment flow where users select location and slot AFTER payment
 *
 * Flow:
 * 1. Select location (Malabo or Bata)
 * 2. Calendar view: navigate months, click available day → see time slots
 * 3. Hold a slot (15 min countdown)
 * 4. Proceed to confirmation
 *
 * Fallback: Submit without appointment if no slots available
 */

import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import {
  MapPin,
  Calendar,
  Clock,
  CheckCircle,
  AlertCircle,
  Loader2,
  ChevronRight,
  ChevronLeft,
  ArrowLeft,
  Timer,
  Building2,
  RefreshCw,
} from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Label } from '@/components/ui/label'
import { Progress } from '@/components/ui/progress'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

import {
  startOfMonth,
  endOfMonth,
  eachDayOfInterval,
  format,
  addMonths,
  subMonths,
  isSameMonth,
  isToday,
  isBefore,
  startOfWeek,
  endOfWeek,
} from 'date-fns'
import { es as esLocale, fr as frLocale, enUS as enLocale } from 'date-fns/locale'

import type {
  EntityLocation,
  AvailableSlot,
  HoldSlotResponse,
  AppointmentHoldStatus,
} from '../types'

// ============================================================================
// TYPES
// ============================================================================

interface AvailableDayInfo {
  timeSlotCount: number
  totalSlotsRemaining: number
}

interface AppointmentSelectionProps {
  // Request-based mode (legacy, after payment - used by admin)
  requestId?: string
  // Session-based mode (before payment, cache-first wizard)
  sessionId?: string
  // Mode inferred: sessionId → session mode, requestId → request mode

  onComplete: (data: {
    hasAppointment: boolean
    locationName?: string
    appointmentDate?: string
    appointmentTime?: string
    city?: string
    entityLocationId?: string
    isFallback: boolean
  }) => void
  onBack: () => void
  locale?: 'es' | 'fr' | 'en'

  // --- Request-based API methods (when requestId is set) ---
  getLocations?: (requestId: string) => Promise<{
    entityCode: string
    locations: EntityLocation[]
    count: number
  }>
  getAvailableDays?: (requestId: string, entityLocationId: string, fromDate?: string, toDate?: string) => Promise<{
    days: Array<{ date: string; timeSlotCount: number; totalSlotsRemaining: number }>
    minDate?: string
  }>
  getSlots?: (requestId: string, entityLocationId: string, fromDate?: string, limit?: number) => Promise<{
    entityCode: string
    locationName: string
    fromDate: string
    slots: AvailableSlot[]
    count: number
    hasAvailability: boolean
  }>
  holdSlot?: (requestId: string, data: {
    entityLocationId: string
    slotConfigId?: string
    appointmentDate: string
    appointmentTime: string
  }) => Promise<HoldSlotResponse>
  getHoldStatus?: (requestId: string) => Promise<AppointmentHoldStatus>
  releaseHold?: (requestId: string) => Promise<{ success: boolean; message: string }>
  submitWithoutAppointment?: (requestId: string, entityLocationId: string) => Promise<{
    success: boolean
    locationName?: string
    message: string
    error?: string
  }>

  // --- Session-based API methods (when sessionId is set) ---
  getSessionLocations?: (sessionId: string) => Promise<{
    entityCode: string
    locations: Array<{
      id: string
      entityCode: string
      locationCode: string
      locationName: string
      city: string
      province: string | null
      region: string | null
      address: string | null
      isMainOffice: boolean
    }>
    count: number
  }>
  getSessionAvailableDays?: (sessionId: string, entityLocationId: string, fromDate?: string, toDate?: string) => Promise<{
    days: Array<{ date: string; timeSlotCount: number; totalSlotsRemaining: number }>
    minDate?: string
  }>
  getSessionSlots?: (sessionId: string, entityLocationId: string, fromDate?: string, limit?: number) => Promise<{
    entityCode: string
    locationName: string
    fromDate: string
    slots: Array<{
      slotDate: string
      slotTime: string
      locationName: string
      locationAddress: string | null
      slotsRemaining: number
      city: string | null
    }>
    count: number
    hasAvailability: boolean
  }>
  saveSelection?: (sessionId: string, data: {
    entityLocationId: string
    locationName: string
    city: string
    appointmentDate: string
    appointmentTime: string
    slotConfigId?: string | null
  }) => Promise<{ success: boolean }>
}

type Step = 'location' | 'slots' | 'held' | 'fallback'

// ============================================================================
// TRANSLATIONS
// ============================================================================

const TEXTS = {
  es: {
    title: 'Seleccionar Cita',
    subtitle: 'Selecciona ubicacion y horario para tu cita',
    step1Title: 'Selecciona Ubicacion',
    step1Desc: 'Elige la oficina donde deseas realizar el tramite',
    step2Title: 'Selecciona Fecha y Horario',
    step2Desc: 'Los dias destacados tienen citas disponibles',
    step3Title: 'Cita Reservada',
    step3Desc: 'Tu cita esta reservada temporalmente',
    mainOffice: 'Oficina Principal',
    regionalOffice: 'Oficina Regional',
    noSlotsTitle: 'No hay citas disponibles',
    noSlotsDesc: 'No hay horarios disponibles en esta ubicacion. Puedes enviar tu solicitud y un agente te asignara una cita.',
    holdSuccess: 'Cita reservada exitosamente',
    holdExpiry: 'Tienes {minutes} minutos para completar el pago',
    slotsRemaining: '{count} espacio(s) disponible(s)',
    selectSlot: 'Seleccionar',
    continueToPayment: 'Continuar al Pago',
    submitWithoutAppt: 'Enviar sin Cita',
    changeLocation: 'Cambiar Ubicacion',
    changeSlot: 'Cambiar Horario',
    back: 'Volver',
    loading: 'Cargando...',
    error: 'Error',
    retry: 'Reintentar',
    holdExpired: 'La reserva ha expirado',
    holdExpiredDesc: 'Tu reserva temporal ha expirado. Por favor selecciona un nuevo horario.',
    selectNewSlot: 'Seleccionar Nuevo Horario',
    today: 'Hoy',
    timeSlotsTitle: 'Horarios disponibles',
    noSlotsForDay: 'No hay horarios para este dia',
    slotsAvailable: '{count} horario(s)',
  },
  fr: {
    title: 'Selectionner un Rendez-vous',
    subtitle: 'Selectionnez le lieu et l\'horaire de votre rendez-vous',
    step1Title: 'Selectionnez le Lieu',
    step1Desc: 'Choisissez le bureau ou vous souhaitez effectuer la demarche',
    step2Title: 'Selectionnez Date et Horaire',
    step2Desc: 'Les jours surlignes ont des rendez-vous disponibles',
    step3Title: 'Rendez-vous Reserve',
    step3Desc: 'Votre rendez-vous est temporairement reserve',
    mainOffice: 'Bureau Principal',
    regionalOffice: 'Bureau Regional',
    noSlotsTitle: 'Pas de rendez-vous disponibles',
    noSlotsDesc: 'Aucun horaire disponible a cet emplacement. Vous pouvez soumettre votre demande et un agent vous attribuera un rendez-vous.',
    holdSuccess: 'Rendez-vous reserve avec succes',
    holdExpiry: 'Vous avez {minutes} minutes pour completer le paiement',
    slotsRemaining: '{count} place(s) disponible(s)',
    selectSlot: 'Selectionner',
    continueToPayment: 'Continuer vers le Paiement',
    submitWithoutAppt: 'Soumettre sans Rendez-vous',
    changeLocation: 'Changer de Lieu',
    changeSlot: 'Changer d\'Horaire',
    back: 'Retour',
    loading: 'Chargement...',
    error: 'Erreur',
    retry: 'Reessayer',
    holdExpired: 'La reservation a expire',
    holdExpiredDesc: 'Votre reservation temporaire a expire. Veuillez selectionner un nouvel horaire.',
    selectNewSlot: 'Selectionner un Nouvel Horaire',
    today: 'Aujourd\'hui',
    timeSlotsTitle: 'Horaires disponibles',
    noSlotsForDay: 'Pas d\'horaires pour ce jour',
    slotsAvailable: '{count} horaire(s)',
  },
  en: {
    title: 'Select Appointment',
    subtitle: 'Select location and time for your appointment',
    step1Title: 'Select Location',
    step1Desc: 'Choose the office where you want to complete the process',
    step2Title: 'Select Date and Time',
    step2Desc: 'Highlighted days have available appointments',
    step3Title: 'Appointment Reserved',
    step3Desc: 'Your appointment is temporarily reserved',
    mainOffice: 'Main Office',
    regionalOffice: 'Regional Office',
    noSlotsTitle: 'No appointments available',
    noSlotsDesc: 'No time slots available at this location. You can submit your request and an agent will assign you an appointment.',
    holdSuccess: 'Appointment reserved successfully',
    holdExpiry: 'You have {minutes} minutes to complete payment',
    slotsRemaining: '{count} slot(s) available',
    selectSlot: 'Select',
    continueToPayment: 'Continue to Payment',
    submitWithoutAppt: 'Submit without Appointment',
    changeLocation: 'Change Location',
    changeSlot: 'Change Time Slot',
    back: 'Back',
    loading: 'Loading...',
    error: 'Error',
    retry: 'Retry',
    holdExpired: 'Reservation has expired',
    holdExpiredDesc: 'Your temporary reservation has expired. Please select a new time slot.',
    selectNewSlot: 'Select New Time Slot',
    today: 'Today',
    timeSlotsTitle: 'Available times',
    noSlotsForDay: 'No times for this day',
    slotsAvailable: '{count} time slot(s)',
  },
}

// ============================================================================
// HELPERS
// ============================================================================

const DATE_LOCALES = { es: esLocale, fr: frLocale, en: enLocale }

function formatDate(dateStr: string, locale: string): string {
  const date = new Date(dateStr)
  const options: Intl.DateTimeFormatOptions = {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  }
  return date.toLocaleDateString(locale === 'es' ? 'es-ES' : locale === 'fr' ? 'fr-FR' : 'en-US', options)
}

function formatTime(timeStr: string): string {
  // Convert HH:MM:SS to HH:MM
  const parts = timeStr.split(':')
  return `${parts[0]}:${parts[1]}`
}

function formatTimeRemaining(seconds: number): string {
  const minutes = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
}

// ============================================================================
// MAIN COMPONENT
// ============================================================================

export function AppointmentSelection({
  requestId,
  sessionId,
  onComplete,
  onBack,
  locale = 'es',
  getLocations,
  getAvailableDays,
  getSlots,
  holdSlot,
  getHoldStatus,
  releaseHold,
  submitWithoutAppointment,
  getSessionLocations,
  getSessionAvailableDays,
  getSessionSlots,
  saveSelection,
}: AppointmentSelectionProps) {
  // Mode: session mode (before payment) vs request mode (after payment, legacy)
  const isSessionMode = Boolean(sessionId)
  const t = TEXTS[locale]
  const dateLocale = DATE_LOCALES[locale]

  // Refs for API callbacks — avoids infinite useEffect loops from inline lambda props
  const getSessionLocationsRef = useRef(getSessionLocations)
  const getSessionAvailableDaysRef = useRef(getSessionAvailableDays)
  const getSessionSlotsRef = useRef(getSessionSlots)
  const saveSelectionRef = useRef(saveSelection)
  const getLocationsRef = useRef(getLocations)
  const getAvailableDaysRef = useRef(getAvailableDays)
  const getSlotsRef = useRef(getSlots)
  const holdSlotRef = useRef(holdSlot)
  const getHoldStatusRef = useRef(getHoldStatus)
  const releaseHoldRef = useRef(releaseHold)
  const submitWithoutAppointmentRef = useRef(submitWithoutAppointment)
  const onCompleteRef = useRef(onComplete)

  // Keep refs up-to-date
  useEffect(() => {
    getSessionLocationsRef.current = getSessionLocations
    getSessionAvailableDaysRef.current = getSessionAvailableDays
    getSessionSlotsRef.current = getSessionSlots
    saveSelectionRef.current = saveSelection
    getLocationsRef.current = getLocations
    getAvailableDaysRef.current = getAvailableDays
    getSlotsRef.current = getSlots
    holdSlotRef.current = holdSlot
    getHoldStatusRef.current = getHoldStatus
    releaseHoldRef.current = releaseHold
    submitWithoutAppointmentRef.current = submitWithoutAppointment
    onCompleteRef.current = onComplete
  })

  // State
  const [currentStep, setCurrentStep] = useState<Step>('location')
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Location state
  const [locations, setLocations] = useState<EntityLocation[]>([])
  const [selectedLocation, setSelectedLocation] = useState<EntityLocation | null>(null)

  // Calendar state
  const [viewMonth, setViewMonth] = useState(new Date())
  const [availableDays, setAvailableDays] = useState<Map<string, AvailableDayInfo>>(new Map())
  const [selectedDate, setSelectedDate] = useState<string | null>(null)
  const [isLoadingDays, setIsLoadingDays] = useState(false)
  const [minBookableDate, setMinBookableDate] = useState<string | null>(null)

  // Slots state (for selected day)
  const [slots, setSlots] = useState<AvailableSlot[]>([])
  const [isLoadingSlots, setIsLoadingSlots] = useState(false)

  // Hold state
  const [holdStatus, setHoldStatus] = useState<AppointmentHoldStatus | null>(null)
  const [holdCountdown, setHoldCountdown] = useState(0)
  const [isHolding, setIsHolding] = useState(false)

  // Calendar days for current month view
  const calendarDays = useMemo(() => {
    const start = startOfWeek(startOfMonth(viewMonth), { locale: dateLocale })
    const end = endOfWeek(endOfMonth(viewMonth), { locale: dateLocale })
    return eachDayOfInterval({ start, end })
  }, [viewMonth, dateLocale])

  // Weekday headers from locale
  const weekdayHeaders = useMemo(() => {
    const start = startOfWeek(new Date(), { locale: dateLocale })
    return Array.from({ length: 7 }, (_, i) => {
      const day = new Date(start)
      day.setDate(day.getDate() + i)
      return format(day, 'EEE', { locale: dateLocale })
    })
  }, [dateLocale])

  // ============================================================================
  // LOAD INITIAL DATA
  // ============================================================================

  useEffect(() => {
    async function loadInitialData() {
      setIsLoading(true)
      setError(null)

      try {
        if (isSessionMode && sessionId && getSessionLocationsRef.current) {
          // Session mode: no hold check, just load locations
          const locationsResponse = await getSessionLocationsRef.current(sessionId)
          // Convert to EntityLocation format
          const locs: EntityLocation[] = locationsResponse.locations.map((l) => ({
            id: l.id,
            entityCode: l.entityCode,
            locationCode: l.locationCode,
            locationName: l.locationName,
            city: l.city,
            province: l.province ?? undefined,
            region: l.region ?? undefined,
            address: l.address ?? undefined,
            isMainOffice: l.isMainOffice,
          }))
          setLocations(locs)
          setCurrentStep('location')
        } else if (requestId && getHoldStatusRef.current && getLocationsRef.current) {
          // Request mode: check for existing hold first
          const existingHold = await getHoldStatusRef.current(requestId)

          if (existingHold.hasHold && !existingHold.isExpired) {
            setHoldStatus(existingHold)
            if (existingHold.expiresAt) {
              const expiresAt = new Date(existingHold.expiresAt)
              const now = new Date()
              const remaining = Math.max(0, Math.floor((expiresAt.getTime() - now.getTime()) / 1000))
              setHoldCountdown(remaining)
            }
            setCurrentStep('held')
          } else {
            const locationsResponse = await getLocationsRef.current(requestId)
            setLocations(locationsResponse.locations)
            setCurrentStep('location')
          }
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load data')
      } finally {
        setIsLoading(false)
      }
    }

    loadInitialData()
    // Only re-run when identity changes, not when callback refs change
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [requestId, sessionId, isSessionMode])

  // ============================================================================
  // COUNTDOWN TIMER
  // ============================================================================

  useEffect(() => {
    if (currentStep !== 'held' || holdCountdown <= 0) return

    const timer = setInterval(() => {
      setHoldCountdown((prev) => {
        if (prev <= 1) {
          clearInterval(timer)
          setCurrentStep('location')
          return 0
        }
        return prev - 1
      })
    }, 1000)

    return () => clearInterval(timer)
  }, [currentStep, holdCountdown])

  // ============================================================================
  // HANDLERS
  // ============================================================================

  const loadAvailableDays = useCallback(async (
    locationId: string,
    fromDate?: string,
    toDate?: string
  ) => {
    let response: { days: Array<{ date: string; timeSlotCount: number; totalSlotsRemaining: number }>; minDate?: string }

    if (isSessionMode && sessionId && getSessionAvailableDaysRef.current) {
      response = await getSessionAvailableDaysRef.current(sessionId, locationId, fromDate, toDate)
    } else if (requestId && getAvailableDaysRef.current) {
      response = await getAvailableDaysRef.current(requestId, locationId, fromDate, toDate)
    } else {
      return { daysMap: new Map<string, AvailableDayInfo>(), minDate: undefined }
    }

    const daysMap = new Map<string, AvailableDayInfo>(
      response.days.map(d => [d.date, {
        timeSlotCount: d.timeSlotCount,
        totalSlotsRemaining: d.totalSlotsRemaining,
      }])
    )
    setAvailableDays(daysMap)
    return { daysMap, minDate: response.minDate }
  }, [requestId, sessionId, isSessionMode])

  const handleSelectLocation = useCallback(async (location: EntityLocation) => {
    setSelectedLocation(location)
    setIsLoadingDays(true)
    setError(null)
    setSelectedDate(null)
    setSlots([])

    try {
      const { daysMap, minDate } = await loadAvailableDays(location.id)
      setMinBookableDate(minDate || null)

      if (minDate) {
        setViewMonth(new Date(minDate + 'T00:00:00'))
      }

      if (daysMap.size > 0) {
        setCurrentStep('slots')
      } else {
        setCurrentStep('fallback')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load available days')
    } finally {
      setIsLoadingDays(false)
    }
  }, [loadAvailableDays])

  const handleMonthChange = useCallback(async (newMonth: Date) => {
    if (!selectedLocation) return
    setViewMonth(newMonth)
    setSelectedDate(null)
    setSlots([])
    setIsLoadingDays(true)

    try {
      const fromDate = format(startOfMonth(newMonth), 'yyyy-MM-dd')
      const toDate = format(endOfMonth(newMonth), 'yyyy-MM-dd')
      await loadAvailableDays(selectedLocation.id, fromDate, toDate)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load days')
    } finally {
      setIsLoadingDays(false)
    }
  }, [selectedLocation, loadAvailableDays])

  const handleSelectDate = useCallback(async (dateStr: string) => {
    if (!selectedLocation) return
    setSelectedDate(dateStr)
    setIsLoadingSlots(true)

    try {
      if (isSessionMode && sessionId && getSessionSlotsRef.current) {
        // Session mode: use session-based API
        const slotsResponse = await getSessionSlotsRef.current(sessionId, selectedLocation.id, dateStr, 20)
        const filtered: AvailableSlot[] = slotsResponse.slots
          .filter(s => s.slotDate === dateStr)
          .map(s => ({
            slotDate: s.slotDate,
            slotTime: s.slotTime,
            locationName: s.locationName,
            locationAddress: s.locationAddress ?? undefined,
            slotsRemaining: s.slotsRemaining,
            city: s.city ?? undefined,
          }))
        setSlots(filtered)
      } else if (requestId && getSlotsRef.current) {
        // Request mode: use request-based API
        const slotsResponse = await getSlotsRef.current(requestId, selectedLocation.id, dateStr, 20)
        const filtered = slotsResponse.slots.filter(s => s.slotDate === dateStr)
        setSlots(filtered)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load time slots')
    } finally {
      setIsLoadingSlots(false)
    }
  }, [requestId, sessionId, isSessionMode, selectedLocation])

  const handleSelectSlot = useCallback(async (slot: AvailableSlot) => {
    if (!selectedLocation) return

    setIsHolding(true)
    setError(null)

    try {
      if (isSessionMode && sessionId && saveSelectionRef.current) {
        // Session mode: save selection to cache, then advance (no hold/countdown)
        const result = await saveSelectionRef.current(sessionId, {
          entityLocationId: selectedLocation.id,
          locationName: slot.locationName,
          city: slot.city || selectedLocation.city,
          appointmentDate: slot.slotDate,
          appointmentTime: slot.slotTime,
        })
        if (result.success) {
          onCompleteRef.current({
            hasAppointment: true,
            locationName: slot.locationName,
            appointmentDate: slot.slotDate,
            appointmentTime: slot.slotTime,
            city: slot.city || selectedLocation.city,
            entityLocationId: selectedLocation.id,
            isFallback: false,
          })
        } else {
          setError('Failed to save appointment selection')
        }
      } else if (requestId && holdSlotRef.current) {
        // Request mode: hold the slot (15 min countdown)
        const holdResponse = await holdSlotRef.current(requestId, {
          entityLocationId: selectedLocation.id,
          appointmentDate: slot.slotDate,
          appointmentTime: slot.slotTime,
        })

        if (holdResponse.success) {
          setHoldStatus({
            hasHold: true,
            status: 'held',
            locationName: slot.locationName,
            appointmentDate: slot.slotDate,
            appointmentTime: slot.slotTime,
            expiresAt: holdResponse.expiresAt,
            isExpired: false,
          })
          setHoldCountdown(holdResponse.expiresInSeconds)
          setCurrentStep('held')
        } else {
          setError(holdResponse.error || 'Failed to hold slot')
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to select slot')
    } finally {
      setIsHolding(false)
    }
  }, [requestId, sessionId, isSessionMode, selectedLocation])

  const handleContinueToPayment = useCallback(() => {
    if (!holdStatus) return

    onCompleteRef.current({
      hasAppointment: true,
      locationName: holdStatus.locationName,
      appointmentDate: holdStatus.appointmentDate,
      appointmentTime: holdStatus.appointmentTime,
      isFallback: false,
    })
  }, [holdStatus])

  const handleChangeSlot = useCallback(async () => {
    try {
      if (releaseHoldRef.current && requestId) await releaseHoldRef.current(requestId)
      setHoldStatus(null)
      setHoldCountdown(0)

      if (selectedLocation) {
        await handleSelectLocation(selectedLocation)
      } else {
        setCurrentStep('location')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to release hold')
    }
  }, [requestId, selectedLocation, handleSelectLocation])

  const handleSubmitWithoutAppointment = useCallback(async () => {
    if (!selectedLocation) return

    if (isSessionMode) {
      // Session mode: just advance with fallback (no DB operation needed)
      onCompleteRef.current({
        hasAppointment: false,
        locationName: selectedLocation.locationName,
        city: selectedLocation.city,
        entityLocationId: selectedLocation.id,
        isFallback: true,
      })
      return
    }

    // Request mode: call the backend to submit without appointment
    setIsLoading(true)
    setError(null)

    try {
      if (!submitWithoutAppointmentRef.current || !requestId) return
      const response = await submitWithoutAppointmentRef.current(requestId, selectedLocation.id)

      if (response.success) {
        onCompleteRef.current({
          hasAppointment: false,
          locationName: response.locationName,
          isFallback: true,
        })
      } else {
        setError(response.error || 'Failed to submit')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to submit')
    } finally {
      setIsLoading(false)
    }
  }, [requestId, isSessionMode, selectedLocation])

  const handleChangeLocation = useCallback(() => {
    setSelectedLocation(null)
    setSlots([])
    setAvailableDays(new Map())
    setSelectedDate(null)
    setCurrentStep('location')
  }, [])

  // ============================================================================
  // RENDER: LOADING STATE
  // ============================================================================

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-48" />
          <Skeleton className="h-4 w-64 mt-2" />
        </CardHeader>
        <CardContent className="space-y-4">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
        </CardContent>
      </Card>
    )
  }

  // ============================================================================
  // RENDER: ERROR STATE
  // ============================================================================

  if (error) {
    return (
      <Card>
        <CardContent className="pt-6">
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>{t.error}</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
          <div className="flex gap-2 mt-4">
            <Button variant="outline" onClick={onBack}>
              <ArrowLeft className="h-4 w-4 mr-2" />
              {t.back}
            </Button>
            <Button onClick={() => window.location.reload()}>
              <RefreshCw className="h-4 w-4 mr-2" />
              {t.retry}
            </Button>
          </div>
        </CardContent>
      </Card>
    )
  }

  // ============================================================================
  // RENDER: STEP 1 - LOCATION SELECTION
  // ============================================================================

  if (currentStep === 'location') {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <MapPin className="h-5 w-5" />
            {t.step1Title}
          </CardTitle>
          <CardDescription>{t.step1Desc}</CardDescription>
        </CardHeader>
        <CardContent>
          <RadioGroup
            value={selectedLocation?.id}
            onValueChange={(value) => {
              const location = locations.find((l) => l.id === value)
              if (location) handleSelectLocation(location)
            }}
            className="space-y-3"
          >
            {locations.map((location) => (
              <div
                key={location.id}
                className={`flex items-start space-x-4 rounded-lg border p-4 cursor-pointer transition-colors ${
                  (isLoadingDays || isLoadingSlots) && selectedLocation?.id === location.id
                    ? 'border-primary bg-primary/5'
                    : 'hover:bg-muted/50'
                }`}
                onClick={() => !(isLoadingDays || isLoadingSlots) && handleSelectLocation(location)}
              >
                <RadioGroupItem value={location.id} id={location.id} disabled={isLoadingDays || isLoadingSlots} />
                <div className="flex-1 space-y-1">
                  <Label
                    htmlFor={location.id}
                    className="text-base font-medium cursor-pointer flex items-center gap-2"
                  >
                    <Building2 className="h-4 w-4" />
                    {location.locationName}
                    {location.isMainOffice && (
                      <Badge variant="secondary" className="ml-2">
                        {t.mainOffice}
                      </Badge>
                    )}
                  </Label>
                  <p className="text-sm text-muted-foreground">
                    {location.city}
                    {location.province && `, ${location.province}`}
                    {location.region && ` - ${location.region}`}
                  </p>
                  {location.address && (
                    <p className="text-sm text-muted-foreground">{location.address}</p>
                  )}
                </div>
                {(isLoadingDays || isLoadingSlots) && selectedLocation?.id === location.id ? (
                  <Loader2 className="h-5 w-5 animate-spin text-primary" />
                ) : (
                  <ChevronRight className="h-5 w-5 text-muted-foreground" />
                )}
              </div>
            ))}
          </RadioGroup>

          <div className="flex justify-start mt-6">
            <Button variant="outline" onClick={onBack}>
              <ArrowLeft className="h-4 w-4 mr-2" />
              {t.back}
            </Button>
          </div>
        </CardContent>
      </Card>
    )
  }

  // ============================================================================
  // RENDER: STEP 2 - CALENDAR + TIME PICKER
  // ============================================================================

  if (currentStep === 'slots') {
    const todayDate = new Date()
    const minDate = minBookableDate ? new Date(minBookableDate + 'T00:00:00') : todayDate

    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Calendar className="h-5 w-5" />
            {t.step2Title}
          </CardTitle>
          <CardDescription>
            {t.step2Desc}
            {selectedLocation && (
              <span className="block mt-1 font-medium">{selectedLocation.locationName}</span>
            )}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Calendar Navigation */}
          <div className="flex items-center justify-between">
            <Button
              variant="outline"
              size="icon"
              onClick={() => handleMonthChange(subMonths(viewMonth, 1))}
              disabled={isLoadingDays}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <div className="flex items-center gap-2">
              <h3 className="text-lg font-semibold capitalize">
                {format(viewMonth, 'MMMM yyyy', { locale: dateLocale })}
              </h3>
              {isLoadingDays && <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />}
            </div>
            <div className="flex items-center gap-1">
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  const today = new Date()
                  setViewMonth(today)
                  handleMonthChange(today)
                }}
                disabled={isLoadingDays}
              >
                {t.today}
              </Button>
              <Button
                variant="outline"
                size="icon"
                onClick={() => handleMonthChange(addMonths(viewMonth, 1))}
                disabled={isLoadingDays}
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </div>

          {/* Weekday Headers */}
          <div className="grid grid-cols-7 gap-1">
            {weekdayHeaders.map((day) => (
              <div
                key={day}
                className="text-center text-xs font-semibold text-muted-foreground py-2 uppercase"
              >
                {day}
              </div>
            ))}
          </div>

          {/* Calendar Grid */}
          <div className="grid grid-cols-7 gap-1">
            {calendarDays.map((day) => {
              const dateKey = format(day, 'yyyy-MM-dd')
              const dayInfo = availableDays.get(dateKey)
              const isCurrentMonth = isSameMonth(day, viewMonth)
              const isTodayDate = isToday(day)
              const isBeforeMin = isBefore(day, minDate)
              const isSelected = selectedDate === dateKey
              const hasSlots = !!dayInfo && dayInfo.totalSlotsRemaining > 0
              const isWeekend = day.getDay() === 0 || day.getDay() === 6

              return (
                <button
                  key={dateKey}
                  type="button"
                  disabled={!hasSlots || !isCurrentMonth || isBeforeMin || isWeekend}
                  onClick={() => hasSlots && isCurrentMonth && !isBeforeMin && handleSelectDate(dateKey)}
                  className={cn(
                    'relative flex flex-col items-center justify-center rounded-lg p-2 min-h-[52px] transition-all text-sm',
                    // Base
                    !isCurrentMonth && 'opacity-30',
                    isCurrentMonth && !hasSlots && 'text-muted-foreground',
                    // Available day
                    hasSlots && isCurrentMonth && !isSelected && 'bg-primary/10 border border-primary/30 text-primary font-semibold hover:bg-primary/20 cursor-pointer',
                    // Selected day
                    isSelected && 'bg-primary text-primary-foreground font-bold shadow-md',
                    // Today ring
                    isTodayDate && !isSelected && 'ring-2 ring-primary/50',
                    // Before min date
                    isBeforeMin && isCurrentMonth && 'opacity-40 cursor-not-allowed',
                    // Weekend
                    isWeekend && isCurrentMonth && 'text-muted-foreground/50',
                    // Disabled
                    (!hasSlots || !isCurrentMonth || isBeforeMin || isWeekend) && 'cursor-default',
                  )}
                >
                  <span>{format(day, 'd')}</span>
                  {hasSlots && isCurrentMonth && (
                    <span className={cn(
                      'text-[10px] leading-tight',
                      isSelected ? 'text-primary-foreground/80' : 'text-primary/70'
                    )}>
                      {dayInfo.timeSlotCount}
                    </span>
                  )}
                </button>
              )
            })}
          </div>

          {/* Time Slots for Selected Day */}
          {selectedDate && (
            <div className="border-t pt-4 mt-2">
              <h4 className="text-sm font-semibold mb-3 flex items-center gap-2">
                <Clock className="h-4 w-4" />
                {t.timeSlotsTitle} — {formatDate(selectedDate, locale)}
              </h4>

              {isLoadingSlots ? (
                <div className="flex items-center justify-center py-6">
                  <Loader2 className="h-5 w-5 animate-spin text-primary mr-2" />
                  <span className="text-sm text-muted-foreground">{t.loading}</span>
                </div>
              ) : slots.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                  {slots.map((slot, idx) => (
                    <Button
                      key={idx}
                      variant={isHolding ? 'outline' : 'outline'}
                      size="sm"
                      className="h-auto py-2 px-4 flex flex-col items-center gap-0.5 hover:bg-primary hover:text-primary-foreground transition-colors"
                      onClick={() => handleSelectSlot(slot)}
                      disabled={isHolding}
                    >
                      {isHolding ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <>
                          <span className="text-base font-semibold">{formatTime(slot.slotTime)}</span>
                          <span className="text-[10px] opacity-70">
                            {t.slotsRemaining.replace('{count}', String(slot.slotsRemaining))}
                          </span>
                        </>
                      )}
                    </Button>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground py-2">{t.noSlotsForDay}</p>
              )}
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-2 pt-2">
            <Button variant="outline" onClick={handleChangeLocation}>
              <ArrowLeft className="h-4 w-4 mr-2" />
              {t.changeLocation}
            </Button>
          </div>
        </CardContent>
      </Card>
    )
  }

  // ============================================================================
  // RENDER: STEP 3 - HOLD CONFIRMED
  // ============================================================================

  if (currentStep === 'held' && holdStatus) {
    const progressPercent = (holdCountdown / 900) * 100 // 900 seconds = 15 minutes

    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-green-600">
            <CheckCircle className="h-5 w-5" />
            {t.step3Title}
          </CardTitle>
          <CardDescription>{t.step3Desc}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Success Alert */}
          <Alert className="border-green-200 bg-green-50">
            <CheckCircle className="h-4 w-4 text-green-600" />
            <AlertTitle className="text-green-800">{t.holdSuccess}</AlertTitle>
            <AlertDescription className="text-green-700">
              {t.holdExpiry.replace('{minutes}', String(Math.ceil(holdCountdown / 60)))}
            </AlertDescription>
          </Alert>

          {/* Countdown Timer */}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="flex items-center gap-2 text-muted-foreground">
                <Timer className="h-4 w-4" />
                {locale === 'es' ? 'Tiempo restante' : locale === 'fr' ? 'Temps restant' : 'Time remaining'}
              </span>
              <span className="font-mono text-lg font-bold text-primary">
                {formatTimeRemaining(holdCountdown)}
              </span>
            </div>
            <Progress value={progressPercent} className="h-2" />
          </div>

          {/* Appointment Details */}
          <div className="rounded-lg border p-4 space-y-3">
            <div className="flex items-center gap-3">
              <MapPin className="h-5 w-5 text-muted-foreground" />
              <div>
                <p className="font-medium">{holdStatus.locationName}</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <Calendar className="h-5 w-5 text-muted-foreground" />
              <p>{holdStatus.appointmentDate && formatDate(holdStatus.appointmentDate, locale)}</p>
            </div>
            <div className="flex items-center gap-3">
              <Clock className="h-5 w-5 text-muted-foreground" />
              <p>{holdStatus.appointmentTime && formatTime(holdStatus.appointmentTime)}</p>
            </div>
          </div>

          {/* Actions */}
          <div className="flex flex-col sm:flex-row gap-3">
            <Button className="flex-1" onClick={handleContinueToPayment}>
              {t.continueToPayment}
              <ChevronRight className="h-4 w-4 ml-2" />
            </Button>
            <Button variant="outline" onClick={handleChangeSlot}>
              {t.changeSlot}
            </Button>
          </div>
        </CardContent>
      </Card>
    )
  }

  // ============================================================================
  // RENDER: FALLBACK - NO SLOTS AVAILABLE
  // ============================================================================

  if (currentStep === 'fallback') {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-amber-600">
            <AlertCircle className="h-5 w-5" />
            {t.noSlotsTitle}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          <Alert className="border-amber-200 bg-amber-50">
            <AlertCircle className="h-4 w-4 text-amber-600" />
            <AlertDescription className="text-amber-700">
              {t.noSlotsDesc}
            </AlertDescription>
          </Alert>

          {selectedLocation && (
            <div className="rounded-lg border p-4">
              <p className="text-sm text-muted-foreground mb-1">
                {locale === 'es' ? 'Ubicacion preferida' : locale === 'fr' ? 'Lieu prefere' : 'Preferred location'}
              </p>
              <p className="font-medium">{selectedLocation.locationName}</p>
              <p className="text-sm text-muted-foreground">{selectedLocation.city}</p>
            </div>
          )}

          <div className="flex flex-col sm:flex-row gap-3">
            <Button className="flex-1" onClick={handleSubmitWithoutAppointment}>
              {t.submitWithoutAppt}
              <ChevronRight className="h-4 w-4 ml-2" />
            </Button>
            <Button variant="outline" onClick={handleChangeLocation}>
              {t.changeLocation}
            </Button>
          </div>
        </CardContent>
      </Card>
    )
  }

  return null
}
