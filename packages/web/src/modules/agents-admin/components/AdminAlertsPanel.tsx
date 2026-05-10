'use client';

/**
 * Admin Alerts Panel - Aggregated alert indicators for agent management.
 * All text from useTranslations('admin.agents.alerts').
 * LLM briefing rendered as markdown.
 *
 * @module agents-admin/components
 */

import { useState } from 'react';
import { useTranslations } from 'next-intl';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Card, CardContent } from '@/components/ui/card';
import {
  AlertTriangle, UserX, Gauge, Lock, Clock,
  ChevronDown, ChevronUp, CheckCircle2, Sparkles,
} from 'lucide-react';
import { renderMarkdown } from '@/core/utils/markdown';
import type { AdminAlertsDashboard } from '../types';

interface AdminAlertsPanelProps {
  dashboard?: AdminAlertsDashboard;
  isLoading: boolean;
}

export function AdminAlertsPanel({ dashboard, isLoading }: AdminAlertsPanelProps) {
  const [expanded, setExpanded] = useState(false);
  const t = useTranslations('admin.agents.alerts');

  if (isLoading) return <Skeleton className="h-16 w-full" />;
  if (!dashboard) return null;

  const totalAlerts = dashboard.total_alerts ?? 0;
  const hasCritical = (dashboard.sla_at_risk_count ?? 0) > 0 || (dashboard.overloaded_count ?? 0) > 0;

  if (totalAlerts === 0) {
    return (
      <div className="space-y-3">
        {dashboard.llm_briefing && (
          <Card className="border-blue-200 bg-blue-50/50">
            <CardContent className="py-3 px-4">
              <div className="flex items-start gap-2">
                <Sparkles className="h-4 w-4 text-blue-500 mt-0.5 shrink-0" />
                <div
                  className="text-sm text-blue-900 prose prose-sm max-w-none"
                  dangerouslySetInnerHTML={{ __html: renderMarkdown(dashboard.llm_briefing) }}
                />
              </div>
            </CardContent>
          </Card>
        )}
        <Alert className="border-green-300 bg-green-50/50">
          <CheckCircle2 className="h-4 w-4 text-green-600" />
          <AlertTitle className="text-green-800 text-sm">{t('allNormal')}</AlertTitle>
          <AlertDescription className="text-green-700 text-xs">{t('allNormalDesc')}</AlertDescription>
        </Alert>
      </div>
    );
  }

  const alertItems = [
    {
      key: 'inactive', count: dashboard.inactive_count ?? 0, icon: UserX,
      label: t('inactiveAgents'), color: 'text-orange-600', bgColor: 'bg-orange-100',
      details: dashboard.inactive_agents?.map(a => a.agent_name).join(', '),
    },
    {
      key: 'overloaded', count: dashboard.overloaded_count ?? 0, icon: Gauge,
      label: t('overloadedAgents'), color: 'text-red-600', bgColor: 'bg-red-100',
      details: dashboard.overloaded_agents?.map(a => `${a.agent_name} (${a.capacity_percentage}%)`).join(', '),
    },
    {
      key: 'stale_locks', count: dashboard.stale_locks_count ?? 0, icon: Lock,
      label: t('staleLocks'), color: 'text-orange-600', bgColor: 'bg-orange-100',
      details: dashboard.stale_locks?.map(l => `${l.payment_reference} (${(l.locked_hours ?? 0).toFixed(1)}h)`).join(', '),
    },
    {
      key: 'sla_at_risk', count: dashboard.sla_at_risk_count ?? 0, icon: Clock,
      label: t('slaAtRisk'), color: 'text-red-600', bgColor: 'bg-red-100',
      details: dashboard.sla_at_risk?.map(s => `${s.payment_reference} (${(s.hours_remaining ?? 0).toFixed(0)}h)`).join(', '),
    },
  ];

  const okLabels: Record<string, string> = {
    sla_at_risk: t('slaOk'), overloaded: t('capacityOk'),
    stale_locks: t('locksOk'), inactive: t('activityOk'),
  };

  const activeAlerts = alertItems.filter(a => a.count > 0);

  return (
    <div className="space-y-3">
      {dashboard.llm_briefing && (
        <Card className={
          dashboard.llm_priority === 'urgent' ? 'border-red-200 bg-red-50/50' :
          dashboard.llm_priority === 'attention' ? 'border-orange-200 bg-orange-50/50' :
          'border-blue-200 bg-blue-50/50'
        }>
          <CardContent className="py-3 px-4">
            <div className="flex items-start gap-2">
              <Sparkles className={`h-4 w-4 mt-0.5 shrink-0 ${
                dashboard.llm_priority === 'urgent' ? 'text-red-500' :
                dashboard.llm_priority === 'attention' ? 'text-orange-500' : 'text-blue-500'
              }`} />
              <div
                className={`text-sm prose prose-sm max-w-none ${
                  dashboard.llm_priority === 'urgent' ? 'text-red-900' :
                  dashboard.llm_priority === 'attention' ? 'text-orange-900' : 'text-blue-900'
                }`}
                dangerouslySetInnerHTML={{ __html: renderMarkdown(dashboard.llm_briefing) }}
              />
            </div>
          </CardContent>
        </Card>
      )}
      <Alert variant={hasCritical ? 'destructive' : 'default'} className={hasCritical ? 'border-red-300 bg-red-50/50' : 'border-orange-300 bg-orange-50/50'}>
        <AlertTriangle className="h-4 w-4" />
        <AlertTitle className="flex items-center justify-between">
          <span className="text-sm">{t('alertsActive', { count: totalAlerts })}</span>
          {activeAlerts.length > 0 && (
            <Button variant="ghost" size="sm" className="h-6 px-2" onClick={() => setExpanded(!expanded)}>
              {expanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
            </Button>
          )}
        </AlertTitle>
        <AlertDescription>
          <div className="flex flex-wrap gap-2 mt-1">
            {alertItems.map((item) => {
              const Icon = item.icon;
              return (
                <Badge key={item.key} variant={item.count > 0 ? 'secondary' : 'outline'}
                  className={item.count > 0 ? `${item.bgColor} ${item.color} border-0` : 'text-green-600'}>
                  <Icon className="h-3 w-3 mr-1" />
                  {item.count > 0 ? `${item.count} ${item.label}` : okLabels[item.key]}
                </Badge>
              );
            })}
          </div>
          {expanded && (
            <div className="mt-3 space-y-2 text-xs">
              {activeAlerts.map((item) => (
                <div key={item.key} className={`${item.color} pl-2 border-l-2`} style={{ borderColor: 'currentColor' }}>
                  <span className="font-medium">{item.label}:</span>{' '}
                  <span className="text-muted-foreground">{item.details || t('noDetails')}</span>
                </div>
              ))}
            </div>
          )}
        </AlertDescription>
      </Alert>
    </div>
  );
}

export default AdminAlertsPanel;
