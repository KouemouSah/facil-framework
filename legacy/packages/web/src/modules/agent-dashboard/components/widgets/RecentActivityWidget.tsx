/**
 * RecentActivityWidget
 * Displays recent agent actions from the audit trail
 *
 * @module agent-dashboard/components/widgets
 * @date 2026-02-22
 */

'use client';

import React from 'react';
import { useLocale, useTranslations } from 'next-intl';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Activity, CheckCircle, XCircle, Eye, Clock } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import apiClient from '@/core/api/client';
import type { EntityCode } from '../../types';

interface RecentActivityWidgetProps {
  entityCode?: EntityCode;
  limit?: number;
  className?: string;
}

interface ActivityItem {
  id: string;
  action_type: string;
  item_type: string;
  reference: string;
  created_at: string;
}

const ACTION_ICONS: Record<string, React.ReactNode> = {
  approve: <CheckCircle className="h-4 w-4 text-green-500" />,
  reject: <XCircle className="h-4 w-4 text-red-500" />,
  lock_for_review: <Eye className="h-4 w-4 text-blue-500" />,
  default: <Activity className="h-4 w-4 text-gray-500" />,
};

function getActionIcon(actionType: string): React.ReactNode {
  return ACTION_ICONS[actionType] || ACTION_ICONS.default;
}

function formatTimeAgo(dateStr: string, locale: string = 'es'): string {
  try {
    const now = Date.now();
    const date = new Date(dateStr).getTime();
    const diffSec = Math.floor((now - date) / 1000);
    const rtf = new Intl.RelativeTimeFormat(locale, { numeric: 'auto', style: 'short' });
    if (diffSec < 60) return rtf.format(-diffSec, 'second');
    const diffMin = Math.floor(diffSec / 60);
    if (diffMin < 60) return rtf.format(-diffMin, 'minute');
    const diffH = Math.floor(diffMin / 60);
    if (diffH < 24) return rtf.format(-diffH, 'hour');
    const diffD = Math.floor(diffH / 24);
    return rtf.format(-diffD, 'day');
  } catch {
    return dateStr;
  }
}

export function RecentActivityWidget({
  limit = 5,
  className,
}: RecentActivityWidgetProps) {
  const t = useTranslations('agent');
  const locale = useLocale();

  const { data, isLoading } = useQuery<ActivityItem[]>({
    queryKey: ['widget', 'recent-activity'],
    queryFn: async () => {
      try {
        const response = await apiClient.get<ActivityItem[]>(
          '/agent/service-requests/dashboard/widgets/recent-activity',
          { params: { limit } }
        );
        return response.data;
      } catch {
        // Endpoint may not exist yet — return empty
        return [];
      }
    },
    staleTime: 60 * 1000,
    refetchInterval: 2 * 60 * 1000,
  });

  if (isLoading) {
    return (
      <Card className={className}>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <Activity className="h-5 w-5 text-violet-600" />
            {t('widgets.recentActivity', { defaultValue: 'Actividad Reciente' })}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  const items = data || [];

  return (
    <Card className={className}>
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <Activity className="h-5 w-5 text-violet-600" />
          {t('widgets.recentActivity', { defaultValue: 'Actividad Reciente' })}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {items.length === 0 ? (
          <div className="text-center py-6 text-muted-foreground">
            <Activity className="h-8 w-8 mx-auto mb-2 opacity-50" />
            <p className="text-sm">
              {t('widgets.noRecentActivity', { defaultValue: 'Sin actividad reciente' })}
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {items.map((item) => (
              <div
                key={item.id}
                className="flex items-center gap-3 p-2 rounded-lg hover:bg-muted/50"
              >
                {getActionIcon(item.action_type)}
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">
                    {item.reference}
                  </p>
                  <p className="text-xs text-muted-foreground capitalize">
                    {item.action_type.replace(/_/g, ' ')}
                  </p>
                </div>
                <span className="text-xs text-muted-foreground flex items-center gap-1">
                  <Clock className="h-3 w-3" />
                  {formatTimeAgo(item.created_at, locale)}
                </span>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default RecentActivityWidget;
