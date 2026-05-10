/**
 * EscalationsWidget
 * Displays pending escalations for supervisors
 * Reads from service_requests WHERE escalated = true
 *
 * @module agent-dashboard/components/widgets
 * @date 2026-02-21
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
  ArrowUpCircle,
  AlertTriangle,
  Clock,
  ArrowRight,
  User,
  DollarSign,
} from 'lucide-react';
import { useEscalations } from '../../hooks/useWidgetData';
import type { EntityCode } from '../../types';
import type { EscalationItem } from '../../hooks/useWidgetData';

// =============================================================================
// PROPS
// =============================================================================

interface EscalationsWidgetProps {
  entityCode: EntityCode;
  limit?: number;
  className?: string;
}

// =============================================================================
// CONSTANTS
// =============================================================================

const LEVEL_COLORS: Record<string, string> = {
  critical: 'bg-red-500 text-white',
  high: 'bg-orange-500 text-white',
  medium: 'bg-yellow-100 text-yellow-800',
  low: 'bg-gray-100 text-gray-800',
};

const LEVEL_ICONS: Record<string, React.ReactNode> = {
  critical: <AlertTriangle className="h-4 w-4 text-red-500" />,
  high: <ArrowUpCircle className="h-4 w-4 text-orange-500" />,
  medium: <ArrowUpCircle className="h-4 w-4 text-yellow-500" />,
  low: <ArrowUpCircle className="h-4 w-4 text-gray-400" />,
};

// =============================================================================
// COMPONENT
// =============================================================================

export function EscalationsWidget({
  entityCode,
  limit = 5,
  className,
}: EscalationsWidgetProps) {
  const locale = useLocale();
  const t = useTranslations('supervisor.escalations');
  const tCommon = useTranslations('common');
  const { data, isLoading, isError } = useEscalations(entityCode, { limit });

  const title = t('title');

  // Loading state
  if (isLoading) {
    return (
      <Card className={className}>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <ArrowUpCircle className="h-5 w-5 text-orange-600" />
            {title}
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
      <Card className={className}>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <ArrowUpCircle className="h-5 w-5 text-orange-600" />
            {title}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            {tCommon('error')}
          </p>
        </CardContent>
      </Card>
    );
  }

  const {
    items = [],
    total_escalations = 0,
    critical_count = 0,
    high_count = 0,
  } = data || {};

  return (
    <Card className={className}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base flex items-center gap-2">
            <ArrowUpCircle className="h-5 w-5 text-orange-600" />
            {title}
            {total_escalations > 0 && (
              <Badge variant="secondary" className="ml-2">
                {total_escalations}
              </Badge>
            )}
          </CardTitle>
          <div className="flex gap-1">
            {critical_count > 0 && (
              <Badge className="bg-red-500 text-white text-xs">
                {critical_count} {t('critical')}
              </Badge>
            )}
            {high_count > 0 && (
              <Badge className="bg-orange-500 text-white text-xs">
                {high_count} {t('high')}
              </Badge>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {items.length === 0 ? (
          <div className="text-center py-6 text-muted-foreground">
            <ArrowUpCircle className="h-8 w-8 mx-auto mb-2 opacity-50" />
            <p className="text-sm">{t('noPending')}</p>
          </div>
        ) : (
          <div className="space-y-2">
            {items.map((item) => (
              <EscalationRow
                key={item.request_id}
                item={item}
              />
            ))}
            <Link href={`/${locale}/dashboard/supervisor/escalations/pending`}>
              <Button variant="ghost" size="sm" className="w-full mt-2">
                {t('viewAll')}
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
// ESCALATION ROW
// =============================================================================

interface EscalationRowProps {
  item: EscalationItem;
}

function EscalationRow({ item }: EscalationRowProps) {
  const t = useTranslations('supervisor.escalations');
  const level = item.escalation_level || 'medium';
  const hoursAgo = item.hours_since_escalation
    ? Math.round(item.hours_since_escalation)
    : null;

  return (
    <div
      className={`p-3 rounded-lg border transition-colors
        ${level === 'critical' ? 'bg-red-50 border-red-200' :
          level === 'high' ? 'bg-orange-50 border-orange-200' :
          'bg-muted/50 border-border'}
      `}
    >
      <div className="flex items-start gap-3">
        {/* Level Icon */}
        <div className="flex-shrink-0 mt-0.5">
          {LEVEL_ICONS[level]}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-medium text-sm">
              {item.reference}
            </span>
            <Badge className={`${LEVEL_COLORS[level]} text-xs`}>
              {t(level)}
            </Badge>
          </div>

          {item.escalation_reason && (
            <p className="text-xs text-muted-foreground line-clamp-1 mb-1">
              {item.escalation_reason}
            </p>
          )}

          <div className="flex items-center gap-3 text-xs text-muted-foreground">
            {item.total_amount != null && item.total_amount > 0 && (
              <span className="flex items-center gap-1">
                <DollarSign className="h-3 w-3" />
                {item.total_amount.toLocaleString()} XAF
              </span>
            )}
            {item.escalated_by_name && (
              <span className="flex items-center gap-1">
                <User className="h-3 w-3" />
                {item.escalated_by_name}
              </span>
            )}
            {hoursAgo !== null && (
              <span className="flex items-center gap-1">
                <Clock className="h-3 w-3" />
                {hoursAgo}h
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default EscalationsWidget;
