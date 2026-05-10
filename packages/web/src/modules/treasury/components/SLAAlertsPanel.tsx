'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { AlertTriangle, Clock, TrendingDown, TrendingUp, Timer } from 'lucide-react';
import type { SLAAlertItem, SLAComplianceData } from '../types';

const MAX_DISPLAY = 5;

interface SLAAlertsPanelProps {
  alerts: SLAAlertItem[];
  compliance?: SLAComplianceData;
  t: (key: string, params?: Record<string, string | number>) => string;
}

function getSLABadge(status: string, t: SLAAlertsPanelProps['t']) {
  switch (status) {
    case 'breached':
      return <Badge variant="destructive" className="text-xs">{t('overview.slaBreached')}</Badge>;
    case 'critical':
      return <Badge className="text-xs bg-orange-500 hover:bg-orange-600">{t('overview.slaCritical')}</Badge>;
    case 'warning':
      return <Badge className="text-xs bg-yellow-500 hover:bg-yellow-600 text-black">{t('overview.slaWarning')}</Badge>;
    default:
      return <Badge variant="secondary" className="text-xs">{t('overview.slaOk')}</Badge>;
  }
}

function formatTimeRemaining(hours: number, t: SLAAlertsPanelProps['t']): string {
  if (hours <= 0) return t('overview.timeExpired');
  if (hours < 1) return `${Math.round(hours * 60)}min`;
  return `${hours.toFixed(1)}h`;
}

function formatAmount(amount: number, currency: string): string {
  return new Intl.NumberFormat('es-GQ', {
    style: 'currency',
    currency: currency,
    maximumFractionDigits: 0,
  }).format(amount);
}

export function SLAAlertsPanel({ alerts, compliance, t }: SLAAlertsPanelProps) {
  const breachedCount = alerts.filter(a => a.slaStatus === 'breached').length;
  const criticalCount = alerts.filter(a => a.slaStatus === 'critical').length;
  const displayAlerts = alerts.slice(0, MAX_DISPLAY);
  const remaining = alerts.length - MAX_DISPLAY;

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-orange-500" />
            <CardTitle className="text-base">{t('overview.slaAlerts')}</CardTitle>
          </div>
          <div className="flex gap-2">
            {breachedCount > 0 && (
              <Badge variant="destructive" className="text-xs">
                {t('overview.breachedCount', { count: breachedCount })}
              </Badge>
            )}
            {criticalCount > 0 && (
              <Badge className="text-xs bg-orange-500">
                {t('overview.criticalCount', { count: criticalCount })}
              </Badge>
            )}
            {alerts.length === 0 && (
              <Badge variant="secondary" className="text-xs">
                {t('overview.noAlerts')}
              </Badge>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-2">
        {/* Historical SLA Compliance Summary */}
        {compliance && compliance.totalValidated > 0 && (
          <div className="rounded-md border p-2 space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-muted-foreground">
                {t('overview.slaCompliance')}
              </span>
              <span className={`text-sm font-bold ${compliance.compliancePct >= 80 ? 'text-green-600' : compliance.compliancePct >= 50 ? 'text-orange-600' : 'text-red-600'}`}>
                {t('overview.complianceRate', { pct: compliance.compliancePct })}
              </span>
            </div>
            {/* Compliance bar */}
            <div className="w-full h-1.5 bg-muted rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all ${compliance.compliancePct >= 80 ? 'bg-green-500' : compliance.compliancePct >= 50 ? 'bg-orange-500' : 'bg-red-500'}`}
                style={{ width: `${Math.min(compliance.compliancePct, 100)}%` }}
              />
            </div>
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <div className="flex items-center gap-1">
                <TrendingUp className="h-3 w-3 text-green-500" />
                <span>{t('overview.totalValidated', { count: compliance.withinSla })}</span>
              </div>
              {compliance.slaBreached > 0 && (
                <div className="flex items-center gap-1">
                  <TrendingDown className="h-3 w-3 text-red-500" />
                  <span>{t('overview.slaBreachedCount', { count: compliance.slaBreached })}</span>
                </div>
              )}
            </div>
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Timer className="h-3 w-3" />
              <span>{t('overview.avgProcessingTime')}: {t('overview.hours', { value: compliance.avgHours })}</span>
              {compliance.currentlyPending > 0 && (
                <>
                  <span className="text-muted-foreground">·</span>
                  <span className="text-orange-600 font-medium">
                    {t('overview.pendingNow', { count: compliance.currentlyPending })}
                  </span>
                </>
              )}
            </div>
          </div>
        )}

        {compliance && compliance.totalValidated === 0 && (
          <p className="text-xs text-muted-foreground text-center py-1">
            {t('overview.noValidations')}
          </p>
        )}

        {/* Active SLA Alerts */}
        {alerts.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-4" role="status">
            {t('overview.allWithinSLA')}
          </p>
        ) : (
          <div className="space-y-2">
            {displayAlerts.map(alert => (
              <div
                key={alert.paymentId}
                className="flex items-center justify-between p-2 rounded-md border"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    {getSLABadge(alert.slaStatus, t)}
                    <span className="text-sm font-medium truncate" title={alert.paymentReference}>
                      {alert.paymentReference}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="text-xs text-muted-foreground truncate" title={alert.userName}>
                      {alert.userName}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      &middot; {alert.paymentMethod}
                    </span>
                  </div>
                </div>
                <div className="text-right ml-2 flex-shrink-0">
                  <p className="text-sm font-medium">
                    {formatAmount(alert.amount, alert.currency)}
                  </p>
                  <div className="flex items-center gap-1 justify-end">
                    <Clock className="h-3 w-3 text-muted-foreground" />
                    <span className={`text-xs ${alert.hoursRemaining <= 0 ? 'text-red-500 font-medium' : 'text-muted-foreground'}`}>
                      {formatTimeRemaining(alert.hoursRemaining, t)}
                    </span>
                  </div>
                </div>
              </div>
            ))}
            {remaining > 0 && (
              <p className="text-xs text-muted-foreground text-center">
                {t('overview.moreItems', { count: remaining })}
              </p>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
