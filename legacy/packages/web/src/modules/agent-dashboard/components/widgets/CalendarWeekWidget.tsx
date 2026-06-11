/**
 * CalendarWeekWidget
 * Displays a weekly calendar view of appointments
 *
 * @module agent-dashboard/components/widgets
 * @date 2026-01-26
 */

'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useLocale, useTranslations } from 'next-intl';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Calendar,
  ChevronLeft,
  ChevronRight,
  Clock,
  MapPin,
  User,
} from 'lucide-react';
import { useCalendarWeek } from '../../hooks/useWidgetData';
import type { EntityCode } from '../../types';
import type { WeekAppointmentItem, DayAppointments } from '../../hooks/useWidgetData';

// =============================================================================
// PROPS
// =============================================================================

interface CalendarWeekWidgetProps {
  entityCode: EntityCode;
  className?: string;
}

// =============================================================================
// CONSTANTS
// =============================================================================

const STATUS_COLORS: Record<string, string> = {
  confirmed: 'bg-green-100 text-green-800',
  arrived: 'bg-blue-100 text-blue-800',
  completed: 'bg-gray-100 text-gray-800',
  no_show: 'bg-red-100 text-red-800',
  pending: 'bg-yellow-100 text-yellow-800',
};

// =============================================================================
// COMPONENT
// =============================================================================

