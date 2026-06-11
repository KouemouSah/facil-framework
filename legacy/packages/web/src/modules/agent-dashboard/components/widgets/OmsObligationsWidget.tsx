/**
 * OmsObligationsWidget
 * Dashboard widget for MIN_* agents showing obligation processing stats.
 * Calls /oms/queue/stats (license_obligations via assignments).
 *
 * Variants:
 *  - pending:    pending_count + total_amount_pending
 *  - completed:  completed_today + total_amount_completed_today
 *  - documents:  pending_count (reuse — obligations needing review)
 *  - ministry:   all 4 KPIs in a compact grid
 */

'use client';

import React from 'react';
import Link from 'next/link';
import { useLocale, useTranslations } from 'next-intl';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import {
  ClipboardList,
  CheckCircle2,
  Clock,
  DollarSign,
  ArrowRight,
  FileCheck,
  AlertCircle,
} from 'lucide-react';
import { omsQueueApi } from '@/modules/oms/services/api';
import type { AgentQueueStats } from '@/modules/oms/types';

// =============================================================================
// TYPES
// =============================================================================

export type OmsWidgetVariant = 'pending' | 'completed' | 'documents' | 'ministry';

interface OmsObligationsWidgetProps {
  variant: OmsWidgetVariant;
  className?: string;
}

// =============================================================================
// VARIANT CONFIG
// =============================================================================

const VARIANT_CONFIG: Record<OmsWidgetVariant, {
  icon: typeof ClipboardList;
  iconColor: string;
  titleKey: string;
}> = {
  pending: {
    icon: Clock,
    iconColor: 'text-amber-600',
    titleKey: 'widgets.omsPendingProcessing',
  },
  completed: {
    icon: CheckCircle2,
    iconColor: 'text-green-600',
    titleKey: 'widgets.omsProcessedToday',
  },
  documents: {
    icon: FileCheck,
    iconColor: 'text-blue-600',
    titleKey: 'widgets.omsDocumentsPending',
  },
  ministry: {
    icon: ClipboardList,
    iconColor: 'text-indigo-600',
    titleKey: 'widgets.omsMinistryStats',
  },
};

// =============================================================================
// HELPER
// =============================================================================

