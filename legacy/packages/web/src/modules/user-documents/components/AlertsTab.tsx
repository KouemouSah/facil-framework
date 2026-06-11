/**
 * AlertsTab - Proactive document alerts (expiry, missing, etc.)
 *
 * Displays alerts grouped by severity with mark-read and dismiss actions.
 * Alerts are color-coded: critical (red), warning (orange), info (blue).
 *
 * @module user-documents/components
 */

'use client';

import { useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useLocale, useTranslations } from 'next-intl';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import {
  AlertTriangle,
  AlertCircle,
  Info,
  Bell,
  BellOff,
  Check,
  X,
  ChevronRight,
} from 'lucide-react';
import { useDocumentAlerts } from '../hooks';
import type { DocumentAlert, AlertSeverity } from '../types';

// ---------------------------------------------------------------------------
// Severity configuration
// ---------------------------------------------------------------------------

const SEVERITY_CONFIG: Record<
  AlertSeverity,
  {
    icon: typeof AlertCircle;
    bgColor: string;
    borderColor: string;
    textColor: string;
    badgeVariant: 'default' | 'destructive' | 'outline';
  }
> = {
  critical: {
    icon: AlertCircle,
    bgColor: 'bg-red-50 dark:bg-red-950/20',
    borderColor: 'border-red-200 dark:border-red-900',
    textColor: 'text-red-700 dark:text-red-300',
    badgeVariant: 'destructive',
  },
  warning: {
    icon: AlertTriangle,
    bgColor: 'bg-orange-50 dark:bg-orange-950/20',
    borderColor: 'border-orange-200 dark:border-orange-900',
    textColor: 'text-orange-700 dark:text-orange-300',
    badgeVariant: 'default',
  },
  info: {
    icon: Info,
    bgColor: 'bg-blue-50 dark:bg-blue-950/20',
    borderColor: 'border-blue-200 dark:border-blue-900',
    textColor: 'text-blue-700 dark:text-blue-300',
    badgeVariant: 'outline',
  },
};

function formatDate(dateStr: string, locale: string): string {
  try {
    return new Intl.DateTimeFormat(locale, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    }).format(new Date(dateStr));
  } catch {
    return dateStr;
  }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

// Action labels and routes for suggested_action codes
const ACTION_LABELS: Record<string, Record<string, string>> = {
  start_renewal: { es: 'Renovar', fr: 'Renouveler', en: 'Renew' },
  view_document: { es: 'Ver documento', fr: 'Voir document', en: 'View document' },
  plan_renewal: { es: 'Planificar', fr: 'Planifier', en: 'Plan renewal' },
  upload_document: { es: 'Subir documento', fr: 'Telecharger', en: 'Upload' },
};