export function CalendarWeekWidget({
  entityCode,
  className,
}: CalendarWeekWidgetProps) {
  const locale = useLocale();
  const t = useTranslations('agent');
  const [weekOffset, setWeekOffset] = useState(0);
  const { data, isLoading, isError } = useCalendarWeek(entityCode, { weekOffset });

  // Loading state
  if (isLoading) {
    return (
      <Card className={className}>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <Calendar className="h-5 w-5 text-indigo-600" />
            {t('widgets.weeklyCalendar', { defaultValue: 'Calendario Semanal' })}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-7 gap-1">
            {[1, 2, 3, 4, 5, 6, 7].map((i) => (
              <Skeleton key={i} className="h-24 w-full" />
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  // Error state
  if (isError) {
    return (
      <Card className={className}>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <Calendar className="h-5 w-5 text-indigo-600" />
            {t('widgets.weeklyCalendar', { defaultValue: 'Calendario Semanal' })}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            {t('widgets.calendarError', { defaultValue: 'Error al cargar calendario' })}
          </p>
        </CardContent>
      </Card>
    );
  }

  const { days = [], total_week = 0, today_count = 0, week_start, week_end } = data || {};

  // Format week range for header
  const formatWeekRange = () => {
    if (!week_start || !week_end) return '';
    const start = new Date(week_start);
    const end = new Date(week_end);
    const options: Intl.DateTimeFormatOptions = { day: 'numeric', month: 'short' };
    return `${start.toLocaleDateString('es-ES', options)} - ${end.toLocaleDateString('es-ES', options)}`;
  };

  return (
    <Card className={className}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base flex items-center gap-2">
            <Calendar className="h-5 w-5 text-indigo-600" />
            {t('widgets.weeklyCalendar', { defaultValue: 'Calendario Semanal' })}
            {total_week > 0 && (
              <Badge variant="secondary" className="ml-2">
                {total_week} {t('widgets.appointment', { defaultValue: 'cita' })}{total_week > 1 ? 's' : ''}
              </Badge>
            )}
          </CardTitle>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={() => setWeekOffset(weekOffset - 1)}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <span className="text-sm font-medium min-w-[120px] text-center">
              {formatWeekRange()}
            </span>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={() => setWeekOffset(weekOffset + 1)}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
            {weekOffset !== 0 && (
              <Button
                variant="outline"
                size="sm"
                className="text-xs"
                onClick={() => setWeekOffset(0)}
              >
                {t('widgets.today', { defaultValue: 'Hoy' })}
              </Button>
            )}
          </div>
        </div>
        {today_count > 0 && (
          <p className="text-xs text-muted-foreground mt-1">
            {today_count} {t('widgets.appointment', { defaultValue: 'cita' })}{today_count > 1 ? 's' : ''} {t('widgets.today', { defaultValue: 'hoy' }).toLowerCase()}
          </p>
        )}
      </CardHeader>
      <CardContent>
        {/* Week Grid */}
        <div className="grid grid-cols-7 gap-1">
          {days.map((day) => (
            <DayColumn
              key={day.date}
              day={day}
              entityCode={entityCode}
              locale={locale}
            />
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

// =============================================================================
// DAY COLUMN
// =============================================================================

interface DayColumnProps {
  day: DayAppointments;
  entityCode: EntityCode;
  locale: string;
}

function DayColumn({ day, entityCode, locale }: DayColumnProps) {
  const entityPath = entityCode.toLowerCase().replace('_', '-');
  const maxVisible = 3;
  const hasMore = day.appointments.length > maxVisible;
  const visibleAppointments = day.appointments.slice(0, maxVisible);

  return (
    <div
      className={`
        min-h-[100px] rounded-lg border p-2
        ${day.is_today ? 'bg-indigo-50 border-indigo-300' : 'bg-muted/30'}
        ${day.is_past && !day.is_today ? 'opacity-60' : ''}
      `}
    >
      {/* Day Header */}
      <div className="text-center mb-2">
        <p className="text-xs text-muted-foreground capitalize">
          {day.day_name.slice(0, 3)}
        </p>
        <p
          className={`
            text-lg font-semibold
            ${day.is_today ? 'text-indigo-600' : ''}
          `}
        >
          {day.day_number}
        </p>
      </div>

      {/* Appointments */}
      <div className="space-y-1">
        {visibleAppointments.length === 0 ? (
          <p className="text-xs text-muted-foreground text-center py-2">
            -
          </p>
        ) : (
          visibleAppointments.map((apt) => (
            <AppointmentCard
              key={apt.id}
              appointment={apt}
              entityPath={entityPath}
              locale={locale}
            />
          ))
        )}
        {hasMore && (
          <Link
            href={`/${locale}/dashboard/agent/${entityPath}/appointments?date=${day.date}`}
            className="block"
          >
            <p className="text-xs text-center text-indigo-600 hover:underline">
              +{day.appointments.length - maxVisible} más
            </p>
          </Link>
        )}
      </div>
    </div>
  );
}

// =============================================================================
// APPOINTMENT CARD
// =============================================================================

interface AppointmentCardProps {
  appointment: WeekAppointmentItem;
  entityPath: string;
  locale: string;
}

function AppointmentCard({ appointment, entityPath, locale }: AppointmentCardProps) {
  const statusClass = STATUS_COLORS[appointment.appointment_status || 'pending'] || STATUS_COLORS.pending;

  return (
    <Link
      href={`/${locale}/dashboard/agent/${entityPath}/request/${appointment.id}`}
      className="block"
    >
      <div
        className={`
          p-1.5 rounded text-xs bg-white border shadow-sm
          hover:shadow-md transition-shadow cursor-pointer
        `}
      >
        {/* Time */}
        {appointment.cita_time && (
          <div className="flex items-center gap-1 text-muted-foreground mb-1">
            <Clock className="h-3 w-3" />
            <span className="font-medium">{appointment.cita_time}</span>
          </div>
        )}

        {/* Citizen */}
        <div className="flex items-center gap-1 truncate">
          <User className="h-3 w-3 text-muted-foreground flex-shrink-0" />
          <span className="truncate font-medium">{appointment.citizen_name}</span>
        </div>

        {/* Location */}
        {appointment.cita_location && (
          <div className="flex items-center gap-1 text-muted-foreground truncate mt-0.5">
            <MapPin className="h-3 w-3 flex-shrink-0" />
            <span className="truncate">{appointment.cita_location}</span>
          </div>
        )}

        {/* Status Badge */}
        {appointment.appointment_status && (
          <Badge className={`${statusClass} text-[10px] mt-1 px-1 py-0`}>
            {appointment.appointment_status}
          </Badge>
        )}
      </div>
    </Link>
  );
}

export default CalendarWeekWidget;
