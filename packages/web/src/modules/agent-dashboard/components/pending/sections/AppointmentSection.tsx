/**
 * AppointmentSection - Appointment display and scheduling
 * Shows existing appointment or allows agent to schedule one
 *
 * @module agent-dashboard/components/pending/sections
 * @date 2026-01-26
 */

'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useTranslations } from 'next-intl';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Calendar, Clock, MapPin, AlertCircle, Loader2, CalendarPlus } from 'lucide-react';
import { toast } from 'sonner';
import { agentAppointmentsApi } from '../../../services/appointments-api';
import { useAgentDashboard } from '../../../hooks/useAgentDashboard';
import type { RequestPreviewAppointment } from '../../../services/agent-requests-api';
import type { SlotsCalendarResponse, SlotTimeDetail } from '../../../services/appointments-api';

// =============================================================================
// PROPS
// =============================================================================

interface AppointmentSectionProps {
  appointment?: RequestPreviewAppointment | null;
  requestId: string;
  entityCode: string;
  onAppointmentCreated?: () => void;
}

// =============================================================================
// COMPONENT
// =============================================================================

export function AppointmentSection({
  appointment,
  requestId,
  entityCode,
  onAppointmentCreated,
}: AppointmentSectionProps) {
  const t = useTranslations('agent.pending');
  const { context } = useAgentDashboard();
  const agentLocationId = context?.entityLocationId;

  // State for scheduling
  const [isScheduling, setIsScheduling] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [slotsData, setSlotsData] = useState<SlotsCalendarResponse | null>(null);
  const [selectedLocationId, setSelectedLocationId] = useState<string>('');
  const [selectedDate, setSelectedDate] = useState<string>('');
  const [selectedTime, setSelectedTime] = useState<string>('');
  const [weekOffset, setWeekOffset] = useState(0);

  // Format date for display
  const formatDate = (dateStr: string): string => {
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString('es-ES', {
        weekday: 'long',
        day: 'numeric',
        month: 'long',
        year: 'numeric',
      });
    } catch {
      return dateStr;
    }
  };

  // Load slots — wrapped in useCallback so useEffect can depend on it
  const loadSlots = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await agentAppointmentsApi.getSlotsDetailed(
        entityCode,
        weekOffset,
        selectedLocationId || undefined
      );
      setSlotsData(data);

      // Auto-select agent's own location, fallback to first available
      if (!selectedLocationId && data.locationsAvailable.length > 0) {
        const agentSite = agentLocationId
          ? data.locationsAvailable.find((l) => l.id === agentLocationId)
          : null;
        setSelectedLocationId(agentSite?.id || data.locationsAvailable[0].id);
      }
    } catch (error) {
      console.error('Error loading slots:', error);
      toast.error(t('appointment.loadError'));
    } finally {
      setIsLoading(false);
    }
  }, [entityCode, weekOffset, selectedLocationId, agentLocationId, t]);

  // Load slots when scheduling mode is activated or location changes
  useEffect(() => {
    if (isScheduling) {
      loadSlots();
    }
  }, [isScheduling, loadSlots]);

  // Get available times for selected date
  const getAvailableTimes = (): SlotTimeDetail[] => {
    if (!slotsData || !selectedDate) return [];
    const day = slotsData.days.find(d => d.date === selectedDate);
    return day?.slots.filter(s => s.isAvailable) || [];
  };

  // Handle booking
  const handleBook = async () => {
    if (!selectedLocationId || !selectedDate || !selectedTime) {
      toast.error(t('appointment.selectAll'));
      return;
    }

    setIsSubmitting(true);
    try {
      const result = await agentAppointmentsApi.bookForCitizen({
        requestId,
        entityLocationId: selectedLocationId,
        appointmentDate: selectedDate,
        appointmentTime: selectedTime,
      });

      if (result.success) {
        toast.success(t('appointment.bookSuccess'));
        setIsScheduling(false);
        onAppointmentCreated?.();
      } else {
        toast.error(result.error || t('appointment.bookError'));
      }
    } catch (error) {
      console.error('Booking error:', error);
      toast.error(t('appointment.bookError'));
    } finally {
      setIsSubmitting(false);
    }
  };

  // Reset form
  const handleCancel = () => {
    setIsScheduling(false);
    setSelectedDate('');
    setSelectedTime('');
    setWeekOffset(0);
  };

  // If appointment exists, show compact info
  if (appointment) {
    return (
      <Card className="border-green-200 bg-green-50/50 h-full">
        <CardContent className="p-3">
          <p className="text-[11px] text-green-700 uppercase tracking-wider mb-1 flex items-center gap-1">
            <Calendar className="h-3 w-3" />
            {t('preview.appointment')}
          </p>
          {/* Line 1: Date + Time */}
          <div className="flex items-center gap-1.5 flex-wrap">
            <Calendar className="h-3.5 w-3.5 text-green-600 shrink-0" />
            <span className="text-sm font-medium capitalize">
              {formatDate(appointment.date)}
            </span>
            <Clock className="h-3.5 w-3.5 text-green-600 shrink-0" />
            <span className="text-sm font-medium">{appointment.time}</span>
          </div>
          {/* Line 2: Location */}
          <div className="flex items-center gap-1.5 mt-0.5">
            <MapPin className="h-3.5 w-3.5 text-green-600 shrink-0" />
            <span className="text-sm font-medium">{appointment.locationName}</span>
          </div>
        </CardContent>
      </Card>
    );
  }

  // No appointment - show scheduling form or prompt
  return (
    <Card className="border-orange-200 bg-orange-50/50 h-full">
      <CardContent className="p-3">
        <p className="text-[11px] text-orange-700 uppercase tracking-wider mb-1.5 flex items-center gap-1">
          <AlertCircle className="h-3 w-3" />
          {t('appointment.noAppointment')}
        </p>
        {!isScheduling ? (
          // Compact prompt to schedule
          <div className="flex items-center justify-between">
            <p className="text-xs text-muted-foreground">
              {t('appointment.noAppointmentDesc')}
            </p>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsScheduling(true)}
              className="border-orange-300 text-orange-700 hover:bg-orange-100 shrink-0 ml-2 h-7 text-xs"
            >
              <CalendarPlus className="h-3.5 w-3.5 mr-1" />
              {t('appointment.schedule')}
            </Button>
          </div>
        ) : (
          // Scheduling form
          <div className="space-y-3">
            {isLoading ? (
              <div className="flex items-center justify-center py-4">
                <Loader2 className="h-5 w-5 animate-spin text-orange-600" />
                <span className="ml-2 text-sm text-muted-foreground">
                  {t('appointment.loadingSlots')}
                </span>
              </div>
            ) : (
              <>
                {/* Location Select */}
                <div className="space-y-1">
                  <label className="text-xs font-medium text-muted-foreground flex items-center gap-1">
                    <MapPin className="h-3 w-3" />
                    {t('appointment.location')}
                  </label>
                  <Select
                    value={selectedLocationId}
                    onValueChange={(v) => {
                      setSelectedLocationId(v);
                      setSelectedDate('');
                      setSelectedTime('');
                    }}
                  >
                    <SelectTrigger className="h-9">
                      <SelectValue placeholder={t('appointment.selectLocation')} />
                    </SelectTrigger>
                    <SelectContent>
                      {slotsData?.locationsAvailable.map((loc) => (
                        <SelectItem key={loc.id} value={loc.id}>
                          {loc.name} ({loc.city})
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {/* Date Select */}
                <div className="space-y-1">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-medium text-muted-foreground flex items-center gap-1">
                      <Calendar className="h-3 w-3" />
                      {t('appointment.date')}
                    </label>
                    <div className="flex gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 px-2 text-xs"
                        onClick={() => setWeekOffset(w => Math.max(0, w - 1))}
                        disabled={weekOffset === 0}
                      >
                        ←
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 px-2 text-xs"
                        onClick={() => setWeekOffset(w => w + 1)}
                      >
                        →
                      </Button>
                    </div>
                  </div>
                  <Select
                    value={selectedDate}
                    onValueChange={(v) => {
                      setSelectedDate(v);
                      setSelectedTime('');
                    }}
                    disabled={!selectedLocationId}
                  >
                    <SelectTrigger className="h-9">
                      <SelectValue placeholder={t('appointment.selectDate')} />
                    </SelectTrigger>
                    <SelectContent>
                      {slotsData?.days
                        .filter(d => !d.isPast && !d.isBlocked && d.totalAvailable > 0)
                        .map((day) => (
                          <SelectItem key={day.date} value={day.date}>
                            {day.dayName} {day.dayNumber} ({day.totalAvailable} {t('appointment.available')})
                          </SelectItem>
                        ))}
                    </SelectContent>
                  </Select>
                </div>

                {/* Time Select */}
                <div className="space-y-1">
                  <label className="text-xs font-medium text-muted-foreground flex items-center gap-1">
                    <Clock className="h-3 w-3" />
                    {t('appointment.time')}
                  </label>
                  <Select
                    value={selectedTime}
                    onValueChange={setSelectedTime}
                    disabled={!selectedDate}
                  >
                    <SelectTrigger className="h-9">
                      <SelectValue placeholder={t('appointment.selectTime')} />
                    </SelectTrigger>
                    <SelectContent>
                      {getAvailableTimes().map((slot) => (
                        <SelectItem key={slot.time} value={slot.time}>
                          {slot.time} ({slot.available} {t('appointment.available')})
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {/* Actions */}
                <div className="flex gap-2 pt-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleCancel}
                    disabled={isSubmitting}
                    className="flex-1"
                  >
                    {t('appointment.cancel')}
                  </Button>
                  <Button
                    size="sm"
                    onClick={handleBook}
                    disabled={isSubmitting || !selectedLocationId || !selectedDate || !selectedTime}
                    className="flex-1 bg-orange-600 hover:bg-orange-700"
                  >
                    {isSubmitting ? (
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    ) : (
                      <CalendarPlus className="h-4 w-4 mr-2" />
                    )}
                    {isSubmitting ? t('appointment.booking') : t('appointment.book')}
                  </Button>
                </div>
              </>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default AppointmentSection;
