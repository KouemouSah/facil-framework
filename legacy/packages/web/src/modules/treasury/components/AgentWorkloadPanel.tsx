'use client';

import { useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Users } from 'lucide-react';
import type { AgentLoadItem } from '../types';

const MAX_DISPLAY = 5;

interface AgentWorkloadPanelProps {
  agents: AgentLoadItem[];
  t: (key: string, params?: Record<string, string | number>) => string;
}

function getStatusColor(status: string): string {
  switch (status) {
    case 'available': return 'bg-green-500';
    case 'normal': return 'bg-blue-500';
    case 'busy': return 'bg-yellow-500';
    case 'overloaded': return 'bg-red-500';
    case 'unavailable': return 'bg-gray-400';
    default: return 'bg-gray-400';
  }
}

function getStatusLabel(status: string, t: AgentWorkloadPanelProps['t']): string {
  switch (status) {
    case 'available': return t('overview.statusAvailable');
    case 'normal': return t('overview.statusNormal');
    case 'busy': return t('overview.statusBusy');
    case 'overloaded': return t('overview.statusOverloaded');
    case 'unavailable': return t('overview.statusUnavailable');
    default: return status;
  }
}

export function AgentWorkloadPanel({ agents, t }: AgentWorkloadPanelProps) {
  const totalPending = agents.reduce((s, a) => s + a.pending, 0);
  const totalCompleted = agents.reduce((s, a) => s + a.completedToday, 0);

  // F4: Sort by capacityPct DESC to show most burdened agents first
  const sortedAgents = useMemo(
    () => [...agents].sort((a, b) => b.capacityPct - a.capacityPct),
    [agents]
  );
  const displayAgents = sortedAgents.slice(0, MAX_DISPLAY);
  const remaining = agents.length - MAX_DISPLAY;

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Users className="h-4 w-4 text-muted-foreground" />
            <CardTitle className="text-base">{t('overview.agentWorkload')}</CardTitle>
          </div>
          <div className="flex gap-3 text-xs text-muted-foreground">
            <span>{totalPending} {t('overview.pending')}</span>
            <span>{totalCompleted} {t('overview.today')}</span>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {agents.length === 0 && (
          <p className="text-sm text-muted-foreground text-center py-4" role="status">
            {t('overview.noActiveAgents')}
          </p>
        )}
        {displayAgents.map(agent => (
          <div key={agent.agentProfileId} className="flex items-center gap-3">
            {/* F6: Status dot with accessible title */}
            <div
              className={`h-2 w-2 rounded-full flex-shrink-0 ${getStatusColor(agent.status)}`}
              title={getStatusLabel(agent.status, t)}
            />
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between mb-1">
                {/* F6: Truncated name with title tooltip */}
                <span className="text-sm font-medium truncate" title={agent.agentName}>
                  {agent.agentName}
                </span>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <Badge variant="outline" className="text-xs h-5">
                    {agent.pending} {t('overview.pendShort')}
                  </Badge>
                  <Badge variant="secondary" className="text-xs h-5">
                    {agent.completedToday} {t('overview.todayShort')}
                  </Badge>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Progress
                  value={Math.min(agent.capacityPct, 100)}
                  className={`h-1.5 flex-1 ${agent.capacityPct >= 80 ? '[&>div]:bg-red-500' : agent.capacityPct >= 60 ? '[&>div]:bg-yellow-500' : '[&>div]:bg-green-500'}`}
                />
                <span className="text-xs text-muted-foreground w-10 text-right">
                  {agent.capacityPct}%
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
      </CardContent>
    </Card>
  );
}
