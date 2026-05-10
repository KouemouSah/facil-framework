/**
 * ScheduleTab Component
 * Calendar view for scheduling new appointments (Monday-Friday only)
 *
 * @module agent-dashboard/components/appointments
 * @date 2026-01-30
 */

'use client';

import React, { useState } from 'react';
import { useTranslations } from 'next-intl';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  ChevronLeft,
  ChevronRight,
  MapPin,
  Calendar,
  Clock,
  XCircle,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
} from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import {
  useSlotsDetailed,
  useBookForCitizen,
  useRescheduleAppointment,
  DaySlotDetail,
  SlotTimeDetail,
  AssignedRequestForAppointment,
} from '../../hooks/useAppointments';
import { RequestCombobox } from './RequestCombobox';
import type { EntityCode } from '../../types';

// =============================================================================
// PROPS
// =============================================================================

interface ScheduleTabProps {
  entityCode: EntityCode;
  locationId?: string;
  onLocationChange?: (locationId: string) => void;
}

// =============================================================================
// SLOT STATUS COLORS
// =============================================================================

function getSlotColor(slot: SlotTimeDetail): string {
  if (!slot.isAvailable) return 'bg-gray-100 text-gray-400 cursor-not-allowed';
  if (slot.available === slot.capacity) return 'bg-green-50 text-green-700 hover:bg-green-100 cursor-pointer';
  if (slot.available > 0) return 'bg-orange-50 text-orange-700 hover:bg-orange-100 cursor-pointer';
  return 'bg-red-50 text-red-700 cursor-not-allowed';
}

// =============================================================================
// COMPONENT
// =============================================================================

