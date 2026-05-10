'use client';

/**
 * Workload Overview Tab - Alerts + entity summary + agent workload table.
 * All text from useTranslations('admin.agents').
 *
 * @module agents-admin/components
 */

import { useState, useMemo } from 'react';
import { useTranslations } from 'next-intl';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table';
import { Skeleton } from '@/components/ui/skeleton';
import { Activity, Building2, Users, ChevronLeft, ChevronRight } from 'lucide-react';
import type { AgentProfile, AdminAlertsDashboard } from '../types';
import { AdminAlertsPanel } from './AdminAlertsPanel';

interface WorkloadOverviewTabProps {
  agents: AgentProfile[];
  agentsLoading: boolean;
  dashboard?: AdminAlertsDashboard;
  dashboardLoading: boolean;
  onViewAgent?: (agentId: string) => void;
}

export function WorkloadOverviewTab({
  agents, agentsLoading, dashboard, dashboardLoading, onViewAgent,
}: WorkloadOverviewTabProps) {
  const t = useTranslations('admin.agents');
  const tCommon = useTranslations('common');

  const [wlPage, setWlPage] = useState(1);
  const [wlPageSize, setWlPageSize] = useState(10);

  const activeAgents = agents
    .filter(a => a.is_active)
    .sort((a, b) => (b.capacity_percentage ?? 0) - (a.capacity_percentage ?? 0));

  const wlTotalPages = Math.max(1, Math.ceil(activeAgents.length / wlPageSize));
  const paginatedWorkload = useMemo(() => {
    const start = (wlPage - 1) * wlPageSize;
    return activeAgents.slice(start, start + wlPageSize);
  }, [activeAgents, wlPage, wlPageSize]);

  const getCapacityColor = (pct: number) => pct >= 80 ? 'text-red-600' : pct >= 60 ? 'text-yellow-600' : 'text-green-600';
  const getCapacityBg = (pct: number) => pct >= 80 ? 'bg-red-50' : pct >= 60 ? 'bg-yellow-50' : '';

  const availabilityMap: Record<string, { key: string; variant: 'default' | 'secondary' | 'destructive' | 'outline' }> = {
    available: { key: 'availability.available', variant: 'default' },
    on_leave: { key: 'availability.onLeave', variant: 'secondary' },
    sick_leave: { key: 'availability.sickLeave', variant: 'destructive' },
    training: { key: 'availability.training', variant: 'outline' },
    mission: { key: 'availability.mission', variant: 'outline' },
    temporarily_unavailable: { key: 'availability.temporarilyUnavailable', variant: 'secondary' },
  };

  const getAvailabilityLabel = (avail?: string) => {
    const config = availabilityMap[avail || 'available'];
    if (!config) return { text: avail || '-', variant: 'outline' as const };
    return { text: t(config.key), variant: config.variant };
  };

  const workloadStatusMap: Record<string, string> = {
    overloaded: 'status.overloaded', busy: 'status.busy', normal: 'status.normal',
    unavailable: 'status.unavailable', available: 'status.available',
  };

  return (
    <div className="space-y-4">
      <AdminAlertsPanel dashboard={dashboard} isLoading={dashboardLoading} />

      {/* Entity Summary */}
      {dashboard?.workload_by_entity && dashboard.workload_by_entity.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Building2 className="h-4 w-4" />
              {t('workload.entitySummary')}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-3 grid-cols-1 md:grid-cols-2 lg:grid-cols-3">
              {dashboard.workload_by_entity.map((entity) => (
                <div key={entity.entity_code} className="flex items-center justify-between p-3 border rounded-lg">
                  <div>
                    <div className="font-medium text-sm">{entity.entity_name || entity.entity_code}</div>
                    <div className="text-xs text-muted-foreground">
                      {t('workload.agentCount', { count: entity.agent_count })} · {t('workload.caseCount', { count: entity.total_assignments ?? 0 })}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className={`text-sm font-bold ${getCapacityColor(entity.avg_capacity)}`}>{entity.avg_capacity}%</div>
                    {entity.overloaded_count > 0 && (
                      <Badge variant="destructive" className="text-[10px] px-1.5 py-0">
                        {t('workload.overloadedCount', { count: entity.overloaded_count })}
                      </Badge>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Agent Workload Table */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-5 w-5" />
            {t('workload.agentWorkload')}
          </CardTitle>
          <CardDescription>
            {t('workload.activeAgentsSorted', { count: activeAgents.length })}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {agentsLoading ? (
            <div className="space-y-2">{[...Array(5)].map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}</div>
          ) : activeAgents.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
              <Users className="h-12 w-12 mb-4 opacity-50" />
              <p>{t('workload.noActiveAgents')}</p>
            </div>
          ) : (
            <div className="border rounded-md overflow-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t('table.agent')}</TableHead>
                    <TableHead>{t('table.entity')}</TableHead>
                    <TableHead className="w-[200px]">{t('table.capacity')}</TableHead>
                    <TableHead className="text-center">{t('table.cases')}</TableHead>
                    <TableHead>{t('table.availability')}</TableHead>
                    <TableHead>{t('table.status')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {paginatedWorkload.map((agent) => {
                    const capacity = agent.capacity_percentage ?? 0;
                    const availConfig = getAvailabilityLabel(agent.availability as string);
                    const statusKey = workloadStatusMap[agent.workload_status || 'available'] || 'status.available';
                    return (
                      <TableRow
                        key={agent.id}
                        className={`${getCapacityBg(capacity)} cursor-pointer hover:bg-muted/50`}
                        onClick={() => onViewAgent?.(agent.id)}
                      >
                        <TableCell>
                          <div>
                            <div className="font-medium text-sm">{agent.user_full_name || 'N/A'}</div>
                            <div className="text-xs text-muted-foreground">{agent.user_email}</div>
                          </div>
                        </TableCell>
                        <TableCell><span className="text-sm">{agent.entity_name || agent.ministry_name || '-'}</span></TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <Progress value={capacity} className="h-2 flex-1" />
                            <span className={`text-xs font-medium w-10 text-right ${getCapacityColor(capacity)}`}>{capacity}%</span>
                          </div>
                        </TableCell>
                        <TableCell className="text-center"><span className="text-sm font-medium">{agent.current_assignments ?? 0}</span></TableCell>
                        <TableCell><Badge variant={availConfig.variant}>{availConfig.text}</Badge></TableCell>
                        <TableCell>
                          <Badge variant={agent.workload_status === 'overloaded' ? 'destructive' : agent.workload_status === 'busy' ? 'secondary' : 'outline'}>
                            {t(statusKey)}
                          </Badge>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          )}
          {/* Workload Pagination */}
          {activeAgents.length > 0 && (
            <div className="flex items-center justify-between pt-4">
              <span className="text-sm text-muted-foreground">
                {tCommon('showing')} {(wlPage - 1) * wlPageSize + 1}-{Math.min(wlPage * wlPageSize, activeAgents.length)} {tCommon('of')} {activeAgents.length}
              </span>
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-2">
                  <span className="text-sm text-muted-foreground">{tCommon('rowsPerPage')}</span>
                  <Select value={String(wlPageSize)} onValueChange={(v) => { setWlPageSize(Number(v)); setWlPage(1); }}>
                    <SelectTrigger className="h-8 w-[70px]">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent side="top">
                      {[10, 20, 30].map((s) => (
                        <SelectItem key={s} value={String(s)}>{s}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <span className="text-sm text-muted-foreground">
                  {tCommon('page')} {wlPage} {tCommon('of')} {wlTotalPages}
                </span>
                <div className="flex items-center gap-1">
                  <Button variant="outline" size="icon" className="h-8 w-8" onClick={() => setWlPage(p => Math.max(1, p - 1))} disabled={wlPage === 1}>
                    <ChevronLeft className="h-4 w-4" />
                  </Button>
                  <Button variant="outline" size="icon" className="h-8 w-8" onClick={() => setWlPage(p => Math.min(wlTotalPages, p + 1))} disabled={wlPage === wlTotalPages}>
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export default WorkloadOverviewTab;
