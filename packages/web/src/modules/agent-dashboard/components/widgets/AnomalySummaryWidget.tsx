/**
 * AnomalySummaryWidget
 * Displays payment anomaly summary for treasury agents and supervisors
 * Uses v_anomaly_summary database view
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
  ShieldAlert,
  AlertTriangle,
  AlertCircle,
  CheckCircle,
  ArrowRight,
  DollarSign,
} from 'lucide-react';
import { useAnomalySummary } from '../../hooks/useWidgetData';
import type { AnomalySummaryItem } from '../../hooks/useWidgetData';

// =============================================================================
// PROPS
// =============================================================================

interface AnomalySummaryWidgetProps {
  className?: string;
}

// =============================================================================
// CONSTANTS
// =============================================================================

const SEVERITY_STYLES: Record<string, {
  bg: string;
  border: string;
  text: string;
  icon: React.ReactNode;
}> = {
  critical: {
    bg: 'bg-red-50',
    border: 'border-red-200',
    text: 'text-red-700',
    icon: <AlertTriangle className="h-4 w-4 text-red-500" />,
  },
  high: {
    bg: 'bg-orange-50',
    border: 'border-orange-200',
    text: 'text-orange-700',
    icon: <AlertCircle className="h-4 w-4 text-orange-500" />,
  },
  medium: {
    bg: 'bg-yellow-50',
    border: 'border-yellow-200',
    text: 'text-yellow-700',
    icon: <AlertCircle className="h-4 w-4 text-yellow-500" />,
  },
  low: {
    bg: 'bg-gray-50',
    border: 'border-gray-200',
    text: 'text-gray-700',
    icon: <AlertCircle className="h-4 w-4 text-gray-400" />,
  },
};

const ANOMALY_TYPE_KEYS: string[] = [
  'amount_mismatch',
  'duplicate_suspected',
  'reconciliation_failed',
  'validated_not_received',
  'sla_breached',
  'high_amount',
  'suspicious_pattern',
  'manual_flag',
  'duplicate_payment',
  'late_validation',
  'orphan_transaction',
  'reference_missing',
];

// =============================================================================
// HELPER FUNCTIONS
// =============================================================================

function formatAmount(amount: number | null, locale: string = 'es'): string {
  if (amount === null) return '--';
  const intlLocale = locale === 'fr' ? 'fr-FR' : locale === 'en' ? 'en-US' : 'es-GQ';
  return new Intl.NumberFormat(intlLocale, {
    style: 'decimal',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
}

// =============================================================================
// COMPONENT
// =============================================================================

export function AnomalySummaryWidget({ className }: AnomalySummaryWidgetProps) {
  const locale = useLocale();
  const t = useTranslations('agent');
  const { data, isLoading, isError } = useAnomalySummary();

  // Loading state
  if (isLoading) {
    return (
      <Card className={className}>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <ShieldAlert className="h-5 w-5 text-red-600" />
            {t('widgets.anomalies', { defaultValue: 'Anomalías' })}
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
      <Card className={className}>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <ShieldAlert className="h-5 w-5 text-red-600" />
            {t('widgets.anomalies', { defaultValue: 'Anomalías' })}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            {t('widgets.anomalyError', { defaultValue: 'Error al cargar anomalías' })}
          </p>
        </CardContent>
      </Card>
    );
  }

  const {
    items = [],
    total_open = 0,
    total_critical = 0,
    total_amount_affected,
  } = data || {};

  return (
    <Card className={className}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base flex items-center gap-2">
            <ShieldAlert className="h-5 w-5 text-red-600" />
            {t('widgets.anomalies', { defaultValue: 'Anomalías' })}
            {total_open > 0 && (
              <Badge variant="secondary" className="ml-2">
                {total_open}
              </Badge>
            )}
          </CardTitle>
          <div className="flex gap-1">
            {total_critical > 0 && (
              <Badge className="bg-red-500 text-white text-xs">
                {total_critical} crítico{total_critical > 1 ? 's' : ''}
              </Badge>
            )}
          </div>
        </div>
        {total_amount_affected && total_amount_affected > 0 && (
          <p className="text-xs text-muted-foreground mt-1 flex items-center gap-1">
            <DollarSign className="h-3 w-3" />
            {t('widgets.amountAffected', { defaultValue: 'Monto afectado' })}: {formatAmount(total_amount_affected, locale)} XAF
          </p>
        )}
      </CardHeader>
      <CardContent>
        {items.length === 0 ? (
          <div className="text-center py-6 text-muted-foreground">
            <CheckCircle className="h-8 w-8 mx-auto mb-2 text-green-500 opacity-75" />
            <p className="text-sm">{t('widgets.noAnomalies', { defaultValue: 'Sin anomalías detectadas' })}</p>
          </div>
        ) : (
          <div className="space-y-2">
            {items.map((item, index) => (
              <AnomalyRow
                key={`${item.anomaly_type}-${item.severity}-${index}`}
                item={item}
                t={t}
                locale={locale}
              />
            ))}
            <Link href={`/${locale}/dashboard/agent/treasury/anomalies`}>
              <Button variant="ghost" size="sm" className="w-full mt-2">
                {t('widgets.viewAllAnomalies', { defaultValue: 'Ver todas las anomalías' })}
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
// ANOMALY ROW
// =============================================================================

interface AnomalyRowProps {
  item: AnomalySummaryItem;
  t: (key: string, values?: Record<string, string>) => string;
  locale: string;
}

function AnomalyRow({ item, t, locale }: AnomalyRowProps) {
  const severity = item.severity || 'medium';
  const style = SEVERITY_STYLES[severity] || SEVERITY_STYLES.medium;
  const typeLabel = ANOMALY_TYPE_KEYS.includes(item.anomaly_type)
    ? t(`widgets.anomalyTypes.${item.anomaly_type}`)
    : item.anomaly_type;

  return (
    <div
      className={`p-3 rounded-lg border ${style.bg} ${style.border}`}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          {style.icon}
          <div>
            <p className={`font-medium text-sm ${style.text}`}>
              {typeLabel}
            </p>
            <p className="text-xs text-muted-foreground capitalize">
              {item.status} • {item.count} caso{item.count > 1 ? 's' : ''}
            </p>
          </div>
        </div>
        <div className="text-right">
          <Badge className={`${
            severity === 'critical' ? 'bg-red-500 text-white' :
            severity === 'high' ? 'bg-orange-500 text-white' :
            severity === 'medium' ? 'bg-yellow-100 text-yellow-800' :
            'bg-gray-100 text-gray-800'
          } text-xs`}>
            {severity}
          </Badge>
          {item.total_affected && item.total_affected > 0 && (
            <p className="text-xs text-muted-foreground mt-1">
              {formatAmount(item.total_affected, locale)} XAF
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

export default AnomalySummaryWidget;