export function AlertsTab() {
  const locale = useLocale() as 'es' | 'fr' | 'en';
  const router = useRouter();
  const t = useTranslations('userDocuments');
  const {
    alerts,
    isLoading,
    unreadCount,
    criticalCount,
    markRead,
    dismiss,
  } = useDocumentAlerts();

  // Handle suggested action click — navigate to appropriate page
  const handleActionClick = useCallback(
    (alert: DocumentAlert) => {
      const action = alert.suggested_action;
      const params = alert.action_params as Record<string, string> | null;

      switch (action) {
        case 'start_renewal':
        case 'plan_renewal': {
          // Navigate to new service request wizard
          const workflowScope = params?.workflow_scope || '';
          if (workflowScope) {
            router.push(`/${locale}/dashboard/service-requests/new?workflow=${workflowScope}`);
          } else {
            router.push(`/${locale}/dashboard/service-requests/new`);
          }
          break;
        }
        case 'view_document': {
          // Navigate to document detail in vault
          const docId = params?.document_id;
          if (docId) {
            router.push(`/${locale}/dashboard/mis-documentos?doc=${docId}`);
          } else {
            router.push(`/${locale}/dashboard/mis-documentos`);
          }
          break;
        }
        case 'upload_document': {
          // Navigate to vault upload
          router.push(`/${locale}/dashboard/mis-documentos?tab=personal`);
          break;
        }
        default:
          // Fallback: navigate to vault
          router.push(`/${locale}/dashboard/mis-documentos`);
      }

      // Mark as actioned
      if (!alert.is_read) {
        markRead.mutate({ alertId: alert.id });
      }
    },
    [locale, router, markRead]
  );

  // Get localized title — backend sends title + title_es/fr/en
  const getTitle = useCallback(
    (alert: DocumentAlert): string => {
      if (locale === 'fr' && alert.title_fr) return alert.title_fr;
      if (locale === 'en' && alert.title_en) return alert.title_en;
      return alert.title_es || alert.title || '';
    },
    [locale]
  );

  // Get localized message
  const getMessage = useCallback(
    (alert: DocumentAlert): string => {
      if (locale === 'fr' && alert.message_fr) return alert.message_fr;
      if (locale === 'en' && alert.message_en) return alert.message_en;
      return alert.message_es || alert.message || '';
    },
    [locale]
  );

  // Handle mark as read
  const handleMarkRead = useCallback(
    (alertId: string) => {
      markRead.mutate({ alertId });
    },
    [markRead]
  );

  // Handle dismiss
  const handleDismiss = useCallback(
    (alertId: string) => {
      dismiss.mutate({ alertId });
    },
    [dismiss]
  );

  // Group alerts by severity (critical first, then warning, then info)
  const activeAlerts = alerts.filter((a) => !a.is_dismissed);
  const groupedAlerts: Record<AlertSeverity, DocumentAlert[]> = {
    critical: activeAlerts.filter((a) => a.severity === 'critical'),
    warning: activeAlerts.filter((a) => a.severity === 'warning'),
    info: activeAlerts.filter((a) => a.severity === 'info'),
  };

  // -------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------

  return (
    <div className="flex flex-col gap-4 h-full">
      {/* Summary bar */}
      {!isLoading && (
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1.5">
            <Bell className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm text-muted-foreground">
              {t('alerts.total', { count: activeAlerts.length })}
            </span>
          </div>
          {unreadCount > 0 && (
            <Badge variant="default" className="text-xs">
              {t('alerts.unread', { count: unreadCount })}
            </Badge>
          )}
          {criticalCount > 0 && (
            <Badge variant="destructive" className="text-xs">
              {t('alerts.critical', { count: criticalCount })}
            </Badge>
          )}
        </div>
      )}

      {/* Loading skeleton */}
      {isLoading && (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="rounded-lg border p-4 space-y-2">
              <div className="flex items-start gap-3">
                <Skeleton className="h-5 w-5 rounded" />
                <div className="flex-1 space-y-2">
                  <Skeleton className="h-4 w-2/3" />
                  <Skeleton className="h-3 w-full" />
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Empty state */}
      {!isLoading && activeAlerts.length === 0 && (
        <div className="flex-1 flex flex-col items-center justify-center text-center py-12">
          <BellOff className="h-12 w-12 text-muted-foreground/50 mb-4" />
          <h3 className="text-lg font-medium">{t('alerts.emptyTitle')}</h3>
          <p className="text-sm text-muted-foreground mt-1 max-w-sm">
            {t('alerts.emptyDescription')}
          </p>
        </div>
      )}

      {/* Alert groups */}
      {!isLoading && activeAlerts.length > 0 && (
        <div className="flex flex-col gap-6 overflow-y-auto flex-1 min-h-0 pb-2">
          {(Object.entries(groupedAlerts) as [AlertSeverity, DocumentAlert[]][]).map(
            ([severity, items]) => {
              if (items.length === 0) return null;
              const config = SEVERITY_CONFIG[severity];

              return (
                <div key={severity}>
                  {/* Group header */}
                  <div className="flex items-center gap-2 mb-2">
                    <config.icon className={`h-4 w-4 ${config.textColor}`} />
                    <span className={`text-sm font-medium ${config.textColor}`}>
                      {t(`alerts.severity.${severity}`)}
                    </span>
                    <Badge variant={config.badgeVariant} className="text-[10px] h-5">
                      {items.length}
                    </Badge>
                  </div>

                  {/* Alert cards */}
                  <div className="space-y-2">
                    {items.map((alert) => {
                      const title = getTitle(alert);
                      const message = getMessage(alert);

                      return (
                        <Card
                          key={alert.id}
                          className={`border ${config.borderColor} ${config.bgColor} ${
                            !alert.is_read ? 'ring-1 ring-primary/20' : ''
                          }`}
                        >
                          <CardContent className="p-4">
                            <div className="flex items-start gap-3">
                              <config.icon
                                className={`h-5 w-5 mt-0.5 shrink-0 ${config.textColor}`}
                              />

                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2">
                                  <p className="text-sm font-medium">{title}</p>
                                  {!alert.is_read && (
                                    <span className="h-2 w-2 rounded-full bg-primary shrink-0" />
                                  )}
                                </div>
                                <p className="text-sm text-muted-foreground mt-1">
                                  {message}
                                </p>
                                <div className="flex items-center gap-3 mt-2">
                                  <span className="text-[10px] text-muted-foreground">
                                    {alert.trigger_date ? formatDate(alert.trigger_date, locale) : ''}
                                  </span>

                                  {alert.suggested_action && (
                                    <Button
                                      variant="link"
                                      size="sm"
                                      className="h-auto p-0 text-xs"
                                      onClick={() => handleActionClick(alert)}
                                    >
                                      {ACTION_LABELS[alert.suggested_action]?.[locale]
                                        || alert.suggested_action}
                                      <ChevronRight className="ml-1 h-3 w-3" />
                                    </Button>
                                  )}
                                </div>
                              </div>

                              {/* Actions */}
                              <div className="flex items-center gap-1 shrink-0">
                                {!alert.is_read && (
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    className="h-7 w-7"
                                    onClick={() => handleMarkRead(alert.id)}
                                    title={t('alerts.markRead')}
                                  >
                                    <Check className="h-3.5 w-3.5" />
                                  </Button>
                                )}
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  className="h-7 w-7 text-muted-foreground hover:text-destructive"
                                  onClick={() => handleDismiss(alert.id)}
                                  title={t('alerts.dismiss')}
                                >
                                  <X className="h-3.5 w-3.5" />
                                </Button>
                              </div>
                            </div>
                          </CardContent>
                        </Card>
                      );
                    })}
                  </div>
                </div>
              );
            }
          )}
        </div>
      )}
    </div>
  );
}