function fmtAmount(amount: number, locale: string): string {
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

export function OmsObligationsWidget({ variant, className }: OmsObligationsWidgetProps) {
  const locale = useLocale();
  const t = useTranslations('agent');
  const config = VARIANT_CONFIG[variant];
  const Icon = config.icon;

  const { data, isLoading, isError } = useQuery<AgentQueueStats>({
    queryKey: ['oms-queue-stats'],
    queryFn: () => omsQueueApi.getStats(),
    staleTime: 30 * 1000,
    refetchInterval: 60 * 1000,
  });

  const widgetTitle = t(config.titleKey, {
    defaultValue: config.titleKey.split('.').pop() || '',
  });

  // Loading
  if (isLoading) {
    return (
      <Card className={className}>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <Icon className={`h-5 w-5 ${config.iconColor}`} />
            {widgetTitle}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Skeleton className="h-16 w-full" />
        </CardContent>
      </Card>
    );
  }

  // Error
  if (isError) {
    return (
      <Card className={className}>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <Icon className={`h-5 w-5 ${config.iconColor}`} />
            {widgetTitle}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <AlertCircle className="h-4 w-4" />
            {t('widgets.loadError', { defaultValue: 'Error al cargar datos' })}
          </div>
        </CardContent>
      </Card>
    );
  }

  const stats = data || { pending_count: 0, completed_today: 0, total_amount_pending: 0, total_amount_completed_today: 0, awaiting_document: 0, not_started: 0 };

  return (
    <Card className={className}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base flex items-center gap-2">
            <Icon className={`h-5 w-5 ${config.iconColor}`} />
            {widgetTitle}
          </CardTitle>
          {variant === 'pending' && stats.pending_count > 0 && (
            <Badge variant="secondary">{stats.pending_count}</Badge>
          )}
          {variant === 'completed' && stats.completed_today > 0 && (
            <Badge className="bg-green-100 text-green-800">{stats.completed_today}</Badge>
          )}
          {variant === 'documents' && stats.awaiting_document > 0 && (
            <Badge className="bg-blue-100 text-blue-800">{stats.awaiting_document}</Badge>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {variant === 'pending' && (
          <PendingView stats={stats} locale={locale} t={t} />
        )}
        {variant === 'completed' && (
          <CompletedView stats={stats} locale={locale} t={t} />
        )}
        {variant === 'documents' && (
          <DocumentsView stats={stats} locale={locale} t={t} />
        )}
        {variant === 'ministry' && (
          <MinistryView stats={stats} locale={locale} t={t} />
        )}
        <Link href={`/${locale}/dashboard/agent/oms`}>
          <Button variant="ghost" size="sm" className="w-full mt-3">
            {t('widgets.viewOmsQueue', { defaultValue: 'Ver cola de obligaciones' })}
            <ArrowRight className="h-4 w-4 ml-2" />
          </Button>
        </Link>
      </CardContent>
    </Card>
  );
}

// =============================================================================
// VARIANT VIEWS
// =============================================================================

function PendingView({ stats, locale, t }: { stats: AgentQueueStats; locale: string; t: ReturnType<typeof useTranslations> }) {
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-sm text-muted-foreground">
          {t('widgets.obligationsPending', { defaultValue: 'Obligaciones pendientes' })}
        </span>
        <span className="text-2xl font-bold">{stats.pending_count}</span>
      </div>
      {stats.not_started > 0 && (
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground flex items-center gap-1">
            <Clock className="h-3.5 w-3.5" />
            {t('widgets.notStarted', { defaultValue: 'Sin iniciar' })}
          </span>
          <span className="font-medium text-amber-600">{stats.not_started}</span>
        </div>
      )}
      {stats.total_amount_pending > 0 && (
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground flex items-center gap-1">
            <DollarSign className="h-3.5 w-3.5" />
            {t('widgets.totalAmount', { defaultValue: 'Monto total' })}
          </span>
          <span className="font-medium">{fmtAmount(stats.total_amount_pending, locale)} XAF</span>
        </div>
      )}
    </div>
  );
}

function CompletedView({ stats, locale, t }: { stats: AgentQueueStats; locale: string; t: ReturnType<typeof useTranslations> }) {
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-sm text-muted-foreground">
          {t('widgets.completedToday', { defaultValue: 'Procesadas hoy' })}
        </span>
        <span className="text-2xl font-bold text-green-600">{stats.completed_today}</span>
      </div>
      {stats.total_amount_completed_today > 0 && (
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground flex items-center gap-1">
            <DollarSign className="h-3.5 w-3.5" />
            {t('widgets.amountProcessed', { defaultValue: 'Monto procesado' })}
          </span>
          <span className="font-medium text-green-600">{fmtAmount(stats.total_amount_completed_today, locale)} XAF</span>
        </div>
      )}
    </div>
  );
}

function DocumentsView({ stats, t }: { stats: AgentQueueStats; locale: string; t: ReturnType<typeof useTranslations> }) {
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-sm text-muted-foreground">
          {t('widgets.obligationsAwaitingDocs', { defaultValue: 'Sin documento emitido' })}
        </span>
        <span className="text-2xl font-bold text-blue-600">{stats.awaiting_document}</span>
      </div>
      {stats.awaiting_document === 0 && stats.pending_count > 0 && (
        <p className="text-xs text-muted-foreground">
          {t('widgets.allDocsIssued', { defaultValue: 'Todos los documentos emitidos' })}
        </p>
      )}
    </div>
  );
}

function MinistryView({ stats, locale, t }: { stats: AgentQueueStats; locale: string; t: ReturnType<typeof useTranslations> }) {
  return (
    <div className="grid grid-cols-3 gap-2">
      <div className="text-center p-2 rounded-lg bg-amber-50">
        <p className="text-xs text-muted-foreground">{t('widgets.pending', { defaultValue: 'Pendientes' })}</p>
        <p className="text-lg font-bold text-amber-700">{stats.pending_count}</p>
      </div>
      <div className="text-center p-2 rounded-lg bg-green-50">
        <p className="text-xs text-muted-foreground">{t('widgets.today', { defaultValue: 'Hoy' })}</p>
        <p className="text-lg font-bold text-green-700">{stats.completed_today}</p>
      </div>
      <div className="text-center p-2 rounded-lg bg-blue-50">
        <p className="text-xs text-muted-foreground">{t('widgets.awaitingDoc', { defaultValue: 'Sin doc.' })}</p>
        <p className="text-lg font-bold text-blue-700">{stats.awaiting_document}</p>
      </div>
      <div className="col-span-3 flex items-center justify-between text-sm px-1 pt-1">
        <span className="text-muted-foreground">{t('widgets.amtPending', { defaultValue: 'Monto pend.' })}</span>
        <span className="font-medium">{fmtAmount(stats.total_amount_pending, locale)} XAF</span>
      </div>
    </div>
  );
}

export default OmsObligationsWidget;