export function ScheduleTab({
  entityCode,
  locationId,
  onLocationChange,
}: ScheduleTabProps) {
  const t = useTranslations('agent.pages.appointments.scheduleTab');
  const { toast } = useToast();
  const [weekOffset, setWeekOffset] = useState(0);
  const [selectedSlot, setSelectedSlot] = useState<{
    date: string;
    time: string;
    dayName: string;
  } | null>(null);
  const [selectedRequest, setSelectedRequest] = useState<AssignedRequestForAppointment | null>(null);

  const { data, isLoading, isError, refetch } = useSlotsDetailed(entityCode, {
    weekOffset,
    locationId,
  });

  const bookMutation = useBookForCitizen();
  const rescheduleMutation = useRescheduleAppointment();

  // Check if selected request already has an appointment
  const hasExistingAppointment = selectedRequest?.existingAppointment != null;
  const isReschedule = hasExistingAppointment;

  const handleSlotClick = (day: DaySlotDetail, slot: SlotTimeDetail) => {
    if (!slot.isAvailable) return;
    setSelectedSlot({
      date: day.date,
      time: slot.time,
      dayName: day.dayName,
    });
  };

  const handleBook = async () => {
    if (!selectedSlot || !selectedRequest || !locationId) {
      toast({
        title: t('error'),
        description: t('selectSlotAndRequest'),
        variant: 'destructive',
      });
      return;
    }

    try {
      if (isReschedule && selectedRequest.existingAppointment) {
        // Reschedule existing appointment
        const result = await rescheduleMutation.mutateAsync({
          reservationId: selectedRequest.existingAppointment.reservationId,
          data: {
            newDate: selectedSlot.date,
            newTime: selectedSlot.time,
          },
        });

        if (result.success) {
          toast({
            title: t('rescheduleSuccess'),
            description: t('bookingSuccess', { date: selectedSlot.date, time: selectedSlot.time }),
          });
          setSelectedSlot(null);
          setSelectedRequest(null);
          refetch();
        } else {
          toast({
            title: t('error'),
            description: result.error || t('rescheduleError'),
            variant: 'destructive',
          });
        }
      } else {
        // Create new appointment
        const result = await bookMutation.mutateAsync({
          requestId: selectedRequest.id,
          entityLocationId: locationId,
          appointmentDate: selectedSlot.date,
          appointmentTime: selectedSlot.time,
        });

        if (result.success) {
          toast({
            title: t('bookingCreated'),
            description: t('bookingSuccess', { date: selectedSlot.date, time: selectedSlot.time }),
          });
          setSelectedSlot(null);
          setSelectedRequest(null);
          refetch();
        } else {
          toast({
            title: t('error'),
            description: result.error || t('creationError'),
            variant: 'destructive',
          });
        }
      }
    } catch (error) {
      toast({
        title: t('error'),
        description: error instanceof Error ? error.message : t('creationError'),
        variant: 'destructive',
      });
    }
  };

  const isPending = bookMutation.isPending || rescheduleMutation.isPending;

  const handleCancelSelection = () => {
    setSelectedSlot(null);
  };

  // Loading state
  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <Skeleton className="h-8 w-48" />
          <div className="flex gap-2">
            <Skeleton className="h-10 w-10" />
            <Skeleton className="h-10 w-10" />
          </div>
        </div>
        <div className="grid grid-cols-5 gap-2">
          {[...Array(5)].map((_, i) => (
            <Skeleton key={i} className="h-64 w-full" />
          ))}
        </div>
      </div>
    );
  }

  // Error state
  if (isError) {
    return (
      <Card>
        <CardContent className="py-8 text-center">
          <XCircle className="h-12 w-12 text-destructive mx-auto mb-4" />
          <p className="text-muted-foreground">
            {t('loadError')}
          </p>
          <Button variant="outline" onClick={() => refetch()} className="mt-4">
            {t('retry')}
          </Button>
        </CardContent>
      </Card>
    );
  }

  const allDays = data?.days || [];
  // Filter to show only weekdays (Monday-Friday)
  const days = allDays.filter((day) => {
    const dayName = day.dayName.toLowerCase();
    return !['sábado', 'domingo', 'saturday', 'sunday', 'samedi', 'dimanche'].includes(dayName);
  });
  const locations = data?.locationsAvailable || [];
  const currentLocation = data?.location;

  // Calculate available slots for weekdays only
  const totalAvailable = days.reduce((sum, day) => sum + day.totalAvailable, 0);
  const totalCapacity = days.reduce((sum, day) => sum + day.totalCapacity, 0);

  // Format week range (Monday to Friday)
  const formatWeekRange = () => {
    if (!data?.weekStart) return '';
    const start = new Date(data.weekStart);
    const end = new Date(start);
    end.setDate(start.getDate() + 4); // Friday = Monday + 4
    const options: Intl.DateTimeFormatOptions = { day: 'numeric', month: 'short' };
    return `${start.toLocaleDateString('es-ES', options)} - ${end.toLocaleDateString('es-ES', options)}`;
  };

  return (
    <div className="space-y-6">
      {/* Header with Navigation */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-center gap-4">
          {/* Location Selector */}
          {locations.length > 1 && (
            <Select
              value={locationId || currentLocation?.id || ''}
              onValueChange={(val) => onLocationChange?.(val)}
            >
              <SelectTrigger className="w-[200px]">
                <MapPin className="h-4 w-4 mr-2" />
                <SelectValue placeholder="Localisation" />
              </SelectTrigger>
              <SelectContent>
                {locations.map((loc) => (
                  <SelectItem key={loc.id} value={loc.id}>
                    {loc.name} ({loc.city})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}

          {/* Week Navigation */}
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="icon"
              onClick={() => setWeekOffset(weekOffset - 1)}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <span className="text-sm font-medium min-w-[140px] text-center">
              {formatWeekRange()}
            </span>
            <Button
              variant="outline"
              size="icon"
              onClick={() => setWeekOffset(weekOffset + 1)}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
            {weekOffset !== 0 && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setWeekOffset(0)}
              >
                {t('today')}
              </Button>
            )}
          </div>
        </div>

        {/* Capacity Info */}
        <div className="text-sm text-muted-foreground">
          {t('slotsAvailable', { available: totalAvailable, total: totalCapacity })}
        </div>
      </div>

      {/* Calendar Grid + Booking Form */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Calendar Grid - 5 columns for weekdays */}
        <div className="lg:col-span-3">
          <Card>
            <CardContent className="p-4">
              <div className="grid grid-cols-5 gap-2">
                {days.map((day) => (
                  <DayColumn
                    key={day.date}
                    day={day}
                    selectedSlot={selectedSlot}
                    onSlotClick={(slot) => handleSlotClick(day, slot)}
                  />
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Legend */}
          <div className="flex flex-wrap gap-4 mt-4 text-sm">
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded bg-green-100 border border-green-300" />
              <span>{t('available')}</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded bg-orange-100 border border-orange-300" />
              <span>{t('limited')}</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded bg-red-100 border border-red-300" />
              <span>{t('full')}</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded bg-gray-100 border border-gray-300" />
              <span>{t('closed')}</span>
            </div>
          </div>
        </div>

        {/* Booking Form */}
        <div className="lg:col-span-1">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">{t('newBooking')}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {selectedSlot ? (
                <>
                  {/* Selected Slot Info */}
                  <div className="p-3 bg-primary/5 rounded-lg border">
                    <div className="flex items-center gap-2 mb-2">
                      <Calendar className="h-4 w-4 text-primary" />
                      <span className="font-medium capitalize">
                        {selectedSlot.dayName}
                      </span>
                    </div>
                    <div className="text-sm text-muted-foreground">
                      {new Date(selectedSlot.date).toLocaleDateString('es-ES', {
                        day: 'numeric',
                        month: 'long',
                        year: 'numeric',
                      })}
                    </div>
                    <div className="flex items-center gap-2 mt-2">
                      <Clock className="h-4 w-4 text-primary" />
                      <span className="font-mono font-semibold">{selectedSlot.time}</span>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="mt-2 text-xs"
                      onClick={handleCancelSelection}
                    >
                      {t('changeSlot')}
                    </Button>
                  </div>

                  {/* Request Selection */}
                  <div className="space-y-2">
                    <Label>
                      {t('requestNumber')} <span className="text-destructive">*</span>
                    </Label>
                    <RequestCombobox
                      entityCode={entityCode}
                      selectedRequest={selectedRequest}
                      onSelect={setSelectedRequest}
                      includeWithAppointment={true}
                    />
                  </div>

                  {/* Warning if request has existing appointment */}
                  {hasExistingAppointment && selectedRequest?.existingAppointment && (
                    <Alert variant="default" className="bg-orange-50 border-orange-200">
                      <AlertTriangle className="h-4 w-4 text-orange-600" />
                      <AlertDescription className="text-orange-800 text-sm">
                        {t('existingAppointmentWarning', {
                          date: selectedRequest.existingAppointment.date,
                          time: selectedRequest.existingAppointment.time,
                        })}
                      </AlertDescription>
                    </Alert>
                  )}

                  {/* Book/Reschedule Button */}
                  <Button
                    className="w-full"
                    onClick={handleBook}
                    disabled={!selectedRequest || isPending}
                    variant={isReschedule ? 'secondary' : 'default'}
                  >
                    {isPending ? (
                      t('creating')
                    ) : isReschedule ? (
                      <>
                        <RefreshCw className="h-4 w-4 mr-2" />
                        {t('reschedule')}
                      </>
                    ) : (
                      <>
                        <CheckCircle2 className="h-4 w-4 mr-2" />
                        {t('confirmBooking')}
                      </>
                    )}
                  </Button>
                </>
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  <Calendar className="h-12 w-12 mx-auto mb-3 opacity-50" />
                  <p>{t('selectSlotPrompt')}</p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// DAY COLUMN COMPONENT
// =============================================================================

interface DayColumnProps {
  day: DaySlotDetail;
  selectedSlot: { date: string; time: string } | null;
  onSlotClick: (slot: SlotTimeDetail) => void;
}

function DayColumn({ day, selectedSlot, onSlotClick }: DayColumnProps) {
  const t = useTranslations('agent.pages.appointments.scheduleTab');
  const isSelected = (slot: SlotTimeDetail) =>
    selectedSlot?.date === day.date && selectedSlot?.time === slot.time;

  // Map Spanish day names to translation keys
  const dayKeyMap: Record<string, string> = {
    lunes: 'mon',
    martes: 'tue',
    miércoles: 'wed',
    jueves: 'thu',
    viernes: 'fri',
  };
  const dayKey = dayKeyMap[day.dayName.toLowerCase()] || 'mon';

  return (
    <div
      className={`
        rounded-lg border overflow-hidden
        ${day.isToday ? 'ring-2 ring-primary ring-offset-1' : ''}
        ${day.isPast ? 'opacity-50' : ''}
      `}
    >
      {/* Day Header */}
      <div
        className={`
          p-2 text-center border-b
          ${day.isToday ? 'bg-primary text-primary-foreground' : 'bg-muted'}
        `}
      >
        <p className="text-xs uppercase tracking-wide">
          {t(`days.${dayKey}`)}
        </p>
        <p className="text-lg font-bold">{day.dayNumber}</p>
      </div>

      {/* Slots */}
      <div className="p-1 max-h-64 overflow-y-auto">
        {day.slots.length === 0 ? (
          <div className="p-2 text-center text-xs text-muted-foreground">
            {t('closed')}
          </div>
        ) : (
          day.slots.map((slot) => (
            <button
              key={slot.time}
              onClick={() => onSlotClick(slot)}
              disabled={!slot.isAvailable}
              className={`
                w-full px-2 py-1.5 mb-1 rounded text-xs font-medium
                transition-all
                ${getSlotColor(slot)}
                ${isSelected(slot) ? 'ring-2 ring-primary ring-offset-1' : ''}
              `}
            >
              <div className="flex items-center justify-between">
                <span className="font-mono">{slot.time}</span>
                <span className="text-[10px]">
                  {slot.available}/{slot.capacity}
                </span>
              </div>
            </button>
          ))
        )}
      </div>

      {/* Day Summary */}
      <div className="p-2 border-t bg-muted/50 text-center">
        <span className="text-xs text-muted-foreground">
          {day.totalAvailable} {t('avail')}
        </span>
      </div>
    </div>
  );
}

export default ScheduleTab;
