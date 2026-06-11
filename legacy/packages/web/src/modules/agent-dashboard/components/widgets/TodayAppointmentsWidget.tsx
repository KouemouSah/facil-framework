/**
 * TodayAppointmentsWidget
 * Displays today's appointments in chronological order
 *
 * @module agent-dashboard/components/widgets
 * @date 2026-01-26
 */

'use client';

import React from 'react';
import Link from 'next/link';
import { useLocale, useTranslations } from 'next-intl';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Calendar,
  Clock,
  MapPin,
  ArrowRight,
  CheckCircle,
  AlertCircle,
} from 'lucide-react';
import { useTodayAppointments } from '../../hooks/useWidgetData';
import type { EntityCode } from '../../types';
import type { AppointmentItem } from '../../hooks/useWidgetData';

// =============================================================================
// PROPS
// =============================================================================

interface TodayAppointmentsWidgetProps {
  entityCode: EntityCode;
  className?: string;
}

// =============================================================================
// COMPONENT
// =============================================================================

export function TodayAppointmentsWidget({
  entityCode,
  className,
}: TodayAppointmentsWidgetProps) {
  const locale = useLocale();
  const t = useTranslations('agent');
  const { data, isLoading, isError } = useTodayAppointments(entityCode);

  // Loading state
  if (isLoading) {
    return (
      <Card className={`h-full ${className || ""}`}>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <Calendar className="h-5 w-5 text-green-600" />
            {t('widgets.todayAppointments', { defaultValue: 'Citas de Hoy' })}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-14 w-full" />
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
            <Calendar className="h-5 w-5 text-green-600" />
            {t('widgets.todayAppointments', { defaultValue: 'Citas de Hoy' })}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            {t('widgets.loadError', { defaultValue: 'Error al cargar datos' })}
          </p>
        </CardContent>
      </Card>
    );
  }

  const { items, total_today, completed_today, upcoming_count } = data || {
    items: [],
    total_today: 0,
    completed_today: 0,
    upcoming_count: 0,
  };

  return (
    <Card className={`h-full ${className || ""}`}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base flex items-center gap-2">
            <Calendar className="h-5 w-5 text-green-600" />
            {t('widgets.todayAppointments', { defaultValue: 'Citas de Hoy' })}
            {total_today > 0 && (
              <Badge variant="secondary" className="ml-2">
                {total_today}
              </Badge>
            )}
          </CardTitle>
          <div className="flex gap-1 text-xs">
            {upcoming_count > 0 && (
              <Badge className="bg-blue-100 text-blue-800">
                {upcoming_count} {t('widgets.pending', { defaultValue: 'pendiente' })}{upcoming_count > 1 ? 's' : ''}
              </Badge>
            )}
            {completed_today > 0 && (
              <Badge className="bg-green-100 text-green-800">
                {completed_today} {t('widgets.completed', { defaultValue: 'completada' })}{completed_today > 1 ? 's' : ''}
              </Badge>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {items.length === 0 ? (
          <div className="text-center py-6 text-muted-foreground">
            <Calendar className="h-8 w-8 mx-auto mb-2 opacity-50" />
            <p className="text-sm">{t('widgets.noAppointmentsToday', { defaultValue: 'Sin citas programadas para hoy' })}</p>
          </div>
        ) : (
          <div className="space-y-2">
            {items.map((item) => (
              <AppointmentRow
                key={item.id}
                item={item}
                entityCode={entityCode}
                locale={locale}
              />
            ))}
            <Link
              href={`/${locale}/dashboard/agent/${entityCode.toLowerCase().replace(/_/g, '-')}/appointments`}
            >
              <Button variant="ghost" size="sm" className="w-full mt-2">
                {t('widgets.viewAllAppointments', { defaultValue: 'Ver todas las citas' })}
                <ArrowRight className="h-4 w-4 ml-2" />
              </Button>
            </Link>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// =============================================================================
// APPOINTMENT ROW
// =============================================================================

interface AppointmentRowProps {
  item: AppointmentItem;
  entityCode: EntityCode;
  locale: string;
}

function AppointmentRow({ item, entityCode, locale }: AppointmentRowProps) {
  const entityPath = entityCode.toLowerCase().replace('_', '-');
  const isCompleted = item.status === 'COMPLETED';
  const isCancelled = item.status === 'CANCELLED';

  // Get type label
  const getTypeLabel = (solicitudType: string) => {
    const labels: Record<string, string> = {
      expedicion: 'Nuevo',
      renovacion: 'Renovación',
    };
    return labels[solicitudType] || solicitudType;
  };

  return (
    <Link
      href={`/${locale}/dashboard/agent/${entityPath}/request/${item.id}`}
      className="block"
    >
      <div
        className={`flex items-center justify-between p-3 rounded-lg border transition-colors cursor-pointer
          ${item.is_past && !isCompleted ? 'bg-yellow-50 border-yellow-200' : 'hover:bg-muted/50 border-transparent hover:border-border'}
          ${isCompleted ? 'bg-green-50 border-green-200 opacity-75' : ''}
          ${isCancelled ? 'bg-gray-50 border-gray-200 opacity-50' : ''}
        `}
      >
        <div className="flex items-center gap-3">
          {/* Time */}
          <div className="flex flex-col items-center min-w-[50px]">
            <Clock className={`h-4 w-4 ${item.is_past ? 'text-yellow-600' : 'text-blue-600'}`} />
            <span className="text-sm font-medium">
              {item.cita_time || '--:--'}
            </span>
          </div>

          {/* Divider */}
          <div className="h-10 w-px bg-border" />

          {/* Info */}
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <p className="font-medium text-sm truncate">{item.citizen_name}</p>
              {isCompleted && (
                <CheckCircle className="h-4 w-4 text-green-600" />
              )}
              {item.is_past && !isCompleted && !isCancelled && (
                <AlertCircle className="h-4 w-4 text-yellow-600" />
              )}
            </div>
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <span>{item.reference}</span>
              <span>•</span>
              <span>{getTypeLabel(item.solicitud_type)}</span>
            </div>
          </div>
        </div>

        {/* Location */}
        {item.cita_location && (
          <div className="flex items-center gap-1 text-xs text-muted-foreground">
            <MapPin className="h-3 w-3" />
            <span className="truncate max-w-[100px]">{item.cita_location}</span>
          </div>
        )}
      </div>
    </Link>
  );
}

export default TodayAppointmentsWidget;
