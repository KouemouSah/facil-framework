'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Activity, CheckCircle, XCircle, ArrowUpCircle } from 'lucide-react';
import type { RecentActivityItem } from '../types';

const MAX_DISPLAY = 5;

interface RecentActivityTimelineProps {
  activities: RecentActivityItem[];
  t: (key: string, params?: Record<string, string | number>) => string;
}

function getActionIcon(action: string) {
  switch (action) {
    case 'approve': return <CheckCircle className="h-4 w-4 text-green-500" />;
    case 'reject': return <XCircle className="h-4 w-4 text-red-500" />;
    case 'escalate': return <ArrowUpCircle className="h-4 w-4 text-orange-500" />;
    default: return <Activity className="h-4 w-4 text-blue-500" />;
  }
}

function getActionLabel(action: string, t: RecentActivityTimelineProps['t']): string {
  switch (action) {
    case 'approve': return t('overview.actionApprove');
    case 'reject': return t('overview.actionReject');
    case 'escalate': return t('overview.actionEscalate');
    case 'lock_for_review': return t('overview.actionReview');
    case 'unlock_release': return t('overview.actionRelease');
    case 'request_documents': return t('overview.actionDocs');
    default: return action;
  }
}

function formatRelativeTime(dateStr: string | null, t: RecentActivityTimelineProps['t']): string {
  if (!dateStr) return '';
  const date = new Date(dateStr);
  if (isNaN(date.getTime())) return '';
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return t('overview.timeNow');
  if (diffMin < 60) return `${t('overview.timeAgo')} ${diffMin}min`;
  const diffHours = Math.floor(diffMin / 60);
  if (diffHours < 24) return `${t('overview.timeAgo')} ${diffHours}h`;
  const diffDays = Math.floor(diffHours / 24);
  return `${t('overview.timeAgo')} ${diffDays}d`;
}

function formatAmount(amount: number, currency: string): string {
  return new Intl.NumberFormat('es-GQ', {
    style: 'currency',
    currency: currency,
    maximumFractionDigits: 0,
  }).format(amount);
}

export function RecentActivityTimeline({ activities, t }: RecentActivityTimelineProps) {
  const displayActivities = activities.slice(0, MAX_DISPLAY);
  const remaining = activities.length - MAX_DISPLAY;

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center gap-2">
          <Activity className="h-4 w-4 text-muted-foreground" />
          <CardTitle className="text-base">{t('overview.recentActivity')}</CardTitle>
        </div>
      </CardHeader>
      <CardContent>
        {activities.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-4" role="status">
            {t('overview.noRecentActivity')}
          </p>
        ) : (
          <div className="space-y-3">
            {displayActivities.map((activity) => (
              // F3: Use composite key instead of array index
              <div key={`${activity.paymentReference}-${activity.createdAt}`} className="flex items-start gap-3">
                <div className="mt-0.5" title={getActionLabel(activity.action, t)}>
                  {getActionIcon(activity.action)}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium" title={activity.agentName}>
                        {activity.agentName}
                      </span>
                      <Badge variant="outline" className="text-xs h-5">
                        {getActionLabel(activity.action, t)}
                      </Badge>
                    </div>
                    <span className="text-xs text-muted-foreground flex-shrink-0">
                      {formatRelativeTime(activity.createdAt, t)}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-xs text-muted-foreground mt-0.5">
                    {/* F6: Truncated reference with title tooltip */}
                    <span className="truncate" title={activity.paymentReference}>
                      {activity.paymentReference}
                    </span>
                    <span>&middot;</span>
                    <span className="flex-shrink-0">{formatAmount(activity.amount, activity.currency)}</span>
                    <span>&middot;</span>
                    <span className="flex-shrink-0">{activity.paymentMethod}</span>
                  </div>
                  {activity.comment && (
                    <p className="text-xs text-muted-foreground mt-1 italic truncate" title={activity.comment}>
                      &ldquo;{activity.comment}&rdquo;
                    </p>
                  )}
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
