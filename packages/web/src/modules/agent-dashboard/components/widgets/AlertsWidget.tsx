/**
 * AlertsWidget
 * Displays system alerts (SLA warnings, documents pending, etc.)
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
  Bell,
  AlertTriangle,
  AlertCircle,
  Info,
  FileText,
  Clock,
  ArrowRight,
  CheckCircle,
} from 'lucide-react';
import { useSystemAlerts } from '../../hooks/useWidgetData';
import type { EntityCode } from '../../types';
import type { AlertItem } from '../../hooks/useWidgetData';

// =============================================================================
// PROPS
// =============================================================================

interface AlertsWidgetProps {
  entityCode: EntityCode;
  maxItems?: number;
  className?: string;
}

// =============================================================================
// CONSTANTS
// =============================================================================

const SEVERITY_STYLES: Record<string, { bg: string; border: string; icon: React.ReactNode }> = {
  error: {
    bg: 'bg-red-50',
    border: 'border-red-200',
    icon: <AlertTriangle className="h-4 w-4 text-red-500" />,
  },
  warning: {
    bg: 'bg-yellow-50',
    border: 'border-yellow-200',
    icon: <AlertCircle className="h-4 w-4 text-yellow-500" />,
  },
  info: {
    bg: 'bg-blue-50',
    border: 'border-blue-200',
    icon: <Info className="h-4 w-4 text-blue-500" />,
  },
};

const TYPE_ICONS: Record<string, React.ReactNode> = {
  sla_warning: <Clock className="h-4 w-4" />,
  documents_pending: <FileText className="h-4 w-4" />,
  assignment_needed: <AlertCircle className="h-4 w-4" />,
  system: <Bell className="h-4 w-4" />,
};

// =============================================================================
// COMPONENT
// =============================================================================

export function AlertsWidget({
  entityCode,
  maxItems = 5,
  className,
}: AlertsWidgetProps) {
  const locale = useLocale();
  const t = useTranslations('agent');
  const { data, isLoading, isError } = useSystemAlerts(entityCode);

  // Loading state
  if (isLoading) {
    return (
      <Card className={`h-full ${className || ''}`}>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <Bell className="h-5 w-5 text-yellow-600" />
            {t('widgets.alerts', { defaultValue: 'Alertas' })}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-16 w-full" />
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  // Error state
  if (isError) {
    return (
      <Card className={`h-full ${className || ''}`}>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <Bell className="h-5 w-5 text-yellow-600" />
            {t('widgets.alerts', { defaultValue: 'Alertas' })}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            {t('widgets.alertsError', { defaultValue: 'Error al cargar alertas' })}
          </p>
        </CardContent>
      </Card>
    );
  }

  const { items, total_warnings, total_errors } = data || {
    items: [],
    total_warnings: 0,
    total_errors: 0,
  };

  const displayedItems = items.slice(0, maxItems);
  const remainingCount = items.length - displayedItems.length;

  return (
    <Card className={`h-full ${className || ''}`}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base flex items-center gap-2">
            <Bell className="h-5 w-5 text-yellow-600" />
            {t('widgets.alerts', { defaultValue: 'Alertas' })}
            {items.length > 0 && (
              <Badge variant="secondary" className="ml-2">
                {items.length}
              </Badge>
            )}
          </CardTitle>
          <div className="flex gap-1">
            {total_errors > 0 && (
              <Badge className="bg-red-500 text-white text-xs">
                {total_errors} crítico{total_errors > 1 ? 's' : ''}
              </Badge>
            )}
            {total_warnings > 0 && (
              <Badge className="bg-yellow-500 text-white text-xs">
                {total_warnings} aviso{total_warnings > 1 ? 's' : ''}
              </Badge>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {items.length === 0 ? (
          <div className="text-center py-6 text-muted-foreground">
            <CheckCircle className="h-8 w-8 mx-auto mb-2 text-green-500 opacity-75" />
            <p className="text-sm">{t('widgets.noActiveAlerts', { defaultValue: 'Sin alertas activas' })}</p>
          </div>
        ) : (
          <div className="space-y-2">
            {displayedItems.map((item) => (
              <AlertRow
                key={item.id}
                item={item}
                locale={locale}
              />
            ))}
            {remainingCount > 0 && (
              <Button variant="ghost" size="sm" className="w-full mt-2">
                {t('widgets.viewMore', { defaultValue: 'Ver {count} más', count: remainingCount })}
                <ArrowRight className="h-4 w-4 ml-2" />
              </Button>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// =============================================================================
// ALERT ROW
// =============================================================================

interface AlertRowProps {
  item: AlertItem;
  locale: string;
}

function AlertRow({ item, locale }: AlertRowProps) {
  const severityStyle = SEVERITY_STYLES[item.severity] || SEVERITY_STYLES.info;
  const typeIcon = TYPE_ICONS[item.type] || <Bell className="h-4 w-4" />;

  const content = (
    <div
      className={`p-3 rounded-lg border transition-colors cursor-pointer
        ${severityStyle.bg} ${severityStyle.border}
        hover:opacity-90
      `}
    >
      <div className="flex items-start gap-3">
        {/* Icon */}
        <div className="flex-shrink-0 mt-0.5">
          {severityStyle.icon}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <p className="font-medium text-sm">{item.title}</p>
            {item.request_reference && (
              <Badge variant="outline" className="text-xs">
                {item.request_reference}
              </Badge>
            )}
          </div>
          <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
            {item.message}
          </p>
        </div>

        {/* Type icon */}
        <div className="flex-shrink-0 text-muted-foreground">
          {typeIcon}
        </div>
      </div>
    </div>
  );

  // If there's an action URL, wrap in Link
  if (item.action_url) {
    const url = item.action_url.startsWith('/')
      ? `/${locale}${item.action_url}`
      : item.action_url;

    return <Link href={url}>{content}</Link>;
  }

  return content;
}

export default AlertsWidget;
