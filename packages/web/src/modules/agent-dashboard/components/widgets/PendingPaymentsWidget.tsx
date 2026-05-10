/**
 * PendingPaymentsWidget
 * Displays pending payment validations for treasury agents
 * Uses v_pending_payment_validations database view
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
  CreditCard,
  Clock,
  ArrowRight,
  User,
  AlertCircle,
} from 'lucide-react';
import { usePendingPayments } from '../../hooks/useWidgetData';
import type { PendingPaymentItem } from '../../hooks/useWidgetData';

// =============================================================================
// PROPS
// =============================================================================

interface PendingPaymentsWidgetProps {
  workflowCode?: string;
  statusFilter?: string;
  title?: string;
  titleKey?: string;
  limit?: number;
  className?: string;
}

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

function getWaitingStatus(hours: number | null): {
  label: string;
  color: string;
} {
  if (hours === null) return { label: 'N/A', color: 'text-gray-500' };
  if (hours < 2) return { label: `${Math.round(hours * 60)}m`, color: 'text-green-600' };
  if (hours < 8) return { label: `${Math.round(hours)}h`, color: 'text-blue-600' };
  if (hours < 24) return { label: `${Math.round(hours)}h`, color: 'text-yellow-600' };
  const days = Math.round(hours / 24);
  return { label: `${days}d`, color: 'text-red-600' };
}

// =============================================================================
// COMPONENT
// =============================================================================

export function PendingPaymentsWidget({
  workflowCode,
  statusFilter,
  title,
  titleKey,
  limit = 5,
  className,
}: PendingPaymentsWidgetProps) {
  const locale = useLocale();
  const t = useTranslations('agent');
  const { data, isLoading, isError } = usePendingPayments({
    workflowCode,
    statusFilter,
    limit,
  });

  const widgetTitle = titleKey ? t(titleKey) : title || t('widgets.pendingPayments', { defaultValue: 'Pagos Pendientes' });

  // Loading state
  if (isLoading) {
    return (
      <Card className={className}>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <CreditCard className="h-5 w-5 text-emerald-600" />
            {widgetTitle}
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
      <Card className={className}>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <CreditCard className="h-5 w-5 text-emerald-600" />
            {widgetTitle}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            {t('widgets.pendingPaymentsError', { defaultValue: 'Error al cargar pagos pendientes' })}
          </p>
        </CardContent>
      </Card>
    );
  }

  const {
    items = [],
    total_pending = 0,
    total_amount,
    avg_waiting_hours,
  } = data || {};

  return (
    <Card className={className}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base flex items-center gap-2">
            <CreditCard className="h-5 w-5 text-emerald-600" />
            {widgetTitle}
            {total_pending > 0 && (
              <Badge variant="secondary" className="ml-2">
                {total_pending}
              </Badge>
            )}
          </CardTitle>
          {total_amount && (
            <Badge className="bg-emerald-100 text-emerald-800">
              {formatAmount(total_amount, locale)} XAF
            </Badge>
          )}
        </div>
        {avg_waiting_hours != null && avg_waiting_hours > 0 && (
          <p className="text-xs text-muted-foreground mt-1">
            {t('widgets.avgWaitingTime', { defaultValue: 'Tiempo promedio de espera' })}: {Math.round(avg_waiting_hours)}h
          </p>
        )}
      </CardHeader>
      <CardContent>
        {items.length === 0 ? (
          <div className="text-center py-6 text-muted-foreground">
            <CreditCard className="h-8 w-8 mx-auto mb-2 opacity-50" />
            <p className="text-sm">{t('widgets.noPendingPayments', { defaultValue: 'Sin pagos pendientes de validación' })}</p>
          </div>
        ) : (
          <div className="space-y-2">
            {items.map((item) => (
              <PaymentRow key={item.payment_id} item={item} locale={locale} />
            ))}
            <Link href={`/${locale}/dashboard/agent/treasury/validation`}>
              <Button variant="ghost" size="sm" className="w-full mt-2">
                {t('widgets.viewAllPayments', { defaultValue: 'Ver todos los pagos' })}
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
// PAYMENT ROW
// =============================================================================

interface PaymentRowProps {
  item: PendingPaymentItem;
  locale: string;
}

function PaymentRow({ item, locale }: PaymentRowProps) {
  const waitingStatus = getWaitingStatus(item.hours_waiting);
  const isLongWait = (item.hours_waiting ?? 0) > 8;

  return (
    <Link
      href={`/${locale}/dashboard/agent/treasury/validation/${item.payment_id}`}
      className="block"
    >
      <div
        className={`p-3 rounded-lg border transition-colors cursor-pointer
          ${isLongWait ? 'bg-yellow-50 border-yellow-200' : 'hover:bg-muted/50 border-transparent hover:border-border'}
        `}
      >
        <div className="flex items-center justify-between">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className="font-medium text-sm truncate">
                {item.payment_reference}
              </span>
              {item.workflow_code && (
                <Badge variant="outline" className="text-xs">
                  {item.workflow_code}
                </Badge>
              )}
            </div>
            <div className="flex items-center gap-3 text-xs text-muted-foreground">
              {item.user_name && (
                <span className="flex items-center gap-1 truncate">
                  <User className="h-3 w-3" />
                  {item.user_name}
                </span>
              )}
              {item.payment_method && (
                <span className="capitalize">{item.payment_method}</span>
              )}
            </div>
          </div>

          <div className="flex flex-col items-end gap-1 ml-3">
            <span className="font-medium text-sm">
              {formatAmount(item.total_amount, locale)} {item.currency}
            </span>
            <span className={`flex items-center gap-1 text-xs ${waitingStatus.color}`}>
              {isLongWait && <AlertCircle className="h-3 w-3" />}
              <Clock className="h-3 w-3" />
              {waitingStatus.label}
            </span>
          </div>
        </div>
      </div>
    </Link>
  );
}

export default PendingPaymentsWidget;
