/**
 * CalendarSlotsWidget
 * Displays slot availability summary for the week
 * Shows available vs booked slots per day with visual indicators
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  CalendarPlus,
  ChevronLeft,
  ChevronRight,
  MapPin,
  ArrowRight,
} from 'lucide-react';
import { useCalendarSlots } from '../../hooks/useWidgetData';
import type { EntityCode } from '../../types';
import type { DaySlotSummary } from '../../hooks/useWidgetData';

// =============================================================================
// PROPS
// =============================================================================

interface CalendarSlotsWidgetProps {
  entityCode: EntityCode;
  className?: string;
}

// =============================================================================
// CONSTANTS
// =============================================================================

const STATUS_STYLES: Record<string, { bg: string; text: string; border: string }> = {
  available: {
    bg: 'bg-green-50',
    text: 'text-green-700',
    border: 'border-green-200',
  },
  limited: {
    bg: 'bg-orange-50',
    text: 'text-orange-700',
    border: 'border-orange-200',
  },
  full: {
    bg: 'bg-red-50',
    text: 'text-red-700',
    border: 'border-red-200',
  },
  closed: {
    bg: 'bg-gray-100',
    text: 'text-gray-400',
    border: 'border-gray-200',
  },
};

// =============================================================================
// COMPONENT
// =============================================================================

export function CalendarSlotsWidget({
  entityCode,
  className,
}: CalendarSlotsWidgetProps) {
  const locale = useLocale();
  const t = useTranslations('agent.widgets.calendar');
  const [weekOffset, setWeekOffset] = useState(0);
  const [locationId, setLocationId] = useState<string | undefined>(undefined);

  const { data, isLoading, isError } = useCalendarSlots(entityCode, {
    weekOffset,
    locationId,
  });

  // Loading state
  if (isLoading) {
    return (
      <Card className={`h-full ${className || ""}`}>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <CalendarPlus className="h-5 w-5 text-emerald-600" />
            {t('title')}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-7 gap-1">
            {[1, 2, 3, 4, 5, 6, 7].map((i) => (
              <Skeleton key={i} className="h-20 w-full" />
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  // Error state
  if (isError) {
    return (
      <Card className={`h-full ${className || ""}`}>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <CalendarPlus className="h-5 w-5 text-emerald-600" />
            {t('title')}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            {t('loadError')}
          </p>
        </CardContent>
      </Card>
    );
  }

  const {
    days = [],
    total_available = 0,
    total_capacity = 0,
    week_start,
    week_end,
    location,
    locations_available = [],
  } = data || {};

  // Format week range for header
  const formatWeekRange = () => {
    if (!week_start || !week_end) return '';
    const start = new Date(week_start);
    const end = new Date(week_end);
    const options: Intl.DateTimeFormatOptions = { day: 'numeric', month: 'short' };
    const localeMap: Record<string, string> = { es: 'es-ES', fr: 'fr-FR', en: 'en-US' };
    const dateLocale = localeMap[locale] || 'es-ES';
    return `${start.toLocaleDateString(dateLocale, options)} - ${end.toLocaleDateString(dateLocale, options)}`;
  };

  const entityPath = entityCode.toLowerCase().replace('_', '-');

  return (
    <Card className={`h-full ${className || ""}`}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <CardTitle className="text-base flex items-center gap-2">
            <CalendarPlus className="h-5 w-5 text-emerald-600" />
            {t('title')}
            {total_available > 0 && (
              <Badge className="bg-emerald-100 text-emerald-800 ml-2">
                {total_available} {t('available')}
              </Badge>
            )}
          </CardTitle>

          {/* Location selector */}
          {locations_available.length > 1 && (
            <Select
              value={locationId || location?.id || ''}
              onValueChange={(val) => setLocationId(val || undefined)}
            >
              <SelectTrigger className="w-[180px] h-8 text-xs">
                <MapPin className="h-3 w-3 mr-1" />
                <SelectValue placeholder={t('location')} />
              </SelectTrigger>
              <SelectContent>
                {locations_available.map((loc) => (
                  <SelectItem key={loc.id} value={loc.id}>
                    {loc.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        </div>

        {/* Week navigation */}
        <div className="flex items-center justify-between mt-2">
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              onClick={() => setWeekOffset(weekOffset - 1)}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <span className="text-xs font-medium min-w-[100px] text-center">
              {formatWeekRange()}
            </span>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              onClick={() => setWeekOffset(weekOffset + 1)}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
            {weekOffset !== 0 && (
              <Button
                variant="outline"
                size="sm"
                className="text-xs h-7 ml-1"
                onClick={() => setWeekOffset(0)}
              >
                {t('today')}
              </Button>
            )}
          </div>

          {/* Capacity indicator */}
          {total_capacity > 0 && (
            <span className="text-xs text-muted-foreground">
              {total_available}/{total_capacity} {t('slots')}
            </span>
          )}
        </div>
      </CardHeader>

      <CardContent>
        {/* Week Grid */}
        <div className="grid grid-cols-7 gap-1 mb-3">
          {days.map((day) => (
            <DaySlotCell key={day.date} day={day} />
          ))}
        </div>

        {/* Link to full page */}
        <Link href={`/${locale}/dashboard/agent/${entityPath}/appointments`}>
          <Button variant="ghost" size="sm" className="w-full">
            {t('scheduleAppointment')}
            <ArrowRight className="h-4 w-4 ml-2" />
          </Button>
        </Link>
      </CardContent>
    </Card>
  );
}

// =============================================================================
// DAY SLOT CELL
// =============================================================================

interface DaySlotCellProps {
  day: DaySlotSummary;
}

function DaySlotCell({ day }: DaySlotCellProps) {
  const style = STATUS_STYLES[day.status] || STATUS_STYLES.closed;

  return (
    <div
      className={`
        rounded-lg border p-2 text-center transition-all
        ${style.bg} ${style.border}
        ${day.is_today ? 'ring-2 ring-emerald-500 ring-offset-1' : ''}
        ${day.is_past ? 'opacity-50' : ''}
      `}
    >
      {/* Day name */}
      <p className="text-[10px] text-muted-foreground uppercase tracking-wide">
        {day.day_name.slice(0, 3)}
      </p>

      {/* Day number */}
      <p className={`text-lg font-bold ${style.text}`}>
        {day.day_number}
      </p>

      {/* Availability */}
      {day.status === 'closed' ? (
        <p className="text-[10px] text-muted-foreground">-</p>
      ) : (
        <div className="mt-1">
          <p className={`text-xs font-medium ${style.text}`}>
            {day.available_slots}
          </p>
          <p className="text-[9px] text-muted-foreground">
            /{day.total_slots}
          </p>
        </div>
      )}

      {/* Fill indicator bar */}
      {day.status !== 'closed' && day.total_slots > 0 && (
        <div className="mt-1 h-1 bg-gray-200 rounded-full overflow-hidden">
          <div
            className={`h-full transition-all ${
              day.status === 'available' ? 'bg-green-500' :
              day.status === 'limited' ? 'bg-orange-500' :
              'bg-red-500'
            }`}
            style={{ width: `${day.fill_percentage}%` }}
          />
        </div>
      )}
    </div>
  );
}

export default CalendarSlotsWidget;
