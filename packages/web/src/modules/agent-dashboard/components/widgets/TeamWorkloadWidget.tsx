/**
 * TeamWorkloadWidget
 * Displays team workload overview for supervisors
 * Uses v_agents_workload_dashboard database view
 *
 * @module agent-dashboard/components/widgets
 * @date 2026-01-26
 */

'use client';

import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Progress } from '@/components/ui/progress';
import { useTranslations } from 'next-intl';
import {
  Users,
  UserCheck,
  AlertTriangle,
  Activity,
} from 'lucide-react';
import { useTeamWorkload } from '../../hooks/useWidgetData';
import type { EntityCode } from '../../types';
import type { TeamMemberWorkload } from '../../hooks/useWidgetData';

// =============================================================================
// PROPS
// =============================================================================

interface TeamWorkloadWidgetProps {
  entityCode: EntityCode;
  maxMembers?: number;
  className?: string;
}

// =============================================================================
// CONSTANTS
// =============================================================================

const LOAD_LEVEL_COLORS: Record<string, string> = {
  low: 'bg-green-100 text-green-800',
  normal: 'bg-blue-100 text-blue-800',
  high: 'bg-orange-100 text-orange-800',
  critical: 'bg-red-100 text-red-800',
};

const LOAD_LEVEL_PROGRESS: Record<string, string> = {
  low: '[&>div]:bg-green-500',
  normal: '[&>div]:bg-blue-500',
  high: '[&>div]:bg-orange-500',
  critical: '[&>div]:bg-red-500',
};

// =============================================================================
// COMPONENT
// =============================================================================

export function TeamWorkloadWidget({
  entityCode,
  maxMembers = 5,
  className,
}: TeamWorkloadWidgetProps) {
  const t = useTranslations('agent');
  const { data, isLoading, isError } = useTeamWorkload(entityCode);

  // Loading state
  if (isLoading) {
    return (
      <Card className={className}>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <Users className="h-5 w-5 text-purple-600" />
            {t('widgets.teamWorkload', { defaultValue: 'Carga del Equipo' })}
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
            <Users className="h-5 w-5 text-purple-600" />
            {t('widgets.teamWorkload', { defaultValue: 'Carga del Equipo' })}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            {t('widgets.teamLoadError', { defaultValue: 'Error al cargar datos del equipo' })}
          </p>
        </CardContent>
      </Card>
    );
  }

  const {
    members = [],
    available_agents = 0,
    overloaded_agents = 0,
    avg_capacity,
  } = data || {};

  const displayMembers = members.slice(0, maxMembers);

  return (
    <Card className={className}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base flex items-center gap-2">
            <Users className="h-5 w-5 text-purple-600" />
            {t('widgets.teamWorkload', { defaultValue: 'Carga del Equipo' })}
          </CardTitle>
          <div className="flex gap-1">
            <Badge className="bg-green-100 text-green-800 text-xs">
              <UserCheck className="h-3 w-3 mr-1" />
              {available_agents}
            </Badge>
            {overloaded_agents > 0 && (
              <Badge className="bg-red-100 text-red-800 text-xs">
                <AlertTriangle className="h-3 w-3 mr-1" />
                {overloaded_agents}
              </Badge>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {members.length === 0 ? (
          <div className="text-center py-6 text-muted-foreground">
            <Users className="h-8 w-8 mx-auto mb-2 opacity-50" />
            <p className="text-sm">{t('widgets.noTeamAgents', { defaultValue: 'Sin agentes en el equipo' })}</p>
          </div>
        ) : (
          <div className="space-y-4">
            {/* Summary Stats */}
            <div className="flex items-center justify-between text-sm pb-2 border-b">
              <span className="text-muted-foreground">
                {t('widgets.avgCapacity', { defaultValue: 'Capacidad promedio' })}
              </span>
              <span className="font-medium flex items-center gap-2">
                <Activity className="h-4 w-4" />
                {avg_capacity ? `${avg_capacity.toFixed(0)}%` : '--'}
              </span>
            </div>

            {/* Team Members */}
            <div className="space-y-3">
              {displayMembers.map((member) => (
                <TeamMemberRow key={member.agent_profile_id} member={member} />
              ))}
            </div>

            {/* Show more indicator */}
            {members.length > maxMembers && (
              <p className="text-xs text-center text-muted-foreground pt-2">
                +{members.length - maxMembers} {t('widgets.moreAgents', { defaultValue: 'agentes más' })}
              </p>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// =============================================================================
// TEAM MEMBER ROW
// =============================================================================

interface TeamMemberRowProps {
  member: TeamMemberWorkload;
}

function TeamMemberRow({ member }: TeamMemberRowProps) {
  const t = useTranslations('agent');
  const capacityValue = member.capacity_percentage ?? 0;
  const loadLevel = member.load_level || 'normal';

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 min-w-0">
          <span className="font-medium text-sm truncate">
            {member.full_name}
          </span>
          <Badge className={`${LOAD_LEVEL_COLORS[loadLevel]} text-xs`}>
            {member.current_assignments}/{member.max_concurrent_assignments}
          </Badge>
        </div>
        <span className="text-xs text-muted-foreground whitespace-nowrap ml-2">
          {capacityValue.toFixed(0)}%
        </span>
      </div>
      <Progress
        value={capacityValue}
        className={`h-1.5 ${LOAD_LEVEL_PROGRESS[loadLevel]}`}
      />
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>
          {member.current_month_processed} {t('widgets.processed', { defaultValue: 'procesadas' })}
        </span>
        {member.sla_respect_percentage !== null && (
          <span className={
            member.sla_respect_percentage >= 90 ? 'text-green-600' :
            member.sla_respect_percentage >= 70 ? 'text-yellow-600' : 'text-red-600'
          }>
            SLA: {member.sla_respect_percentage.toFixed(0)}%
          </span>
        )}
      </div>
    </div>
  );
}

export default TeamWorkloadWidget;
