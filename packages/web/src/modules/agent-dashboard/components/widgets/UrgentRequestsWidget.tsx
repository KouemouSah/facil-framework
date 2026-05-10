/**
 * UrgentRequestsWidget
 * Displays urgent and assigned requests in a compact table
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
  AlertTriangle,
  AlertCircle,
  Clock,
  ArrowRight,
  User,
} from 'lucide-react';
import { useUrgentRequests } from '../../hooks/useWidgetData';
import type { EntityCode } from '../../types';
import type { UrgentRequestItem } from '../../hooks/useWidgetData';

// =============================================================================
// PROPS
// =============================================================================

interface UrgentRequestsWidgetProps {
  entityCode: EntityCode;
  limit?: number;
  className?: string;
}

// =============================================================================
// CONSTANTS
// =============================================================================

const PRIORITY_COLORS: Record<string, string> = {
  URGENT: 'bg-red-500 text-white',
  HIGH: 'bg-orange-500 text-white',
  NORMAL: 'bg-blue-100 text-blue-800',
  LOW: 'bg-gray-100 text-gray-800',
};

const SLA_ICONS: Record<string, React.ReactNode> = {
  violated: <AlertTriangle className="h-4 w-4 text-red-500" />,
  at_risk: <AlertCircle className="h-4 w-4 text-yellow-500" />,
  on_track: <Clock className="h-4 w-4 text-green-500" />,
};

// =============================================================================
// COMPONENT
// =============================================================================

export function UrgentRequestsWidget({
  entityCode,
  limit = 5,
  className,
}: UrgentRequestsWidgetProps) {
  const locale = useLocale();
  const t = useTranslations('agent');
  const { data, isLoading, isError } = useUrgentRequests(entityCode, { limit });

  // Loading state
  if (isLoading) {
    return (
      <Card className={`h-full ${className || ""}`}>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-red-500" />
            {t('widgets.urgentRequests', { defaultValue: 'Solicitudes Urgentes' })}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-12 w-full" />
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
            <AlertTriangle className="h-5 w-5 text-red-500" />
            {t('widgets.urgentRequests', { defaultValue: 'Solicitudes Urgentes' })}
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

  const { items, total_urgent, total_high, total_assigned } = data || {
    items: [],
    total_urgent: 0,
    total_high: 0,
    total_assigned: 0,
  };

  const totalCount = total_urgent + total_high + total_assigned;

  return (
    <Card className={`h-full ${className || ""}`}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-red-500" />
            {t('widgets.urgentRequests', { defaultValue: 'Solicitudes Urgentes' })}
            {totalCount > 0 && (
              <Badge variant="secondary" className="ml-2">
                {totalCount}
              </Badge>
            )}
          </CardTitle>
          <div className="flex gap-1">
            {total_urgent > 0 && (
              <Badge className="bg-red-500 text-white text-xs">
                {total_urgent} urgente{total_urgent > 1 ? 's' : ''}
              </Badge>
            )}
            {total_high > 0 && (
              <Badge className="bg-orange-500 text-white text-xs">
                {total_high} alta{total_high > 1 ? 's' : ''}
              </Badge>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {items.length === 0 ? (
          <div className="text-center py-6 text-muted-foreground">
            <Clock className="h-8 w-8 mx-auto mb-2 opacity-50" />
            <p className="text-sm">{t('widgets.noUrgentRequests', { defaultValue: 'Sin solicitudes urgentes' })}</p>
          </div>
        ) : (
          <div className="space-y-2">
            {items.map((item) => (
              <RequestRow
                key={item.id}
                item={item}
                entityCode={entityCode}
                locale={locale}
              />
            ))}
            {totalCount > items.length && (
              <Link
                href={`/${locale}/dashboard/agent/${entityCode.toLowerCase().replace(/_/g, '-')}/pending`}
              >
                <Button variant="ghost" size="sm" className="w-full mt-2">
                  {t('widgets.viewAll', { defaultValue: 'Ver todas' })} ({totalCount})
                  <ArrowRight className="h-4 w-4 ml-2" />
                </Button>
              </Link>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// =============================================================================
// REQUEST ROW
// =============================================================================

interface RequestRowProps {
  item: UrgentRequestItem;
  entityCode: EntityCode;
  locale: string;
}

function RequestRow({ item, entityCode, locale }: RequestRowProps) {
  const t = useTranslations('agent');
  // Build entity base path
  const entityPath = entityCode.toLowerCase().replace('_', '-');

  return (
    <Link
      href={`/${locale}/dashboard/agent/${entityPath}/request/${item.id}`}
      className="block"
    >
      <div className="flex items-center justify-between p-2 rounded-lg hover:bg-muted/50 transition-colors cursor-pointer border border-transparent hover:border-border">
        <div className="flex items-center gap-3 min-w-0">
          {SLA_ICONS[item.sla_status]}
          <div className="min-w-0">
            <p className="font-medium text-sm truncate">{item.reference}</p>
            <p className="text-xs text-muted-foreground truncate">
              {item.citizen_name}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Badge className={`${PRIORITY_COLORS[item.priority]} text-xs`}>
            {item.priority}
          </Badge>
          {item.assigned_to && (
            <span title={t('widgets.assigned', { defaultValue: 'Asignado' })}>
              <User className="h-4 w-4 text-blue-500" />
            </span>
          )}
        </div>
      </div>
    </Link>
  );
}

export default UrgentRequestsWidget;
