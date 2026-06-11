/**
 * RescheduleDialog Component
 * Dialog for rescheduling an existing appointment
 *
 * @module agent-dashboard/components/appointments
 * @date 2026-01-30
 */

'use client';

import React, { useState } from 'react';
import { useTranslations } from 'next-intl';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import {
  ChevronLeft,
  ChevronRight,
  Calendar,
  Clock,
  RefreshCw,
  XCircle,
} from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import {
  useSlotsDetailed,
  useRescheduleAppointment,
  DaySlotDetail,
  SlotTimeDetail,
} from '../../hooks/useAppointments';
import type { EntityCode } from '../../types';

// =============================================================================
// PROPS
// =============================================================================

interface RescheduleDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  reservationId: string;
  currentDate: string;
  currentTime: string;
  reference: string;
  entityCode: EntityCode;
  locationId?: string;
  onSuccess?: () => void;
}

// =============================================================================
// HELPERS
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

export function RescheduleDialog({
  open,
  onOpenChange,
  reservationId,
  currentDate,
  currentTime,
  reference,
  entityCode,
  locationId,
  onSuccess,
}: RescheduleDialogProps) {
  const t = useTranslations('agent.pages.appointments.scheduleTab');
  const { toast } = useToast();
  const [weekOffset, setWeekOffset] = useState(0);
  const [selectedSlot, setSelectedSlot] = useState<{
    date: string;
    time: string;
    dayName: string;
  } | null>(null);

  const { data, isLoading, isError, refetch } = useSlotsDetailed(entityCode, {
    weekOffset,
    locationId,
    enabled: open,
  });

  const rescheduleMutation = useRescheduleAppointment();

  // Filter to show only weekdays
  const allDays = data?.days || [];
  const days = allDays.filter((day) => {
    const dayName = day.dayName.toLowerCase();
    return !['sábado', 'domingo', 'saturday', 'sunday', 'samedi', 'dimanche'].includes(dayName);
  });

  // Format week range
  const formatWeekRange = () => {
    if (!data?.weekStart) return '';
    const start = new Date(data.weekStart);
    const end = new Date(start);
    end.setDate(start.getDate() + 4);
    const options: Intl.DateTimeFormatOptions = { day: 'numeric', month: 'short' };
    return `${start.toLocaleDateString('es-ES', options)} - ${end.toLocaleDateString('es-ES', options)}`;
  };

  const handleSlotClick = (day: DaySlotDetail, slot: SlotTimeDetail) => {
    if (!slot.isAvailable) return;
    setSelectedSlot({
      date: day.date,
      time: slot.time,
      dayName: day.dayName,
    });
  };

  const handleReschedule = async () => {
    if (!selectedSlot) return;

    try {
      const result = await rescheduleMutation.mutateAsync({
        reservationId,
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
        onOpenChange(false);
        onSuccess?.();
      } else {
        toast({
          title: t('error'),
          description: result.error || t('rescheduleError'),
          variant: 'destructive',
        });
      }
    } catch (error) {
      toast({
        title: t('error'),
        description: error instanceof Error ? error.message : t('rescheduleError'),
        variant: 'destructive',
      });
    }
  };

  // Day name mapping
  const dayKeyMap: Record<string, string> = {
    lunes: 'mon',
    martes: 'tue',
    miércoles: 'wed',
    jueves: 'thu',
    viernes: 'fri',
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <RefreshCw className="h-5 w-5" />
            {t('reschedule')}
          </DialogTitle>
          <DialogDescription>
            {reference} - {t('existingAppointmentWarning', { date: currentDate, time: currentTime })}
          </DialogDescription>
        </DialogHeader>

        {isLoading ? (
          <div className="space-y-4 py-4">
            <div className="flex justify-center gap-2">
              <Skeleton className="h-8 w-8" />
              <Skeleton className="h-8 w-32" />
              <Skeleton className="h-8 w-8" />
            </div>
            <div className="grid grid-cols-5 gap-2">
              {[...Array(5)].map((_, i) => (
                <Skeleton key={i} className="h-48 w-full" />
              ))}
            </div>
          </div>
        ) : isError ? (
          <div className="py-8 text-center">
            <XCircle className="h-12 w-12 text-destructive mx-auto mb-4" />
            <p className="text-muted-foreground">{t('loadError')}</p>
            <Button variant="outline" onClick={() => refetch()} className="mt-4">
              {t('retry')}
            </Button>
          </div>
        ) : (
          <div className="space-y-4 py-4">
            {/* Week Navigation */}
            <div className="flex items-center justify-center gap-2">
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

            {/* Calendar Grid */}
            <div className="grid grid-cols-5 gap-2">
              {days.map((day) => {
                const dayKey = dayKeyMap[day.dayName.toLowerCase()] || 'mon';
                return (
                  <div
                    key={day.date}
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
                    <div className="p-1 max-h-48 overflow-y-auto">
                      {day.slots.length === 0 ? (
                        <div className="p-2 text-center text-xs text-muted-foreground">
                          {t('closed')}
                        </div>
                      ) : (
                        day.slots.map((slot) => {
                          const isSelected =
                            selectedSlot?.date === day.date && selectedSlot?.time === slot.time;
                          return (
                            <button
                              key={slot.time}
                              onClick={() => handleSlotClick(day, slot)}
                              disabled={!slot.isAvailable}
                              className={`
                                w-full px-2 py-1 mb-1 rounded text-xs font-medium
                                transition-all
                                ${getSlotColor(slot)}
                                ${isSelected ? 'ring-2 ring-primary ring-offset-1' : ''}
                              `}
                            >
                              <div className="flex items-center justify-between">
                                <span className="font-mono">{slot.time}</span>
                                <span className="text-[10px]">
                                  {slot.available}/{slot.capacity}
                                </span>
                              </div>
                            </button>
                          );
                        })
                      )}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Selected Slot Info */}
            {selectedSlot && (
              <div className="p-3 bg-primary/5 rounded-lg border flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className="flex items-center gap-2">
                    <Calendar className="h-4 w-4 text-primary" />
                    <span className="font-medium capitalize">{selectedSlot.dayName}</span>
                    <span className="text-muted-foreground">
                      {new Date(selectedSlot.date).toLocaleDateString('es-ES', {
                        day: 'numeric',
                        month: 'short',
                      })}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Clock className="h-4 w-4 text-primary" />
                    <span className="font-mono font-semibold">{selectedSlot.time}</span>
                  </div>
                </div>
                <Badge variant="secondary">{t('selectSlot')}</Badge>
              </div>
            )}
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            {t('cancel') || 'Cancelar'}
          </Button>
          <Button
            onClick={handleReschedule}
            disabled={!selectedSlot || rescheduleMutation.isPending}
          >
            {rescheduleMutation.isPending ? (
              t('creating')
            ) : (
              <>
                <RefreshCw className="h-4 w-4 mr-2" />
                {t('reschedule')}
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default RescheduleDialog;
